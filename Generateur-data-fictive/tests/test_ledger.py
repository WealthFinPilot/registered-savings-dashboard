"""Grand livre (J4).

C2 : comptabilité de la graine 20261103 recalculée depuis les CSV sans importer ledger.py (graines 1 à 20 :
test_ledger_seeds.py) ; un retrait infaisable arrête le moteur.
C3 : frais de compte recalculés au cent ; marché plat sans frais, puis avec frais.
C4 : rééquilibrages imparfaits et inertie ; aucune anticipation (21 graines, coupures tirées, jour et veille de
chaque rééquilibrage, trois marchés de remplacement) ; sensibilité à la dérive lue la veille.
"""
import datetime as dt
from collections import Counter

import numpy as np
import pytest
from conftest import GRAINE, GRAINES_COMPORTEMENT, PLAFONDS_SQL, TYPICAL
from criteres_grand_livre import RESIDU_CENT, comptabilite, frais_attendus, lire_export

from synthetic_finance.behaviour import simuler_comportement
from synthetic_finance.config import charger
from synthetic_finance.fiscal import lire_plafonds
from synthetic_finance.ledger import GrandLivreError, regards, tenir_grand_livre
from synthetic_finance.market import simuler_marches
from synthetic_finance.universe import construire_univers


def _base(graine: int) -> tuple:
    """Configuration et tables de l'univers et des marchés (entrées du comportement)."""
    cfg = charger(TYPICAL, graine)
    tables = construire_univers(cfg).tables()
    tables |= simuler_marches(cfg, tables).tables()
    return cfg, tables


@pytest.fixture(scope="module")
def chaine() -> tuple:
    """Graine 20261103, en mémoire : tables jusqu'au comportement compris."""
    cfg, tables = _base(GRAINE)
    return cfg, tables | simuler_comportement(cfg, tables, lire_plafonds(PLAFONDS_SQL)).tables()


@pytest.fixture(scope="module")
def typique(exports_grand_livre) -> dict:
    return lire_export(exports_grand_livre[GRAINE])


# ------------------------------------------------------------------------------------------------
# Comptabilité (C2)
# ------------------------------------------------------------------------------------------------
def test_compta_graine_typique(typique) -> None:
    erreurs, detail = comptabilite(typique)
    print(detail)
    assert not erreurs, erreurs[:10]


def test_compta_retrait_infaisable(chaine) -> None:
    cfg, tables = chaine
    mvts = [dict(m) for m in tables["external_movements"]]
    m = next(x for x in mvts if x["movement_type"] == "RETRAIT")
    m["amount_cad"] = -1_000_000.0
    with pytest.raises(GrandLivreError, match=r"retrait .* demandés") as e:
        tenir_grand_livre(cfg, tables | {"external_movements": mvts})
    print(f"refus explicite : {e.value}")


# ------------------------------------------------------------------------------------------------
# Frais et marché plat (C3)
# ------------------------------------------------------------------------------------------------
def test_frais_recalcules(typique) -> None:
    cfg = charger(TYPICAL, GRAINE)
    attendus = frais_attendus(typique, cfg.fee_tier_threshold_cad)
    frais = [m for m in typique["external_movements"] if m["movement_type"] == "FRAIS"]
    exportes = {(m["date"], m["account_id"]): round(-m["amount_cad"] * 100) for m in frais}
    differents = sorted(k for k in set(attendus) | set(exportes) if attendus.get(k) != exportes.get(k))
    print(f"{len(frais)} FRAIS, {sum(exportes.values()) / 100:.2f} $ ; recalculés : {len(attendus)}, "
          f"{sum(attendus.values()) / 100:.2f} $ ; écarts : {differents[:5] or 'aucun'}")
    assert not differents


def _plat(tables: dict, frais: bool) -> dict:
    """VL constantes (le premier cours de chaque fonds) ; taux de frais de compte à 0 si « frais » est faux."""
    premier: dict[str, float] = {}
    for l in tables["fund_prices_daily"]:
        premier.setdefault(l["fund_id"], l["nav_total_return"])
    plat = tables | {"fund_prices_daily": [l | {"nav_total_return": premier[l["fund_id"]]} for l in tables["fund_prices_daily"]]}
    if not frais:
        plat["funds"] = [f | {"account_fee_low_pct": 0.0, "account_fee_high_pct": 0.0} for f in tables["funds"]]
    return plat


