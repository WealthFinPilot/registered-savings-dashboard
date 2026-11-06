"""Sûreté fiscale (J3, C2) : graine 20261103 et graines 1 à 20, 21 exécutions, 0 échec attendu.

Les droits sont recalculés ici, indépendamment de synthetic_finance.fiscal : plafonds relus dans
sql/plafonds.sql par une lecture propre au test, situation du personnage relue dans persona.csv, flux
relus dans external_movements.csv. Aucun montant fiscal n'est écrit dans ce fichier : seul le taux de
18 % du revenu gagné (règle R11, canada.ca) y figure, comme dans fiscal.py.
"""
import ast
import datetime as dt
import re
import tomllib
from collections import defaultdict

import pytest
from conftest import PLAFONDS_SQL, RACINE, lire

TAUX_REER = 0.18


def plafonds_sql() -> tuple[dict, dict]:
    texte = PLAFONDS_SQL.read_text(encoding="utf-8")
    montants = {}
    for ligne in texte.splitlines():
        m = re.match(r"\s*\('(\w+)',\s*'(\w+)',\s*(NULL|\d+),\s*([\d.]+),", ligne)
        if m:
            montants[(m[1], m[2], None if m[3] == "NULL" else int(m[3]))] = float(m[4])
    periodes = {int(a): dt.date.fromisoformat(d) for a, d in re.findall(r"\((\d{4}),\s*DATE '([\d-]+)'", texte)}
    return montants, periodes


def recalcul(dossier) -> tuple[list[str], dict]:
    """Rend les dépassements (cotisations > droits) et les droits au début recalculés par (régime, année)."""
    montants, periodes = plafonds_sql()
    comptes = {c["account_id"]: c for c in lire(dossier, "accounts")}
    perso = lire(dossier, "persona")
    revenu = {int(l["year"]): float(l["earned_income_cad"]) for l in perso if l["earned_income_cad"]}
    celi_1 = min(int(l["year"]) for l in perso if l["celi_eligible"] == "true")
    reer_0 = next(float(l["reer_unused_end_cad"]) for l in perso if l["reer_unused_end_cad"])
    debut_horizon = min(dt.date.fromisoformat(l["date"]) for l in lire(dossier, "market_regimes_daily"))

    def annee(regime: str, jour: dt.date) -> int:
        return min(a for a, f in periodes.items() if f >= jour) if regime == "REER" else jour.year

    c, w = defaultdict(float), defaultdict(float)
    for m in lire(dossier, "external_movements"):
        regime, jour, x = comptes[m["account_id"]]["regime"], dt.date.fromisoformat(m["date"]), float(m["amount_cad"])
        if regime != "COMP":
            (c if x > 0 else w)[(regime, annee(regime, jour))] += abs(x)
    annees = sorted({a for _, a in c} | {debut_horizon.year})
    droits, depassements = {}, []
    for a in range(min(annees), max(annees) + 1):
        droits[("CELI", a)] = (sum(montants[("CELI", "plafond_annuel", y)] for y in range(celi_1, a + 1))
                               - sum(v for (r, y), v in c.items() if r == "CELI" and y < a)
                               + sum(v for (r, y), v in w.items() if r == "CELI" and y < a))
    ouvertures = [dt.date.fromisoformat(x["opened_at"]).year for x in comptes.values() if x["regime"] == "CELIAPP"]
    if ouvertures:
        y0 = min(ouvertures)
        for a in range(y0, max(annees) + 1):
            vie = montants[("CELIAPP", "plafond_vie", None)] - sum(v for (r, y), v in c.items() if r == "CELIAPP" and y < a)
            if a == y0:
                droits[("CELIAPP", a)] = min(montants[("CELIAPP", "plafond_annuel", a)], vie)
            else:
                report = min(montants[("CELIAPP", "report_max", None)], max(droits[("CELIAPP", a - 1)] - c[("CELIAPP", a - 1)], 0))
                droits[("CELIAPP", a)] = min(montants[("CELIAPP", "plafond_annuel", a)] + report, vie)
    d0 = annee("REER", debut_horizon)
    inutilises = reer_0
    for a in range(d0, max(annees) + 1):
        droits[("REER", a)] = inutilises + min(TAUX_REER * revenu[a - 1], montants[("REER", "plafond_annuel", a)])
        inutilises = droits[("REER", a)] - c[("REER", a)]
    for cle, v in sorted(c.items()):
        if cle not in droits:
            depassements.append(f"{cle} : cotisations {v:.2f} sans droits calculables")
        elif v > droits[cle] + 0.005:
            depassements.append(f"{cle} : cotisations {v:.2f} > droits {droits[cle]:.2f}")
    return depassements, droits


