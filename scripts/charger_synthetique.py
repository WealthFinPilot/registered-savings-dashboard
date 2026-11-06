"""Charge dans finance_ve01 les tables écrites par l'adaptateur du générateur synthétique (J6).

Rejoue sql/schema.sql, sql/plafonds.sql et sql/vues.sql, vide les tables de la vE01, puis charge chaque fichier
<schéma>.<table>.csv de <export>/finance_ve01/ par COPY, dans une seule transaction. Contrôle ensuite le nombre de
lignes de chaque table contre son fichier, les références que les clés étrangères ne couvrent pas, les tables qui
doivent rester vides, et interroge chaque vue rapport.*. Refuse toute base autre que finance_ve01, avant d'écrire.

Usage (depuis la racine, interpréteur de Generateur-data-fictive/.venv, extra « finance ») :
  python scripts/charger_synthetique.py --path Generateur-data-fictive/outputs/vitrine_seed_20261103
Code de sortie : 0 si tous les contrôles passent, 1 sinon, 2 si la base est refusée.
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path

import psycopg

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "Generateur-data-fictive" / "src"))
from synthetic_finance.adapter import DOSSIER, TABLES  # noqa: E402

SQL = RACINE / "sql"
PSQL = Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
BASE = "finance_ve01"                                   # seule base où ce script écrit
# Colonnes au nom neutre dans les fichiers de l'adaptateur -> nom de la colonne dans schema.sql
RENOMMEES = {("ref.symbole", "nom"): "nom_yahoo"}
# Tables vidées avant chargement : celles de l'adaptateur, plus celles qui restent vides (aucun compte à relevé,
# aucun transfert ni saisie hors export) et le journal des chargements
VIDES = ["fait.releve_cotisation", "fait.releve", "ref.transfert_entrant", "ref.transfert_sortant",
         "ref.versement_hors_export", "ref.retrait_hors_export"]
# Références sans clé étrangère dans schema.sql : (libellé, requête qui compte les orphelins)
ORPHELINS = [
    ("fait.transaction.code_fonds hors pub.profil_code",
     "SELECT count(*) FROM fait.transaction t WHERE NOT EXISTS (SELECT 1 FROM pub.profil_code c WHERE c.code_fonds = t.code_fonds)"),
    ("fait.sommaire.code_fonds hors pub.profil_code",
     "SELECT count(*) FROM fait.sommaire s WHERE NOT EXISTS (SELECT 1 FROM pub.profil_code c WHERE c.code_fonds = s.code_fonds)"),
    ("pub.profil_code.code_fa hors ref.fonds",
     "SELECT count(*) FROM pub.profil_code c WHERE NOT EXISTS (SELECT 1 FROM ref.fonds f WHERE f.code_fa = c.code_fa)"),
    ("pub.profil.code_fa hors ref.fonds",
     "SELECT count(*) FROM pub.profil p WHERE NOT EXISTS (SELECT 1 FROM ref.fonds f WHERE f.code_fa = p.code_fa)"),
    ("pub.rapport_annuel.code_fa hors ref.fonds",
     "SELECT count(*) FROM pub.rapport_annuel r WHERE NOT EXISTS (SELECT 1 FROM ref.fonds f WHERE f.code_fa = r.code_fa)"),
    ("ref.symbole sans cours",
     "SELECT count(*) FROM ref.symbole s WHERE NOT EXISTS (SELECT 1 FROM pub.cours c WHERE c.symbole = s.symbole)"),
    ("ref.repere sans cours ajusté",
     "SELECT count(*) FROM ref.repere r WHERE NOT EXISTS (SELECT 1 FROM pub.cours c WHERE c.symbole = r.symbole AND c.cloture_ajustee IS NOT NULL)"),
    ("ref.repere.code_fa hors ref.fonds",
     "SELECT count(*) FROM ref.repere r WHERE NOT EXISTS (SELECT 1 FROM ref.fonds f WHERE f.code_fa = r.code_fa)"),
    ("pub.profil.profil_risque hors ref.risque",
     "SELECT count(*) FROM pub.profil p WHERE NOT EXISTS (SELECT 1 FROM ref.risque r WHERE r.libelle = p.profil_risque)"),
    ("pub.profil_ligne « pays » hors ref.geographie",
     "SELECT count(*) FROM pub.profil_ligne l WHERE l.section = 'pays' AND NOT EXISTS (SELECT 1 FROM ref.geographie g WHERE g.libelle = l.libelle)"),
    ("sous-jacent de pub.profil_ligne hors ref.style",
     "SELECT count(*) FROM pub.profil_ligne l WHERE l.section = 'actuelle' AND l.parent IS NOT NULL AND NOT EXISTS (SELECT 1 FROM ref.style s WHERE s.type = 'sous-jacent' AND s.cle = l.libelle)"),
    ("fait.transaction.libelle hors ref.nature",
     "SELECT count(*) FROM fait.transaction t WHERE NOT EXISTS (SELECT 1 FROM ref.nature n WHERE t.libelle LIKE replace(n.motif, '*', '%') AND n.nature = t.nature AND n.signe = t.signe)"),
    ("fait.transaction : parts_restantes ≠ précédentes ± négociées",
     "SELECT count(*) FROM (SELECT parts_restantes, signe * parts_negociees AS d, lag(parts_restantes, 1, 0) OVER "
     "(PARTITION BY compte_alias, code_fonds ORDER BY rang) AS p FROM fait.transaction) x WHERE p + d <> parts_restantes"),
]


def verifier_base(dsn: str) -> None:
    """Garde-fou : s'arrête (code 2) avant toute écriture si la base n'est pas finance_ve01."""
    with psycopg.connect(dsn) as cx:
        base = cx.execute("SELECT current_database()").fetchone()[0]
    if base != BASE:
        print(f"Base refusée : {base}. Ce script n'écrit que dans {BASE} ; rien n'a été écrit.", file=sys.stderr)
        raise SystemExit(2)


def psql(dbname: str, fichier: Path) -> None:
    subprocess.run([str(PSQL), "-h", "localhost", "-U", "finance", "-d", dbname, "-v", "ON_ERROR_STOP=1",
                    "-q", "-1", "-f", str(fichier)], check=True, cwd=SQL)


def lignes_csv(chemin: Path) -> int:
    with chemin.open(encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def charger(cur, table: str, chemin: Path) -> None:
    colonnes = ", ".join(RENOMMEES.get((table, c), c) for c, _ in TABLES[table])
    with cur.copy(f"COPY {table} ({colonnes}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copie, \
            chemin.open("rb") as f:
        while bloc := f.read(1 << 20):
            copie.write(bloc)


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--path", type=Path, required=True, help="dossier d'export du générateur")
    p.add_argument("--dbname", default=BASE, help="base visée ; toute autre que finance_ve01 est refusée")
    a = p.parse_args(argv)
    dsn = f"host=localhost port=5432 dbname={a.dbname} user=finance"
    verifier_base(dsn)
    source = a.path / DOSSIER
    fichiers = {t: source / f"{t}.csv" for t in TABLES}
    absents = [str(f) for f in fichiers.values() if not f.is_file()]
    if absents:
        print(f"Fichiers absents : {absents}", file=sys.stderr)
        return 1
    for f in ("schema.sql", "plafonds.sql", "vues.sql"):
        psql(a.dbname, SQL / f)
    print(f"Rejoués dans {BASE} : sql/schema.sql, sql/plafonds.sql, sql/vues.sql")

    echecs = 0
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(reversed(list(TABLES)))}, {', '.join(VIDES)}, fait.chargement")
        for table, chemin in fichiers.items():
            charger(cur, table, chemin)
        n_tr = cur.execute("SELECT count(*) FROM fait.transaction").fetchone()[0]
        cur.execute("INSERT INTO fait.chargement (historiques, rapports, lignes) VALUES "
                    "((SELECT count(*) FROM fait.historique), (SELECT count(DISTINCT compte_alias) FROM fait.sommaire), %s)",
                    (n_tr,))
    print(f"Chargé : {len(fichiers)} tables depuis {source.relative_to(RACINE) if source.is_relative_to(RACINE) else source}")

    with psycopg.connect(dsn) as cx:
        print("\nLignes par table (base / fichier)")
        for table, chemin in fichiers.items():
            n, m = cx.execute(f"SELECT count(*) FROM {table}").fetchone()[0], lignes_csv(chemin)
            echecs += n != m
            print(f"  [{'PASS' if n == m else 'FAIL'}] {table} : {n} / {m}")
        print("\nTables qui restent vides")
        for table in VIDES:
            n = cx.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            echecs += n != 0
            print(f"  [{'PASS' if n == 0 else 'FAIL'}] {table} : {n}")
        print("\nRéférences sans clé étrangère (orphelins)")
        for libelle, requete in ORPHELINS:
            n = cx.execute(requete).fetchone()[0]
            echecs += n != 0
            print(f"  [{'PASS' if n == 0 else 'FAIL'}] {libelle} : {n}")
        print("\nVues rapport.* (SELECT count(*))")
        vues = [v for (v,) in cx.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'rapport' "
                                         "ORDER BY table_name").fetchall()]
        for v in vues:
            try:
                n = cx.execute(f"SELECT count(*) FROM rapport.{v}").fetchone()[0]
                print(f"  [PASS] rapport.{v} : {n}")
            except psycopg.Error as e:
                cx.rollback()
                echecs += 1
                print(f"  [FAIL] rapport.{v} : {type(e).__name__} {e}".rstrip())
    print(f"\nRésultat : {'tous les contrôles passent' if echecs == 0 else f'{echecs} ÉCHEC(S)'} ({len(vues)} vues)")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
