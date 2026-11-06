"""Recette de finance_ve01 chargée par l'adaptateur (J6), contre l'oracle du générateur synthétique.

Lit la base (vues rapport.*, tables chargées) et les CSV du générateur (data/, finance_ve01/distributions.csv) ;
n'importe pas adapter.py : les règles sont recalculées ici, depuis ce que voit le rapport.

  --controle distributions : rendement total du rapport = rendement de la VL totale, calendrier, valeur conservée (C2)
  --controle grand-livre   : valorisations, flux et droits du rapport = grand livre et droits du générateur (C3)
  --controle oracle        : TWR Dietz du rapport contre TWR quotidien du J5, par compte, société, global (C4)
  --controle reperes       : ref.repere = repère de catégorie ; corrélation et écart de suivi (J6b, C2)
  --controle rapport       : écrit <export>/adapter_report.md (C5)

Usage (depuis la racine) : python scripts/recette_synthetique.py --controle distributions
  [--path Generateur-data-fictive/outputs/vitrine_seed_20261103]. Code de sortie 1 si un contrôle bloquant échoue.
"""
import argparse
import bisect
import csv
import datetime as dt
import math
import sys
from collections import defaultdict
from pathlib import Path

import psycopg

RACINE = Path(__file__).resolve().parent.parent
EXPORT = RACINE / "Generateur-data-fictive" / "outputs" / "vitrine_seed_20261103"
DSN = "host=localhost port=5432 dbname=finance_ve01 user=finance"
DEMI_PRIX = 0.00005                     # arrondi d'un prix publié à 4 décimales
DEMI_PART = 0.0005                      # arrondi d'une part publiée à 3 décimales
DEMI_CENT = 0.005


