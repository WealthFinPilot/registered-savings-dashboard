"""Mesures sur la graine 20261103 et les graines 1 à 20 (J5) : TWR et rendement du marché (C2), réconciliation et MWR
(C3), contrefactuels et écart aux politiques (C4), recalculés sans importer performance.py, sauf la décomposition de
l'écart (diagnostic). Chaque graine est allée au bout des mesures, donc sans retrait infaisable du contrefactuel."""
import statistics

import pytest
from conftest import GRAINES_COMPORTEMENT, TYPICAL
from criteres_performance import contrefactuel, lire_export, marche, periodes, twr

from synthetic_finance.config import charger
from synthetic_finance.performance import ecarts_politique

P = charger(TYPICAL).performance


@pytest.fixture(scope="module")
def exports(exports_performance) -> dict[int, dict]:
    return {g: lire_export(d) for g, d in exports_performance.items()}


@pytest.fixture(scope="module")
def bilans(exports) -> dict[int, tuple]:
    return {g: periodes(t, P["mwr_bounds"], P["annualize_min_days"]) for g, t in exports.items()}


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_twr_graine(exports, graine: int) -> None:
    erreurs, detail = twr(exports[graine])
    e2, _, d2 = marche(exports[graine])
    print(f"graine {graine} : {detail} ; {d2}")
    assert not erreurs + e2, (erreurs + e2)[:10]


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_reconciliation_graine(bilans, graine: int) -> None:
    erreurs, _, detail = bilans[graine]
    print(f"graine {graine} : {detail}")
    assert not [x for x in erreurs if "MWR" not in x], erreurs[:10]


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_mwr_graine(bilans, graine: int) -> None:
    erreurs, bilan, _ = bilans[graine]
    print(f"graine {graine} : motifs {bilan['motifs']}, pire écart à la bissection {bilan['pire_mwr']:.1e}")
    assert not [x for x in erreurs if "MWR" in x], erreurs[:10]


def test_mwr_bilan_graines(bilans) -> None:
    motifs: dict[str, int] = {}
    opposes = periodes_total = 0
    for g, (_, b, _) in bilans.items():
        for k, n in b["motifs"].items():
            motifs[k] = motifs.get(k, 0) + n
        opposes += b["opposes"]
        periodes_total += b["periodes"]
        print(f"graine {g} : {b['periodes']} périodes, motifs {b['motifs']}, TWR et MWR de signes opposés {b['opposes']}")
    print(f"21 graines : {periodes_total} périodes ; MWR par motif {motifs} ; signes opposés {opposes}")


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_contrefactuel_graine(exports, graine: int) -> None:
    erreurs, detail = contrefactuel(exports[graine])
    print(f"graine {graine} : {detail}")
    assert not erreurs, erreurs[:10]


def test_biais_ecart_politique_graines(exports) -> None:
    """Diagnostic sans seuil : écart annualisé institution − politique et sa décomposition, 21 graines × 3 institutions ;
    chaque politique date d'avant le premier apport de son institution."""
    lignes, erreurs = [], []
    for g, t in exports.items():
        premiers: dict[str, object] = {}
        inst = {a["account_id"]: a["institution_id"] for a in t["accounts"]}
        for m in t["external_movements"]:
            if m["movement_type"] in ("PAC", "PONCTUEL"):
                i = inst[m["account_id"]]
                premiers[i] = min(premiers.get(i, m["date"]), m["date"])
        for i, d in premiers.items():
            cible = min(l["effective_date"] for l in t["allocation_targets_history"]
                        if l["level"] == "institution" and l["institution_id"] == i)
            if cible > d:
                erreurs.append(f"graine {g}, R-POL-{i} : cibles du {cible}, premier apport le {d}")
        ecarts = ecarts_politique(t)
        for i in sorted({a["institution_id"] for a in t["accounts"]} - {x["institution_id"] for x in ecarts}):
            print(f"graine {g} {i} : aucun rendement (comptes jamais alimentés), sans écart")
        for x in ecarts:
            lignes.append(x)
            print(f"graine {g} {x['institution_id']} depuis {x['debut']} ({x['annees']:.1f} ans) : TWR {x['twr']:+.2f} %, "
                  f"politique {x['twr_politique']:+.2f} %, écart {x['ecart']:+.2f} = −frais {x['frais']:.2f} "
                  f"(RFG {x['rfg']:.2f} + compte {x['frais_compte']:.2f} − passifs {x['frais_passifs']:.2f}) + reste {x['reste']:+.2f}")

    def resume(cle: str) -> str:
        v = [x[cle] for x in lignes]
        return f"{statistics.mean(v):+.2f} ± {statistics.stdev(v) / len(v) ** 0.5:.2f}"
    gagnants = sum(1 for x in lignes if x["ecart"] > 0)
    print(f"{len(lignes)} institutions × graines : écart moyen {resume('ecart')} pt/an, frais nets moyens {resume('frais')}, "
          f"reste moyen {resume('reste')} (moyenne ± erreur type) ; politique battue en TWR net : {gagnants} fois")
    assert not erreurs, erreurs
