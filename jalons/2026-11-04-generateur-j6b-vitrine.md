# Contrat de jalon — Générateur synthétique, J6b : scénario vitrine et repères de catégorie

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-04
- **Contrat validé par le responsable :** oui, le 2026-11-04
- **Statut :** accepté par l'évaluateur (second passage, critère C1 resserré) ; C4 à constater par le responsable

## Objectif

Le responsable a vu le jeu `typical` dans Desktop et le juge peu lisible sur deux points.
- **TWR faible.** Le TWR global annualisé est de −0,9 % depuis le début : le tirage de marché de la graine
  20261103 est défavorable (repère actions mondiales à −0,6 %/an).
- **Repère collé au portefeuille.** La courbe du patrimoine suit celle de son repère : corrélation
  quotidienne de 0,991, écart de suivi de 2,1 %/an. Chaque fonds est en effet comparé à son propre
  composite passif, qui a les mêmes expositions.

Décisions du responsable du 2026-11-04, sur recommandation :
- un scénario `vitrine`, dont le flux `markets` reçoit sa propre graine, choisie dans une liste figée
  d'avance sur un critère écrit ici avant tout tirage ;
- des repères passifs de catégorie, de composition fixe, à la place du composite dans `ref.repere`.

Le rapport (J7) se bâtit ensuite sur `vitrine`. `typical` reste le scénario neutre du cahier des charges.

## Livrables

| Livrable | Chemin |
|---|---|
| Graine propre au flux `markets` (`[scenario] market_seed`, facultative ; absente = graine du scénario) | `Generateur-data-fictive/src/synthetic_finance/config.py`, `market.py` |
| Repères de catégorie (`benchmark_type = "category"`), compositions par archétype dans la configuration | `Generateur-data-fictive/src/synthetic_finance/benchmarks.py`, `configs/base.toml` (`[markets.benchmarks.category.*]`) |
| `ref.repere` d'un fonds = son repère de catégorie | `Generateur-data-fictive/src/synthetic_finance/adapter.py` |
| Scénario vitrine | `Generateur-data-fictive/configs/vitrine.toml` |
| Sélection de la graine de marché | `Generateur-data-fictive/scripts/choisir_graine_marche.py` |
| Export et rapports, scénario vitrine | `Generateur-data-fictive/outputs/vitrine_seed_20261103/` |
| Tests, contrat de données, README à jour | `Generateur-data-fictive/tests/`, `docs/contrat_donnees.md`, `README.md` |

