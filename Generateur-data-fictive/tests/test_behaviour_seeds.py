"""Comportement multi-graines (J3, C3) : graines 1 à 20, liste figée d'avance, aucune écartée.

Le taux d'échec de chaque point (a) à (h) est imprimé. Bloquant sur les 20 graines : (f) au plus 30 % de
ponctuels multiples de 500 $ et (g) chaque retrait ≤ 50 % des apports nets ; au moins un retrait sur
l'horizon dans au moins la moitié des graines. La validation de l'export passe sur toutes.
"""
from collections import defaultdict

import pytest
from conftest import GRAINE
from criteres_comportement import POINTS, donnees

from synthetic_finance.validation import valider

BLOQUANTS = ("f", "g")


@pytest.fixture(scope="module")
def mesures(exports_comportement) -> dict[int, dict]:
    return {g: donnees(d) for g, d in exports_comportement.items() if g != GRAINE}


def test_validation_sur_vingt_graines(exports_comportement) -> None:
    echecs = defaultdict(list)
    for g, d in exports_comportement.items():
        if g == GRAINE:
            continue
        for c in valider(d)["checks"]:
            if c["status"] != "pass":
                echecs[c["name"]].append(g)
    noms = [c["name"] for c in valider(exports_comportement[1])["checks"] if c["name"].startswith("comportement_")]
    for n in noms:
        print(f"{n:<34} échecs {len(echecs.get(n, []))}/20 {echecs.get(n) or ''}")
    assert not echecs, dict(echecs)


def test_taux_d_echec_par_point(mesures) -> None:
    echecs = defaultdict(list)
    for g, d in mesures.items():
        for p, f in POINTS.items():
            ok, detail = f(d)
            if not ok:
                echecs[p].append((g, detail))
    for p in sorted(POINTS):
        liste = echecs.get(p, [])
        statut = "bloquant" if p in BLOQUANTS else "diagnostic"
        print(f"({p}) {statut:<10} graines en échec {len(liste)}/20 ({len(liste) / 20:.0%}) {[g for g, _ in liste]}")
        for g, detail in liste:
            print(f"      graine {g:>2} : {detail}")
    assert not any(echecs.get(p) for p in BLOQUANTS)


def test_retraits_dans_la_moitie_des_graines(mesures) -> None:
    avec = [g for g, d in mesures.items() if any(m["movement_type"] == "RETRAIT" for m in d["mvts"])]
    print(f"graines avec au moins un retrait : {len(avec)}/20 {avec}")
    assert len(avec) >= 10
