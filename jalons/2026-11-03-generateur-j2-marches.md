# Contrat de jalon — Générateur synthétique, J2 : marchés, VL et repères

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03
- **Statut :** accepté ; C5 constaté par le responsable le 2026-11-03 (tirage défavorable gardé : la graine est fixée d'avance)

## Objectif

Construire le moteur B du cahier des charges (§ 4 et § 8) : un modèle multifactoriel à pas
journalier ouvrable, à régimes latents et volatilité variable, qui produit la VL en rendement total
de chaque fonds de l'univers J1 et des repères passifs tirés des mêmes facteurs. Le moteur ignore
tout du portefeuille : il ne lit ni les comptes ni les allocations des comptes, et ne fabrique
aucune trajectoire choisie d'avance.

## Livrables

| Livrable | Chemin |
|---|---|
| Moteur de marché (facteurs, régimes, VL) et repères | `Generateur-data-fictive/src/synthetic_finance/market.py`, `benchmarks.py` |
| Paramètres de marché commentés | `Generateur-data-fictive/configs/base.toml`, section `[markets]` |
| Étape `markets` de la CLI, contrôles ajoutés au validateur | `Generateur-data-fictive/src/synthetic_finance/cli.py`, `validation.py` |
| Tests du marché, multi-graines, reproductibilité | `Generateur-data-fictive/tests/test_market.py`, `test_market_seeds.py`, `test_reproducibility.py` |
| Rapport de marché | `Generateur-data-fictive/outputs/typical_seed_20261103/market_report.md` |
| Export, graine 20261103 | `Generateur-data-fictive/outputs/typical_seed_20261103/data/fund_prices_daily.csv`, `benchmarks.csv`, `benchmarks_daily.csv`, `market_regimes_daily.csv` |
| Contrat de données et README à jour | `Generateur-data-fictive/docs/contrat_donnees.md`, `README.md` |

Toutes les commandes se lancent depuis `Generateur-data-fictive/` avec `.venv/Scripts/python`.
Preuves sous `jalons/preuves/generateur-j2-marches/`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Exécution et grain.** `generate --stage markets` puis `validate` s'exécutent sans erreur. `fund_prices_daily.csv` a exactement une ligne par fonds et par jour ouvrable (lundi à vendredi) de max(`start_date`, `inception_date`) à `end_date`, aucune avant le lancement du fonds ; `benchmarks_daily.csv`, une ligne par repère et par jour ouvrable de l'horizon. Toutes les VL et tous les indices sont finis et strictement positifs. Le validateur affiche ces contrôles un par un. | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage markets` puis `python -m synthetic_finance validate --path outputs/typical_seed_20261103` → `generate-validate.txt` |
| C2 | **Construction du modèle.** Les tests passent et vérifient : matrice de covariance des facteurs semi-définie positive dans chaque régime (plus petite valeur propre ≥ −1e-10) ; prix obtenus par rendements logarithmiques ; régimes tirés d'une chaîne de Markov, sans aucune date ni rendement annuel dans la section `[markets]` ; aucune borne qui écrête les rendements ; bêtas de chaque fonds dérivés de ses expositions J1 (classe, géographie, style, duration, part non couverte en devises) ; repères = mêmes facteurs, alpha nul, frais passifs explicites et inférieurs au RFG de chaque fonds comparé. Repères livrés : un composite passif par fonds, un repère de politique par institution (pondérations = cibles initiales J1 de l'institution), un repère actions mondiales et un repère équilibré. | `pytest -q tests/test_market.py` → `pytest-market.txt` ; lecture de `market.py`, `benchmarks.py`, `configs/base.toml` |
| C3 | **Faits stylisés, graine 20261103.** Sur les rendements journaliers : kurtosis excédentaire > 1 pour chaque fonds à plus de 50 % d'actions ; autocorrélation moyenne de r² sur les décalages 1 à 10 > 0,05 pour ces mêmes fonds (volatilité regroupée) ; médiane des volatilités annualisées strictement croissante monétaire < obligations < portefeuilles mixtes < actions ; aucune paire de fonds à corrélation > 0,98 ; corrélation de Spearman > 0,5 entre la similarité des expositions de deux fonds et leur corrélation réalisée. **Multi-graines (graines 1 à 20, liste figée) :** C1 et les invariants de C2 passent sur les 20 ; part des graines où le repère actions mondiales a au moins une année civile négative comprise entre 30 % et 95 % ; au moins une graine avec un repli maximal du repère actions mondiales supérieur à 25 %. Le taux d'échec de chaque contrôle est imprimé. | `pytest -q tests/test_market.py tests/test_market_seeds.py -rA` → `pytest-faits.txt` |
| C4 | **Reproductibilité, indépendance, non-régression.** Deux exécutions à graine égale donnent des CSV identiques (SHA-256), une autre graine des VL différentes ; modifier un paramètre de l'univers qui ne touche ni aux fonds ni à leurs expositions (par exemple les poids des comptes) laisse `fund_prices_daily.csv` identique ; les 7 CSV de l'univers produits à l'étape `markets` sont identiques à ceux du J1 commités (`ce0a60f`). Le balayage de fuite, étendu aux nouveaux fichiers, ne trouve aucun symbole de FNB réel, nom d'indice réel (motifs listés dans le script) ou nom d'institution réelle, et le moteur n'ouvre aucune connexion réseau. | `pytest -q tests/test_reproducibility.py` → `repro.txt` ; `git diff --stat ce0a60f -- outputs/typical_seed_20261103/data/` → `non-regression.txt` ; `python scripts/balayage_fuite.py` → `fuite.txt` |
| C5 | **Lecture par le responsable.** `market_report.md` donne, par fonds et par repère : rendements par année civile de 2021 à 2026, volatilité annualisée, repli maximal, et la matrice de corrélation ; plus la chronologie des régimes. Le responsable juge que les trajectoires ne ressemblent ni à une croissance régulière ni à du bruit sans logique, que les profils prudent, équilibré et dynamique se distinguent, et que les repères ne sont pas des adversaires faibles. | `outputs/typical_seed_20261103/market_report.md`, lu par le responsable |

## Hypothèses à confirmer

- **H1 — Calendrier :** jours ouvrables du lundi au vendredi, jours fériés non modélisés ; convention
  écrite dans le contrat de données. Raison : aucune liste de fériés à maintenir, et le rapport
  Power BI ne s'en sert pas.
- **H2 — Devises :** tous les fonds valorisés en CAD ; un facteur de change USD/CAD synthétique
  s'applique à la part non couverte (`fx_exposure_pct`). Aucune série de change n'est exportée.
- **H3 — Distributions :** VL en rendement total, distributions réinvesties implicitement (§ 4 du
  cahier des charges) ; aucun dividende en espèces.
- **H4 — Horizon :** celui de `base.toml`, du 2021-11-01 au 2026-10-30, sans modification.

## Hors périmètre

Comportement de l'épargnant et événements (J3), grand livre, positions et frais de compte (J4),
TWR, MWR et contrefactuel passif en dollars (J5), scénarios `stress` et `adversarial`, adaptateur
vers `finance_ve01` et rapport Power BI (J6). Séries de change exportées, dividendes en espèces,
jours fériés. L'ancien `generateur/generer.py` n'est ni modifié ni supprimé.

## Modifications du contrat

## Verdicts

### 2026-11-03

```text
JALON    : Générateur synthétique, J2 : marchés, VL et repères
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté) — J'ai recompté sur disque : fund_prices_daily.csv a 17905 lignes (17904 VL plus l'en-tête) et benchmarks_daily.csv en a 24796 (24795 plus l'en-tête, soit 19 repères × 1305 jours). Ces totaux correspondent à generate-validate.txt:31-34. Le validateur (validation.py:303-374) contrôle bien le grain par fonds, l'absence de VL avant le lancement, la positivité et le caractère fini. Il affiche 5 contrôles `marche_*` un par un. La sortie de commande est celle de l'exécutant (generate-validate.txt:35 « Validation : réussie »).
- [C2] PASS (attesté) — pytest-market.txt (11 passed). J'ai lu market.py, benchmarks.py et les tests. Plus petite valeur propre de la covariance : 4.2e-08, soit ≥ −1e-10 (pytest-faits.txt:5). VL = VL₀·exp(Σr) (market.py:316). Chaîne de Markov (market.py:104-120). Aucun clip, minimum ni maximum, vérifié par analyse AST (test_market.py:112-127). Bêtas dérivés des expositions : fonction `charges()` (market.py:231), pentes ≈ 1 (pytest-faits.txt:24). Repères : alpha nul, frais passifs de 0,031 à 0,111 % et inférieurs au RFG (test_market.py:170-193). Livrés : 14 composites, 3 politiques, R-ACT-MONDE et R-EQUILIBRE (market_report.md:47-73). Le test des dates et années dans `[markets]` ne trouve rien (pytest-faits.txt:14).
- [C3] PASS (attesté) — pytest-faits.txt (16 passed), graine 20261103. Kurtosis excédentaire de 11,3 à 18,6 pour les 9 fonds à plus de 50 % d'actions (lignes 30-38). Autocorrélation de r² de 0,118 à 0,183 (mêmes lignes). Médianes de volatilité : 0,09 % < 5,42 % < 10,56 % < 17,58 % (ligne 41). Corrélation maximale 0,937 (ligne 44). Spearman 0,764 (ligne 44). Multi-graines : 0 échec sur 20 pour chaque contrôle du validateur (lignes 47-65) et pour les invariants (ligne 68). Années négatives : 14/20 = 70 % (ligne 91). Repli > 25 % pour 8 graines (ligne 94). Taux d'échec imprimés pour kurtosis, autocorrélation et paires (lignes 97-99).
- [C4] PASS (attesté) — repro.txt (7 passed). test_reproducibility.py:57-93 contrôle le SHA-256 entre deux processus, l'effet d'une autre graine, l'indépendance vis-à-vis des poids et délais des comptes, et l'identité des 7 CSV de l'univers entre les étapes universe et markets. fuite.txt:15 : « AUCUNE FUITE », 40 fichiers balayés, 0 import réseau. non-regression.txt est vide, ce qui correspond à un `git diff --stat` sans écart. Le git status initial ne montre aucun data/*.csv modifié, donc aucun écart avec ce0a60f.
- [C5] À CONSTATER PAR LE RESPONSABLE — lecture de market_report.md. Les sections exigées sont présentes (rendements 2021-2026, volatilité, repli max, corrélations, régimes).
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE : (1) C5, jugement sur le rapport. Les rendements annualisés sont faibles ou négatifs sur 5 ans : R-ACT-MONDE −0,6 %, F302 −0,9 %, F105 −1,5 %. À toi de juger si les repères ne sont pas des adversaires faibles. (2) Les 5 preuves .txt sont des sorties produites par l'exécutant. Pour contrôler, relance depuis Generateur-data-fictive/ `.venv/Scripts/python -m pytest -q tests/test_market.py tests/test_market_seeds.py tests/test_reproducibility.py` et `git diff --stat ce0a60f -- outputs/typical_seed_20261103/data/`. (3) À titre informatif, hors critère : avec la graine 1, 8 fonds actions échouent au seuil d'autocorrélation de r² (pytest-faits.txt:98). Le contrat n'impose ce seuil qu'à la graine 20261103.
```
