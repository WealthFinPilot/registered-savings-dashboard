"""Reproductibilité (J1 C3, J2 C4, J3 C4, J4 C4, J5 C4, J6 C4) : même graine et même configuration -> CSV identiques octet pour
octet, y compris d'un processus à l'autre (CLI) ; autre graine -> univers et marchés différents ; VL
indépendantes des comptes ; univers inchangé par l'étape markets."""
import hashlib
import json
import subprocess
from collections import Counter
import sys
from pathlib import Path

from conftest import GRAINE, TYPICAL, generer, lire


def empreintes(dossier: Path) -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((dossier / "data").glob("*.csv"))}


# J6b : les repères de catégorie (R-CAT-*) s'ajoutent à benchmarks.csv et benchmarks_daily.csv (contrat J6b, H4).
# Contre un commit antérieur, ces deux fichiers se comparent sans leurs lignes de catégorie : tout le reste, octet
# pour octet, et les lignes retirées sont toutes des R-CAT-.
REPERES = ("benchmarks.csv", "benchmarks_daily.csv")


def empreinte_sans_categories(dossier: Path, nom: str) -> str:
    contenu = (dossier / "data" / nom).read_bytes()
    if nom not in REPERES:
        return hashlib.sha256(contenu).hexdigest()
    lignes = contenu.splitlines(keepends=True)
    return hashlib.sha256(b"".join(l for l in lignes if b"R-CAT-" not in l)).hexdigest()


def cli(dossier: Path, seed: int) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(TYPICAL),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "universe"], check=True,
                   capture_output=True)


def test_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli(tmp_path / "a", GRAINE)
    cli(tmp_path / "b", GRAINE)
    a, b = empreintes(tmp_path / "a"), empreintes(tmp_path / "b")
    assert len(a) == 7 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")
    ma, mb = (json.loads((tmp_path / x / "manifest.json").read_text(encoding="utf-8")) for x in "ab")
    assert ma["config_hash"] == mb["config_hash"] and ma["seed"] == mb["seed"] == GRAINE


def test_meme_graine_en_memoire(tmp_path: Path) -> None:
    assert empreintes(generer(tmp_path / "a")) == empreintes(generer(tmp_path / "b"))


def test_autre_graine_autre_univers(tmp_path: Path) -> None:
    a, b = empreintes(generer(tmp_path / "a")), empreintes(generer(tmp_path / "b", GRAINE + 1))
    differents = [f for f in a if a[f] != b[f]]
    assert len(differents) >= 5, differents
    ma, mb = (json.loads((tmp_path / x / "manifest.json").read_text(encoding="utf-8")) for x in "ab")
    assert ma["config_hash"] != mb["config_hash"]      # la graine fait partie de la configuration


# ------------------------------------------------------------------------------------------------
# Marchés (J2, C4)
# ------------------------------------------------------------------------------------------------
MARCHE = ("benchmarks.csv", "benchmarks_daily.csv", "fund_prices_daily.csv", "market_regimes_daily.csv")


def cli_marche(dossier: Path, seed: int, config: Path = TYPICAL) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(config),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "markets"], check=True, capture_output=True)


def test_marche_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli_marche(tmp_path / "a", GRAINE)
    cli_marche(tmp_path / "b", GRAINE)
    a, b = empreintes(tmp_path / "a"), empreintes(tmp_path / "b")
    assert len(a) == 11 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")


def test_marche_autre_graine_autres_vl(tmp_path: Path) -> None:
    a = empreintes(generer(tmp_path / "a", etape="markets"))
    b = empreintes(generer(tmp_path / "b", GRAINE + 1, etape="markets"))
    differents = [f for f in MARCHE if a[f] != b[f]]
    print(f"graine {GRAINE + 1} : fichiers de marché différents {differents}")
    assert {"fund_prices_daily.csv", "benchmarks_daily.csv", "market_regimes_daily.csv"} <= set(differents)


