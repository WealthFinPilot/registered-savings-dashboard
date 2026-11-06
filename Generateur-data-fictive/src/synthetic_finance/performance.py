"""Moteur E — mesures après la simulation : TWR, MWR, réconciliation, contrefactuel passif (cahier des charges § 7, § 8).

Ne lit que le grand livre (J4) et les repères (J2) ; ne tire rien et ne modifie aucune table. Conventions :
- V⁺ₜ : valeur d'une entité à la clôture, après flux (Σ total_value_cad de ses comptes ouverts) ;
- Fₜ : flux externes du jour, PAC + PONCTUEL + RETRAIT. Les FRAIS n'en sont pas : ils restent dans la valeur et
  pèsent sur le rendement ;
- V⁻ₜ = V⁺ₜ − Fₜ : les flux s'exécutent à la VL de clôture (J4), la valeur avant flux s'en déduit au résidu
  d'arrondi des parts près ;
- rₜ = V⁻ₜ ÷ V⁺ₜ₋₁ − 1, vide quand V⁺ₜ₋₁ = 0 (entité qui vient d'ouvrir) ; TWR cumulé = Π(1 + rₜ) − 1.
Entités : chaque compte, chaque institution, le portefeuille. Le TWR d'une institution ou du portefeuille se calcule
sur les valeurs et les flux agrégés, jamais en moyennant des TWR.

MWR : taux ρ qui annule Σ cₖ (1 + ρ)^(−τₖ), flux vus de l'épargnant (valeur de début et apports < 0, retraits et
valeur de fin > 0, FRAIS hors flux). τ en années de 365 jours ; une période plus courte que annualize_min_days rend
le taux de la période (τ en fraction de la période). Racines repérées sur une grille en log(1 + ρ), resserrées par
fausse position modifiée (Illinois) ; MWR vide avec motif s'il n'y en a pas exactement une.

Contrefactuel : les mêmes flux externes aux mêmes dates, investis dans un repère à l'indice de clôture (parts en
précision double). Aucun FRAIS de compte : seuls les frais passifs, déjà dans l'indice. Institution : son repère de
politique R-POL-<institution_id> ; portefeuille : somme des trois (R-POL), plus les repères de contexte.
"""
import datetime as dt
import math
from dataclasses import dataclass

import numpy as np

from .config import Config, ConfigError

PORTEFEUILLE = "PORTFOLIO"
POLITIQUES = "R-POL"                     # somme des contrefactuels de politique des institutions
OUVERTURE = "inception"                  # période « depuis l'ouverture »
NIVEAUX = ("portfolio", "institution", "account")
APPORTS, RETRAITS = ("PAC", "PONCTUEL"), ("RETRAIT",)


class PerformanceError(ValueError):
    """Mesure impossible (retrait du contrefactuel au-delà de sa valeur) : le moteur s'arrête."""


@dataclass
class Mesures:
    performance_daily: list[dict]
    performance_periods: list[dict]
    counterfactual_daily: list[dict]

    def tables(self) -> dict[str, list[dict]]:
        return dict(self.__dict__)


@dataclass
class Jour:
    date: dt.date
    valeur: int                          # V⁺, cents
    apports: int                         # PAC + PONCTUEL, cents ≥ 0
    retraits: int                        # RETRAIT, cents ≤ 0
    frais: int                           # FRAIS, cents ≤ 0

    @property
    def flux(self) -> int:
        return self.apports + self.retraits


def cents(x: float) -> int:
    return math.floor(x * 100 + 0.5)


def entites(accounts: list[dict]) -> dict[tuple[str, str], set[str]]:
    """Comptes de chaque entité, dans l'ordre d'export : portefeuille, institutions, comptes."""
    sortie = {("portfolio", PORTEFEUILLE): {c["account_id"] for c in accounts}}
    for i in sorted({c["institution_id"] for c in accounts}):
        sortie[("institution", i)] = {c["account_id"] for c in accounts if c["institution_id"] == i}
    for c in sorted(accounts, key=lambda c: c["account_id"]):
        sortie[("account", c["account_id"])] = {c["account_id"]}
    return sortie


