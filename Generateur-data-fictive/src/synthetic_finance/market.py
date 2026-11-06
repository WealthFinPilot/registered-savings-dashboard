"""Moteur B — marchés : facteurs latents à régimes, volatilité regroupée, VL des fonds.

Le moteur ne lit que les fonds et leurs expositions (univers J1), jamais les comptes ni les versements :
il produit les prix que le portefeuille détienne ou non les fonds. Tout est tiré du flux « markets »
de la graine, en cinq sous-flux dans un ordre figé (régimes, chocs, sauts, niveaux, fonds).

Construction, au pas journalier ouvrable t :
- régime R_t : chaîne de Markov, sortie géométrique de durée moyenne configurée ;
- chocs ε_t : 17 Student-t indépendants, réduits à une variance 1 ;
- facteurs F_t = μ(R_t) + √h_t · A(R_t) · ε_t (+ sauts sur le facteur actions mondial). La covariance
  journalière d'un régime vaut A · Aᵀ : semi-définie positive par construction ;
- h_t : variance commune GARCH(1,1) de moyenne 1, nourrie par le choc mondial (sauts compris) ;
- taux : taux fantômes d'Ornstein-Uhlenbeck, sans plancher ; taux observé = softplus du fantôme
  (positif, sans borne) ; la variation du taux observé est le facteur qui fait le prix des obligations ;
- fonds : r = F · b + portage + (alpha − RFG) / an + bruit propre + sauts propres, en rendement
  logarithmique ; VL = VL₀ · exp(Σ r), donc strictement positive. Aucun rendement n'est écrêté.
"""
import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from .config import GEOGRAPHIES, STYLE_FACTORS, Config, ConfigError, MarketSpec, RegimeSpec
from .rng import flux, generateurs

FACTEURS = tuple(f"equity_{g}" for g in GEOGRAPHIES) + (
    "rate_canada", "rate_global", "slope", "credit", "fx_usd_cad") + tuple(f"style_{s}" for s in STYLE_FACTORS) + (
    "real_assets",)
CHOCS = ("global",) + tuple(f"region_{g}" for g in GEOGRAPHIES) + (
    "rate_common", "rate_canada", "rate_global", "slope", "credit", "fx") + tuple(f"style_{s}" for s in STYLE_FACTORS) + (
    "real_assets",)
IF = {f: i for i, f in enumerate(FACTEURS)}
IC = {c: i for i, c in enumerate(CHOCS)}
SOUS_FLUX = ("regimes", "shocks", "jumps", "levels", "funds")
# Style d'actions -> (facteur, signe) ; « value » est le côté court du facteur croissance
STYLE_CHARGE = {"growth": ("style_growth", 1.0), "value": ("style_growth", -1.0),
                "dividend": ("style_dividend", 1.0), "quality": ("style_quality", 1.0)}
# Niveaux de taux qui rémunèrent le revenu fixe (Canada, reste du monde) et l'encaisse (taux court)
PORTAGES: tuple[str, ...] = ("rate_canada", "rate_global", "short")


def jours_ouvrables(debut: dt.date, fin: dt.date) -> list[dt.date]:
    """Lundi à vendredi, bornes comprises ; jours fériés non modélisés (convention du contrat de données)."""
    n = (fin - debut).days + 1
    return [j for j in (debut + dt.timedelta(days=k) for k in range(n)) if j.weekday() < 5]


