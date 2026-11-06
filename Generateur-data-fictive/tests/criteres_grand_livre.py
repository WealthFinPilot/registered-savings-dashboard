"""Recalcul indépendant du grand livre (J4, C2 et C3), depuis les seuls CSV : ce module n'importe pas ledger.py.

comptabilite() rejoue les ordres jour par jour (parts en millièmes entiers), contrôle positions, valeurs, liens
mouvement → ordres et l'identité patrimoniale ; frais_attendus() recalcule les frais de compte du mois.
"""
import datetime as dt
import math
from pathlib import Path

from synthetic_finance.export import lire_csv

TABLES = ("institutions", "accounts", "funds", "fund_prices_daily", "allocation_targets_history", "events",
          "external_movements", "internal_trades", "positions_daily", "account_values_daily")
RESIDU_PARTS, RESIDU_CENT = 0.0005, 0.005         # demi-millième de part ; vente totale arrondie au cent


def lire_export(dossier: Path) -> dict[str, list[dict]]:
    return {t: lire_csv(dossier / "data" / f"{t}.csv", t) for t in TABLES}


def cents(x: float) -> int:
    return math.floor(x * 100 + 0.5)


def comptabilite(t: dict[str, list[dict]]) -> tuple[list[str], str]:
    erreurs: list[str] = []
    comptes = {c["account_id"]: c for c in t["accounts"]}
    vl = {(l["fund_id"], l["date"]): l["nav_total_return"] for l in t["fund_prices_daily"]}
    jours = sorted({l["date"] for l in t["fund_prices_daily"]})
    mvts = {m["movement_id"]: m for m in t["external_movements"]}
    evs = {e["event_id"]: e for e in t["events"]}
    ordres_jour: dict[dt.date, list[dict]] = {}
    for o in t["internal_trades"]:
        ordres_jour.setdefault(o["date"], []).append(o)
    pos: dict[tuple[dt.date, str], dict[str, dict]] = {}
    for p in t["positions_daily"]:
        pos.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p
    val = {(v["date"], v["account_id"]): v for v in t["account_values_daily"]}

    parts: dict[str, dict[str, int]] = {a: {} for a in comptes}
    resultat = {a: 0.0 for a in comptes}             # Σ parts de la veille × variation de VL
    residu = {a: 0.0 for a in comptes}               # Σ signé (parts × VL − montant), achats + et ventes −
    residu_abs = {a: 0.0 for a in comptes}
    par_lien: dict[str, dict[str, int]] = {}
    pire = 0.0
    veille = None
    for j in jours:
        if veille is not None:
            for a, p in parts.items():
                resultat[a] += sum(u / 1000 * (vl[(f, j)] - vl[(f, veille)]) for f, u in p.items())
        for o in ordres_jour.get(j, ()):
            a, f, u = o["account_id"], o["fund_id"], round(o["units"] * 1000)
            x = vl.get((f, j))
            if x is None or o["unit_price"] != x:
                erreurs.append(f"{o['trade_id']} : prix {o['unit_price']} ≠ VL {x}")
                continue
            signe = 1 if o["side"] == "BUY" else -1
            parts[a][f] = parts[a].get(f, 0) + signe * u
            if parts[a][f] < 0:
                erreurs.append(f"{o['trade_id']} : vente au-delà des parts détenues ({parts[a][f]} millièmes)")
            if parts[a][f] == 0:
                del parts[a][f]
            r = u / 1000 * x - o["gross_amount_cad"]
            pire = max(pire, abs(r) / (RESIDU_PARTS * x + RESIDU_CENT))
            residu[a] += signe * r
            residu_abs[a] += abs(r)
            lien = o["movement_id"] or o["event_id"]
            par_lien.setdefault(lien, {"BUY": 0, "SELL": 0})[o["side"]] += round(o["gross_amount_cad"] * 100)
        for a, c in comptes.items():
            if c["opened_at"] > j:
                continue
            lignes = pos.get((j, a), {})
            if {f: round(p["units"] * 1000) for f, p in lignes.items()} != parts[a]:
                erreurs.append(f"{a} le {j} : positions ≠ ordres rejoués")
            for f, p in lignes.items():
                if round(p["market_value_cad"] * 100) != cents(round(p["units"] * 1000) * vl[(f, j)] / 1000):
                    erreurs.append(f"{a} {f} le {j} : valeur {p['market_value_cad']} ≠ parts × VL au cent")
            v = val.get((j, a))
            if v is None or v["cash_cad"] != 0 or round(v["total_value_cad"] * 100) != sum(
                    round(p["market_value_cad"] * 100) for p in lignes.values()):
                erreurs.append(f"{a} le {j} : valeur du compte ≠ Σ positions, ou encaisse non nulle")
        veille = j

    # Chaque mouvement exécuté exactement une fois ; chaque rééquilibrage, ventes = achats, sans flux externe
    for k, m in mvts.items():
        s = par_lien.get(k)
        sens = "BUY" if m["amount_cad"] > 0 else "SELL"
        if s is None or s[sens] != round(abs(m["amount_cad"]) * 100) or s["SELL" if sens == "BUY" else "BUY"]:
            erreurs.append(f"{k} ({m['movement_type']} {m['amount_cad']:.2f}) : ordres {s}")
    for lien, s in par_lien.items():
        if lien in mvts:
            continue
        if evs.get(lien, {}).get("event_type") != "reequilibrage":
            erreurs.append(f"ordres liés à {lien}, ni mouvement ni rééquilibrage")
        elif s["BUY"] != s["SELL"]:
            erreurs.append(f"{lien} : ventes {s['SELL'] / 100:.2f} ≠ achats {s['BUY'] / 100:.2f}")

    # Identité patrimoniale à l'arrêté : valeur = apports − retraits − frais + résultat de placement, à l'arrondi près
    fin = jours[-1]
    ecarts = []
    for a in comptes:
        flux = sum(m["amount_cad"] for m in mvts.values() if m["account_id"] == a)
        exacte = sum(u / 1000 * vl[(f, fin)] for f, u in parts[a].items())
        exportee = val[(fin, a)]["total_value_cad"] if (fin, a) in val else 0.0
        if abs(exacte - flux - resultat[a] - residu[a]) > 1e-6:
            erreurs.append(f"{a} : valeur exacte {exacte:.6f} ≠ flux + résultat + résidus")
        borne = residu_abs[a] + RESIDU_CENT * len(parts[a]) + 1e-6
        ecarts.append(abs(exportee - flux - resultat[a]))
        if ecarts[-1] > borne:
            erreurs.append(f"{a} : |valeur − flux − résultat| = {ecarts[-1]:.4f} > {borne:.4f}")
    total = sum(v["total_value_cad"] for (d, _), v in val.items() if d == fin)
    flux_total = sum(m["amount_cad"] for m in mvts.values())
    gap_total = abs(total - flux_total - sum(resultat.values()))
    if gap_total > sum(residu_abs.values()) + RESIDU_CENT * sum(len(p) for p in parts.values()) + 1e-6:
        erreurs.append(f"total : |valeur − flux − résultat| = {gap_total:.4f}")
    detail = (f"{len(t['internal_trades'])} ordres, {len(mvts)} mouvements ; résidu d'arrondi Σ {sum(residu_abs.values()):.2f} $, "
              f"pire ordre à {pire:.0%} de sa borne ; valeur à l'arrêté {total:.2f} $ = flux {flux_total:.2f} $ + résultat "
              f"{sum(resultat.values()):.2f} $ (écart {gap_total:.4f} $)")
    return erreurs, detail


