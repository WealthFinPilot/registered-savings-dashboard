"""Moteur C — comportement de l'épargnant : capacité d'épargne latente, PAC, ponctuels, retraits,
révisions de cible, journal d'événements, droits de cotisation.

Les décisions précèdent les montants : une capacité d'épargne latente ne change qu'à des événements
datés (phase d'épargne, ouverture de compte, ajustement, revue) ; entre deux décisions, le PAC de chaque
compte reste constant. Les ponctuels, retraits, mois atypiques et pauses suivent des processus de
Poisson ; chacun naît d'un événement du journal. Les droits de cotisation (fiscal.Droits) bornent chaque
apport ; un excédent est réorienté vers un COMP ouvert, sinon abandonné, et l'événement est journalisé.

Chronologie : la simulation avance mois par mois et, dans un mois, jour par jour (décisions avant
versements). Le marché n'est lu que par le repli du repère actions mondiales arrêté au jour ouvrable
précédant la décision : aucune décision ne connaît un prix de son jour ou d'après. Les tirages viennent
du flux « behaviour » de la graine, en sous-flux nommés, consommés dans l'ordre chronologique.
"""
import calendar
import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import Config, ConfigError
from .fiscal import Droits, Personnage, Plafonds
from .market import jours_ouvrables
from .rng import flux, generateurs
from .universe import _arrondir_poids, incliner, ouvrable

SOUS_FLUX = ("persona", "capacite", "comptes", "atypiques", "ponctuels", "retraits", "cibles")
REPERE_SIGNAL = "R-ACT-MONDE"
PAS_CIBLE = 5
# Ordre des opérations d'un même jour : décisions, puis versements et retraits
ORDRE = {"ouverture": 0, "phase": 1, "retour": 2, "prudence": 3, "revue": 4, "ajustement": 5, "pac": 6,
         "ponctuel": 7, "impose": 7, "remboursement": 8, "retrait": 9}
LIBELLES_PHASE = {"hausse_revenus": "hausse de revenus", "pression_budgetaire": "pression budgétaire",
                  "nouveau_projet": "nouveau projet (achat d'une première habitation)",
                  "reprise_epargne": "reprise de l'épargne"}
LIBELLES_PONCTUEL = {"prime": "prime versée", "argent_disponible": "argent disponible versé", "cadeau": "cadeau versé",
                     "remboursement_impot": "remboursement d'impôt versé"}


@dataclass
class Comportement:
    events: list[dict]
    external_movements: list[dict]
    contribution_room: list[dict]
    persona: list[dict]
    tax_limits: list[dict]
    allocation_targets_history: list[dict]

    def tables(self) -> dict[str, list[dict]]:
        return dict(self.__dict__)


def arrondir(x: float, pas: int) -> float:
    return float(math.floor(x / pas + 0.5) * pas)


def _categorie(rng: np.random.Generator, poids: dict) -> Any:
    cles = list(poids)
    p = np.array([poids[k] for k in cles], dtype=float)
    return cles[int(rng.choice(len(cles), p=p / p.sum()))]


def dans_mois(annee: int, mois: int, jour: int) -> dt.date:
    """Jour ouvrable du mois : samedi ou dimanche reporté au lundi, ou ramené au vendredi si le lundi
    tombe le mois suivant ; un jour au-delà de la fin du mois devient le dernier jour ouvrable."""
    dernier = calendar.monthrange(annee, mois)[1]
    d = ouvrable(dt.date(annee, mois, min(jour, dernier)))
    if d.month != mois:
        d = dt.date(annee, mois, dernier)
        while d.weekday() >= 5:
            d -= dt.timedelta(days=1)
    return d


def _jour(rng: np.random.Generator, annee: int, mois: int) -> dt.date:
    return dans_mois(annee, mois, int(rng.integers(1, calendar.monthrange(annee, mois)[1] + 1)))


def _personnage(cfg: Config, rng: np.random.Generator) -> tuple[Personnage, float]:
    p = cfg.persona
    premiere = int(rng.integers(p["celi_first_year"][0], p["celi_first_year"][1] + 1))
    revenu = float(np.exp(rng.normal(math.log(p["earned_income"][0]), p["earned_income"][1])))
    revenus = {}
    for a in range(cfg.start_date.year - 1, cfg.end_date.year + 1):
        revenus[a] = round(revenu, -2)
        revenu *= 1 + rng.normal(*p["income_growth_pct"]) / 100
    inutilises = round(float(rng.uniform(*p["reer_opening_unused"])), 2)
    taux = float(rng.uniform(*p["marginal_tax_rate"]))
    return Personnage(premiere, revenus, inutilises), taux