# ------------------------------------------------------------------------------------------------
# Structure des facteurs
# ------------------------------------------------------------------------------------------------
def matrice_charges(m: MarketSpec, r: RegimeSpec) -> np.ndarray:
    """A (facteurs × chocs), en unités journalières : rendement log pour les actions, le change et les
    styles ; variation de taux (décimale) pour les taux, la pente et le crédit."""
    A = np.zeros((len(FACTEURS), len(CHOCS)))
    jour = math.sqrt(m.trading_days_per_year)
    vm, svm = r.vol_multiplier, r.specific_vol_multiplier
    for g in GEOGRAPHIES:
        beta, propre = m.regions[g]
        A[IF[f"equity_{g}"], IC["global"]] = m.global_equity_vol_pct / 100 / jour * vm * beta
        A[IF[f"equity_{g}"], IC[f"region_{g}"]] = propre / 100 / jour * vm * svm

    def correle(facteur: str, sigma: float, rho: float, propres: dict[str, float]) -> None:
        """Facteur = σ · [ρ · choc mondial + √(1 − ρ²) · Σ √part · choc propre] (parts de total 1)."""
        A[IF[facteur], IC["global"]] = sigma * rho
        for choc, part in propres.items():
            A[IF[facteur], IC[choc]] = sigma * math.sqrt(1 - rho ** 2) * math.sqrt(part)

    t = m.rates
    cs = t["common_share"]
    correle("rate_canada", t["canada_vol_bp"] / 1e4 / jour * vm, r.rates_equity_rho,
            {"rate_common": cs, "rate_canada": 1 - cs})
    correle("rate_global", t["global_vol_bp"] / 1e4 / jour * vm, r.rates_equity_rho,
            {"rate_common": cs, "rate_global": 1 - cs})
    correle("slope", t["slope_vol_bp"] / 1e4 / jour * vm, 0.0, {"slope": 1.0})
    correle("credit", t["credit_vol_bp"] / 1e4 / jour * vm, t["credit_equity_rho"], {"credit": 1.0})
    correle("fx_usd_cad", m.fx["vol_pct"] / 100 / jour * vm, m.fx["equity_rho"], {"fx": 1.0})
    for s in STYLE_FACTORS:
        correle(f"style_{s}", m.styles[s]["vol_pct"] / 100 / jour * vm, m.styles[s]["equity_rho"], {f"style_{s}": 1.0})
    correle("real_assets", m.real_assets["vol_pct"] / 100 / jour * vm, 0.0, {"real_assets": 1.0})
    return A


def covariance(m: MarketSpec, r: RegimeSpec) -> np.ndarray:
    """Covariance journalière des facteurs dans un régime, à variance GARCH moyenne (h = 1)."""
    A = matrice_charges(m, r)
    return A @ A.T


def derive(m: MarketSpec, r: RegimeSpec, regionale: dict[str, float]) -> np.ndarray:
    """Dérive journalière des facteurs dans un régime (le rappel des taux vers leur moyenne s'y ajoute)."""
    j = m.trading_days_per_year
    mu = np.zeros(len(FACTEURS))
    for g in GEOGRAPHIES:
        mu[IF[f"equity_{g}"]] = (m.regions[g][0] * r.equity_drift_pct + regionale[g]) / 100 / j
    mu[IF["rate_canada"]] = mu[IF["rate_global"]] = r.yield_drift_bp / 1e4 / j
    mu[IF["credit"]] = r.credit_drift_bp / 1e4 / j
    mu[IF["fx_usd_cad"]] = r.fx_drift_pct / 100 / j
    for s in STYLE_FACTORS:
        mu[IF[f"style_{s}"]] = r.style_drift_pct[s] / 100 / j
    return mu