def frais_attendus(t: dict[str, list[dict]], seuil_cad: float) -> dict[tuple[dt.date, str], int]:
    """Frais de chaque compte en fin de mois, en cents, recalculés sur les parts avant frais (positions de clôture +
    ventes liées aux FRAIS du jour). Taux sous le palier : account_fee_low_pct ; au-delà : account_fee_high_pct.
    Un frais inférieur à un millième de la part la moins chère du compte n'est pas prélevé."""
    comptes = {c["account_id"]: c for c in t["accounts"]}
    fonds = {f["fund_id"]: f for f in t["funds"]}
    vl = {(l["fund_id"], l["date"]): l["nav_total_return"] for l in t["fund_prices_daily"]}
    jours = sorted({l["date"] for l in t["fund_prices_daily"]})
    fins = [j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month]
    frais_ids = {m["movement_id"] for m in t["external_movements"] if m["movement_type"] == "FRAIS"}
    avant: dict[tuple[dt.date, str], dict[str, int]] = {}
    for p in t["positions_daily"]:
        if p["date"] in fins:
            avant.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = round(p["units"] * 1000)
    for o in t["internal_trades"]:
        if o["movement_id"] in frais_ids:
            d = avant.setdefault((o["date"], o["account_id"]), {})
            d[o["fund_id"]] = d.get(o["fund_id"], 0) + round(o["units"] * 1000)
    attendus = {}
    for j in fins:
        valeurs = {a: {f: cents(u * vl[(f, j)] / 1000) for f, u in avant.get((j, a), {}).items()} for a in comptes}
        actif: dict[str, int] = {}
        for a, v in valeurs.items():
            actif[comptes[a]["institution_id"]] = actif.get(comptes[a]["institution_id"], 0) + sum(v.values())
        for a, v in valeurs.items():
            if not v:
                continue
            colonne = "account_fee_high_pct" if actif[comptes[a]["institution_id"]] >= seuil_cad * 100 else "account_fee_low_pct"
            montant = cents(sum(x / 100 * fonds[f][colonne] / 100 / 12 for f, x in v.items()))
            if math.floor(montant / 100 / min(vl[(f, j)] for f in v) * 1000 + 0.5) > 0:
                attendus[(j, a)] = montant
    return attendus
