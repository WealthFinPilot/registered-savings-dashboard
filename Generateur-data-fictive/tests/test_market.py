"""Moteur de marché : construction du modèle (C2) et faits stylisés sur la graine du scénario (C3).

Les mesures de C3 sont recalculées ici sur les CSV bruts, sans passer par le validateur. Chaque test
imprime ce qu'il mesure : `pytest -rA` montre les valeurs, pas seulement le verdict.
"""
import ast
import datetime as dt
import itertools
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
from conftest import GRAINE, RACINE, TYPICAL, lire

from synthetic_finance.config import charger, construire, lire_toml
from synthetic_finance.market import (FACTEURS, IF, charges, covariance, rendements, simuler_marches,
                                      transitions)
from synthetic_finance.universe import construire_univers
from synthetic_finance.validation import valider

SOURCES = [RACINE / "src" / "synthetic_finance" / f for f in ("market.py", "benchmarks.py")]


@pytest.fixture(scope="module")
def cfg():
    return charger(TYPICAL, GRAINE)


@pytest.fixture(scope="module")
def simulation(cfg):
    univers = construire_univers(cfg).tables()
    return univers, simuler_marches(cfg, univers)


def series_csv(dossier: Path, table: str, cle: str, valeur: str) -> dict[str, tuple[list[str], np.ndarray]]:
    groupes = defaultdict(list)
    for l in lire(dossier, table):
        groupes[l[cle]].append((l["date"], float(l[valeur])))
    return {k: ([d for d, _ in sorted(v)], np.array([x for _, x in sorted(v)])) for k, v in groupes.items()}


def parts_classes(dossier: Path) -> dict[str, dict[str, float]]:
    parts = defaultdict(dict)
    for l in lire(dossier, "fund_exposures_by_axis"):
        if l["axis"] == "asset_class":
            parts[l["fund_id"]][l["category"]] = float(l["weight"])
    return parts


# ================================================================================================
# C2 — construction du modèle
# ================================================================================================
def test_covariance_semi_definie_positive(cfg) -> None:
    for k, r in cfg.markets.regimes.items():
        v = np.linalg.eigvalsh(covariance(cfg.markets, r))
        print(f"{k:<15} plus petite valeur propre {v.min():.3e}, plus grande {v.max():.3e}")
        assert v.min() >= -1e-10


def test_prix_par_rendements_logarithmiques(simulation, export_marche: Path) -> None:
    _, res = simulation
    ecart_memoire = ecart_csv = 0.0
    vl_csv = series_csv(export_marche, "fund_prices_daily", "fund_id", "nav_total_return")
    for f in res.fonds:
        vl = f.vl[f.debut:]
        assert np.isfinite(vl).all() and (vl > 0).all()
        ecart_memoire = max(ecart_memoire, float(np.abs(np.diff(np.log(vl)) - f.rendements[f.debut + 1:]).max()))
        _, v = vl_csv[f.fund_id]
        # VL exportée à 6 décimales : erreur relative ≤ 5e-7 / VL par point, donc ≤ 1e-6 sur un rendement
        ecart_csv = max(ecart_csv, float(np.abs(np.diff(np.log(v)) - f.rendements[f.debut + 1:]).max()))
    print(f"écart max log(VL_t / VL_t-1) − rendement simulé : en mémoire {ecart_memoire:.1e}, CSV {ecart_csv:.1e}")
    assert ecart_memoire < 1e-12 and ecart_csv < 1e-6


