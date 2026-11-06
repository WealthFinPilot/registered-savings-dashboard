"""Exports normalisés : CSV UTF-8, séparateur virgule, point décimal, dates ISO 8601, montants en CAD
sans symbole ni séparateur de milliers. Une valeur vide = NULL. Le format de chaque colonne est
déclaré dans SCHEMAS : c'est aussi le contrat que relit la validation.
"""
import csv
import datetime as dt
import json
import platform
from pathlib import Path

import numpy as np

from . import AVERTISSEMENT, VERSION
from .config import Config

# Type de colonne -> (formatage, lecture). decN : décimal à N chiffres, jamais en notation scientifique.
def _dec(n: int):
    return (lambda v: f"{v:.{n}f}", float)


TYPES = {
    "str": (str, str),
    "int": (lambda v: str(int(v)), int),
    "bool": (lambda v: "true" if v else "false", lambda s: {"true": True, "false": False}[s]),
    "date": (lambda v: v.isoformat(), dt.date.fromisoformat),
    "dec1": _dec(1), "dec2": _dec(2), "dec3": _dec(3), "dec4": _dec(4), "dec6": _dec(6), "dec10": _dec(10),
}

SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "institutions": [("institution_id", "str"), ("name", "str"), ("strategy_profile", "str"), ("opened_at", "date"),
                     ("choice_reason", "str"), ("risk_appetite", "dec4"), ("fee_level", "dec4"),
                     ("savings_weight_prior", "dec4")],
    "accounts": [("account_id", "str"), ("institution_id", "str"), ("regime", "str"), ("account_alias", "str"),
                 ("opened_at", "date"), ("closed_at", "date")],
    "funds": [("fund_id", "str"), ("institution_id", "str"), ("archetype", "str"), ("fund_name", "str"),
              ("currency", "str"), ("inception_date", "date"), ("risk_profile_hint", "str"), ("fee_policy", "str"),
              ("mer_pct", "dec2"), ("account_fee_low_pct", "dec2"), ("account_fee_high_pct", "dec2"),
              ("distribution_frequency", "str"), ("equity_fx_hedged", "bool"), ("fx_exposure_pct", "dec2"),
              ("duration_years", "dec1"), ("rate_sensitivity", "dec2"), ("top10_weight_pct", "dec1"),
              ("trading_cost_pct", "dec2"), ("turnover_pct", "dec1"), ("eligible_regimes", "str")],
    "fund_exposures": [("fund_id", "str"), ("asset_class", "str"), ("geography", "str"), ("style", "str"),
                       ("weight", "dec4")],
    "fund_exposures_by_axis": [("fund_id", "str"), ("axis", "str"), ("category", "str"), ("weight", "dec4")],
    "fund_strategic_targets": [("fund_id", "str"), ("asset_class", "str"), ("target_weight", "dec2")],
    "allocation_targets_history": [("effective_date", "date"), ("level", "str"), ("institution_id", "str"),
                                   ("account_id", "str"), ("fund_id", "str"), ("target_weight", "dec2")],
    # Marchés (J2) : VL en rendement total, distributions réinvesties ; indices base 100
    "fund_prices_daily": [("date", "date"), ("fund_id", "str"), ("nav_total_return", "dec6"), ("currency", "str")],
    "benchmarks": [("benchmark_id", "str"), ("benchmark_type", "str"), ("benchmark_name", "str"), ("fund_id", "str"),
                   ("institution_id", "str"), ("passive_fee_pct", "dec4"), ("composition", "str")],
    "benchmarks_daily": [("date", "date"), ("benchmark_id", "str"), ("index_total_return", "dec6"),
                         ("currency", "str")],
    "market_regimes_daily": [("date", "date"), ("regime", "str")],
    # Comportement (J3) : journal d'événements, flux externes (> 0 apport, < 0 retrait), droits par régime
    "events": [("event_id", "str"), ("date", "date"), ("event_type", "str"), ("institution_id", "str"),
               ("account_id", "str"), ("description", "str"), ("scenario_impact", "str")],
    "external_movements": [("movement_id", "str"), ("date", "date"), ("account_id", "str"), ("movement_type", "str"),
                           ("amount_cad", "dec2"), ("event_id", "str")],
    "contribution_room": [("regime", "str"), ("year", "int"), ("new_room_cad", "dec2"), ("room_start_cad", "dec2"),
                          ("contributions_cad", "dec2"), ("withdrawals_cad", "dec2"), ("room_end_cad", "dec2")],
    "persona": [("year", "int"), ("earned_income_cad", "dec2"), ("celi_eligible", "bool"),
                ("reer_unused_end_cad", "dec2")],
    "tax_limits": [("regime", "str"), ("rubric", "str"), ("year", "int"), ("amount_cad", "dec2"),
                   ("period_end", "date"), ("rule", "str")],
    # Grand livre (J4) : ordres (parts en millièmes, VL du jour), positions et valeurs à la clôture
    "internal_trades": [("trade_id", "str"), ("date", "date"), ("account_id", "str"), ("fund_id", "str"), ("side", "str"),
                        ("units", "dec3"), ("unit_price", "dec6"), ("gross_amount_cad", "dec2"), ("fee_cad", "dec2"),
                        ("movement_id", "str"), ("event_id", "str")],
    "positions_daily": [("date", "date"), ("account_id", "str"), ("fund_id", "str"), ("units", "dec3"),
                        ("market_value_cad", "dec2")],
    "account_values_daily": [("date", "date"), ("account_id", "str"), ("cash_cad", "dec2"), ("invested_value_cad", "dec2"),
                             ("total_value_cad", "dec2")],
    # Mesures (J5) : rendements en fraction (0,01 = 1 %), 10 décimales ; flux externes sans FRAIS, FRAIS ≤ 0 à part
    "performance_daily": [("date", "date"), ("entity_type", "str"), ("entity_id", "str"), ("market_value_cad", "dec2"),
                          ("net_external_flow_cad", "dec2"), ("fees_cad", "dec2"), ("daily_twr", "dec10"),
                          ("cumulative_twr", "dec10")],
    "performance_periods": [("entity_type", "str"), ("entity_id", "str"), ("period", "str"), ("start_date", "date"),
                            ("end_date", "date"), ("days", "int"), ("start_value_cad", "dec2"),
                            ("contributions_cad", "dec2"), ("withdrawals_cad", "dec2"), ("fees_cad", "dec2"),
                            ("investment_result_cad", "dec2"), ("end_value_cad", "dec2"), ("twr", "dec10"),
                            ("mwr", "dec10"), ("mwr_annualized", "bool"), ("mwr_status", "str")],
    "counterfactual_daily": [("date", "date"), ("entity_type", "str"), ("entity_id", "str"), ("benchmark_id", "str"),
                             ("market_value_cad", "dec2"), ("net_external_flow_cad", "dec2"), ("daily_twr", "dec10"),
                             ("cumulative_twr", "dec10")],
}
# Tables écrites par chaque étape, dans l'ordre de la chaîne
TABLES_ETAPE = {
    "universe": ("institutions", "accounts", "funds", "fund_exposures", "fund_exposures_by_axis",
                 "fund_strategic_targets", "allocation_targets_history"),
    "markets": ("fund_prices_daily", "benchmarks", "benchmarks_daily", "market_regimes_daily"),
    # allocation_targets_history (univers) est réécrite par behaviour : lignes du J1 en tête, révisions ensuite
    "behaviour": ("events", "external_movements", "contribution_room", "persona", "tax_limits"),
    # events et external_movements (comportement) sont réécrites par ledger : rééquilibrages et FRAIS ajoutés
    "ledger": ("internal_trades", "positions_daily", "account_values_daily"),
    "performance": ("performance_daily", "performance_periods", "counterfactual_daily"),
    "adapter": (),                           # écrit finance_ve01/, pas data/ (adapter.py)
}