Preuves sous `jalons/preuves/generateur-j6b-vitrine/`. Interpréteur : `Generateur-data-fictive/.venv`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Graine de marché choisie sans tricher.** Le script essaie dans l'ordre les graines de marché 1 à 50, graine principale fixée à 20261103, et retient la première qui remplit les trois conditions suivantes, sur l'oracle TWR du J5 (`performance_periods`, global, depuis le début) : (a) TWR global annualisé entre 8 % et 12 % ; (b) au moins une année civile complète de TWR global négative ; (c) repli maximal de la valeur du portefeuille hors flux sous −15 %. Il imprime une ligne par graine essayée, jusqu'à la graine retenue incluse. `vitrine.toml` porte cette graine et ne surcharge rien d'autre que le nom, `market_seed` et un commentaire qui renvoie à ce contrat. Les CSV de l'univers produits par `vitrine` sont identiques à ceux de `typical`. | `python scripts/choisir_graine_marche.py` → `graine.txt` ; `configs/vitrine.toml` ; comparaison SHA-256 des CSV de l'univers → `univers.txt` |
| C2 | **Repères de catégorie.** Il y a un repère `category` par archétype de fonds présent dans l'univers. Sa composition est fixe et écrite dans `base.toml`, en style « marché large » et selon la géographie de la catégorie. Il a un alpha nul, aucun bruit propre et ne tire aucune valeur aléatoire. Ses frais passifs sont inférieurs au RFG de chaque fonds qui s'y compare. Avec la graine du J6, `fund_prices_daily.csv` de `typical` reste identique octet pour octet : les repères ne consomment pas le flux `markets`. Dans l'export de l'adaptateur, chaque fonds a exactement un `ref.repere`, celui de sa catégorie, avec un poids de 1. Diagnostic imprimé, sans seuil : par fonds et au niveau global, corrélation quotidienne et écart de suivi contre le repère de catégorie, puis contre le composite. | `pytest -q tests/test_market.py tests/test_adapter.py -rA` → `pytest.txt` ; `python scripts/recette_synthetique.py --controle reperes --path outputs/vitrine_seed_20261103` → `reperes.txt` |
| C3 | **Chaîne intacte sur `vitrine`.** `generate --stage adapter` puis `validate` passent. Le chargement dans `finance_ve01` et les contrôles `distributions`, `grand-livre` et `oracle` de `recette_synthetique.py` passent avec les bornes validées au J6. La suite complète `pytest -q` passe, tests multi-graines de `typical` compris. Le balayage de fuite, sur les deux périmètres, ne trouve rien. | `generate` + `validate` + `charger_synthetique.py` → `chargement.txt` ; `recette_synthetique.py --controle distributions|grand-livre|oracle` → `distributions.txt`, `grand-livre.txt`, `oracle.txt` ; `pytest -q` → `pytest-complet.txt` ; `balayage_fuite.py` et `--perimetre projet` → `fuite.txt` |
| C4 | **Lecture par le responsable.** Il lit `market_report.md` et `adapter_report.md` de `vitrine` : rendements par année, TWR global, repli, écarts aux repères de catégorie. Il juge le marché favorable sans être invraisemblable et les écarts aux repères explicables. | `outputs/vitrine_seed_20261103/*.md`, lus par le responsable |

## Hypothèses à confirmer

- **H1 — TWR visé :** le TWR global annualisé depuis le début, calculé par l'oracle quotidien du J5. Le TWR
  Dietz du rapport s'en écarte de 0,2 point en moyenne (J6), ce qui ne change pas la plage de C1.
- **H2 — Ce qui bouge :** le comportement lit le marché passé, avec une prudence après une baisse. Le
  comportement, le grand livre et les rendements de `vitrine` changent donc, et la VM finale aussi,
  probablement au-dessus des 61 k$ de `typical`. L'univers du J1 ne change pas.
- **H3 — Compositions de catégorie :** les profils mixtes (prudent, pondéré, dynamique) se comparent à un
  équilibré de même part en actions, arrondie à la dizaine. Les fonds d'actions se comparent à un indice
  large de leur géographie. Dividendes et petites capitalisations se comparent à l'indice large de leur
  géographie : l'écart de style devient lisible. Les obligations et le monétaire se comparent à leur classe.
- **H4 — Repères existants :** le composite par fonds, les politiques et les deux repères de contexte
  restent livrés, car l'oracle du J5 et `market_report.md` les utilisent. Seul `ref.repere` change.
  Les lignes des repères de catégorie s'ajoutent à `benchmarks.csv` et `benchmarks_daily.csv` de
  `typical` : la non-régression de C2 porte sur `fund_prices_daily.csv`.
- **H5 — Si aucune graine de 1 à 50 ne remplit le critère :** arrêt, et retour au responsable. La plage n'est
  pas élargie en cours de route.

## Hors périmètre

Le modèle de marché et ses paramètres du J2 : seule la graine du flux `markets` change. Le rapport Power BI
(J7, qui reprend ensuite sur `vitrine`), `sql/`, le modèle sémantique. Scénarios `stress` et
`adversarial` (J8).

## Modifications du contrat

Les deux premières, du 2026-11-04, en cours de travail : **validées par le responsable le 2026-11-04**. Aucun
critère ne change.

