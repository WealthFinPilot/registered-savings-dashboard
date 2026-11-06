# DashBoard-Finance — version d'exposition vE01

Tableau de bord Power BI de l'épargne enregistrée (CELI, CELIAPP, REER, comptes non enregistrés) :
droits de cotisation, répartition des versements, performance pondérée par le temps, stratégie,
risque et performance comparée à des repères.

**Toutes les données sont fictives, cours compris.** Sociétés (Société 1, 2, 3), comptes, fonds, valeurs
liquidatives, repères, versements et avis REER sortent du générateur `Generateur-data-fictive/`, à partir
d'une graine fixe. Aucun fonds ni indice réel ne sert de gabarit.

Le rapport (`rapport/DashBoard-Finance.pbip`, format PBIP) s'ouvre sans base de données : chaque
table est embarquée dans le modèle. Ouvrir dans Power BI Desktop, puis **Actualiser**.

## Histoire et méthode

Le pipeline d'ingestion de la version d'exploitation (lecture des exports, extraction de PDF
publics, cours, chargement PostgreSQL) existe, mais **n'est pas présenté ici, pour des raisons de
confidentialité** : il traite des données réelles. Ce dépôt en décrit la méthode, les outils et
l'architecture ; le rapport publié est alimenté par le générateur fictif.

La méthode de construction (analyse des exports, base PostgreSQL et chargement Python, extraction de
PDF publics, cours publics, recette contre un témoin indépendant, publication) est racontée dans
[docs/histoire-du-projet.md](docs/histoire-du-projet.md), illustrée sur le jeu fictif. Architecture : [docs/architecture.md](docs/architecture.md). Règles de calcul
citées par `sql/vues.sql` : [droits](docs/regles-droits.md), [performance](docs/regles-performance.md),
[stratégie](docs/regles-strategie.md).

## Reconstruction

Reconstruction (facultative), avec PostgreSQL local et une base `finance_ve01` :

1. `python -m synthetic_finance generate --config configs/vitrine.toml --seed 20261103 --out outputs/vitrine_seed_20261103 --stage adapter`
   (depuis `Generateur-data-fictive/`) ;
2. `python scripts/charger_synthetique.py --path Generateur-data-fictive/outputs/vitrine_seed_20261103` ;
3. `python scripts/recette_synthetique.py --controle distributions|grand-livre|oracle|rapport` ;
4. `python scripts/figer.py`, Power BI Desktop fermé.
