"""Adaptateur (J6, C2) sur la graine 20261103 et les graines 1 à 20 : rendement total, calendrier et valeur conservée,
recalculés depuis les CSV par criteres_adaptateur.py, sans importer adapter.py ni charger de base."""
import pytest
from conftest import GRAINES_COMPORTEMENT
from criteres_adaptateur import Export, calendrier, conservation, integrite, rendement


@pytest.fixture(scope="module")
def exports(exports_adaptateur) -> dict[int, Export]:
    return {g: Export(d) for g, d in exports_adaptateur.items()}


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_distribution_graine(exports, graine: int) -> None:
    e = exports[graine]
    resultats = [f(e) for f in (integrite, rendement, calendrier, conservation)]
    print(f"graine {graine} : " + " | ".join(d for _, d in resultats))
    erreurs = [x for r, _ in resultats for x in r]
    assert not erreurs, erreurs[:10]
