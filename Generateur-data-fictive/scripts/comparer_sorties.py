"""Compare deux sorties du générateur, CSV par CSV, ligne à ligne et colonne par colonne.

Sert à prouver qu'un changement ne touche que des colonnes désignées (par exemple des libellés) : toute autre
différence, ligne en plus ou en moins, ou CSV absent d'un côté, est un échec. Les fichiers non CSV (rapports,
manifeste) sont listés pour information, sans entrer dans le verdict.

Usage : python scripts/comparer_sorties.py <avant> <après> [--permis table.colonne ...]
        (table = nom du CSV sans extension, par exemple fait.transaction)
Code de sortie 1 si une différence sort des colonnes permises.
"""
import argparse
import csv
import sys
from pathlib import Path


def lire(f: Path) -> tuple[list[str], list[list[str]]]:
    with f.open(encoding="utf-8", newline="") as h:
        lignes = list(csv.reader(h))
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("avant", type=Path)
    p.add_argument("apres", type=Path)
    p.add_argument("--permis", nargs="*", default=[])
    a = p.parse_args()
    permis = {tuple(x.rsplit(".", 1)) for x in a.permis}
    echecs = 0
    noms = sorted({f.relative_to(a.avant).as_posix() for f in a.avant.rglob("*") if f.is_file()}
                  | {f.relative_to(a.apres).as_posix() for f in a.apres.rglob("*") if f.is_file()})
    for nom in noms:
        fa, fp = a.avant / nom, a.apres / nom
        if not fa.is_file() or not fp.is_file():
            echecs += nom.endswith(".csv")
            print(f"  [{'FAIL' if nom.endswith('.csv') else 'info'}] {nom} : absent {'avant' if not fa.is_file() else 'après'}")
            continue
        if fa.read_bytes() == fp.read_bytes():
            print(f"  [PASS] {nom} : identique")
            continue
        if not nom.endswith(".csv"):
            print(f"  [info] {nom} : différent (hors CSV, hors verdict)")
            continue
        table = Path(nom).stem
        ea, la = lire(fa)
        ep, lp = lire(fp)
        if ea != ep or len(la) != len(lp):
            echecs += 1
            print(f"  [FAIL] {nom} : en-têtes ou nombre de lignes différents ({len(la)} contre {len(lp)})")
            continue
        colonnes = {}
        for ra, rp in zip(la, lp):
            for c, va, vp in zip(ea, ra, rp):
                if va != vp:
                    colonnes[c] = colonnes.get(c, 0) + 1
        hors = {c: n for c, n in colonnes.items() if (table, c) not in permis}
        echecs += bool(hors)
        detail = ", ".join(f"{c} : {n} ligne(s)" for c, n in sorted(colonnes.items()))
        print(f"  [{'FAIL' if hors else 'PASS'}] {nom} : {len(la)} lignes ; différences dans {detail}"
              + (f" ; HORS PERMIS : {', '.join(sorted(hors))}" if hors else " (colonnes permises)"))
    print(f"Résultat : {'AUCUNE DIFFÉRENCE HORS COLONNES PERMISES' if not echecs else f'{echecs} ÉCHEC(S)'}")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
