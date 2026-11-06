"""Recalcul indépendant des mesures (J5, C2 à C4), depuis les tables du grand livre : ce module n'importe pas
performance.py.

series() reconstruit la valeur, les flux et les frais de chaque entité ; twr() compare rendements et TWR cumulés ;
marche() vérifie chaque jour que r × V⁺ de la veille = rendement des parts détenues la veille + frais du jour, au
résidu d'arrondi près ; periodes() refait l'identité de chaque période et le MWR par bissection ; contrefactuel()
refait le placement des mêmes flux dans l'indice.
"""
import datetime as dt
import math
from pathlib import Path

from synthetic_finance.export import lire_csv

TABLES = ("accounts", "funds", "benchmarks", "benchmarks_daily", "fund_prices_daily", "external_movements",
          "internal_trades", "positions_daily", "account_values_daily", "allocation_targets_history",
          "performance_daily", "performance_periods", "counterfactual_daily")
TOLERANCE = 1e-9
RESIDU_CENT = 0.005


def lire_export(dossier: Path) -> dict[str, list[dict]]:
    return {t: lire_csv(dossier / "data" / f"{t}.csv", t) for t in TABLES}


def c(x: float) -> int:
    return round(x * 100)


def entites(t: dict) -> dict[tuple[str, str], set[str]]:
    comptes = {a["account_id"]: a["institution_id"] for a in t["accounts"]}
    sortie = {("portfolio", "PORTFOLIO"): set(comptes)}
    for a, i in comptes.items():
        sortie.setdefault(("institution", i), set()).add(a)
        sortie[("account", a)] = {a}
    return sortie


def series(t: dict) -> dict[tuple[str, str], list[tuple[dt.date, int, int, int, int]]]:
    """(date, V⁺, apports, retraits, frais) en cents, jours où l'entité a au moins un compte ouvert."""
    val: dict[dt.date, dict[str, int]] = {}
    for v in t["account_values_daily"]:
        val.setdefault(v["date"], {})[v["account_id"]] = c(v["total_value_cad"])
    mvt: dict[tuple[dt.date, str], list[int]] = {}
    for m in t["external_movements"]:
        k = {"PAC": 0, "PONCTUEL": 0, "RETRAIT": 1, "FRAIS": 2}[m["movement_type"]]
        mvt.setdefault((m["date"], m["account_id"]), [0, 0, 0])[k] += c(m["amount_cad"])
    sortie = {}
    for e, membres in entites(t).items():
        lignes = []
        for d in sorted(val):
            ouverts = membres & val[d].keys()
            if ouverts:
                x = [sum(mvt.get((d, a), (0, 0, 0))[k] for a in ouverts) for k in range(3)]
                lignes.append((d, sum(val[d][a] for a in ouverts), *x))
        sortie[e] = lignes
    return sortie