def _bilan_plat(cfg, g) -> tuple[float, float, float]:
    """Valeur à l'arrêté, borne d'arrondi (résidus des ordres + arrondi au cent des positions), total des FRAIS."""
    valeur = sum(v["total_value_cad"] for v in g.account_values_daily if v["date"] == cfg.end_date)
    borne = sum(abs(o["units"] * o["unit_price"] - o["gross_amount_cad"]) for o in g.internal_trades)
    borne += RESIDU_CENT * sum(1 for p in g.positions_daily if p["date"] == cfg.end_date) + 1e-6
    return valeur, borne, -sum(m["amount_cad"] for m in g.external_movements if m["movement_type"] == "FRAIS")


def test_marche_plat_sans_frais(chaine) -> None:
    cfg, tables = chaine
    g = tenir_grand_livre(cfg, _plat(tables, frais=False))
    valeur, borne, frais = _bilan_plat(cfg, g)
    flux = sum(m["amount_cad"] for m in tables["external_movements"])
    print(f"valeur {valeur:.2f} $, flux nets {flux:.2f} $, écart {valeur - flux:+.4f} $ (borne {borne:.4f} $), FRAIS {frais:.2f} $")
    assert frais == 0 and abs(valeur - flux) <= borne


def test_marche_plat_avec_frais(chaine) -> None:
    cfg, tables = chaine
    g = tenir_grand_livre(cfg, _plat(tables, frais=True))
    valeur, borne, frais = _bilan_plat(cfg, g)
    flux = sum(m["amount_cad"] for m in tables["external_movements"])

    def par_type(mvts: list[dict]) -> dict[str, float]:
        return {k: round(sum(m["amount_cad"] for m in mvts if m["movement_type"] == k), 2) for k in ("PAC", "PONCTUEL", "RETRAIT")}
    print(f"valeur {valeur:.2f} $ = flux nets {flux:.2f} $ − FRAIS {frais:.2f} $, écart {valeur - flux + frais:+.4f} $ "
          f"(borne {borne:.4f} $) ; apports et retraits {par_type(g.external_movements)}")
    assert frais > 0 and abs(valeur - (flux - frais)) <= borne
    assert par_type(g.external_movements) == par_type(tables["external_movements"])   # FRAIS hors apports et retraits


# ------------------------------------------------------------------------------------------------
# Rééquilibrages (C4)
# ------------------------------------------------------------------------------------------------
def _derive(valeurs: dict[str, float], cible: dict[str, float]) -> float:
    total = sum(valeurs.values())
    return 0.0 if total <= 0 else 50 * sum(abs(valeurs.get(f, 0) / total - cible.get(f, 0) / 100)
                                           for f in set(valeurs) | set(cible))


def _cibles(t: dict) -> dict[str, list[tuple[dt.date, dict[str, float]]]]:
    groupes: dict[tuple[str, dt.date], dict[str, float]] = {}
    for l in t["allocation_targets_history"]:
        if l["level"] == "account":
            groupes.setdefault((l["account_id"], l["effective_date"]), {})[l["fund_id"]] = l["target_weight"]
    sortie: dict[str, list] = {}
    for (a, d), c in sorted(groupes.items()):
        sortie.setdefault(a, []).append((d, c))
    return sortie


def _en_vigueur(cibles: dict, a: str, jour: dt.date) -> dict[str, float]:
    return [c for d, c in cibles[a] if d <= jour][-1]