def series(t: dict[str, list[dict]]) -> dict[tuple[str, str], list[Jour]]:
    """Série quotidienne de chaque entité, sur les jours où elle a au moins un compte ouvert."""
    val: dict[dt.date, dict[str, int]] = {}
    for v in t["account_values_daily"]:
        val.setdefault(v["date"], {})[v["account_id"]] = cents(v["total_value_cad"])
    mvt: dict[tuple[dt.date, str], list[int]] = {}
    for m in t["external_movements"]:
        k = (APPORTS, RETRAITS, ("FRAIS",))
        rang = next(n for n, types in enumerate(k) if m["movement_type"] in types)
        mvt.setdefault((m["date"], m["account_id"]), [0, 0, 0])[rang] += cents(m["amount_cad"])
    sortie = {}
    for e, comptes in entites(t["accounts"]).items():
        jours = []
        for d in sorted(val):
            presents = comptes & val[d].keys()
            if not presents:
                continue
            a, r, f = (sum(mvt.get((d, c), (0, 0, 0))[n] for c in presents) for n in range(3))
            jours.append(Jour(d, sum(val[d][c] for c in presents), a, r, f))
        sortie[e] = jours
    return sortie


def rendements(jours: list[Jour]) -> list[float | None]:
    """rₜ = (V⁺ₜ − Fₜ) ÷ V⁺ₜ₋₁ − 1, vide si V⁺ₜ₋₁ = 0."""
    sortie, veille = [], 0
    for j in jours:
        sortie.append(None if veille == 0 else (j.valeur - j.flux) / veille - 1)
        veille = j.valeur
    return sortie


def cumuler(r: list[float | None]) -> list[float]:
    sortie, c = [], 1.0
    for x in r:
        if x is not None:
            c *= 1 + x
        sortie.append(c - 1)
    return sortie


# ------------------------------------------------------------------------------------------------
# MWR
# ------------------------------------------------------------------------------------------------
def xirr(flux: list[tuple[float, float]], bornes: tuple[float, float], points: int) -> tuple[float | None, str]:
    """Taux ρ qui annule Σ c (1 + ρ)^(−τ), flux (τ, c) ; rend (ρ, « ok ») ou (None, motif)."""
    tau = np.array([x for x, _ in flux])
    c = np.array([y for _, y in flux])
    if not (np.any(c < 0) and np.any(c > 0)):
        return None, "aucun changement de signe"

    def van(rho: float) -> float:
        return float(np.sum(c * np.exp(-tau * math.log1p(rho))))

    grille = np.expm1(np.linspace(math.log1p(bornes[0]), math.log1p(bornes[1]), points))
    valeurs = (c[None, :] * np.exp(-np.outer(np.log1p(grille), tau))).sum(axis=1)
    racines = [k for k in range(points - 1) if valeurs[k] == 0 or valeurs[k] * valeurs[k + 1] < 0]
    if valeurs[-1] == 0:
        racines.append(points - 1)
    if len(racines) > 1:
        return None, "plusieurs racines"
    if not racines:
        return None, "non convergé"
    k = racines[0]
    if valeurs[k] == 0:
        return float(grille[k]), "ok"
    # Fausse position modifiée (Illinois) : l'extrémité qui ne bouge pas deux fois de suite voit sa valeur divisée par 2
    a, b, fa, fb = float(grille[k]), float(grille[k + 1]), float(valeurs[k]), float(valeurs[k + 1])
    echelle, cote = float(np.abs(c).sum()), 0
    for _ in range(200):
        x = (a * fb - b * fa) / (fb - fa)
        fx = van(x)
        if abs(fx) <= 1e-13 * echelle:
            return x, "ok"
        if fx * fb > 0:
            b, fb = x, fx
            if cote == -1:
                fa /= 2
            cote = -1
        else:
            a, fa = x, fx
            if cote == 1:
                fb /= 2
            cote = 1
        if abs(b - a) <= 1e-14 * max(1.0, abs(x)):
            return x, "ok"
    return None, "non convergé"


