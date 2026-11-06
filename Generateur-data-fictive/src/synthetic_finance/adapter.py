"""Adaptateur (J6) : tables de finance_ve01, en CSV, depuis les exports des J1 à J5 (contrat de données, § 3).

Ne lit que les CSV écrits dans data/ (ce que la validation contrôle) et n'écrit que dans finance_ve01/ : un fichier
<schéma>.<table>.csv par table que lisent les vues rapport.*, plus distributions.csv (journal des versements, hors
base). Aucune connexion : le chargement se fait hors du paquet (scripts/charger_synthetique.py, à la racine).

Distributions. La VL du J2 est en rendement total ; le rapport lit une VL ex-distribution et des réinvestissements.
Un versement au jour d de taux τ (fraction de la VL avant versement) fait k(d) = k(d−) × (1 − τ), VL ex = VL totale
× k, distribution par part D = VL totale(d) × k(d−) × τ. D'où (VL ex(d) + D) ÷ VL ex(d − 1) = VL totale(d) ÷ VL
totale(d − 1) : le rendement total ne change pas. Seul le partage entre prix et distribution est tiré (flux adapter).

Parts. Le grand livre tient ses parts U dans la VL totale ; les parts publiées valent round(U ÷ k, 3) après chaque
opération, donc parts × VL ex = U × VL totale au millième de part près, sans dérive. Un réinvestissement porte la
différence de parts du jour de versement ; son montant = parts de la veille × D, au cent (ce que relit
rapport.distribution). À une même date : versements d'abord (sur les parts de la veille), puis les ordres du jour.
"""
import csv
import datetime as dt
import math
from pathlib import Path

from .benchmarks import categorie_du_fonds
from .config import Config
from .export import TYPES, lire_csv
from .market import jours_ouvrables
from .rng import flux, generateurs

DOSSIER = "finance_ve01"

# Colonnes de chaque table (types de export.TYPES), dans l'ordre de chargement : une table après celles qu'elle
# référence. Les tables optionnelles du schéma (relevés, transferts, saisies hors export) n'ont pas de fichier. Une
# colonne dont le nom désigne une source de cours réelle porte ici un nom neutre ; le chargeur la renomme.
TABLES: dict[str, list[tuple[str, str]]] = {
    "ref.compte": [("alias", "str"), ("numero", "str"), ("genre", "str"), ("societe", "str"), ("ferme_le", "date")],
    "ref.nature": [("motif", "str"), ("nature", "str"), ("signe", "int"), ("cotisation", "bool")],
    "ref.parametre": [("cle", "str"), ("valeur", "int"), ("note", "str")],
    "ref.reer_avis": [("annee_deduction", "int"), ("maximum_deductible", "dec2"), ("cotisations_inutilisees", "dec2"),
                      ("deduction_20800", "dec2"), ("note", "str")],
    "ref.risque": [("libelle", "str"), ("rang", "int")],
    "ref.geographie": [("libelle", "str"), ("categorie", "str")],
    "ref.style": [("cle", "str"), ("type", "str"), ("style", "str"), ("note", "str")],
    "ref.fonds": [("code_fa", "str"), ("nom_court", "str"), ("profil", "str"), ("ordre_profil", "int"), ("mandat", "str"),
                  ("note", "str")],
    "ref.symbole": [("code_fa", "str"), ("symbole", "str"), ("nom", "str")],
    "ref.repere": [("code_fa", "str"), ("indice", "str"), ("symbole", "str"), ("poids", "dec4"), ("note", "str")],
    "pub.profil": [("code_fa", "str"), ("date_donnees", "date"), ("nom", "str"), ("type_fonds", "str"),
                   ("profil_risque", "str"), ("rfg", "dec2"), ("frais_moins", "dec2"), ("frais_plus", "dec2"),
                   ("fichier", "str")],
    "pub.profil_code": [("code_fonds", "str"), ("code_fa", "str"), ("option_achat", "str")],
    "pub.profil_ligne": [("code_fa", "str"), ("date_donnees", "date"), ("section", "str"), ("ordre", "int"),
                         ("libelle", "str"), ("poids", "dec2"), ("parent", "str")],
    "pub.rapport_annuel": [("code_fa", "str"), ("exercice", "date"), ("nom", "str"), ("revenus", "dec2"),
                           ("dividendes", "dec2"), ("gains_capital", "dec2"), ("remb_capital", "dec2"), ("total", "dec2"),
                           ("rfg", "dec2"), ("rfg_avant", "dec2"), ("rfo", "dec2"), ("rotation", "dec2"),
                           ("fichier", "str")],
    "pub.cours": [("symbole", "str"), ("date_seance", "date"), ("cloture", "dec4"), ("cloture_ajustee", "dec6"),
                  ("devise", "str")],
    "fait.historique": [("compte_alias", "str"), ("date_export", "date"), ("debut", "date"), ("fin", "date")],
    "fait.transaction": [("compte_alias", "str"), ("rang", "int"), ("code_fonds", "str"), ("nom_fonds", "str"),
                         ("date_negociation", "date"), ("date_processus", "date"), ("libelle", "str"), ("nature", "str"),
                         ("signe", "int"), ("montant_brut", "dec2"), ("deductions", "dec2"), ("montant_net", "dec2"),
                         ("prix_part", "dec4"), ("parts_negociees", "dec3"), ("parts_restantes", "dec3")],
    "fait.sommaire": [("compte_alias", "str"), ("date_valorisation", "date"), ("code_fonds", "str"), ("nom_fonds", "str"),
                      ("nb_actions", "dec3"), ("prix_action", "dec4"), ("prix_moyen", "dec4"),
                      ("valeur_comptable", "dec2"), ("valeur_marchande", "dec2")],
}
# Journal des versements de l'adaptateur (hors base) : taux tiré et distribution par part, revenu et gains en capital
DISTRIBUTIONS = [("date", "date"), ("fund_id", "str"), ("rate", "dec10"), ("per_unit_income", "dec10"),
                 ("per_unit_capital_gain", "dec10"), ("nav_total_return", "dec6"), ("nav_ex_before", "dec10")]

