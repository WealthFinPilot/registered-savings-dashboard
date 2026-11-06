"""Adaptateur (J6), graine 20261103 : refus de toute autre base (C1), intégrité des fichiers (C1), distributions sans
rendement fictif (C2), recalculées par criteres_adaptateur.py sans importer adapter.py."""
import importlib.util
from pathlib import Path

import psycopg
import pytest
from conftest import generer
from criteres_adaptateur import Export, calendrier, conservation, integrite, rendement

PROJET = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def export(tmp_path_factory) -> Export:
    return Export(generer(tmp_path_factory.mktemp("adaptateur") / "typical", etape="adapter"))


def chargeur():
    spec = importlib.util.spec_from_file_location("charger_synthetique", PROJET / "scripts" / "charger_synthetique.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refus_autre_base(export: Export, monkeypatch, capsys) -> None:
    """Base « postgres » : arrêt (code 2) au contrôle de current_database(), avant tout psql ou COPY ; finance_ve01
    reste telle quelle."""
    module = chargeur()
    appels = []
    monkeypatch.setattr(module, "psql", lambda *a: appels.append(("psql", a)))
    monkeypatch.setattr(module, "charger", lambda *a: appels.append(("copy", a)))
    with psycopg.connect(f"host=localhost port=5432 dbname={module.BASE} user=finance") as cx:
        avant = cx.execute("SELECT count(*), coalesce(max(horodatage)::text, '') FROM fait.transaction, "
                           "(SELECT max(horodatage) AS horodatage FROM fait.chargement) c").fetchone()
    with pytest.raises(SystemExit) as fin:
        module.main(["--path", str(export.dossier), "--dbname", "postgres"])
    with psycopg.connect(f"host=localhost port=5432 dbname={module.BASE} user=finance") as cx:
        apres = cx.execute("SELECT count(*), coalesce(max(horodatage)::text, '') FROM fait.transaction, "
                           "(SELECT max(horodatage) AS horodatage FROM fait.chargement) c").fetchone()
    message = capsys.readouterr().err.strip()
    print(f"code {fin.value.code} ; « {message} » ; appels psql ou COPY : {len(appels)} ; finance_ve01 avant {avant}, "
          f"après {apres}")
    assert fin.value.code == 2 and not appels and avant == apres and "refusée" in message


def test_integrite(export: Export) -> None:
    erreurs, detail = integrite(export)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_distribution_rendement_total(export: Export) -> None:
    erreurs, detail = rendement(export)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_distribution_calendrier(export: Export) -> None:
    erreurs, detail = calendrier(export)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_distribution_valeur_conservee(export: Export) -> None:
    erreurs, detail = conservation(export)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_repere_categorie(export: Export) -> None:
    """J6b, C2 : chaque fonds a exactement un ref.repere, son repère de catégorie (lu dans la configuration brute),
    de poids 1, et l'indice de ce repère est publié dans pub.cours."""
    import csv
    import tomllib
    racine = Path(__file__).resolve().parents[1]
    brut = tomllib.loads((racine / "configs" / "base.toml").read_text(encoding="utf-8"))
    de = {a: f"R-CAT-{k.upper().replace('_', '-')}" for k, v in brut["markets"]["benchmarks"]["category"].items()
          for a in v["archetypes"]}

    def lire(nom: str) -> list[dict]:
        with nom.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    fonds = lire(export.dossier / "data" / "funds.csv")
    lignes = lire(export.dossier / "finance_ve01" / "ref.repere.csv")
    symboles = {l["symbole"] for l in lire(export.dossier / "finance_ve01" / "pub.cours.csv")}
    for f in fonds:
        r = [l for l in lignes if l["code_fa"] == f["fund_id"]]
        assert len(r) == 1 and r[0]["symbole"] == f"SYN-{de[f['archetype']]}" and float(r[0]["poids"]) == 1.0, f["fund_id"]
        assert r[0]["symbole"] in symboles
    assert len(lignes) == len(fonds)
    print(f"{len(fonds)} fonds, {len({l['symbole'] for l in lignes})} repères de catégorie distincts dans ref.repere")
