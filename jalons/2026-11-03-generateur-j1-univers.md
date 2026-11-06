# Contrat de jalon — Générateur synthétique, J1 : contrat de données et univers

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03
- **Statut :** accepté (C5 constaté par le responsable le 2026-11-04)

## Objectif

Poser le socle du générateur indépendant décrit dans
`Generateur-data-fictive/INSTRUCTIONS_GENERATEUR_PATRIMOINE_SYNTHETIQUE.md` : schéma de
configuration, trois institutions fictives, comptes, une quinzaine de fonds synthétiques et leurs
expositions, tirés d'une graine, sans aucune dépendance à un cours réel ni au générateur actuel.

## Livrables

| Livrable | Chemin |
|---|---|
| Paquet Python (config, univers, export, validation, CLI) | `Generateur-data-fictive/src/synthetic_finance/` |
| Configurations commentées | `Generateur-data-fictive/configs/base.toml`, `typical.toml` |
| Tests de l'univers | `Generateur-data-fictive/tests/test_universe.py`, `test_reproducibility.py` |
| Contrat de données (cible et correspondance avec `finance_ve01`) | `Generateur-data-fictive/docs/contrat_donnees.md` |
| Export de l'univers, graine 20261103 | `Generateur-data-fictive/outputs/typical_seed_20261103/` |

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | `generate --stage universe` puis `validate` s'exécutent sans erreur et écrivent `institutions.csv`, `accounts.csv`, `funds.csv`, `fund_exposures.csv`, `allocation_targets_history.csv`, `manifest.json` (`synthetic: true`, graine, empreinte de configuration) | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage universe` puis `python -m synthetic_finance validate --path outputs/typical_seed_20261103` → `jalons/preuves/generateur-j1-univers/generate-validate.txt` |
| C2 | Les invariants de l'univers passent : exactement 3 institutions ; 12 à 18 fonds, 4 à 6 par institution ; aucune clé orpheline ni en double ; chaque axe d'exposition (classe d'actifs, géographie, style) totalise 100 % ± 0,01 par fond ; les quatre régimes présents, alias distincts du régime ; aucun CELIAPP ouvert avant le 2023-04-01 ; parts cibles des institutions non toutes à moins de 2 points de 33,3 % | `pytest -q tests/test_universe.py` → `jalons/preuves/generateur-j1-univers/pytest.txt` |
| C3 | Reproductible : deux exécutions à graine égale donnent des CSV identiques (SHA-256) ; une autre graine donne un univers différent | `pytest -q tests/test_reproducibility.py` → `jalons/preuves/generateur-j1-univers/repro.txt` |
| C4 | Indépendance : le code ne lit aucun fichier hors de `Generateur-data-fictive/`, n'ouvre aucune connexion réseau ; aucun symbole de FNB réel ni nom d'institution réelle dans le code, les configurations et les exports | `python scripts/balayage_fuite.py` → `jalons/preuves/generateur-j1-univers/fuite.txt` (comptes d'occurrences seulement, aucun nom réel imprimé) |
| C5 | Les trois profils se lisent dans les expositions pondérées par l'allocation cible : part en actions strictement croissante de l'institution prudente à la dynamique, sans qu'aucune ne tombe sur une valeur ronde imposée (multiple de 5 %) | `outputs/typical_seed_20261103/universe_report.md`, lu par le responsable |

## Hors périmètre

Marchés et VL (J2), comportement de l'épargnant (J3), grand livre (J4), TWR, MWR et contrefactuel
(J5), scénarios `stress` et `adversarial`, multi-graines, adaptateur vers `finance_ve01` et
rapport Power BI (J6). L'ancien `generateur/generer.py` n'est ni modifié ni supprimé dans ce jalon.

## Modifications du contrat

## Verdicts

### 2026-11-03

```text
JALON    : Générateur synthétique, J1 : contrat de données et univers
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté) — jalons/preuves/generateur-j1-univers/generate-validate.txt:1-25 : « Généré … graine 20261103, étape universe », 14 contrôles [PASS], « Validation : réussie ». Les 5 CSV et manifest.json existent sur disque. manifest.json:5-8 contient config_hash, `synthetic: true` et la graine. validation.json:3 donne `"passed": true`.
- [C2] PASS (attesté) — pytest.txt « 11 passed ». tests/test_universe.py:19-73 contrôle les invariants sur les CSV bruts, hors validateur : 3 institutions, 12 à 18 fonds, 4 à 6 par institution, clés, axes à 100 ± 0,01, 4 régimes, alias, CELIAPP ≥ 2023-04-01, parts non toutes proches de 33,3 %. Le test tourne aussi sur 40 graines tirées par hypothesis (l.82-89) et 6 tests de refus sur export corrompu (l.99-141). J'ai compté 11 tests, ce qui correspond à la sortie. Les effectifs du rapport se retrouvent sur disque : 14 fonds, 6 comptes, 222 cellules (fund_exposures.csv a 223 lignes avec l'en-tête), 32 lignes de cibles.
- [C3] PASS (attesté) — repro.txt « 3 passed ». tests/test_reproducibility.py:22-42 compare les SHA-256 des 7 CSV entre deux processus CLI et en mémoire. Il exige aussi qu'une autre graine change au moins 5 fichiers sur 7 et le config_hash.
- [C4] PASS (attesté) — fuite.txt:14 « AUCUNE FUITE », 31 fichiers balayés, 0 occurrence. Mon Grep indépendant de noms d'institutions courants sur src, configs, tests, docs, outputs et scripts donne 0 résultat. Dans src/, les seules lectures de fichier sont la configuration TOML (config.py:53) et les CSV et manifest de l'export (export.py, validation.py:41). Aucun import réseau n'apparaît dans les lectures de src/.
- [C5] À CONSTATER PAR LE RESPONSABLE — la colonne Preuve le nomme. Pour info : universe_report.md:15 donne 33,5 % < 65,7 % < 97,5 %, aucune valeur multiple de 5.
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE : (1) C5 : lire outputs/typical_seed_20261103/universe_report.md, en particulier que la Société 3 « dynamique » à 97,5 % d'actions (2 pôles : 50 % Canada, 50 % États-Unis) te paraît crédible. (2) C1 à C4 sont attestés : les sorties viennent de l'exécutant et je n'ai rien lancé. Pour les revalider, exécute `pytest -q` et `python scripts/balayage_fuite.py` depuis Generateur-data-fictive/. (3) Précision sur C4 : scripts/balayage_fuite.py lit en lecture seule les listes de la v1 (`../DashBoard-Finance/donnees/reference`) pour construire ses motifs. Le contrat vise « le code » du générateur (src/), donc je n'y vois pas d'écart. Le script n'imprime aucun nom réel.
```

C5 constaté par le responsable le 2026-11-04.
