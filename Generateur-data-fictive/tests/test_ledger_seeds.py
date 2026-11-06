"""Grand livre sur la graine 20261103 et les graines 1 à 20 (J4, C2) : comptabilité recalculée depuis les CSV sans
importer ledger.py ; chaque graine est allée au bout du grand livre, donc sans retrait infaisable."""
import pytest
from conftest import GRAINES_COMPORTEMENT
from criteres_grand_livre import comptabilite, lire_export


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_compta_graine(exports_grand_livre, graine: int) -> None:
    t = lire_export(exports_grand_livre[graine])
    erreurs, detail = comptabilite(t)
    retraits = sum(1 for m in t["external_movements"] if m["movement_type"] == "RETRAIT")
    print(f"graine {graine} : {detail} ; {retraits} retraits, tous exécutés")
    assert not erreurs, erreurs[:10]
