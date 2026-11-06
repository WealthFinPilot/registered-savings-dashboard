"""Invariants de l'univers (C2) : sur la graine du scénario, sur des graines tirées par hypothesis, et
contrôles négatifs (le validateur doit refuser un export corrompu)."""
import datetime as dt
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest
from conftest import TYPICAL, generer, lire, reecrire
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from synthetic_finance.config import ConfigError, charger, construire, lire_toml
from synthetic_finance.validation import valider

CELIAPP = dt.date(2023, 4, 1)


def invariants(dossier: Path) -> None:
    """Contrôles écrits indépendamment du validateur, sur les CSV bruts."""
    inst, comptes, fonds = lire(dossier, "institutions"), lire(dossier, "accounts"), lire(dossier, "funds")
    cellules, cibles = lire(dossier, "fund_exposures"), lire(dossier, "allocation_targets_history")

    # Exactement 3 institutions ; 12 à 18 fonds, 4 à 6 par institution
    assert len(inst) == 3
    ids_inst = {i["institution_id"] for i in inst}
    assert 12 <= len(fonds) <= 18
    par_inst = defaultdict(int)
    for f in fonds:
        par_inst[f["institution_id"]] += 1
    assert set(par_inst) == ids_inst and all(4 <= n <= 6 for n in par_inst.values())

    # Aucune clé en double ni orpheline
    for lignes, cle in ((inst, "institution_id"), (comptes, "account_id"), (comptes, "account_alias"),
                        (fonds, "fund_id"), (fonds, "fund_name")):
        assert len({l[cle] for l in lignes}) == len(lignes), cle
    assert len({(c["fund_id"], c["asset_class"], c["geography"], c["style"]) for c in cellules}) == len(cellules)
    ids_fonds = {f["fund_id"]: f for f in fonds}
    ids_comptes = {c["account_id"]: c for c in comptes}
    assert all(c["institution_id"] in ids_inst for c in comptes)
    assert all(f["institution_id"] in ids_inst for f in fonds)
    assert all(c["fund_id"] in ids_fonds for c in cellules)
    for c in cibles:
        assert c["fund_id"] in ids_fonds and c["institution_id"] in ids_inst
        assert ids_fonds[c["fund_id"]]["institution_id"] == c["institution_id"]
        if c["level"] == "account":
            assert ids_comptes[c["account_id"]]["institution_id"] == c["institution_id"]

    # Chaque axe à 100 % ± 0,01 par fonds : cellules conjointes, puis vue publiée par axe, qui doit en
    # être la marge exacte
    par_axe = lire(dossier, "fund_exposures_by_axis")
    for fid in ids_fonds:
        assert abs(sum(float(c["weight"]) for c in cellules if c["fund_id"] == fid) - 100) <= 0.01, fid
        for axe in ("asset_class", "geography", "style"):
            publie = {l["category"]: float(l["weight"]) for l in par_axe if l["fund_id"] == fid and l["axis"] == axe}
            assert abs(sum(publie.values()) - 100) <= 0.01, (fid, axe)
            marge = defaultdict(float)
            for c in cellules:
                if c["fund_id"] == fid:
                    marge[c[axe]] += float(c["weight"])
            assert publie.keys() == marge.keys() and all(abs(publie[k] - marge[k]) < 1e-6 for k in marge)

    # Quatre régimes ; alias distinct du régime ; aucun CELIAPP avant le 2023-04-01
    assert {c["regime"] for c in comptes} == {"CELI", "CELIAPP", "REER", "COMP"}
    for c in comptes:
        assert c["account_alias"] != c["regime"] and c["account_alias"].startswith(c["regime"] + "-")
        if c["regime"] == "CELIAPP":
            assert dt.date.fromisoformat(c["opened_at"]) >= CELIAPP

    # Parts cibles des institutions : pas toutes à moins de 2 points de 33,3 %
    poids = [float(i["savings_weight_prior"]) for i in inst]
    assert abs(sum(poids) - 1) < 1e-6
    assert not all(abs(p - 1 / 3) < 0.02 for p in poids)