def test_droits_jamais_depasses(exports_comportement) -> None:
    echecs = {}
    for g, d in exports_comportement.items():
        depassements, _ = recalcul(d)
        if depassements:
            echecs[g] = depassements
    print(f"dépassements de droits : {len(echecs)}/{len(exports_comportement)} exécutions {echecs or ''}")
    assert not echecs


def test_contribution_room_egale_au_recalcul(exports_comportement) -> None:
    ecarts = defaultdict(list)
    for g, d in exports_comportement.items():
        _, droits = recalcul(d)
        for l in lire(d, "contribution_room"):
            cle = (l["regime"], int(l["year"]))
            if cle in droits and abs(float(l["room_start_cad"]) - droits[cle]) > 0.01:
                ecarts[g].append(f"{cle} : exporté {l['room_start_cad']} ≠ recalculé {droits[cle]:.2f}")
    print(f"droits exportés ≠ recalcul indépendant : {len(ecarts)}/{len(exports_comportement)} {dict(ecarts) or ''}")
    assert not ecarts


def test_aucun_retrait_reer_ni_celiapp_et_celiapp_date(exports_comportement) -> None:
    echecs = defaultdict(list)
    for g, d in exports_comportement.items():
        comptes = {c["account_id"]: c for c in lire(d, "accounts")}
        for m in lire(d, "external_movements"):
            c = comptes[m["account_id"]]
            if c["regime"] in ("REER", "CELIAPP") and float(m["amount_cad"]) < 0:
                echecs[g].append(f"{m['movement_id']} retrait {c['regime']}")
            if c["regime"] == "CELIAPP" and (m["date"] < "2023-04-01" or m["date"] < c["opened_at"]):
                echecs[g].append(f"{m['movement_id']} CELIAPP le {m['date']}")
    print(f"retraits REER/CELIAPP ou CELIAPP précoce : {len(echecs)}/{len(exports_comportement)} {dict(echecs) or ''}")
    assert not echecs


def _montants_fiscaux() -> set[float]:
    montants, _ = plafonds_sql()
    return set(montants.values())


@pytest.mark.parametrize("module", ["behaviour.py", "fiscal.py"])
def test_aucun_montant_fiscal_dans_le_code(module: str) -> None:
    interdits = _montants_fiscaux()
    arbre = ast.parse((RACINE / "src" / "synthetic_finance" / module).read_text(encoding="utf-8"))
    trouves = sorted({n.value for n in ast.walk(arbre) if isinstance(n, ast.Constant)
                      and isinstance(n.value, (int, float)) and not isinstance(n.value, bool) and float(n.value) in interdits})
    print(f"{module} : constantes égales à un plafond de sql/plafonds.sql : {trouves or 'aucune'}")
    assert not trouves


def test_aucun_montant_fiscal_dans_la_configuration() -> None:
    interdits = _montants_fiscaux()
    brut = tomllib.loads((RACINE / "configs" / "base.toml").read_text(encoding="utf-8"))

    def nombres(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from nombres(v)
        elif isinstance(x, list):
            for v in x:
                yield from nombres(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            yield float(x)

    trouves = sorted({v for s in ("behaviour", "persona") for v in nombres(brut[s]) if v in interdits})
    print(f"base.toml [behaviour] et [persona] : valeurs égales à un plafond : {trouves or 'aucune'}")
    assert not trouves