def test_reequilibrages_imparfaits(typique) -> None:
    cfg = charger(TYPICAL, GRAINE)
    comptes = {c["account_id"]: c for c in typique["accounts"]}
    seuil, controles = regards(cfg, comptes)
    cibles = _cibles(typique)
    valeurs: dict[tuple[dt.date, str], dict[str, float]] = {}
    for p in typique["positions_daily"]:
        valeurs.setdefault((p["date"], p["account_id"]), {})[p["fund_id"]] = p["market_value_cad"]
    jours = sorted({d for d, _ in valeurs})
    veille = dict(zip(jours[1:], jours))
    revisions = {(e["account_id"], e["date"]) for e in typique["events"]
                 if e["event_type"] in ("revue_annuelle", "ajout_fonds", "prudence_marche", "retour_cible")}
    reeq = [e for e in typique["events"] if e["event_type"] == "reequilibrage"]
    jours_reeq = {(e["account_id"], e["date"]) for e in reeq}

    erreurs, incomplets = [], []
    for e in reeq:
        a, d = e["account_id"], e["date"]
        vise = _en_vigueur(cibles, a, d)
        avant, apres = _derive(valeurs.get((veille[d], a), {}), vise), _derive(valeurs[(d, a)], vise)
        if "dérive de" in e["description"]:
            if a not in controles.get(d, ()) or avant < seuil[a]:
                erreurs.append(f"{e['event_id']} : dérive {avant:.1f} à la veille, seuil {seuil[a]}, regard prévu : {a in controles.get(d, ())}")
        elif (a, d) not in revisions:
            erreurs.append(f"{e['event_id']} : aucun changement de cible du J3 le {d}")
        if "100% de l'écart" not in e["scenario_impact"] and apres > 0:
            incomplets.append(f"{e['event_id']} {comptes[a]['account_alias']} {avant:.1f} → {apres:.1f}")

    # Inertie : jours consécutifs où la dérive de clôture dépasse le seuil du compte sans rééquilibrage ce jour-là
    plus_longue: tuple[int, str, dt.date | None] = (0, "", None)
    for a in comptes:
        serie, debut = 0, None
        for j in jours:
            if (j, a) in valeurs and _derive(valeurs[(j, a)], _en_vigueur(cibles, a, j)) > seuil[a] and (a, j) not in jours_reeq:
                serie, debut = serie + 1, debut or j
                plus_longue = max(plus_longue, (serie, a, debut), key=lambda x: x[0])
            else:
                serie, debut = 0, None
    print(f"{len(reeq)} rééquilibrages, causes {dict(Counter('dérive' if 'dérive de' in e['description'] else 'cible' for e in reeq))} ; "
          f"incomplets : {incomplets} ; plus longue dérive au-delà du seuil laissée sans suite : {plus_longue[0]} jours "
          f"ouvrables ({comptes[plus_longue[1]]['account_alias'] if plus_longue[1] else '—'}, seuil "
          f"{seuil.get(plus_longue[1], '—')} points, depuis le {plus_longue[2]})")
    assert not erreurs, erreurs
    assert incomplets and plus_longue[0] >= 5


def test_reequilibrages_par_annee(exports_grand_livre) -> None:
    derives = 0
    for graine, dossier in exports_grand_livre.items():
        evs = [e for e in lire_export(dossier)["events"] if e["event_type"] == "reequilibrage"]
        par_an = Counter((e["date"].year, "dérive" if "dérive de" in e["description"] else "cible") for e in evs)
        derives += sum(n for (_, c), n in par_an.items() if c == "dérive")
        annees = sorted({a for a, _ in par_an})
        print(f"graine {graine} : " + ("; ".join(f"{a} {par_an[(a, 'cible')]} cible + {par_an[(a, 'dérive')]} dérive"
                                                for a in annees) or "aucun"))
    assert derives > 0


# ------------------------------------------------------------------------------------------------
# Aucune anticipation (C4)
# ------------------------------------------------------------------------------------------------
MARCHE = {"fund_prices_daily": "nav_total_return", "benchmarks_daily": "index_total_return"}


def _variantes(tables: dict, autre: dict) -> dict:
    """Marchés de remplacement à partir de t (VL et repères) : une autre graine, une hausse ×2, un krach ×0,5."""
    def echelle(f: float):
        return lambda nom, t: [l | {MARCHE[nom]: l[MARCHE[nom]] * f} for l in tables[nom] if l["date"] >= t]
    return {"autre graine": lambda nom, t: [l for l in autre[nom] if l["date"] >= t],
            "hausse": echelle(2.0), "krach": echelle(0.5)}


def _remplacer(tables: dict, t: dt.date, apres) -> dict:
    modifiees = dict(tables)
    for nom in MARCHE:
        modifiees[nom] = [l for l in tables[nom] if l["date"] < t] + apres(nom, t)
    return modifiees


def _chaine(cfg, base: dict, plafonds) -> tuple[dict, dict]:
    """Comportement puis grand livre ; rend les sorties du comportement et les tables complètes."""
    comportement = simuler_comportement(cfg, base, plafonds).tables()
    return comportement, base | comportement | tenir_grand_livre(cfg, base | comportement).tables()