def periodes(p: dict, jours: list[Jour], r: list[float | None]) -> list[dict]:
    """Chaque année civile (tronquée à l'ouverture et à l'arrêté), puis depuis l'ouverture. Valeur de début : V⁺ de la
    veille du premier jour de la période, 0 si l'entité ouvre dans la période (date de début = jour d'ouverture)."""
    decoupe = [(str(a), [k for k, j in enumerate(jours) if j.date.year == a]) for a in sorted({j.date.year for j in jours})]
    sortie = []
    for libelle, idx in decoupe + [(OUVERTURE, list(range(len(jours))))]:
        k0, fin = idx[0], jours[idx[-1]]
        debut_date, debut = (jours[k0 - 1].date, jours[k0 - 1].valeur) if k0 > 0 else (jours[k0].date, 0)
        lignes = [jours[k] for k in idx]
        apports, retraits, frais = (sum(getattr(j, n) for j in lignes) for n in ("apports", "retraits", "frais"))
        rs = [x for x in (r[k] for k in idx) if x is not None]
        duree = (fin.date - debut_date).days
        unite = 365 if duree >= p["annualize_min_days"] else max(duree, 1)
        flux: dict[dt.date, int] = {debut_date: -debut}
        for j in lignes:
            flux[j.date] = flux.get(j.date, 0) - j.flux
        flux[fin.date] = flux.get(fin.date, 0) + fin.valeur
        taux, motif = xirr([((d - debut_date).days / unite, c / 100) for d, c in sorted(flux.items()) if c != 0],
                           p["mwr_bounds"], p["mwr_grid"])
        sortie.append(dict(period=libelle, start_date=debut_date, end_date=fin.date, days=duree,
                           start_value_cad=debut / 100, contributions_cad=apports / 100, withdrawals_cad=-retraits / 100,
                           fees_cad=frais / 100, investment_result_cad=(fin.valeur - debut - apports - retraits - frais) / 100,
                           end_value_cad=fin.valeur / 100, twr=math.prod(1 + x for x in rs) - 1 if rs else None,
                           mwr=taux, mwr_annualized=unite == 365, mwr_status=motif))
    return sortie


# ------------------------------------------------------------------------------------------------
# Contrefactuel passif
# ------------------------------------------------------------------------------------------------
def investir(jours: list[Jour], indice: dict[dt.date, float], libelle: str) -> list[tuple[float, float]]:
    """Valeurs (avant flux, après flux) en dollars, non arrondies, d'un placement des flux de « jours » dans l'indice."""
    parts, sortie = 0.0, []
    for j in jours:
        x = indice.get(j.date)
        if x is None:
            raise PerformanceError(f"{libelle} : aucun indice le {j.date}")
        avant = parts * x
        if j.flux < 0 and -j.flux / 100 > avant + 1e-9:
            raise PerformanceError(f"{libelle}, {j.date} : retrait de {-j.flux / 100:.2f} $, le contrefactuel vaut "
                                   f"{avant:.2f} $")
        parts += j.flux / 100 / x
        if parts < 0 and parts * x > -1e-9:
            parts = 0.0                          # retrait de toute la valeur : reste d'arrondi en virgule flottante
        sortie.append((avant, parts * x))
    return sortie


def lignes_contrefactuel(e: tuple[str, str], bid: str, jours: list[Jour], valeurs: list[tuple[float, float]]) -> list[dict]:
    sortie, veille, c = [], 0.0, 1.0
    for j, (avant, apres) in zip(jours, valeurs):
        r = None if veille == 0 else avant / veille - 1
        if r is not None:
            c *= 1 + r
        sortie.append(dict(date=j.date, entity_type=e[0], entity_id=e[1], benchmark_id=bid,
                           market_value_cad=cents(apres) / 100, net_external_flow_cad=j.flux / 100,
                           daily_twr=r, cumulative_twr=c - 1))
        veille = apres
    return sortie


def contrefactuels(p: dict, t: dict[str, list[dict]], s: dict[tuple[str, str], list[Jour]]) -> list[dict]:
    indices: dict[str, dict[dt.date, float]] = {}
    for l in t["benchmarks_daily"]:
        indices.setdefault(l["benchmark_id"], {})[l["date"]] = round(l["index_total_return"], 6)
    connus = {b["benchmark_id"] for b in t["benchmarks"]}
    manquants = [b for b in p["context_benchmarks"] if b not in connus]
    if manquants:
        raise ConfigError(f"performance.context_benchmarks : repères inconnus {manquants}")
    portefeuille = s[("portfolio", PORTEFEUILLE)]
    sortie, somme = [], {j.date: [0.0, 0.0] for j in portefeuille}
    for e, jours in s.items():
        if e[0] != "institution":
            continue
        bid = f"R-POL-{e[1]}"
        valeurs = investir(jours, indices[bid], f"contrefactuel {bid}")
        for j, (avant, apres) in zip(jours, valeurs):
            somme[j.date][0] += avant
            somme[j.date][1] += apres
        sortie += lignes_contrefactuel(e, bid, jours, valeurs)
    e = ("portfolio", PORTEFEUILLE)
    sortie += lignes_contrefactuel(e, POLITIQUES, portefeuille, [(somme[j.date][0], somme[j.date][1]) for j in portefeuille])
    for bid in p["context_benchmarks"]:
        sortie += lignes_contrefactuel(e, bid, portefeuille, investir(portefeuille, indices[bid], f"contrefactuel {bid}"))
    ordre = {e: n for n, e in enumerate(NIVEAUX)}
    return sorted(sortie, key=lambda l: (ordre[l["entity_type"]], l["entity_id"], l["benchmark_id"], l["date"]))


