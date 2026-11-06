"""Comportement (J3, C3 sur la graine 20261103 ; C4 : aucune anticipation).

C3 : chaque point (a) à (h) du contrat est bloquant sur la graine 20261103.
C4 : remplacer les VL et indices à partir d'une date t (autre graine, hausse, krach) ne change ni les
événements, ni les mouvements, ni les cibles datés au plus tard t ; graine 20261103 et graines 1 à 20.
"""
import datetime as dt

import numpy as np
import pytest
from conftest import GRAINE, GRAINES_COMPORTEMENT, PLAFONDS_SQL, TYPICAL
from criteres_comportement import POINTS, donnees

from synthetic_finance.behaviour import simuler_comportement
from synthetic_finance.config import charger
from synthetic_finance.fiscal import lire_plafonds
from synthetic_finance.market import simuler_marches
from synthetic_finance.universe import construire_univers


@pytest.fixture(scope="module")
def typique(exports_comportement) -> dict:
    return donnees(exports_comportement[GRAINE])


@pytest.mark.parametrize("point", sorted(POINTS))
def test_point_c3_graine_typique(typique, point: str) -> None:
    ok, detail = POINTS[point](typique)
    print(f"({point}) {detail}")
    assert ok, detail


def test_chaque_mouvement_a_son_evenement(typique) -> None:
    evs = {e["event_id"]: e for e in typique["evs"]}
    sans = [m["movement_id"] for m in typique["mvts"]
            if m["event_id"] not in evs or dt.date.fromisoformat(evs[m["event_id"]]["date"]) > m["date"]]
    print(f"{len(typique['mvts'])} mouvements, {len(evs)} événements ; sans événement antérieur : {sans or 'aucun'}")
    assert not sans


# ------------------------------------------------------------------------------------------------
# Aucune anticipation (C4)
# ------------------------------------------------------------------------------------------------
MARCHE = {"fund_prices_daily": "nav_total_return", "benchmarks_daily": "index_total_return"}


def _variantes(tables: dict, autre: dict) -> dict:
    """Marchés de remplacement à partir de t : une autre graine ; une hausse (×2) qui porte le repère à un
    nouveau sommet, donc efface tout repli dès t ; un krach (×0,5) qui creuse un repli de plus de 50 %."""
    def echelle(f: float):
        return lambda nom, t: [l | {MARCHE[nom]: l[MARCHE[nom]] * f} for l in tables[nom] if l["date"] >= t]
    return {"autre graine": lambda nom, t: [l for l in autre[nom] if l["date"] >= t],
            "hausse": echelle(2.0), "krach": echelle(0.5)}


def _remplacer(tables: dict, t: dt.date, apres) -> dict:
    modifiees = dict(tables)
    for nom in MARCHE:
        modifiees[nom] = [l for l in tables[nom] if l["date"] < t] + apres(nom, t)
    return modifiees


def _jusqu_a(c, t: dt.date) -> tuple:
    """Tout ce qui est daté au plus tard t : une décision du jour t ne connaît que la clôture de la veille."""
    return ([e for e in c.events if e["date"] <= t], [m for m in c.external_movements if m["date"] <= t],
            [l for l in c.allocation_targets_history if l["effective_date"] <= t])


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_aucune_anticipation(graine: int) -> None:
    cfg = charger(TYPICAL, graine)
    tables = construire_univers(cfg).tables()
    tables |= simuler_marches(cfg, tables).tables()
    variantes = _variantes(tables, simuler_marches(cfg, tables, seed=graine + 1).tables())
    plafonds = lire_plafonds(PLAFONDS_SQL)
    reference = simuler_comportement(cfg, tables, plafonds)
    jours = sorted({l["date"] for l in tables["market_regimes_daily"]})
    decisions = [e["date"] for e in reference.events if e["event_type"] == "prudence_marche"]
    # La graine typique doit porter au moins une décision liée au marché, sinon le test ne prouve rien
    assert decisions or graine != GRAINE, "graine typique sans décision liée au marché"

    # Coupures : une tirée d'avance dans chaque sixième de l'horizon (graine fixe), puis le jour et la veille
    # de chaque décision liée au marché
    rng = np.random.default_rng(graine)
    coupures = {jours[int(rng.choice(x))] for x in np.array_split(np.arange(1, len(jours)), 6)}
    for d in decisions:
        coupures |= {d, jours[jours.index(d) - 1]}
    for t in sorted(coupures):
        for nom, apres in variantes.items():
            variante = simuler_comportement(cfg, _remplacer(tables, t, apres), plafonds)
            assert _jusqu_a(reference, t) == _jusqu_a(variante, t), f"coupure {t}, marché « {nom} »"

    # Sensibilité : un marché changé dès la veille d'une décision la supprime. Le test voit donc bien la lecture
    # du marché, et la coupure au jour même, qui n'y change rien, borne cette lecture à la veille.
    for d in decisions:
        variante = simuler_comportement(cfg, _remplacer(tables, jours[jours.index(d) - 1], variantes["hausse"]), plafonds)
        assert not any(e["date"] == d and e["event_type"] == "prudence_marche" for e in variante.events),             f"décision du {d} insensible au marché de la veille"
    print(f"graine {graine} : {len(coupures)} coupures × {len(variantes)} marchés ; décisions liées au marché : "
          f"{', '.join(map(str, decisions)) or 'aucune'}")
