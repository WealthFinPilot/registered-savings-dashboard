"""Mesures (J5).

C2 : TWR de la graine 20261103 recalculé depuis les CSV sans importer performance.py (graines 1 à 20 :
test_performance_seeds.py) ; chaque jour, r × V⁺ de la veille = marché des parts détenues + frais, au résidu d'arrondi
près ; marché plat sans frais, puis avec frais ; un versement d'un million ne crée aucun rendement.
C3 : réconciliation de chaque période et MWR par bissection ; cas limites du MWR.
C4 : contrefactuels (calendrier des flux, rendement de l'indice, marché plat, retrait infaisable) ; politique fixée d'avance.
"""
import numpy as np
import pytest
from conftest import GRAINE, PLAFONDS_SQL, TYPICAL
from criteres_performance import bissection, c, contrefactuel, lire_export, marche, periodes, series, twr

from synthetic_finance.behaviour import simuler_comportement
from synthetic_finance.config import charger
from synthetic_finance.fiscal import lire_plafonds
from synthetic_finance.ledger import tenir_grand_livre
from synthetic_finance.market import simuler_marches
from synthetic_finance.performance import PerformanceError, mesurer, xirr
from synthetic_finance.universe import construire_univers

CFG = charger(TYPICAL, GRAINE)
BORNES, ANNUALISE = CFG.performance["mwr_bounds"], CFG.performance["annualize_min_days"]


@pytest.fixture(scope="module")
def chaine() -> tuple:
    """Graine 20261103, en mémoire : tables jusqu'au comportement compris."""
    cfg = charger(TYPICAL, GRAINE)
    tables = construire_univers(cfg).tables()
    tables |= simuler_marches(cfg, tables).tables()
    return cfg, tables | simuler_comportement(cfg, tables, lire_plafonds(PLAFONDS_SQL)).tables()


@pytest.fixture(scope="module")
def typique(exports_performance) -> dict:
    return lire_export(exports_performance[GRAINE])


def _mesures(cfg, tables: dict) -> dict:
    """Grand livre puis mesures, en mémoire."""
    complet = tables | tenir_grand_livre(cfg, tables).tables()
    return complet | mesurer(cfg, complet).tables()


def _plat(tables: dict, frais: bool) -> dict:
    """VL et indices constants (premier cours de chaque série) ; taux de frais de compte à 0 si « frais » est faux."""
    plat = dict(tables)
    for nom, col, cle in (("fund_prices_daily", "nav_total_return", "fund_id"),
                          ("benchmarks_daily", "index_total_return", "benchmark_id")):
        premier: dict[str, float] = {}
        for l in tables[nom]:
            premier.setdefault(l[cle], l[col])
        plat[nom] = [l | {col: premier[l[cle]]} for l in tables[nom]]
    if not frais:
        plat["funds"] = [f | {"account_fee_low_pct": 0.0, "account_fee_high_pct": 0.0} for f in tables["funds"]]
    return plat


def _fins(t: dict) -> dict[tuple[str, str], dict]:
    fin: dict[tuple[str, str], dict] = {}
    for l in t["performance_daily"]:
        fin[(l["entity_type"], l["entity_id"])] = l
    return fin


# ------------------------------------------------------------------------------------------------
# TWR (C2)
# ------------------------------------------------------------------------------------------------
def test_twr_graine_typique(typique) -> None:
    erreurs, detail = twr(typique)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_twr_rendement_du_marche(typique) -> None:
    erreurs, _, detail = marche(typique)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_twr_marche_plat_sans_frais(chaine) -> None:
    cfg, tables = chaine
    t = _mesures(cfg, _plat(tables, frais=False))
    erreurs, ecarts, detail = marche(t)              # marché nul, frais nuls : |r × V⁺ de la veille| ≤ résidu du jour
    erreurs += twr(t)[0]
    fin = _fins(t)
    pire = {n: max(abs(l["cumulative_twr"]) for e, l in fin.items() if e[0] == n) for n in ("portfolio", "institution", "account")}
    frais = sum(m["amount_cad"] for m in t["external_movements"] if m["movement_type"] == "FRAIS")
    print(f"{detail} ; FRAIS {frais:.2f} $ ; |TWR cumulé| le plus grand à l'arrêté : "
          + ", ".join(f"{n} {x:.1e}" for n, x in pire.items()))
    assert frais == 0 and not erreurs, erreurs[:10]


