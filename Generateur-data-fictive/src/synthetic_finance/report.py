"""Rapports lisibles, écrits depuis les CSV exportés : univers (universe_report.md), marchés
(market_report.md), comportement (behaviour_report.md), grand livre (ledger_report.md) et rendements
(performance_report.md)."""
import datetime as dt
from pathlib import Path

from . import AVERTISSEMENT
from .benchmarks import categorie_du_fonds
from .ledger import ecart
from .performance import OUVERTURE, POLITIQUES, PORTEFEUILLE, ecarts_politique
from .validation import (charger_export, controler, controler_comportement, controler_grand_livre, controler_marches,
                         controler_performance, correlation, equity_share, politique_actions, rendements_annuels,
                         repli_max, series, volatilite)

PROFIL_FR = {"prudent": "prudent", "balanced": "intermédiaire", "growth": "dynamique"}
AXES_FR = {"asset_class": "Classe d'actifs", "geography": "Géographie", "style": "Style"}


def _pct(x: float) -> str:
    return f"{x:.1f} %".replace(".", ",")


def _dec(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _exposition_ponderee(tables: dict, institution_id: str, axe: str) -> dict[str, float]:
    """Exposition de la politique d'une institution sur un axe : Σ poids cible × poids du fonds."""
    cible = {l["fund_id"]: l["target_weight"] / 100 for l in tables["allocation_targets_history"]
             if l["level"] == "institution" and l["institution_id"] == institution_id}
    sortie: dict[str, float] = {}
    for l in tables["fund_exposures_by_axis"]:
        if l["axis"] == axe and l["fund_id"] in cible:
            sortie[l["category"]] = sortie.get(l["category"], 0) + cible[l["fund_id"]] * l["weight"]
    return dict(sorted(sortie.items(), key=lambda kv: -kv[1]))


def ecrire_rapport(dossier: Path) -> Path:
    manifest, cfg, t = charger_export(dossier)
    resultats, alertes = controler(manifest, cfg, t)
    eq_fonds, eq_pol = equity_share(t), politique_actions(t)
    noms = {i["institution_id"]: i["name"] for i in t["institutions"]}
    alias = {c["account_id"]: c["account_alias"] for c in t["accounts"]}
    L = [f"# Univers synthétique — {manifest['scenario_id']}", "",
         f"> {AVERTISSEMENT}", "",
         f"Graine {manifest['seed']}, empreinte de configuration `{manifest['config_hash'][:16]}…`, "
         f"horizon {manifest['period']['start']} → {manifest['period']['end']}, version {manifest['version']}.", "",
         "## Institutions", "",
         "| Institution | Profil visé | Ouverture | Raison du choix | Appétit tiré (actions) | Poids d'épargne a priori "
         "| Fonds | Part en actions de la politique |",
         "|---|---|---|---|---:|---:|---:|---:|"]
    for i in t["institutions"]:
        n = sum(1 for f in t["funds"] if f["institution_id"] == i["institution_id"])
        L.append(f"| {i['name']} | {PROFIL_FR[i['strategy_profile']]} | {i['opened_at']} | {i['choice_reason']} "
                 f"| {_pct(i['risk_appetite'] * 100)} | {_pct(i['savings_weight_prior'] * 100)} | {n} "
                 f"| **{_pct(eq_pol[i['institution_id']] * 100)}** |")
    suite = sorted(t["institutions"], key=lambda i: ("prudent", "balanced", "growth").index(i["strategy_profile"]))
    parts = [eq_pol[i["institution_id"]] * 100 for i in suite]
    ordonnee = all(a < b for a, b in zip(parts, parts[1:]))
    rondes = [i["name"] for i, x in zip(suite, parts) if abs(x / 5 - round(x / 5)) < 1e-6]
    L += ["", "**Lecture des profils** : part en actions " + " < ".join(
        f"{PROFIL_FR[i['strategy_profile']]} {_pct(x)}" for i, x in zip(suite, parts))
          + f" — ordre {'respecté' if ordonnee else 'NON respecté'} ; "
          + (f"multiple de 5 % : {', '.join(rondes)}." if rondes else "aucune part sur un multiple de 5 %.")]
    L += ["", "Part en actions de la politique = Σ (poids cible du fonds × part en actions effective du fonds). "
          "L'appétit est la variable latente tirée ; la part réalisée en diffère, par la gamme disponible et "
          "l'arrondi humain des cibles à 5 %.", ""]
    for i in t["institutions"]:
        L += [f"### {i['name']} — expositions de la politique", ""]
        for axe in ("asset_class", "geography", "style"):
            e = _exposition_ponderee(t, i["institution_id"], axe)
            L.append(f"- {AXES_FR[axe]} : " + ", ".join(f"{k} {_pct(v)}" for k, v in e.items()))
        cible = [l for l in t["allocation_targets_history"] if l["level"] == "institution"
                 and l["institution_id"] == i["institution_id"]]
        L.append("- Cible : " + ", ".join(f"{l['fund_id']} {l['target_weight']:.0f} %" for l in cible))
        L.append("")
    L += ["## Comptes", "", "| Compte | Alias | Régime | Institution | Ouverture | Allocation cible à l'ouverture |",
          "|---|---|---|---|---|---|"]
    for c in t["accounts"]:
        cible = [l for l in t["allocation_targets_history"] if l["account_id"] == c["account_id"]
                 and l["effective_date"] == c["opened_at"]]   # les révisions (J3) sont dans behaviour_report.md
        L.append(f"| {c['account_id']} | {c['account_alias']} | {c['regime']} | {noms[c['institution_id']]} "
                 f"| {c['opened_at']} | " + ", ".join(f"{l['fund_id']} {l['target_weight']:.0f} %" for l in cible) + " |")
    L += ["", "## Fonds", "",
          "| Fonds | Nom | Lancement | Actions | Risque (indication) | RFG | Frais de compte < / ≥ palier "
          "| Exposition aux devises | Distribution |",
          "|---|---|---|---:|---|---:|---:|---:|---|"]
    for f in t["funds"]:
        L.append(f"| {f['fund_id']} | {f['fund_name']} | {f['inception_date']} | {_pct(eq_fonds[f['fund_id']] * 100)} "
                 f"| {f['risk_profile_hint']} | {_dec(f['mer_pct'])} % | {_dec(f['account_fee_low_pct'])} / "
                 f"{_dec(f['account_fee_high_pct'])} % | {_pct(f['fx_exposure_pct'])} | {f['distribution_frequency']} |")
    L += ["", "## Contrôles", "", "| Contrôle | Statut | Détail |", "|---|---|---|"]
    L += [f"| {r.name} | {r.status} | {r.detail} |" for r in resultats]
    L += ["", "## Diagnostics", ""]
    L += [f"- {a}" for a in alertes] or ["- Aucune anomalie détectée."]
    if alias:
        L += ["", f"{len(alias)} comptes, {len(t['funds'])} fonds, {len(t['fund_exposures'])} cellules d'exposition."]
    chemin = dossier / "universe_report.md"
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin


# ------------------------------------------------------------------------------------------------
# Rapport de marché (J2)
# ------------------------------------------------------------------------------------------------
REGIME_FR = {"expansion": "expansion", "ralentissement": "ralentissement", "crise": "crise", "reprise": "reprise"}


def _signe(x: float) -> str:
    return f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def _corr(x: float) -> str:
    return f"{x:.2f}".replace(".", ",").replace("-", "−")


def _ligne_serie(libelle: str, dates, valeurs, annees: list[int], extra: str = "") -> str:
    par_annee = rendements_annuels(dates, valeurs)
    cellules = []
    for a in annees:
        if a not in par_annee:
            cellules.append("—")
        else:
            r, complete = par_annee[a]
            cellules.append(_signe(r) + ("" if complete else " *"))
    n = len(valeurs) - 1
    annualise = (valeurs[-1] / valeurs[0]) ** (252 / n) - 1 if n > 0 else 0.0
    return (f"| {libelle} | {dates[0]} | " + " | ".join(cellules) + f" | {_signe(annualise)} "
            f"| {_pct(volatilite(valeurs) * 100)} | {_signe(repli_max(valeurs))} |" + extra)


def ecrire_rapport_marche(dossier: Path) -> Path:
    manifest, cfg, t = charger_export(dossier)
    resultats, alertes = controler_marches(cfg, t)
    vl = series(t["fund_prices_daily"], "fund_id", "nav_total_return")
    ind = series(t["benchmarks_daily"], "benchmark_id", "index_total_return")
    fonds = {f["fund_id"]: f for f in t["funds"]}
    noms = {i["institution_id"]: i["name"] for i in t["institutions"]}
    profil = {i["institution_id"]: PROFIL_FR[i["strategy_profile"]] for i in t["institutions"]}
    reperes = {b["benchmark_id"]: b for b in t["benchmarks"]}
    jours = [l["date"] for l in t["market_regimes_daily"]]
    annees = sorted({d.year for d in jours})
    entete = "| " + " | ".join(str(a) for a in annees) + " | Annualisé | Volatilité | Repli max |"
    sep = "|---|---|" + "---:|" * (len(annees) + 3)

    L = [f"# Marchés synthétiques — {manifest['scenario_id']}", "", f"> {AVERTISSEMENT}", "",
         f"Graine {manifest['seed']}, horizon {jours[0]} → {jours[-1]} ({len(jours)} jours ouvrables, lundi à vendredi, "
         "fériés non modélisés). VL en rendement total (distributions réinvesties), en CAD ; repères base 100.", "",
         "Modèle : facteurs latents (actions par région, taux Canada et reste du monde, pente, crédit, change "
         "USD/CAD, styles, actifs réels), régimes tirés d'une chaîne de Markov, variance commune GARCH(1,1), "
         "chocs Student-t et sauts rares des deux signes. Aucune date ni aucun rendement annuel n'est imposé : "
         + ("la trajectoire ci-dessous est celle que la graine a tirée, retenue sans sélection." if cfg.market_seed is None
            else f"la trajectoire ci-dessous est celle de la graine de marché {cfg.market_seed}, retenue parmi les graines "
                 "1 à 50 sur un critère de TWR global écrit d'avance (scénario vitrine, "
                 "`scripts/choisir_graine_marche.py`) : marché favorable choisi, non tiré au hasard."), "",
         "## Régimes", ""]
    periodes, debut = [], 0
    regs = [l["regime"] for l in t["market_regimes_daily"]]
    for k in range(1, len(regs) + 1):
        if k == len(regs) or regs[k] != regs[debut]:
            periodes.append((jours[debut], jours[k - 1], regs[debut], k - debut))
            debut = k
    L += ["| Début | Fin | Régime | Jours ouvrables |", "|---|---|---|---:|"]
    L += [f"| {a} | {b} | {REGIME_FR.get(r, r)} | {n} |" for a, b, r, n in periodes]
    parts = {r: sum(1 for x in regs if x == r) / len(regs) for r in dict.fromkeys(regs)}
    L += ["", "Temps passé : " + ", ".join(f"{REGIME_FR.get(r, r)} {_pct(p * 100)}" for r, p in parts.items()) + ".", ""]

    L += ["## Fonds", "", r"\* année incomplète (début de l'horizon, lancement du fonds ou fin de l'horizon). "
          "Écart au composite = rendement annualisé du fonds − celui de son repère composite passif, sur les mêmes "
          "jours : il cumule l'alpha tiré, le bruit propre et l'écart de frais (RFG − frais passifs). Écart à la "
          "catégorie = même calcul contre le repère de catégorie (repère du fonds dans le rapport) : il ajoute l'écart "
          "de composition (style, géographie, part d'actions).", "",
          "| Fonds | Début " + entete + " Écart au composite | Écart à la catégorie |", sep + "---:|---:|"]
    for k in sorted(vl):
        f = fonds[k]
        d, v = vl[k]
        dc, vc = ind[f"R-{k}"]
        vc = vc[dc.index(d[0]):]
        n = len(v) - 1
        ecart = (v[-1] / v[0]) ** (252 / n) - (vc[-1] / vc[0]) ** (252 / n) if n > 0 else 0.0
        dk, vk = ind[categorie_du_fonds(cfg, f["archetype"])]
        vk = vk[dk.index(d[0]):]
        ecart_cat = (v[-1] / v[0]) ** (252 / n) - (vk[-1] / vk[0]) ** (252 / n) if n > 0 else 0.0
        libelle = f"{k} {cfg.archetypes[f['archetype']].label} ({noms[f['institution_id']]})"
        L.append(_ligne_serie(libelle, d, v, annees, f" {_signe(ecart)} | {_signe(ecart_cat)} |"))
    L += ["", "## Repères", "", "| Repère | Début " + entete, sep]
    for typ in ("policy", "sensitivity", "category", "composite"):
        for k in sorted(b for b in reperes if reperes[b]["benchmark_type"] == typ):
            b = reperes[k]
            libelle = b["benchmark_name"].replace(" (fictif)", "")
            if typ == "policy":
                libelle = f"Politique {noms[b['institution_id']]} ({profil[b['institution_id']]})"
            d, v = ind[k]
            L.append(_ligne_serie(f"{k} — {libelle}", d, v, annees))
    L += ["", "Frais passifs et composition :", ""]
    L += [f"- {k} : {_dec(reperes[k]['passive_fee_pct'])} % par an — {reperes[k]['composition']}"
          for k in reperes if reperes[k]["benchmark_type"] != "composite"]
    L += ["- Composites : frais passifs de "
          + ", ".join(f"{_dec(reperes[k]['passive_fee_pct'])} % ({reperes[k]['fund_id']})"
                      for k in reperes if reperes[k]["benchmark_type"] == "composite") + "."]

    cles = sorted(vl) + [k for k in reperes if reperes[k]["benchmark_type"] != "composite"]
    toutes = {**vl, **{k: ind[k] for k in cles if k in ind}}
    L += ["", "## Corrélations des rendements journaliers", "",
          "Sur les jours communs aux deux séries. Fonds, puis politiques et repères de contexte.", "",
          "| | " + " | ".join(cles) + " |", "|---|" + "---:|" * len(cles)]
    for a in cles:
        L.append(f"| {a} | " + " | ".join("1" if a == b else _corr(correlation(toutes[a], toutes[b])) for b in cles) + " |")
    L += ["", "## Contrôles", "", "| Contrôle | Statut | Détail |", "|---|---|---|"]
    L += [f"| {r.name} | {r.status} | {r.detail} |" for r in resultats]
    L += ["", "## Diagnostics", ""]
    L += [f"- {a}" for a in alertes] or ["- Aucune anomalie détectée."]
    chemin = dossier / "market_report.md"
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin


# ------------------------------------------------------------------------------------------------
# Rapport de comportement (J3)
# ------------------------------------------------------------------------------------------------
MOIS_FR = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
TYPES_EVENEMENT_FR = {
    "ouverture_compte": "ouverture de compte", "phase_epargne": "phase d'épargne", "ajustement_pac": "ajustement de PAC",
    "revue_annuelle": "revue annuelle", "ajout_fonds": "ajout d'un fonds", "prudence_marche": "prudence après une baisse",
    "retour_cible": "retour à la cible", "mois_atypique": "mois atypique", "pause_pac": "pause de PAC",
    "prime": "ponctuel : prime", "argent_disponible": "ponctuel : argent disponible", "cadeau": "ponctuel : cadeau",
    "remboursement_impot": "ponctuel : remboursement d'impôt", "depense_imprevue": "dépense imprévue",
    "plafond_atteint": "plafond de droits atteint",
    "ponctuel_impose": "ponctuel imposé (cas d'usage)", "reequilibrage": "rééquilibrage"}


def _cad(x: float) -> str:
    return f"{x:,.0f}".replace(",", "\u202f").replace("-", "−") + " $"


def ecrire_rapport_comportement(dossier: Path) -> Path:
    manifest, cfg, t = charger_export(dossier)
    resultats, alertes = controler_comportement(cfg, t)
    comptes = {c["account_id"]: c for c in t["accounts"]}
    noms = {i["institution_id"]: i["name"] for i in t["institutions"]}
    mvts = [m for m in t["external_movements"] if m["movement_type"] != "FRAIS"]   # FRAIS : ledger_report.md
    evs = [e for e in t["events"] if e["event_type"] != "reequilibrage"]
    persona = t["persona"]

    L = [f"# Comportement de l'épargnant — {manifest['scenario_id']}", "", f"> {AVERTISSEMENT}", "",
         f"Graine {manifest['seed']}, horizon {cfg.start_date} → {cfg.end_date}. Flux externes en CAD : `PAC` et "
         "`PONCTUEL` > 0, `RETRAIT` < 0 ; les frais de compte (`FRAIS`) viennent au J4 avec le grand livre.", "",
         "Le moteur tire une capacité d'épargne latente qui ne change qu'à des décisions datées (phases, ouvertures, "
         "ajustements, revues) ; entre deux décisions, le PAC de chaque compte reste constant. Ponctuels, retraits, mois "
         "atypiques et pauses naissent de processus de Poisson ; chacun a son événement dans le journal. Le marché n'est "
         "lu que dans le passé (repli du repère actions mondiales arrêté la veille d'une décision).", ""]

    premiere = min((l["year"] for l in persona if l["celi_eligible"]), default=None)
    revenus = [l for l in persona if l["earned_income_cad"] is not None]
    reer = next((l["reer_unused_end_cad"] for l in persona if l["reer_unused_end_cad"] is not None), None)
    L += ["## Personnage fictif", "",
          f"- Première année d'admissibilité au CELI : {premiere} ; aucun CELI antérieur à l'horizon.",
          "- Revenu gagné : " + ", ".join(f"{l['year']} {_cad(l['earned_income_cad'])}" for l in revenus) + ".",
          f"- Droits REER inutilisés à la fin de {revenus[0]['year'] if revenus else '—'} : {_cad(reer or 0)}.",
          f"- Plafonds : `{manifest.get('inputs', {}).get('tax_limits', {}).get('source', '—')}` "
          f"(SHA-256 `{manifest.get('inputs', {}).get('tax_limits', {}).get('sha256', '—')[:12]}…`), recopiés dans "
          "`tax_limits.csv`.", ""]

    L += ["## Chronologie des événements", "", "| Événement | Date | Type | Compte | Description | Effet |",
          "|---|---|---|---|---|---|"]
    for e in evs:
        compte = comptes[e["account_id"]]["account_alias"] if e["account_id"] else "—"
        L.append(f"| {e['event_id']} | {e['date']} | {TYPES_EVENEMENT_FR.get(e['event_type'], e['event_type'])} | {compte} "
                 f"| {e['description']} | {e['scenario_impact'] or ''} |")

    # PAC total par mois
    pac: dict[tuple[int, int], float] = {}
    for m in mvts:
        if m["movement_type"] == "PAC":
            cle = (m["date"].year, m["date"].month)
            pac[cle] = pac.get(cle, 0.0) + m["amount_cad"]
    premiere_ouverture = min(c["opened_at"] for c in comptes.values())
    mois = [(a, m) for a in range(cfg.start_date.year, cfg.end_date.year + 1) for m in range(1, 13)
            if (premiere_ouverture.year, premiere_ouverture.month) <= (a, m) <= (cfg.end_date.year, cfg.end_date.month)]
    valeurs = sorted(pac.get(k, 0.0) for k in mois)
    mediane = valeurs[len(valeurs) // 2] if len(valeurs) % 2 else (valeurs[len(valeurs) // 2 - 1] + valeurs[len(valeurs) // 2]) / 2
    sans = sum(1 for k in mois if pac.get(k, 0.0) == 0)
    L += ["", "## PAC total, mois par mois", "",
          f"Depuis la première ouverture ({premiere_ouverture}) : médiane {_cad(mediane)} par mois ; {sans} mois sans "
          f"aucun PAC sur {len(mois)} ({_pct(100 * sans / len(mois))}). « 0 » = mois sans PAC.", "",
          "| Année | " + " | ".join(MOIS_FR) + " | Total |", "|---|" + "---:|" * 13]
    for a in sorted({k[0] for k in mois}):
        cellules = [("" if (a, m) not in mois else f"{pac.get((a, m), 0.0):.0f}") for m in range(1, 13)]
        L.append(f"| {a} | " + " | ".join(cellules) + f" | {_cad(sum(pac.get((a, m), 0.0) for m in range(1, 13)))} |")

    # Année × institution × régime
    L += ["", "## Flux par année, institution et régime", "", "| Année | Institution | Régime | PAC | Ponctuels | Retraits |",
          "|---|---|---|---:|---:|---:|"]
    agregat: dict[tuple, dict[str, float]] = {}
    for m in mvts:
        c = comptes[m["account_id"]]
        cle = (m["date"].year, noms[c["institution_id"]], c["regime"])
        agregat.setdefault(cle, dict(PAC=0.0, PONCTUEL=0.0, RETRAIT=0.0))[m["movement_type"]] += m["amount_cad"]
    for (a, inst, regime), v in sorted(agregat.items()):
        L.append(f"| {a} | {inst} | {regime} | {_cad(v['PAC'])} | {_cad(v['PONCTUEL'])} | {_cad(v['RETRAIT'])} |")
    totaux = {k: sum(v[k] for v in agregat.values()) for k in ("PAC", "PONCTUEL", "RETRAIT")}
    parts = {}
    for (a, inst, regime), v in agregat.items():
        parts[inst] = parts.get(inst, 0.0) + v["PAC"]
    L += ["", f"Sur l'horizon : PAC {_cad(totaux['PAC'])}, ponctuels {_cad(totaux['PONCTUEL'])}, retraits "
          f"{_cad(totaux['RETRAIT'])}. Part des PAC par institution : "
          + ", ".join(f"{k} {_pct(100 * v / totaux['PAC'])}" for k, v in sorted(parts.items())) + "."]
    ponctuels = [m["amount_cad"] for m in mvts if m["movement_type"] == "PONCTUEL"]
    if ponctuels:
        L.append(f"Ponctuels : {len(ponctuels)}, de {_cad(min(ponctuels))} à {_cad(max(ponctuels))} ; multiples de 500 $ : "
                 f"{sum(1 for x in ponctuels if abs(x / 500 - round(x / 500)) < 1e-9)} sur {len(ponctuels)}.")

    # Droits
    L += ["", "## Droits de cotisation", "", "Année civile pour le CELI et le CELIAPP, année de déduction pour le REER "
          "(une cotisation de janvier ou février compte pour l'année précédente si sa période n'est pas close).", "",
          "| Régime | Année | Nouveaux droits | Droits au début | Cotisations | Retraits | Droits restants |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for l in t["contribution_room"]:
        L.append(f"| {l['regime']} | {l['year']} | {_cad(l['new_room_cad'])} | {_cad(l['room_start_cad'])} "
                 f"| {_cad(l['contributions_cad'])} | {_cad(l['withdrawals_cad'])} | {_cad(l['room_end_cad'])} |")

    # Cibles
    L += ["", "## Changements de cible des comptes", "", "| Date | Compte | Cible | Événement |", "|---|---|---|---|"]
    ev_cible = {(e["account_id"], e["date"]): e for e in evs
                if e["event_type"] in ("revue_annuelle", "ajout_fonds", "prudence_marche", "retour_cible")}
    groupes: dict[tuple, list] = {}
    for l in t["allocation_targets_history"]:
        if l["level"] == "account":
            groupes.setdefault((l["effective_date"], l["account_id"]), []).append(l)
    for (d, a), lignes in sorted(groupes.items()):
        e = ev_cible.get((a, d))
        cible = ", ".join(f"{l['fund_id']} {l['target_weight']:.0f} %" for l in lignes)
        source = f"{e['event_id']} {TYPES_EVENEMENT_FR[e['event_type']]}" if e else "cible d'ouverture (J1)"
        L.append(f"| {d} | {comptes[a]['account_alias']} | {cible} | {source} |")

    L += ["", "## Contrôles", "", "| Contrôle | Statut | Détail |", "|---|---|---|"]
    L += [f"| {r.name} | {r.status} | {r.detail} |" for r in resultats]
    L += ["", "## Diagnostics", ""]
    L += [f"- {a}" for a in alertes] or ["- Aucune anomalie détectée."]
    chemin = dossier / "behaviour_report.md"
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin


def _nb(x: float, n: int) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def _cad2(x: float) -> str:
    return f"{x:,.2f}".replace(",", "\u202f").replace(".", ",").replace("-", "−") + " $"


def ecrire_rapport_grand_livre(dossier: Path) -> Path:
    manifest, cfg, t = charger_export(dossier)
    resultats, _ = controler_grand_livre(cfg, t)
    comptes = {c["account_id"]: c for c in t["accounts"]}
    noms = {i["institution_id"]: i["name"] for i in t["institutions"]}
    mvts, ordres = t["external_movements"], t["internal_trades"]
    evs = {e["event_id"]: e for e in t["events"]}
    val = {(v["date"], v["account_id"]): v["total_value_cad"] for v in t["account_values_daily"]}
    pos: dict[tuple[dt.date, str], dict[str, dict]] = {}
    for p in t["positions_daily"]:
        pos.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p
    jours = sorted({d for d, _ in val})
    veille = dict(zip(jours[1:], jours))
    inst = {a: c["institution_id"] for a, c in comptes.items()}

    def valeur(j: dt.date, i: str) -> float:
        return sum(v for (d, a), v in val.items() if d == j and inst[a] == i)

    L = [f"# Grand livre — {manifest['scenario_id']}", "", f"> {AVERTISSEMENT}", "",
         f"Graine {manifest['seed']}, horizon {cfg.start_date} → {cfg.end_date}. Chaque apport est investi le jour même à "
         "la VL de clôture (encaisse nulle) : un PAC suit la cible du compte, un ponctuel comble d'abord les fonds "
         "sous-pondérés à la veille, un retrait vend au prorata des valeurs de la veille. Les frais de compte (`FRAIS`) sont "
         "prélevés au dernier jour ouvrable du mois par rachat de parts ; le RFG est déjà dans la VL et n'est pas facturé "
         "une seconde fois. Parts à 3 décimales : le résidu d'arrondi reste dans la valeur.", ""]

    # Année × société
    fins_annee = {}
    for j in jours:
        fins_annee[j.year] = j
    L += ["## Flux et valeur par année et par société", "",
          "Résultat de placement = valeur de fin − valeur de début − apports + retraits + frais (avant frais de compte, "
          "après RFG). Valeur au dernier jour ouvrable de l'année ; la dernière ligne de chaque société est l'arrêté.", "",
          "| Société | Année | Apports | Retraits | Frais | Résultat de placement | Valeur de fin |",
          "|---|---|---:|---:|---:|---:|---:|"]
    totaux = {k: 0.0 for k in ("apports", "retraits", "frais", "resultat")}
    for i in sorted(noms):
        debut = 0.0
        for annee, fin in sorted(fins_annee.items()):
            lignes = [m for m in mvts if inst[m["account_id"]] == i and m["date"].year == annee]
            apports = sum(m["amount_cad"] for m in lignes if m["movement_type"] in ("PAC", "PONCTUEL"))
            retraits = -sum(m["amount_cad"] for m in lignes if m["movement_type"] == "RETRAIT")
            frais = -sum(m["amount_cad"] for m in lignes if m["movement_type"] == "FRAIS")
            v = valeur(fin, i)
            if not (lignes or v or debut):
                continue
            resultat = v - debut - apports + retraits + frais
            for k, x in zip(totaux, (apports, retraits, frais, resultat)):
                totaux[k] += x
            libelle = f"{annee} (arrêté {fin})" if fin == jours[-1] else str(annee)
            L.append(f"| {noms[i]} | {libelle} | {_cad(apports)} | {_cad(retraits)} | {_cad(frais)} | {_cad(resultat)} "
                     f"| {_cad(v)} |")
            debut = v
    total = sum(valeur(jours[-1], i) for i in noms)
    L += ["", f"Patrimoine à l'arrêté : {_cad(total)} = apports {_cad(totaux['apports'])} − retraits "
          f"{_cad(totaux['retraits'])} − frais {_cad(totaux['frais'])} + résultat de placement {_cad(totaux['resultat'])}."]

    # Frais
    seuil = cfg.fee_tier_threshold_cad
    L += ["", "## Frais de compte", "",
          f"Taux annualisé = frais de l'année ÷ moyenne des valeurs de fin de mois × 12 ÷ nombre de mois. Palier : actif du "
          f"ménage chez la société sous {_cad(seuil)} (taux `account_fee_low_pct` des fonds) ou au-delà "
          "(`account_fee_high_pct`).", "", "| Société | Année | Frais | Taux annualisé | Palier à l'arrêté |",
          "|---|---|---:|---:|---|"]
    fins_mois = [j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month]
    for i in sorted(noms):
        palier = "au-delà du palier" if valeur(jours[-1], i) >= seuil else "sous le palier"
        for annee in sorted(fins_annee):
            vm = [valeur(j, i) for j in fins_mois if j.year == annee]
            vm = [x for x in vm if x > 0]
            frais = -sum(m["amount_cad"] for m in mvts if m["movement_type"] == "FRAIS" and inst[m["account_id"]] == i
                         and m["date"].year == annee)
            if not vm:
                continue
            taux = frais / (sum(vm) / len(vm)) * 12 / len(vm)
            L.append(f"| {noms[i]} | {annee} | {_cad2(frais)} | {_pct(100 * taux).replace(' %', '')} % | "
                     f"{palier if annee == jours[-1].year else ''} |")

    # Rééquilibrages
    cibles: dict[str, dict[dt.date, dict[str, float]]] = {}
    for l in t["allocation_targets_history"]:
        if l["level"] == "account":
            cibles.setdefault(l["account_id"], {}).setdefault(l["effective_date"], {})[l["fund_id"]] = l["target_weight"]

    def derive(j: dt.date, a: str, jour_cible: dt.date) -> float:
        """Dérive des positions du jour j par rapport à la cible en vigueur le jour du rééquilibrage."""
        vise = [x for d, x in sorted(cibles[a].items()) if d <= jour_cible][-1]
        return ecart({f: round(p["market_value_cad"] * 100) for f, p in pos.get((j, a), {}).items()}, vise)

    reeq = [e for e in t["events"] if e["event_type"] == "reequilibrage"]
    echanges = {}
    for o in ordres:
        if o["event_id"] and o["side"] == "SELL":
            echanges[o["event_id"]] = echanges.get(o["event_id"], 0.0) + o["gross_amount_cad"]
    L += ["", "## Rééquilibrages", "",
          "Dérive = ½ Σ |poids − cible|, en points : la part de la valeur qu'il faudrait déplacer. « Veille » : ce que la "
          "décision a lu ; « clôture » : après l'échange, aux VL du jour.", "",
          "| Événement | Date | Compte | Cause | Échange | Dérive à la veille | Dérive à la clôture |", "|---|---|---|---|---:|---:|---:|"]
    for e in reeq:
        a = e["account_id"]
        cause = e["description"].split(" : ", 1)[1] if " : " in e["description"] else e["description"].split("(", 1)[1].rstrip(")")
        L.append(f"| {e['event_id']} | {e['date']} | {comptes[a]['account_alias']} | {cause} | {_cad2(echanges.get(e['event_id'], 0))} "
                 f"| {_dec(derive(veille[e['date']], a, e['date']))} | {_dec(derive(e['date'], a, e['date']))} |")
    if not reeq:
        L.append("| — | | | aucun rééquilibrage | | | |")

    # Parcours vérifiables
    def parcours(titre: str, j: dt.date, a: str, lien: str, entete: str) -> None:
        L.extend(["", f"### {titre}", "", entete, "", "| Ordre | Fonds | Sens | Parts | VL | Montant |", "|---|---|---|---:|---:|---:|"])
        for o in ordres:
            if (o["movement_id"] or o["event_id"]) == lien:
                L.append(f"| {o['trade_id']} | {o['fund_id']} | {o['side']} | {_nb(o['units'], 3)} | {_nb(o['unit_price'], 6)} "
                         f"| {_cad2(o['gross_amount_cad'])} |")
        L.extend(["", "| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |",
                  "|---|---:|---:|---:|---:|"])
        avant, apres = pos.get((veille[j], a), {}), pos.get((j, a), {})
        for f in sorted(set(avant) | set(apres)):
            u0 = avant[f]["units"] if f in avant else 0.0
            u1, v1 = (apres[f]["units"], apres[f]["market_value_cad"]) if f in apres else (0.0, 0.0)
            prix = next((l["nav_total_return"] for l in t["fund_prices_daily"] if l["fund_id"] == f and l["date"] == j), 0.0)
            L.append(f"| {f} | {_nb(u0, 3)} | {_nb(u1, 3)} | {_nb(prix, 6)} | {_cad2(v1)} |")
        L.append(f"\nValeur du {comptes[a]['account_alias']} : {_cad2(val.get((veille[j], a), 0.0))} à la clôture du "
                 f"{veille[j]}, {_cad2(val.get((j, a), 0.0))} à la clôture du {j}.")

    L += ["", "## Parcours vérifiables à la main", "",
          "Compte → mouvement → ordres → positions → valeur. Parts de clôture = parts de la veille ± ordres du jour (et "
          "frais si le jour est une fin de mois) ; valeur = parts × VL, arrondie au cent."]
    lies = {}
    for o in ordres:
        lies.setdefault(o["movement_id"] or o["event_id"], []).append(o)
    pac = next((m for m in mvts if m["movement_type"] == "PAC" and len(lies.get(m["movement_id"], [])) >= 2
                and m["date"] in veille and m["date"] not in fins_mois), None)
    retrait = next((m for m in mvts if m["movement_type"] == "RETRAIT" and m["date"] not in fins_mois), None)
    for titre, m in (("Un PAC", pac), ("Un retrait", retrait)):
        if m is None:
            L += ["", f"### {titre}", "", "Aucun dans ce scénario."]
            continue
        parcours(titre, m["date"], m["account_id"], m["movement_id"],
                 f"{m['movement_id']} du {m['date']}, {comptes[m['account_id']]['account_alias']} chez "
                 f"{noms[inst[m['account_id']]]} : {m['movement_type']} de {_cad2(m['amount_cad'])}, événement {m['event_id']} "
                 f"({evs[m['event_id']]['description']}). Autres mouvements du compte ce jour-là : "
                 + (", ".join(x["movement_id"] for x in mvts if x["account_id"] == m["account_id"] and x["date"] == m["date"]
                              and x is not m) or "aucun") + ".")
    e = next((x for x in reeq if x["date"] not in fins_mois and "(100% " not in x["scenario_impact"]),
             next((x for x in reeq if x["date"] not in fins_mois), None))           # un incomplet, de préférence
    if e is None:
        L += ["", "### Un rééquilibrage", "", "Aucun dans ce scénario."]
    else:
        parcours("Un rééquilibrage", e["date"], e["account_id"], e["event_id"],
                 f"{e['event_id']} du {e['date']} : {e['description']} ; {e['scenario_impact']}.")

    L += ["", "## Contrôles", "", "| Contrôle | Statut | Détail |", "|---|---|---|"]
    L += [f"| {r.name} | {r.status} | {r.detail} |" for r in resultats]
    chemin = dossier / "ledger_report.md"
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin


GEO_FR = {"canada": "Canada", "united_states": "États-Unis", "europe": "Europe", "asia_pacific": "Asie-Pacifique",
          "emerging": "Émergents", "other": "Autres régions"}
CLASSE_FR = {"equity": "Actions", "fixed_income": "Obligations", "cash": "Encaisse", "other": "Autres"}


def _taux(x: float | None, n: int = 2) -> str:
    return "—" if x is None else f"{100 * x:+.{n}f} %".replace(".", ",").replace("-", "−")


def ecrire_rapport_performance(dossier: Path) -> Path:
    manifest, cfg, t = charger_export(dossier)
    resultats, _ = controler_performance(cfg, t)
    comptes = {c["account_id"]: c for c in t["accounts"]}
    noms = {i["institution_id"]: i["name"] for i in t["institutions"]}
    nom_entite = {("portfolio", PORTEFEUILLE): "Portefeuille"} | {("institution", i): n for i, n in noms.items()} \
        | {("account", a): c["account_alias"] for a, c in comptes.items()}
    perf: dict[tuple[str, str], list[dict]] = {}
    for l in t["performance_daily"]:
        perf.setdefault((l["entity_type"], l["entity_id"]), []).append(l)
    jour_perf = {(l["entity_type"], l["entity_id"], l["date"]): l for l in t["performance_daily"]}
    cf: dict[tuple[str, str, str], list[dict]] = {}
    for l in t["counterfactual_daily"]:
        cf.setdefault((l["entity_type"], l["entity_id"], l["benchmark_id"]), []).append(l)
    principales = [("portfolio", PORTEFEUILLE)] + [("institution", i) for i in sorted(noms)]
    annualise = cfg.performance["annualize_min_days"] if cfg.performance else 365

    L = [f"# Rendements et repères — {manifest['scenario_id']}", "", f"> {AVERTISSEMENT}", "",
         f"Graine {manifest['seed']}, horizon {cfg.start_date} → {cfg.end_date}. Mesures calculées après la simulation, sur le "
         "seul grand livre. TWR : rₜ = (V⁺ₜ − Fₜ) ÷ V⁺ₜ₋₁ − 1, où V⁺ est la valeur de clôture après flux et F les apports et "
         "retraits du jour (les flux s'exécutent à la VL de clôture) ; les frais de compte (`FRAIS`) ne sont pas des flux, ils "
         "réduisent le rendement. Le TWR d'une société ou du portefeuille se calcule sur les valeurs et flux agrégés. MWR : "
         "taux interne des flux vus de l'épargnant (valeur de début et apports sortent de sa poche, retraits et valeur de fin y "
         f"reviennent), annualisé si la période dure au moins {annualise} jours, sinon taux de la période (marqué « p. »). Une "
         "année civile court de la dernière clôture de l'année précédente à la dernière de l'année : 364 à 368 jours selon le "
         "calendrier.", ""]

    # Tableau entité × période
    L += ["## Rendements par période", "",
          "Résultat de placement = fin − début − apports + retraits + frais de compte : variation de valeur due aux marchés, "
          "nette du RFG (déjà dans la VL) et avant frais de compte, qui figurent à part.", "",
          "| Entité | Période | Début | Apports | Retraits | Frais | Résultat | Fin | TWR | MWR |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    periodes = t["performance_periods"]
    for e in principales:
        for p in (x for x in periodes if (x["entity_type"], x["entity_id"]) == e):
            libelle = "depuis l'ouverture" if p["period"] == OUVERTURE else p["period"]
            mwr = (_taux(p["mwr"]) + ("" if p["mwr_annualized"] else " p.")) if p["mwr"] is not None else f"— ({p['mwr_status']})"
            L.append(f"| {nom_entite[e]} | {libelle} ({p['start_date']} → {p['end_date']}) | {_cad(p['start_value_cad'])} | "
                     f"{_cad(p['contributions_cad'])} | {_cad(p['withdrawals_cad'])} | {_cad(-p['fees_cad'])} | "
                     f"{_cad(p['investment_result_cad'])} | {_cad(p['end_value_cad'])} | {_taux(p['twr'])} | {mwr} |")
    opposes = [p for p in periodes if p["twr"] is not None and p["mwr"] is not None and p["twr"] * p["mwr"] < 0]
    vides = [p for p in periodes if p["mwr"] is None]
    L += ["", f"TWR et MWR de signes opposés : {len(opposes)} période(s) sur {len(periodes)}, comptes compris"
          + (" — " + ", ".join(f"{nom_entite[(p['entity_type'], p['entity_id'])]} {p['period']} (TWR {_taux(p['twr'])}, MWR "
                               f"{_taux(p['mwr'])})" for p in opposes) if opposes else "")
          + f". MWR vides : {len(vides)}" + (" — " + ", ".join(f"{nom_entite[(p['entity_type'], p['entity_id'])]} {p['period']} : "
                                                              f"{p['mwr_status']}" for p in vides) if vides else "") + ".",
          "", "L'écart entre TWR et MWR mesure le calendrier des versements : le TWR neutralise les montants, le MWR pèse "
          "chaque dollar le temps où il est resté placé. Une perte précoce sur un petit encours pèse lourd dans le TWR et peu "
          "dans le MWR."]

    # Consolidation
    fin_ptf = perf[("portfolio", PORTEFEUILLE)][-1]
    instits = [perf[e][-1] for e in principales[1:]]
    simple = sum(l["cumulative_twr"] for l in instits) / len(instits)
    pondere = sum(l["cumulative_twr"] * l["market_value_cad"] for l in instits) / sum(l["market_value_cad"] for l in instits)
    L += ["", "## Consolidation", "",
          f"TWR du portefeuille depuis l'ouverture, calculé sur les valeurs et flux agrégés : {_taux(fin_ptf['cumulative_twr'])}. "
          f"Moyenne simple des TWR des sociétés : {_taux(simple)} ; moyenne pondérée par la valeur à l'arrêté : {_taux(pondere)}. "
          "Ni l'une ni l'autre ne vaut le TWR consolidé : les sociétés n'ouvrent pas aux mêmes dates et leurs poids changent "
          "chaque jour."]

    # Comparaison aux repères
    ecarts = ecarts_politique(t)
    L += ["", "## Comparaison aux repères passifs", "",
          "Contrefactuel : les mêmes apports et retraits, aux mêmes dates, placés dans le repère de politique de la société "
          "(cibles initiales du J1, rééquilibrées chaque jour, frais passifs dans l'indice, aucun frais de compte). TWR "
          "annualisés depuis le premier rendement de la société. Frais nets = RFG moyen pondéré par l'encours + frais de compte "
          "annualisés − frais passifs du repère ; reste = écart + frais nets : alpha des fonds, allocation réelle différente de "
          "la politique, rééquilibrages et dérive.", "",
          "| Société | Depuis | TWR | Politique | Écart | RFG | Frais de compte | Frais passifs | Frais nets | Reste | Valeur | "
          "Contrefactuel |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for x in ecarts:
        L.append(f"| {noms[x['institution_id']]} | {x['debut']} | {_taux(x['twr'] / 100)} | {_taux(x['twr_politique'] / 100)} | "
                 f"{_taux(x['ecart'] / 100)} | {_nb(x['rfg'], 2)} % | {_nb(x['frais_compte'], 2)} % | {_nb(x['frais_passifs'], 2)} % "
                 f"| {_nb(x['frais'], 2)} % | {_taux(x['reste'] / 100)} | {_cad(x['valeur'])} | {_cad(x['valeur_politique'])} |")
    compo = {b["benchmark_id"]: b["composition"].replace(" | ", ", ") for b in t["benchmarks"]} \
        | {POLITIQUES: "somme des trois contrefactuels de politique"}
    L += ["", "Portefeuille contre ses contrefactuels, sur les mêmes jours (TWR cumulé depuis l'ouverture, valeur à l'arrêté) :", "",
          "| Contrefactuel | Composition | TWR cumulé | Valeur à l'arrêté | Réel − contrefactuel |", "|---|---|---:|---:|---:|",
          f"| Réel | — | {_taux(fin_ptf['cumulative_twr'])} | {_cad(fin_ptf['market_value_cad'])} | — |"]
    for (typ, _, b), lignes in sorted(cf.items()):
        if typ == "portfolio":
            L.append(f"| {b} | {compo[b]} | {_taux(lignes[-1]['cumulative_twr'])} | {_cad(lignes[-1]['market_value_cad'])} | "
                     f"{_cad(fin_ptf['market_value_cad'] - lignes[-1]['market_value_cad'])} |")
    gagnants = [noms[x["institution_id"]] for x in ecarts if x["ecart"] > 0]
    L += ["", ("Aucune société ne bat sa politique en TWR net. " if not gagnants
               else f"Bat sa politique en TWR net : {', '.join(gagnants)}. ")
          + "Les frais nets fixent l'écart attendu ; le reste, sur cinq ans ou moins, ne prouve aucun talent : les alpha des "
          "fonds sont tirés autour de zéro, et l'allocation réelle des comptes s'écarte de la politique (cibles des comptes, "
          "révisions du J3, dérive). R-ACT-MONDE et R-EQUILIBRE donnent le contexte ; ils ne sont pas ajustés au risque des "
          "sociétés."]

    # Allocation effective
    expo: dict[tuple[str, str], dict[str, float]] = {}
    for l in t["fund_exposures_by_axis"]:
        if l["axis"] in ("asset_class", "geography"):
            expo.setdefault((l["fund_id"], l["axis"]), {})[l["category"]] = l["weight"] / 100
    jours = sorted({l["date"] for l in t["account_values_daily"]})
    fins: dict[int, dt.date] = {}
    for j in jours:
        fins[j.year] = j
    lignes_pos: dict[tuple[dt.date, str], list[dict]] = {}
    for p in t["positions_daily"]:
        if p["date"] in fins.values():
            lignes_pos.setdefault((p["date"], comptes[p["account_id"]]["institution_id"]), []).append(p)
    L += ["", "## Allocation effective", "",
          "Exposition pondérée par l'encours au dernier jour ouvrable de chaque année et à l'arrêté : Σ valeur de la position "
          "× poids de la catégorie dans le fonds ÷ valeur de la société. Géographie : sur la seule part en actions.", "",
          "| Société | Date | " + " | ".join(CLASSE_FR.values()) + " | " + " | ".join(GEO_FR.values()) + " |",
          "|---|---|" + "---:|" * (len(CLASSE_FR) + len(GEO_FR))]
    for i in sorted(noms):
        for j in sorted(fins.values()):
            lignes = lignes_pos.get((j, i), [])
            total = sum(p["market_value_cad"] for p in lignes)
            if total <= 0:
                continue
            classes = {k: sum(p["market_value_cad"] * expo[(p["fund_id"], "asset_class")].get(k, 0) for p in lignes) / total
                       for k in CLASSE_FR}
            actions = classes["equity"] * total
            geo = {k: sum(p["market_value_cad"] * expo[(p["fund_id"], "asset_class")].get("equity", 0)
                          * expo.get((p["fund_id"], "geography"), {}).get(k, 0) for p in lignes) / actions if actions else 0.0
                   for k in GEO_FR}
            L.append(f"| {noms[i]} | {j} | " + " | ".join(_pct(100 * classes[k]) for k in CLASSE_FR) + " | "
                     + " | ".join(_pct(100 * geo[k]) for k in GEO_FR) + " |")

    # Parcours : l'apport le plus gros relativement à la valeur du compte la veille, hors fin de mois
    fins_mois = {j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month}
    veille = dict(zip(jours[1:], jours))

    def valeur_veille(m: dict) -> float:
        x = jour_perf.get(("account", m["account_id"], veille.get(m["date"])))
        return x["market_value_cad"] if x else 0.0
    candidats = [m for m in t["external_movements"] if m["movement_type"] in ("PAC", "PONCTUEL") and m["date"] not in fins_mois
                 and valeur_veille(m) > 0]
    m = max(candidats, key=lambda x: (x["amount_cad"] / valeur_veille(x), x["movement_id"]))
    a, j, v = m["account_id"], m["date"], veille[m["date"]]
    vl = {(l["fund_id"], l["date"]): l["nav_total_return"] for l in t["fund_prices_daily"] if l["date"] in (v, j)}
    avant = {p["fund_id"]: p["units"] for p in t["positions_daily"] if p["date"] == v and p["account_id"] == a}
    apres = {p["fund_id"]: p["units"] for p in t["positions_daily"] if p["date"] == j and p["account_id"] == a}
    hier, ajd = jour_perf[("account", a, v)], jour_perf[("account", a, j)]
    marche = sum(u * vl[(f, j)] for f, u in avant.items()) / sum(u * vl[(f, v)] for f, u in avant.items()) - 1
    L += ["", "## Parcours vérifiable : un gros apport ne crée pas de rendement", "",
          f"{m['movement_id']} du {j}, {comptes[a]['account_alias']} chez {noms[comptes[a]['institution_id']]} : "
          f"{m['movement_type']} de {_cad2(m['amount_cad'])}, soit {_pct(100 * m['amount_cad'] / hier['market_value_cad'])} de la "
          "valeur du compte la veille (l'apport le plus gros relativement au compte, hors fin de mois).", "",
          "| Ordre | Fonds | Sens | Parts | VL | Montant |", "|---|---|---|---:|---:|---:|"]
    for o in t["internal_trades"]:
        if o["movement_id"] == m["movement_id"]:
            L.append(f"| {o['trade_id']} | {o['fund_id']} | {o['side']} | {_nb(o['units'], 3)} | {_nb(o['unit_price'], 6)} | "
                     f"{_cad2(o['gross_amount_cad'])} |")
    L += ["", f"| Fonds | Parts le {v} | VL le {v} | VL le {j} | Parts le {j} |", "|---|---:|---:|---:|---:|"]
    for f in sorted(set(avant) | set(apres)):
        L.append(f"| {f} | {_nb(avant.get(f, 0.0), 3)} | {_nb(vl.get((f, v), 0.0), 6)} | {_nb(vl[(f, j)], 6)} | "
                 f"{_nb(apres.get(f, 0.0), 3)} |")
    L += ["", f"- V⁺ du {v} : {_cad2(hier['market_value_cad'])} ; V⁺ du {j} : {_cad2(ajd['market_value_cad'])} ; flux du jour "
          f"F = {_cad2(ajd['net_external_flow_cad'])} ; V⁻ = V⁺ − F = {_cad2(ajd['market_value_cad'] - ajd['net_external_flow_cad'])}.",
          f"- Rendement du jour : r = V⁻ ÷ V⁺ de la veille − 1 = {_taux(ajd['daily_twr'], 4)}. Rendement des seules parts "
          f"détenues la veille, aux VL du jour : {_taux(marche, 4)}. L'écart ({_nb(1e4 * (ajd['daily_twr'] - marche), 4).replace('-', '−')} point de "
          "base) vient de l'arrondi des parts achetées et des valeurs au cent.",
          f"- TWR cumulé du compte : {_taux(hier['cumulative_twr'], 4)} la veille, {_taux(ajd['cumulative_twr'], 4)} le jour de "
          f"l'apport. La valeur est multipliée par {_nb(ajd['market_value_cad'] / hier['market_value_cad'], 2)}, le TWR ne bouge "
          "que du rendement du marché."]
    for e in (("institution", comptes[a]["institution_id"]), ("portfolio", PORTEFEUILLE)):
        x = jour_perf[(*e, j)]
        L.append(f"- {nom_entite[e]} le {j} : flux {_cad2(x['net_external_flow_cad'])}, r = {_taux(x['daily_twr'], 4)}.")

    L += ["", "## Contrôles", "", "| Contrôle | Statut | Détail |", "|---|---|---|"]
    L += [f"| {r.name} | {r.status} | {r.detail} |" for r in resultats]
    chemin = dossier / "performance_report.md"
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin
