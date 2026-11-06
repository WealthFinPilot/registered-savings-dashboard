"""Choix de la graine de marché du scénario vitrine (jalon J6b, critère C1, écrit avant tout tirage ; resserré
par le responsable le 2026-11-04, après lecture de la graine 27 retenue par le premier critère).

Graine principale fixée (celle de base.toml) : l'univers ne change pas. Les graines de marché 1 à 100 sont
essayées dans l'ordre ; la première qui remplit les cinq conditions est retenue, sur l'oracle TWR du J5
(portefeuille entier) :
  (a) TWR global annualisé depuis l'ouverture, (1 + TWR)^(365,25 / jours) − 1, entre 6 % et 10 % ;
  (b) au moins une année civile complète (2022 à 2025) de TWR global négative ;
  (c) repli maximal de la valeur hors flux (indice 1 + TWR cumulé quotidien) sous −15 % ;
  (d) TWR global de chaque année complète (2022 à 2025) entre −20 % et +25 % ;
  (e) TWR global de l'année en cours (2026, jusqu'à l'arrêté) positif.
Une ligne par graine essayée, jusqu'à la graine retenue incluse. Rien n'est écrit : la graine retenue se
recopie à la main dans configs/vitrine.toml. Sans graine retenue : code de sortie 1, et la plage ne
s'élargit pas (H5).

Usage (depuis Generateur-data-fictive/) : python scripts/choisir_graine_marche.py
"""
import sys
from pathlib import Path

from synthetic_finance.behaviour import simuler_comportement
from synthetic_finance.config import _fusion, construire, lire_toml
from synthetic_finance.fiscal import lire_plafonds, trouver_plafonds
from synthetic_finance.ledger import tenir_grand_livre
from synthetic_finance.market import simuler_marches
from synthetic_finance.performance import OUVERTURE, PORTEFEUILLE, mesurer
from synthetic_finance.universe import construire_univers

BASE = Path(__file__).resolve().parent.parent / "configs" / "base.toml"
GRAINES = range(1, 101)
TWR_ANNUALISE = (0.06, 0.10)
ANNEE_BORNES = (-0.20, 0.25)
ANNEE_EN_COURS = "2026"
ANNEES_COMPLETES = ("2022", "2023", "2024", "2025")
REPLI_MAX = -0.15


def essai(graine: int, limites) -> tuple[float, dict[str, float], float, float]:
    cfg = construire(_fusion(lire_toml(BASE), {"scenario": {"name": "vitrine", "market_seed": graine}}))
    tables = construire_univers(cfg).tables()
    tables |= simuler_marches(cfg, tables).tables()
    tables |= simuler_comportement(cfg, tables, limites).tables()
    tables |= tenir_grand_livre(cfg, tables).tables()
    tables |= mesurer(cfg, tables).tables()
    periodes = {p["period"]: p for p in tables["performance_periods"]
                if p["entity_type"] == "portfolio" and p["entity_id"] == PORTEFEUILLE}
    total = periodes[OUVERTURE]
    annualise = (1 + float(total["twr"])) ** (365.25 / int(total["days"])) - 1
    annees = {a: float(periodes[a]["twr"]) for a in ANNEES_COMPLETES}
    en_cours = float(periodes[ANNEE_EN_COURS]["twr"])
    sommet, repli = 1.0, 0.0
    for l in tables["performance_daily"]:
        if l["entity_type"] == "portfolio" and l["entity_id"] == PORTEFEUILLE:
            indice = 1 + float(l["cumulative_twr"])
            sommet = max(sommet, indice)
            repli = min(repli, indice / sommet - 1)
    return annualise, annees, repli, en_cours


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    limites = lire_plafonds(trouver_plafonds(BASE))
    print(f"Graine principale de {BASE.name} ; graines de marché {GRAINES.start} à {GRAINES.stop - 1}, dans l'ordre")
    print(f"Critère : (a) TWR annualisé dans [{TWR_ANNUALISE[0]:.0%}, {TWR_ANNUALISE[1]:.0%}] ; "
          f"(b) une année de {ANNEES_COMPLETES[0]} à {ANNEES_COMPLETES[-1]} < 0 ; (c) repli < {REPLI_MAX:.0%} ; "
          f"(d) chaque année complète dans [{ANNEE_BORNES[0]:.0%}, {ANNEE_BORNES[1]:+.0%}] ; (e) {ANNEE_EN_COURS} > 0")
    print("graine  TWR ann.  " + "  ".join(f"{a:>7}" for a in ANNEES_COMPLETES + (ANNEE_EN_COURS,))
          + "    repli   a b c d e")
    for g in GRAINES:
        annualise, annees, repli, en_cours = essai(g, limites)
        a = TWR_ANNUALISE[0] <= annualise <= TWR_ANNUALISE[1]
        b = min(annees.values()) < 0
        c = repli < REPLI_MAX
        d = all(ANNEE_BORNES[0] <= v <= ANNEE_BORNES[1] for v in annees.values())
        e = en_cours > 0
        print(f"{g:>6}  {annualise:>8.2%}  " + "  ".join(f"{v:>7.2%}" for v in [*annees.values(), en_cours])
              + f"  {repli:>7.2%}   " + " ".join("x" if v else "." for v in (a, b, c, d, e)))
        if a and b and c and d and e:
            print(f"Graine de marché retenue : {g}")
            return 0
    print("Aucune graine retenue : retour au responsable (H5)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