# ------------------------------------------------------------------------------------------------
# TWR (C2)
# ------------------------------------------------------------------------------------------------
def twr(t: dict) -> tuple[list[str], str]:
    erreurs = []
    exporte: dict[tuple[str, str], list[dict]] = {}
    for l in t["performance_daily"]:
        exporte.setdefault((l["entity_type"], l["entity_id"]), []).append(l)
    s = series(t)
    if set(s) != set(exporte):
        erreurs.append(f"entités exportées {sorted(exporte)} ≠ attendues {sorted(s)}")
    n, pire = 0, 0.0
    for e, lignes in s.items():
        exp = exporte.get(e, [])
        if [l["date"] for l in exp] != [x[0] for x in lignes]:
            erreurs.append(f"{e[1]} : jours exportés ≠ jours d'ouverture")
            continue
        veille, cumul = 0, 1.0
        for (d, v, ap, re, fr), l in zip(lignes, exp):
            if (c(l["market_value_cad"]), c(l["net_external_flow_cad"]), c(l["fees_cad"])) != (v, ap + re, fr):
                erreurs.append(f"{e[1]} le {d} : V⁺, flux ou frais ≠ recalcul")
            r = None if veille == 0 else (v - ap - re) / veille - 1
            if r is not None:
                cumul *= 1 + r
                n += 1
            ecart = abs(cumul - 1 - l["cumulative_twr"])
            if r is not None:
                if l["daily_twr"] is None:
                    erreurs.append(f"{e[1]} le {d} : rendement vide")
                    continue
                ecart = max(ecart, abs(r - l["daily_twr"]))
            elif l["daily_twr"] is not None:
                erreurs.append(f"{e[1]} le {d} : rendement {l['daily_twr']} alors que la veille vaut 0")
            pire = max(pire, ecart)
            if ecart > TOLERANCE:
                erreurs.append(f"{e[1]} le {d} : écart {ecart:.2e}")
            veille = v
    fin = {e: l[-1] for e, l in exporte.items()}
    ptf = fin[("portfolio", "PORTFOLIO")]["cumulative_twr"]
    inst = [l for e, l in fin.items() if e[0] == "institution"]
    cpt = [l for e, l in fin.items() if e[0] == "account"]

    def moyennes(lignes: list[dict]) -> tuple[float, float]:
        return (sum(l["cumulative_twr"] for l in lignes) / len(lignes),
                sum(l["cumulative_twr"] * l["market_value_cad"] for l in lignes) / sum(l["market_value_cad"] for l in lignes))
    (si, pi), (sc, pc) = moyennes(inst), moyennes(cpt)
    detail = (f"{n} rendements recalculés sur {len(s)} entités, pire écart {pire:.1e} ; TWR consolidé {ptf:+.4%} ; "
              f"moyenne des institutions simple {si:+.4%} (écart {ptf - si:+.4%}), pondérée par la valeur finale {pi:+.4%} "
              f"(écart {ptf - pi:+.4%}) ; moyenne des comptes simple {sc:+.4%}, pondérée {pc:+.4%}")
    return erreurs, detail


def marche(t: dict) -> tuple[list[str], dict[tuple[str, str, dt.date], tuple[float, float]], str]:
    """Pour chaque entité et chaque jour à rendement : écart = r × V⁺ₜ₋₁ − (Σ parts de la veille × variation de VL +
    frais du jour), en dollars, et sa borne = Σ |parts × VL − montant| des ordres du jour + 0,005 $ par ligne de
    position la veille et le jour (valeurs arrondies au cent)."""
    vl = {(l["fund_id"], l["date"]): round(l["nav_total_return"], 6) for l in t["fund_prices_daily"]}
    pos: dict[tuple[dt.date, str], dict[str, float]] = {}
    for p in t["positions_daily"]:
        pos.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p["units"]
    residu: dict[tuple[dt.date, str], float] = {}
    for o in t["internal_trades"]:
        k = (o["date"], o["account_id"])
        residu[k] = residu.get(k, 0.0) + abs(o["units"] * o["unit_price"] - o["gross_amount_cad"])
    frais: dict[tuple[dt.date, str], float] = {}
    for m in t["external_movements"]:
        if m["movement_type"] == "FRAIS":
            frais[(m["date"], m["account_id"])] = frais.get((m["date"], m["account_id"]), 0.0) + m["amount_cad"]
    membres = entites(t)
    erreurs, ecarts, pire = [], {}, 0.0
    lignes: dict[tuple[str, str], list[dict]] = {}
    for l in t["performance_daily"]:
        lignes.setdefault((l["entity_type"], l["entity_id"]), []).append(l)
    for e, ls in lignes.items():
        for hier, l in zip(ls, ls[1:]):
            if l["daily_twr"] is None:
                continue
            v, d = hier["date"], l["date"]
            gain = sum(u * (vl[(f, d)] - vl[(f, v)]) for a in membres[e] for f, u in pos.get((v, a), {}).items())
            ecart = l["daily_twr"] * hier["market_value_cad"] - gain - sum(frais.get((d, a), 0.0) for a in membres[e])
            borne = sum(residu.get((d, a), 0.0) + RESIDU_CENT * (len(pos.get((v, a), {})) + len(pos.get((d, a), {})))
                        for a in membres[e]) + 1e-6
            ecarts[(e[0], e[1], d)] = (ecart, borne)
            pire = max(pire, abs(ecart) / borne)
            if abs(ecart) > borne:
                erreurs.append(f"{e[1]} le {d} : r × V⁺ veille − marché − frais = {ecart:+.4f} $ > borne {borne:.4f} $")
    detail = f"{len(ecarts)} jours × entités : r × V⁺ de la veille = marché des parts détenues + frais, pire écart à {pire:.0%} de sa borne"
    return erreurs, ecarts, detail


