"""Moteur A — univers de placement : institutions, comptes, fonds, expositions, allocations cibles.

Tout est tiré du flux « universe » de la graine, dans un ordre figé : quatre sous-flux (institutions,
fonds, comptes, politique), pour qu'un changement d'une partie ne déplace pas les tirages des autres.
Les contraintes (régimes, ouverture du CELIAPP, poids plancher) sont tenues par rejet explicite d'un
tirage, plafonné : au-delà, ConfigError. Aucune valeur n'est corrigée après coup.
"""
import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from .config import CLASS_STYLE, PROFILES, Archetype, Config, ConfigError
from .rng import flux, generateurs

JOURS_PAR_MOIS = 30.4375
UNITES_EXPOSITION = 1_000_000           # 100 % au dix-millième de point
ESSAIS_MAX = 1000
REGIMES_ELIGIBLES = "CELI|CELIAPP|REER|COMP"
FEE_POLICY = "mer_in_nav+account_fee_tiered"


@dataclass
class Universe:
    institutions: list[dict] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)
    funds: list[dict] = field(default_factory=list)
    fund_exposures: list[dict] = field(default_factory=list)
    fund_exposures_by_axis: list[dict] = field(default_factory=list)
    fund_strategic_targets: list[dict] = field(default_factory=list)
    allocation_targets_history: list[dict] = field(default_factory=list)

    def tables(self) -> dict[str, list[dict]]:
        return dict(self.__dict__)


# ------------------------------------------------------------------------------------------------
# Outils
# ------------------------------------------------------------------------------------------------
def ouvrable(jour: dt.date) -> dt.date:
    """Samedi ou dimanche : lundi suivant. Jours fériés non modélisés (calendrier de marché, J2)."""
    while jour.weekday() >= 5:
        jour += dt.timedelta(days=1)
    return jour


def repartir(poids: list[float], unites: int, minimum: int = 0) -> list[int]:
    """Répartit « unites » entiers au prorata de poids, méthode des plus forts restes, chaque poids
    recevant au moins « minimum ». La somme est exacte."""
    if minimum * len(poids) > unites:
        raise ConfigError(f"répartition impossible : {len(poids)} × {minimum} > {unites}")
    reste = unites - minimum * len(poids)
    total = sum(poids)
    bruts = [reste * p / total for p in poids]
    entiers = [math.floor(b) for b in bruts]
    ordre = sorted(range(len(poids)), key=lambda i: (bruts[i] - entiers[i], -i), reverse=True)
    for i in ordre[:reste - sum(entiers)]:
        entiers[i] += 1
    return [e + minimum for e in entiers]


def _dirichlet(rng: np.random.Generator, moyenne: dict[str, float], concentration: float) -> dict[str, float]:
    """Dirichlet de moyenne « moyenne » (en %) : seules les catégories présentes sont tirées."""
    cles = list(moyenne)
    if len(cles) == 1:
        return {cles[0]: 1.0}
    alpha = np.array([moyenne[k] / 100 for k in cles]) * concentration
    return {k: float(x) for k, x in zip(cles, rng.dirichlet(alpha))}


def _delai(rng: np.random.Generator, moyenne_mois: float, max_jours: int) -> int:
    """Délai exponentiel en jours, tronqué à max_jours par rejet."""
    if max_jours < 0:
        raise ConfigError("fenêtre d'ouverture vide : revoir accounts.* et les dates du scénario")
    for _ in range(ESSAIS_MAX):
        x = rng.exponential(moyenne_mois * JOURS_PAR_MOIS)
        if x <= max_jours:
            return int(x)
    raise ConfigError(f"délai exponentiel de moyenne {moyenne_mois} mois incompatible avec {max_jours} jours")


def indice_risque(classes: dict[str, float], part_emergents: float, top10: float) -> str:
    """Indication de risque, du profil d'exposition (pas de la volatilité, mesurée au J2)."""
    score = classes.get("equity", 0) + 0.8 * classes.get("other", 0) + 0.10 * classes.get("fixed_income", 0)
    if classes.get("equity", 0) >= 0.5:
        score += 0.2 * part_emergents + max(0.0, top10 - 35) / 100
    for seuil, libelle in ((0.12, "Faible"), (0.70, "Faible-Moyen"), (1.00, "Moyen"), (1.15, "Moyen-Élevé")):
        if score < seuil:
            return libelle
    return "Élevé"