def transitions(m: MarketSpec) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Matrice de transition journalière et loi stationnaire de la chaîne des régimes."""
    cles = list(m.regimes)
    P = np.zeros((len(cles), len(cles)))
    for i, k in enumerate(cles):
        sortie = 12 / (m.regimes[k].mean_duration_months * m.trading_days_per_year)
        P[i, i] = 1 - sortie
        for suivant, p in m.regimes[k].next.items():
            P[i, cles.index(suivant)] = sortie * p
    # Loi stationnaire : P^(2^24) (élévations au carré successives), lignes identiques si la chaîne
    # est irréductible et apériodique
    Q = P.copy()
    for _ in range(24):
        Q = Q @ Q
    if np.ptp(Q, axis=0).max() > 1e-9:
        raise ConfigError("markets.regimes : chaîne de Markov sans loi stationnaire unique")
    return cles, P, Q[0] / Q[0].sum()


def spec(cfg: Config) -> MarketSpec:
    if cfg.markets is None:
        raise ConfigError("markets : section absente de la configuration")
    return cfg.markets


def _student(rng: np.random.Generator, df: float, taille) -> np.ndarray:
    """Student-t réduite à une variance 1."""
    return rng.standard_t(df, taille) * math.sqrt((df - 2) / df)


# ------------------------------------------------------------------------------------------------
# Simulation des facteurs
# ------------------------------------------------------------------------------------------------
@dataclass
class Marche:
    dates: list[dt.date]
    regimes: list[str]                        # régime de chaque jour
    facteurs: np.ndarray                      # jours × FACTEURS ; ligne 0 nulle (jour de départ)
    niveaux: dict[str, np.ndarray]            # taux annuels décimaux : rate_canada, rate_global, short
    variance: np.ndarray                      # h_t
    sauts: np.ndarray                         # saut log du facteur mondial, par jour
    derive_regionale: dict[str, float]        # % par an, tirée par graine
    parametres: dict = field(default_factory=dict)


def simuler_facteurs(cfg: Config, r: dict[str, np.random.Generator]) -> Marche:
    m = spec(cfg)
    dates = jours_ouvrables(cfg.start_date, cfg.end_date)
    n, j = len(dates), m.trading_days_per_year

    # Régimes : état initial stationnaire, puis une transition par jour
    cles, P, pi = transitions(m)
    u = r["regimes"].random(n)
    etat = np.empty(n, dtype=int)
    etat[0] = int(np.searchsorted(np.cumsum(pi), u[0], side="right"))
    cumul = np.cumsum(P, axis=1)
    cumul[:, -1] = 1.0                  # u < 1 : l'indice tombe toujours dans la chaîne
    for t in range(1, n):
        etat[t] = int(np.searchsorted(cumul[etat[t - 1]], u[t], side="right"))
    regs = [m.regimes[cles[e]] for e in etat]

    # Chocs, sauts du facteur mondial (Poisson, taille normale ; somme de c sauts ~ N(c·μ, √c·σ))
    eps = _student(r["shocks"], m.shock_df, (n, len(CHOCS)))
    intensite = np.array([g.jump_rate_per_year / j for g in regs])
    nombre = r["jumps"].poisson(intensite)
    z = r["jumps"].standard_normal(n)
    sauts = np.array([c * g.jump_size_pct[0] / 100 + math.sqrt(c) * g.jump_size_pct[1] / 100 * zz
                      for c, g, zz in zip(nombre, regs, z)])
    sauts[0] = 0.0

    # Niveaux de départ et dérives régionales
    lv, t_ = r["levels"], m.rates
    y_ca0 = float(lv.uniform(*t_["canada_initial_pct"])) / 100
    y_gl0 = float(lv.uniform(*t_["global_initial_pct"])) / 100
    theta_ca = float(lv.uniform(*t_["long_run_pct"])) / 100
    theta_gl = float(lv.uniform(*t_["long_run_pct"])) / 100
    ecart_court = float(lv.uniform(*t_["short_spread_pct"])) / 100
    regionale = {g: float(lv.normal(0, m.regional_drift_sigma_pct)) for g in GEOGRAPHIES}

    A = {k: matrice_charges(m, m.regimes[k]) for k in cles}
    mu = {k: derive(m, m.regimes[k], regionale) for k in cles}
    sigma_mondial = {k: m.global_equity_vol_pct / 100 / math.sqrt(j) * m.regimes[k].vol_multiplier for k in cles}
    beta_eq = np.array([m.regions[f.removeprefix("equity_")][0] if f.startswith("equity_") else 0.0
                        for f in FACTEURS])
    kappa = t_["mean_reversion_per_year"] / j
    omega = 1 - m.garch_alpha - m.garch_beta

    lam = t_["lower_bound_smoothing_bp"] / 1e4

    def observe(x):
        """Taux observé = softplus du taux fantôme (Black) : ≈ x au-dessus de quelques λ, tend vers 0
        sans jamais l'atteindre en dessous. Lissage continu, aucune borne."""
        return lam * np.logaddexp(0.0, x / lam)

    F = np.zeros((n, len(FACTEURS)))
    h = np.ones(n)                      # départ à la variance moyenne
    s_ca, s_gl = np.empty(n), np.empty(n)   # taux fantômes (Ornstein-Uhlenbeck, sans plancher)
    s_ca[0], s_gl[0] = y_ca0, y_gl0
    x_prec = None
    for t in range(1, n):
        k = cles[etat[t]]
        if x_prec is not None:
            h[t] = omega + m.garch_alpha * x_prec ** 2 + m.garch_beta * h[t - 1]
        F[t] = mu[k] + math.sqrt(h[t]) * (A[k] @ eps[t]) + beta_eq * sauts[t]
        s_ca[t] = s_ca[t - 1] + F[t, IF["rate_canada"]] + kappa * (theta_ca - s_ca[t - 1])
        s_gl[t] = s_gl[t - 1] + F[t, IF["rate_global"]] + kappa * (theta_gl - s_gl[t - 1])
        x_prec = math.sqrt(h[t]) * eps[t, IC["global"]] + sauts[t] / sigma_mondial[k]   # choc mondial réduit
    y_ca, y_gl = observe(s_ca), observe(s_gl)
    # Le facteur de taux est la variation du taux observé : c'est elle qui fait le prix des obligations
    F[1:, IF["rate_canada"]] = np.diff(y_ca)
    F[1:, IF["rate_global"]] = np.diff(y_gl)
    niveaux = dict(rate_canada=y_ca, rate_global=y_gl, short=observe(s_ca - ecart_court))
    return Marche(dates, [cles[e] for e in etat], F, niveaux, h, sauts, regionale,
                  dict(y_canada_initial=y_ca0, y_global_initial=y_gl0, theta_canada=theta_ca, theta_global=theta_gl,
                       short_spread=ecart_court))


