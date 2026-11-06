"""Lecture et validation de la configuration (TOML, héritage par « extends »).

Toute incohérence lève ConfigError avec le chemin de la clé fautive : rien n'est corrigé en silence.
"""
import datetime as dt
import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ASSET_CLASSES = ("equity", "fixed_income", "cash", "other")
GEOGRAPHIES = ("canada", "united_states", "europe", "asia_pacific", "emerging", "other")
EQUITY_STYLES = ("broad_market", "growth", "value", "dividend", "quality")
# Style d'une classe autre que les actions : un seul, imposé par la classe
CLASS_STYLE = {"fixed_income": "fixed_income", "cash": "cash", "other": "real_assets"}
STYLES = EQUITY_STYLES + tuple(CLASS_STYLE.values())
PROFILES = ("prudent", "balanced", "growth")        # ordre de risque croissant attendu
DISTRIBUTIONS = ("monthly", "annual")


class ConfigError(ValueError):
    pass


def _exiger(condition: object, chemin: str, message: str) -> None:
    if not condition:
        raise ConfigError(f"{chemin} : {message}")


# Tables qui sont une répartition ou une pondération : une surcharge les remplace en entier (fusionnées,
# elles garderaient les catégories du parent et ne totaliseraient plus 100)
ENTIERES = {"strategic", "asset_class", "equity_geography", "fixed_income_geography", "cash_geography",
            "other_geography", "equity_style", "archetype_affinity", "regime_affinity",
            "next", "style_drift_pct", "regions", "tracking_error_pct", "passive_fee_pct",
            "phase_multiplier", "phase_weights", "pac_rounding", "atypical_types", "lump_types",
            "lump_capacity_multiple", "lump_rounding"}


def _fusion(base: dict, surcharge: dict) -> dict:
    """Fusion profonde : les tables se fusionnent, sauf ENTIERES ; le reste (listes comprises) se remplace."""
    sortie = dict(base)
    for cle, valeur in surcharge.items():
        if isinstance(valeur, dict) and isinstance(sortie.get(cle), dict) and cle not in ENTIERES:
            sortie[cle] = _fusion(sortie[cle], valeur)
        else:
            sortie[cle] = valeur
    return sortie


def lire_toml(chemin: Path, _vus: tuple[Path, ...] = ()) -> dict:
    chemin = chemin.resolve()
    _exiger(chemin not in _vus, str(chemin), "héritage circulaire")
    _exiger(chemin.is_file(), str(chemin), "fichier de configuration introuvable")
    brut = tomllib.loads(chemin.read_text(encoding="utf-8"))
    parent = brut.pop("extends", None)
    if parent is None:
        return brut
    return _fusion(lire_toml(chemin.parent / parent, _vus + (chemin,)), brut)


# ------------------------------------------------------------------------------------------------
# Contrôles élémentaires
# ------------------------------------------------------------------------------------------------
def _plage(valeur: Any, chemin: str, bas: float | None = None, haut: float | None = None) -> tuple[float, float]:
    _exiger(isinstance(valeur, list) and len(valeur) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valeur),
            chemin, "attendu [min, max] numériques")
    a, b = float(valeur[0]), float(valeur[1])
    _exiger(a <= b, chemin, f"min {a} > max {b}")
    _exiger(bas is None or a >= bas, chemin, f"min {a} < {bas}")
    _exiger(haut is None or b <= haut, chemin, f"max {b} > {haut}")
    return a, b


def _repartition(valeur: Any, chemin: str, categories: tuple[str, ...]) -> dict[str, float]:
    """Moyenne de Dirichlet en % : catégories connues, poids > 0, total 100."""
    _exiger(isinstance(valeur, dict) and valeur, chemin, "table de pourcentages attendue")
    inconnues = set(valeur) - set(categories)
    _exiger(not inconnues, chemin, f"catégories inconnues {sorted(inconnues)}")
    _exiger(all(isinstance(v, (int, float)) and v > 0 for v in valeur.values()), chemin, "poids > 0 attendus")
    _exiger(abs(sum(valeur.values()) - 100) < 1e-9, chemin, f"total {sum(valeur.values())} ≠ 100")
    return {c: float(valeur[c]) for c in categories if c in valeur}


def _nombre(valeur: Any, chemin: str, bas: float | None = None, haut: float | None = None) -> float:
    _exiger(isinstance(valeur, (int, float)) and not isinstance(valeur, bool), chemin, "nombre attendu")
    _exiger(bas is None or valeur >= bas, chemin, f"{valeur} < {bas}")
    _exiger(haut is None or valeur <= haut, chemin, f"{valeur} > {haut}")
    return float(valeur)


def _date(valeur: Any, chemin: str) -> dt.date:
    _exiger(isinstance(valeur, dt.date) and not isinstance(valeur, dt.datetime), chemin, "date AAAA-MM-JJ attendue")
    return valeur


# ------------------------------------------------------------------------------------------------
# Objets de configuration
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    strategic: dict[str, float]
    asset_class: dict[str, float]
    asset_class_concentration: float
    equity_geography: dict[str, float]
    fixed_income_geography: dict[str, float]
    cash_geography: dict[str, float]
    other_geography: dict[str, float]
    geography_concentration: float
    equity_style: dict[str, float]
    style_concentration: float
    mer_pct: tuple[float, float]
    account_fee_pct: tuple[float, float]
    duration_years: tuple[float, float] | None
    distribution: str
    equity_hedge_probability: float
    trading_cost_pct: tuple[float, float]
    turnover_pct: tuple[float, float]
    top10_weight_pct: tuple[float, float]

    @property
    def strategic_equity(self) -> float:
        return self.strategic.get("equity", 0.0) / 100


