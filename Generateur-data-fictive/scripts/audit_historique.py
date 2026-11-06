"""Audit de fuite sur tout l'historique d'une révision (tous les commits atteignables, pas seulement l'arbre).

Mêmes familles de motifs que scripts/balayage_fuite.py (listes privées et motifs-prives.txt, lus à l'exécution,
jamais écrits ici), sur chaque fichier texte de chaque commit, partitions figées du modèle décompressées.
N'imprime jamais un motif : seulement la famille, le chemin et le premier commit où le fichier apparaît.
Usage (depuis la racine du projet) : python Generateur-data-fictive/scripts/audit_historique.py . origin/main
Code de sortie 1 si une occurrence est trouvée.
"""
import subprocess
import sys
from pathlib import Path

DEPOT = Path(sys.argv[1])
REV = sys.argv[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import balayage_fuite as b  # noqa: E402

EXT = {".py", ".toml", ".md", ".csv", ".json", ".txt", ".tmdl", ".sql", ".pbip", ".pbir", ".pbism", ".gitignore"}


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(DEPOT), *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    familles = [(l, g, v) for l, g, v in b.motifs() if v]   # listes privées + motifs-prives.txt
    vus: dict[str, tuple[str, str]] = {}
    for c in git("rev-list", REV).split():
        for ligne in git("ls-tree", "-r", c).splitlines():
            meta, chemin = ligne.split("\t", 1)
            sha = meta.split()[2]
            p = Path(chemin)
            if sha in vus or (p.suffix not in EXT and p.name not in EXT) or "RegisteredResources" in chemin:
                continue
            vus[sha] = (c[:7], chemin)
    print(f"Commits : {len(git('rev-list', REV).split())} ; blobs texte distincts : {len(vus)}")
    total = 0
    for sha, (c, chemin) in vus.items():
        try:
            t = git("cat-file", "-p", sha)
        except subprocess.CalledProcessError:
            continue
        textes = {Path(chemin): t}
        if chemin.endswith(".tmdl"):
            try:
                textes |= b.partitions_figees(textes)
            except Exception:  # noqa: BLE001
                pass
        for libelle, genre, valeurs in familles:
            n = b.compter(textes, genre, valeurs)
            if n:
                total += n
                print(f"  FUITE {libelle} : {n} dans {chemin} (1er commit vu {c})")
    print(f"Résultat : {'AUCUNE FUITE' if total == 0 else f'{total} occurrence(s)'}")
    raise SystemExit(1 if total else 0)


main()