# ------------------------------------------------------------------------------------------------
# Périodes et MWR (C3)
# ------------------------------------------------------------------------------------------------
def bissection(flux: list[tuple[float, float]], bornes: tuple[float, float], points: int = 2000) -> tuple[float | None, str]:
    """Racine unique de Σ c (1 + ρ)^(−τ) dans les bornes, par bissection ; sinon (None, motif)."""
    if not (any(x < 0 for _, x in flux) and any(x > 0 for _, x in flux)):
        return None, "aucun changement de signe"

    def van(rho: float) -> float:
        return math.fsum(x * (1 + rho) ** (-tau) for tau, x in flux)
    a, b = math.log1p(bornes[0]), math.log1p(bornes[1])
    grille = [math.expm1(a + (b - a) * k / (points - 1)) for k in range(points)]
    valeurs = [van(x) for x in grille]
    paires = [k for k in range(points - 1) if valeurs[k] == 0 or valeurs[k] * valeurs[k + 1] < 0]
    if len(paires) != 1:
        return None, "plusieurs racines" if paires else "non convergé"
    bas, haut = grille[paires[0]], grille[paires[0] + 1]
    signe_bas = valeurs[paires[0]] > 0
    for _ in range(300):
        milieu = (bas + haut) / 2
        if (van(milieu) > 0) == signe_bas:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2, "ok"