# ------------------------------------------------------------------------------------------------
# Institutions
# ------------------------------------------------------------------------------------------------
def _institutions(cfg: Config, rng: np.random.Generator) -> list[dict]:
    specs = cfg.institutions
    rang = [PROFILES.index(s.strategy_profile) for s in specs]
    for _ in range(ESSAIS_MAX):
        appetit = [float(np.clip(rng.normal(*s.risk_appetite), 0.02, 0.98)) for s in specs]
        suite = [a for _, a in sorted(zip(rang, appetit))]
        if all(b - a >= cfg.min_appetite_gap for a, b in zip(suite, suite[1:])):
            break
    else:
        raise ConfigError("risk_appetite et min_appetite_gap : ordre des profils inatteignable")
    frais = [float(math.exp(rng.normal(*s.fee_level))) for s in specs]
    for _ in range(ESSAIS_MAX):          # logistique-normale tronquée
        z = np.array([s.savings_bias for s in specs]) + rng.normal(0, cfg.institution_weight_sigma, len(specs))
        poids = np.exp(z) / np.exp(z).sum()
        if poids.min() >= cfg.min_institution_weight and                 not all(abs(p - 1 / len(specs)) < cfg.equal_split_tolerance for p in poids):
            break
    else:
        raise ConfigError("universe.min_institution_weight ou equal_split_tolerance inatteignable")
    # Ordre d'ouverture : la première dès le départ, les suivantes après un délai exponentiel compté
    # depuis la première
    ordre = [int(i) for i in rng.permutation(len(specs))]
    premiere = ouvrable(cfg.start_date + dt.timedelta(days=int(rng.integers(0, cfg.accounts["first_opening_window_days"] + 1))))
    max_jours = int(cfg.accounts["institution_delay_max_months"] * JOURS_PAR_MOIS)
    delais = sorted(_delai(rng, cfg.accounts["institution_delay_months"], max_jours) for _ in specs[1:])
    ouvertures = {ordre[0]: premiere}
    for i, d in zip(ordre[1:], delais):
        ouvertures[i] = ouvrable(premiere + dt.timedelta(days=d))
    raisons = {ordre[0]: cfg.first_institution_reason or str(rng.choice(specs[ordre[0]].reasons))}
    for i in ordre[1:]:
        raisons[i] = str(rng.choice(specs[i].reasons))
    return [dict(institution_id=f"I{i + 1}", name=s.name, strategy_profile=s.strategy_profile,
                 opened_at=ouvertures[i], choice_reason=raisons[i], risk_appetite=round(appetit[i], 4),
                 fee_level=round(frais[i], 4), savings_weight_prior=float(poids[i]))
            for i, s in enumerate(specs)]


# ------------------------------------------------------------------------------------------------
# Fonds et expositions
# ------------------------------------------------------------------------------------------------
def _geo_moyenne(a: Archetype, classe: str) -> dict[str, float]:
    return {"equity": a.equity_geography, "fixed_income": a.fixed_income_geography,
            "cash": a.cash_geography, "other": a.other_geography}[classe]


