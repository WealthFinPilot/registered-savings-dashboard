"""Balayage de fuite du générateur : aucun nom, code ou symbole réel dans le code, les configurations,
les tests, la documentation et les exports ; aucun accès réseau ni lecture hors du dossier dans src/.

Les motifs tirés de la v1 ne sont écrits nulle part : ils sont lus à l'exécution, en lecture seule, dans
les listes de référence de la v1 (institutions, numéros de compte, codes, noms et symboles de fonds,
indices de repère) et dans les noms de fichiers des cours de FNB réels de la vE01. Seule exception :
les familles d'indices boursiers publics (INDICES_REELS), vocabulaire public sans lien avec la v1,
listées ici parce que les repères synthétiques (J2) ne doivent porter le nom d'aucun indice réel. La
sortie n'imprime que des comptes d'occurrences, jamais un motif.

Périmètre « projet » (`--perimetre projet`) : le rapport livré (hors `StaticResources/RegisteredResources`,
base64 du thème), `sql/`, `scripts/`, `docs/`, `jalons/` et `README.md` de la racine. Les partitions figées par `scripts/figer.py`
(JSON en deflate brut, base64) sont décompressées avant la recherche : sans cela, elles seraient invisibles.

Usage (depuis Generateur-data-fictive/) : python scripts/balayage_fuite.py [--perimetre generateur|projet] ;
code de sortie 1 si fuite.
"""
import argparse
import ast
import base64
import csv
import re
import sys
import zlib
from pathlib import Path

ICI = Path(__file__).resolve().parent.parent            # Generateur-data-fictive/
PROJET = ICI.parent                                     # DashBoard-Finance-vE01/
V1 = PROJET.parent / "DashBoard-Finance" / "donnees" / "reference"
YAHOO = PROJET / "donnees_publiques" / "yahoo"
# Motifs privés supplémentaires (libellés, codes, fragments de noms), un par ligne, casse respectée ;
# fichier exclu du suivi git : les motifs ne sont jamais publiés
PRIVES = PROJET / "motifs-prives.txt"

# (fichier de la v1, colonnes, genre) : « nom » = sous-chaîne sans casse ; « code » = jeton exact
SOURCES_V1 = [("comptes.csv", ("societe",), "nom"), ("comptes.csv", ("numero",), "code"),
              ("fonds.csv", ("nom_court",), "nom"), ("fonds.csv", ("code_fa",), "code"),
              ("symboles.csv", ("nom_yahoo",), "nom"), ("symboles.csv", ("symbole", "code_fa"), "code"),
              ("reperes.csv", ("indice",), "nom"), ("reperes.csv", ("symbole",), "code")]
# Le cahier des charges (INSTRUCTIONS_…md, rédigé par le responsable) n'est pas balayé : vocabulaire
# générique, hors du périmètre code / configurations / exports
BALAYES = ["src", "configs", "tests", "docs", "outputs", "scripts", "README.md", "pyproject.toml"]
EXTENSIONS = {".py", ".toml", ".md", ".csv", ".json", ".txt"}
BALAYES_PROJET = ["rapport", "sql", "scripts", "docs", "jalons", "README.md"]
EXTENSIONS_PROJET = EXTENSIONS | {".tmdl", ".sql", ".pbip", ".pbir", ".pbism"}
EXCLUS_PROJET = ("StaticResources", "RegisteredResources")      # base64 du thème : faux positifs
# « DAX » est le langage du modèle, partout dans le rapport et les commentaires SQL : l'indice homonyme
# n'est pas recherché dans le périmètre projet
INDICES_EXEMPTES_PROJET = {"DAX"}
# Bloc figé : littéraux base64 concaténés entre Binary.FromText( et BinaryEncoding.Base64
FIGEE = re.compile(r"Binary\.FromText\((?P<b64>.*?)BinaryEncoding\.Base64", re.S)
IMPORTS_INTERDITS = {"socket", "urllib", "http", "requests", "httpx", "psycopg", "psycopg2", "subprocess",
                     "ftplib", "smtplib", "ssl", "webbrowser"}
CHAINES_INTERDITES = ("DashBoard-Finance", "donnees_publiques", "donnees_fictives", "yahoo", "../", "..\\")
# Familles d'indices réels : jeton entier, sans casse (les repères synthétiques s'appellent « Repère … »)
INDICES_REELS = ("S&P", "TSX", "MSCI", "FTSE", "Russell", "Nasdaq", "Dow Jones", "Bloomberg", "Stoxx", "Nikkei",
                 "Hang Seng", "DAX", "CAC 40", "Solactive", "Morningstar", "Wilshire", "Euronext", "Markit")


def lire_v1(nom: str, colonnes: tuple[str, ...]) -> set[str] | None:
    chemin = V1 / nom
    if not chemin.is_file():
        return None
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        return {(l.get(c) or "").strip() for l in csv.DictReader(f, delimiter=";") for c in colonnes} - {""}


def motifs() -> list[tuple[str, str, set[str] | None]]:
    sortie = [(f"v1 {n} [{', '.join(c)}]", g, lire_v1(n, c)) for n, c, g in SOURCES_V1]
    symboles = {p.stem for p in YAHOO.rglob("*.json")} if YAHOO.is_dir() else None
    if symboles is not None:
        symboles |= {s.split(".")[0] for s in symboles}
    sortie.append(("vE01 cours de FNB réels (noms de fichiers)", "code", symboles))
    prives = ({l for l in PRIVES.read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.startswith("#")} if PRIVES.is_file() else None)
    sortie.append(("motifs privés supplémentaires", "exact", prives))
    return sortie