LIBELLES = {"PAC": ("Achat — versement programmé", "PAC", 1), "PONCTUEL": ("Achat — versement ponctuel", "ponctuel", 1),
            "RETRAIT": ("Rachat — retrait", "retrait", -1), "FRAIS": ("Frais de gestion", "frais", -1)}
REINVESTISSEMENT = "Distribution réinvestie"
NATURES = [("Achat — versement programmé", "PAC", 1, True), ("Achat — versement ponctuel", "ponctuel", 1, True),
           (REINVESTISSEMENT, "revenu", 1, False), ("Arbitrage — achat depuis *", "interne", 1, False),
           ("Arbitrage — vente vers *", "interne", -1, False), ("Frais de gestion", "frais", -1, False),
           ("Rachat — retrait", "retrait", -1, False)]
RISQUES = ("Faible", "Faible-Moyen", "Moyen", "Moyen-Élevé", "Élevé")
ORDRE_PROFIL = {"Épargne": 1, "Revenu": 2, "Conservateur": 3, "Modéré": 4, "Croissance": 5, "Actions": 6}

# Catégories du contrat de données (§ 2.6) vers les libellés des profils et les tables de correspondance
CLASSE = {"equity": "Actions", "fixed_income": "Titres à revenu fixe", "cash": "Trésorerie et équivalents",
          "other": "Alternatifs"}
SOUS_JACENT = {  # (classe, style) -> libellé d'un sous-jacent de portefeuille, style du rapport (ref.style)
    "broad_market": ("Actions de marché large (fictif)", "Mixte"), "value": ("Actions de valeur (fictif)", "Mixte"),
    "quality": ("Actions de qualité (fictif)", "Mixte"), "growth": ("Actions de croissance (fictif)", "Croissance"),
    "dividend": ("Actions à dividendes (fictif)", "Dividendes"), "fixed_income": ("Obligations (fictif)", "Revenu fixe"),
    "cash": ("Trésorerie (fictif)", "Trésorerie"), "real_assets": ("Actifs réels (fictif)", "Alternatifs")}