- **Tests de non-régression des J4 et J5 (application de H4).** `test_j1_a_j4_…` et `test_j1_a_j5_…`
  (`tests/test_reproducibility.py`) comparent les CSV de `data/` à ceux des commits `c6288c3` et `d6972b9`.
  Comme H4 le prévoit, `benchmarks.csv` et `benchmarks_daily.csv` gagnent les lignes `R-CAT-`. Ces deux
  fichiers se comparent désormais sans ces lignes. Le reste doit être identique octet pour octet, et les lignes
  retirées sont toutes des lignes de catégorie. Les 20 autres CSV se comparent toujours en entier.
- **Libellés des catégories.** Le balayage de fuite (C3) a trouvé un motif de la liste privée dans le
  libellé générique d'une catégorie. Les catégories d'actions et de revenu fixe reprennent donc les
  libellés de leurs archétypes, suivis de « marché large ». Les compositions ne changent pas.
- **C1, critère de sélection resserré (décision du responsable du 2026-11-04, à la lecture du C4).** La graine 27,
  retenue par le premier critère, donnait un TWR global de +52 % en 2022, +30 % en 2025 et −19 % en 2026 : la
  moyenne était dans la cible, chaque année non. Nouveau critère, écrit avant le nouveau tirage : (a) TWR
  annualisé de 6 à 10 % ; (b) et (c) inchangés ; (d) chaque année complète de 2022 à 2025 entre −20 % et +25 % ;
  (e) 2026, jusqu'à l'arrêté, positif. Graines 1 à 100, depuis la graine 1. Le premier verdict reste au contrat,
  et un nouvel évaluateur juge les preuves rejouées.

## Verdicts

### 2026-11-04, premier passage (graine 27, caduc depuis le resserrement de C1)