def ecrire_csv(chemin: Path, table: str, lignes: list[dict]) -> None:
    colonnes = SCHEMAS[table]
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c for c, _ in colonnes])
        for l in lignes:
            inconnues = set(l) - {c for c, _ in colonnes}
            if inconnues:
                raise ValueError(f"{table} : colonnes hors schéma {sorted(inconnues)}")
            w.writerow(["" if l[c] is None else TYPES[t][0](l[c]) for c, t in colonnes])


def lire_csv(chemin: Path, table: str) -> list[dict]:
    """Relit un export en types Python ; toute valeur mal formée lève ValueError avec sa ligne."""
    colonnes = SCHEMAS[table]
    with chemin.open(encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        entete = next(r)
        if entete != [c for c, _ in colonnes]:
            raise ValueError(f"{chemin.name} : en-tête {entete} ≠ schéma")
        lignes = []
        for n, valeurs in enumerate(r, 2):
            try:
                lignes.append({c: None if v == "" else TYPES[t][1](v) for (c, t), v in zip(colonnes, valeurs, strict=True)})
            except (ValueError, KeyError) as e:
                raise ValueError(f"{chemin.name}, ligne {n} : {e}") from e
        return lignes


def ecrire_manifest(dossier: Path, cfg: Config, etapes: list[str], entrees: dict | None = None) -> dict:
    manifest = dict(
        scenario_id=f"{cfg.name}_seed_{cfg.seed}", scenario=cfg.name, seed=cfg.seed, config_hash=cfg.hash,
        generated_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), version=VERSION,
        synthetic=True, synthetic_flag=True, notice=AVERTISSEMENT, stages=etapes,
        period=dict(start=cfg.start_date.isoformat(), end=cfg.end_date.isoformat()), currency=cfg.base_currency,
        rng=dict(bit_generator="PCG64", seed_sequence="numpy.random.SeedSequence(seed).spawn",
                 streams=["universe", "markets", "behaviour", "events", "ledger", "adapter"]),
        environment=dict(python=platform.python_version(), numpy=np.__version__),
        tables={t: f"data/{t}.csv" for e in etapes for t in TABLES_ETAPE[e]}, inputs=entrees or {}, config=cfg.raw)
    (dossier / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n",
                                           encoding="utf-8")
    return manifest


def exporter(dossier: Path, cfg: Config, tables: dict[str, list[dict]], etapes: list[str],
             entrees: dict | None = None) -> None:
    donnees = dossier / "data"
    donnees.mkdir(parents=True, exist_ok=True)
    attendues = {t for e in etapes for t in TABLES_ETAPE[e]}
    if set(tables) != attendues:
        raise ValueError(f"tables {sorted(tables)} ≠ tables des étapes {etapes}")
    for table in SCHEMAS:                    # export précédent d'une étape plus longue : retiré, pas mélangé
        if table not in attendues:
            (donnees / f"{table}.csv").unlink(missing_ok=True)
    for table, lignes in tables.items():
        ecrire_csv(donnees / f"{table}.csv", table, lignes)
    ecrire_manifest(dossier, cfg, etapes, entrees)
