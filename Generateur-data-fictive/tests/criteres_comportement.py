"""Points (a) à (h) du critère C3 du J3, mesurés sur les CSV exportés, sans rien importer du moteur.

Chaque fonction rend (réussi, détail lisible). Les seuils sont ceux du contrat de jalon
(jalons/2026-11-03-generateur-j3-comportements.md), écrits ici une seule fois.
"""
import datetime as dt
import statistics
from pathlib import Path

from conftest import lire

PAC_MEDIAN = (500, 1000)
PHASES = (2, 5)
PLATEAU_MOIS = 6
HAUSSES_MAX = 12
REDUCTION_ATYPIQUE = 0.70                 # mois atypique : PAC total ≤ 70 % du mois précédent (ou nul)
MOIS_SANS_PAC_MAX = 0.15
PONCTUEL_BORNES = (100, 10_000)
MULTIPLES_500_MAX = 0.30
RETRAIT_PART_MAX = 0.50
EGALITE_POINTS = 0.02


def donnees(dossier: Path) -> dict:
    comptes = {c["account_id"]: c for c in lire(dossier, "accounts")}
    mvts = [dict(m, date=dt.date.fromisoformat(m["date"]), amount_cad=float(m["amount_cad"]))
            for m in lire(dossier, "external_movements")]
    evs = lire(dossier, "events")
    insts = {i["institution_id"]: i["name"] for i in lire(dossier, "institutions")}
    fin = max(dt.date.fromisoformat(l["date"]) for l in lire(dossier, "market_regimes_daily"))
    premiere = min(dt.date.fromisoformat(c["opened_at"]) for c in comptes.values())
    mois, a, m = [], premiere.year, premiere.month
    while (a, m) <= (fin.year, fin.month):
        mois.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    total = {k: 0.0 for k in mois}
    for x in mvts:
        if x["movement_type"] == "PAC":
            total[(x["date"].year, x["date"].month)] += x["amount_cad"]
    return dict(comptes=comptes, mvts=mvts, evs=evs, insts=insts, mois=mois, total=total)


def a_mediane_pac(d: dict) -> tuple[bool, str]:
    med = statistics.median(d["total"].values())
    return PAC_MEDIAN[0] <= med <= PAC_MEDIAN[1], f"médiane du PAC total mensuel {med:.0f} $ sur {len(d['mois'])} mois"


def b_phases(d: dict) -> tuple[bool, str]:
    n = sum(1 for e in d["evs"] if e["event_type"] == "phase_epargne")
    return PHASES[0] <= n <= PHASES[1], f"{n} phases d'épargne"


def c_plateaux(d: dict) -> tuple[bool, str]:
    valeurs = [d["total"][k] for k in d["mois"]]
    plus_long, courant = 0, 0
    for i, v in enumerate(valeurs):
        courant = courant + 1 if v > 0 and i > 0 and v == valeurs[i - 1] else (1 if v > 0 else 0)
        plus_long = max(plus_long, courant)
    hausses, suite = 0, 0
    for i in range(1, len(valeurs)):
        suite = suite + 1 if valeurs[i] > valeurs[i - 1] else 0
        hausses = max(hausses, suite)
    figes = []
    for a, c in d["comptes"].items():
        pac = [m["amount_cad"] for m in d["mvts"] if m["account_id"] == a and m["movement_type"] == "PAC"]
        if len(pac) >= 2 and len(set(pac)) == 1:
            figes.append(f"{c['account_alias']} ({len(pac)} × {pac[0]:.0f} $)")
    ok = plus_long >= PLATEAU_MOIS and not figes and hausses < HAUSSES_MAX
    return ok, (f"plus long plateau {plus_long} mois ; comptes au PAC figé : {', '.join(figes) or 'aucun'} ; "
                f"plus longue suite de hausses {hausses} mois")


def d_atypiques(d: dict) -> tuple[bool, str]:
    valeurs = [d["total"][k] for k in d["mois"]]
    atypiques = sum(1 for i in range(1, len(valeurs)) if valeurs[i - 1] > 0 and valeurs[i] <= REDUCTION_ATYPIQUE * valeurs[i - 1])
    sans = sum(1 for v in valeurs if v == 0)
    ok = atypiques >= 1 and sans <= MOIS_SANS_PAC_MAX * len(valeurs)
    return ok, f"{atypiques} mois suspendus ou réduits d'au moins 30 % ; {sans} mois sans PAC sur {len(valeurs)}"


def e_ponctuels(d: dict) -> tuple[bool, str]:
    p = [m for m in d["mvts"] if m["movement_type"] == "PONCTUEL"]
    hors = [m["amount_cad"] for m in p if not PONCTUEL_BORNES[0] <= m["amount_cad"] <= PONCTUEL_BORNES[1]]
    annees = sorted({a for a, _ in d["mois"]})
    chaque_annee = []
    for mm in range(1, 13):
        presentes = [a for a in annees if (a, mm) in d["total"]]
        recus = {m["date"].year for m in p if m["date"].month == mm}
        if len(presentes) >= 2 and set(presentes) <= recus:
            chaque_annee.append(mm)
    ok = not hors and not chaque_annee
    return ok, (f"{len(p)} ponctuels, montants hors [100, 10 000] : {hors or 'aucun'} ; mois civils servis chaque année : "
                f"{chaque_annee or 'aucun'}")


def f_multiples(d: dict) -> tuple[bool, str]:
    p = [m["amount_cad"] for m in d["mvts"] if m["movement_type"] == "PONCTUEL"]
    n = sum(1 for x in p if abs(x / 500 - round(x / 500)) < 1e-9)
    part = n / len(p) if p else 0.0
    return part <= MULTIPLES_500_MAX, f"{n} ponctuels multiples de 500 $ sur {len(p)} ({part:.0%})"


def g_retraits(d: dict) -> tuple[bool, str]:
    ordre = {"PAC": 0, "PONCTUEL": 1, "RETRAIT": 2}
    nets: dict[str, float] = {}
    fautifs, n = [], 0
    for m in sorted(d["mvts"], key=lambda x: (x["date"], ordre[x["movement_type"]], x["movement_id"])):
        if m["movement_type"] == "RETRAIT":
            n += 1
            if -m["amount_cad"] > RETRAIT_PART_MAX * nets.get(m["account_id"], 0.0) + 1e-6:
                fautifs.append(m["movement_id"])
        nets[m["account_id"]] = nets.get(m["account_id"], 0.0) + m["amount_cad"]
    return not fautifs, f"{n} retraits ; au-delà de 50 % des apports nets : {fautifs or 'aucun'}"


def h_parts(d: dict) -> tuple[bool, str]:
    parts: dict[str, float] = {}
    for m in d["mvts"]:
        if m["movement_type"] == "PAC":
            i = d["comptes"][m["account_id"]]["institution_id"]
            parts[i] = parts.get(i, 0.0) + m["amount_cad"]
    total = sum(parts.values())
    p = {d["insts"][i]: parts.get(i, 0.0) / total for i in d["insts"]}
    egales = all(abs(x - 1 / 3) < EGALITE_POINTS for x in p.values())
    return not egales, "parts des PAC : " + ", ".join(f"{k} {v:.1%}" for k, v in sorted(p.items()))


POINTS = {"a": a_mediane_pac, "b": b_phases, "c": c_plateaux, "d": d_atypiques, "e": e_ponctuels,
          "f": f_multiples, "g": g_retraits, "h": h_parts}