PAYS = {"canada": ("Canada", "Canada"), "united_states": ("États-Unis", "États-Unis"),
        "europe": ("Europe", "Autres pays"), "asia_pacific": ("Bassin du Pacifique", "Autres pays"),
        "emerging": ("Marchés émergents", "Autres pays"), "other": ("Autres", "Autres pays")}


class AdaptateurError(ValueError):
    """Export incohérent pour l'adaptateur (ordre sans mouvement ni événement, parts négatives) : rien n'est écrit."""


def _milli(x: float) -> int:
    return round(x * 1000)


def _jour_suivant(j: dt.date) -> dt.date:
    return jours_ouvrables(j + dt.timedelta(days=1), j + dt.timedelta(days=7))[0]


def _fin_de_mois(annee: int, mois: int) -> dt.date:
    debut = dt.date(annee, mois, 1)
    fin = (debut + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    return jours_ouvrables(debut, fin)[-1]


# ------------------------------------------------------------------------------------------------
# Distributions et VL ex
# ------------------------------------------------------------------------------------------------
def distributions(cfg: Config, funds: list[dict], prix: dict[str, list[tuple[dt.date, float]]]) -> list[dict]:
    """Calendrier et taux de chaque versement. Tirages dans l'ordre des fonds, puis des dates : un fonds ajouté
    ne déplace pas les tirages des fonds précédents dans sa propre suite (un sous-flux par fonds)."""
    a = cfg.adapter
    assert a is not None
    racine = flux(cfg.seed)["adapter"]
    alea = generateurs(racine, tuple(f["fund_id"] for f in funds))
    sortie = []
    for f in funds:
        g = alea[f["fund_id"]]
        serie = prix[f["fund_id"]]
        vl = dict(serie)
        jours = [j for j, _ in serie]
        premier, dernier = jours[0], jours[-1]
        tout = f["archetype"] in a["distribute_all"]
        bas, haut = (0.0, 0.0) if tout else a["yield_pct"][f["archetype"]]
        taux_annuel = float(g.uniform(bas, haut)) / 100
        dates: list[dt.date] = []
        for annee in range(premier.year, dernier.year + 1):
            if f["distribution_frequency"] == "monthly" or tout:
                dates += [_fin_de_mois(annee, m) for m in range(1, 13)]
            else:
                fenetre = jours_ouvrables(dt.date(annee, 12, 32 - a["december_window_days"]), dt.date(annee, 12, 31))
                dates.append(fenetre[int(g.integers(len(fenetre)))])
        dates = [d for d in dates if premier < d <= dernier and d in vl]
        k, precedent = 1.0, premier
        for d in dates:
            bruit = math.exp(a["payment_noise_sigma"] * float(g.standard_normal()))
            part_gain = float(g.uniform(*a["capital_gain_share"]))
            if tout:
                gain = vl[d] / vl[precedent] - 1
                t_rev, t_gc = (gain / (1 + gain), 0.0) if gain > 0 else (0.0, 0.0)
            else:
                t_rev = taux_annuel * bruit / (12 if f["distribution_frequency"] == "monthly" else 1)
                t_gc = 0.0
                if d.month == 12:            # gains en capital de l'année civile, au-delà du rendement versé
                    base = max((j for j in jours if j.year < d.year), default=premier)
                    t_gc = part_gain * max(0.0, vl[d] / vl[base] - 1 - taux_annuel)
            precedent = d
            if t_rev + t_gc <= 0:
                continue
            sortie.append(dict(date=d, fund_id=f["fund_id"], rate=t_rev + t_gc, per_unit_income=vl[d] * k * t_rev,
                               per_unit_capital_gain=vl[d] * k * t_gc, nav_total_return=vl[d], nav_ex_before=vl[d] * k))
            k *= 1 - t_rev - t_gc
    return sortie


def facteurs(prix: dict[str, list[tuple[dt.date, float]]], dist: list[dict]) -> dict[str, dict[dt.date, float]]:
    """k(t) de chaque fonds, après le versement du jour : VL ex = VL totale × k."""
    taux: dict[tuple[str, dt.date], float] = {(d["fund_id"], d["date"]): d["rate"] for d in dist}
    sortie = {}
    for f, serie in prix.items():
        k, kf = 1.0, {}
        for j, _ in serie:
            k *= 1 - taux.get((f, j), 0.0)
            kf[j] = k
        sortie[f] = kf
    return sortie


# ------------------------------------------------------------------------------------------------
# Profils, correspondances, repères
# ------------------------------------------------------------------------------------------------
def _parts(expositions: list[dict], fonds: str, sauf_tresorerie: bool = False) -> tuple[dict, dict, dict]:
    classe, geo, style = {}, {}, {}
    for e in expositions:
        if e["fund_id"] != fonds:
            continue
        classe[e["asset_class"]] = classe.get(e["asset_class"], 0) + e["weight"]
        style[(e["asset_class"], e["style"])] = style.get((e["asset_class"], e["style"]), 0) + e["weight"]
        if not (sauf_tresorerie and e["asset_class"] == "cash"):
            geo[e["geography"]] = geo.get(e["geography"], 0) + e["weight"]
    return classe, geo, style


def caracteres(f: dict, cibles: dict[str, float], geo: dict[str, float]) -> tuple[str, str, str]:
    """(profil, mandat, type de fonds) du rapport, dérivés du mandat déclaré et de la géographie hors trésorerie."""
    total = sum(geo.values()) or 1
    g = {k: v / total * 100 for k, v in geo.items()}
    if g.get("canada", 0) >= 65:
        mandat = "Canada"
    elif g.get("emerging", 0) >= 50:
        mandat = "Marchés émergents"
    elif g.get("canada", 0) + g.get("united_states", 0) >= 85:
        mandat = "Amérique du Nord"
    else:
        mandat = "Mondial"
    if f["archetype"] == "monetaire":
        return "Épargne", mandat, "Marché monétaire canadien"
    if len(cibles) == 1:
        seule = next(iter(cibles))
        profil = {"cash": "Épargne", "fixed_income": "Revenu", "equity": "Actions"}.get(seule, "Croissance")
        return profil, mandat, {"fixed_income": "Revenu fixe", "equity": "Actions"}.get(seule, "Équilibré")
    croissance = cibles.get("equity", 0) + cibles.get("other", 0)
    profil = "Conservateur" if croissance < 45 else "Modéré" if croissance < 70 else "Croissance"
    return profil, mandat, "Actifs réels" if cibles.get("other", 0) >= 50 else "Équilibré"


def nom_court(f: dict) -> str:
    return f"{f['fund_id']} – {f['fund_name'].split(' — ')[0]}"


def profils(cfg: Config, t: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """pub.profil, pub.profil_ligne, pub.profil_code, ref.fonds, ref.style, ref.geographie, ref.risque. Expositions
    constantes (J1) : un seul profil par fonds, daté du début de l'horizon, applicable à tous les points."""
    date = cfg.start_date
    cibles: dict[str, dict[str, float]] = {}
    for c in t["fund_strategic_targets"]:
        cibles.setdefault(c["fund_id"], {})[c["asset_class"]] = c["target_weight"]
    entetes, lignes, codes, fonds, styles = [], [], [], [], {}
    for f in t["funds"]:
        fid = f["fund_id"]
        classe, _, style = _parts(t["fund_exposures"], fid)
        _, geo, _ = _parts(t["fund_exposures"], fid, sauf_tresorerie=True)
        profil, mandat, type_fonds = caracteres(f, cibles[fid], geo)
        entetes.append(dict(code_fa=fid, date_donnees=date, nom=f["fund_name"], type_fonds=type_fonds,
                            profil_risque=f["risk_profile_hint"], rfg=f["mer_pct"], frais_moins=f["account_fee_low_pct"],
                            frais_plus=f["account_fee_high_pct"], fichier=f"fictif/{fid}-{date:%Y-%m}.pdf"))
        codes.append(dict(code_fonds=fid, code_fa=fid, option_achat="FA"))
        fonds.append(dict(code_fa=fid, nom_court=nom_court(f), profil=profil, ordre_profil=ORDRE_PROFIL[profil],
                          mandat=mandat, note="fictif"))
        ordre = 0

        def ligne(section: str, libelle: str, poids: float, parent: str | None = None) -> None:
            nonlocal ordre
            ordre += 1
            lignes.append(dict(code_fa=fid, date_donnees=date, section=section, ordre=ordre, libelle=libelle,
                               poids=round(poids, 2), parent=parent))

        if type_fonds.startswith("Marché monétaire"):
            ligne("secteur", CLASSE["cash"], 100)
            styles[("fonds", fid)] = "Trésorerie"
            continue
        if set(cibles[fid]) <= {"equity"}:
            # Fonds d'actions : répartition de l'actif (actions, trésorerie), style du fonds = style dominant des actions
            for k in ("equity", "cash"):
                if classe.get(k, 0) > 0:
                    ligne("actif", CLASSE[k], classe[k])
            par_style: dict[str, float] = {}
            for (k, s), w in style.items():
                if k == "equity":
                    par_style[SOUS_JACENT[s][1]] = par_style.get(SOUS_JACENT[s][1], 0) + w
            styles[("fonds", fid)] = max(sorted(par_style), key=lambda s: par_style[s])
        else:
            # Fonds multiclasses et revenu fixe : répartition actuelle (classes, sous-jacents par style) et cible
            for k in ("equity", "fixed_income", "other", "cash"):
                if classe.get(k, 0) <= 0:
                    continue
                enfants = [(SOUS_JACENT[s], w) for (kk, s), w in sorted(style.items()) if kk == k and w > 0]
                ligne("actuelle", CLASSE[k], sum(round(w, 2) for _, w in enfants))
                for (libelle, st), w in enfants:
                    ligne("actuelle", libelle, w, CLASSE[k])
                    styles[("sous-jacent", libelle)] = st
            for k in ("equity", "fixed_income", "other", "cash"):
                if cibles[fid].get(k, 0) > 0:
                    ligne("cible", CLASSE[k], cibles[fid][k])
        for g, w in sorted(geo.items(), key=lambda x: -x[1]):
            ligne("pays", PAYS[g][0], w / sum(geo.values()) * 100)
    return {
        "pub.profil": entetes, "pub.profil_ligne": lignes, "pub.profil_code": codes, "ref.fonds": fonds,
        "ref.style": [dict(cle=c, type=ty, style=s, note="fictif") for (ty, c), s in sorted(styles.items())],
        "ref.geographie": [dict(libelle=l, categorie=c) for l, c in PAYS.values()],
        "ref.risque": [dict(libelle=l, rang=n) for n, l in enumerate(RISQUES, 1)],
    }


def rapports_annuels(cfg: Config, t: dict[str, list[dict]], dist: list[dict]) -> list[dict]:
    """Distributions par part de chaque exercice (1ᵉʳ octobre au 30 septembre) clos dans l'horizon. Revenu courant :
    part actions en dividendes, le reste en revenus ; gains en capital de décembre à part ; aucun remboursement."""
    actions = {f["fund_id"]: _parts(t["fund_exposures"], f["fund_id"])[0].get("equity", 0) / 100 for f in t["funds"]}
    lignes = []
    for f in t["funds"]:
        fid = f["fund_id"]
        for annee in range(cfg.start_date.year + (cfg.start_date >= dt.date(cfg.start_date.year, 10, 1)),
                           cfg.end_date.year + 1):
            exercice = dt.date(annee, 9, 30)
            if exercice > cfg.end_date:
                continue
            versements = [d for d in dist if d["fund_id"] == fid and dt.date(annee - 1, 10, 1) <= d["date"] <= exercice]
            rev = sum(d["per_unit_income"] for d in versements)
            div, rev = rev * actions[fid], rev * (1 - actions[fid])
            gc = sum(d["per_unit_capital_gain"] for d in versements)
            natures = [round(x, 2) for x in (rev, div, gc, 0.0)]
            lignes.append(dict(code_fa=fid, exercice=exercice, nom=f["fund_name"], revenus=natures[0],
                               dividendes=natures[1], gains_capital=natures[2], remb_capital=natures[3],
                               total=round(sum(natures), 2), rfg=f["mer_pct"], rfg_avant=f["mer_pct"],
                               rfo=f["trading_cost_pct"], rotation=f["turnover_pct"],
                               fichier=f"fictif/{exercice}/{fid}.pdf"))
    return lignes


def cours(cfg: Config, t: dict[str, list[dict]], prix: dict, kf: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """pub.cours (VL ex des fonds, indices des repères), ref.symbole, ref.repere (repère de catégorie, poids 1)."""
    lignes = [dict(symbole=f"SYN-{f}", date_seance=j, cloture=round(v * kf[f][j], 4), cloture_ajustee=None, devise="CAD")
              for f, serie in prix.items() for j, v in serie]
    lignes += [dict(symbole=f"SYN-{b['benchmark_id']}", date_seance=b["date"], cloture=round(b["index_total_return"], 4),
                    cloture_ajustee=b["index_total_return"], devise="CAD") for b in t["benchmarks_daily"]]
    symboles = [dict(code_fa=f["fund_id"], symbole=f"SYN-{f['fund_id']}", nom=f["fund_name"]) for f in t["funds"]]
    noms = {b["benchmark_id"]: b["benchmark_name"] for b in t["benchmarks"]}
    reperes = []
    for f in t["funds"]:
        b = categorie_du_fonds(cfg, f["archetype"])
        reperes.append(dict(code_fa=f["fund_id"], indice=noms[b], symbole=f"SYN-{b}", poids=1.0,
                            note="repère synthétique de catégorie, composition fixe, mêmes facteurs"))
    return lignes, symboles, reperes


# ------------------------------------------------------------------------------------------------
# Comptes, transactions, sommaire, droits
# ------------------------------------------------------------------------------------------------
def transactions(cfg: Config, t: dict[str, list[dict]], dist: list[dict], kf: dict) -> tuple[list[dict], list[dict]]:
    """fait.transaction et fait.sommaire (à l'arrêté). Parts publiées = round(U ÷ k, 3) après chaque opération."""
    alias = {a["account_id"]: a["account_alias"] for a in t["accounts"]}
    fonds = {f["fund_id"]: f for f in t["funds"]}
    mouvement = {m["movement_id"]: m["movement_type"] for m in t["external_movements"]}
    vl_ex = {(f, j): round(v * kf[f][j], 4) for f, serie in _prix(t).items() for j, v in serie}
    ordres = sorted(t["internal_trades"], key=lambda o: (o["date"], o["trade_id"]))
    # Contrepartie d'un arbitrage : le plus gros ordre de sens opposé du même événement, même compte, même jour
    contre: dict[tuple, dict[str, tuple[float, str]]] = {}
    for o in ordres:
        if o["movement_id"] is None:
            if o["event_id"] is None:
                raise AdaptateurError(f"{o['trade_id']} : ordre sans mouvement ni événement")
            x = contre.setdefault((o["date"], o["account_id"], o["event_id"]), {})
            if o["gross_amount_cad"] > x.get(o["side"], (-1.0, ""))[0]:
                x[o["side"]] = (o["gross_amount_cad"], o["fund_id"])
    versements: dict[dt.date, list[dict]] = {}
    for d in dist:
        versements.setdefault(d["date"], []).append(d)
    par_jour: dict[dt.date, list[dict]] = {}
    for o in ordres:
        par_jour.setdefault(o["date"], []).append(o)

    u: dict[tuple[str, str], int] = {}              # parts du grand livre (millièmes, VL totale)
    publiees: dict[tuple[str, str], int] = {}       # parts publiées (millièmes, VL ex)
    cout: dict[tuple[str, str], float] = {}         # valeur comptable (coût moyen)
    lignes: dict[str, list[dict]] = {a: [] for a in alias}

    def ecrire(a: str, f: str, j: dt.date, libelle: str, nature: str, signe: int, montant: float, frais: float,
               avant: int, apres: int) -> None:
        lignes[a].append(dict(compte_alias=alias[a], code_fonds=f, nom_fonds=fonds[f]["fund_name"], date_negociation=j,
                              date_processus=_jour_suivant(j), libelle=libelle, nature=nature, signe=signe,
                              montant_brut=montant, deductions=frais, montant_net=round(montant - frais, 2),
                              prix_part=vl_ex[(f, j)], parts_negociees=abs(apres - avant) / 1000,
                              parts_restantes=apres / 1000))

    for j in sorted(set(versements) | set(par_jour)):
        for d in sorted(versements.get(j, []), key=lambda x: x["fund_id"]):
            f = d["fund_id"]
            for a in sorted(k[0] for k, v in u.items() if k[1] == f and v > 0):
                avant, apres = publiees[(a, f)], round(u[(a, f)] / kf[f][j])
                montant = round(avant / 1000 * (d["per_unit_income"] + d["per_unit_capital_gain"]), 2)
                if montant == 0 and apres == avant:
                    continue
                ecrire(a, f, j, REINVESTISSEMENT, "revenu", 1, montant, 0.0, avant, apres)
                publiees[(a, f)] = apres
                cout[(a, f)] += montant
        for o in par_jour.get(j, []):
            cle, f, a = (o["account_id"], o["fund_id"]), o["fund_id"], o["account_id"]
            signe = 1 if o["side"] == "BUY" else -1
            u[cle] = u.get(cle, 0) + signe * _milli(o["units"])
            if u[cle] < 0:
                raise AdaptateurError(f"{o['trade_id']} : parts négatives")
            avant, apres = publiees.get(cle, 0), round(u[cle] / kf[f][j])
            if o["movement_id"] is not None:
                libelle, nature, _ = LIBELLES[mouvement[o["movement_id"]]]
            else:
                autre = contre[(j, a, o["event_id"])].get("SELL" if signe > 0 else "BUY")
                if autre is None:
                    raise AdaptateurError(f"{o['trade_id']} : arbitrage sans contrepartie")
                libelle = f"Arbitrage — {'achat depuis' if signe > 0 else 'vente vers'} {nom_court(fonds[autre[1]])}"
                nature = "interne"
            ecrire(a, f, j, libelle, nature, signe, o["gross_amount_cad"], o["fee_cad"], avant, apres)
            if signe > 0:
                cout[cle] = cout.get(cle, 0.0) + o["gross_amount_cad"]
            else:
                cout[cle] -= cout[cle] * (avant - apres) / avant if avant else 0.0
            publiees[cle] = apres

    sortie = []
    for a in sorted(lignes):
        sortie += [dict(rang=n, **l) for n, l in enumerate(lignes[a], 1)]
    fin = cfg.end_date
    sommaire = [dict(compte_alias=alias[a], date_valorisation=fin, code_fonds=f, nom_fonds=fonds[f]["fund_name"],
                     nb_actions=p / 1000, prix_action=vl_ex[(f, fin)], prix_moyen=round(cout[(a, f)] / (p / 1000), 4),
                     valeur_comptable=round(cout[(a, f)], 2), valeur_marchande=round(p / 1000 * vl_ex[(f, fin)], 2))
                for (a, f), p in sorted(publiees.items()) if p > 0]
    return sortie, sommaire


def comptes(cfg: Config, t: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """ref.compte, ref.nature, ref.parametre, ref.reer_avis, fait.historique. Avis REER : maximum déductible = droits
    du J3 au début de l'année de déduction ; toute cotisation déduite l'année même, aucune cotisation inutilisée."""
    nom = {i["institution_id"]: i["name"] for i in t["institutions"]}
    reer = sorted((r for r in t["contribution_room"] if r["regime"] == "REER"), key=lambda r: r["year"])
    celi = min(p["year"] for p in t["persona"] if p["celi_eligible"])
    celiapp = [a["opened_at"].year for a in t["accounts"] if a["regime"] == "CELIAPP"]
    parametres = [dict(cle="celi_premiere_annee", valeur=celi, note="fictif")]
    if celiapp:
        parametres.append(dict(cle="celiapp_ouverture", valeur=min(celiapp), note="fictif"))
    return {
        "ref.compte": [dict(alias=a["account_alias"], numero=f"FICT-{a['account_id']}", genre=a["regime"],
                            societe=nom[a["institution_id"]], ferme_le=a["closed_at"]) for a in t["accounts"]],
        "ref.nature": [dict(motif=m, nature=n, signe=s, cotisation=c) for m, n, s, c in NATURES],
        "ref.parametre": parametres,
        "ref.reer_avis": [dict(annee_deduction=r["year"], maximum_deductible=r["room_start_cad"],
                               cotisations_inutilisees=0.0 if n == 0 else None,
                               deduction_20800=r["contributions_cad"] if r["year"] < cfg.end_date.year else None,
                               note="fictif") for n, r in enumerate(reer)],
        "fait.historique": [dict(compte_alias=a["account_alias"], date_export=cfg.end_date, debut=a["opened_at"],
                                 fin=a["closed_at"] or cfg.end_date) for a in t["accounts"]],
    }


# ------------------------------------------------------------------------------------------------
# Entrée
# ------------------------------------------------------------------------------------------------
LUES = ("institutions", "accounts", "funds", "fund_exposures", "fund_strategic_targets", "fund_prices_daily",
        "benchmarks", "benchmarks_daily", "external_movements", "contribution_room", "persona", "internal_trades")


def _prix(t: dict[str, list[dict]]) -> dict[str, list[tuple[dt.date, float]]]:
    prix: dict[str, list[tuple[dt.date, float]]] = {}
    for p in t["fund_prices_daily"]:
        prix.setdefault(p["fund_id"], []).append((p["date"], p["nav_total_return"]))
    return {f: sorted(s) for f, s in prix.items()}


def construire(cfg: Config, dossier: Path) -> dict[str, list[dict]]:
    t = {n: lire_csv(dossier / "data" / f"{n}.csv", n) for n in LUES}
    prix = _prix(t)
    dist = distributions(cfg, sorted(t["funds"], key=lambda f: f["fund_id"]), prix)
    kf = facteurs(prix, dist)
    lignes, sommaire = transactions(cfg, t, dist, kf)
    cotes, symboles, reperes = cours(cfg, t, prix, kf)
    tables = comptes(cfg, t) | profils(cfg, t)
    tables |= {"ref.symbole": symboles, "ref.repere": reperes, "pub.rapport_annuel": rapports_annuels(cfg, t, dist),
               "pub.cours": cotes, "fait.transaction": lignes, "fait.sommaire": sommaire, "distributions": dist}
    return tables


def ecrire(chemin: Path, colonnes: list[tuple[str, str]], lignes: list[dict]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c for c, _ in colonnes])
        for l in lignes:
            w.writerow(["" if l[c] is None else TYPES[ty][0](l[c]) for c, ty in colonnes])


def adapter(cfg: Config, dossier: Path) -> dict[str, int]:
    """Écrit finance_ve01/ dans le dossier d'export ; rend le nombre de lignes par fichier."""
    if cfg.adapter is None:
        raise AdaptateurError("section [adapter] absente de la configuration")
    tables = construire(cfg, dossier)
    sortie = dossier / DOSSIER
    sortie.mkdir(exist_ok=True)
    for ancien in sortie.glob("*.csv"):
        ancien.unlink()
    for nom, colonnes in TABLES.items():
        ecrire(sortie / f"{nom}.csv", colonnes, tables[nom])
    ecrire(sortie / "distributions.csv", DISTRIBUTIONS, tables["distributions"])
    return {nom: len(l) for nom, l in tables.items()}


def lire(dossier: Path, nom: str) -> list[dict]:
    """Relit un fichier de finance_ve01/ en types Python (même contrat que export.lire_csv)."""
    colonnes = DISTRIBUTIONS if nom == "distributions" else TABLES[nom]
    with (dossier / DOSSIER / f"{nom}.csv").open(encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        if next(r) != [c for c, _ in colonnes]:
            raise ValueError(f"{nom}.csv : en-tête ≠ schéma")
        return [{c: None if v == "" else TYPES[ty][1](v) for (c, ty), v in zip(colonnes, l, strict=True)} for l in r]