def test_twr_marche_plat_avec_frais(chaine) -> None:
    cfg, tables = chaine
    t = _mesures(cfg, _plat(tables, frais=True))
    erreurs, ecarts, detail = marche(t)              # marché nul : r × V⁺ de la veille = frais du jour, au résidu près
    erreurs += twr(t)[0]
    # TWR cumulé = Π(1 + frais du jour ÷ V⁺ de la veille) − 1, à la somme des résidus relatifs près
    lignes: dict[tuple[str, str], list[dict]] = {}
    for l in t["performance_daily"]:
        lignes.setdefault((l["entity_type"], l["entity_id"]), []).append(l)
    pire = 0.0
    for e, ls in lignes.items():
        produit, borne = 1.0, 1e-9
        for hier, l in zip(ls, ls[1:]):
            if l["daily_twr"] is not None:
                produit *= 1 + l["fees_cad"] / hier["market_value_cad"]
                borne += ecarts[(e[0], e[1], l["date"])][1] / hier["market_value_cad"]
        ecart = abs(1 + ls[-1]["cumulative_twr"] - produit)
        pire = max(pire, ecart / borne)
        if ecart > borne:
            erreurs.append(f"{e[1]} : 1 + TWR {1 + ls[-1]['cumulative_twr']:.10f} ≠ Π(1 + frais ÷ V) {produit:.10f}")
        if ls[-1]["cumulative_twr"] >= 0:
            erreurs.append(f"{e[1]} : TWR {ls[-1]['cumulative_twr']} ≥ 0 malgré les frais")
    fin = _fins(t)
    print(f"{detail} ; TWR à l'arrêté : " + ", ".join(f"{e[1]} {l['cumulative_twr']:+.4%}" for e, l in fin.items())
          + f" ; écart au produit des frais : pire à {pire:.0%} de sa borne")
    assert not erreurs, erreurs[:10]


def test_twr_versement_sans_saut(chaine) -> None:
    """Un PONCTUEL de 1 000 000 $ sur le compte COMP un jour t tiré (hors fin de mois : les FRAIS du jour portent sur la
    valeur après apport) : r du jour t inchangé au résidu d'arrondi près à tous les niveaux ; ensuite, chaque jour,
    r × V⁺ de la veille = marché des parts détenues + frais (la composition du compte a changé, le rendement suit)."""
    cfg, tables = chaine
    reference = _mesures(cfg, tables)
    comp = next(a for a in reference["accounts"] if a["regime"] == "COMP")
    a = comp["account_id"]
    lignes = [l for l in reference["performance_daily"] if l["entity_type"] == "account" and l["entity_id"] == a]
    jours = sorted({l["date"] for l in reference["performance_daily"]})
    fins_mois = {j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month}
    candidats = [l["date"] for hier, l in zip(lignes, lignes[1:]) if hier["market_value_cad"] > 0 and l["date"] not in fins_mois]
    t = candidats[int(np.random.default_rng(GRAINE).integers(len(candidats)))]
    ajout = dict(movement_id="M99999", date=t, account_id=a, movement_type="PONCTUEL", amount_cad=1_000_000.0, event_id=None)
    variante = _mesures(cfg, tables | {"external_movements": tables["external_movements"] + [ajout]})

    _, e_ref, _ = marche(reference)
    erreurs, e_var, detail = marche(variante)
    r_ref = {(l["entity_type"], l["entity_id"], l["date"]): l for l in reference["performance_daily"]}
    r_var = {(l["entity_type"], l["entity_id"], l["date"]): l for l in variante["performance_daily"]}
    touchees = [("account", a), ("institution", comp["institution_id"]), ("portfolio", "PORTFOLIO")]
    veille = jours[jours.index(t) - 1]
    resume = []
    for e in sorted({(k[0], k[1]) for k in r_ref if k[2] == t}):
        x, y = r_ref[(*e, t)], r_var[(*e, t)]
        v = r_ref[(*e, veille)]["market_value_cad"]
        if e in touchees:
            borne = (e_ref[(*e, t)][1] + e_var[(*e, t)][1]) / v
            resume.append(f"{e[1]} : r {x['daily_twr']:+.8f} → {y['daily_twr']:+.8f} (écart {y['daily_twr'] - x['daily_twr']:+.1e}, "
                          f"borne {borne:.1e}), valeur {x['market_value_cad']:.2f} → {y['market_value_cad']:.2f} $")
            if abs(y["daily_twr"] - x["daily_twr"]) > borne:
                erreurs.append(f"{e[1]} le {t} : saut de {y['daily_twr'] - x['daily_twr']:+.2e} > borne {borne:.2e}")
        elif x["daily_twr"] != y["daily_twr"]:
            erreurs.append(f"{e[1]} le {t} : rendement changé alors que l'entité ne reçoit rien")
    print(f"jour t = {t}, {comp['account_alias']} ; " + " ; ".join(resume) + f" ; variante : {detail}")
    assert not erreurs, erreurs[:10]