def test_vl_independantes_des_comptes(tmp_path: Path) -> None:
    """Poids des comptes et délais d'ouverture changés : les comptes et leurs cibles bougent, les VL non.
    Le moteur de marché ne lit ni les comptes ni leurs allocations."""
    variante = tmp_path / "variante.toml"
    variante.write_text(f'extends = "{TYPICAL.as_posix()}"\n[policy]\naccount_weight_sigma = 0.9\n'
                        '[accounts]\naccount_delay_months = 4\n', encoding="utf-8")
    a = empreintes(generer(tmp_path / "a", etape="markets"))
    b = empreintes(generer(tmp_path / "b", config=variante, etape="markets"))
    changes = sorted(f for f in a if a[f] != b[f])
    print(f"fichiers modifiés par la variante : {changes}")
    assert {"accounts.csv", "allocation_targets_history.csv"} <= set(changes)
    assert a["fund_prices_daily.csv"] == b["fund_prices_daily.csv"]
    assert a["funds.csv"] == b["funds.csv"] and a["fund_exposures.csv"] == b["fund_exposures.csv"]


def test_univers_inchange_par_l_etape_marches(tmp_path: Path) -> None:
    u = empreintes(generer(tmp_path / "u"))
    m = empreintes(generer(tmp_path / "m", etape="markets"))
    assert len(u) == 7 and all(m[f] == h for f, h in u.items())
    print("7 CSV de l'univers identiques entre --stage universe et --stage markets")


# ------------------------------------------------------------------------------------------------
# Comportement (J3, C4)
# ------------------------------------------------------------------------------------------------
COMPORTEMENT = ("contribution_room.csv", "events.csv", "external_movements.csv", "persona.csv", "tax_limits.csv")


def cli_comportement(dossier: Path, seed: int) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(TYPICAL),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "behaviour"], check=True, capture_output=True)


def test_comportement_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli_comportement(tmp_path / "a", GRAINE)
    cli_comportement(tmp_path / "b", GRAINE)
    a, b = empreintes(tmp_path / "a"), empreintes(tmp_path / "b")
    assert len(a) == 16 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")


def test_comportement_autre_graine_autres_mouvements(tmp_path: Path) -> None:
    a = empreintes(generer(tmp_path / "a", etape="behaviour"))
    b = empreintes(generer(tmp_path / "b", GRAINE + 1, etape="behaviour"))
    differents = [f for f in COMPORTEMENT if a[f] != b[f]]
    print(f"graine {GRAINE + 1} : fichiers de comportement différents {differents}")
    assert {"events.csv", "external_movements.csv", "contribution_room.csv", "persona.csv"} <= set(differents)
    assert a["tax_limits.csv"] == b["tax_limits.csv"]          # mêmes plafonds publics, quelle que soit la graine


def test_univers_et_marches_inchanges_par_l_etape_comportement(tmp_path: Path) -> None:
    """Les 10 CSV des étapes universe et markets sont identiques octet pour octet ; allocation_targets_history
    commence par les lignes de l'étape markets (cibles du J1), les révisions du J3 viennent après."""
    m = generer(tmp_path / "m", etape="markets")
    c = generer(tmp_path / "c", etape="behaviour")
    em, ec = empreintes(m), empreintes(c)
    autres = [f for f in em if f != "allocation_targets_history.csv"]
    assert len(autres) == 10 and all(em[f] == ec[f] for f in autres)
    avant = (m / "data" / "allocation_targets_history.csv").read_text(encoding="utf-8")
    apres = (c / "data" / "allocation_targets_history.csv").read_text(encoding="utf-8")
    assert apres.startswith(avant) and len(apres) > len(avant)
    print(f"10 CSV identiques ; allocation_targets_history : {avant.count(chr(10))} lignes du J1 en tête, "
          f"{apres.count(chr(10)) - avant.count(chr(10))} lignes de révision ajoutées")


# ------------------------------------------------------------------------------------------------
# Grand livre (J4, C4)
# ------------------------------------------------------------------------------------------------
GRAND_LIVRE = ("account_values_daily.csv", "internal_trades.csv", "positions_daily.csv")


