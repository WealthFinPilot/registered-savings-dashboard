"""Moteur E (partie univers) — contrôles bloquants et diagnostics d'un dossier d'export.

La validation relit les CSV écrits, jamais les objets en mémoire : elle contrôle ce qui sera importé.
Chaque contrôle rend pass/fail et un détail ; un diagnostic (warning) signale une anomalie sans
bloquer. Rien n'est corrigé.
"""
import datetime as dt
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .benchmarks import categorie_du_fonds
from .config import ASSET_CLASSES, GEOGRAPHIES, PROFILES, STYLES, Config, construire, empreinte
from .export import TABLES_ETAPE, lire_csv
from .market import jours_ouvrables

TOLERANCE_AXE = 0.01                    # point de %, sur un total de 100
QUASI_IDENTIQUES = 5.0                  # distance L1 (points) entre expositions de deux fonds
CORRELATION_COPIE = 0.98                # deux fonds plus corrélés que cela : trajectoires dupliquées
# Deux fonds d'un même archétype chez deux institutions se ressemblent : c'est voulu (recouvrement
# de stratégies). L'anomalie est un groupe d'au moins trois fonds deux à deux quasi identiques.


@dataclass
class Resultat:
    name: str
    status: str                         # pass | fail
    detail: str


def _dates(objet):
    """Configuration relue du manifest : chaînes AAAA-MM-JJ redevenues des dates (comme en TOML)."""
    if isinstance(objet, dict):
        return {k: _dates(v) for k, v in objet.items()}
    if isinstance(objet, list):
        return [_dates(v) for v in objet]
    if isinstance(objet, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", objet):
        return dt.date.fromisoformat(objet)
    return objet


def charger_export(dossier: Path) -> tuple[dict, Config, dict[str, list[dict]]]:
    manifest = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    raw = _dates(manifest["config"])
    if empreinte(raw) != manifest["config_hash"]:
        raise ValueError("manifest.json : la configuration enregistrée ne correspond pas à config_hash")
    tables = {t: lire_csv(dossier / "data" / f"{t}.csv", t) for e in manifest["stages"] for t in TABLES_ETAPE[e]}
    return manifest, construire(raw), tables


def equity_share(tables: dict[str, list[dict]]) -> dict[str, float]:
    """Part en actions de chaque fonds (0 à 1), axe classe d'actifs."""
    parts = {f["fund_id"]: 0.0 for f in tables["funds"]}
    for l in tables["fund_exposures_by_axis"]:
        if l["axis"] == "asset_class" and l["category"] == "equity":
            parts[l["fund_id"]] = l["weight"] / 100
    return parts


def politique_actions(tables: dict[str, list[dict]]) -> dict[str, float]:
    """Part en actions de l'allocation cible initiale de chaque institution (0 à 1)."""
    eq = equity_share(tables)
    sortie: dict[str, float] = {}
    for l in tables["allocation_targets_history"]:
        if l["level"] == "institution":
            sortie[l["institution_id"]] = sortie.get(l["institution_id"], 0) + l["target_weight"] / 100 * eq[l["fund_id"]]
    return sortie


def controler(manifest: dict, cfg: Config, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    inst, comptes, fonds = t["institutions"], t["accounts"], t["funds"]
    id_inst = {i["institution_id"] for i in inst}
    id_fonds = {f["fund_id"]: f for f in fonds}
    id_comptes = {c["account_id"]: c for c in comptes}

    check("manifest_synthetique", [] if manifest.get("synthetic") is True and manifest.get("synthetic_flag") is True
          else ["drapeau synthetic absent ou faux"], "synthetic = true")

    # Clés et références
    erreurs = []
    for table, cle in (("institutions", ("institution_id",)), ("institutions", ("name",)),
                       ("accounts", ("account_id",)), ("accounts", ("account_alias",)), ("funds", ("fund_id",)),
                       ("funds", ("fund_name",)), ("fund_exposures", ("fund_id", "asset_class", "geography", "style")),
                       ("fund_exposures_by_axis", ("fund_id", "axis", "category")),
                       ("fund_strategic_targets", ("fund_id", "asset_class")),
                       ("allocation_targets_history", ("effective_date", "level", "institution_id", "account_id", "fund_id"))):
        vus = [tuple(l[c] for c in cle) for l in t[table]]
        if len(vus) != len(set(vus)):
            erreurs.append(f"{table} : doublons sur {cle}")
    check("cles_uniques", erreurs, "aucun doublon de clé")

    erreurs = [f"accounts {c['account_id']} : institution {c['institution_id']} inconnue" for c in comptes
               if c["institution_id"] not in id_inst]
    erreurs += [f"funds {f['fund_id']} : institution {f['institution_id']} inconnue" for f in fonds
                if f["institution_id"] not in id_inst]
    for table in ("fund_exposures", "fund_exposures_by_axis", "fund_strategic_targets", "allocation_targets_history"):
        erreurs += [f"{table} : fonds {l['fund_id']} inconnu" for l in t[table] if l["fund_id"] not in id_fonds]
    for l in t["allocation_targets_history"]:
        f = id_fonds.get(l["fund_id"])
        if l["level"] == "account":
            c = id_comptes.get(l["account_id"])
            if c is None:
                erreurs.append(f"cible : compte {l['account_id']} inconnu")
            elif f and f["institution_id"] != c["institution_id"]:
                erreurs.append(f"cible : fonds {f['fund_id']} hors de l'institution du compte {c['account_id']}")
        elif l["level"] == "institution":
            if l["account_id"] is not None or (f and f["institution_id"] != l["institution_id"]):
                erreurs.append(f"cible d'institution incohérente : {l}")
        else:
            erreurs.append(f"cible : niveau inconnu {l['level']}")
    check("references", erreurs, "aucune référence orpheline")

    # Institutions et fonds
    profils = sorted(i["strategy_profile"] for i in inst)
    check("trois_institutions", [] if len(inst) == 3 and profils == sorted(PROFILES)
          else [f"{len(inst)} institutions, profils {profils}"], "3 institutions, un profil chacune")
    erreurs = [] if cfg.fund_count[0] <= len(fonds) <= cfg.fund_count[1] \
        else [f"{len(fonds)} fonds hors de {cfg.fund_count}"]
    for spec, i in zip(cfg.institutions, sorted(inst, key=lambda x: x["institution_id"])):
        n = sum(1 for f in fonds if f["institution_id"] == i["institution_id"])
        if not spec.fund_count[0] <= n <= spec.fund_count[1]:
            erreurs.append(f"{i['name']} : {n} fonds hors de {spec.fund_count}")
    check("nombre_de_fonds", erreurs, f"{len(fonds)} fonds, " + ", ".join(
        f"{i['name']} {sum(1 for f in fonds if f['institution_id'] == i['institution_id'])}" for i in inst))
    erreurs = [f"{f['fund_id']} : nom non marqué fictif" for f in fonds if not f["fund_name"].endswith("(fictif)")]
    erreurs += [f"{i['institution_id']} : nom {i['name']!r} hors du motif « Société N »" for i in inst
                if not re.fullmatch(r"Société \d", i["name"])]
    check("noms_fictifs", erreurs, "institutions « Société N », fonds marqués « (fictif) »")

    # Expositions : chaque axe à 100 %, catégories connues, cohérence cellule / axe
    erreurs = []
    categories = {"asset_class": ASSET_CLASSES, "geography": GEOGRAPHIES, "style": STYLES}
    for fid in id_fonds:
        cellules = [l for l in t["fund_exposures"] if l["fund_id"] == fid]
        if not cellules:
            erreurs.append(f"{fid} : aucune exposition")
            continue
        for axe, cats in categories.items():
            somme: dict[str, float] = {}
            for l in cellules:
                if l[axe] not in cats:
                    erreurs.append(f"{fid} : {axe} inconnu {l[axe]}")
                somme[l[axe]] = somme.get(l[axe], 0) + l["weight"]
            if abs(sum(somme.values()) - 100) > TOLERANCE_AXE:
                erreurs.append(f"{fid} : axe {axe} = {sum(somme.values()):.4f} %")
            publie = {l["category"]: l["weight"] for l in t["fund_exposures_by_axis"]
                      if l["fund_id"] == fid and l["axis"] == axe}
            if set(publie) != set(somme) or any(abs(publie[k] - somme[k]) > 1e-6 for k in somme):
                erreurs.append(f"{fid} : vue par axe {axe} ≠ cellules")
        cible = sum(l["target_weight"] for l in t["fund_strategic_targets"] if l["fund_id"] == fid)
        if abs(cible - 100) > TOLERANCE_AXE:
            erreurs.append(f"{fid} : mandat = {cible} %")
        if any(l["weight"] <= 0 for l in cellules):
            erreurs.append(f"{fid} : poids nul ou négatif")
    check("expositions_100", erreurs, f"3 axes × {len(fonds)} fonds à 100 % ± {TOLERANCE_AXE}, mandats à 100 %")

    erreurs = [f"{f['fund_id']} : frais de palier haut {f['account_fee_high_pct']} > bas {f['account_fee_low_pct']}"
               for f in fonds if f["account_fee_high_pct"] > f["account_fee_low_pct"]]
    erreurs += [f"{f['fund_id']} : devise {f['currency']}" for f in fonds if f["currency"] != "CAD"]
    erreurs += [f"{f['fund_id']} : RFG {f['mer_pct']} hors de ]0, 3]" for f in fonds if not 0 < f["mer_pct"] <= 3]
    check("frais_coherents", erreurs, "RFG dans ]0, 3] %, palier haut ≤ palier bas, tout en CAD")

    # Comptes et régimes
    regimes = {c["regime"] for c in comptes}
    erreurs = [] if regimes == set(cfg.regimes) else [f"régimes présents {sorted(regimes)}"]
    erreurs += [f"{c['account_id']} : alias {c['account_alias']!r} hors du motif <RÉGIME>-<n>" for c in comptes
                if not re.fullmatch(rf"{c['regime']}-\d+", c["account_alias"]) or c["account_alias"] == c["regime"]]
    erreurs += [f"{c['account_id']} : régime {c['regime']} inconnu" for c in comptes if c["regime"] not in cfg.regimes]
    paires = [(c["institution_id"], c["regime"]) for c in comptes]
    erreurs += ["deux comptes d'un même régime dans une institution"] if len(paires) != len(set(paires)) else []
    for i in inst:
        n = sum(1 for c in comptes if c["institution_id"] == i["institution_id"])
        if n < cfg.accounts["min_per_institution"]:
            erreurs.append(f"{i['name']} : {n} compte(s)")
    check("regimes_et_alias", erreurs, f"4 régimes, {len(comptes)} comptes, alias distincts du régime")

    erreurs = [f"{c['account_alias']} ouvert le {c['opened_at']}" for c in comptes
               if c["regime"] == "CELIAPP" and c["opened_at"] < cfg.celiapp_available_from]
    check("celiapp_apres_ouverture_du_regime", erreurs, f"aucun CELIAPP avant le {cfg.celiapp_available_from}")

    erreurs = [f"{c['account_alias']} ouvert le {c['opened_at']} hors horizon" for c in comptes
               if not cfg.start_date <= c["opened_at"] <= cfg.end_date]
    erreurs += [f"{c['account_alias']} fermé le {c['closed_at']} avant ouverture" for c in comptes
                if c["closed_at"] is not None and c["closed_at"] < c["opened_at"]]
    for i in inst:
        premier = min((c["opened_at"] for c in comptes if c["institution_id"] == i["institution_id"]), default=None)
        if premier != i["opened_at"]:
            erreurs.append(f"{i['name']} : ouverte le {i['opened_at']}, premier compte le {premier}")
    check("dates_d_ouverture", erreurs, "comptes ouverts dans l'horizon, institutions ouvertes avec leur premier compte")

    # Allocations cibles
    erreurs = []
    groupes: dict[tuple, float] = {}
    for l in t["allocation_targets_history"]:
        cle = (l["level"], l["account_id"] or l["institution_id"], l["effective_date"])
        groupes[cle] = groupes.get(cle, 0) + l["target_weight"]
        f = id_fonds[l["fund_id"]]
        if f["inception_date"] > l["effective_date"]:
            erreurs.append(f"cible {cle} : fonds {f['fund_id']} lancé le {f['inception_date']}")
        ouverture = id_comptes[l["account_id"]]["opened_at"] if l["level"] == "account" else \
            next(i["opened_at"] for i in inst if i["institution_id"] == l["institution_id"])
        if l["effective_date"] < ouverture:
            erreurs.append(f"cible {cle} avant l'ouverture ({ouverture})")
    erreurs += [f"cible {k} : total {v} %" for k, v in groupes.items() if abs(v - 100) > TOLERANCE_AXE]
    sans_cible = [c["account_id"] for c in comptes if not any(k[0] == "account" and k[1] == c["account_id"] for k in groupes)]
    erreurs += [f"compte {c} sans allocation cible" for c in sans_cible]
    check("allocations_cibles", erreurs, f"{len(groupes)} allocations à 100 %, aucun fonds avant son lancement")

    # Poids d'épargne a priori : asymétriques, sans extrême absurde
    poids = [i["savings_weight_prior"] for i in inst]
    erreurs = [] if abs(sum(poids) - 1) < 1e-6 else [f"total {sum(poids)}"]
    erreurs += [] if min(poids) >= cfg.min_institution_weight else [f"poids minimal {min(poids)}"]
    erreurs += ["répartition quasi égale (toutes les parts à moins de 2 points de 33,3 %)"] \
        if all(abs(p - 1 / 3) < cfg.equal_split_tolerance for p in poids) else []
    check("poids_institutions_asymetriques", erreurs, " / ".join(f"{i['name']} {i['savings_weight_prior']:.1%}" for i in inst))

    # Profils lisibles : part en actions de la politique croissante prudent < intermédiaire < dynamique
    eq = politique_actions(t)
    rang = {i["strategy_profile"]: eq[i["institution_id"]] for i in inst}
    suite = [rang[p] for p in PROFILES]
    check("profils_ordonnes", [] if suite == sorted(suite) and len(set(suite)) == 3
          else [f"parts en actions {dict(zip(PROFILES, suite))}"],
          " < ".join(f"{p} {rang[p]:.1%}" for p in PROFILES))

    # Diagnostics (non bloquants)
    alertes = []
    for p, v in rang.items():
        if abs(v * 100 / 5 - round(v * 100 / 5)) < 1e-6:
            alertes.append(f"part en actions du profil {p} sur un multiple de 5 % ({v:.2%})")
    vecteurs = {fid: {(l["asset_class"], l["geography"], l["style"]): l["weight"] for l in t["fund_exposures"]
                      if l["fund_id"] == fid} for fid in id_fonds}
    ids = sorted(vecteurs)
    proches = {a: set() for a in ids}
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            d = sum(abs(vecteurs[a].get(k, 0) - vecteurs[b].get(k, 0)) for k in set(vecteurs[a]) | set(vecteurs[b]))
            if d < QUASI_IDENTIQUES:
                proches[a].add(b)
                proches[b].add(a)
    for a in ids:
        for b in sorted(x for x in proches[a] if x > a):
            for c in sorted(x for x in proches[a] & proches[b] if x > b):
                alertes.append(f"trois fonds quasi identiques {a}, {b}, {c} (distance < {QUASI_IDENTIQUES} points)")
    if max(poids) > 0.95:
        alertes.append("une institution dépasse 95 % des poids d'épargne")
    return res, alertes


# ------------------------------------------------------------------------------------------------
# Marchés (J2) : mesures sur les séries exportées
# ------------------------------------------------------------------------------------------------
def series(lignes: list[dict], cle: str, valeur: str) -> dict[str, tuple[list[dt.date], np.ndarray]]:
    """Séries par identifiant, triées par date : (dates, valeurs)."""
    groupes: dict[str, list[tuple[dt.date, float]]] = {}
    for l in lignes:
        groupes.setdefault(l[cle], []).append((l["date"], l[valeur]))
    return {k: ([d for d, _ in sorted(v)], np.array([x for _, x in sorted(v)])) for k, v in groupes.items()}


def rendements_log(valeurs: np.ndarray) -> np.ndarray:
    return np.diff(np.log(valeurs))


def volatilite(valeurs: np.ndarray, jours: int = 252) -> float:
    """Volatilité annualisée des rendements log journaliers."""
    return float(rendements_log(valeurs).std(ddof=1) * math.sqrt(jours))


def repli_max(valeurs: np.ndarray) -> float:
    """Repli maximal depuis le plus haut précédent (négatif ou nul)."""
    return float((valeurs / np.maximum.accumulate(valeurs) - 1).min())


def rendements_annuels(dates: list[dt.date], valeurs: np.ndarray) -> dict[int, tuple[float, bool]]:
    """Rendement par année civile : (rendement, année complète). Une année est complète si la série la
    couvre du premier au dernier jour ouvrable ; son point de départ est alors la dernière valeur de
    l'année précédente. Sinon, le rendement court de la première à la dernière valeur de l'année."""
    sortie = {}
    for annee in sorted({d.year for d in dates}):
        idx = [i for i, d in enumerate(dates) if d.year == annee]
        depart = idx[0] - 1 if idx[0] > 0 else idx[0]
        complete = idx[0] > 0 and dates[idx[-1]] >= dt.date(annee, 12, 29)
        sortie[annee] = (float(valeurs[idx[-1]] / valeurs[depart] - 1), complete)
    return sortie


def correlation(a: tuple[list[dt.date], np.ndarray], b: tuple[list[dt.date], np.ndarray]) -> float:
    """Corrélation des rendements log journaliers sur les dates communes."""
    communes = set(a[0]) & set(b[0])
    va = np.array([x for d, x in zip(*a) if d in communes])
    vb = np.array([x for d, x in zip(*b) if d in communes])
    return float(np.corrcoef(rendements_log(va), rendements_log(vb))[0, 1])


def controler_marches(cfg: Config, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    jours = jours_ouvrables(cfg.start_date, cfg.end_date)
    fonds = {f["fund_id"]: f for f in t["funds"]}
    regimes = {l["date"]: l["regime"] for l in t["market_regimes_daily"]}
    erreurs = [] if [l["date"] for l in t["market_regimes_daily"]] == jours         else [f"{len(regimes)} jours de régime pour {len(jours)} jours ouvrables"]
    connus = set(cfg.markets.regimes) if cfg.markets else set()
    erreurs += [f"régime inconnu {r}" for r in sorted(set(regimes.values()) - connus)]
    check("marche_calendrier", erreurs, f"{len(jours)} jours ouvrables (lundi à vendredi) du {jours[0]} au "
          f"{jours[-1]}, {len(set(regimes.values()))} régimes visités")

    vl = series(t["fund_prices_daily"], "fund_id", "nav_total_return")
    erreurs = [f"fonds {k} inconnu" for k in vl if k not in fonds]
    erreurs += [f"{k} : aucune VL" for k in fonds if k not in vl]
    paires = [(l["date"], l["fund_id"]) for l in t["fund_prices_daily"]]
    erreurs += ["fund_prices_daily : doublons (date, fund_id)"] if len(paires) != len(set(paires)) else []
    for k, (dates, _) in vl.items():
        if k not in fonds:
            continue
        lancement = fonds[k]["inception_date"]
        attendu = [d for d in jours if d >= max(cfg.start_date, lancement)]
        if dates != attendu:
            avant = sum(1 for d in dates if d < lancement)
            erreurs.append(f"{k} : {len(dates)} VL pour {len(attendu)} jours ouvrables attendus"
                           + (f", dont {avant} avant le lancement du {lancement}" if avant else ""))
    check("marche_grain_vl", erreurs, f"{len(t['fund_prices_daily'])} VL : une par fonds et jour ouvrable, du "
          f"lancement (ou du début de l'horizon) à la fin, aucune avant le lancement")

    ind = series(t["benchmarks_daily"], "benchmark_id", "index_total_return")
    ids = [b["benchmark_id"] for b in t["benchmarks"]]
    erreurs = ["benchmarks : identifiants en double"] if len(ids) != len(set(ids)) else []
    erreurs += [f"repère {k} absent de benchmarks.csv" for k in ind if k not in ids]
    erreurs += [f"{k} : aucun indice" for k in ids if k not in ind]
    erreurs += [f"{k} : {len(d)} indices pour {len(jours)} jours ouvrables" for k, (d, _) in ind.items() if d != jours]
    check("marche_grain_reperes", erreurs, f"{len(t['benchmarks_daily'])} indices : une ligne par repère et jour "
          f"ouvrable de l'horizon, {len(ids)} repères")

    erreurs = [f"{l['fund_id']} {l['date']} : VL {l['nav_total_return']}" for l in t["fund_prices_daily"]
               if not (math.isfinite(l["nav_total_return"]) and l["nav_total_return"] > 0)]
    erreurs += [f"{l['benchmark_id']} {l['date']} : indice {l['index_total_return']}" for l in t["benchmarks_daily"]
                if not (math.isfinite(l["index_total_return"]) and l["index_total_return"] > 0)]
    erreurs += [f"devise {c}" for c in {l["currency"] for l in t["fund_prices_daily"] + t["benchmarks_daily"]} - {"CAD"}]
    check("marche_valeurs_positives", erreurs, "VL et indices finis, strictement positifs, en CAD")

    erreurs = []
    reperes = {b["benchmark_id"]: b for b in t["benchmarks"]}
    for f in fonds.values():
        b = reperes.get(f"R-{f['fund_id']}")
        if b is None or b["benchmark_type"] != "composite" or b["fund_id"] != f["fund_id"]:
            erreurs.append(f"{f['fund_id']} : composite absent ou mal rattaché")
        elif not b["passive_fee_pct"] < f["mer_pct"]:
            erreurs.append(f"R-{f['fund_id']} : frais passifs {b['passive_fee_pct']} ≥ RFG {f['mer_pct']}")
    cibles = [l for l in t["allocation_targets_history"] if l["level"] == "institution"]
    for i in t["institutions"]:
        b = reperes.get(f"R-POL-{i['institution_id']}")
        lignes = [l for l in cibles if l["institution_id"] == i["institution_id"]]
        premiere = min(l["effective_date"] for l in lignes)
        rfg = sum(l["target_weight"] / 100 * fonds[l["fund_id"]]["mer_pct"] for l in lignes
                  if l["effective_date"] == premiere)
        if b is None or b["benchmark_type"] != "policy" or b["institution_id"] != i["institution_id"]:
            erreurs.append(f"{i['institution_id']} : repère de politique absent ou mal rattaché")
        elif not b["passive_fee_pct"] < rfg:
            erreurs.append(f"R-POL-{i['institution_id']} : frais passifs {b['passive_fee_pct']} ≥ RFG pondéré {rfg:.2f}")
    contexte = sorted(k for k, b in reperes.items() if b["benchmark_type"] == "sensitivity")
    erreurs += [] if contexte == ["R-ACT-MONDE", "R-EQUILIBRE"] else [f"repères de contexte {contexte}"]
    for f in fonds.values():
        k = categorie_du_fonds(cfg, f["archetype"])
        b = reperes.get(k)
        if b is None or b["benchmark_type"] != "category":
            erreurs.append(f"{f['fund_id']} : repère de catégorie {k} absent")
        elif not b["passive_fee_pct"] < f["mer_pct"]:
            erreurs.append(f"{k} : frais passifs {b['passive_fee_pct']} ≥ RFG {f['mer_pct']} de {f['fund_id']}")
    attendus = {categorie_du_fonds(cfg, f["archetype"]) for f in fonds.values()}
    categories = {k for k, b in reperes.items() if b["benchmark_type"] == "category"}
    erreurs += [f"repères de catégorie sans fonds : {sorted(categories - attendus)}"] if categories - attendus else []
    erreurs += [f"{k} : base {v[0]} ≠ 100" for k, (_, v) in ind.items() if abs(v[0] - 100) > 1e-9]
    check("marche_reperes", erreurs, f"{len(fonds)} composites (frais passifs < RFG du fonds), "
          f"{len(t['institutions'])} politiques (frais < RFG pondéré), 2 repères de contexte, "
          f"{len(categories)} repères de catégorie (frais passifs < RFG de chaque fonds comparé), base 100")

    # Diagnostics : trajectoires dupliquées, volatilité quasi nulle hors marché monétaire
    alertes = []
    cles = sorted(k for k in vl if k in fonds)
    for i, a in enumerate(cles):
        for b in cles[i + 1:]:
            c = correlation(vl[a], vl[b])
            if c > CORRELATION_COPIE:
                alertes.append(f"{a} et {b} : corrélation {c:.3f} > {CORRELATION_COPIE}")
    for k in cles:
        v = volatilite(vl[k][1])
        if v < 0.005 and fonds[k]["archetype"] != "monetaire":
            alertes.append(f"{k} : volatilité {v:.2%}, quasi nulle")
    return res, alertes


# ------------------------------------------------------------------------------------------------
# Comportement (J3)
# ------------------------------------------------------------------------------------------------
TYPES_FLUX = ("PAC", "PONCTUEL", "RETRAIT")
EVENEMENTS_CIBLE = ("revue_annuelle", "ajout_fonds", "prudence_marche", "retour_cible")


def annee_droits(regime: str, jour: dt.date, periodes: dict[int, dt.date]) -> int:
    """Année civile (CELI, CELIAPP) ou année de déduction (REER : première période qui finit à la date ou après)."""
    if regime != "REER":
        return jour.year
    return min(a for a, fin in periodes.items() if fin >= jour)


def controler_comportement(cfg: Config, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    comptes = {c["account_id"]: c for c in t["accounts"]}
    insts = {i["institution_id"] for i in t["institutions"]}
    mvts = [m for m in t["external_movements"] if m["movement_type"] != "FRAIS"]   # FRAIS : grand livre (J4)
    evs = t["events"]
    id_ev = {e["event_id"]: e for e in evs}

    erreurs = [f"{m['movement_id']} : type {m['movement_type']}" for m in mvts if m["movement_type"] not in TYPES_FLUX]
    erreurs += [f"{m['movement_id']} : {m['movement_type']} de signe incorrect ({m['amount_cad']})" for m in mvts
                if (m["movement_type"] == "RETRAIT") != (m["amount_cad"] < 0) or m["amount_cad"] == 0]
    erreurs += [f"{m['movement_id']} : {m['amount_cad']} hors du cent" for m in mvts
                if abs(m["amount_cad"] * 100 - round(m["amount_cad"] * 100)) > 1e-6]
    n = {k: sum(1 for m in mvts if m["movement_type"] == k) for k in TYPES_FLUX}
    check("comportement_types_et_signes", erreurs, f"{len(mvts)} mouvements : {n['PAC']} PAC, {n['PONCTUEL']} ponctuels, "
          f"{n['RETRAIT']} retraits ; apports > 0, retraits < 0, au cent (FRAIS : contrôles du grand livre)")

    erreurs = []
    for m in mvts:
        c = comptes.get(m["account_id"])
        if c is None:
            erreurs.append(f"{m['movement_id']} : compte {m['account_id']} inconnu")
            continue
        if m["date"].weekday() >= 5:
            erreurs.append(f"{m['movement_id']} : {m['date']} n'est pas un jour ouvrable")
        if not c["opened_at"] <= m["date"] <= cfg.end_date or (c["closed_at"] and m["date"] >= c["closed_at"]):
            erreurs.append(f"{m['movement_id']} : {m['date']} hors de la vie du {c['account_alias']}")
    check("comportement_comptes_et_dates", erreurs, "chaque mouvement : compte connu, jour ouvrable, entre l'ouverture du "
          "compte et la fin de l'horizon")

    erreurs = [] if len(id_ev) == len(evs) else ["events : identifiants en double"]
    ids_m = [m["movement_id"] for m in mvts]
    erreurs += [] if len(ids_m) == len(set(ids_m)) else ["external_movements : identifiants en double"]
    for m in mvts:
        e = id_ev.get(m["event_id"])
        if e is None:
            erreurs.append(f"{m['movement_id']} : événement {m['event_id']} absent")
        elif e["date"] > m["date"]:
            erreurs.append(f"{m['movement_id']} : événement {e['event_id']} daté du {e['date']}, après le mouvement")
    erreurs += [f"{e['event_id']} : compte {e['account_id']} inconnu" for e in evs if e["account_id"] and e["account_id"] not in comptes]
    erreurs += [f"{e['event_id']} : institution {e['institution_id']} inconnue" for e in evs
                if e["institution_id"] and e["institution_id"] not in insts]
    erreurs += [f"{e['event_id']} : {e['date']} hors horizon" for e in evs if not cfg.start_date <= e["date"] <= cfg.end_date]
    # Nouvelle cible d'un compte (après celle de son ouverture) : un événement de révision le même jour
    revisions = {(e["account_id"], e["date"]) for e in evs if e["event_type"] in EVENEMENTS_CIBLE}
    nouvelles = {(l["account_id"], l["effective_date"]) for l in t["allocation_targets_history"]
                 if l["level"] == "account" and l["effective_date"] > comptes[l["account_id"]]["opened_at"]}
    erreurs += [f"cible {a} du {d} sans événement de révision" for a, d in sorted(nouvelles - revisions)]
    check("comportement_evenements", erreurs, f"{len(evs)} événements, clés uniques ; chaque mouvement et chacune des "
          f"{len(nouvelles)} nouvelles cibles de compte renvoient à un événement daté au plus tard le jour de l'effet")

    erreurs = [f"{m['movement_id']} : retrait d'un {comptes[m['account_id']]['regime']}" for m in mvts
               if m["movement_type"] == "RETRAIT" and comptes[m["account_id"]]["regime"] in ("REER", "CELIAPP")]
    erreurs += [f"{m['movement_id']} : CELIAPP alimenté le {m['date']}, avant le {cfg.celiapp_available_from}" for m in mvts
                if comptes[m["account_id"]]["regime"] == "CELIAPP" and m["date"] < cfg.celiapp_available_from]
    check("comportement_regimes", erreurs, "aucun retrait de REER ni de CELIAPP ; aucun CELIAPP alimenté avant "
          f"{cfg.celiapp_available_from}")

    # Droits : la table contribution_room réconciliée avec les mouvements et les plafonds exportés
    erreurs = []
    periodes = {l["year"]: l["period_end"] for l in t["tax_limits"] if l["rubric"] == "fin_periode"}
    plafond = {(l["regime"], l["rubric"], l["year"]): l["amount_cad"] for l in t["tax_limits"] if l["amount_cad"] is not None}
    cotis: dict[tuple[str, int], float] = {}
    retraits: dict[tuple[str, int], float] = {}
    for m in mvts:
        regime = comptes[m["account_id"]]["regime"]
        if regime == "COMP":
            continue
        cle = (regime, annee_droits(regime, m["date"], periodes))
        cible = cotis if m["amount_cad"] > 0 else retraits
        cible[cle] = cible.get(cle, 0.0) + abs(m["amount_cad"])
    salle = {(l["regime"], l["year"]): l for l in t["contribution_room"]}
    # Excédent admis seulement l'année d'un ponctuel imposé (behaviour.scripted_lumps), dans son régime
    alias = {c["account_alias"]: c for c in comptes.values()}
    hors_droits = {(alias[x["account"]]["regime"], annee_droits(alias[x["account"]]["regime"], x["date"], periodes))
                   for x in (cfg.behaviour or {}).get("scripted_lumps", ()) if alias[x["account"]]["regime"] != "COMP"}
    for cle in set(cotis) | set(retraits):
        if cle not in salle:
            erreurs.append(f"droits {cle} absents de contribution_room")
    for (regime, a), l in sorted(salle.items()):
        if abs(l["contributions_cad"] - cotis.get((regime, a), 0.0)) > 0.005:
            erreurs.append(f"{regime} {a} : cotisations {l['contributions_cad']} ≠ mouvements {cotis.get((regime, a), 0.0):.2f}")
        if abs(l["withdrawals_cad"] - retraits.get((regime, a), 0.0)) > 0.005:
            erreurs.append(f"{regime} {a} : retraits {l['withdrawals_cad']} ≠ mouvements {retraits.get((regime, a), 0.0):.2f}")
        negatif_admis = (regime, a) in hors_droits
        if (l["room_end_cad"] < -0.005 and not negatif_admis)                 or abs(l["room_start_cad"] - l["contributions_cad"] - l["room_end_cad"]) > 0.005:
            erreurs.append(f"{regime} {a} : droits {l['room_start_cad']} − {l['contributions_cad']} ≠ {l['room_end_cad']} ou négatifs")
        prec = salle.get((regime, a - 1))
        if prec is None:
            continue
        if regime == "CELI":
            attendu = prec["room_end_cad"] + prec["withdrawals_cad"] + l["new_room_cad"]
        elif regime == "REER":
            attendu = prec["room_end_cad"] + l["new_room_cad"]
        else:
            verse = sum(x["contributions_cad"] for (r, y), x in salle.items() if r == "CELIAPP" and y < a)
            attendu = min(l["new_room_cad"] + min(plafond[("CELIAPP", "report_max", None)], max(prec["room_end_cad"], 0.0)),
                          plafond[("CELIAPP", "plafond_vie", None)] - verse)
        if abs(l["room_start_cad"] - attendu) > 0.01:
            erreurs.append(f"{regime} {a} : droits au début {l['room_start_cad']} ≠ report attendu {attendu:.2f}")
        if regime == "CELI" and abs(l["new_room_cad"] - plafond.get(("CELI", "plafond_annuel", a), -1)) > 0.005:
            erreurs.append(f"CELI {a} : nouveaux droits {l['new_room_cad']} ≠ plafond annuel")
    check("comportement_droits", erreurs, f"{len(salle)} lignes régime × année : cotisations et retraits = mouvements, "
          "droits jamais dépassés" + (f" hors excédents scénarisés {sorted(hors_droits)}" if hors_droits else "")
          + ", reports d'une année sur l'autre cohérents avec tax_limits")

    # Retraits : au plus withdrawal_max_share des apports nets du compte à leur date (garde-fou sans grand livre)
    erreurs = []
    part = cfg.behaviour["withdrawal_max_share"] if cfg.behaviour else 0.5
    ordre = {"PAC": 0, "PONCTUEL": 1, "RETRAIT": 2}
    nets: dict[str, float] = {}
    for m in sorted(mvts, key=lambda x: (x["date"], ordre[x["movement_type"]], x["movement_id"])):
        if m["movement_type"] == "RETRAIT" and -m["amount_cad"] > part * nets.get(m["account_id"], 0.0) + 1e-6:
            erreurs.append(f"{m['movement_id']} : retrait {-m['amount_cad']:.2f} > {part:.0%} des apports nets "
                           f"{nets.get(m['account_id'], 0.0):.2f}")
        nets[m["account_id"]] = nets.get(m["account_id"], 0.0) + m["amount_cad"]
    check("comportement_retraits_bornes", erreurs, f"{n['RETRAIT']} retraits, chacun ≤ {part:.0%} des apports nets du compte "
          "à sa date")

    alertes = []
    for a, c in comptes.items():
        pac = [m["amount_cad"] for m in mvts if m["account_id"] == a and m["movement_type"] == "PAC"]
        if len(pac) >= 6 and len(set(pac)) == 1:
            alertes.append(f"{c['account_alias']} : {len(pac)} PAC tous de {pac[0]:.2f} $")
    return res, alertes


# ------------------------------------------------------------------------------------------------
# Grand livre (J4)
# ------------------------------------------------------------------------------------------------
RESIDU_PARTS = 0.0005                   # demi-millième de part : arrondi des parts à 3 décimales
RESIDU_CENT = 0.005                     # vente de toutes les parts : montant arrondi au cent


def controler_grand_livre(cfg: Config, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    comptes = {c["account_id"]: c for c in t["accounts"]}
    fonds = {f["fund_id"]: f for f in t["funds"]}
    vl = {(l["fund_id"], l["date"]): l["nav_total_return"] for l in t["fund_prices_daily"]}
    ordres, mvts = t["internal_trades"], t["external_movements"]
    id_m = {m["movement_id"]: m for m in mvts}
    id_ev = {e["event_id"]: e for e in t["events"]}
    jours = jours_ouvrables(cfg.start_date, cfg.end_date)
    fins_mois = {j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month}
    cibles: dict[str, dict[dt.date, dict[str, float]]] = {}
    for l in t["allocation_targets_history"]:
        if l["level"] == "account":
            cibles.setdefault(l["account_id"], {}).setdefault(l["effective_date"], {})[l["fund_id"]] = l["target_weight"]

    # Format, liens et résidu de chaque ordre
    erreurs = [] if len({o["trade_id"] for o in ordres}) == len(ordres) else ["internal_trades : identifiants en double"]
    residus = []
    for o in ordres:
        k = o["trade_id"]
        if o["side"] not in ("BUY", "SELL") or o["units"] <= 0 or o["gross_amount_cad"] <= 0 or o["fee_cad"] != 0:
            erreurs.append(f"{k} : sens {o['side']}, parts {o['units']}, montant {o['gross_amount_cad']}, frais {o['fee_cad']}")
        if (o["movement_id"] is None) == (o["event_id"] is None):
            erreurs.append(f"{k} : ni mouvement ni événement, ou les deux")
        elif o["movement_id"] is not None and o["movement_id"] not in id_m:
            erreurs.append(f"{k} : mouvement {o['movement_id']} absent")
        elif o["event_id"] is not None and id_ev.get(o["event_id"], {}).get("event_type") != "reequilibrage":
            erreurs.append(f"{k} : {o['event_id']} n'est pas un rééquilibrage")
        x = vl.get((o["fund_id"], o["date"]))
        if x is None or abs(o["unit_price"] - x) > 1e-9:
            erreurs.append(f"{k} : prix {o['unit_price']} ≠ VL {x} du {o['fund_id']} le {o['date']}")
            continue
        residus.append(abs(o["units"] * x - o["gross_amount_cad"]))
        if residus[-1] > RESIDU_PARTS * x + RESIDU_CENT + 1e-9:
            erreurs.append(f"{k} : résidu {residus[-1]:.4f} $ au-delà de l'arrondi des parts")
    check("grand_livre_ordres", erreurs, f"{len(ordres)} ordres : BUY ou SELL, parts > 0, VL du jour, aucun frais de "
          f"transaction, un lien chacun (mouvement ou rééquilibrage) ; résidu d'arrondi max {max(residus, default=0):.4f} $, "
          f"total {sum(residus):.2f} $")

    # Dates et fonds : vie du compte, lancement du fonds, cible en vigueur pour un achat
    erreurs = []
    for o in ordres:
        c = comptes.get(o["account_id"])
        if c is None or o["fund_id"] not in fonds:
            erreurs.append(f"{o['trade_id']} : compte ou fonds inconnu")
            continue
        if not c["opened_at"] <= o["date"] <= cfg.end_date or (c["closed_at"] and o["date"] >= c["closed_at"]):
            erreurs.append(f"{o['trade_id']} : {o['date']} hors de la vie du {c['account_alias']}")
        if o["date"] < fonds[o["fund_id"]]["inception_date"]:
            erreurs.append(f"{o['trade_id']} : {o['fund_id']} pas encore lancé le {o['date']}")
        if o["side"] == "BUY":
            vise = [x for d, x in sorted(cibles.get(o["account_id"], {}).items()) if d <= o["date"]]
            if not vise or vise[-1].get(o["fund_id"], 0) <= 0:
                erreurs.append(f"{o['trade_id']} : achat de {o['fund_id']}, hors de la cible du {c['account_alias']}")
    check("grand_livre_ordres_dates", erreurs, "chaque ordre dans la vie de son compte, sur un fonds lancé ; chaque achat "
          "sur un fonds de la cible en vigueur")

    # Mouvements : un apport = ses achats, un retrait ou un frais = ses ventes ; un rééquilibrage, ventes = achats
    erreurs = []
    par_lien: dict[str, dict[str, int]] = {}
    for o in ordres:
        cle = o["movement_id"] or o["event_id"]
        par_lien.setdefault(cle, {"BUY": 0, "SELL": 0})[o["side"]] += round(o["gross_amount_cad"] * 100)
    for m in mvts:
        s = par_lien.get(m["movement_id"], {"BUY": 0, "SELL": 0})
        sens = "BUY" if m["amount_cad"] > 0 else "SELL"
        if s[sens] != round(abs(m["amount_cad"]) * 100) or s["BUY" if sens == "SELL" else "SELL"]:
            erreurs.append(f"{m['movement_id']} ({m['movement_type']} {m['amount_cad']:.2f}) : achats {s['BUY'] / 100:.2f}, "
                           f"ventes {s['SELL'] / 100:.2f}")
    reeq = [e for e in t["events"] if e["event_type"] == "reequilibrage"]
    for e in reeq:
        s = par_lien.get(e["event_id"], {"BUY": 0, "SELL": 0})
        if s["BUY"] != s["SELL"] or s["BUY"] == 0:
            erreurs.append(f"{e['event_id']} : ventes {s['SELL'] / 100:.2f} ≠ achats {s['BUY'] / 100:.2f}")
    frais = [m for m in mvts if m["movement_type"] == "FRAIS"]
    erreurs += [f"{m['movement_id']} : FRAIS {m['amount_cad']} le {m['date']}" for m in frais
                if m["amount_cad"] >= 0 or m["date"] not in fins_mois or m["event_id"] is not None]
    check("grand_livre_mouvements", erreurs, f"{len(mvts)} mouvements, chacun exécuté une fois (apport = achats, retrait ou "
          f"frais = ventes) ; {len(reeq)} rééquilibrages à ventes = achats ; {len(frais)} FRAIS < 0 en fin de mois")

    # Positions : parts = cumul des ordres, jamais négatives ; valeurs au cent ; une valeur par compte ouvert et par jour
    erreurs = []
    flux_ordres: dict[tuple[dt.date, str, str], int] = {}
    for o in ordres:
        cle = (o["date"], o["account_id"], o["fund_id"])
        flux_ordres[cle] = flux_ordres.get(cle, 0) + round(o["units"] * 1000) * (1 if o["side"] == "BUY" else -1)
    pos: dict[tuple[dt.date, str], dict[str, dict]] = {}
    for p in t["positions_daily"]:
        pos.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p
    val = {(v["date"], v["account_id"]): v for v in t["account_values_daily"]}
    tenues: dict[tuple[str, str], int] = {}
    for j in jours:
        for a, c in comptes.items():
            ouvert = c["opened_at"] <= j and (c["closed_at"] is None or j < c["closed_at"])
            for f in fonds:
                d = flux_ordres.get((j, a, f), 0)
                if d:
                    tenues[(a, f)] = tenues.get((a, f), 0) + d
            if not ouvert:
                if (j, a) in val or (j, a) in pos:
                    erreurs.append(f"{a} : valeur le {j}, hors de la vie du compte")
                continue
            lignes = pos.get((j, a), {})
            attendu = {f: u for (b, f), u in tenues.items() if b == a and u != 0}
            if any(u < 0 for u in attendu.values()):
                erreurs.append(f"{a} le {j} : parts négatives")
            if {f: round(p["units"] * 1000) for f, p in lignes.items()} != attendu:
                erreurs.append(f"{a} le {j} : positions ≠ cumul des ordres")
            investi = 0.0
            for f, p in lignes.items():
                if abs(p["market_value_cad"] - round(p["units"] * vl[(f, j)], 2)) > RESIDU_CENT + 1e-9:
                    erreurs.append(f"{a} {f} le {j} : valeur {p['market_value_cad']} ≠ parts × VL")
                investi += p["market_value_cad"]
            v = val.get((j, a))
            if v is None or v["cash_cad"] != 0 or abs(v["invested_value_cad"] - investi) > 0.005 \
                    or abs(v["total_value_cad"] - v["invested_value_cad"] - v["cash_cad"]) > 0.005:
                erreurs.append(f"{a} le {j} : valeur du compte absente ou ≠ Σ positions + encaisse nulle")
    check("grand_livre_positions", erreurs, f"{len(t['positions_daily'])} positions : parts = cumul des ordres, jamais "
          f"négatives, valeur = parts × VL au cent ; {len(val)} valeurs de compte = Σ positions, encaisse nulle")
    return res, []


TOLERANCE_TWR = 1e-9                     # rendements exportés à 10 décimales
MOTIFS_MWR = {"ok", "aucun changement de signe", "plusieurs racines", "non convergé"}


def controler_performance(cfg: Config, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    def c(x: float) -> int:
        return round(x * 100)

    # Entités attendues et leurs jours : ceux où au moins un de leurs comptes a une valeur
    comptes = {a["account_id"]: a["institution_id"] for a in t["accounts"]}
    membres = {("portfolio", "PORTFOLIO"): set(comptes)}
    for a, i in comptes.items():
        membres.setdefault(("institution", i), set()).add(a)
        membres[("account", a)] = {a}
    val: dict[tuple[dt.date, str], int] = {(v["date"], v["account_id"]): c(v["total_value_cad"]) for v in t["account_values_daily"]}
    flux: dict[tuple[dt.date, str], list[int]] = {}
    for m in t["external_movements"]:
        x = flux.setdefault((m["date"], m["account_id"]), [0, 0])
        x[m["movement_type"] == "FRAIS"] += c(m["amount_cad"])

    # Grain, agrégats et flux de performance_daily
    perf = t["performance_daily"]
    erreurs = [] if len({(l["date"], l["entity_type"], l["entity_id"]) for l in perf}) == len(perf) else \
        ["performance_daily : clés en double"]
    par_entite: dict[tuple[str, str], list[dict]] = {}
    for l in perf:
        par_entite.setdefault((l["entity_type"], l["entity_id"]), []).append(l)
    if set(par_entite) != set(membres):
        erreurs.append(f"entités {sorted(set(par_entite) ^ set(membres))} absentes ou inconnues")
    for e, lignes in par_entite.items():
        if e not in membres:
            continue
        jours = sorted({d for d, a in val if a in membres[e]})
        if [l["date"] for l in lignes] != jours:
            erreurs.append(f"{e[1]} : jours ≠ jours où un de ses comptes est ouvert")
            continue
        for l in lignes:
            ouverts = [a for a in membres[e] if (l["date"], a) in val]
            attendu = (sum(val[(l["date"], a)] for a in ouverts), sum(flux.get((l["date"], a), (0, 0))[0] for a in ouverts),
                       sum(flux.get((l["date"], a), (0, 0))[1] for a in ouverts))
            if (c(l["market_value_cad"]), c(l["net_external_flow_cad"]), c(l["fees_cad"])) != attendu:
                erreurs.append(f"{e[1]} le {l['date']} : valeur, flux ou frais ≠ Σ des comptes")
    check("performance_grain", erreurs, f"{len(perf)} lignes, {len(par_entite)} entités (portefeuille, "
          f"{sum(1 for e in par_entite if e[0] == 'institution')} institutions, {sum(1 for e in par_entite if e[0] == 'account')} "
          "comptes) : un jour par jour d'ouverture, valeur = Σ des comptes, flux sans FRAIS, FRAIS à part")

    # TWR quotidien et cumulé recalculés
    erreurs, n = [], 0
    for e, lignes in par_entite.items():
        veille, cumul = 0, 1.0
        for l in lignes:
            r = None if veille == 0 else (c(l["market_value_cad"]) - c(l["net_external_flow_cad"])) / veille - 1
            if r is not None:
                cumul *= 1 + r
                n += 1
            if (r is None) != (l["daily_twr"] is None) or (r is not None and abs(r - l["daily_twr"]) > TOLERANCE_TWR) \
                    or abs(cumul - 1 - l["cumulative_twr"]) > TOLERANCE_TWR:
                erreurs.append(f"{e[1]} le {l['date']} : TWR {l['daily_twr']} / {l['cumulative_twr']} ≠ recalcul {r} / {cumul - 1}")
            veille = c(l["market_value_cad"])
    check("performance_twr", erreurs, f"{n} rendements quotidiens = (V⁺ − flux) ÷ V⁺ de la veille − 1 et TWR cumulés, "
          f"à {TOLERANCE_TWR:g} près ; vides le jour qui suit une valeur nulle")

    # Périodes : couverture, identité au cent, TWR = produit des rendements, MWR vide ⇔ motif
    erreurs = []
    periodes = t["performance_periods"]
    for e, lignes in par_entite.items():
        attendues = [str(a) for a in sorted({l["date"].year for l in lignes})] + ["inception"]
        obtenues = [p for p in periodes if (p["entity_type"], p["entity_id"]) == e]
        if [p["period"] for p in obtenues] != attendues:
            erreurs.append(f"{e[1]} : périodes {[p['period'] for p in obtenues]} ≠ {attendues}")
            continue
        for p in obtenues:
            dedans = [l for l in lignes if p["period"] == "inception" or l["date"].year == int(p["period"])]
            avant = [l for l in lignes if l["date"] < dedans[0]["date"]]
            rs = [l["daily_twr"] for l in dedans if l["daily_twr"] is not None]
            twr = math.prod(1 + r for r in rs) - 1 if rs else None
            if c(p["start_value_cad"]) != (c(avant[-1]["market_value_cad"]) if avant else 0) \
                    or c(p["end_value_cad"]) != c(dedans[-1]["market_value_cad"]) \
                    or c(p["contributions_cad"]) - c(p["withdrawals_cad"]) != sum(c(l["net_external_flow_cad"]) for l in dedans) \
                    or c(p["fees_cad"]) != sum(c(l["fees_cad"]) for l in dedans):
                erreurs.append(f"{e[1]} {p['period']} : valeurs ou flux ≠ performance_daily")
            if c(p["end_value_cad"]) != c(p["start_value_cad"]) + c(p["contributions_cad"]) - c(p["withdrawals_cad"]) \
                    + c(p["fees_cad"]) + c(p["investment_result_cad"]):
                erreurs.append(f"{e[1]} {p['period']} : fin ≠ début + apports − retraits + frais + résultat")
            if (twr is None) != (p["twr"] is None) or (twr is not None and abs(twr - p["twr"]) > 10 * TOLERANCE_TWR):
                erreurs.append(f"{e[1]} {p['period']} : TWR {p['twr']} ≠ Π(1 + r) − 1 = {twr}")
            if p["mwr_status"] not in MOTIFS_MWR or (p["mwr"] is None) != (p["mwr_status"] != "ok") \
                    or p["mwr_annualized"] != (p["days"] >= cfg.performance["annualize_min_days"]):
                erreurs.append(f"{e[1]} {p['period']} : MWR {p['mwr']} ({p['mwr_status']}, annualisé {p['mwr_annualized']})")
    vides = sum(1 for p in periodes if p["mwr"] is None)
    check("performance_periodes", erreurs, f"{len(periodes)} périodes (années civiles et depuis l'ouverture) : fin = début + "
          f"apports − retraits + frais + résultat au cent, TWR = Π(1 + r) − 1 ; {vides} MWR vides, chacun avec son motif")

    # Contrefactuels : mêmes jours et mêmes flux que l'entité, repères connus
    erreurs = []
    cf = t["counterfactual_daily"]
    if len({(l["date"], l["entity_type"], l["entity_id"], l["benchmark_id"]) for l in cf}) != len(cf):
        erreurs.append("counterfactual_daily : clés en double")
    connus = {b["benchmark_id"] for b in t["benchmarks"]}
    series_cf: dict[tuple[str, str, str], list[dict]] = {}
    for l in cf:
        series_cf.setdefault((l["entity_type"], l["entity_id"], l["benchmark_id"]), []).append(l)
    attendus = {("portfolio", "PORTFOLIO", b) for b in ("R-POL",) + tuple(cfg.performance["context_benchmarks"])}
    attendus |= {("institution", i, f"R-POL-{i}") for _, i in (e for e in membres if e[0] == "institution")}
    if set(series_cf) != attendus:
        erreurs.append(f"contrefactuels {sorted(set(series_cf) ^ attendus)} absents ou inattendus")
    for (typ, ident, b), lignes in series_cf.items():
        if b != "R-POL" and b not in connus:
            erreurs.append(f"{b} : repère inconnu")
        reel = [(l["date"], l["net_external_flow_cad"]) for l in par_entite.get((typ, ident), [])]
        if [(l["date"], l["net_external_flow_cad"]) for l in lignes] != reel:
            erreurs.append(f"{ident} × {b} : calendrier de flux ≠ celui de l'entité")
        if any(l["market_value_cad"] < 0 for l in lignes):
            erreurs.append(f"{ident} × {b} : valeur négative")
    check("performance_contrefactuel", erreurs, f"{len(series_cf)} contrefactuels, {len(cf)} lignes : mêmes jours et mêmes "
          "flux externes que leur entité, sans FRAIS de compte ; repères de politique et de contexte connus")
    return res, []


# Clés primaires des tables de finance_ve01 (sql/schema.sql)
CLES_ADAPTATEUR = {
    "ref.compte": ("alias",), "ref.nature": ("motif",), "ref.parametre": ("cle",), "ref.reer_avis": ("annee_deduction",),
    "ref.risque": ("libelle",), "ref.geographie": ("libelle",), "ref.style": ("type", "cle"), "ref.fonds": ("code_fa",),
    "ref.symbole": ("code_fa",), "ref.repere": ("code_fa", "indice"), "pub.profil": ("code_fa", "date_donnees"),
    "pub.profil_code": ("code_fonds",), "pub.profil_ligne": ("code_fa", "date_donnees", "section", "ordre"),
    "pub.rapport_annuel": ("code_fa", "exercice"), "pub.cours": ("symbole", "date_seance"),
    "fait.historique": ("compte_alias",), "fait.transaction": ("compte_alias", "rang"),
    "fait.sommaire": ("compte_alias", "date_valorisation", "code_fonds"),
}


def controler_adaptateur(cfg: Config, dossier: Path, t: dict[str, list[dict]]) -> tuple[list[Resultat], list[str]]:
    """Fichiers de finance_ve01/ : présence et en-têtes, clés, références, chaîne des parts, prix et distributions."""
    from .adapter import TABLES, lire
    res: list[Resultat] = []

    def check(nom: str, erreurs: list[str], ok: str) -> None:
        res.append(Resultat(nom, "fail" if erreurs else "pass", "; ".join(erreurs[:10]) if erreurs else ok))

    f = {n: lire(dossier, n) for n in TABLES}
    dist = lire(dossier, "distributions")
    check("adaptateur_fichiers", [], f"{len(f)} tables et distributions.csv relues, en-têtes conformes, "
          f"{sum(len(x) for x in f.values())} lignes")
    erreurs = []
    for n, cle in CLES_ADAPTATEUR.items():
        vus = [tuple(l[c] for c in cle) for l in f[n]]
        if len(set(vus)) != len(vus):
            erreurs.append(f"{n} : clés en double")
    check("adaptateur_cles", erreurs, f"{len(CLES_ADAPTATEUR)} clés primaires uniques")

    comptes = {l["alias"] for l in f["ref.compte"]}
    fonds = {l["code_fa"] for l in f["ref.fonds"]}
    symboles = {l["symbole"] for l in f["pub.cours"]}
    profils = {(l["code_fa"], l["date_donnees"]) for l in f["pub.profil"]}
    codes = {l["code_fonds"] for l in f["pub.profil_code"]}
    erreurs = []
    for nom, orphelins in (
            ("fait.historique → ref.compte", [l for l in f["fait.historique"] if l["compte_alias"] not in comptes]),
            ("fait.transaction → fait.historique", [l for l in f["fait.transaction"]
                                                    if l["compte_alias"] not in {h["compte_alias"] for h in f["fait.historique"]}]),
            ("fait.transaction → pub.profil_code", [l for l in f["fait.transaction"] if l["code_fonds"] not in codes]),
            ("fait.sommaire → ref.compte", [l for l in f["fait.sommaire"] if l["compte_alias"] not in comptes]),
            ("pub.profil_ligne → pub.profil", [l for l in f["pub.profil_ligne"] if (l["code_fa"], l["date_donnees"]) not in profils]),
            ("pub.profil_code → ref.fonds", [l for l in f["pub.profil_code"] if l["code_fa"] not in fonds]),
            ("ref.symbole → pub.cours", [l for l in f["ref.symbole"] if l["symbole"] not in symboles]),
            ("ref.repere → pub.cours", [l for l in f["ref.repere"] if l["symbole"] not in symboles]),
            ("comptes du générateur → ref.compte", [a for a in t["accounts"] if a["account_alias"] not in comptes])):
        if orphelins:
            erreurs.append(f"{nom} : {len(orphelins)} orphelin(s)")
    check("adaptateur_references", erreurs, "aucune référence orpheline")

    erreurs, parts = [], {}
    for l in f["fait.transaction"]:
        cle = (l["compte_alias"], l["code_fonds"])
        attendu = round(parts.get(cle, 0.0) + l["signe"] * l["parts_negociees"], 3)
        if abs(attendu - l["parts_restantes"]) > 1e-9 or l["parts_restantes"] < 0 or l["montant_brut"] < 0:
            erreurs.append(f"{cle} rang {l['rang']}")
        parts[cle] = l["parts_restantes"]
    revenus = sum(1 for l in f["fait.transaction"] if l["nature"] == "revenu")
    if len(f["fait.transaction"]) != len(t["internal_trades"]) + revenus:
        erreurs.append(f"{len(f['fait.transaction'])} transactions ≠ {len(t['internal_trades'])} ordres + {revenus} réinvestissements")
    check("adaptateur_parts", erreurs, f"{len(f['fait.transaction'])} transactions = {len(t['internal_trades'])} ordres + "
          f"{revenus} réinvestissements ; parts restantes = précédentes ± négociées, jamais négatives")

    fin = max(p["date"] for p in t["positions_daily"])
    detenues = {(p["account_id"], p["fund_id"]) for p in t["positions_daily"] if p["date"] == fin and p["units"] > 0}
    erreurs = [] if len(f["fait.sommaire"]) == len(detenues) else [f"{len(f['fait.sommaire'])} lignes ≠ {len(detenues)} positions"]
    check("adaptateur_sommaire", erreurs, f"{len(detenues)} positions non nulles à l'arrêté {fin}")

    erreurs = [f"{l['symbole']} {l['date_seance']} : clôture {l['cloture']}" for l in f["pub.cours"] if l["cloture"] <= 0]
    erreurs += [f"{d['fund_id']} {d['date']} : taux {d['rate']}" for d in dist if not 0 < d["rate"] < 1]
    erreurs += [f"{d['fund_id']} {d['date']} : distribution négative" for d in dist
                if d["per_unit_income"] < 0 or d["per_unit_capital_gain"] < 0]
    check("adaptateur_prix_distributions", erreurs, f"{len(f['pub.cours'])} cours > 0 ; {len(dist)} versements, "
          f"taux dans ]0, 1[, distributions ≥ 0")
    return res, []


def valider(dossier: Path) -> dict:
    try:
        manifest, cfg, tables = charger_export(dossier)
        resultats, alertes = controler(manifest, cfg, tables)
        if "markets" in manifest["stages"]:
            r_marche, a_marche = controler_marches(cfg, tables)
            resultats, alertes = resultats + r_marche, alertes + a_marche
        if "behaviour" in manifest["stages"]:
            r_comp, a_comp = controler_comportement(cfg, tables)
            resultats, alertes = resultats + r_comp, alertes + a_comp
        if "ledger" in manifest["stages"]:
            r_gl, a_gl = controler_grand_livre(cfg, tables)
            resultats, alertes = resultats + r_gl, alertes + a_gl
        if "performance" in manifest["stages"]:
            r_pf, a_pf = controler_performance(cfg, tables)
            resultats, alertes = resultats + r_pf, alertes + a_pf
        if "adapter" in manifest["stages"]:
            r_ad, a_ad = controler_adaptateur(cfg, dossier, tables)
            resultats, alertes = resultats + r_ad, alertes + a_ad
    except (ValueError, KeyError, FileNotFoundError) as e:
        resultats, alertes = [Resultat("lecture_export", "fail", f"{type(e).__name__} : {e}")], []
    rapport = dict(path=str(dossier), passed=all(r.status == "pass" for r in resultats),
                   checks=[asdict(r) for r in resultats], warnings=alertes)
    (dossier / "validation.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rapport