# ------------------------------------------------------------------------------------------------
# Assemblage
# ------------------------------------------------------------------------------------------------
def mesurer(cfg: Config, t: dict[str, list[dict]]) -> Mesures:
    if cfg.performance is None:
        raise ConfigError("performance : section absente de la configuration")
    p = cfg.performance
    s = series(t)
    quotidien, par_periode = [], []
    for e, jours in s.items():
        r = rendements(jours)
        for j, x, c in zip(jours, r, cumuler(r)):
            quotidien.append(dict(date=j.date, entity_type=e[0], entity_id=e[1], market_value_cad=j.valeur / 100,
                                  net_external_flow_cad=j.flux / 100, fees_cad=j.frais / 100, daily_twr=x,
                                  cumulative_twr=c))
        par_periode += [dict(entity_type=e[0], entity_id=e[1], **l) for l in periodes(p, jours, r)]
    return Mesures(quotidien, par_periode, contrefactuels(p, t, s))


# ------------------------------------------------------------------------------------------------
# Écart à la politique (rapport et diagnostic multi-graines, après coup)
# ------------------------------------------------------------------------------------------------
def ecarts_politique(t: dict[str, list[dict]]) -> list[dict]:
    """Par institution, depuis son premier rendement : TWR annualisés de l'institution et de son contrefactuel de
    politique, écart, et sa décomposition. Frais = RFG moyen pondéré par l'encours + FRAIS annualisés − frais passifs
    du repère ; reste = écart + frais (alpha des fonds, allocation différente de la politique, rééquilibrages). Une
    institution sans aucun rendement (comptes ouverts, jamais alimentés) n'a pas d'écart : elle est omise."""
    comptes = {c["account_id"]: c["institution_id"] for c in t["accounts"]}
    mer = {f["fund_id"]: f["mer_pct"] for f in t["funds"]}
    passif = {b["benchmark_id"]: b["passive_fee_pct"] for b in t["benchmarks"]}
    rfg: dict[str, list[float]] = {}
    for p in t["positions_daily"]:
        x = rfg.setdefault(comptes[p["account_id"]], [0.0, 0.0])
        x[0] += p["market_value_cad"] * mer[p["fund_id"]]
        x[1] += p["market_value_cad"]
    perf = [l for l in t["performance_daily"] if l["entity_type"] == "institution"]
    cf = {(l["entity_id"], l["date"]): l for l in t["counterfactual_daily"] if l["entity_type"] == "institution"}
    sortie = []
    for i in sorted({l["entity_id"] for l in perf}):
        lignes = [l for l in perf if l["entity_id"] == i]
        k0 = next((k for k, l in enumerate(lignes) if l["daily_twr"] is not None), 0) - 1
        if k0 < 0:
            continue
        debut, fin = lignes[k0], lignes[-1]
        annees = (fin["date"] - debut["date"]).days / 365
        reel = (1 + fin["cumulative_twr"]) / (1 + debut["cumulative_twr"])
        pol = (1 + cf[(i, fin["date"])]["cumulative_twr"]) / (1 + cf[(i, debut["date"])]["cumulative_twr"])
        a_reel, a_pol = 100 * (reel ** (1 / annees) - 1), 100 * (pol ** (1 / annees) - 1)
        valeurs = [l["market_value_cad"] for l in lignes[k0:] if l["market_value_cad"] > 0]
        frais_compte = -sum(l["fees_cad"] for l in lignes[k0 + 1:]) / (sum(valeurs) / len(valeurs)) / annees * 100
        frais = rfg[i][0] / rfg[i][1] + frais_compte - passif[f"R-POL-{i}"]
        sortie.append(dict(institution_id=i, debut=debut["date"], fin=fin["date"], annees=annees, twr=a_reel,
                           twr_politique=a_pol, ecart=a_reel - a_pol, rfg=rfg[i][0] / rfg[i][1], frais_compte=frais_compte,
                           frais_passifs=passif[f"R-POL-{i}"], frais=frais, reste=a_reel - a_pol + frais,
                           valeur=fin["market_value_cad"], valeur_politique=cf[(i, fin["date"])]["market_value_cad"]))
    return sortie