def periodes(t: dict, bornes: tuple[float, float], annualise: int) -> tuple[list[str], dict, str]:
    """Chaque période recalculée depuis les comptes : bornes de dates, valeurs, flux, frais ; résultat de placement du
    moteur comparé à Σ parts de la veille × variation de VL (borne : résidus des ordres de la période + 0,005 $ par ligne
    de position au début et à la fin) ; TWR = produit des rendements ; MWR par bissection à 1e-6."""
    vl = {(l["fund_id"], l["date"]): round(l["nav_total_return"], 6) for l in t["fund_prices_daily"]}
    pos: dict[tuple[dt.date, str], dict[str, float]] = {}
    for p in t["positions_daily"]:
        pos.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p["units"]
    residu: dict[tuple[dt.date, str], float] = {}
    for o in t["internal_trades"]:
        k = (o["date"], o["account_id"])
        residu[k] = residu.get(k, 0.0) + abs(o["units"] * o["unit_price"] - o["gross_amount_cad"])
    exporte = {(p["entity_type"], p["entity_id"], p["period"]): p for p in t["performance_periods"]}
    rendement = {(l["entity_type"], l["entity_id"], l["date"]): l["daily_twr"] for l in t["performance_daily"]}
    membres = entites(t)
    erreurs, bilan = [], dict(periodes=0, motifs={}, opposes=0, pire_resultat=0.0, pire_mwr=0.0)
    for e, lignes in series(t).items():
        decoupe = [(str(y), [x for x in lignes if x[0].year == y]) for y in sorted({x[0].year for x in lignes})]
        for nom, dedans in decoupe + [("inception", lignes)]:
            p = exporte.get((e[0], e[1], nom))
            if p is None:
                erreurs.append(f"{e[1]} {nom} : période absente")
                continue
            bilan["periodes"] += 1
            avant = [x for x in lignes if x[0] < dedans[0][0]]
            d0, v0 = (avant[-1][0], avant[-1][1]) if avant else (dedans[0][0], 0)
            d1, v1 = dedans[-1][0], dedans[-1][1]
            ap, re, fr = (sum(x[k] for x in dedans) for k in (2, 3, 4))
            attendu = (d0, d1, (d1 - d0).days, v0, ap, -re, fr, v1)
            obtenu = (p["start_date"], p["end_date"], p["days"], c(p["start_value_cad"]), c(p["contributions_cad"]),
                      c(p["withdrawals_cad"]), c(p["fees_cad"]), c(p["end_value_cad"]))
            if obtenu != attendu:
                erreurs.append(f"{e[1]} {nom} : {obtenu} ≠ {attendu}")
                continue
            if v1 != v0 + ap + re + fr + c(p["investment_result_cad"]):
                erreurs.append(f"{e[1]} {nom} : fin ≠ début + apports − retraits + frais + résultat")
            # Résultat de placement par les parts : Σ parts de la veille × variation de VL, jour par jour
            jours = [d0] + [x[0] for x in dedans if x[0] != d0]
            gain = sum(u * (vl[(f, d)] - vl[(f, v)]) for v, d in zip(jours, jours[1:]) for a in membres[e]
                       for f, u in pos.get((v, a), {}).items())
            borne = sum(residu.get((x[0], a), 0.0) for x in dedans for a in membres[e])
            borne += RESIDU_CENT * sum(len(pos.get((d0, a), {})) * bool(avant) + len(pos.get((d1, a), {})) for a in membres[e])
            ecart = abs(p["investment_result_cad"] - gain)
            bilan["pire_resultat"] = max(bilan["pire_resultat"], ecart / (borne + 1e-6))
            if ecart > borne + 1e-6:
                erreurs.append(f"{e[1]} {nom} : résultat {p['investment_result_cad']:.2f} ≠ parts × ΔVL {gain:.4f} (borne {borne:.4f})")
            rs = [rendement[(e[0], e[1], x[0])] for x in dedans if rendement[(e[0], e[1], x[0])] is not None]
            tw = math.prod(1 + r for r in rs) - 1 if rs else None
            if (tw is None) != (p["twr"] is None) or (tw is not None and abs(tw - p["twr"]) > 10 * TOLERANCE):
                erreurs.append(f"{e[1]} {nom} : TWR {p['twr']} ≠ {tw}")
            # MWR : flux de l'épargnant, τ en années (ou en fraction de la période si elle est courte)
            duree = (d1 - d0).days
            unite = 365 if duree >= annualise else max(duree, 1)
            flux: dict[dt.date, int] = {d0: -v0}
            for x in dedans:
                flux[x[0]] = flux.get(x[0], 0) - (x[2] + x[3])
            flux[d1] = flux.get(d1, 0) + v1
            taux, motif = bissection([((d - d0).days / unite, x / 100) for d, x in sorted(flux.items()) if x != 0], bornes)
            bilan["motifs"][motif] = bilan["motifs"].get(motif, 0) + 1
            if motif != p["mwr_status"] or (taux is None) != (p["mwr"] is None) \
                    or p["mwr_annualized"] != (unite == 365):
                erreurs.append(f"{e[1]} {nom} : MWR {p['mwr']} ({p['mwr_status']}) ≠ bissection {taux} ({motif})")
            elif taux is not None:
                bilan["pire_mwr"] = max(bilan["pire_mwr"], abs(taux - p["mwr"]))
                if abs(taux - p["mwr"]) > 1e-6:
                    erreurs.append(f"{e[1]} {nom} : MWR {p['mwr']:.8f} ≠ bissection {taux:.8f}")
            if p["twr"] is not None and p["mwr"] is not None and p["twr"] * p["mwr"] < 0:
                bilan["opposes"] += 1
    detail = (f"{bilan['periodes']} périodes ; résultat de placement = parts × ΔVL, pire écart à {bilan['pire_resultat']:.0%} "
              f"de sa borne ; MWR par bissection, pire écart {bilan['pire_mwr']:.1e} ; motifs {bilan['motifs']} ; TWR et MWR "
              f"de signes opposés : {bilan['opposes']}")
    return erreurs, bilan, detail