def test_scenario_typique(export_typique: Path) -> None:
    invariants(export_typique)
    r = valider(export_typique)
    assert r["passed"], [c for c in r["checks"] if c["status"] == "fail"]


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_graines_quelconques(seed: int) -> None:
    with tempfile.TemporaryDirectory() as d:
        dossier = generer(Path(d), seed)
        invariants(dossier)
        r = valider(dossier)
        assert r["passed"], (seed, [c for c in r["checks"] if c["status"] == "fail"])


# ------------------------------------------------------------------------------------------------
# Le validateur refuse un export corrompu
# ------------------------------------------------------------------------------------------------
def _echecs(dossier: Path) -> set[str]:
    return {c["name"] for c in valider(dossier)["checks"] if c["status"] == "fail"}


def test_refuse_axe_a_99(export_typique: Path) -> None:
    lignes = lire(export_typique, "fund_exposures")
    lignes[0]["weight"] = f"{float(lignes[0]['weight']) - 1:.4f}"
    reecrire(export_typique, "fund_exposures", lignes)
    assert "expositions_100" in _echecs(export_typique)


def test_refuse_fonds_orphelin(export_typique: Path) -> None:
    lignes = lire(export_typique, "fund_exposures")
    lignes[0]["fund_id"] = "F999"
    reecrire(export_typique, "fund_exposures", lignes)
    assert "references" in _echecs(export_typique)


def test_refuse_celiapp_premature(export_typique: Path) -> None:
    lignes = lire(export_typique, "accounts")
    for l in lignes:
        if l["regime"] == "CELIAPP":
            l["opened_at"] = "2023-03-31"
    reecrire(export_typique, "accounts", lignes)
    assert "celiapp_apres_ouverture_du_regime" in _echecs(export_typique)


def test_refuse_tiers_egaux(export_typique: Path) -> None:
    lignes = lire(export_typique, "institutions")
    for l, p in zip(lignes, ("0.3333", "0.3333", "0.3334")):
        l["savings_weight_prior"] = p
    reecrire(export_typique, "institutions", lignes)
    assert "poids_institutions_asymetriques" in _echecs(export_typique)


def test_refuse_doublon_alias(export_typique: Path) -> None:
    lignes = lire(export_typique, "accounts")
    lignes[1]["account_alias"] = lignes[0]["account_alias"]
    reecrire(export_typique, "accounts", lignes)
    assert {"cles_uniques", "regimes_et_alias"} & _echecs(export_typique)


def test_refuse_valeur_mal_formee(export_typique: Path) -> None:
    lignes = lire(export_typique, "funds")
    lignes[0]["mer_pct"] = "0,25"
    reecrire(export_typique, "funds", lignes)
    assert _echecs(export_typique) == {"lecture_export"}


# ------------------------------------------------------------------------------------------------
# Configuration : refus explicite, jamais de correction silencieuse
# ------------------------------------------------------------------------------------------------
def test_config_repartition_fausse_refusee() -> None:
    raw = lire_toml(TYPICAL)
    raw["archetypes"]["monetaire"]["asset_class"] = {"cash": 90, "fixed_income": 5}
    with pytest.raises(ConfigError, match="monetaire.asset_class"):
        construire(raw)


def test_config_quatre_institutions_refusee() -> None:
    raw = lire_toml(TYPICAL)
    raw["institutions"].append(dict(raw["institutions"][0], name="Société 4"))
    with pytest.raises(ConfigError, match="exactement 3"):
        construire(raw)


def test_heritage_remplace_une_repartition(tmp_path: Path) -> None:
    (tmp_path / "base.toml").write_text(TYPICAL.with_name("base.toml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "x.toml").write_text('extends = "base.toml"\n[archetypes.obligations_canadiennes]\n'
                                     'fixed_income_geography = { canada = 100 }\n', encoding="utf-8")
    cfg = charger(tmp_path / "x.toml")
    assert cfg.archetypes["obligations_canadiennes"].fixed_income_geography == {"canada": 100.0}