def _fonds(cfg: Config, rng: np.random.Generator, institutions: list[dict]) -> tuple[list, list, list, list]:
    funds, cellules, par_axe, strategiques = [], [], [], []
    for i, (spec, inst) in enumerate(zip(cfg.institutions, institutions)):
        n = int(rng.integers(spec.fund_count[0], spec.fund_count[1] + 1))
        coeur = list(spec.core_archetypes)
        p = np.array([spec.archetype_affinity[k] for k in coeur])
        choisis = [coeur[int(rng.choice(len(coeur), p=p / p.sum()))]]
        cle_coeur = choisis[0]
        possibles = [k for k, x in spec.archetype_affinity.items() if x > 0 and k not in choisis]
        p = np.array([spec.archetype_affinity[k] for k in possibles])
        choisis += [possibles[j] for j in rng.choice(len(possibles), size=n - 1, replace=False, p=p / p.sum())]
        choisis.sort(key=lambda k: (cfg.archetypes[k].strategic_equity, k))
        for rang, cle in enumerate(choisis, 1):
            a = cfg.archetypes[cle]
            fund_id = f"F{i + 1}{rang:02d}"
            # Allocation effective autour du mandat, puis géographie et style dans chaque classe
            classes = _dirichlet(rng, a.asset_class, a.asset_class_concentration)
            brut = {}
            for classe, w in classes.items():
                geo = _dirichlet(rng, _geo_moyenne(a, classe), a.geography_concentration)
                styles = _dirichlet(rng, a.equity_style, a.style_concentration) if classe == "equity" \
                    else {CLASS_STYLE[classe]: 1.0}
                for g, wg in geo.items():
                    for s, ws in styles.items():
                        brut[(classe, g, s)] = w * wg * ws
            cles = list(brut)
            unites = repartir([brut[k] for k in cles], UNITES_EXPOSITION)
            exposition = {k: u for k, u in zip(cles, unites) if u > 0}
            for (classe, g, s), u in exposition.items():
                cellules.append(dict(fund_id=fund_id, asset_class=classe, geography=g, style=s, weight=u / 10_000))
            for axe, pos in (("asset_class", 0), ("geography", 1), ("style", 2)):
                somme: dict[str, int] = {}
                for k, u in exposition.items():
                    somme[k[pos]] = somme.get(k[pos], 0) + u
                par_axe += [dict(fund_id=fund_id, axis=axe, category=c, weight=u / 10_000) for c, u in somme.items()]
            for classe, w in a.strategic.items():
                strategiques.append(dict(fund_id=fund_id, asset_class=classe, target_weight=w))

            part = {c: sum(u for k, u in exposition.items() if k[0] == c) / UNITES_EXPOSITION for c in classes}
            actions = sum(u for k, u in exposition.items() if k[0] == "equity")
            emergents = sum(u for k, u in exposition.items() if k[0] == "equity" and k[1] == "emerging")
            couvert = bool(rng.random() < a.equity_hedge_probability)
            devises = sum(u for (classe, g, _), u in exposition.items()
                          if g != "canada" and (classe == "other" or (classe == "equity" and not couvert)))
            mer = round(float(rng.uniform(*a.mer_pct)) * inst["fee_level"], 2)
            bas = round(float(rng.uniform(*a.account_fee_pct)) * inst["fee_level"], 2)
            haut = round(max(bas - float(rng.uniform(0.10, 0.20)), 0.05), 2)
            duree = round(float(rng.uniform(*a.duration_years)), 1) if a.duration_years and "fixed_income" in part else None
            top10 = round(float(rng.uniform(*a.top10_weight_pct)), 1)
            if rng.random() < cfg.new_fund_probability and cle != cle_coeur:    # le fonds cœur existe au départ
                lancement = cfg.start_date + dt.timedelta(days=int(rng.integers(cfg.new_fund_window_days[0],
                                                                                cfg.new_fund_window_days[1] + 1)))
            else:
                lancement = cfg.start_date - dt.timedelta(days=int(rng.integers(cfg.old_fund_age_days[0],
                                                                                cfg.old_fund_age_days[1] + 1)))
            funds.append(dict(
                fund_id=fund_id, institution_id=inst["institution_id"], archetype=cle,
                fund_name=f"{a.label} — {inst['name']} (fictif)", currency="CAD", inception_date=ouvrable(lancement),
                risk_profile_hint=indice_risque(part, emergents / actions if actions else 0.0, top10),
                fee_policy=FEE_POLICY, mer_pct=mer, account_fee_low_pct=bas, account_fee_high_pct=haut,
                distribution_frequency=a.distribution, equity_fx_hedged=couvert,
                fx_exposure_pct=round(devises / 10_000, 2), duration_years=duree,
                rate_sensitivity=round(part.get("fixed_income", 0) * duree, 2) if duree is not None else None,
                top10_weight_pct=top10, trading_cost_pct=round(float(rng.uniform(*a.trading_cost_pct)), 2),
                turnover_pct=round(float(rng.uniform(*a.turnover_pct)), 1), eligible_regimes=REGIMES_ELIGIBLES))
    return funds, cellules, par_axe, strategiques