@dataclass(frozen=True)
class InstitutionSpec:
    name: str
    strategy_profile: str
    risk_appetite: tuple[float, float]
    fund_count: tuple[int, int]
    fee_level: tuple[float, float]
    savings_bias: float
    reasons: tuple[str, ...]
    core_archetypes: tuple[str, ...]
    archetype_affinity: dict[str, float]
    regime_affinity: dict[str, float]


@dataclass(frozen=True)
class RegimeSpec:
    key: str
    mean_duration_months: float
    next: dict[str, float]                  # probabilités du régime suivant, total 1
    equity_drift_pct: float
    vol_multiplier: float
    specific_vol_multiplier: float
    rates_equity_rho: float
    yield_drift_bp: float
    credit_drift_bp: float
    fx_drift_pct: float
    style_drift_pct: dict[str, float]
    jump_rate_per_year: float
    jump_size_pct: tuple[float, float]      # [moyenne, écart-type]


@dataclass(frozen=True)
class MarketSpec:
    trading_days_per_year: int
    shock_df: float
    garch_alpha: float
    garch_beta: float
    regimes: dict[str, RegimeSpec]
    global_equity_vol_pct: float
    regional_drift_sigma_pct: float
    regions: dict[str, tuple[float, float]]  # géographie -> (beta, volatilité propre %)
    rates: dict[str, Any]
    fx: dict[str, float]
    styles: dict[str, dict[str, float]]
    real_assets: dict[str, float]
    funds: dict[str, Any]
    passive_fee_pct: dict[str, float]
    sensitivity: dict[str, dict[str, Any]]   # repères de contexte : global_equity, balanced
    categories: dict[str, dict[str, Any]]    # repères de catégorie : nom, archétypes comparés, composition


@dataclass(frozen=True)
class Config:
    raw: dict
    name: str
    start_date: dt.date
    end_date: dt.date
    base_currency: str
    seed: int
    market_seed: int | None                  # graine propre au flux markets ; None = seed
    # univers
    fund_count: tuple[int, int]
    regimes: tuple[str, ...]
    celiapp_available_from: dt.date
    fee_tier_threshold_cad: float
    new_fund_probability: float
    new_fund_window_days: tuple[int, int]
    old_fund_age_days: tuple[int, int]
    institution_weight_sigma: float
    min_institution_weight: float
    equal_split_tolerance: float
    min_appetite_gap: float
    first_institution_reason: str
    # comptes
    accounts: dict[str, Any]
    account_count: dict[str, tuple[int, int]]
    # allocations cibles
    policy: dict[str, Any]
    institutions: tuple[InstitutionSpec, ...]
    archetypes: dict[str, Archetype]
    markets: MarketSpec | None = None       # absent : seule l'étape universe est possible
    behaviour: dict[str, Any] | None = None  # absent (avec persona) : pas d'étape behaviour
    persona: dict[str, Any] | None = None
    ledger: dict[str, Any] | None = None     # absent : pas d'étape ledger
    performance: dict[str, Any] | None = None  # absent : pas d'étape performance
    adapter: dict[str, Any] | None = None      # absent : pas d'étape adapter

    @property
    def hash(self) -> str:
        return empreinte(self.raw)


def empreinte(raw: dict) -> str:
    """SHA-256 de la configuration résolue, sérialisée de façon canonique."""
    texte = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _archetype(cle: str, brut: dict[str, Any], defauts: dict[str, Any]) -> Archetype:
    c = f"archetypes.{cle}"
    v = _fusion(defauts, brut)
    _exiger(isinstance(v.get("label"), str) and v["label"], f"{c}.label", "libellé attendu")
    strategic = _repartition(v.get("strategic"), f"{c}.strategic", ASSET_CLASSES)
    effectif = _repartition(v.get("asset_class", v.get("strategic")), f"{c}.asset_class", ASSET_CLASSES)
    _exiger(set(strategic) <= set(effectif), f"{c}.asset_class", "chaque classe du mandat doit être tirée")
    actions = "equity" in effectif
    _exiger(not actions or "equity_geography" in v, f"{c}.equity_geography", "requis : le fonds détient des actions")
    _exiger(not actions or "equity_style" in v, f"{c}.equity_style", "requis : le fonds détient des actions")
    _exiger(v.get("distribution") in DISTRIBUTIONS, f"{c}.distribution", f"attendu {DISTRIBUTIONS}")
    revenu_fixe = "fixed_income" in effectif
    _exiger(not revenu_fixe or "duration_years" in v, f"{c}.duration_years", "requis : le fonds détient du revenu fixe")
    return Archetype(
        key=cle, label=v["label"], strategic=strategic, asset_class=effectif,
        asset_class_concentration=_nombre(v.get("asset_class_concentration"), f"{c}.asset_class_concentration", 1),
        equity_geography=_repartition(v["equity_geography"], f"{c}.equity_geography", GEOGRAPHIES) if actions else {},
        fixed_income_geography=_repartition(v.get("fixed_income_geography"), f"{c}.fixed_income_geography", GEOGRAPHIES),
        cash_geography=_repartition(v.get("cash_geography"), f"{c}.cash_geography", GEOGRAPHIES),
        other_geography=_repartition(v.get("other_geography"), f"{c}.other_geography", GEOGRAPHIES),
        geography_concentration=_nombre(v.get("geography_concentration"), f"{c}.geography_concentration", 1),
        equity_style=_repartition(v["equity_style"], f"{c}.equity_style", EQUITY_STYLES) if actions else {},
        style_concentration=_nombre(v.get("style_concentration"), f"{c}.style_concentration", 1),
        mer_pct=_plage(v.get("mer_pct"), f"{c}.mer_pct", 0, 3),
        account_fee_pct=_plage(v.get("account_fee_pct"), f"{c}.account_fee_pct", 0, 3),
        duration_years=_plage(v["duration_years"], f"{c}.duration_years", 0, 30) if revenu_fixe else None,
        distribution=v["distribution"],
        equity_hedge_probability=_nombre(v.get("equity_hedge_probability"), f"{c}.equity_hedge_probability", 0, 1),
        trading_cost_pct=_plage(v.get("trading_cost_pct"), f"{c}.trading_cost_pct", 0, 2),
        turnover_pct=_plage(v.get("turnover_pct"), f"{c}.turnover_pct", 0, 500),
        top10_weight_pct=_plage(v.get("top10_weight_pct"), f"{c}.top10_weight_pct", 0, 100),
    )


