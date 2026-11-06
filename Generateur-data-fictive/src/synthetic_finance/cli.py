"""Interface en ligne de commande : generate, validate, report.

  python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 \
      --out outputs/typical_seed_20261103 --stage markets
  python -m synthetic_finance validate --path outputs/typical_seed_20261103
  python -m synthetic_finance report --path outputs/typical_seed_20261103
"""
import argparse
import json
import sys
from pathlib import Path

from .adapter import DOSSIER, AdaptateurError, adapter

from .behaviour import simuler_comportement
from .config import ConfigError, charger
from .export import exporter
from .fiscal import lire_plafonds, trouver_plafonds
from .ledger import GrandLivreError, tenir_grand_livre
from .market import simuler_marches
from .performance import PerformanceError, mesurer
from .report import (ecrire_rapport, ecrire_rapport_comportement, ecrire_rapport_grand_livre, ecrire_rapport_marche,
                     ecrire_rapport_performance)
from .universe import construire_univers
from .validation import valider

ETAPES: tuple[str, ...] = ("universe", "markets", "behaviour", "ledger", "performance", "adapter")   # étapes livrées, dans l'ordre


def generer(config: Path, seed: int | None, sortie: Path, etape: str, plafonds: Path | None = None) -> list[str]:
    """Exécute la chaîne jusqu'à « etape » comprise ; rend la liste des étapes exécutées. Les plafonds
    fiscaux (étape behaviour) sont lus dans « plafonds », par défaut le sql/plafonds.sql du projet
    trouvé au-dessus de la configuration."""
    if etape not in ETAPES:
        raise ConfigError(f"--stage {etape} : étape pas encore implémentée (disponibles : {', '.join(ETAPES)})")
    etapes = list(ETAPES[:ETAPES.index(etape) + 1])
    cfg = charger(config, seed)
    tables = construire_univers(cfg).tables()
    if "markets" in etapes:
        tables |= simuler_marches(cfg, tables).tables()
    entrees = {}
    if "behaviour" in etapes:
        source = plafonds or trouver_plafonds(Path(config))
        limites = lire_plafonds(source)
        tables |= simuler_comportement(cfg, tables, limites).tables()
        entrees["tax_limits"] = dict(source="sql/plafonds.sql", sha256=limites.sha256)
    if "ledger" in etapes:
        tables |= tenir_grand_livre(cfg, tables).tables()
    if "performance" in etapes:
        tables |= mesurer(cfg, tables).tables()
    exporter(sortie, cfg, tables, etapes, entrees)
    if "adapter" in etapes:
        # L'adaptateur relit les CSV écrits (ce que contrôle la validation) et écrit finance_ve01/ à côté
        lignes = adapter(cfg, sortie)
        chemin = sortie / "manifest.json"
        manifest = json.loads(chemin.read_text(encoding="utf-8"))
        manifest["finance_ve01"] = {n: f"{DOSSIER}/{n}.csv" for n in lignes}
        chemin.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    else:                                    # export précédent d'une étape plus longue : retiré, pas mélangé
        for ancien in (sortie / DOSSIER).glob("*.csv"):
            ancien.unlink()
    ecrire_rapport(sortie)
    if "markets" in etapes:
        ecrire_rapport_marche(sortie)
    if "behaviour" in etapes:
        ecrire_rapport_comportement(sortie)
    if "ledger" in etapes:
        ecrire_rapport_grand_livre(sortie)
    if "performance" in etapes:
        ecrire_rapport_performance(sortie)
    return etapes


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):       # console Windows : accents lisibles sans PYTHONIOENCODING
        flux.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="synthetic_finance", description="Générateur de patrimoine synthétique")
    sous = p.add_subparsers(dest="commande", required=True)
    g = sous.add_parser("generate", help="générer un scénario")
    g.add_argument("--config", type=Path, required=True)
    g.add_argument("--seed", type=int, help="remplace scenario.seed")
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--stage", default="universe", help=f"dernière étape à exécuter, parmi {', '.join(ETAPES)}")
    for nom, aide in (("validate", "valider un dossier d'export"), ("report", "réécrire les rapports")):
        s = sous.add_parser(nom, help=aide)
        s.add_argument("--path", type=Path, required=True)
    a = p.parse_args(argv)

    if a.commande == "generate":
        try:
            etapes = generer(a.config, a.seed, a.out, a.stage)
        except ConfigError as e:
            print(f"Configuration refusée — {e}", file=sys.stderr)
            return 2
        except GrandLivreError as e:
            print(f"Grand livre impossible — {e}", file=sys.stderr)
            return 3
        except PerformanceError as e:
            print(f"Mesures impossibles — {e}", file=sys.stderr)
            return 4
        except AdaptateurError as e:
            print(f"Adaptation impossible — {e}", file=sys.stderr)
            return 5
        print(f"Généré : {a.out} (graine {a.seed if a.seed is not None else 'de la configuration'}, "
              f"étapes {', '.join(etapes)})")
        for f in sorted((a.out / "data").glob("*.csv")):
            print(f"  data/{f.name}")
        print("  manifest.json\n  universe_report.md" + ("\n  market_report.md" if "markets" in etapes else "")
              + ("\n  behaviour_report.md" if "behaviour" in etapes else "")
              + ("\n  ledger_report.md" if "ledger" in etapes else "")
              + ("\n  performance_report.md" if "performance" in etapes else ""))
        return 0
    if a.commande == "validate":
        r = valider(a.path)
        for c in r["checks"]:
            print(f"[{c['status'].upper():4}] {c['name']} — {c['detail']}")
        for w in r["warnings"]:
            print(f"[DIAG] {w}")
        print(f"Validation : {'réussie' if r['passed'] else 'ÉCHEC'} ({a.path / 'validation.json'})")
        return 0 if r["passed"] else 1
    print(f"Rapport : {ecrire_rapport(a.path)}")
    if (a.path / "data" / "fund_prices_daily.csv").is_file():
        print(f"Rapport : {ecrire_rapport_marche(a.path)}")
    if (a.path / "data" / "external_movements.csv").is_file():
        print(f"Rapport : {ecrire_rapport_comportement(a.path)}")
    if (a.path / "data" / "internal_trades.csv").is_file():
        print(f"Rapport : {ecrire_rapport_grand_livre(a.path)}")
    if (a.path / "data" / "performance_daily.csv").is_file():
        print(f"Rapport : {ecrire_rapport_performance(a.path)}")
    return 0