# ------------------------------------------------------------------------------------------------
# Contrefactuel (C4)
# ------------------------------------------------------------------------------------------------
def contrefactuel(t: dict) -> tuple[list[str], str]:
    """Flux = PAC + PONCTUEL + RETRAIT de l'entité, jour par jour ; valeur = Σ flux × indice du jour ÷ indice du jour du
    flux, au cent ; TWR cumulé = indice du jour ÷ indice de la veille du premier rendement − 1 (repère unique)."""
    indice = {(l["benchmark_id"], l["date"]): round(l["index_total_return"], 6) for l in t["benchmarks_daily"]}
    s = series(t)
    erreurs = []
    par_serie: dict[tuple[str, str, str], list[dict]] = {}
    for l in t["counterfactual_daily"]:
        par_serie.setdefault((l["entity_type"], l["entity_id"], l["benchmark_id"]), []).append(l)
    institutions = sorted(e[1] for e in s if e[0] == "institution")
    pire_twr, pire_val = 0.0, 0.0
    for (typ, ident, b), lignes in par_serie.items():
        reel = s[(typ, ident)]
        if [(l["date"], c(l["net_external_flow_cad"])) for l in lignes] != [(x[0], x[2] + x[3]) for x in reel]:
            erreurs.append(f"{ident} × {b} : calendrier de flux ≠ PAC + PONCTUEL + RETRAIT de l'entité")
            continue
        if b == "R-POL":
            composantes = [(f"R-POL-{i}", s[("institution", i)]) for i in institutions]
        else:
            composantes = [(b, reel)]
        depart = None
        flux_jour = {(bb, x[0]): (x[2] + x[3]) / 100 for bb, serie in composantes for x in serie}
        parts = {bb: 0.0 for bb, _ in composantes}          # Σ flux ÷ indice du jour du flux
        for k, l in enumerate(lignes):
            d = l["date"]
            for bb in parts:
                parts[bb] += flux_jour.get((bb, d), 0.0) / indice[(bb, d)]
            exacte = sum(u * indice[(bb, d)] for bb, u in parts.items())
            pire_val = max(pire_val, abs(exacte - l["market_value_cad"]))
            if abs(exacte - l["market_value_cad"]) > RESIDU_CENT + 1e-6:
                erreurs.append(f"{ident} × {b} le {d} : valeur {l['market_value_cad']} ≠ flux replacés {exacte:.4f}")
            if len(composantes) == 1:
                if l["daily_twr"] is not None and depart is None:
                    depart = lignes[k - 1]["date"]
                attendu = indice[(b, d)] / indice[(b, depart)] - 1 if depart else 0.0
                pire_twr = max(pire_twr, abs(attendu - l["cumulative_twr"]))
                if abs(attendu - l["cumulative_twr"]) > TOLERANCE:
                    erreurs.append(f"{ident} × {b} le {d} : TWR {l['cumulative_twr']} ≠ indice {attendu}")
    detail = (f"{len(par_serie)} contrefactuels : flux = PAC + PONCTUEL + RETRAIT aux mêmes dates ; valeur = flux replacés "
              f"dans l'indice, pire écart {pire_val:.4f} $ ; TWR = rendement de l'indice, pire écart {pire_twr:.1e}")
    return erreurs, detail