def _institution(i: int, v: dict[str, Any], archetypes: dict, regimes: tuple[str, ...]) -> InstitutionSpec:
    c = f"institutions[{i}]"
    _exiger(isinstance(v.get("name"), str) and v["name"], f"{c}.name", "nom attendu")
    _exiger(v.get("strategy_profile") in PROFILES, f"{c}.strategy_profile", f"attendu {PROFILES}")
    appetit = v.get("risk_appetite")
    _exiger(isinstance(appetit, list) and len(appetit) == 2, f"{c}.risk_appetite", "attendu [moyenne, écart-type]")
    moyenne = _nombre(appetit[0], f"{c}.risk_appetite[0]", 0, 1)
    ecart = _nombre(appetit[1], f"{c}.risk_appetite[1]", 0, 0.5)
    bas, haut = _plage(v.get("fund_count"), f"{c}.fund_count", 1, 20)
    _exiger(bas == int(bas) and haut == int(haut), f"{c}.fund_count", "entiers attendus")
    aff = v.get("archetype_affinity")
    _exiger(isinstance(aff, dict) and aff, f"{c}.archetype_affinity", "table attendue")
    _exiger(set(aff) <= set(archetypes), f"{c}.archetype_affinity", f"archétypes inconnus {sorted(set(aff) - set(archetypes))}")
    _exiger(all(_nombre(x, f"{c}.archetype_affinity", 0) >= 0 for x in aff.values()), f"{c}.archetype_affinity", "≥ 0")
    _exiger(sum(1 for x in aff.values() if x > 0) >= haut, f"{c}.archetype_affinity",
            f"moins d'archétypes possibles que fund_count max ({int(haut)})")
    reg = v.get("regime_affinity")
    _exiger(isinstance(reg, dict) and set(reg) == set(regimes), f"{c}.regime_affinity", f"une affinité par régime {regimes}")
    _exiger(all(_nombre(x, f"{c}.regime_affinity", 0) >= 0 for x in reg.values()), f"{c}.regime_affinity", "≥ 0")
    raisons = v.get("reasons")
    _exiger(isinstance(raisons, list) and raisons and all(isinstance(r, str) for r in raisons), f"{c}.reasons",
            "liste de raisons attendue")
    coeur = v.get("core_archetypes")
    _exiger(isinstance(coeur, list) and coeur and all(aff.get(k, 0) > 0 for k in coeur), f"{c}.core_archetypes",
            "liste non vide d'archétypes d'affinité > 0")
    mu, sigma = v.get("fee_level", [None, None])
    return InstitutionSpec(
        name=v["name"], strategy_profile=v["strategy_profile"], risk_appetite=(moyenne, ecart),
        fund_count=(int(bas), int(haut)),
        fee_level=(_nombre(mu, f"{c}.fee_level[0]", -1, 1), _nombre(sigma, f"{c}.fee_level[1]", 0, 1)),
        savings_bias=_nombre(v.get("savings_bias", 0.0), f"{c}.savings_bias", -3, 3),
        reasons=tuple(raisons), core_archetypes=tuple(coeur), archetype_affinity={k: float(x) for k, x in aff.items()},
        regime_affinity={k: float(reg[k]) for k in regimes})


STYLE_FACTORS = ("growth", "dividend", "quality")


def _table(valeur: Any, chemin: str) -> dict:
    _exiger(isinstance(valeur, dict), chemin, "table attendue")
    return valeur


def _regime(cle: str, v: dict[str, Any]) -> RegimeSpec:
    c = f"markets.regimes.{cle}"
    v = _table(v, c)
    suivants = _table(v.get("next"), f"{c}.next")
    _exiger(suivants and cle not in suivants, f"{c}.next", "au moins un autre régime, jamais lui-même")
    _exiger(all(_nombre(x, f"{c}.next", 0, 1) > 0 for x in suivants.values()), f"{c}.next", "probabilités > 0")
    _exiger(abs(sum(suivants.values()) - 1) < 1e-9, f"{c}.next", f"total {sum(suivants.values())} ≠ 1")
    styles = _table(v.get("style_drift_pct"), f"{c}.style_drift_pct")
    _exiger(set(styles) == set(STYLE_FACTORS), f"{c}.style_drift_pct", f"attendu {STYLE_FACTORS}")
    saut = v.get("jump_size_pct")
    _exiger(isinstance(saut, list) and len(saut) == 2, f"{c}.jump_size_pct", "attendu [moyenne, écart-type]")
    return RegimeSpec(
        key=cle, mean_duration_months=_nombre(v.get("mean_duration_months"), f"{c}.mean_duration_months", 0.5, 240),
        next={k: float(x) for k, x in suivants.items()},
        equity_drift_pct=_nombre(v.get("equity_drift_pct"), f"{c}.equity_drift_pct", -100, 100),
        vol_multiplier=_nombre(v.get("vol_multiplier"), f"{c}.vol_multiplier", 0.1, 5),
        specific_vol_multiplier=_nombre(v.get("specific_vol_multiplier"), f"{c}.specific_vol_multiplier", 0.1, 5),
        rates_equity_rho=_nombre(v.get("rates_equity_rho"), f"{c}.rates_equity_rho", -0.95, 0.95),
        yield_drift_bp=_nombre(v.get("yield_drift_bp"), f"{c}.yield_drift_bp", -1000, 1000),
        credit_drift_bp=_nombre(v.get("credit_drift_bp"), f"{c}.credit_drift_bp", -1000, 1000),
        fx_drift_pct=_nombre(v.get("fx_drift_pct"), f"{c}.fx_drift_pct", -50, 50),
        style_drift_pct={k: _nombre(styles[k], f"{c}.style_drift_pct.{k}", -50, 50) for k in STYLE_FACTORS},
        jump_rate_per_year=_nombre(v.get("jump_rate_per_year"), f"{c}.jump_rate_per_year", 0, 50),
        jump_size_pct=(_nombre(saut[0], f"{c}.jump_size_pct[0]", -50, 50),
                       _nombre(saut[1], f"{c}.jump_size_pct[1]", 0, 50)))