# ------------------------------------------------------------------------------------------------
# Expositions -> charges factorielles
# ------------------------------------------------------------------------------------------------
@dataclass
class Charges:
    b: np.ndarray                            # charge sur chaque facteur
    portage: dict[str, float]                # part rémunérée par chaque niveau de taux (PORTAGES)
    classes: dict[str, float]                # parts par classe d'actifs (0 à 1)


def charges(cellules: list[dict], duration: float | None, fx_exposure_pct: float, m: MarketSpec) -> Charges:
    """Charges factorielles déduites des expositions : actions par région et style, revenu fixe par
    duration (Canada ou reste du monde), encaisse au taux court, actifs réels, part non couverte en devises.
    Les cellules portent un poids en % (0 à 100)."""
    b = np.zeros(len(FACTEURS))
    portage: dict[str, float] = dict.fromkeys(PORTAGES, 0.0)
    classes: dict[str, float] = {}
    d = duration or 0.0
    for c in cellules:
        w = c["weight"] / 100
        classe, g = c["asset_class"], c["geography"]
        classes[classe] = classes.get(classe, 0.0) + w
        if classe == "equity":
            b[IF[f"equity_{g}"]] += w
            if c["style"] in STYLE_CHARGE:
                f, signe = STYLE_CHARGE[c["style"]]
                b[IF[f]] += signe * w
        elif classe == "fixed_income":
            if duration is None:
                raise ConfigError("revenu fixe sans duration : expositions incohérentes")
            taux = "rate_canada" if g == "canada" else "rate_global"
            b[IF[taux]] -= w * d
            b[IF["slope"]] -= w * d * (d - 5) / 5
            b[IF["credit"]] -= w * d * m.rates["credit_duration_share"]
            portage[taux] += w
        elif classe == "cash":
            portage["short"] += w
        else:                                # actifs réels : part actions de la région + facteur propre
            b[IF[f"equity_{g}"]] += w * m.real_assets["equity_beta"]
            b[IF["real_assets"]] += w
    b[IF["fx_usd_cad"]] = fx_exposure_pct / 100
    return Charges(b, portage, classes)


def rendements(ch: Charges, marche: Marche, frais_pct: float, j: int) -> np.ndarray:
    """Rendements log journaliers d'une exposition passive, nets de frais annuels ; jour 0 nul. Le
    portage rémunère au niveau de la veille."""
    r = marche.facteurs @ ch.b
    for k, w in ch.portage.items():
        if w:
            r[1:] += w * marche.niveaux[k][:-1] / j
    r[1:] -= frais_pct / 100 / j
    r[0] = 0.0
    return r


# ------------------------------------------------------------------------------------------------
# Fonds
# ------------------------------------------------------------------------------------------------
@dataclass
class Fonds:
    fund_id: str
    charges: Charges
    tracking_error_pct: float
    alpha_pct: float
    debut: int                               # indice du premier jour coté
    vl0: float
    rendements: np.ndarray                   # log, jour 0 nul
    vl: np.ndarray                           # NaN avant le premier jour coté


