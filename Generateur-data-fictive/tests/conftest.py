import csv
from pathlib import Path

import pytest

from synthetic_finance.adapter import adapter
from synthetic_finance.behaviour import simuler_comportement
from synthetic_finance.config import charger
from synthetic_finance.export import exporter
from synthetic_finance.fiscal import lire_plafonds
from synthetic_finance.ledger import tenir_grand_livre
from synthetic_finance.market import simuler_marches
from synthetic_finance.performance import mesurer
from synthetic_finance.universe import construire_univers

RACINE = Path(__file__).resolve().parent.parent
TYPICAL = RACINE / "configs" / "typical.toml"
GRAINE = 20261103
PLAFONDS_SQL = RACINE.parent / "sql" / "plafonds.sql"     # seule source des plafonds fiscaux
GRAINES_COMPORTEMENT = (GRAINE,) + tuple(range(1, 21))     # liste figée d'avance, aucune écartée


def generer(dossier: Path, seed: int = GRAINE, config: Path = TYPICAL, etape: str = "universe") -> Path:
    cfg = charger(config, seed)
    tables = construire_univers(cfg).tables()
    etapes = ["universe"]
    entrees = {}
    if etape in ("markets", "behaviour", "ledger", "performance", "adapter"):
        tables |= simuler_marches(cfg, tables).tables()
        etapes.append("markets")
    if etape in ("behaviour", "ledger", "performance", "adapter"):
        limites = lire_plafonds(PLAFONDS_SQL)
        tables |= simuler_comportement(cfg, tables, limites).tables()
        etapes.append("behaviour")
        entrees["tax_limits"] = dict(source="sql/plafonds.sql", sha256=limites.sha256)
    if etape in ("ledger", "performance", "adapter"):
        tables |= tenir_grand_livre(cfg, tables).tables()
        etapes.append("ledger")
    if etape in ("performance", "adapter"):
        tables |= mesurer(cfg, tables).tables()
        etapes.append("performance")
    if etape == "adapter":
        etapes.append("adapter")
    exporter(dossier, cfg, tables, etapes, entrees)
    if etape == "adapter":
        adapter(cfg, dossier)
    return dossier


def lire(dossier: Path, table: str) -> list[dict]:
    with (dossier / "data" / f"{table}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def reecrire(dossier: Path, table: str, lignes: list[dict]) -> None:
    with (dossier / "data" / f"{table}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(lignes)


@pytest.fixture
def export_typique(tmp_path: Path) -> Path:
    return generer(tmp_path / "typical")


@pytest.fixture(scope="module")
def export_marche(tmp_path_factory) -> Path:
    return generer(tmp_path_factory.mktemp("marche") / "typical", etape="markets")


@pytest.fixture(scope="session")
def exports_comportement(tmp_path_factory) -> dict[int, Path]:
    """Graine 20261103 puis graines 1 à 20, jusqu'à l'étape behaviour : partagé par les tests du J3."""
    racine = tmp_path_factory.mktemp("comportement")
    return {g: generer(racine / str(g), g, etape="behaviour") for g in GRAINES_COMPORTEMENT}


@pytest.fixture(scope="session")
def exports_grand_livre(tmp_path_factory) -> dict[int, Path]:
    """Graine 20261103 puis graines 1 à 20, jusqu'à l'étape ledger : partagé par les tests du J4."""
    racine = tmp_path_factory.mktemp("grand_livre")
    return {g: generer(racine / str(g), g, etape="ledger") for g in GRAINES_COMPORTEMENT}


@pytest.fixture(scope="session")
def exports_performance(tmp_path_factory) -> dict[int, Path]:
    """Graine 20261103 puis graines 1 à 20, jusqu'à l'étape performance : partagé par les tests du J5."""
    racine = tmp_path_factory.mktemp("performance")
    return {g: generer(racine / str(g), g, etape="performance") for g in GRAINES_COMPORTEMENT}


@pytest.fixture(scope="session")
def exports_adaptateur(tmp_path_factory) -> dict[int, Path]:
    """Graine 20261103 puis graines 1 à 20, jusqu'à l'étape adapter : partagé par les tests du J6."""
    racine = tmp_path_factory.mktemp("adaptateur")
    return {g: generer(racine / str(g), g, etape="adapter") for g in GRAINES_COMPORTEMENT}