def test_regimes_markov_sans_date_ni_rendement_annuel(cfg, simulation) -> None:
    brut = lire_toml(TYPICAL)["markets"]
    dates, annees = [], []

    def parcourir(objet, chemin: str) -> None:
        if isinstance(objet, dict):
            for k, v in objet.items():
                if re.search(r"(19|20)\d{2}", str(k)):
                    annees.append(f"{chemin}.{k}")
                parcourir(v, f"{chemin}.{k}")
        elif isinstance(objet, list):
            for i, v in enumerate(objet):
                parcourir(v, f"{chemin}[{i}]")
        elif isinstance(objet, (dt.date, dt.datetime)):
            dates.append(chemin)
        elif isinstance(objet, str) and re.search(r"(19|20)\d{2}", objet):
            annees.append(chemin)
    parcourir(brut, "markets")
    print(f"section [markets] : {len(dates)} date(s), {len(annees)} clé ou valeur évoquant une année")
    assert not dates and not annees

    cles, P, pi = transitions(cfg.markets)
    assert np.allclose(P.sum(axis=1), 1) and abs(pi.sum() - 1) < 1e-12 and (pi > 0).all()
    _, res = simulation
    suite = res.marche.regimes
    vus = {(a, b) for a, b in zip(suite, suite[1:]) if a != b}
    permis = {(a, b) for a, r in cfg.markets.regimes.items() for b in r.next}
    print("loi stationnaire : " + ", ".join(f"{k} {p:.1%}" for k, p in zip(cles, pi))
          + f" ; transitions observées {sorted(vus)}")
    assert vus <= permis
    autre = simuler_marches(cfg, construire_univers(cfg).tables(), seed=GRAINE + 1).marche.regimes
    assert autre != suite                    # la suite des régimes vient de la graine


def test_aucune_borne_dans_le_code() -> None:
    """Aucun appel à clip, minimum, maximum, fmin ou fmax (numpy) dans le moteur et les repères ; min et
    max natifs seulement sur des dates (lancement, date d'effet). Les réductions tableau.min() et
    tableau.max() mesurent, elles ne bornent rien : non visées."""
    interdits = []
    for f in SOURCES:
        texte = f.read_text(encoding="utf-8")
        for noeud in ast.walk(ast.parse(texte)):
            if not isinstance(noeud, ast.Call):
                continue
            if isinstance(noeud.func, ast.Attribute) and noeud.func.attr in ("clip", "minimum", "maximum", "fmin", "fmax"):
                interdits.append(f"{f.name}:{noeud.lineno} {noeud.func.attr}")
            elif isinstance(noeud.func, ast.Name) and noeud.func.id in ("min", "max")                     and "date" not in (ast.get_source_segment(texte, noeud) or ""):
                interdits.append(f"{f.name}:{noeud.lineno} {noeud.func.id}")
    print(f"appels de bornage trouvés : {interdits or 'aucun'}")
    assert not interdits


def test_aucun_ecretage_des_pertes() -> None:
    """Des sauts de −40 % en moyenne, quasi quotidiens : la perte journalière passe, rien ne la rattrape."""
    raw = lire_toml(TYPICAL)
    for r in raw["markets"]["regimes"].values():
        r["jump_rate_per_year"], r["jump_size_pct"] = 50, [-40.0, 1.0]
    extreme = construire(raw)
    univers = construire_univers(extreme).tables()
    res = simuler_marches(extreme, univers)
    pire = min(float(f.rendements.min()) for f in res.fonds)
    print(f"pire rendement journalier d'un fonds : {math.expm1(pire):.1%}")
    assert math.expm1(pire) < -0.30