def simuler_fonds(cfg: Config, marche: Marche, funds: list[dict], cellules: list[dict],
                  rng: np.random.Generator) -> list[Fonds]:
    m = spec(cfg)
    j, n = m.trading_days_per_year, len(marche.dates)
    p = m.funds
    sortie = []
    for f in funds:                          # ordre de l'univers : tirages stables d'une exécution à l'autre
        ch = charges([c for c in cellules if c["fund_id"] == f["fund_id"]], f["duration_years"],
                     f["fx_exposure_pct"], m)
        ecart = sum(w * float(rng.uniform(*p["tracking_error_pct"][k])) for k, w in sorted(ch.classes.items()))
        alpha = float(rng.normal(0, p["alpha_te_ratio"] * ecart))
        bruit = _student(rng, p["idiosyncratic_df"], n) * ecart / 100 / math.sqrt(j)
        nombre = rng.poisson(p["jump_rate_per_year"] / j, n)
        sauts = np.sqrt(nombre) * rng.standard_normal(n) * p["jump_sigma_pct"] / 100 \
            * (ch.classes.get("equity", 0) + ch.classes.get("other", 0))
        vl0 = float(math.exp(rng.uniform(*np.log(p["initial_nav"]))))
        r = rendements(ch, marche, f["mer_pct"], j)
        r[1:] += alpha / 100 / j + bruit[1:] + sauts[1:]
        debut = next((t for t, d in enumerate(marche.dates) if d >= max(cfg.start_date, f["inception_date"])), None)
        if debut is None:
            raise ConfigError(f"{f['fund_id']} : lancé après la fin de l'horizon")
        if f["inception_date"] > cfg.start_date:
            vl0 = p["launch_nav"]
        vl = np.full(n, np.nan)
        vl[debut:] = vl0 * np.exp(np.cumsum(np.r_[0.0, r[debut + 1:]]))
        sortie.append(Fonds(f["fund_id"], ch, ecart, alpha, debut, vl0, r, vl))
    return sortie


@dataclass
class ResultatMarche:
    marche: Marche
    fonds: list[Fonds]
    reperes: list                            # benchmarks.Repere

    def tables(self) -> dict[str, list[dict]]:
        dates = self.marche.dates
        prix = [dict(date=dates[t], fund_id=f.fund_id, nav_total_return=float(f.vl[t]), currency="CAD")
                for f in self.fonds for t in range(f.debut, len(dates))]
        reperes = [dict(benchmark_id=b.benchmark_id, benchmark_type=b.benchmark_type, benchmark_name=b.name,
                        fund_id=b.fund_id, institution_id=b.institution_id, passive_fee_pct=b.passive_fee_pct,
                        composition=b.composition) for b in self.reperes]
        indices = [dict(date=dates[t], benchmark_id=b.benchmark_id, index_total_return=float(b.indice[t]), currency="CAD")
                   for b in self.reperes for t in range(len(dates))]
        regimes = [dict(date=d, regime=k) for d, k in zip(dates, self.marche.regimes)]
        return dict(fund_prices_daily=prix, benchmarks=reperes, benchmarks_daily=indices,
                    market_regimes_daily=regimes)


def simuler_marches(cfg: Config, tables: dict[str, list[dict]], seed: int | None = None) -> ResultatMarche:
    """Point d'entrée : lit funds, fund_exposures et les cibles initiales des institutions (repères de
    politique), rien d'autre de l'univers."""
    from .benchmarks import construire_reperes
    spec(cfg)
    # Graine du flux : argument (tests), sinon scenario.market_seed, sinon la graine du scénario
    graine = seed if seed is not None else cfg.market_seed if cfg.market_seed is not None else cfg.seed
    r = generateurs(flux(graine)["markets"], SOUS_FLUX)
    marche = simuler_facteurs(cfg, r)
    fonds = simuler_fonds(cfg, marche, tables["funds"], tables["fund_exposures"], r["funds"])
    cibles = [l for l in tables["allocation_targets_history"] if l["level"] == "institution"]
    reperes = construire_reperes(cfg, marche, tables["funds"], tables["fund_exposures"], cibles)
    return ResultatMarche(marche, fonds, reperes)