```text
JALON    : Générateur synthétique, J6b : scénario vitrine et repères de catégorie
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté) — Le script lit bien l'oracle du J5 (`choisir_graine_marche.py:33-51`) et essaie les graines 1 à 50 dans l'ordre. `graine.txt` montre 27 lignes. Aucune graine avant la 27 ne remplit a, b et c ensemble, et la 27 les remplit (9,53 %, 2024 à -9,92 %, repli -27,92 %). `vitrine.toml:7-9` ne porte que le nom et `market_seed = 27`. `univers.txt` montre 7 CSV d'univers identiques (SHA-256), et la VL de typical est inchangée. Je n'ai pas relancé le script.
- [C2] PASS (attesté) — `base.toml:421-500` fixe les compositions par catégorie. `test_reperes_categorie`, `test_categories_sans_tirage` et `test_repere_categorie` passent (`pytest.txt`, 20 passed), et `reperes.txt` confirme 14 fonds avec une ligne chacun et un poids de 1. Le diagnostic liste 12 fonds plus le global. F102 et F104 en sont absents parce qu'ils n'ont aucune transaction : `rapport.rendement_quotidien` ne les voit donc pas. Leur ligne `ref.repere` existe (`ref.repere.csv:3,5`). Le test d'absence de tirage vérifie qu'une catégorie modifiée ne change pas les VL. Le test d'alpha nul et de bruit nul compare les rendements du repère à la fonction `rendements` qu'il contrôle, donc il reste en partie circulaire.
- [C3] PASS (attesté) — `chargement.txt` : `validate` réussi, 18 tables chargées, 45 vues et tous les contrôles passent. `distributions.txt`, `grand-livre.txt` et `oracle.txt` se terminent par « tous les contrôles bloquants passent » (code 0). `pytest-complet.txt` : 261 passed. `fuite.txt` : « AUCUNE FUITE » sur les deux périmètres. Je n'ai pas pu confirmer que les bornes du J6 sont bien celles appliquées.
- [C4] À CONSTATER PAR LE RESPONSABLE — lecture de `outputs/vitrine_seed_20261103/market_report.md` et `adapter_report.md`.
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE :
- Tous les PASS reposent sur des sorties enregistrées par l'exécutant. Pour contrôler, relance `python scripts/choisir_graine_marche.py` et `pytest -q` depuis `Generateur-data-fictive/`.
- Le contrat note que ses modifications (`## Modifications du contrat`) sont « à valider par le responsable ». Elles assouplissent les tests de non-régression J4 et J5, qui ignorent désormais les lignes `R-CAT-` (`tests/test_reproducibility.py:18-29`). Elles renomment aussi les libellés de catégories.
- Pour C4, regarde ce que montre `vitrine` : 2022 à +52 %, 2026 en cours à -19 %, repli de -28 %. Le critère « favorable sans être invraisemblable » est à toi.
- La section `## Verdicts` du contrat est vide.
```

### 2026-11-04, second passage (critère C1 resserré, graine 19)

```text
JALON    : Générateur synthétique, J6b : scénario vitrine et repères de catégorie (rejeu après resserrement de C1, graines 1 à 100)
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté), jugé sur le critère resserré (a à e, 6 à 10 %, graines 1 à 100). `graine.txt:5-24` : 19 lignes, la graine 19 est retenue (7,60 % ; 2022 +14,06 %, 2023 +17,72 %, 2024 -1,57 %, 2025 -0,51 % ; 2026 +7,35 % ; repli -15,14 %). Aucune graine 1 à 18 ne remplit les cinq conditions : 11 et 15 passent (a) mais ont (b) ou (c) en échec, et 7 a un repli de -14,51 %. `choisir_graine_marche.py:30-35,71-78` code bien a à e. `vitrine.toml:7-9` ne porte que le nom et `market_seed = 19`. `univers.txt:2-8` : 7 CSV d'univers aux SHA-256 identiques, VL de typical inchangée (`univers.txt:14`). Je n'ai pas relancé le script.
- [C2] PASS (attesté) : `pytest.txt:20 passed`, dont `test_reperes_categorie`, `test_categories_sans_tirage` et `test_repere_categorie` (10 repères pour 14 fonds). `reperes.txt:2` : 14 fonds, une ligne chacun, repère de catégorie, poids 1. Le diagnostic (`reperes.txt:4-17`) liste 12 fonds plus le global. F102 et F104 en sont absents (aucune transaction, donc aucun rendement quotidien), sans conséquence sur le critère. Le test d'alpha nul et de bruit nul reste en partie circulaire.
- [C3] PASS (attesté) : `chargement.txt:65-106` (`validate` réussi), `:189-282` (18 tables, 45 vues, tous les contrôles passent). `distributions.txt:7`, `grand-livre.txt:15` et `oracle.txt:47` : « tous les contrôles bloquants passent ». `pytest-complet.txt:6` : 261 passed. `fuite.txt:16,34` : AUCUNE FUITE sur les deux périmètres. Les chiffres du rejeu sont cohérents entre fichiers (`oracle.txt` et `graine.txt` donnent les mêmes TWR annuels pour 2022 à 2026 ; `manifest.json:77` porte `market_seed: 19`). Je n'ai pas pu vérifier que les bornes appliquées sont bien celles du J6.
- [C4] À CONSTATER PAR LE RESPONSABLE : lecture de `market_report.md` et `adapter_report.md` dans `outputs/vitrine_seed_20261103/`.
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE :
- Les PASS reposent sur des sorties enregistrées par l'exécutant. Pour contrôler : depuis `Generateur-data-fictive/`, relancer `python scripts/choisir_graine_marche.py` (doit s'arrêter à la graine 19) puis `pytest -q`.
- Le tableau des critères du contrat (C1, lignes 42) et la ligne `Statut` (ligne 6) portent encore l'ancien texte (8 à 12 %, graines 1 à 50, « accepté »). Seule la section « Modifications du contrat » fait foi. Le premier verdict (graine 27) est devenu caduc : il est à remplacer par celui-ci.
- C4 : la graine 19 donne +14 % en 2022, +18 % en 2023, -1,6 % en 2024, -0,5 % en 2025 et +7 % en 2026. Le repli maximal de -15,14 % passe de justesse sous le seuil de -15 %.
```

Le tableau des critères garde le texte validé à l'ouverture, selon la règle du contrat ; le critère en vigueur pour C1
est celui de *Modifications du contrat*. Le premier verdict reste en place, marqué caduc, pour la traçabilité.