def cli_grand_livre(dossier: Path, seed: int) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(TYPICAL),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "ledger"], check=True, capture_output=True)


def test_grand_livre_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli_grand_livre(tmp_path / "a", GRAINE)
    cli_grand_livre(tmp_path / "b", GRAINE)
    a, b = empreintes(tmp_path / "a"), empreintes(tmp_path / "b")
    assert len(a) == 19 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")


def test_grand_livre_autre_graine_autres_ordres(tmp_path: Path) -> None:
    a = empreintes(generer(tmp_path / "a", etape="ledger"))
    b = empreintes(generer(tmp_path / "b", GRAINE + 1, etape="ledger"))
    differents = [f for f in GRAND_LIVRE if a[f] != b[f]]
    print(f"graine {GRAINE + 1} : fichiers du grand livre différents {differents}")
    assert differents == list(GRAND_LIVRE)


def test_j1_a_j3_inchanges_par_l_etape_grand_livre(tmp_path: Path) -> None:
    """Les CSV des étapes universe et markets, et ceux du comportement hors events et external_movements, sont
    identiques octet pour octet. events et external_movements : le contenu du J3 est intact, hors identifiants
    (renumérotés dans l'ordre chronologique) ; le grand livre n'ajoute que des rééquilibrages et des FRAIS."""
    c = generer(tmp_path / "c", etape="behaviour")
    g = generer(tmp_path / "g", etape="ledger")
    ec, eg = empreintes(c), empreintes(g)
    octet = [f for f in ec if f not in ("events.csv", "external_movements.csv")]
    assert len(octet) == 14 and all(ec[f] == eg[f] for f in octet)

    def contenu(dossier: Path) -> tuple[list, list]:
        evs = lire(dossier, "events")
        cle = {e["event_id"]: (e["date"], e["event_type"], e["account_id"], e["description"]) for e in evs}
        sans_id = [{k: v for k, v in e.items() if k != "event_id"} for e in evs if e["event_type"] != "reequilibrage"]
        mvts = [(m["date"], m["account_id"], m["movement_type"], m["amount_cad"], cle[m["event_id"]])
                for m in lire(dossier, "external_movements") if m["movement_type"] != "FRAIS"]
        return sans_id, mvts

    (ev_c, mv_c), (ev_g, mv_g) = contenu(c), contenu(g)
    assert ev_c == ev_g and mv_c == mv_g
    ajouts = Counter(e["event_type"] for e in lire(g, "events")) - Counter(e["event_type"] for e in lire(c, "events"))
    frais = sum(1 for m in lire(g, "external_movements") if m["movement_type"] == "FRAIS")
    print(f"14 CSV identiques ; {len(ev_c)} événements et {len(mv_c)} mouvements du J3 identiques hors identifiants ; "
          f"ajoutés : {dict(ajouts)}, {frais} FRAIS")


# ------------------------------------------------------------------------------------------------
# Mesures (J5, C4)
# ------------------------------------------------------------------------------------------------
MESURES = ("counterfactual_daily.csv", "performance_daily.csv", "performance_periods.csv")
J4 = "c6288c3"                                      # commit du J4 : sorties de référence de la graine 20261103


def cli_performance(dossier: Path, seed: int) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(TYPICAL),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "performance"], check=True, capture_output=True)


def test_performance_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli_performance(tmp_path / "a", GRAINE)
    cli_performance(tmp_path / "b", GRAINE)
    a, b = empreintes(tmp_path / "a"), empreintes(tmp_path / "b")
    assert len(a) == 22 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")


