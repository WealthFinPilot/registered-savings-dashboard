"""Multi-graines (C3) : graines 1 à 20, liste figée d'avance, aucune écartée.

Bloquant : la validation de l'export (C1) et les invariants du modèle (C2) passent sur les 20 ; la part
des graines où le repère actions mondiales a au moins une année civile complète négative est comprise
entre 30 % et 95 % ; au moins une graine connaît un repli maximal de ce repère supérieur à 25 %.
Diagnostic (imprimé, non bloquant) : taux d'échec des faits stylisés de C3 graine par graine.
"""
import itertools
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
from conftest import TYPICAL, generer, lire

from synthetic_finance.config import charger
from synthetic_finance.market import covariance, spec
from synthetic_finance.validation import valider
from test_market import autocorrelation_carres, correlation_commune, kurtosis_excedentaire, parts_classes, series_csv

GRAINES = tuple(range(1, 21))
REPERE_ACTIONS = "R-ACT-MONDE"


@pytest.fixture(scope="module")
def exports(tmp_path_factory) -> dict[int, Path]:
    racine = tmp_path_factory.mktemp("graines")
    return {g: generer(racine / str(g), g, etape="markets") for g in GRAINES}


@pytest.fixture(scope="module")
def mesures(exports) -> dict[int, dict]:
    sortie = {}
    for g, d in exports.items():
        dates, v = series_csv(d, "benchmarks_daily", "benchmark_id", "index_total_return")[REPERE_ACTIONS]
        annees = {}
        for a in sorted({x[:4] for x in dates}):
            idx = [i for i, x in enumerate(dates) if x.startswith(a)]
            complete = idx[0] > 0 and dates[idx[-1]] >= f"{a}-12-29"
            if complete:
                annees[int(a)] = float(v[idx[-1]] / v[idx[0] - 1] - 1)
        sortie[g] = dict(annees=annees, repli=float((v / np.maximum.accumulate(v) - 1).min()),
                         annualise=float((v[-1] / v[0]) ** (252 / (len(v) - 1)) - 1))
    return sortie


def test_validation_sur_vingt_graines(exports) -> None:
    echecs = defaultdict(list)
    for g, d in exports.items():
        for c in valider(d)["checks"]:
            if c["status"] != "pass":
                echecs[c["name"]].append(g)
    noms = [c["name"] for c in valider(exports[GRAINES[0]])["checks"]]
    for n in noms:
        print(f"{n:<36} échecs {len(echecs.get(n, []))}/{len(GRAINES)} {echecs.get(n) or ''}")
    assert not echecs


def test_invariants_du_modele_sur_vingt_graines(exports) -> None:
    """VL et indices finis et positifs ; transitions de régime permises ; covariances semi-définies
    positives (elles ne dépendent pas de la graine). Le grain journalier relève de la validation."""
    m = spec(charger(TYPICAL))
    permis = {(a, b) for a, r in m.regimes.items() for b in r.next}
    psd = min(float(np.linalg.eigvalsh(covariance(m, r)).min()) for r in m.regimes.values())
    echecs = []
    for g, d in exports.items():
        for table, col in (("fund_prices_daily", "nav_total_return"), ("benchmarks_daily", "index_total_return")):
            x = np.array([float(l[col]) for l in lire(d, table)])
            if not (np.isfinite(x).all() and (x > 0).all()):
                echecs.append(f"graine {g} : {table} non positif")
        suite = [l["regime"] for l in lire(d, "market_regimes_daily")]
        if not {(a, b) for a, b in zip(suite, suite[1:]) if a != b} <= permis:
            echecs.append(f"graine {g} : transition de régime non permise")
    print(f"plus petite valeur propre des covariances {psd:.3e} ; échecs {echecs or 'aucun'}")
    assert psd >= -1e-10 and not echecs


def test_part_des_graines_avec_une_annee_negative(mesures) -> None:
    negatives = [g for g, m in mesures.items() if any(r < 0 for r in m["annees"].values())]
    part = len(negatives) / len(GRAINES)
    for g, m in mesures.items():
        print(f"graine {g:>2} : " + " ".join(f"{a} {r:+.1%}" for a, r in m["annees"].items())
              + f" | annualisé {m['annualise']:+.1%} | repli max {m['repli']:.1%}")
    print(f"graines avec au moins une année civile complète négative : {len(negatives)}/{len(GRAINES)} ({part:.0%})")
    assert 0.30 <= part <= 0.95


def test_au_moins_un_repli_profond(mesures) -> None:
    profonds = sorted(g for g, m in mesures.items() if m["repli"] < -0.25)
    print(f"graines avec un repli maximal du repère actions mondiales au-delà de 25 % : {profonds}")
    assert profonds


def test_taux_d_echec_des_faits_stylises(exports) -> None:
    """Diagnostic : C3 n'impose ces seuils qu'à la graine du scénario ; ici, on les mesure sans bloquer."""
    echecs = defaultdict(list)
    for g, d in exports.items():
        vl = series_csv(d, "fund_prices_daily", "fund_id", "nav_total_return")
        parts = parts_classes(d)
        for f in (f for f in vl if parts[f].get("equity", 0) > 50):
            r = np.diff(np.log(vl[f][1]))
            if kurtosis_excedentaire(r) <= 1:
                echecs["kurtosis excédentaire > 1"].append(f"{g}:{f}")
            if autocorrelation_carres(r) <= 0.05:
                echecs["autocorrélation de r² > 0,05"].append(f"{g}:{f}")
        maxi = max(correlation_commune(vl[a], vl[b]) for a, b in itertools.combinations(sorted(vl), 2))
        if maxi > 0.98:
            echecs["aucune paire > 0,98"].append(f"{g} ({maxi:.3f})")
    for n in ("kurtosis excédentaire > 1", "autocorrélation de r² > 0,05", "aucune paire > 0,98"):
        graines = sorted({int(x.split(":")[0].split(" ")[0]) for x in echecs[n]})
        print(f"{n:<32} graines en échec {len(graines)}/{len(GRAINES)} ({len(graines) / len(GRAINES):.0%}) "
              f"{echecs[n][:8] or ''}")
    assert len(exports) == len(GRAINES)      # diagnostic : imprimé, pas bloquant