def test_charges_derivees_des_expositions(cfg, simulation) -> None:
    m = cfg.markets
    ch = charges([dict(asset_class="equity", geography="canada", style="broad_market", weight=100.0)], None, 0.0, m)
    assert ch.b[IF["equity_canada"]] == 1 and np.count_nonzero(ch.b) == 1
    ch = charges([dict(asset_class="equity", geography="united_states", style="growth", weight=60.0),
                  dict(asset_class="fixed_income", geography="europe", style="fixed_income", weight=40.0)],
                 6.0, 60.0, m)
    attendu = {"equity_united_states": 0.6, "style_growth": 0.6, "rate_global": -2.4, "slope": -0.4 * 6 * 0.2,
               "credit": -0.4 * 6 * m.rates["credit_duration_share"], "fx_usd_cad": 0.6}
    for f in FACTEURS:
        assert ch.b[IF[f]] == pytest.approx(attendu.get(f, 0.0))
    assert ch.portage == {"rate_canada": 0.0, "rate_global": pytest.approx(0.4), "short": 0.0}

    # Les rendements simulés portent ces charges : la pente du rendement d'un fonds sur sa part
    # factorielle F · b vaut 1 (le reste, bruit propre et sauts, est indépendant des facteurs). Fonds dont
    # la part factorielle a une volatilité d'au moins 1 % par an : en dessous, la pente est du bruit.
    _, res = simulation
    pentes = {}
    for f in res.fonds:
        x = (res.marche.facteurs @ f.charges.b)[f.debut + 1:]
        y = f.rendements[f.debut + 1:]
        if x.std() * math.sqrt(252) >= 0.01:
            pentes[f.fund_id] = float(np.cov(x, y)[0, 1] / x.var(ddof=1))
    print("pente du rendement sur F · b : " + ", ".join(f"{k} {v:.3f}" for k, v in pentes.items()))
    assert len(pentes) >= len(res.fonds) - 1 and all(abs(v - 1) < 0.05 for v in pentes.values())


def test_reperes_memes_facteurs_sans_alpha(cfg, simulation) -> None:
    univers, res = simulation
    m, j = cfg.markets, cfg.markets.trading_days_per_year
    fonds = {f.fund_id: f for f in res.fonds}
    mer = {f["fund_id"]: f["mer_pct"] for f in univers["funds"]}
    reperes = {b.benchmark_id: b for b in res.reperes}
    for fid, f in fonds.items():
        b = reperes[f"R-{fid}"]
        assert np.array_equal(b.charges.b, f.charges.b) and b.charges.portage == f.charges.portage
        assert np.allclose(b.rendements, rendements(b.charges, res.marche, b.passive_fee_pct, j), atol=1e-15)
        assert 0 < b.passive_fee_pct < mer[fid]
    cibles = defaultdict(dict)
    for l in univers["allocation_targets_history"]:
        if l["level"] == "institution":
            cibles[l["institution_id"]][l["fund_id"]] = l["target_weight"] / 100
    for i, poids in cibles.items():
        b = reperes[f"R-POL-{i}"]
        simple = sum(w * np.expm1(reperes[f"R-{fid}"].rendements) for fid, w in poids.items())
        assert np.allclose(b.rendements, np.log1p(simple), atol=1e-15)
        assert b.passive_fee_pct < sum(w * mer[fid] for fid, w in poids.items())
    contexte = sorted(k for k, b in reperes.items() if b.benchmark_type == "sensitivity")
    assert contexte == ["R-ACT-MONDE", "R-EQUILIBRE"]
    print(f"{len(fonds)} composites, {len(cibles)} politiques, contexte {contexte} ; "
          f"frais passifs {min(b.passive_fee_pct for b in res.reperes):.3f} à {max(b.passive_fee_pct for b in res.reperes):.3f} %")


def test_validation_export_marche(export_marche: Path) -> None:
    r = valider(export_marche)
    assert r["passed"], [c for c in r["checks"] if c["status"] == "fail"]


# ================================================================================================
# C3 — faits stylisés, graine du scénario
# ================================================================================================
def kurtosis_excedentaire(x: np.ndarray) -> float:
    z = x - x.mean()
    return float((z ** 4).mean() / (z ** 2).mean() ** 2 - 3)


def autocorrelation_carres(x: np.ndarray, decalages=range(1, 11)) -> float:
    c = x ** 2 - (x ** 2).mean()
    return float(np.mean([(c[:-k] * c[k:]).sum() / (c * c).sum() for k in decalages]))


def rangs(x: np.ndarray) -> np.ndarray:
    ordre = np.argsort(x, kind="stable")
    r = np.empty(len(x))
    r[ordre] = np.arange(len(x), dtype=float)
    for v in np.unique(x):                   # ex aequo : rang moyen
        r[x == v] = r[x == v].mean()
    return r