def test_j1_a_j4_inchanges_par_l_etape_performance(tmp_path: Path) -> None:
    """Les 19 CSV de l'étape ledger sont identiques octet pour octet à ceux de l'étape performance, et à ceux du commit
    du J4 (blobs relus par git show) : les mesures ne modifient aucune table."""
    dg = generer(tmp_path / "g", etape="ledger")
    g = empreintes(dg)
    p = empreintes(generer(tmp_path / "p", etape="performance"))
    assert len(g) == 19 and all(p[f] == h for f, h in g.items()) and set(p) - set(g) == set(MESURES)
    racine = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=Path(__file__).parent, check=True,
                            capture_output=True, text=True).stdout.strip()
    differents = []
    for f, h in sorted(g.items()):
        blob = subprocess.run(["git", "show", f"{J4}:Generateur-data-fictive/outputs/typical_seed_20261103/data/{f}"],
                              cwd=racine, check=True, capture_output=True).stdout
        if hashlib.sha256(blob).hexdigest() != empreinte_sans_categories(dg, f):
            differents.append(f)
    print(f"19 CSV identiques entre --stage ledger et --stage performance ; contre {J4} : "
          f"{'tous identiques' if not differents else differents} (repères hors R-CAT-) ; ajoutés : {', '.join(MESURES)}")
    assert not differents


# ------------------------------------------------------------------------------------------------
# Adaptateur (J6, C4)
# ------------------------------------------------------------------------------------------------
J5 = "d6972b9"                                      # commit du J5 : sorties de référence de la graine 20261103


def empreintes_adaptateur(dossier: Path) -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((dossier / "finance_ve01").glob("*.csv"))}


def cli_adaptateur(dossier: Path, seed: int) -> None:
    subprocess.run([sys.executable, "-m", "synthetic_finance", "generate", "--config", str(TYPICAL),
                    "--seed", str(seed), "--out", str(dossier), "--stage", "adapter"], check=True, capture_output=True)


def test_adaptateur_meme_graine_deux_processus(tmp_path: Path) -> None:
    cli_adaptateur(tmp_path / "a", GRAINE)
    cli_adaptateur(tmp_path / "b", GRAINE)
    a, b = empreintes_adaptateur(tmp_path / "a"), empreintes_adaptateur(tmp_path / "b")
    assert len(a) == 19 and a == b
    for f, h in a.items():
        print(f"{f:<32} {h}")


def test_adaptateur_autre_graine_autres_distributions(tmp_path: Path) -> None:
    a = empreintes_adaptateur(generer(tmp_path / "a", etape="adapter"))
    b = empreintes_adaptateur(generer(tmp_path / "b", GRAINE + 1, etape="adapter"))
    differents = sorted(f for f in a if a[f] != b[f])
    print(f"graine {GRAINE + 1} : fichiers différents {differents}")
    assert {"distributions.csv", "fait.transaction.csv", "pub.cours.csv"} <= set(differents)
    assert a["ref.nature.csv"] == b["ref.nature.csv"] and a["ref.risque.csv"] == b["ref.risque.csv"]


def test_j1_a_j5_inchanges_par_l_etape_adaptateur(tmp_path: Path) -> None:
    """Les 22 CSV de l'étape performance sont identiques octet pour octet à ceux de l'étape adapter, et à ceux du commit
    du J5 (blobs relus par git show) : l'adaptateur n'écrit que dans finance_ve01/."""
    dp = generer(tmp_path / "p", etape="performance")
    p = empreintes(dp)
    a = empreintes(generer(tmp_path / "a", etape="adapter"))
    assert len(p) == 22 and p == a
    racine = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=Path(__file__).parent, check=True,
                            capture_output=True, text=True).stdout.strip()
    differents = []
    for f, h in sorted(p.items()):
        blob = subprocess.run(["git", "show", f"{J5}:Generateur-data-fictive/outputs/typical_seed_20261103/data/{f}"],
                              cwd=racine, check=True, capture_output=True).stdout
        if hashlib.sha256(blob).hexdigest() != empreinte_sans_categories(dp, f):
            differents.append(f)
    print(f"22 CSV identiques entre --stage performance et --stage adapter ; contre {J5} : "
          f"{'tous identiques' if not differents else differents} (repères hors R-CAT-)")
    assert not differents