# ------------------------------------------------------------------------------------------------
# Comptes
# ------------------------------------------------------------------------------------------------
def _affecter(cfg: Config, rng: np.random.Generator) -> list[tuple[str, int]]:
    """(régime, rang d'institution) de chaque compte : au plus un compte d'un régime par institution,
    au moins min_per_institution comptes par institution. Rejet du tirage sinon."""
    nb = len(cfg.institutions)
    for _ in range(ESSAIS_MAX):
        comptes, ok = [], True
        for regime in cfg.regimes:
            bas, haut = cfg.account_count[regime]
            for _ in range(int(rng.integers(bas, haut + 1))):
                libres = [i for i in range(nb) if (regime, i) not in comptes]
                aff = np.array([cfg.institutions[i].regime_affinity[regime] for i in libres])
                if not libres or aff.sum() == 0:
                    ok = False
                    break
                comptes.append((regime, libres[int(rng.choice(len(libres), p=aff / aff.sum()))]))
        if ok and all(sum(1 for _, i in comptes if i == k) >= cfg.accounts["min_per_institution"] for k in range(nb)):
            return comptes
    raise ConfigError("accounts.count et regime_affinity : aucune affectation valide des comptes")


def _comptes(cfg: Config, rng: np.random.Generator, institutions: list[dict]) -> list[dict]:
    affectation = _affecter(cfg, rng)
    limite = cfg.end_date - dt.timedelta(days=int(cfg.accounts["last_opening_before_end_months"] * JOURS_PAR_MOIS))
    lignes = []
    for i, inst in enumerate(institutions):
        regimes = [r for r, k in affectation if k == i]
        candidats = [r for r in regimes if r != "CELIAPP"]
        premier = candidats[int(rng.integers(len(candidats)))]
        for r in regimes:
            if r == premier:
                ouverture = inst["opened_at"]
            else:
                base = max(inst["opened_at"], cfg.celiapp_available_from) if r == "CELIAPP" else inst["opened_at"]
                moyenne = cfg.accounts["celiapp_delay_months" if r == "CELIAPP" else "account_delay_months"]
                ouverture = ouvrable(base + dt.timedelta(days=_delai(rng, moyenne, (limite - base).days)))
            lignes.append(dict(institution_id=inst["institution_id"], regime=r, opened_at=ouverture, _rang=i))
    lignes.sort(key=lambda c: (c["opened_at"], cfg.regimes.index(c["regime"]), c["_rang"]))
    compteur: dict[str, int] = {}
    for n, c in enumerate(lignes, 1):
        compteur[c["regime"]] = compteur.get(c["regime"], 0) + 1
        c.update(account_id=f"C{n:02d}", account_alias=f"{c['regime']}-{compteur[c['regime']]}", closed_at=None)
        del c["_rang"]
    for inst in institutions:      # l'institution s'ouvre avec son premier compte
        inst["opened_at"] = min(c["opened_at"] for c in lignes if c["institution_id"] == inst["institution_id"])
    return [{k: c[k] for k in ("account_id", "institution_id", "regime", "account_alias", "opened_at", "closed_at")}
            for c in lignes]