def _composition(v: dict[str, Any], c: str) -> dict[str, Any]:
    """Repère de contexte : répartition par classe, géographie des actions, duration si revenu fixe."""
    classes = _repartition(v.get("asset_class"), f"{c}.asset_class", ASSET_CLASSES)
    _exiger(set(classes) <= {"equity", "fixed_income", "cash"}, f"{c}.asset_class",
            "actions, revenu fixe ou liquidités")
    sortie: dict[str, Any] = dict(asset_class=classes)
    if "equity" in classes:
        sortie["equity_geography"] = _repartition(v.get("equity_geography"), f"{c}.equity_geography", GEOGRAPHIES)
    if "fixed_income" in classes:
        sortie["duration_years"] = _nombre(v.get("duration_years"), f"{c}.duration_years", 0, 30)
    return sortie


def _categorie(v: dict[str, Any], c: str) -> dict[str, Any]:
    """Repère de catégorie : nom, archétypes comparés, puis composition fixe en style « marché large ».
    Contrairement au repère de contexte, il admet les actifs réels et une géographie du revenu fixe."""
    _exiger(isinstance(v.get("name"), str) and v["name"], f"{c}.name", "libellé attendu")
    _exiger(isinstance(v.get("archetypes"), list) and v["archetypes"], f"{c}.archetypes", "liste d'archétypes attendue")
    classes = _repartition(v.get("asset_class"), f"{c}.asset_class", ASSET_CLASSES)
    sortie: dict[str, Any] = dict(name=v["name"], archetypes=tuple(v["archetypes"]), asset_class=classes)
    if "equity" in classes:
        sortie["equity_geography"] = _repartition(v.get("equity_geography"), f"{c}.equity_geography", GEOGRAPHIES)
    if "fixed_income" in classes:
        sortie["duration_years"] = _nombre(v.get("duration_years"), f"{c}.duration_years", 0, 30)
        if "fixed_income_geography" in v:
            sortie["fixed_income_geography"] = _repartition(v["fixed_income_geography"],
                                                            f"{c}.fixed_income_geography", GEOGRAPHIES)
    if "other" in classes:
        sortie["other_geography"] = _repartition(v.get("other_geography"), f"{c}.other_geography", GEOGRAPHIES)
    return sortie