def fichiers(racine: Path, balayes: list[str], extensions: set[str]) -> list[Path]:
    soi = Path(__file__).resolve()
    liste = []
    for nom in balayes:
        p = racine / nom
        candidats = [p] if p.is_file() else sorted(p.rglob("*")) if p.is_dir() else []
        liste += [f for f in candidats if f.is_file() and f.suffix in extensions and f.resolve() != soi
                  and "__pycache__" not in f.parts and ".pbi" not in f.parts
                  and not all(e in f.parts for e in EXCLUS_PROJET)]
    return liste


def lire(f: Path) -> str:
    """Texte d'un fichier. Un fichier qui n'est pas en UTF-8 (sortie de console Windows, encodage mixte, dans
    jalons/preuves/) est lu deux fois, en UTF-8 avec remplacement et en latin-1, textes mis bout à bout : aucun
    motif n'échappe à la recherche ; seul compte le fait qu'il y ait zéro occurrence ou non."""
    try:
        return f.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        brut = f.read_bytes()
        return brut.decode("utf-8", errors="replace") + "\n" + brut.decode("latin-1")


def partitions_figees(textes: dict[Path, str]) -> dict[Path, str]:
    """Contenu décompressé de chaque bloc figé du TMDL, sous une clé « fichier#n »."""
    sortie = {}
    for f, t in textes.items():
        if f.suffix != ".tmdl":
            continue
        for i, m in enumerate(FIGEE.finditer(t)):
            b64 = "".join(re.findall(r'"([A-Za-z0-9+/=]+)"', m["b64"]))
            sortie[Path(f"{f}#{i}")] = zlib.decompress(base64.b64decode(b64), wbits=-15).decode("utf-8")
    return sortie


def compter(textes: dict[Path, str], genre: str, valeurs: set[str]) -> int:
    n = 0
    for v in valeurs:
        if genre == "exact":                    # sous-chaîne, casse respectée
            n += sum(t.count(v) for t in textes.values())
            continue
        if genre == "nom":
            if len(v) < 4:                      # trop court pour une recherche en sous-chaîne
                continue
            motif = re.compile(re.escape(v), re.IGNORECASE)
        else:                                   # jeton entier ; ni partie décimale, ni partie entière d'un montant
            motif = re.compile(rf"(?<![\w.]){re.escape(v)}(?![\w]|\.\d)")
        n += sum(len(motif.findall(t)) for t in textes.values())
    return n


def controle_code() -> tuple[int, int]:
    """Imports réseau ou de sous-processus, et chaînes pointant hors du dossier, dans src/."""
    imports = chemins = 0
    for f in sorted((ICI / "src").rglob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                imports += sum(1 for a in noeud.names if a.name.split(".")[0] in IMPORTS_INTERDITS)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
                imports += noeud.module.split(".")[0] in IMPORTS_INTERDITS
            elif isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                chemins += any(c in noeud.value for c in CHAINES_INTERDITES)
    return imports, chemins


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")
    parseur = argparse.ArgumentParser(description="Balayage de fuite")
    parseur.add_argument("--perimetre", choices=("generateur", "projet"), default="generateur")
    perimetre = parseur.parse_args().perimetre
    if perimetre == "projet":
        liste = fichiers(PROJET, BALAYES_PROJET, EXTENSIONS_PROJET)
        textes = {f: lire(f) for f in liste}
        figees = partitions_figees(textes)
        textes |= figees
        print(f"Fichiers balayés : {len(liste)} ({', '.join(BALAYES_PROJET)} de la racine), "
              f"hors {'/'.join(EXCLUS_PROJET)} et .pbi ; partitions figées décompressées : {len(figees)}")
    else:
        liste = fichiers(ICI, BALAYES, EXTENSIONS)
        textes = {f: f.read_text(encoding="utf-8") for f in liste}
        print(f"Fichiers balayés : {len(liste)} ({', '.join(BALAYES)}), hors .venv et ce script")
    total, absentes = 0, 0
    for libelle, genre, valeurs in motifs():
        if valeurs is None:
            absentes += 1
            print(f"  [ABSENTE] {libelle} : source introuvable, non balayée")
            continue
        n = compter(textes, genre, valeurs)
        total += n
        print(f"  [{'OK' if n == 0 else 'FUITE':5}] {libelle} ({genre}) : {n} occurrence(s)")
    indices = [v for v in INDICES_REELS if perimetre == "generateur" or v not in INDICES_EXEMPTES_PROJET]
    n = sum(len(re.findall(rf"(?<![\w&]){re.escape(v)}(?![\w&])", t, re.IGNORECASE))
            for v in indices for t in textes.values())
    total += n
    print(f"  [{'OK' if n == 0 else 'FUITE':5}] familles d'indices réels (jeton) : "
          f"{n} occurrence(s)")
    noms = {}
    for f in liste:
        if f.suffix == ".csv" and f.name == "institutions.csv":
            with f.open(encoding="utf-8", newline="") as h:
                noms[f] = [l["name"] for l in csv.DictReader(h)]
    hors_motif = sum(1 for v in noms.values() for n in v if not re.fullmatch(r"Société \d", n))
    print(f"  [{'OK' if hors_motif == 0 else 'FUITE':5}] noms d'institution exportés hors du motif « Société N » : {hors_motif}")
    imports, chemins = controle_code()
    print(f"  [{'OK' if imports == 0 else 'FUITE':5}] imports réseau ou sous-processus dans src/ : {imports}")
    print(f"  [{'OK' if chemins == 0 else 'FUITE':5}] chaînes pointant hors du dossier dans src/ : {chemins}")
    echec = total + hors_motif + imports + chemins
    print(f"Résultat : {'AUCUNE FUITE' if echec == 0 else f'{echec} FUITE(S)'}"
          + (f" — {absentes} source(s) absente(s)" if absentes else ""))
    return 1 if echec else 0


if __name__ == "__main__":
    raise SystemExit(main())