def _jusqu_a(g: dict, t: dt.date) -> tuple:
    """Décisions datées au plus tard t (événements ; mouvements, et fonds et sens des ordres du jour t) ; ordres,
    frais, positions et valeurs strictement avant t : le jour t s'exécute à la VL de clôture de t (H1)."""
    frais_t = {m["movement_id"] for m in g["external_movements"] if m["date"] == t and m["movement_type"] == "FRAIS"}
    return ([e for e in g["events"] if e["date"] <= t],
            [m for m in g["external_movements"] if m["date"] < t],
            [{k: v for k, v in m.items() if k != "movement_id"} for m in g["external_movements"]
             if m["date"] == t and m["movement_type"] != "FRAIS"],
            [o for o in g["internal_trades"] if o["date"] < t],
            sorted((o["account_id"], o["fund_id"], o["side"], o["event_id"] or "") for o in g["internal_trades"]
                   if o["date"] == t and o["movement_id"] not in frais_t),
            [p for p in g["positions_daily"] if p["date"] < t],
            [v for v in g["account_values_daily"] if v["date"] < t])


@pytest.mark.parametrize("graine", GRAINES_COMPORTEMENT)
def test_aucune_anticipation_grand_livre(graine: int) -> None:
    cfg, base = _base(graine)
    plafonds = lire_plafonds(PLAFONDS_SQL)
    variantes = _variantes(base, simuler_marches(cfg, base, seed=graine + 1).tables())
    comportement, reference = _chaine(cfg, base, plafonds)
    jours = sorted({l["date"] for l in base["market_regimes_daily"]})
    reeq = [e for e in reference["events"] if e["event_type"] == "reequilibrage"]

    # Coupures : une tirée d'avance dans chaque sixième de l'horizon (graine fixe), puis le jour et la veille de
    # chaque rééquilibrage
    rng = np.random.default_rng(graine)
    coupures = {jours[int(rng.choice(x))] for x in np.array_split(np.arange(1, len(jours)), 6)}
    for e in reeq:
        coupures |= {e["date"], jours[jours.index(e["date"]) - 1]}
    for t in sorted(coupures):
        attendu = _jusqu_a(reference, t)
        for nom, apres in variantes.items():
            _, variante = _chaine(cfg, _remplacer(base, t, apres), plafonds)
            assert attendu == _jusqu_a(variante, t), f"coupure {t}, marché « {nom} »"

    # Sensibilité : des VL qui, dès la veille d'un rééquilibrage dû à la dérive, ramènent les poids du compte sur sa
    # cible le suppriment. La dérive est donc bien lue sur le marché, et la coupure au jour même la borne à la veille.
    # Les ordres de la veille s'exécutent aux VL changées (un fonds acheté la veille vaut son prix d'achat, quelle
    # que soit sa VL) : les facteurs s'ajustent par itérations sur les positions de la variante.
    cibles = _cibles(reference)
    derives = [e for e in reeq if "dérive de" in e["description"]]
    ecartes = 0
    for e in derives:
        a, d = e["account_id"], e["date"]
        v = jours[jours.index(d) - 1]
        vise = _en_vigueur(cibles, a, d)
        positions = reference["positions_daily"]
        facteur: dict[str, float] = {}
        for _ in range(12):
            tenues = {p["fund_id"]: p["market_value_cad"] for p in positions if p["date"] == v and p["account_id"] == a}
            if any(tenues.get(f, 0) <= 0 for f, w in vise.items() if w > 0):
                break                                   # fonds visé non détenu : aucune VL ne ramène la cible
            total = sum(tenues.values())
            for f, x in tenues.items():
                facteur[f] = facteur.get(f, 1.0) * (vise.get(f, 0) / 100 * total / x if vise.get(f, 0) > 0 else 1e-3)
            prix = [l | {"nav_total_return": l["nav_total_return"] * facteur[l["fund_id"]]}
                    if l["date"] >= v and l["fund_id"] in facteur else l for l in base["fund_prices_daily"]]
            g = tenir_grand_livre(cfg, base | comportement | {"fund_prices_daily": prix})
            positions = g.positions_daily
            if not any(x["event_type"] == "reequilibrage" and x["account_id"] == a and x["date"] == d for x in g.events):
                break
        else:
            raise AssertionError(f"{e['event_id']} du {d} insensible aux VL de la veille")
        if not facteur or any(tenues.get(f, 0) <= 0 for f, w in vise.items() if w > 0):
            ecartes += 1
    print(f"graine {graine} : {len(coupures)} coupures × {len(variantes)} marchés ; {len(reeq)} rééquilibrages dont "
          f"{len(derives)} dus à la dérive, {len(derives) - ecartes} supprimés par des VL ramenées sur la cible la veille"
          + (f", {ecartes} écartés (fonds visé non détenu)" if ecartes else ""))