def lire(chemin: Path) -> list[dict]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def jour(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def connexion() -> psycopg.Connection:
    cx = psycopg.connect(DSN)
    base = cx.execute("SELECT current_database()").fetchone()[0]
    if base != "finance_ve01":
        raise SystemExit(f"Base inattendue : {base}")
    return cx


def vl_totale(export: Path) -> dict[str, dict[dt.date, float]]:
    vl: dict[str, dict[dt.date, float]] = defaultdict(dict)
    for p in lire(export / "data" / "fund_prices_daily.csv"):
        vl[p["fund_id"]][jour(p["date"])] = float(p["nav_total_return"])
    return vl


def fin_de_mois(j: dt.date) -> bool:
    """Dernier jour ouvrable du mois (lundi à vendredi, sans jours fériés, comme le générateur)."""
    k = j + dt.timedelta(days=1)
    while k.weekday() >= 5:
        k += dt.timedelta(days=1)
    return k.month != j.month


# ------------------------------------------------------------------------------------------------
# C2 — distributions
# ------------------------------------------------------------------------------------------------
def controle_distributions(cx, export: Path) -> int:
    echecs = 0
    vl = vl_totale(export)
    frequence = {f["fund_id"]: f["distribution_frequency"] for f in lire(export / "data" / "funds.csv")}
    journal = {(d["fund_id"], jour(d["date"])): float(d["rate"]) for d in
               lire(export / "finance_ve01" / "distributions.csv")}

    # 1. Rendement total du rapport, jours où le fonds est détenu la veille (seuls jours lus par rendement_quotidien)
    lignes = cx.execute("""
        SELECT r.code_fa, r.jour, r.veille, r.prix::float8, r.prix_veille::float8, r.distribution::float8, r.rendement,
               coalesce(h.parts, 0)::float8, coalesce(d.n, 0), coalesce(d.parts, 0)::float8, coalesce(h.n, 0)
        FROM rapport.rendement_fonds r
        LEFT JOIN LATERAL (SELECT sum(p.parts) AS parts, count(*) FILTER (WHERE p.parts > 0) AS n FROM rapport.parts p
                           WHERE p.code_fa = r.code_fa AND p.du <= r.veille AND p.au > r.veille) h ON true
        LEFT JOIN LATERAL (SELECT count(*) AS n, sum(p.parts) AS parts FROM fait.transaction t
                           JOIN rapport.parts p ON p.compte_alias = t.compte_alias AND p.code_fonds = t.code_fonds
                                               AND p.du < t.date_negociation AND p.au >= t.date_negociation
                           WHERE t.nature = 'revenu' AND t.code_fonds = r.code_fa AND t.date_negociation = r.jour
                             AND p.parts > 0) d ON true
        WHERE r.veille IS NOT NULL ORDER BY 1, 2""").fetchall()
    verifies = exclus = jours_dist = invisibles = 0
    pire, pire_abs, hors, hors_contrat, pire_contrat = 0.0, 0.0, [], 0, 0.0
    for f, j, veille, prix, prix_veille, dist, r, detenues, n, parts_dist, detenteurs in lignes:
        if detenues <= 0:
            exclus += 1
            continue
        verifies += 1
        r_tr = vl[f][j] / vl[f][veille] - 1
        # Arrondi au cent des réinvestissements : sur les comptes qui en reçoivent un ; un jour de versement où aucun
        # montant n'atteint le cent, la distribution est invisible au rapport, < 0,005 $ par détenteur de la veille
        if n:
            cent = DEMI_CENT * n / parts_dist
        elif (f, j) in journal:
            cent = DEMI_CENT * detenteurs / detenues
            invisibles += 1
        else:
            cent = 0.0
        borne = (DEMI_PRIX * (2 + r_tr) + cent) / prix_veille
        jours_dist += n > 0
        ecart = abs(r - r_tr)
        # Borne écrite à l'ouverture : 0,00005 sur chaque prix et sur la distribution par part
        b_contrat = (DEMI_PRIX * (2 + r_tr) + (DEMI_PRIX if n or (f, j) in journal else 0.0)) / prix_veille
        hors_contrat += ecart > b_contrat
        pire_contrat = max(pire_contrat, ecart / b_contrat)
        pire_abs = max(pire_abs, ecart)
        pire = max(pire, ecart / borne)
        if ecart > borne:
            hors.append(f"{f} {j} : écart {ecart:.2e} > borne {borne:.2e}")
    echecs += bool(hors)
    print(f"[{'FAIL' if hors else 'PASS'}] rendement total du rapport = rendement de la VL totale : {verifies} jours "
          f"fonds vérifiés (dont {jours_dist} jours de distribution), pire écart {pire_abs:.2e}, pire écart ÷ borne "
          f"{pire:.3f} ; {invisibles} versements sous le cent pour tous les détenteurs ; {exclus} jours sans détenteur la "
          f"veille, non lus par rapport.rendement_quotidien")
    for h in hors[:10]:
        print(f"    {h}")
    print(f"[DIAG] borne écrite à l'ouverture du contrat (0,00005 sur chaque prix et sur la distribution par part, sans "
          f"l'arrondi au cent des réinvestissements) : pire écart ÷ borne {pire_contrat:.3f}, {hors_contrat} jours "
          f"fonds au-delà sur {verifies} ; jours sans détenteur la veille, non contrôlés : {exclus}")

    # 2. Calendrier et signe : sauts de VL ex ÷ VL totale, lus dans pub.cours
    cotes: dict[str, list[tuple[dt.date, float]]] = defaultdict(list)
    for s, j, c in cx.execute("SELECT s.code_fa, c.date_seance, c.cloture::float8 FROM pub.cours c "
                              "JOIN ref.symbole s USING (symbole) ORDER BY 1, 2"):
        cotes[s].append((j, c))
    sauts, mal_dates, positifs, non_journal, ecart_taux, decembre = 0, [], [], [], 0.0, defaultdict(int)
    min_vl = min(c for serie in cotes.values() for _, c in serie)
    for f, serie in cotes.items():
        for (j0, c0), (j1, c1) in zip(serie, serie[1:]):
            q = (c1 / vl[f][j1]) / (c0 / vl[f][j0]) - 1
            borne = DEMI_PRIX / c1 + DEMI_PRIX / c0
            if q > borne:
                positifs.append(f"{f} {j1} : +{q:.2e}")
            if q >= -borne:
                continue
            sauts += 1
            if frequence[f] == "monthly" and not fin_de_mois(j1):
                mal_dates.append(f"{f} {j1} (mensuel, hors fin de mois)")
            if frequence[f] == "annual" and not (j1.month == 12 and j1.day >= 20):
                mal_dates.append(f"{f} {j1} (annuel, hors fenêtre de décembre)")
            if frequence[f] == "annual":
                decembre[(f, j1.year)] += 1
            if (f, j1) not in journal:
                non_journal.append(f"{f} {j1}")
            else:
                ecart_taux = max(ecart_taux, abs(-q - journal[(f, j1)]) / borne)
    doublons = [f"{f} {a}" for (f, a), n in decembre.items() if n > 1]
    invisibles = sum(1 for (f, j), t in journal.items() if t > 3 * (2 * DEMI_PRIX / dict(cotes[f])[j]))
    erreurs = mal_dates + doublons + positifs + non_journal
    echecs += bool(erreurs) or min_vl <= 0
    print(f"[{'FAIL' if erreurs else 'PASS'}] calendrier : {sauts} versements lus dans pub.cours (sur {len(journal)} du "
          f"journal, dont {invisibles} au-dessus de 3 fois l'arrondi du prix), mensuels en fin de mois, annuels du 20 au "
          f"31 décembre, au plus un par décembre ; hors calendrier {len(mal_dates)}, doublons {len(doublons)}, absents du "
          f"journal {len(non_journal)} ; taux lu ÷ taux du journal à {ecart_taux:.2f} fois l'arrondi au plus")
    for e in erreurs[:10]:
        print(f"    {e}")
    neg = cx.execute("SELECT count(*) FROM rapport.distribution WHERE par_part < 0").fetchone()[0] + \
        cx.execute("SELECT count(*) FROM fait.transaction WHERE nature = 'revenu' AND montant_brut < 0").fetchone()[0]
    echecs += neg > 0 or min_vl <= 0
    print(f"[{'FAIL' if neg or min_vl <= 0 else 'PASS'}] signe : {len(positifs)} hausse de VL ex ÷ VL totale, {neg} "
          f"distribution négative ; VL ex minimale {min_vl:.4f} $")

    # 3. Valeur conservée : parts publiées × VL ex = parts du grand livre × VL totale, chaque jour, chaque compte
    alias = {a["account_id"]: a["account_alias"] for a in lire(export / "data" / "accounts.csv")}
    parts: dict[tuple[str, str], tuple[list[dt.date], list[float]]] = {}
    for a, f, j, p in cx.execute("SELECT compte_alias, code_fonds, du, parts::float8 FROM rapport.parts ORDER BY 1, 2, 3"):
        x = parts.setdefault((a, f), ([], []))
        x[0].append(j)
        x[1].append(p)
    prix = {f: dict(s) for f, s in cotes.items()}
    n, hors, pire = 0, [], 0.0
    for l in lire(export / "data" / "positions_daily.csv"):
        a, f, j = alias[l["account_id"]], l["fund_id"], jour(l["date"])
        dates, valeurs = parts.get((a, f), ([], []))
        k = bisect.bisect_right(dates, j) - 1
        p_ex = valeurs[k] if k >= 0 else 0.0
        valeur = p_ex * prix[f][j]
        borne = DEMI_PART * prix[f][j] + p_ex * DEMI_PRIX + DEMI_CENT + 1e-9
        e = abs(valeur - float(l["market_value_cad"]))
        n += 1
        pire = max(pire, e / borne)
        if e > borne:
            hors.append(f"{a} {f} {j} : {valeur:.4f} contre {l['market_value_cad']}")
    echecs += bool(hors)
    print(f"[{'FAIL' if hors else 'PASS'}] valeur conservée : {n} positions jour × compte × fonds, pire écart ÷ borne "
          f"{pire:.3f} (borne : 0,0005 part × VL ex + parts × 0,00005 + 0,005 $)")
    for h in hors[:10]:
        print(f"    {h}")
    return echecs


# ------------------------------------------------------------------------------------------------
# C3 — le rapport retrouve le grand livre
# ------------------------------------------------------------------------------------------------
def controle_grand_livre(cx, export: Path) -> int:
    echecs = 0
    comptes = lire(export / "data" / "accounts.csv")
    alias = {a["account_id"]: a["account_alias"] for a in comptes}
    valeurs = {(alias[v["account_id"]], jour(v["date"])): float(v["total_value_cad"])
               for v in lire(export / "data" / "account_values_daily.csv")}

    # Valorisations : chaque point de rapport.valorisation contre la valeur du compte ce jour-là
    points = cx.execute("""SELECT compte_alias, date_point, sum(valeur_marchande)::float8, sum(parts)::float8, count(*),
                                  sum(parts * prix)::float8, count(*) FILTER (WHERE date_prix <> date_point)
                           FROM rapport.valorisation GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
    hors_contrat, hors_large, perimes, pire_c, pire_l = [], [], 0, 0.0, 0.0
    for a, j, vm, p, n, vp, anciens in points:
        e = abs(vm - valeurs[(a, j)])
        b_contrat = p * DEMI_PRIX + n * DEMI_CENT + 1e-9
        b_large = b_contrat + DEMI_PART * (vp / p if p else 0) * n          # plus l'arrondi des parts publiées
        perimes += anciens
        pire_c, pire_l = max(pire_c, e / b_contrat), max(pire_l, e / b_large)
        if e > b_contrat:
            hors_contrat.append(f"{a} {j} : rapport {vm:.2f}, grand livre {valeurs[(a, j)]:.2f}, écart {e:.4f}")
        if e > b_large:
            hors_large.append(f"{a} {j} : écart {e:.4f} > {b_large:.4f}")
    # Borne bloquante : celle de la modification du contrat (C3), qui ajoute l'arrondi des parts publiées admis par C2
    echecs += bool(hors_large) or perimes > 0
    print(f"[{'FAIL' if hors_large or perimes else 'PASS'}] valorisations : {len(points)} points compte × date, pire "
          f"écart ÷ borne {pire_l:.3f} (Σ lignes : 0,0005 part × VL + parts × 0,00005 + 0,005 $), {len(hors_large)} "
          f"au-delà ; {perimes} lignes à un prix d'une autre date")
    for h in hors_large[:10]:
        print(f"    {h}")
    print(f"[DIAG] borne écrite à l'ouverture du contrat (Σ lignes : parts × 0,00005 + 0,005 $, sans l'arrondi des "
          f"parts) : pire écart ÷ borne {pire_c:.3f}, {len(hors_contrat)} au-delà")
    for h in hors_contrat[:10]:
        print(f"    {h}")

    arrete = cx.execute("SELECT date_arrete FROM rapport.arrete").fetchone()[0]
    fin = max(j for _, j in valeurs)
    vm_r, p_r, n_r = cx.execute("SELECT sum(valeur_marchande)::float8, sum(parts)::float8, count(*) FROM rapport.valorisation "
                                "WHERE date_point = %s", (arrete,)).fetchone()
    vm_g = sum(v for (a, j), v in valeurs.items() if j == fin)
    b = p_r * DEMI_PRIX + n_r * DEMI_CENT
    ok = arrete == fin and abs(vm_r - vm_g) <= b
    echecs += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] arrêté : rapport.arrete {arrete}, fin du grand livre {fin} ; VM {vm_r:,.2f} $ "
          f"contre {vm_g:,.2f} $ (écart {abs(vm_r - vm_g):.4f}, borne {b:.4f})")

    # Flux par compte × année
    attendu: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    for m in lire(export / "data" / "external_movements.csv"):
        i = {"PAC": 0, "PONCTUEL": 0, "RETRAIT": 1, "FRAIS": 2}[m["movement_type"]]
        attendu[(alias[m["account_id"]], jour(m["date"]).year)][i] += abs(round(float(m["amount_cad"]) * 100))
    obtenu = {(a, y): [round(v * 100), round(r * 100), round(f * 100)] for a, y, v, r, f in cx.execute(
        "SELECT compte_alias, annee, sum(versements), sum(retraits), sum(frais) FROM rapport.performance GROUP BY 1, 2")}
    ecarts = [f"{k} : rapport {obtenu.get(k)}, générateur {v}" for k, v in sorted(attendu.items()) if obtenu.get(k) != v]
    ecarts += [f"{k} : absent du générateur" for k in obtenu if k not in attendu and any(obtenu[k])]
    echecs += bool(ecarts)
    print(f"[{'FAIL' if ecarts else 'PASS'}] flux par compte × année (versements PAC et ponctuels, retraits, frais) : "
          f"{len(attendu)} couples, {len(ecarts)} écart(s) au cent")
    for e in ecarts[:10]:
        print(f"    {e}")

    # Droits par régime × année
    salle = {(r["regime"], int(r["year"])): (round(float(r["contributions_cad"]) * 100), round(float(r["room_end_cad"]) * 100))
             for r in lire(export / "data" / "contribution_room.csv")}
    vue = {(r, a): (c, d) for r, a, c, d in cx.execute("SELECT regime, annee, cotisations, droits_restants FROM rapport.droits")}
    ecarts, absentes = [], []
    for k, (c, d) in sorted(vue.items()):
        if d is None:
            ecarts.append(f"{k} : droits vides (plafond ou avis manquant)")
        elif k not in salle:
            ecarts.append(f"{k} : absent du générateur")
        elif (round(c * 100), round(d * 100)) != salle[k]:
            ecarts.append(f"{k} : rapport ({c}, {d}), générateur {tuple(x / 100 for x in salle[k])}")
    for k, (c, _) in sorted(salle.items()):
        if k not in vue:
            (absentes if c == 0 else ecarts).append(f"{k} : absent du rapport, cotisations {c / 100:.2f}")
    echecs += bool(ecarts)
    print(f"[{'FAIL' if ecarts else 'PASS'}] droits par régime × année (cotisations, droits restants) : {len(vue)} lignes "
          f"du rapport, {len(ecarts)} écart(s) au cent ; années du générateur sans cotisation ni ligne au rapport "
          f"(la vue commence à la première cotisation) : {', '.join(absentes) or 'aucune'}")
    for e in ecarts[:10]:
        print(f"    {e}")

    plafonds = {(r, ru, a): float(m) for r, ru, a, m in cx.execute("SELECT regime, rubrique, annee, montant FROM ref.plafond")}
    limites = lire(export / "data" / "tax_limits.csv")
    limites = [l for l in limites if l["amount_cad"]]          # les fins de période REER n'ont pas de montant
    diff = [l for l in limites if
            plafonds.get((l["regime"], l["rubric"], int(l["year"]) if l["year"] else None)) != float(l["amount_cad"])]
    niveaux = cx.execute("SELECT niveau, count(*) FROM rapport.alerte GROUP BY 1 ORDER BY 1").fetchall()
    calendrier = sum(n for v, n in niveaux if v == "calendrier REER à compléter")
    ok = not diff and calendrier == 0
    echecs += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] plafonds : {len(limites)} plafonds du générateur, {len(diff)} absent(s) de "
          f"ref.plafond ou différent(s) ; droits de rapport.droits_* tous calculés depuis ref.plafond et ref.reer_avis "
          f"(aucune ligne vide ci-dessus) ; niveaux de rapport.alerte : {dict(niveaux)}")
    for l in diff[:10]:
        print(f"    {l}")
    return echecs


# ------------------------------------------------------------------------------------------------
# C4 — Dietz du rapport contre TWR quotidien
# ------------------------------------------------------------------------------------------------
def tableau_oracle(cx, export: Path) -> list[dict]:
    comptes = lire(export / "data" / "accounts.csv")
    alias = {a["account_id"]: a["account_alias"] for a in comptes}
    societe = {i["institution_id"]: i["name"] for i in lire(export / "data" / "institutions.csv")}
    twr = {}
    for p in lire(export / "data" / "performance_periods.csv"):
        if p["period"] == "inception":
            continue
        e = {"account": lambda x: alias[x], "institution": lambda x: societe[x], "portfolio": lambda x: "Global"}[
            p["entity_type"]](p["entity_id"])
        twr[(p["entity_type"], e, int(p["period"]))] = float(p["twr"])
    dietz = {}
    for a, y, r in cx.execute("SELECT coalesce(compte_alias, 'Global'), annee, twr FROM rapport.rendement_annuel"):
        dietz[("portfolio" if a == "Global" else "account", a, y)] = float(r)
    mensuel: dict[tuple[str, int], list[float]] = defaultdict(list)
    for s, y, r in cx.execute("""SELECT c.societe, p.annee, sum(p.numerateur) / nullif(sum(p.denominateur), 0)
                                 FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias
                                 GROUP BY c.societe, p.annee, p.mois ORDER BY 1, 2, p.mois"""):
        mensuel[(s, y)].append(float(r or 0))
    for (s, y), rs in mensuel.items():
        dietz[("institution", s, y)] = math.prod(1 + r for r in rs) - 1
    lignes = []
    for k in sorted(set(twr) | set(dietz), key=lambda k: (("portfolio", "institution", "account").index(k[0]), k[1], k[2])):
        d, t = dietz.get(k), twr.get(k)
        lignes.append(dict(niveau=k[0], entite=k[1], annee=k[2], dietz=d, twr=t,
                           ecart=None if d is None or t is None else (d - t) * 100))
    return lignes


def controle_oracle(cx, export: Path) -> int:
    lignes = tableau_oracle(cx, export)
    noms = {"portfolio": "global", "institution": "société", "account": "compte"}
    print(f"{'niveau':<8} {'entité':<11} {'année':>5} {'Dietz':>9} {'TWR':>9} {'écart (pt)':>11}")
    for l in lignes:
        f = (lambda x: "—" if x is None else f"{x * 100:8.2f}%")
        print(f"{noms[l['niveau']]:<8} {l['entite']:<11} {l['annee']:>5} {f(l['dietz']):>9} {f(l['twr']):>9} "
              f"{'—' if l['ecart'] is None else format(l['ecart'], '+.3f'):>11}")
    valides = [l for l in lignes if l["ecart"] is not None]
    pire = max(valides, key=lambda l: abs(l["ecart"]))
    manquants = [l for l in lignes if l["ecart"] is None]
    print(f"[DIAG] {len(valides)} couples entité × année ; plus grand écart absolu {abs(pire['ecart']):.3f} point "
          f"({noms[pire['niveau']]} {pire['entite']} {pire['annee']}) ; écart moyen absolu "
          f"{sum(abs(l['ecart']) for l in valides) / len(valides):.3f} point ; sans contrepartie : "
          f"{', '.join(f'{l['entite']} {l['annee']}' for l in manquants) or 'aucun'}")
    return 0


# ------------------------------------------------------------------------------------------------
# J6b, C2 — repères de catégorie
# ------------------------------------------------------------------------------------------------
def _stats(paires: list[tuple[float, float]]) -> tuple[float, float]:
    """Corrélation quotidienne et écart de suivi annualisé (écart-type de r − repère × √252)."""
    n = len(paires)
    mx, my = sum(x for x, _ in paires) / n, sum(y for _, y in paires) / n
    sxy = sum((x - mx) * (y - my) for x, y in paires)
    sx, sy = math.sqrt(sum((x - mx) ** 2 for x, _ in paires)), math.sqrt(sum((y - my) ** 2 for _, y in paires))
    d = [x - y for x, y in paires]
    md = sum(d) / n
    return sxy / (sx * sy), math.sqrt(sum((v - md) ** 2 for v in d) / (n - 1) * 252)


def controle_reperes(cx, export: Path) -> int:
    fonds = lire(export / "data" / "funds.csv")
    reperes = {b["benchmark_id"]: b for b in lire(export / "data" / "benchmarks.csv")}
    lignes = lire(export / "finance_ve01" / "ref.repere.csv")
    erreurs = []
    for f in fonds:
        r = [l for l in lignes if l["code_fa"] == f["fund_id"]]
        b = reperes.get(r[0]["symbole"].removeprefix("SYN-")) if len(r) == 1 else None
        if b is None or b["benchmark_type"] != "category" or float(r[0]["poids"]) != 1.0:
            erreurs.append(f"{f['fund_id']} : {len(r)} ligne(s) de ref.repere, attendu une, catégorie, poids 1")
    base = cx.execute("SELECT code_fa, count(*), min(symbole) FROM ref.repere GROUP BY 1 ORDER BY 1").fetchall()
    erreurs += [f"base {c} : {n} lignes" for c, n, _ in base if n != 1]
    erreurs += [f"base {c} : {s} ≠ export" for c, _, s in base
                if s != next(l["symbole"] for l in lignes if l["code_fa"] == c)]
    print(f"[{'PASS' if not erreurs else 'FAIL'}] ref.repere : {len(fonds)} fonds, une ligne chacun, repère de catégorie, "
          f"poids 1 (export et base, {len(base)} fonds en base)" + "".join(f"\n    {e}" for e in erreurs[:10]))

    # Indices des composites (CSV) : rendement simple du jour sur la veille du rapport
    indice = defaultdict(dict)
    for l in lire(export / "data" / "benchmarks_daily.csv"):
        indice[l["benchmark_id"]][dt.date.fromisoformat(l["date"])] = float(l["index_total_return"])
    q = cx.execute("SELECT compte_alias, code_fa, jour, veille, vm_veille, rendement, repere FROM rapport.rendement_quotidien "
                   "WHERE repere IS NOT NULL").fetchall()
    par_fonds, par_jour = defaultdict(dict), defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for _, fid, jour, veille, vm, r, rep in q:
        c = indice[f"R-{fid}"]
        comp = c[jour] / c[veille] - 1
        par_fonds[fid][jour] = (r, rep, comp)
        s = par_jour[jour]
        s[0] += vm
        s[1] += vm * r
        s[2] += vm * rep
        s[3] += vm * comp
    print("[DIAG] corrélation quotidienne et écart de suivi annualisé du rendement, contre le repère de catégorie "
          "(ref.repere) puis contre le composite du fonds")
    print(f"    {'périmètre':<10} {'repère de catégorie':<22} {'n':>5}  {'corr cat.':>9} {'suivi cat.':>10}  "
          f"{'corr comp.':>10} {'suivi comp.':>11}")
    categorie = {l["code_fa"]: l["symbole"].removeprefix("SYN-") for l in lignes}
    serie = {fid: list(j.values()) for fid, j in sorted(par_fonds.items())}
    serie["global"] = [(s[1] / s[0], s[2] / s[0], s[3] / s[0]) for _, s in sorted(par_jour.items()) if s[0] > 0]
    for k, v in serie.items():
        cc, tc = _stats([(r, rep) for r, rep, _ in v])
        cp, tp = _stats([(r, comp) for r, _, comp in v])
        print(f"    {k:<10} {categorie.get(k, 'pondéré par la VM'):<22} {len(v):>5}  {cc:>9.4f} {tc:>9.2%}  "
              f"{cp:>10.4f} {tp:>10.2%}")
    return len(erreurs)


# ------------------------------------------------------------------------------------------------
# C5 — rapport de l'adaptateur
# ------------------------------------------------------------------------------------------------
def cause(cx, l: dict, twr_jour: dict) -> str:
    """Mois qui porte le plus l'écart : Dietz du mois (compte, ou Σ numérateurs ÷ Σ dénominateurs des comptes de la
    société ou de tous les comptes) contre le TWR quotidien de l'entité chaîné sur le même mois, puis son motif."""
    filtre = {"account": "c.alias = %s", "institution": "c.societe = %s", "portfolio": "%s = 'Global'"}[l["niveau"]]
    mois = cx.execute(f"""SELECT p.mois, min(p.date_debut), max(p.date_fin), sum(p.vm_debut)::float8,
                                 sum(p.versements + p.retraits)::float8,
                                 (sum(p.numerateur) / nullif(sum(p.denominateur), 0))::float8
                          FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias
                          WHERE {filtre} AND p.annee = %s GROUP BY p.mois ORDER BY p.mois""",
                      (l["entite"], l["annee"])).fetchall()
    premier = cx.execute(f"""SELECT min(p.mois) FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias
                             WHERE {filtre}""", (l["entite"],)).fetchone()[0]
    nouveaux = dict(cx.execute(f"""SELECT o.mois, count(*) FROM (SELECT p.compte_alias, min(p.mois) AS mois
                                   FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias
                                   WHERE {filtre} GROUP BY 1) o GROUP BY 1""", (l["entite"],)).fetchall())
    serie = twr_jour[(l["niveau"], l["entite"])]
    ecarts = []
    for m, d0, d1, vm0, flux, rd in mois:
        rt = math.prod(1 + x for j, x in serie if d0 < j <= d1) - 1
        e = (rd or 0) - rt
        if m == premier:
            motif = "premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés"
        elif m in nouveaux:
            motif = f"ouverture de {nouveaux[m]} compte(s) : premier mois d'un compte, agrégé aux autres"
        elif vm0 > 0 and flux / vm0 > 0.2:
            motif = f"flux de {flux / vm0:.0%} de la valeur de début : pondération de Dietz"
        else:
            motif = "approximation de Dietz sur des flux en cours de mois, marché agité"
        ecarts.append((e, m, motif))
    # Mois de même signe que l'écart annuel, du plus lourd au plus léger, jusqu'à en porter au moins 80 %
    cible, retenus, cumul = l["ecart"] / 100, [], 0.0
    for e, m, motif in sorted(ecarts, key=lambda x: -abs(x[0])):
        if e * cible <= 0 or abs(cumul) >= 0.8 * abs(cible):
            continue
        retenus.append(f"{m:%Y-%m} {e * 100:+.2f} pt, {motif}")
        cumul += e
    return " ; ".join(retenus) + f" (Σ {cumul * 100:+.2f} pt sur {cible * 100:+.2f})"


def ecrire_rapport(cx, export: Path) -> Path:
    o = []
    o.append("# Rapport de l'adaptateur vers finance_ve01 (J6)\n")
    o.append("> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER. Écrit par "
             "`scripts/recette_synthetique.py --controle rapport` depuis la base chargée et les exports.\n")
    arrete = cx.execute("SELECT date_arrete FROM rapport.arrete").fetchone()[0]
    o.append(f"Base `finance_ve01`, arrêté du {arrete}. Le rapport Power BI figé n'est pas touché tant que "
             "`scripts/figer.py` ne tourne pas (J7).\n")

    o.append("## 1. Distributions par fonds et par année\n")
    o.append("Taux = somme des taux versés dans l'année (fraction de la VL avant versement), revenu courant + gains "
             "en capital de décembre ; la plage de `[adapter.yield_pct]` ne porte que sur le revenu courant, les gains en "
             "capital sont une part tirée du gain de l'année au-delà de ce revenu. Réinvesti = montants des "
             "lignes « Distribution réinvestie » des comptes. Natures : dernier exercice publié "
             "(`pub.rapport_annuel`, exercice au 30 septembre), part de chaque nature.\n")
    fonds = {f["fund_id"]: f for f in lire(export / "data" / "funds.csv")}
    taux: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for d in lire(export / "finance_ve01" / "distributions.csv"):
        x = taux[(d["fund_id"], jour(d["date"]).year)]
        part_gc = float(d["per_unit_capital_gain"]) / (float(d["per_unit_income"]) + float(d["per_unit_capital_gain"]))
        x[0] += float(d["rate"]) * (1 - part_gc)
        x[1] += float(d["rate"]) * part_gc
    reinv = {(f, y): float(m) for f, y, m in cx.execute(
        "SELECT code_fonds, extract(year FROM date_negociation)::int, sum(montant_brut) FROM fait.transaction "
        "WHERE nature = 'revenu' GROUP BY 1, 2")}
    natures = {r[0]: r[1:] for r in cx.execute(
        "SELECT code_fa, part_revenus, part_dividendes, part_gains_capital FROM rapport.rapport_fonds")}
    annees = sorted({y for _, y in taux})
    o.append("| Fonds | Archétype | Fréquence | " + " | ".join(f"{y} revenu + gains / réinvesti" for y in annees)
             + " | Revenus / dividendes / gains en capital |")
    o.append("|---|---|---|" + "---|" * len(annees) + "---|")
    for f in sorted(fonds):
        n = natures.get(f)
        nat = " / ".join("—" if x is None else f"{float(x):.0%}" for x in n) if n else "—"
        o.append(f"| {f} | {fonds[f]['archetype']} | {fonds[f]['distribution_frequency']} | "
                 + " | ".join(f"{taux[(f, y)][0]:.2%} + {taux[(f, y)][1]:.2%} / {reinv.get((f, y), 0):,.2f} $"
                              if (f, y) in taux else f"— / {reinv.get((f, y), 0):,.2f} $" for y in annees) + f" | {nat} |")

    o.append("\n## 2. TWR Dietz du rapport contre TWR quotidien du J5\n")
    o.append("Dietz : `rapport.rendement_annuel` (compte, global), Dietz mensuel de la société chaîné "
             "(Σ numérateurs ÷ Σ dénominateurs de `rapport.performance`). TWR : `performance_periods`. Cause donnée "
             "pour tout écart de plus de 0,5 point : les mois de même signe qui en portent au moins 80 %, chaque mois "
             "comparé au TWR quotidien chaîné sur le même mois, avec son motif.\n")
    alias = {a["account_id"]: a["account_alias"] for a in lire(export / "data" / "accounts.csv")}
    societe = {i["institution_id"]: i["name"] for i in lire(export / "data" / "institutions.csv")}
    nom = {"account": alias.get, "institution": societe.get, "portfolio": lambda _: "Global"}
    twr_jour: dict[tuple[str, str], list[tuple[dt.date, float]]] = defaultdict(list)
    for p in lire(export / "data" / "performance_daily.csv"):
        if p["daily_twr"]:
            cle = (p["entity_type"], nom[p["entity_type"]](p["entity_id"]))
            twr_jour[cle].append((jour(p["date"]), float(p["daily_twr"])))
    noms = {"portfolio": "global", "institution": "société", "account": "compte"}
    o.append("| Niveau | Entité | Année | Dietz | TWR | Écart (pt) | Cause (écart > 0,5 pt) |")
    o.append("|---|---|---|---|---|---|---|")
    for l in tableau_oracle(cx, export):
        f = (lambda x: "—" if x is None else f"{x:.2%}")
        c = cause(cx, l, twr_jour) if l["ecart"] is not None and abs(l["ecart"]) > 0.5 else ""
        o.append(f"| {noms[l['niveau']]} | {l['entite']} | {l['annee']} | {f(l['dietz'])} | {f(l['twr'])} | "
                 f"{'—' if l['ecart'] is None else format(l['ecart'], '+.3f')} | {c} |")

    o.append("\n## 3. Requêtes de recette SQL\n")
    requetes = [
        "SELECT * FROM rapport.arrete",
        "SELECT regime, annee, droits_debut, cotisations, droits_restants, niveau FROM rapport.alerte ORDER BY 1, 2",
        "SELECT c.societe, round(sum(p.vm_fin)) FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias "
        "WHERE (p.compte_alias, p.date_fin) IN (SELECT compte_alias, max(date_fin) FROM rapport.performance GROUP BY 1) "
        "GROUP BY 1 ORDER BY 1",
        "SELECT coalesce(compte_alias, 'GLOBAL'), annee, round(twr * 100, 2) FROM rapport.rendement_annuel ORDER BY 1, 2",
        "SELECT niveau, perimetre, fenetre, n, round(volatilite::numeric, 4), round(rendement::numeric, 4), "
        "round(rendement_repere::numeric, 4), round(pire_baisse::numeric, 4) FROM rapport.risque_mesure ORDER BY 3, 1, 2",
    ]
    for q in requetes:
        cur = cx.execute(q)
        o.append(f"```sql\n{q};\n```\n")
        o.append("| " + " | ".join(d.name for d in cur.description) + " |")
        o.append("|" + "---|" * len(cur.description))
        for r in cur.fetchall():
            o.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
        o.append("")

    o.append("## 4. Valeur marchande par société à l'arrêté\n")
    lignes = cx.execute("""SELECT k.societe, sum(v.valeur_marchande) FROM rapport.valorisation v
                           JOIN ref.compte k ON k.alias = v.compte_alias WHERE v.date_point = %s
                           GROUP BY 1 ORDER BY 1""", (arrete,)).fetchall()
    total = sum(float(v) for _, v in lignes)
    o.append("| Société | VM | Part |\n|---|---|---|")
    for s, v in lignes:
        o.append(f"| {s} | {float(v):,.2f} $ | {float(v) / total:.1%} |")
    o.append(f"| Total | {total:,.2f} $ | 100 % |\n")
    seuil = cx.execute("SELECT societe, round(vm_menage, 2), tranche, round(distance, 2) FROM rapport.seuil ORDER BY 1").fetchall()
    o.append("Seuil de frais par société (`rapport.seuil`) : " + " ; ".join(f"{s} {v} $ ({t})" for s, v, t, _ in seuil) + ".\n")
    chemin = export / "adapter_report.md"
    chemin.write_text("\n".join(o) + "\n", encoding="utf-8")
    return chemin


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Recette de finance_ve01 contre l'oracle du générateur synthétique")
    p.add_argument("--controle", required=True, choices=("distributions", "grand-livre", "oracle", "reperes", "rapport"))
    p.add_argument("--path", type=Path, default=EXPORT)
    a = p.parse_args(argv)
    with connexion() as cx:
        if a.controle == "rapport":
            print(f"Rapport : {ecrire_rapport(cx, a.path)}")
            return 0
        echecs = {"distributions": controle_distributions, "grand-livre": controle_grand_livre,
                  "oracle": controle_oracle, "reperes": controle_reperes}[a.controle](cx, a.path)
    print(f"Résultat : {'tous les contrôles bloquants passent' if echecs == 0 else f'{echecs} ÉCHEC(S)'}")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