def _marches(m: dict[str, Any]) -> MarketSpec:
    c = "markets"
    _exiger(m.get("method") == "latent_multifactor_regime_switching", f"{c}.method",
            "seule latent_multifactor_regime_switching est implémentée")
    jours = m.get("trading_days_per_year")
    _exiger(isinstance(jours, int) and 200 <= jours <= 270, f"{c}.trading_days_per_year", "entier de 200 à 270")
    garch = _table(m.get("garch"), f"{c}.garch")
    alpha = _nombre(garch.get("alpha"), f"{c}.garch.alpha", 0, 1)
    beta = _nombre(garch.get("beta"), f"{c}.garch.beta", 0, 1)
    _exiger(alpha + beta < 1, f"{c}.garch", "alpha + beta < 1 (variance stationnaire)")
    bruts = _table(m.get("regimes"), f"{c}.regimes")
    _exiger(len(bruts) >= 2, f"{c}.regimes", "au moins deux régimes")
    regimes = {k: _regime(k, v) for k, v in bruts.items()}
    for r in regimes.values():
        _exiger(set(r.next) <= set(regimes), f"{c}.regimes.{r.key}.next",
                f"régimes inconnus {sorted(set(r.next) - set(regimes))}")

    e = _table(m.get("equity"), f"{c}.equity")
    regions = _table(e.get("regions"), f"{c}.equity.regions")
    _exiger(set(regions) == set(GEOGRAPHIES), f"{c}.equity.regions", f"une entrée par géographie {GEOGRAPHIES}")
    for g in GEOGRAPHIES:
        _exiger(isinstance(regions[g], list) and len(regions[g]) == 2, f"{c}.equity.regions.{g}",
                "attendu [beta, volatilité propre %]")
    regions = {g: (_nombre(regions[g][0], f"{c}.equity.regions.{g}[0]", 0, 3),
                   _nombre(regions[g][1], f"{c}.equity.regions.{g}[1]", 0, 100)) for g in GEOGRAPHIES}

    t = _table(m.get("rates"), f"{c}.rates")
    rates: dict[str, Any] = {k: _plage(t.get(k), f"{c}.rates.{k}", -5, 20)
                             for k in ("canada_initial_pct", "global_initial_pct", "long_run_pct", "short_spread_pct")}
    rates |= {k: _nombre(t.get(k), f"{c}.rates.{k}", *bornes) for k, bornes in (
        ("mean_reversion_per_year", (0, 10)), ("canada_vol_bp", (0, 1000)), ("global_vol_bp", (0, 1000)),
        ("common_share", (0, 1)), ("slope_vol_bp", (0, 1000)), ("credit_vol_bp", (0, 1000)),
        ("credit_equity_rho", (-0.95, 0.95)), ("credit_duration_share", (0, 1)),
        ("lower_bound_smoothing_bp", (1, 200)))}

    fx = _table(m.get("fx"), f"{c}.fx")
    styles = _table(m.get("styles"), f"{c}.styles")
    _exiger(set(styles) == set(STYLE_FACTORS), f"{c}.styles", f"attendu {STYLE_FACTORS}")
    reels = _table(m.get("real_assets"), f"{c}.real_assets")

    f = _table(m.get("funds"), f"{c}.funds")
    ecarts = _table(f.get("tracking_error_pct"), f"{c}.funds.tracking_error_pct")
    _exiger(set(ecarts) == set(ASSET_CLASSES), f"{c}.funds.tracking_error_pct", f"une plage par classe {ASSET_CLASSES}")
    funds = dict(
        tracking_error_pct={k: _plage(ecarts[k], f"{c}.funds.tracking_error_pct.{k}", 0, 50) for k in ASSET_CLASSES},
        alpha_te_ratio=_nombre(f.get("alpha_te_ratio"), f"{c}.funds.alpha_te_ratio", 0, 2),
        idiosyncratic_df=_nombre(f.get("idiosyncratic_df"), f"{c}.funds.idiosyncratic_df", 2.01, 1000),
        jump_rate_per_year=_nombre(f.get("jump_rate_per_year"), f"{c}.funds.jump_rate_per_year", 0, 50),
        jump_sigma_pct=_nombre(f.get("jump_sigma_pct"), f"{c}.funds.jump_sigma_pct", 0, 50),
        initial_nav=_plage(f.get("initial_nav"), f"{c}.funds.initial_nav", 0.01),
        launch_nav=_nombre(f.get("launch_nav"), f"{c}.funds.launch_nav", 0.01))

    b = _table(m.get("benchmarks"), f"{c}.benchmarks")
    frais = _table(b.get("passive_fee_pct"), f"{c}.benchmarks.passive_fee_pct")
    _exiger(set(frais) == set(ASSET_CLASSES), f"{c}.benchmarks.passive_fee_pct", f"un taux par classe {ASSET_CLASSES}")
    return MarketSpec(
        trading_days_per_year=jours, shock_df=_nombre(m.get("shock_df"), f"{c}.shock_df", 4.01, 1000),
        garch_alpha=alpha, garch_beta=beta, regimes=regimes,
        global_equity_vol_pct=_nombre(e.get("global_vol_pct"), f"{c}.equity.global_vol_pct", 0, 100),
        regional_drift_sigma_pct=_nombre(e.get("regional_drift_sigma_pct"), f"{c}.equity.regional_drift_sigma_pct", 0, 20),
        regions=regions, rates=rates,
        fx=dict(vol_pct=_nombre(fx.get("vol_pct"), f"{c}.fx.vol_pct", 0, 100),
                equity_rho=_nombre(fx.get("equity_rho"), f"{c}.fx.equity_rho", -0.95, 0.95)),
        styles={k: dict(vol_pct=_nombre(_table(styles[k], f"{c}.styles.{k}").get("vol_pct"), f"{c}.styles.{k}.vol_pct", 0, 100),
                        equity_rho=_nombre(styles[k].get("equity_rho"), f"{c}.styles.{k}.equity_rho", -0.95, 0.95))
                for k in STYLE_FACTORS},
        real_assets=dict(vol_pct=_nombre(reels.get("vol_pct"), f"{c}.real_assets.vol_pct", 0, 100),
                         equity_beta=_nombre(reels.get("equity_beta"), f"{c}.real_assets.equity_beta", 0, 2)),
        funds=funds,
        passive_fee_pct={k: _nombre(frais[k], f"{c}.benchmarks.passive_fee_pct.{k}", 0, 1) for k in ASSET_CLASSES},
        sensitivity={k: _composition(_table(b.get(k), f"{c}.benchmarks.{k}"), f"{c}.benchmarks.{k}")
                     for k in ("global_equity", "balanced")},
        categories={k: _categorie(_table(v, f"{c}.benchmarks.category.{k}"), f"{c}.benchmarks.category.{k}")
                    for k, v in _table(b.get("category"), f"{c}.benchmarks.category").items()})


def _lognormale(valeur: Any, chemin: str) -> tuple[float, float]:
    _exiger(isinstance(valeur, list) and len(valeur) == 2, chemin, "attendu [médiane, sigma log]")
    return _nombre(valeur[0], f"{chemin}[0]", 0), _nombre(valeur[1], f"{chemin}[1]", 0, 3)


def _poids(valeur: Any, chemin: str, cles: tuple[str, ...] | None = None) -> dict[str, float]:
    """Loi catégorielle : poids > 0, normalisés ; clés imposées si « cles »."""
    _exiger(isinstance(valeur, dict) and valeur, chemin, "table de poids attendue")
    _exiger(cles is None or set(valeur) == set(cles), chemin, f"attendu les clés {cles}")
    _exiger(all(_nombre(x, chemin, 0) > 0 for x in valeur.values()), chemin, "poids > 0 attendus")
    total = sum(valeur.values())
    return {k: float(x) / total for k, x in valeur.items()}


def _mois(valeur: Any, chemin: str) -> tuple[float, ...]:
    _exiger(isinstance(valeur, list) and len(valeur) == 12, chemin, "douze poids mensuels attendus")
    return tuple(_nombre(x, f"{chemin}[{i}]", 0.01) for i, x in enumerate(valeur))


PHASES = ("hausse_revenus", "pression_budgetaire", "nouveau_projet", "reprise_epargne")
PONCTUELS = ("prime", "argent_disponible", "cadeau")
ATYPIQUES = ("suspension", "reduction", "report")


def _comportement(b: dict[str, Any]) -> dict[str, Any]:
    c = "behaviour"

    def n(k: str, *bornes) -> float:
        return _nombre(b.get(k), f"{c}.{k}", *bornes)

    def pl(k: str, *bornes) -> tuple[float, float]:
        return _plage(b.get(k), f"{c}.{k}", *bornes)

    entiers = {}
    for k, bornes in (("phase_count", (0, 12)), ("pac_day", (1, 28)), ("pause_months", (1, 12)),
                      ("report_days", (1, 25)), ("refund_months", (1, 12)), ("phase_window_months", (0, 24))):
        a, z = pl(k, *bornes)
        _exiger(a == int(a) and z == int(z), f"{c}.{k}", "entiers attendus")
        entiers[k] = (int(a), int(z))
    multiplicateurs = _table(b.get("phase_multiplier"), f"{c}.phase_multiplier")
    _exiger(set(multiplicateurs) == set(PHASES), f"{c}.phase_multiplier", f"attendu {PHASES}")
    arrondis = {}
    for k in ("pac_rounding", "lump_rounding"):
        poids = _poids(b.get(k), f"{c}.{k}")
        _exiger(all(x.isdigit() and int(x) > 0 for x in poids), f"{c}.{k}", "pas entiers en dollars attendus")
        arrondis[k] = {int(x): w for x, w in poids.items()}
    multiples = _table(b.get("lump_capacity_multiple"), f"{c}.lump_capacity_multiple")
    _exiger(set(multiples) == set(PONCTUELS), f"{c}.lump_capacity_multiple", f"attendu {PONCTUELS}")
    return dict(
        monthly_capacity=_lognormale(b.get("monthly_capacity"), f"{c}.monthly_capacity"),
        revision_noise_sigma=n("revision_noise_sigma", 0, 1),
        phase_min_gap_months=int(n("phase_min_gap_months", 1, 36)),
        phase_multiplier={k: _plage(multiplicateurs[k], f"{c}.phase_multiplier.{k}", 0.1, 3) for k in PHASES},
        phase_weights=_poids(b.get("phase_weights"), f"{c}.phase_weights", PHASES),
        phase_reversion=n("phase_reversion", 0, 20), project_celiapp_boost=n("project_celiapp_boost", 1, 10),
        account_weight_sigma=n("account_weight_sigma", 0, 3),
        account_weight_drift_sigma=n("account_weight_drift_sigma", 0, 3),
        no_pac_probability=n("no_pac_probability", 0, 0.9), min_pac=n("min_pac", 1),
        adjustment_rate_per_year=n("adjustment_rate_per_year", 0, 12), adjustment_sigma=n("adjustment_sigma", 0, 1),
        atypical_rate_per_year=n("atypical_rate_per_year", 0, 12),
        atypical_types=_poids(b.get("atypical_types"), f"{c}.atypical_types", ATYPIQUES),
        reduction_factor=pl("reduction_factor", 0.05, 0.95), pause_rate_per_year=n("pause_rate_per_year", 0, 12),
        lump_rate_per_year=n("lump_rate_per_year", 0, 24),
        lump_month_weights=_mois(b.get("lump_month_weights"), f"{c}.lump_month_weights"),
        lump_types=_poids(b.get("lump_types"), f"{c}.lump_types", PONCTUELS),
        lump_capacity_multiple={k: _lognormale(multiples[k], f"{c}.lump_capacity_multiple.{k}") for k in PONCTUELS},
        lump_bounds_capacity_multiple=pl("lump_bounds_capacity_multiple", 0, 100),
        lump_bounds_cad=pl("lump_bounds_cad", 0),
        reer_season_boost=n("reer_season_boost", 0.1, 10), celi_january_boost=n("celi_january_boost", 0.1, 10),
        refund_probability=n("refund_probability", 0, 1),
        withdrawal_rate_per_year=n("withdrawal_rate_per_year", 0, 12),
        withdrawal_capacity_multiple=_lognormale(b.get("withdrawal_capacity_multiple"),
                                                 f"{c}.withdrawal_capacity_multiple"),
        withdrawal_max_share=n("withdrawal_max_share", 0, 1), withdrawal_min_cad=n("withdrawal_min_cad", 0),
        review_month_weights=_mois(b.get("review_month_weights"), f"{c}.review_month_weights"),
        review_change_probability=n("review_change_probability", 0, 1), review_sigma=n("review_sigma", 0, 3),
        review_pac_probability=n("review_pac_probability", 0, 1),
        new_fund_adoption_probability=n("new_fund_adoption_probability", 0, 1),
        prudence_drawdown_pct=n("prudence_drawdown_pct", -90, 0),
        prudence_monthly_probability=n("prudence_monthly_probability", 0, 1),
        prudence_equity_shift=n("prudence_equity_shift", 0, 1),
        prudence_min_equity_drop=n("prudence_min_equity_drop", 0, 1),
        prudence_duration_months=n("prudence_duration_months", 1, 60),
        scripted_lumps=_ponctuels_imposes(b.get("scripted_lumps", [])),
        **entiers, **arrondis)


def _ponctuels_imposes(v: Any) -> tuple[dict[str, Any], ...]:
    """Ponctuels imposés d'un scénario (cas d'usage du rapport) : date, compte (alias), montant, motif.
    Ils ne consomment aucun tirage et passent outre les droits de cotisation."""
    c = "behaviour.scripted_lumps"
    _exiger(isinstance(v, list), c, "liste de tables attendue")
    sortie = []
    for k, x in enumerate(v):
        ck = f"{c}[{k}]"
        _table(x, ck)
        _exiger(set(x) == {"date", "account", "amount_cad", "reason"}, ck, "clés date, account, amount_cad, reason")
        _exiger(isinstance(x["account"], str) and x["account"], f"{ck}.account", "alias de compte attendu")
        _exiger(isinstance(x["reason"], str) and x["reason"], f"{ck}.reason", "motif attendu")
        sortie.append(dict(date=_date(x["date"], f"{ck}.date"), account=x["account"],
                           amount_cad=_nombre(x["amount_cad"], f"{ck}.amount_cad", 1), reason=x["reason"]))
    return tuple(sorted(sortie, key=lambda x: x["date"]))