# ------------------------------------------------------------------------------------------------
# Allocations cibles
# ------------------------------------------------------------------------------------------------
def _arrondir_poids(poids: dict[str, float], pas: int) -> dict[str, int]:
    """Poids humains : multiples de « pas » %, les poids sous un demi-pas abandonnés, total 100."""
    gardes = {k: w for k, w in poids.items() if w * 100 >= pas / 2} or {max(poids, key=lambda k: poids[k]): 1.0}
    cles = list(gardes)
    return {k: u * pas for k, u in zip(cles, repartir([gardes[k] for k in cles], 100 // pas, minimum=1))}


def incliner(preferences: np.ndarray, actions: np.ndarray, cible: float) -> np.ndarray:
    """Inclinaison exponentielle : w ∝ préférences × exp(λ × part en actions), λ tel que Σ w × actions
    = cible. C'est l'écart minimal aux préférences (entropie relative) qui atteint la cible. Cible hors
    de la gamme : λ borné, l'allocation reste à l'extrême atteignable."""
    def poids(lam: float) -> np.ndarray:
        x = np.log(preferences) + lam * actions
        w = np.exp(x - x.max())
        return w / w.sum()

    bas, haut = -60.0, 60.0
    if float(poids(bas) @ actions) >= cible:
        return poids(bas)
    if float(poids(haut) @ actions) <= cible:
        return poids(haut)
    for _ in range(100):                 # bissection : Σ w × actions croît avec λ
        milieu = (bas + haut) / 2
        if float(poids(milieu) @ actions) < cible:
            bas = milieu
        else:
            haut = milieu
    return poids((bas + haut) / 2)


def _politiques(cfg: Config, rng: np.random.Generator, institutions: list[dict], accounts: list[dict],
                funds: list[dict], par_axe: list[dict]) -> list[dict]:
    p = cfg.policy
    actions = {f["fund_id"]: 0.0 for f in funds}
    for l in par_axe:
        if l["axis"] == "asset_class" and l["category"] == "equity":
            actions[l["fund_id"]] = l["weight"] / 100
    lignes, politique = [], {}
    for inst in institutions:
        eligibles = [f["fund_id"] for f in funds
                     if f["institution_id"] == inst["institution_id"] and f["inception_date"] <= inst["opened_at"]]
        if not eligibles:
            raise ConfigError(f"{inst['name']} : aucun fonds lancé à l'ouverture ({inst['opened_at']})")
        preferences = rng.dirichlet(np.full(len(eligibles), p["preference_concentration"]))
        tirage = incliner(preferences, np.array([actions[f] for f in eligibles]), inst["risk_appetite"])
        cible = _arrondir_poids({f: float(w) for f, w in zip(eligibles, tirage)}, p["rounding_step"])
        politique[inst["institution_id"]] = cible
        lignes += [dict(effective_date=inst["opened_at"], level="institution", institution_id=inst["institution_id"],
                        account_id=None, fund_id=f, target_weight=float(w)) for f, w in cible.items()]
    bas, haut = (int(x) for x in p["account_funds"])
    for c in accounts:
        cible = politique[c["institution_id"]]
        fonds = list(cible)
        k = int(rng.integers(min(bas, len(fonds)), min(haut, len(fonds)) + 1))
        poids = np.array([cible[f] for f in fonds], dtype=float)
        choisis = [fonds[j] for j in sorted(rng.choice(len(fonds), size=k, replace=False, p=poids / poids.sum()))]
        bruit = {f: cible[f] * math.exp(rng.normal(0, p["account_weight_sigma"])) for f in choisis}
        total = sum(bruit.values())
        compte = _arrondir_poids({f: w / total for f, w in bruit.items()}, p["rounding_step"])
        lignes += [dict(effective_date=c["opened_at"], level="account", institution_id=c["institution_id"],
                        account_id=c["account_id"], fund_id=f, target_weight=float(w)) for f, w in compte.items()]
    return lignes


def construire_univers(cfg: Config, seed: int | None = None) -> Universe:
    r = generateurs(flux(cfg.seed if seed is None else seed)["universe"], ("institutions", "funds", "accounts", "policy"))
    institutions = _institutions(cfg, r["institutions"])
    accounts = _comptes(cfg, r["accounts"], institutions)
    funds, cellules, par_axe, strategiques = _fonds(cfg, r["funds"], institutions)
    cibles = _politiques(cfg, r["policy"], institutions, accounts, funds, par_axe)
    # Poids d'épargne au dix-millième, somme exacte
    for inst, u in zip(institutions, repartir([i["savings_weight_prior"] for i in institutions], 10_000)):
        inst["savings_weight_prior"] = u / 10_000
    return Universe(institutions, accounts, funds, cellules, par_axe, strategiques, cibles)
