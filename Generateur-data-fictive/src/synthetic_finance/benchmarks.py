"""Repères passifs, tirés des mêmes facteurs que les fonds (cahier des charges, § 8).

Un repère n'a ni alpha, ni bruit propre, ni saut propre : il porte les charges factorielles d'une
composition fixée d'avance et des frais passifs explicites (par classe d'actifs, `markets.benchmarks`).
- composite de chaque fonds : ses expositions J1, telles quelles ;
- politique de chaque institution : ses cibles initiales J1, rééquilibrées chaque jour, appliquées
  aux composites de ses fonds ;
- contexte : actions mondiales et équilibré, compositions de la configuration ;
- catégorie : un par catégorie d'archétypes présente dans l'univers, composition fixe de la
  configuration en style « marché large » ; c'est le repère du fonds dans le rapport (ref.repere).
Indice base 100 au premier jour ouvrable de l'horizon, en rendement total.
"""
from dataclasses import dataclass

import numpy as np

from .config import Config
from .market import Charges, Marche, charges, rendements, spec

BASE = 100.0


@dataclass
class Repere:
    benchmark_id: str
    benchmark_type: str                      # composite | policy | sensitivity | category
    name: str
    fund_id: str | None
    institution_id: str | None
    passive_fee_pct: float
    composition: str
    charges: Charges | None                  # None pour une politique (mélange de composites)
    rendements: np.ndarray                   # log, jour 0 nul
    indice: np.ndarray


def _indice(r: np.ndarray) -> np.ndarray:
    return BASE * np.exp(np.cumsum(r))


def frais_passifs(ch: Charges, taux: dict[str, float]) -> float:
    return sum(w * taux[k] for k, w in ch.classes.items())


def _cellules_contexte(composition: dict) -> tuple[list[dict], float]:
    """Cellules (poids en %) et part non couverte en devises d'un repère de contexte."""
    cellules, devises = [], 0.0
    for classe, w in composition["asset_class"].items():
        if classe == "equity":
            for g, wg in composition["equity_geography"].items():
                cellules.append(dict(asset_class="equity", geography=g, style="broad_market", weight=w * wg / 100))
                devises += w * wg / 100 if g != "canada" else 0.0
        elif classe == "other":              # actifs réels, non couverts hors du Canada
            for g, wg in composition["other_geography"].items():
                cellules.append(dict(asset_class="other", geography=g, style="other", weight=w * wg / 100))
                devises += w * wg / 100 if g != "canada" else 0.0
        elif classe == "fixed_income" and "fixed_income_geography" in composition:   # couvert : sans devises
            for g, wg in composition["fixed_income_geography"].items():
                cellules.append(dict(asset_class=classe, geography=g, style=classe, weight=w * wg / 100))
        else:
            cellules.append(dict(asset_class=classe, geography="canada", style=classe, weight=w))
    return cellules, devises


def construire_reperes(cfg: Config, marche: Marche, funds: list[dict], cellules: list[dict],
                       cibles: list[dict]) -> list[Repere]:
    m = spec(cfg)
    j = m.trading_days_per_year
    taux = m.passive_fee_pct
    reperes: list[Repere] = []
    composites: dict[str, Repere] = {}
    for f in funds:
        ch = charges([c for c in cellules if c["fund_id"] == f["fund_id"]], f["duration_years"],
                     f["fx_exposure_pct"], m)
        frais = frais_passifs(ch, taux)
        r = rendements(ch, marche, frais, j)
        b = Repere(f"R-{f['fund_id']}", "composite", f"Repère composite passif de {f['fund_id']} (fictif)",
                   f["fund_id"], None, frais, f"expositions de {f['fund_id']}", ch, r, _indice(r))
        composites[f["fund_id"]] = b
        reperes.append(b)

    institutions = sorted({l["institution_id"] for l in cibles})
    for i in institutions:
        lignes = [l for l in cibles if l["institution_id"] == i]
        premiere = min(l["effective_date"] for l in lignes)
        poids = {l["fund_id"]: l["target_weight"] / 100 for l in lignes if l["effective_date"] == premiere}
        # Mélange rééquilibré chaque jour : rendement simple = Σ w × rendement simple des composites
        simple = sum(w * np.expm1(composites[f].rendements) for f, w in poids.items())
        r = np.log1p(simple)
        frais = sum(w * composites[f].passive_fee_pct for f, w in poids.items())
        compo = " | ".join(f"{f} {w * 100:.0f} %" for f, w in poids.items())
        reperes.append(Repere(f"R-POL-{i}", "policy", f"Repère de politique — {i} (fictif)", None, i, frais,
                              f"cibles du {premiere.isoformat()} : {compo}", None, r, _indice(r)))

    for cle, ident, nom in (("global_equity", "R-ACT-MONDE", "Repère actions mondiales (fictif)"),
                            ("balanced", "R-EQUILIBRE", "Repère équilibré (fictif)")):
        composition = m.sensitivity[cle]
        cel, devises = _cellules_contexte(composition)
        ch = charges(cel, composition.get("duration_years"), devises, m)
        frais = frais_passifs(ch, taux)
        r = rendements(ch, marche, frais, j)
        compo = " | ".join(f"{k} {w:.0f} %" for k, w in composition["asset_class"].items())
        reperes.append(Repere(ident, "sensitivity", nom, None, None, frais, compo, ch, r, _indice(r)))

    presents = {f["archetype"] for f in funds}
    for cle, cat in m.categories.items():
        if not presents & set(cat["archetypes"]):
            continue
        cel, devises = _cellules_contexte(cat)
        ch = charges(cel, cat.get("duration_years"), devises, m)
        frais = frais_passifs(ch, taux)
        r = rendements(ch, marche, frais, j)
        compo = " | ".join(f"{k} {w:.0f} %" for k, w in cat["asset_class"].items())
        reperes.append(Repere(categorie_id(cle), "category", f"Repère de catégorie — {cat['name']} (fictif)", None,
                              None, frais, f"{compo} ; archétypes {', '.join(cat['archetypes'])}", ch, r, _indice(r)))
    return reperes


def categorie_id(cle: str) -> str:
    return "R-CAT-" + cle.upper().replace("_", "-")


def categorie_du_fonds(cfg: Config, archetype: str) -> str:
    """Identifiant du repère de catégorie d'un archétype (la configuration garantit l'unicité)."""
    return next(categorie_id(k) for k, v in spec(cfg).categories.items() if archetype in v["archetypes"])
