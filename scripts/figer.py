"""Fige le rapport : chaque partition qui lit une vue de PostgreSQL reçoit le contenu de cette vue,
embarqué dans le M (JSON compressé en deflate brut, encodé en base64, comme « Entrer des données »).

Seules les deux lignes de connexion changent : `Source = PostgreSQL.Database(...)` disparaît et
`#"Vue x lue" = Source{[Schema = "rapport", Item = "x"]}[Data]` devient une table typée de mêmes
colonnes, mêmes types. Les étapes suivantes de chaque requête (typage, filtres, renommages) restent
telles quelles. Le rapport s'ouvre et s'actualise ensuite sans base.

Rejouable : une partition déjà figée est refigée à partir du bloc balisé.
Usage : python scripts/figer.py
"""
import base64
import datetime as dt
import decimal
import json
import re
import zlib
from pathlib import Path

import psycopg

RACINE = Path(__file__).resolve().parent.parent
TABLES = RACINE / "rapport" / "DashBoard-Finance.SemanticModel" / "definition" / "tables"
BASE = "finance_ve01"
DSN = f"host=localhost port=5432 dbname={BASE} user=finance"
TRONCON = 4000      # longueur des littéraux base64 concaténés, pour l'éditeur et les diffs

CONNEXION = re.compile(r'^[\t ]+// Connexion à la base PostgreSQL locale.*\n[\t ]+Source = PostgreSQL\.Database\("localhost", "finance"\),\n',
                       re.M)
LECTURE = re.compile(r'^(?P<ind>[\t ]+)(?P<etape>#"[^"]+") = Source\{\[Schema = "rapport", Item = "(?P<vue>\w+)"\]\}\[Data\],$',
                     re.M)
FIGEE = re.compile(r'^(?P<ind>[\t ]+)(?P<etape>#"[^"]+") =\n[\t ]+// Figée : vue rapport\.(?P<vue>\w+) de finance_ve01.*?'
                   r'\n(?P=ind)    in\n(?P=ind)        Typée,$', re.M | re.S)

TYPES = {"text": "type text", "smallint": "Int64.Type", "integer": "Int64.Type", "bigint": "Int64.Type",
         "numeric": "type number", "double precision": "type number", "date": "type date",
         "boolean": "type logical"}


def valeur(v):
    if v is None or isinstance(v, (str, int)) and not isinstance(v, bool):
        return v
    if isinstance(v, bool):
        return int(v)                       # 0/1, converti par Logical.From
    if isinstance(v, (decimal.Decimal, float)):
        return float(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    raise TypeError(f"type non prévu : {type(v).__name__}")


def m_embarque(cur, vue: str, ind: str, etape: str) -> str:
    colonnes = cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                           "WHERE table_schema = 'rapport' AND table_name = %s ORDER BY ordinal_position",
                           (vue,)).fetchall()
    noms = [c for c, _ in colonnes]
    lignes = cur.execute(f'SELECT * FROM rapport."{vue}" ORDER BY ' + ", ".join(str(i + 1) for i in range(len(noms)))).fetchall()
    brut = json.dumps([[valeur(v) for v in l] for l in lignes], ensure_ascii=False, separators=(",", ":"))
    deflate = zlib.compressobj(level=9, wbits=-15)           # deflate brut, sans en-tête zlib
    b64 = base64.b64encode(deflate.compress(brut.encode("utf-8")) + deflate.flush()).decode("ascii")
    troncons = [b64[i:i + TRONCON] for i in range(0, len(b64), TRONCON)]

    i1, i2 = ind + "    ", ind + "        "
    texte = (" &\n" + i2 + "    ").join(f'"{t}"' for t in troncons)
    liste = lambda xs: "{" + ", ".join(xs) + "}"
    dates = [c for c, t in colonnes if t == "date"]
    autres = [f'{{"{c}", {TYPES[t]}}}' for c, t in colonnes if t != "date"]
    pas = [f"{i1}// Figée : vue rapport.{vue} de finance_ve01, données fictives, {len(lignes)} lignes (scripts/figer.py)",
           f"{i1}let",
           f"{i2}Lignes = Json.Document(Binary.Decompress(Binary.FromText(",
           f"{i2}    {texte},",
           f"{i2}    BinaryEncoding.Base64), Compression.Deflate)),",
           f"{i2}Brute = Table.FromRows(Lignes, {liste(chr(34) + n + chr(34) for n in noms)}),"]
    precedent = "Brute"
    if dates:
        transfo = [f'{{"{c}", each Date.FromText(_, [Format = "yyyy-MM-dd", Culture = "en-US"]), type nullable date}}'
                   for c in dates]
        pas.append(f"{i2}Dates = Table.TransformColumns(Brute, {liste(transfo)}),")
        precedent = "Dates"
    pas += [f"{i2}Typée = Table.TransformColumnTypes({precedent}, {liste(autres)})",
            f"{i1}in",
            f"{i2}Typée,"]
    return f"{ind}{etape} =\n" + "\n".join(pas)


def main() -> int:
    with psycopg.connect(DSN) as cx, cx.cursor() as cur:
        if cur.execute("SELECT current_database()").fetchone()[0] != BASE:
            raise SystemExit(f"Base inattendue : ce script ne lit que {BASE}.")
        for fichier in sorted(TABLES.glob("*.tmdl")):
            texte = fichier.read_text(encoding="utf-8")
            nouveau = CONNEXION.sub("", texte)
            nouveau = LECTURE.sub(lambda m: m_embarque(cur, m["vue"], m["ind"], m["etape"]), nouveau)
            nouveau = FIGEE.sub(lambda m: m_embarque(cur, m["vue"], m["ind"], m["etape"]), nouveau)
            if "PostgreSQL.Database" in nouveau:
                raise SystemExit(f"{fichier.name} : connexion PostgreSQL restante, motif non reconnu")
            vues = [m["vue"] for m in FIGEE.finditer(nouveau)]
            if nouveau != texte:   # read_text normalise en \n ; on rend la fin de ligne d'origine
                fin = "\r\n" if b"\r\n" in fichier.read_bytes() else "\n"
                fichier.write_text(nouveau, encoding="utf-8", newline=fin)
            if vues:   # chaque partition figée est nommée, qu'elle change ou non
                etat = "refigée" if nouveau != texte else "inchangée"
                print(f"{fichier.name} : rapport.{', rapport.'.join(vues)}, {len(nouveau) // 1024} Ko, {etat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