@dataclass
class _Etat:
    """État courant de l'épargnant ; les montants sont en CAD."""
    capacite: float
    capacite_depart: float
    poids_log: dict[str, float] = field(default_factory=dict)
    avec_pac: dict[str, bool] = field(default_factory=dict)
    montant: dict[str, float] = field(default_factory=dict)
    pas: dict[str, int] = field(default_factory=dict)
    niveau: dict[str, int] = field(default_factory=dict)         # événement qui a fixé le PAC du compte
    jour_pac: dict[str, int] = field(default_factory=dict)
    pause: dict[str, int] = field(default_factory=dict)          # indice du premier mois après la pause
    cible: dict[str, dict[str, int]] = field(default_factory=dict)
    cible_date: dict[str, dt.date] = field(default_factory=dict)
    avant_prudence: dict[str, dict[str, int]] = field(default_factory=dict)
    retour: dict[str, int] = field(default_factory=dict)         # compte en prudence -> mois du retour
    apports_nets: dict[str, float] = field(default_factory=dict)
    projet: bool = False
    hors_droits: dict[str, int] = field(default_factory=dict)    # régime -> année de droits sans contrôle


def simuler_comportement(cfg: Config, tables: dict[str, list[dict]], plafonds: Plafonds,
                         seed: int | None = None) -> Comportement:
    if cfg.behaviour is None or cfg.persona is None:
        raise ConfigError("behaviour, persona : sections absentes de la configuration")
    b = cfg.behaviour
    r = generateurs(flux(cfg.seed if seed is None else seed)["behaviour"], SOUS_FLUX)
    perso, taux_marginal = _personnage(cfg, r["persona"])

    comptes = {c["account_id"]: c for c in tables["accounts"]}
    insts = {i["institution_id"]: i for i in tables["institutions"]}
    specs = {s.name: s for s in cfg.institutions}
    fonds = {f["fund_id"]: f for f in tables["funds"]}
    actions = {f: 0.0 for f in fonds}
    for l in tables["fund_exposures_by_axis"]:
        if l["axis"] == "asset_class" and l["category"] == "equity":
            actions[l["fund_id"]] = l["weight"] / 100
    celiapp = [c["opened_at"].year for c in comptes.values() if c["regime"] == "CELIAPP"]
    droits = Droits(plafonds, perso, plafonds.annee_reer(cfg.start_date), min(celiapp) if celiapp else None)

    # Signal de marché : repli du repère actions mondiales, connu à la clôture de chaque jour ouvrable
    jours = jours_ouvrables(cfg.start_date, cfg.end_date)
    indice = {l["date"]: l["index_total_return"] for l in tables["benchmarks_daily"] if l["benchmark_id"] == REPERE_SIGNAL}
    if len(indice) != len(jours):
        raise ConfigError(f"behaviour : repère {REPERE_SIGNAL} incomplet ({len(indice)} jours pour {len(jours)})")
    repli, sommet = {}, 0.0
    for j in jours:
        sommet = max(sommet, indice[j])
        repli[j] = indice[j] / sommet - 1

    def repli_veille(jour: dt.date) -> float | None:
        """Repli arrêté au dernier jour ouvrable strictement avant « jour »."""
        avant = [j for j in jours if j < jour]
        return repli[avant[-1]] if avant else None

    capacite = float(np.exp(r["capacite"].normal(math.log(b["monthly_capacity"][0]), b["monthly_capacity"][1])))
    e = _Etat(capacite=capacite, capacite_depart=capacite)
    for l in tables["allocation_targets_history"]:
        if l["level"] == "account":
            e.cible.setdefault(l["account_id"], {})[l["fund_id"]] = int(round(l["target_weight"]))
            e.cible_date[l["account_id"]] = l["effective_date"]

    # Ponctuels imposés (cas d'usage) : contrôlés d'avance, ils ne consomment aucun tirage
    par_alias = {c["account_alias"]: a for a, c in comptes.items()}
    for x in b.get("scripted_lumps", ()):
        a = par_alias.get(x["account"])
        if a is None:
            raise ConfigError(f"behaviour.scripted_lumps : compte {x['account']} inconnu ({sorted(par_alias)})")
        c = comptes[a]
        if not (cfg.start_date <= x["date"] <= cfg.end_date) or x["date"].weekday() >= 5                 or x["date"] < c["opened_at"] or (c["closed_at"] is not None and x["date"] >= c["closed_at"]):
            raise ConfigError(f"behaviour.scripted_lumps : {x['date']} n'est pas un jour ouvrable où {x['account']} est ouvert")

    evenements: list[dict] = []
    mouvements: list[dict] = []
    cibles: list[dict] = []

    def evenement(jour: dt.date, genre: str, description: str, impact: str, compte: str | None = None,
                  institution: str | None = None) -> int:
        if compte is not None:
            institution = comptes[compte]["institution_id"]
        evenements.append(dict(_n=len(evenements), date=jour, event_type=genre, institution_id=institution,
                               account_id=compte, description=description, scenario_impact=impact))
        return len(evenements) - 1

    def ouverts(jour: dt.date) -> list[str]:
        """Comptes ouverts à cette date et dont l'ouverture est déjà traitée (deux ouvertures le même jour)."""
        return [a for a, c in comptes.items() if a in e.avec_pac and c["opened_at"] <= jour
                and (c["closed_at"] is None or c["closed_at"] > jour)]

    def pac_total() -> float:
        return sum(e.montant.values())

    # --------------------------------------------------------------------------------------------
    # Décisions sur les PAC
    # --------------------------------------------------------------------------------------------
    def affinite(a: str) -> float:
        return max(specs[insts[comptes[a]["institution_id"]]["name"]].regime_affinity[comptes[a]["regime"]], 1e-6)

    def poids(groupe: list[str]) -> dict[str, float]:
        """Poids d'épargne des comptes d'un groupe : le poids a priori de chaque institution (J1) se partage
        entre ses comptes du groupe au prorata de l'affinité du régime, puis le bruit latent du compte."""
        par_inst: dict[str, float] = {}
        for a in groupe:
            par_inst[comptes[a]["institution_id"]] = par_inst.get(comptes[a]["institution_id"], 0.0) + affinite(a)
        return {a: insts[comptes[a]["institution_id"]]["savings_weight_prior"] * affinite(a)
                / par_inst[comptes[a]["institution_id"]] * math.exp(e.poids_log[a]) for a in groupe}

    def reviser(jour: dt.date, ev: int) -> None:
        """Révision de tous les PAC : capacité bruitée, ventilée selon les poids latents des comptes."""
        g = r["capacite"]
        actifs = [a for a in ouverts(jour) if e.avec_pac[a]]
        for a in actifs:
            e.poids_log[a] += g.normal(0, b["account_weight_drift_sigma"])
        if not actifs:
            return
        total = e.capacite * math.exp(g.normal(0, b["revision_noise_sigma"]))
        w = {a: x * (b["project_celiapp_boost"] if e.projet and comptes[a]["regime"] == "CELIAPP" else 1)
             for a, x in poids(actifs).items()}
        s = sum(w.values())
        pas = int(_categorie(g, b["pac_rounding"]))
        pas_possibles = sorted(b["pac_rounding"])
        for a in actifs:
            brut = total * w[a] / s
            # Pas d'arrondi tiré, ramené au plus grand pas possible sous 15 % du montant : 50 $ ne s'arrondit
            # pas à la cinquantaine
            p = max([x for x in pas_possibles if x <= max(pas_possibles[0], min(pas, 0.15 * brut))])
            e.montant[a] = max(b["min_pac"], arrondir(brut, p))
            e.pas[a], e.niveau[a] = p, ev

    def ajuster(a: str, ev: int) -> bool:
        """Ajustement décidé : il change le montant, d'au moins un pas d'arrondi dans le sens du tirage."""
        ancien = e.montant[a]
        z = r["capacite"].normal(0, b["adjustment_sigma"])
        nouveau = arrondir(ancien * math.exp(z), e.pas[a])
        if nouveau == ancien:
            nouveau = ancien + (e.pas[a] if z >= 0 else -e.pas[a])
        e.montant[a] = max(b["min_pac"], nouveau)
        if e.montant[a] != ancien:
            e.niveau[a] = ev
            return True
        return False

    def ouvrir(a: str) -> None:
        c = comptes[a]
        inst = insts[c["institution_id"]]
        g = r["comptes"]
        e.poids_log[a] = g.normal(0, b["account_weight_sigma"])      # bruit latent du compte ; voir poids()
        premier = not e.avec_pac
        e.avec_pac[a] = premier or bool(g.random() >= b["no_pac_probability"])
        e.montant[a], e.pas[a] = 0.0, 5
        e.apports_nets[a] = 0.0
        avant = pac_total()
        ev = evenement(c["opened_at"], "ouverture_compte", f"ouverture du {c['account_alias']} chez {inst['name']}",
                       "", compte=a)
        reviser(c["opened_at"], ev)
        evenements[ev]["scenario_impact"] = (f"PAC total {avant:.0f} → {pac_total():.0f} $"
                                             + ("" if e.avec_pac[a] else " ; compte sans PAC (ponctuels seulement)"))

    # --------------------------------------------------------------------------------------------
    # Apports : droits de cotisation et réorientation
    # --------------------------------------------------------------------------------------------
    def verser(jour: dt.date, a: str, montant: float, genre: str, ev: int) -> None:
        regime = comptes[a]["regime"]
        if regime in e.hors_droits and e.hors_droits[regime] == droits.annee(regime, jour):
            # Après un ponctuel imposé : l'épargnant ne voit pas son excédent, ses apports continuent
            droits.cotiser(regime, jour, montant, hors_droits=True)
            mouvements.append(dict(date=jour, account_id=a, movement_type=genre, amount_cad=round(montant, 2), event_id=ev))
            e.apports_nets[a] += montant
            return
        brut = droits.disponible(regime, jour)
        dispo = brut if math.isinf(brut) else max(0.0, math.floor(brut * 100) / 100)
        part = min(montant, dispo)
        if part < montant and part < b["min_pac"]:
            part = 0.0                          # reliquat de droits sous le versement minimal : tout est réorienté
        reste = round(montant - part, 2)
        if part > 0:
            droits.cotiser(regime, jour, part)
            mouvements.append(dict(date=jour, account_id=a, movement_type=genre, amount_cad=round(part, 2), event_id=ev))
            e.apports_nets[a] += part
        if reste > 0:
            comp = [x for x in ouverts(jour) if comptes[x]["regime"] == "COMP"]
            comp.sort(key=lambda x: comptes[x]["institution_id"] != comptes[a]["institution_id"])
            evr = evenement(jour, "plafond_atteint", f"droits {regime} épuisés sur le {comptes[a]['account_alias']}",
                            f"{reste:.2f} $ " + (f"réorientés vers le {comptes[comp[0]]['account_alias']}" if comp
                                                 else "non versés"), compte=a)
            if comp:
                mouvements.append(dict(date=jour, account_id=comp[0], movement_type=genre, amount_cad=reste, event_id=evr))
                e.apports_nets[comp[0]] += reste

    # --------------------------------------------------------------------------------------------
    # Cibles des comptes
    # --------------------------------------------------------------------------------------------
    def part_actions(cible: dict[str, int]) -> float:
        return sum(w / 100 * actions[f] for f, w in cible.items())

    def poser_cible(jour: dt.date, a: str, cible: dict[str, int]) -> None:
        e.cible[a], e.cible_date[a] = dict(cible), jour
        cibles.extend(dict(effective_date=jour, level="account", institution_id=comptes[a]["institution_id"],
                           account_id=a, fund_id=f, target_weight=float(w)) for f, w in sorted(cible.items()))

    def texte_cible(cible: dict[str, int]) -> str:
        return ", ".join(f"{f} {w} %" for f, w in sorted(cible.items()))

    def revue(jour: dt.date, a: str) -> None:
        g = r["cibles"]
        change, pac = g.random() < b["review_change_probability"], g.random() < b["review_pac_probability"]
        bruit = {f: w * math.exp(g.normal(0, b["review_sigma"])) for f, w in e.cible[a].items()}
        nouveaux = [f for f, x in fonds.items() if x["institution_id"] == comptes[a]["institution_id"]
                    and e.cible_date[a] < x["inception_date"] <= jour and f not in e.cible[a]]
        adopte = nouveaux[int(g.integers(len(nouveaux)))] if nouveaux and g.random() < b["new_fund_adoption_probability"] else None
        if a in e.retour or e.cible_date[a] == jour:
            return                                      # en prudence, ou cible déjà changée ce jour
        if adopte:
            bruit[adopte] = 0.15 * sum(bruit.values())
        cible = _arrondir_poids({f: w / sum(bruit.values()) for f, w in bruit.items()}, PAS_CIBLE) if change or adopte else e.cible[a]
        ancien_pac = e.montant.get(a, 0.0)
        nouvelle = cible != e.cible[a]
        ev = evenement(jour, "ajout_fonds" if adopte and adopte in cible else "revue_annuelle",
                       f"revue du {comptes[a]['account_alias']}" + (f", ajout de {adopte}" if adopte and adopte in cible else ""),
                       "", compte=a)
        impacts = []
        if nouvelle:
            impacts.append(f"cible {texte_cible(e.cible[a])} → {texte_cible(cible)}")
            poser_cible(jour, a, cible)
        if pac and e.avec_pac[a] and ancien_pac > 0 and ajuster(a, ev):
            impacts.append(f"PAC {ancien_pac:.0f} → {e.montant[a]:.0f} $")
        if impacts:
            evenements[ev]["scenario_impact"] = " ; ".join(impacts)
        else:
            evenements.pop()                            # inertie : la revue ne change rien, rien à journaliser

    def prudence(jour: dt.date, i: int) -> None:
        g = r["cibles"]
        u, duree = g.random(), int(g.geometric(1 / b["prudence_duration_months"]))
        signal = repli_veille(jour)
        if signal is None or signal * 100 > b["prudence_drawdown_pct"] or e.retour or u >= b["prudence_monthly_probability"]:
            return
        candidats = [a for a in ouverts(jour) if e.cible_date.get(a) != jour and part_actions(e.cible[a]) > 0.5]
        if not candidats:
            return
        a = max(candidats, key=lambda x: (part_actions(e.cible[x]), x))
        gamme = [f for f, x in fonds.items() if x["institution_id"] == comptes[a]["institution_id"] and x["inception_date"] <= jour]
        pref = np.array([e.cible[a].get(f, 2) for f in gamme], dtype=float)
        visee = part_actions(e.cible[a]) - b["prudence_equity_shift"]
        tirage = incliner(pref / pref.sum(), np.array([actions[f] for f in gamme]), visee)
        cible = _arrondir_poids({f: float(w) for f, w in zip(gamme, tirage)}, PAS_CIBLE)
        if part_actions(e.cible[a]) - part_actions(cible) < b["prudence_min_equity_drop"]:
            return                                  # la gamme du compte ne permet pas de se protéger
        evenement(jour, "prudence_marche", f"repli de {-signal:.0%} du repère actions mondiales : le "
                  f"{comptes[a]['account_alias']} passe à une cible plus prudente",
                  f"cible {texte_cible(e.cible[a])} → {texte_cible(cible)} ; actions "
                  f"{part_actions(e.cible[a]):.0%} → {part_actions(cible):.0%}", compte=a)
        e.avant_prudence[a] = dict(e.cible[a])
        poser_cible(jour, a, cible)
        e.retour[a] = i + duree

    def retour(jour: dt.date, a: str) -> None:
        cible = {f: w for f, w in e.avant_prudence.pop(a).items()}
        del e.retour[a]
        if e.cible_date[a] == jour or cible == e.cible[a]:
            return
        evenement(jour, "retour_cible", f"le {comptes[a]['account_alias']} revient à sa cible d'avant la baisse",
                  f"cible {texte_cible(e.cible[a])} → {texte_cible(cible)}", compte=a)
        poser_cible(jour, a, cible)

    # --------------------------------------------------------------------------------------------
    # Phases, ponctuels, retraits
    # --------------------------------------------------------------------------------------------
    def phase(jour: dt.date) -> None:
        g = r["capacite"]
        # Rappel budgétaire : loin au-dessus du niveau de départ, une phase qui baisse devient plus probable
        rapport = e.capacite / e.capacite_depart
        poids = {k: w * rapport ** (b["phase_reversion"] * (1 if sum(b["phase_multiplier"][k]) < 2 else -1))
                 for k, w in b["phase_weights"].items()}
        genre = _categorie(g, poids)
        mult = float(g.uniform(*b["phase_multiplier"][genre]))
        avant = pac_total()
        e.capacite *= mult
        e.projet = genre == "nouveau_projet" or (e.projet and genre != "pression_budgetaire")
        if genre == "hausse_revenus":           # le revenu gagné suit : droits REER des années suivantes
            for y in perso.revenus:
                if y >= jour.year:
                    fraction = (13 - jour.month) / 12 if y == jour.year else 1.0
                    perso.revenus[y] = round(perso.revenus[y] * (1 + (mult - 1) * fraction), -2)
        ev = evenement(jour, "phase_epargne", LIBELLES_PHASE[genre], "")
        reviser(jour, ev)
        evenements[ev]["scenario_impact"] = f"capacité ×{mult:.2f} ; PAC total {avant:.0f} → {pac_total():.0f} $"

    def ponctuel(jour: dt.date, genre: str) -> None:
        gp = r["ponctuels"]
        actifs = ouverts(jour)
        if genre == "remboursement_impot":
            montant = round(droits.cotisations.get(("REER", jour.year - 1), 0.0) * taux_marginal, 2)
            if montant < b["lump_bounds_cad"][0] or not actifs:
                return
        else:
            mediane, sigma = b["lump_capacity_multiple"][genre]
            lo = max(b["lump_bounds_capacity_multiple"][0] * e.capacite, b["lump_bounds_cad"][0])
            hi = min(b["lump_bounds_capacity_multiple"][1] * e.capacite, b["lump_bounds_cad"][1])
            pas = int(_categorie(gp, b["lump_rounding"]))
            for _ in range(1000):               # loi tronquée par rejet, jamais écrêtée
                montant = arrondir(e.capacite * float(np.exp(gp.normal(math.log(mediane), sigma))), pas)
                if lo <= montant <= hi:
                    break
            else:
                raise ConfigError("behaviour.lump_bounds : aucun montant de ponctuel dans les bornes")
            if not actifs:
                return
        wp = poids(actifs)
        w = np.array([wp[a]
                      * (b["reer_season_boost"] if comptes[a]["regime"] == "REER" and jour.month <= 2 else 1)
                      * (b["celi_january_boost"] if comptes[a]["regime"] == "CELI" and jour.month == 1 else 1)
                      for a in actifs])
        a = actifs[int(gp.choice(len(actifs), p=w / w.sum()))]
        ev = evenement(jour, genre, f"{LIBELLES_PONCTUEL[genre]} au {comptes[a]['account_alias']}",
                       f"+{montant:.2f} $", compte=a)
        verser(jour, a, montant, "PONCTUEL", ev)

    def impose(jour: dt.date, k: int) -> None:
        x = b["scripted_lumps"][k]
        a = par_alias[x["account"]]
        regime = comptes[a]["regime"]
        avant = droits.disponible(regime, jour)
        if regime != "COMP":
            e.hors_droits[regime] = droits.annee(regime, jour)
        ev = evenement(jour, "ponctuel_impose", f"ponctuel imposé au {x['account']} : {x['reason']}",
                       f"+{x['amount_cad']:.2f} $" + ("" if regime == "COMP" else f" ; droits {regime} disponibles avant : {avant:.2f} $"),
                       compte=a)
        verser(jour, a, x["amount_cad"], "PONCTUEL", ev)

    def retrait(jour: dt.date, multiple: float, pas: int, u: float) -> None:
        besoin = arrondir(e.capacite * multiple, pas)
        eligibles = [a for a in ouverts(jour) if comptes[a]["regime"] in ("CELI", "COMP")
                     and b["withdrawal_max_share"] * e.apports_nets[a] >= b["withdrawal_min_cad"]]
        if not eligibles:
            evenement(jour, "depense_imprevue", "dépense imprévue", f"{besoin:.0f} $ couverts hors du patrimoine suivi")
            return
        poids = np.cumsum([e.apports_nets[a] for a in eligibles])
        a = eligibles[min(int(np.searchsorted(poids / poids[-1], u, side="right")), len(eligibles) - 1)]
        # Au plus withdrawal_max_share des apports nets : sans grand livre, la valeur du compte est inconnue
        plafond = math.floor(b["withdrawal_max_share"] * e.apports_nets[a] / pas) * pas
        montant = max(b["withdrawal_min_cad"], min(besoin, plafond))
        ev = evenement(jour, "depense_imprevue", f"dépense imprévue, retrait du {comptes[a]['account_alias']}",
                       f"−{montant:.2f} $" + ("" if montant == besoin else f" (besoin {besoin:.0f} $, retrait partiel)"),
                       compte=a)
        droits.retirer(comptes[a]["regime"], jour, montant)
        mouvements.append(dict(date=jour, account_id=a, movement_type="RETRAIT", amount_cad=-montant, event_id=ev))
        e.apports_nets[a] -= montant

    # --------------------------------------------------------------------------------------------
    # Calendrier : phases tirées d'avance (elles ne dépendent pas du marché), revues annuelles
    # --------------------------------------------------------------------------------------------
    mois = []
    a_, m_ = cfg.start_date.year, cfg.start_date.month
    while (a_, m_) <= (cfg.end_date.year, cfg.end_date.month):
        mois.append((a_, m_))
        a_, m_ = (a_ + 1, 1) if m_ == 12 else (a_, m_ + 1)
    g = r["capacite"]
    nb_phases = int(g.integers(b["phase_count"][0], b["phase_count"][1] + 1))
    bas, haut = b["phase_window_months"][0], len(mois) - b["phase_window_months"][1]
    phases: list[int] = []
    for _ in range(1000):
        tirage = sorted(int(x) for x in g.choice(np.arange(bas, haut), size=nb_phases, replace=False))
        if all(y - x >= b["phase_min_gap_months"] for x, y in zip(tirage, tirage[1:])):
            phases = tirage
            break
    else:
        raise ConfigError("behaviour.phase_count, phase_min_gap_months : aucun calendrier de phases possible")
    for a in comptes:                           # jour de prélèvement de chaque compte, tiré d'avance
        e.jour_pac[a] = int(r["comptes"].integers(b["pac_day"][0], b["pac_day"][1] + 1))
    mois_revue = np.array(b["review_month_weights"]) / sum(b["review_month_weights"])
    revues: dict[str, dt.date] = {}
    remboursement: tuple[dt.date, bool] | None = None

    for i, (annee, m) in enumerate(mois):
        premier_jour = dans_mois(annee, m, 1)
        items: list[tuple] = []

        def ajouter(jour: dt.date, genre: str, *args) -> None:
            if cfg.start_date <= jour <= cfg.end_date:
                items.append((jour, ORDRE[genre], len(items), genre, args))

        for a, c in comptes.items():
            if (c["opened_at"].year, c["opened_at"].month) == (annee, m):
                ajouter(c["opened_at"], "ouverture", a)
        if i in phases:
            ajouter(_jour(r["capacite"], annee, m), "phase")
        for a, mois_retour in list(e.retour.items()):
            if mois_retour == i:
                ajouter(premier_jour, "retour", a)
        ajouter(premier_jour, "prudence", i)
        if m == 1 or i == 0:                    # revues de l'année : une date par compte, tirée en janvier
            gc = r["cibles"]
            for a in comptes:
                mm = int(gc.choice(12, p=mois_revue)) + 1
                revues[a] = _jour(gc, annee, mm)
        for a, jour in revues.items():
            if (jour.year, jour.month) == (annee, m):
                ajouter(jour, "revue", a)
        for _ in range(int(r["capacite"].poisson(b["adjustment_rate_per_year"] / 12))):
            ajouter(_jour(r["capacite"], annee, m), "ajustement", float(r["capacite"].random()))

        # Mois atypique (tous les comptes) et pause (un compte), décidés au premier jour ouvrable
        ga = r["atypiques"]
        atypique = ga.poisson(b["atypical_rate_per_year"] / 12) > 0
        genre_atypique = _categorie(ga, b["atypical_types"])
        facteur = float(ga.uniform(*b["reduction_factor"]))
        report = int(ga.integers(b["report_days"][0], b["report_days"][1] + 1))
        pause = ga.poisson(b["pause_rate_per_year"] / 12) > 0
        duree_pause = int(ga.integers(b["pause_months"][0], b["pause_months"][1] + 1))
        u_pause = float(ga.random())
        ev_atypique = None
        actifs_mois = [a for a in ouverts(premier_jour) if e.montant.get(a, 0) > 0 and e.pause.get(a, 0) <= i]
        if atypique and actifs_mois:
            libelle = {"suspension": "PAC suspendus ce mois-ci (dépense imprévue)",
                       "reduction": f"PAC réduits à {facteur:.0%} ce mois-ci (budget serré)",
                       "report": f"PAC reportés de {report} jours (décalage de paie)"}[genre_atypique]
            effet = {"suspension": "0 $", "reduction": f"environ {pac_total() * facteur:.0f} $",
                     "report": "inchangé, versé plus tard"}[genre_atypique]
            ev_atypique = evenement(premier_jour, "mois_atypique", libelle, f"PAC total du mois {pac_total():.0f} $ → {effet}")
        if pause and actifs_mois:
            a = actifs_mois[int(u_pause * len(actifs_mois))]
            e.pause[a] = i + duree_pause
            evenement(premier_jour, "pause_pac", f"pause du PAC du {comptes[a]['account_alias']} pendant {duree_pause} mois",
                      f"−{e.montant[a]:.0f} $ par mois jusqu'à la reprise", compte=a)

        # PAC du mois : un par compte ouvert à sa date (le montant est lu au jour du versement)
        for a in comptes:
            jour = dans_mois(annee, m, e.jour_pac[a])
            if ev_atypique is not None and genre_atypique == "report":
                jour = dans_mois(annee, m, e.jour_pac[a] + report)
            if jour >= comptes[a]["opened_at"]:
                ajouter(jour, "pac", a)

        # Ponctuels (saisonnalité en tendance) et remboursement d'impôt des cotisations REER
        gp = r["ponctuels"]
        poids_mois = b["lump_month_weights"][m - 1] / (sum(b["lump_month_weights"]) / 12)
        for _ in range(int(gp.poisson(b["lump_rate_per_year"] / 12 * poids_mois))):
            ajouter(_jour(gp, annee, m), "ponctuel", _categorie(gp, b["lump_types"]))
        if m == 1:
            mois_remb = int(gp.integers(b["refund_months"][0], b["refund_months"][1] + 1))
            remboursement = (_jour(gp, annee, mois_remb), bool(gp.random() < b["refund_probability"]))
        if remboursement and remboursement[1] and (remboursement[0].year, remboursement[0].month) == (annee, m):
            ajouter(remboursement[0], "remboursement")

        # Retraits : besoin de liquidités
        gr = r["retraits"]
        for _ in range(int(gr.poisson(b["withdrawal_rate_per_year"] / 12))):
            multiple = float(np.exp(gr.normal(math.log(b["withdrawal_capacity_multiple"][0]),
                                              b["withdrawal_capacity_multiple"][1])))
            ajouter(_jour(gr, annee, m), "retrait", multiple, int(_categorie(gr, b["lump_rounding"])), float(gr.random()))
        for k, x in enumerate(b.get("scripted_lumps", ())):
            if (x["date"].year, x["date"].month) == (annee, m):
                ajouter(x["date"], "impose", k)

        for jour, _, _, genre, args in sorted(items, key=lambda x: x[:3]):
            if genre == "ouverture":
                ouvrir(args[0])
            elif genre == "phase":
                phase(jour)
            elif genre == "retour":
                retour(jour, args[0])
            elif genre == "prudence":
                prudence(jour, args[0])
            elif genre == "revue":
                if comptes[args[0]]["opened_at"] < jour and args[0] in e.cible:
                    revue(jour, args[0])
            elif genre == "ajustement":
                actifs = [a for a in ouverts(jour) if e.montant.get(a, 0) > 0]
                if actifs:
                    a = actifs[int(args[0] * len(actifs))]
                    avant = e.montant[a]
                    ev = evenement(jour, "ajustement_pac", f"ajustement du PAC du {comptes[a]['account_alias']}", "", compte=a)
                    if ajuster(a, ev):
                        evenements[ev]["scenario_impact"] = f"PAC {avant:.0f} → {e.montant[a]:.0f} $"
                    else:
                        evenements.pop()
            elif genre == "pac":
                a = args[0]
                if e.montant.get(a, 0) <= 0 or e.pause.get(a, 0) > i or (ev_atypique is not None and genre_atypique == "suspension"):
                    continue
                montant, ev = e.montant[a], e.niveau[a]
                if ev_atypique is not None and genre_atypique == "reduction":
                    montant, ev = max(b["min_pac"], arrondir(montant * facteur, 5)), ev_atypique
                elif ev_atypique is not None:
                    ev = ev_atypique
                verser(jour, a, montant, "PAC", ev)
            elif genre == "ponctuel":
                ponctuel(jour, args[0])
            elif genre == "remboursement":
                ponctuel(jour, "remboursement_impot")
            elif genre == "impose":
                impose(jour, args[0])
            elif genre == "retrait":
                retrait(jour, *args)

    # --------------------------------------------------------------------------------------------
    # Identifiants stables : ordre chronologique
    # --------------------------------------------------------------------------------------------
    ordre_ev = sorted(range(len(evenements)), key=lambda k: (evenements[k]["date"], k))
    ident = {k: f"E{n:04d}" for n, k in enumerate(ordre_ev, 1)}
    events = []
    for k in ordre_ev:
        l = {c: v for c, v in evenements[k].items() if c != "_n"}
        events.append(dict(event_id=ident[k], **l))
    types = {"PAC": 0, "PONCTUEL": 1, "RETRAIT": 2}
    mouvements.sort(key=lambda l: (l["date"], l["account_id"], types[l["movement_type"]]))
    for n, l in enumerate(mouvements, 1):
        l["movement_id"] = f"M{n:05d}"
        l["event_id"] = ident[l["event_id"]]

    annees = dict(CELI=range(cfg.start_date.year, cfg.end_date.year + 1),
                  REER=range(droits.premiere_annee_reer, plafonds.annee_reer(cfg.end_date) + 1))
    if droits.ouverture_celiapp is not None:
        annees["CELIAPP"] = range(droits.ouverture_celiapp, cfg.end_date.year + 1)
    persona = [dict(year=y, earned_income_cad=perso.revenus.get(y), celi_eligible=y >= perso.celi_first_year,
                    reer_unused_end_cad=perso.reer_unused_start if y == droits.premiere_annee_reer - 1 else None)
               for y in range(min(perso.celi_first_year, cfg.start_date.year - 1), cfg.end_date.year + 1)]
    limites = [dict(regime=l["regime"], rubric=l["rubrique"], year=l["annee"], amount_cad=l["montant"], period_end=None,
                    rule=l["regle"]) for l in plafonds.lignes]
    limites += [dict(regime="REER", rubric="fin_periode", year=a, amount_cad=None, period_end=d, rule="R6")
                for a, d in sorted(plafonds.periodes_reer.items())]
    historique = tables["allocation_targets_history"] + sorted(cibles, key=lambda l: (l["effective_date"], l["account_id"], l["fund_id"]))
    return Comportement(events, mouvements, droits.tableau(annees), persona, limites, historique)