def correlation_commune(a, b) -> float:
    communes = set(a[0]) & set(b[0])
    va = np.array([x for d, x in zip(*a) if d in communes])
    vb = np.array([x for d, x in zip(*b) if d in communes])
    return float(np.corrcoef(np.diff(np.log(va)), np.diff(np.log(vb)))[0, 1])


def test_queues_epaisses_et_volatilite_regroupee(export_marche: Path) -> None:
    vl = series_csv(export_marche, "fund_prices_daily", "fund_id", "nav_total_return")
    parts = parts_classes(export_marche)
    actions = sorted(f for f in vl if parts[f].get("equity", 0) > 50)
    assert actions
    for f in actions:
        r = np.diff(np.log(vl[f][1]))
        k, a = kurtosis_excedentaire(r), autocorrelation_carres(r)
        print(f"{f} actions {parts[f]['equity']:.1f} % : kurtosis excédentaire {k:.2f}, autocorrélation moyenne de r² "
              f"(décalages 1 à 10) {a:.3f}")
        assert k > 1 and a > 0.05


def test_volatilites_ordonnees_par_mandat(export_marche: Path) -> None:
    """Groupes par mandat déclaré (fund_strategic_targets) : monétaire = 100 % liquidités, obligations =
    100 % revenu fixe, actions = 100 % actions, mixtes = actions et revenu fixe à la fois. Les mandats
    d'actifs réels n'entrent dans aucun groupe."""
    vl = series_csv(export_marche, "fund_prices_daily", "fund_id", "nav_total_return")
    mandat = defaultdict(dict)
    for l in lire(export_marche, "fund_strategic_targets"):
        mandat[l["fund_id"]][l["asset_class"]] = float(l["target_weight"])
    groupes = defaultdict(list)
    for f, m in mandat.items():
        if m == {"cash": 100.0}:
            g = "monétaire"
        elif m == {"fixed_income": 100.0}:
            g = "obligations"
        elif m == {"equity": 100.0}:
            g = "actions"
        elif m.get("equity", 0) > 0 and m.get("fixed_income", 0) > 0:
            g = "mixtes"
        else:
            continue
        groupes[g].append(float(np.diff(np.log(vl[f][1])).std(ddof=1) * math.sqrt(252)))
    ordre = ["monétaire", "obligations", "mixtes", "actions"]
    medianes = [float(np.median(groupes[g])) for g in ordre]
    print(" < ".join(f"{g} {m:.2%} ({len(groupes[g])} fonds)" for g, m in zip(ordre, medianes)))
    assert all(a < b for a, b in zip(medianes, medianes[1:]))


def test_correlations_plausibles(export_marche: Path) -> None:
    vl = series_csv(export_marche, "fund_prices_daily", "fund_id", "nav_total_return")
    axes = defaultdict(dict)
    for l in lire(export_marche, "fund_exposures_by_axis"):
        axes[l["fund_id"]][(l["axis"], l["category"])] = float(l["weight"])
    categories = sorted({c for v in axes.values() for c in v})
    vecteur = {f: np.array([axes[f].get(c, 0.0) for c in categories]) for f in vl}
    similarite, correlations, maxi = [], [], ("", -1.0)
    for a, b in itertools.combinations(sorted(vl), 2):
        similarite.append(float(vecteur[a] @ vecteur[b] / np.linalg.norm(vecteur[a]) / np.linalg.norm(vecteur[b])))
        c = correlation_commune(vl[a], vl[b])
        correlations.append(c)
        maxi = max(maxi, (f"{a}-{b}", c), key=lambda x: x[1])
    spearman = float(np.corrcoef(rangs(np.array(similarite)), rangs(np.array(correlations)))[0, 1])
    print(f"{len(correlations)} paires ; corrélation maximale {maxi[1]:.3f} ({maxi[0]}) ; Spearman similarité des "
          f"expositions / corrélation réalisée {spearman:.3f}")
    assert maxi[1] <= 0.98 and spearman > 0.5