def _personnage(v: dict[str, Any]) -> dict[str, Any]:
    c = "persona"
    a, z = _plage(v.get("celi_first_year"), f"{c}.celi_first_year", 2009, 2100)
    _exiger(a == int(a) and z == int(z), f"{c}.celi_first_year", "années entières attendues")
    croissance = v.get("income_growth_pct")
    _exiger(isinstance(croissance, list) and len(croissance) == 2, f"{c}.income_growth_pct", "attendu [moyenne, écart-type]")
    return dict(celi_first_year=(int(a), int(z)),
                earned_income=_lognormale(v.get("earned_income"), f"{c}.earned_income"),
                income_growth_pct=(_nombre(croissance[0], f"{c}.income_growth_pct[0]", -20, 20),
                                   _nombre(croissance[1], f"{c}.income_growth_pct[1]", 0, 20)),
                reer_opening_unused=_plage(v.get("reer_opening_unused"), f"{c}.reer_opening_unused", 0),
                marginal_tax_rate=_plage(v.get("marginal_tax_rate"), f"{c}.marginal_tax_rate", 0, 0.6))


def _grand_livre(v: dict[str, Any]) -> dict[str, Any]:
    c = "ledger"
    return dict(drift_threshold_pts=_plage(v.get("drift_threshold_pts"), f"{c}.drift_threshold_pts", 0.5, 50),
                drift_check_months=_nombre(v.get("drift_check_months"), f"{c}.drift_check_months", 1, 24),
                rebalance_fraction=_plage(v.get("rebalance_fraction"), f"{c}.rebalance_fraction", 0.05, 1),
                full_rebalance_probability=_nombre(v.get("full_rebalance_probability"),
                                                   f"{c}.full_rebalance_probability", 0, 1),
                rebalance_min_cad=_nombre(v.get("rebalance_min_cad"), f"{c}.rebalance_min_cad", 0))


def _mesures(v: dict[str, Any]) -> dict[str, Any]:
    c = "performance"
    bas, haut = _plage(v.get("mwr_bounds"), f"{c}.mwr_bounds", -0.999, 1000)
    _exiger(bas < 0 < haut, f"{c}.mwr_bounds", "l'intervalle doit contenir 0")
    contexte = v.get("context_benchmarks")
    _exiger(isinstance(contexte, list) and all(isinstance(x, str) for x in contexte), f"{c}.context_benchmarks",
            "liste d'identifiants de repères attendue")
    return dict(mwr_bounds=(bas, haut), mwr_grid=int(_nombre(v.get("mwr_grid"), f"{c}.mwr_grid", 10, 10000)),
                annualize_min_days=int(_nombre(v.get("annualize_min_days"), f"{c}.annualize_min_days", 1)),
                context_benchmarks=tuple(contexte))


def _adaptateur(v: dict[str, Any], archetypes: dict[str, Archetype]) -> dict[str, Any]:
    c = "adapter"
    tout = v.get("distribute_all", [])
    _exiger(isinstance(tout, list) and set(tout) <= set(archetypes), f"{c}.distribute_all", "archétypes connus attendus")
    taux = v.get("yield_pct", {})
    _exiger(isinstance(taux, dict), f"{c}.yield_pct", "table archétype = [min, max] attendue")
    manquants = set(archetypes) - set(taux) - set(tout)
    _exiger(not manquants, f"{c}.yield_pct", f"archétypes sans rendement distribué {sorted(manquants)}")
    _exiger(not set(taux) - set(archetypes), f"{c}.yield_pct", f"archétypes inconnus {sorted(set(taux) - set(archetypes))}")
    _exiger(not set(taux) & set(tout), f"{c}.yield_pct", "un archétype de distribute_all n'a pas de rendement fixé")
    return dict(distribute_all=tuple(tout),
                yield_pct={k: _plage(x, f"{c}.yield_pct.{k}", 0, 15) for k, x in taux.items()},
                payment_noise_sigma=_nombre(v.get("payment_noise_sigma"), f"{c}.payment_noise_sigma", 0, 1),
                capital_gain_share=_plage(v.get("capital_gain_share"), f"{c}.capital_gain_share", 0, 1),
                december_window_days=int(_nombre(v.get("december_window_days"), f"{c}.december_window_days", 1, 31)))


