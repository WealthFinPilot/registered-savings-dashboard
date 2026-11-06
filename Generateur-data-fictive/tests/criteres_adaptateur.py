"""Recalcul indépendant des critères de l'adaptateur (J6, C1 et C2), depuis les seuls CSV : ce module n'importe pas
adapter.py. Il refait en Python ce que font les vues du rapport (rapport.parts, rapport.distribution,
rapport.rendement_fonds), pour les graines où aucune base n'est chargée.

integrite() : nombres de lignes attendus, clés, chaîne des parts. rendement() : rendement total vu par le rapport
contre la VL totale, jours où le fonds est détenu la veille. calendrier() : versements lus comme sauts de VL ex ÷ VL
totale. conservation() : parts publiées × VL ex contre la valeur des positions du grand livre.
"""
import bisect
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

DEMI_PRIX, DEMI_PART, DEMI_CENT = 0.00005, 0.0005, 0.005


def lire(dossier: Path, nom: str) -> list[dict]:
    sous = "finance_ve01" if "." in nom or nom == "distributions" else "data"
    with (dossier / sous / f"{nom}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def jour(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def fin_de_mois(j: dt.date) -> bool:
    k = j + dt.timedelta(days=1)
    while k.weekday() >= 5:
        k += dt.timedelta(days=1)
    return k.month != j.month


class Export:
    """Tables relues une fois : VL totales, cours publiés, parts publiées par compte et fonds."""

    def __init__(self, dossier: Path):
        self.dossier = dossier
        self.vl: dict[str, dict[dt.date, float]] = defaultdict(dict)
        for p in lire(dossier, "fund_prices_daily"):
            self.vl[p["fund_id"]][jour(p["date"])] = float(p["nav_total_return"])
        self.cours: dict[str, list[tuple[dt.date, float]]] = defaultdict(list)
        for c in lire(dossier, "pub.cours"):
            if c["symbole"].removeprefix("SYN-") in self.vl:
                self.cours[c["symbole"].removeprefix("SYN-")].append((jour(c["date_seance"]), float(c["cloture"])))
        for s in self.cours.values():
            s.sort()
        self.transactions = sorted(lire(dossier, "fait.transaction"), key=lambda l: (l["compte_alias"], int(l["rang"])))
        # Parts publiées après la dernière opération de chaque date (rapport.parts)
        self.parts: dict[tuple[str, str], tuple[list[dt.date], list[float]]] = {}
        for l in self.transactions:
            dates, valeurs = self.parts.setdefault((l["compte_alias"], l["code_fonds"]), ([], []))
            j = jour(l["date_negociation"])
            if dates and dates[-1] == j:
                valeurs[-1] = float(l["parts_restantes"])
            else:
                dates.append(j)
                valeurs.append(float(l["parts_restantes"]))

    def detenues(self, compte: str, fonds: str, j: dt.date) -> float:
        dates, valeurs = self.parts.get((compte, fonds), ([], []))
        k = bisect.bisect_right(dates, j) - 1
        return valeurs[k] if k >= 0 else 0.0


def integrite(e: Export) -> tuple[list[str], str]:
    erreurs = []
    ordres = lire(e.dossier, "internal_trades")
    revenus = [l for l in e.transactions if l["nature"] == "revenu"]
    if len(e.transactions) != len(ordres) + len(revenus):
        erreurs.append(f"{len(e.transactions)} transactions ≠ {len(ordres)} ordres + {len(revenus)} réinvestissements")
    positions = lire(e.dossier, "positions_daily")
    fin = max(p["date"] for p in positions)
    detenues = sum(1 for p in positions if p["date"] == fin and float(p["units"]) > 0)
    sommaire = lire(e.dossier, "fait.sommaire")
    if len(sommaire) != detenues:
        erreurs.append(f"{len(sommaire)} lignes de sommaire ≠ {detenues} positions non nulles à l'arrêté")
    precedent: dict[tuple[str, str], int] = {}
    for l in e.transactions:
        cle = (l["compte_alias"], l["code_fonds"])
        apres = precedent.get(cle, 0) + int(l["signe"]) * round(float(l["parts_negociees"]) * 1000)
        if apres != round(float(l["parts_restantes"]) * 1000) or apres < 0:
            erreurs.append(f"{cle} rang {l['rang']} : chaîne des parts rompue")
        precedent[cle] = round(float(l["parts_restantes"]) * 1000)
    rangs = [(l["compte_alias"], l["rang"]) for l in e.transactions]
    if len(set(rangs)) != len(rangs):
        erreurs.append("fait.transaction : (compte, rang) en double")
    comptes = {l["account_alias"] for l in lire(e.dossier, "accounts")}
    if {l["alias"] for l in lire(e.dossier, "ref.compte")} != comptes:
        erreurs.append("ref.compte ≠ comptes du générateur")
    vides = [n for n in ("fait.releve", "fait.releve_cotisation", "ref.transfert_entrant", "ref.transfert_sortant",
                         "ref.versement_hors_export", "ref.retrait_hors_export")
             if (e.dossier / "finance_ve01" / f"{n}.csv").exists()]
    if vides:
        erreurs.append(f"fichiers de tables qui doivent rester vides : {vides}")
    return erreurs, (f"{len(e.transactions)} transactions = {len(ordres)} ordres + {len(revenus)} réinvestissements ; "
                     f"{len(sommaire)} lignes de sommaire ; chaîne des parts intacte")


def rendement(e: Export) -> tuple[list[str], str]:
    """(prix + distribution par part du jour) ÷ prix de la veille − 1 contre la VL totale. Distribution par part comme
    rapport.distribution : Σ montants réinvestis ÷ Σ parts de la veille des comptes qui les reçoivent."""
    revenus: dict[tuple[str, dt.date], list[tuple[str, float]]] = defaultdict(list)
    for l in e.transactions:
        if l["nature"] == "revenu":
            revenus[(l["code_fonds"], jour(l["date_negociation"]))].append((l["compte_alias"], float(l["montant_brut"])))
    comptes = {a for a, _ in e.parts}
    journal = {(d["fund_id"], jour(d["date"])) for d in lire(e.dossier, "distributions")}
    erreurs, verifies, exclus, invisibles, pire = [], 0, 0, 0, 0.0
    for f, serie in e.cours.items():
        for (j0, p0), (j1, p1) in zip(serie, serie[1:]):
            detenteurs = [(a, e.detenues(a, f, j0)) for a in comptes if e.detenues(a, f, j0) > 0]
            if not detenteurs:
                exclus += 1
                continue
            verifies += 1
            r_tr = e.vl[f][j1] / e.vl[f][j0] - 1
            lignes = revenus.get((f, j1), [])
            parts = sum(e.detenues(a, f, j0) for a, _ in lignes)
            d = sum(m for _, m in lignes) / parts if lignes else 0.0
            # Arrondi au cent des réinvestissements : sur les comptes qui en reçoivent un ; un jour de versement où
            # aucun montant n'atteint le cent, la distribution est invisible au rapport, < 0,005 $ par détenteur
            if lignes:
                cent = DEMI_CENT * len(lignes) / parts
            elif (f, j1) in journal:
                cent = DEMI_CENT * len(detenteurs) / sum(p for _, p in detenteurs)
                invisibles += 1
            else:
                cent = 0.0
            borne = (DEMI_PRIX * (2 + r_tr) + cent) / p0
            ecart = abs((p1 + d) / p0 - 1 - r_tr)
            pire = max(pire, ecart / borne)
            if ecart > borne:
                erreurs.append(f"{f} {j1} : écart {ecart:.2e} > borne {borne:.2e}")
    return erreurs, (f"{verifies} jours fonds détenus vérifiés, pire écart ÷ borne {pire:.3f} ; {invisibles} versements "
                     f"sous le cent pour tous les détenteurs ; {exclus} jours sans détenteur")


def calendrier(e: Export) -> tuple[list[str], str]:
    frequence = {f["fund_id"]: f["distribution_frequency"] for f in lire(e.dossier, "funds")}
    journal = {(d["fund_id"], jour(d["date"])) for d in lire(e.dossier, "distributions")}
    erreurs, sauts, decembre = [], 0, defaultdict(int)
    min_vl = min(c for s in e.cours.values() for _, c in s)
    if min_vl <= 0:
        erreurs.append(f"VL ex minimale {min_vl}")
    for f, serie in e.cours.items():
        for (j0, c0), (j1, c1) in zip(serie, serie[1:]):
            q = (c1 / e.vl[f][j1]) / (c0 / e.vl[f][j0]) - 1
            borne = DEMI_PRIX / c1 + DEMI_PRIX / c0
            if q > borne:
                erreurs.append(f"{f} {j1} : VL ex ÷ VL totale en hausse (distribution négative)")
            if q >= -borne:
                continue
            sauts += 1
            if frequence[f] == "monthly" and not fin_de_mois(j1):
                erreurs.append(f"{f} {j1} : versement mensuel hors fin de mois")
            if frequence[f] == "annual":
                decembre[(f, j1.year)] += 1
                if not (j1.month == 12 and j1.day >= 20):
                    erreurs.append(f"{f} {j1} : versement annuel hors fenêtre de décembre")
            if (f, j1) not in journal:
                erreurs.append(f"{f} {j1} : versement absent du journal")
    erreurs += [f"{f} {a} : {n} versements annuels" for (f, a), n in decembre.items() if n > 1]
    negatifs = [l for l in e.transactions if l["nature"] == "revenu" and float(l["montant_brut"]) < 0]
    erreurs += [f"{l['compte_alias']} rang {l['rang']} : réinvestissement négatif" for l in negatifs]
    return erreurs, f"{sauts} versements lus dans les cours ({len(journal)} au journal), VL ex minimale {min_vl:.4f}"


def conservation(e: Export) -> tuple[list[str], str]:
    alias = {a["account_id"]: a["account_alias"] for a in lire(e.dossier, "accounts")}
    prix = {f: dict(s) for f, s in e.cours.items()}
    erreurs, n, pire = [], 0, 0.0
    for l in lire(e.dossier, "positions_daily"):
        a, f, j = alias[l["account_id"]], l["fund_id"], jour(l["date"])
        p = e.detenues(a, f, j)
        borne = DEMI_PART * prix[f][j] + p * DEMI_PRIX + DEMI_CENT + 1e-9
        ecart = abs(p * prix[f][j] - float(l["market_value_cad"]))
        n += 1
        pire = max(pire, ecart / borne)
        if ecart > borne:
            erreurs.append(f"{a} {f} {j} : écart {ecart:.4f} > {borne:.4f}")
    return erreurs, f"{n} positions jour × compte × fonds, pire écart ÷ borne {pire:.3f}"