# ------------------------------------------------------------------------------------------------
# J6b : repères de catégorie et graine de marché propre (scénario vitrine)
# ------------------------------------------------------------------------------------------------
VITRINE = RACINE / "configs" / "vitrine.toml"


def test_reperes_categorie(cfg, simulation) -> None:
    """Un repère « category » par catégorie d'archétypes présente (lue dans la configuration brute, pas dans
    benchmarks.py), mêmes facteurs, alpha nul, aucun bruit propre, frais passifs < RFG de chaque fonds comparé."""
    univers, res = simulation
    brut = cfg.raw["markets"]["benchmarks"]["category"]
    de = {a: f"R-CAT-{k.upper().replace('_', '-')}" for k, v in brut.items() for a in v["archetypes"]}
    attendus = {de[f["archetype"]] for f in univers["funds"]}
    reperes = {b.benchmark_id: b for b in res.reperes if b.benchmark_type == "category"}
    assert set(reperes) == attendus
    j = cfg.markets.trading_days_per_year
    for b in reperes.values():
        assert np.allclose(b.rendements, rendements(b.charges, res.marche, b.passive_fee_pct, j), atol=1e-15)
        assert b.indice[0] == 100.0
    for f in univers["funds"]:
        assert reperes[de[f["archetype"]]].passive_fee_pct < f["mer_pct"], f["fund_id"]
    print(f"{len(reperes)} repères de catégorie pour {len(univers['funds'])} fonds : {sorted(reperes)}")


def test_categories_sans_tirage(cfg, simulation) -> None:
    """Changer la composition d'une catégorie ne change ni les VL, ni les autres repères : les repères de catégorie
    ne consomment pas le flux markets."""
    univers, res = simulation
    raw = cfg.raw | {"markets": cfg.raw["markets"] | {"benchmarks": cfg.raw["markets"]["benchmarks"] | {
        "category": cfg.raw["markets"]["benchmarks"]["category"] | {"act_can": cfg.raw["markets"]["benchmarks"]["category"]["act_can"]
                                                                    | {"equity_geography": {"canada": 60, "united_states": 40}}}}}}
    autre = simuler_marches(construire(raw), univers)
    assert all(np.array_equal(a.vl, b.vl, equal_nan=True) for a, b in zip(res.fonds, autre.fonds))
    avant = {b.benchmark_id: b for b in res.reperes}
    apres = {b.benchmark_id: b for b in autre.reperes}
    assert all(np.array_equal(avant[k].indice, apres[k].indice) for k in avant if k != "R-CAT-ACT-CAN")
    assert not np.array_equal(avant["R-CAT-ACT-CAN"].indice, apres["R-CAT-ACT-CAN"].indice)
    print(f"{len(res.fonds)} VL et {len(avant) - 1} repères identiques ; R-CAT-ACT-CAN seul modifié")


def test_graine_de_marche(cfg, simulation) -> None:
    """vitrine : univers identique à typical (graine principale), marché tiré par market_seed seul."""
    univers, res = simulation
    v = charger(VITRINE, GRAINE)
    assert v.seed == cfg.seed and v.market_seed is not None and cfg.market_seed is None
    uv = construire_univers(v).tables()
    assert uv == univers
    rv = simuler_marches(v, uv)
    assert not any(np.array_equal(a.vl, b.vl, equal_nan=True) for a, b in zip(res.fonds, rv.fonds))
    explicite = simuler_marches(cfg, univers, seed=v.market_seed)
    assert all(np.array_equal(a.vl, b.vl, equal_nan=True) for a, b in zip(rv.fonds, explicite.fonds))
    print(f"graine principale {v.seed}, graine de marché {v.market_seed} : univers identique, VL toutes différentes, "
          "égales à celles de typical tirées avec la graine de marché")