# ------------------------------------------------------------------------------------------------
# Réconciliation et MWR (C3)
# ------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def periodes_typiques(typique) -> tuple:
    return periodes(typique, BORNES, ANNUALISE)


def test_reconciliation_graine_typique(periodes_typiques) -> None:
    erreurs, _, detail = periodes_typiques
    print(detail)
    assert not [x for x in erreurs if "MWR" not in x], erreurs[:10]


def test_mwr_graine_typique(periodes_typiques) -> None:
    erreurs, bilan, detail = periodes_typiques
    print(f"motifs {bilan['motifs']}, pire écart à la bissection {bilan['pire_mwr']:.1e}, signes opposés {bilan['opposes']}")
    assert not [x for x in erreurs if "MWR" in x], erreurs[:10]


def test_mwr_cas_limites() -> None:
    """Racine unique, aucun changement de signe, deux racines (10 % et 20 %) : moteur et bissection d'accord."""
    cas = {"simple": [(0.0, -100.0), (1.0, 110.0)], "sans signe": [(0.0, -100.0), (1.0, -10.0)],
           "deux racines": [(0.0, -1.0), (1.0, 2.3), (2.0, -1.32)]}
    for nom, flux in cas.items():
        moteur, test = xirr(flux, BORNES, CFG.performance["mwr_grid"]), bissection(flux, BORNES)
        print(f"{nom} : moteur {moteur}, bissection {test}")
        assert moteur[1] == test[1] and (moteur[0] is None) == (test[0] is None)
        if moteur[0] is not None:
            assert abs(moteur[0] - test[0]) < 1e-9
    assert xirr(cas["simple"], BORNES, 400) == pytest.approx((0.1, "ok"))
    assert xirr(cas["deux racines"], BORNES, 400) == (None, "plusieurs racines")


# ------------------------------------------------------------------------------------------------
# Contrefactuel et non-biais (C4)
# ------------------------------------------------------------------------------------------------
def test_contrefactuel_graine_typique(typique) -> None:
    erreurs, detail = contrefactuel(typique)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_contrefactuel_marche_plat(chaine) -> None:
    cfg, tables = chaine
    t = _mesures(cfg, _plat(tables, frais=True))
    s = series(t)
    fin: dict[tuple[str, str, str], dict] = {}
    for l in t["counterfactual_daily"]:
        fin[(l["entity_type"], l["entity_id"], l["benchmark_id"])] = l
    erreurs = []
    for (typ, ident, b), l in sorted(fin.items()):
        flux = sum(x[2] + x[3] for x in s[(typ, ident)])
        print(f"{ident} × {b} : valeur {l['market_value_cad']:.2f} $, flux nets {flux / 100:.2f} $, TWR {l['cumulative_twr']:+.1e}")
        if c(l["market_value_cad"]) != flux or abs(l["cumulative_twr"]) > 1e-12:
            erreurs.append(f"{ident} × {b}")
    assert not erreurs, erreurs


def test_contrefactuel_retrait_infaisable(chaine) -> None:
    cfg, tables = chaine
    complet = tables | tenir_grand_livre(cfg, tables).tables()
    m = next(x for x in complet["external_movements"] if x["movement_type"] == "PAC")
    retrait = dict(m, movement_id="M99999", movement_type="RETRAIT", amount_cad=-1_000_000.0, event_id=None)
    with pytest.raises(PerformanceError, match="retrait") as e:
        mesurer(cfg, complet | {"external_movements": complet["external_movements"] + [retrait]})
    print(f"refus explicite : {e.value}")


def test_biais_politique_fixee_d_avance(typique) -> None:
    """La politique de chaque institution (cibles initiales du J1) date d'avant son premier flux externe."""
    erreurs = []
    for i in sorted({a["institution_id"] for a in typique["accounts"]}):
        date_cible = min(l["effective_date"] for l in typique["allocation_targets_history"]
                         if l["level"] == "institution" and l["institution_id"] == i)
        comptes = {a["account_id"] for a in typique["accounts"] if a["institution_id"] == i}
        premier = min(m["date"] for m in typique["external_movements"] if m["account_id"] in comptes
                      and m["movement_type"] in ("PAC", "PONCTUEL"))
        compo = next(b["composition"] for b in typique["benchmarks"] if b["benchmark_id"] == f"R-POL-{i}")
        print(f"R-POL-{i} : {compo} ; premier apport le {premier}")
        if not (date_cible <= premier and compo.startswith(f"cibles du {date_cible.isoformat()}")):
            erreurs.append(f"R-POL-{i} : cibles du {date_cible}, premier apport le {premier}")
    assert not erreurs, erreurs