def construire(raw: dict[str, Any]) -> Config:
    s, u, a, p = (raw.get(k, {}) for k in ("scenario", "universe", "accounts", "policy"))
    debut, fin = _date(s.get("start_date"), "scenario.start_date"), _date(s.get("end_date"), "scenario.end_date")
    _exiger(debut < fin, "scenario", "start_date doit précéder end_date")
    _exiger(s.get("base_currency") == "CAD", "scenario.base_currency", "seul CAD est simulé")
    _exiger(isinstance(s.get("seed"), int) and s["seed"] >= 0, "scenario.seed", "entier ≥ 0 attendu")
    _exiger(isinstance(s.get("name"), str) and s["name"].isidentifier(), "scenario.name", "identifiant attendu")
    _exiger(s.get("market_seed") is None or isinstance(s["market_seed"], int) and s["market_seed"] >= 0,
            "scenario.market_seed", "entier ≥ 0 attendu, ou absent")

    regimes = tuple(u.get("regimes", ()))
    _exiger(set(regimes) == {"CELI", "CELIAPP", "REER", "COMP"} and len(regimes) == 4, "universe.regimes",
            "les quatre régimes CELI, CELIAPP, REER, COMP")
    nb_bas, nb_haut = _plage(u.get("fund_count"), "universe.fund_count", 1, 60)

    defauts = raw.get("exposure_defaults", {})
    bruts = raw.get("archetypes", {})
    _exiger(isinstance(bruts, dict) and bruts, "archetypes", "au moins un archétype")
    archetypes = {k: _archetype(k, v, defauts) for k, v in bruts.items()}
    libelles = [x.label for x in archetypes.values()]
    _exiger(len(set(libelles)) == len(libelles), "archetypes", "libellés en double")

    insts = raw.get("institutions", [])
    _exiger(isinstance(insts, list) and len(insts) == 3, "institutions", "exactement 3 institutions")
    institutions = tuple(_institution(i, v, archetypes, regimes) for i, v in enumerate(insts))
    _exiger(len({x.name for x in institutions}) == 3, "institutions", "noms en double")
    _exiger(sorted(x.strategy_profile for x in institutions) == sorted(PROFILES), "institutions",
            f"un profil de chaque sorte {PROFILES}")
    _exiger(sum(x.fund_count[0] for x in institutions) >= nb_bas
            and sum(x.fund_count[1] for x in institutions) <= nb_haut, "institutions.fund_count",
            "incompatible avec universe.fund_count")

    comptes = a.get("count", {})
    _exiger(set(comptes) == set(regimes), "accounts.count", "un intervalle par régime")
    account_count = {}
    for r in regimes:
        bas, haut = _plage(comptes[r], f"accounts.count.{r}", 1, 3)
        _exiger(bas == int(bas) and haut == int(haut), f"accounts.count.{r}", "entiers attendus")
        _exiger(haut <= 3, f"accounts.count.{r}", "au plus un compte du régime par institution")
        account_count[r] = (int(bas), int(haut))
    for cle in ("min_per_institution", "first_opening_window_days", "institution_delay_months",
                "institution_delay_max_months", "account_delay_months", "celiapp_delay_months",
                "last_opening_before_end_months"):
        _nombre(a.get(cle), f"accounts.{cle}", 0)
    _exiger(sum(h for _, h in account_count.values()) >= 3 * a["min_per_institution"], "accounts",
            "trop peu de comptes pour min_per_institution")

    _nombre(p.get("preference_concentration"), "policy.preference_concentration", 0.05)
    _exiger(p.get("rounding_step") in (1, 2, 5, 10), "policy.rounding_step", "1, 2, 5 ou 10")
    _plage(p.get("account_funds"), "policy.account_funds", 1, 10)
    _nombre(p.get("account_weight_sigma"), "policy.account_weight_sigma", 0, 2)

    marches = _marches(_table(raw["markets"], "markets")) if "markets" in raw else None
    if marches is not None:
        vus = [a for v in marches.categories.values() for a in v["archetypes"]]
        _exiger(sorted(vus) == sorted(archetypes), "markets.benchmarks.category",
                "chaque archétype dans exactement une catégorie "
                f"(manquants {sorted(set(archetypes) - set(vus))}, inconnus ou doublés "
                f"{sorted(a for a in set(vus) if a not in archetypes or vus.count(a) > 1)})")
    fenetre = _plage(u.get("new_fund_window_days"), "universe.new_fund_window_days", 0)
    age = _plage(u.get("old_fund_age_days"), "universe.old_fund_age_days", 1)
    return Config(
        raw=raw, name=s["name"], start_date=debut, end_date=fin, base_currency="CAD", seed=s["seed"],
        market_seed=s.get("market_seed"),
        fund_count=(int(nb_bas), int(nb_haut)), regimes=regimes,
        celiapp_available_from=_date(u.get("celiapp_available_from"), "universe.celiapp_available_from"),
        fee_tier_threshold_cad=_nombre(u.get("fee_tier_threshold_cad"), "universe.fee_tier_threshold_cad", 0),
        new_fund_probability=_nombre(u.get("new_fund_probability"), "universe.new_fund_probability", 0, 1),
        new_fund_window_days=(int(fenetre[0]), int(fenetre[1])), old_fund_age_days=(int(age[0]), int(age[1])),
        institution_weight_sigma=_nombre(u.get("institution_weight_sigma"), "universe.institution_weight_sigma", 0),
        min_institution_weight=_nombre(u.get("min_institution_weight"), "universe.min_institution_weight", 0, 0.33),
        equal_split_tolerance=_nombre(u.get("equal_split_tolerance"), "universe.equal_split_tolerance", 0, 0.33),
        min_appetite_gap=_nombre(u.get("min_appetite_gap"), "universe.min_appetite_gap", 0, 0.5),
        first_institution_reason=str(u.get("first_institution_reason", "")),
        accounts=dict(a), account_count=account_count, policy=dict(p),
        institutions=institutions, archetypes=archetypes,
        markets=marches,
        behaviour=_comportement(_table(raw["behaviour"], "behaviour")) if "behaviour" in raw else None,
        persona=_personnage(_table(raw["persona"], "persona")) if "persona" in raw else None,
        ledger=_grand_livre(_table(raw["ledger"], "ledger")) if "ledger" in raw else None,
        performance=_mesures(_table(raw["performance"], "performance")) if "performance" in raw else None,
        adapter=_adaptateur(_table(raw["adapter"], "adapter"), archetypes) if "adapter" in raw else None)


def charger(chemin: Path, seed: int | None = None) -> Config:
    """Configuration résolue ; une graine passée en argument remplace scenario.seed et entre dans
    l'empreinte (deux graines = deux configurations distinctes)."""
    raw = lire_toml(Path(chemin))
    if seed is not None:
        raw = _fusion(raw, {"scenario": {"seed": seed}})
    return construire(raw)
