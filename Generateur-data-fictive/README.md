# Générateur de patrimoine financier synthétique

> Données SYNTHÉTIQUES / NON RÉELLES / NON CONSTITUTIVES D'UN CONSEIL FINANCIER.

Moteur de simulation reproductible qui fabrique l'histoire patrimoniale d'un épargnant fictif : trois
institutions, des comptes CELI, CELIAPP, REER et non enregistrés, une quinzaine de fonds synthétiques.
Aucun cours réel, aucun fonds réel servant de gabarit : tout est tiré de distributions paramétrées
(`configs/`) à partir d'une graine. Cahier des charges :
[INSTRUCTIONS_GENERATEUR_PATRIMOINE_SYNTHETIQUE.md](INSTRUCTIONS_GENERATEUR_PATRIMOINE_SYNTHETIQUE.md) ;
contrat de données : [docs/contrat_donnees.md](docs/contrat_donnees.md).

État : jalon 6 (univers ; marchés : VL des fonds, repères, régimes ; comportement : PAC, ponctuels,
retraits, révisions de cible, événements, droits de cotisation ; grand livre : ordres, parts, frais de
compte, rééquilibrages, positions et valeurs quotidiennes ; mesures : TWR, MWR, réconciliation,
contrefactuel passif ; adaptateur : distributions, VL ex-distribution et tables de `finance_ve01`).

## Reproduire

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -e ".[test,finance]"
.venv/Scripts/python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 \
    --out outputs/typical_seed_20261103 --stage adapter
.venv/Scripts/python -m synthetic_finance validate --path outputs/typical_seed_20261103
# Scénario du rapport Power BI : même univers, graine de marché choisie (scripts/choisir_graine_marche.py)
.venv/Scripts/python -m synthetic_finance generate --config configs/vitrine.toml --seed 20261103 \n    --out outputs/vitrine_seed_20261103 --stage adapter
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/balayage_fuite.py
```

Sorties : `data/*.csv`, `manifest.json` (graine, empreinte de configuration, versions, empreinte des
plafonds lus, `synthetic: true`), `validation.json`, `universe_report.md`, `market_report.md`,
`behaviour_report.md`, `ledger_report.md`, `performance_report.md`, et `finance_ve01/<schéma>.<table>.csv`
(étape `adapter`). `--stage universe`, `markets`, `behaviour`, `ledger` ou `performance` s'arrêtent avant.

Vers le rapport Power BI (depuis la racine du projet, même interpréteur, extra `finance`) :

```bash
python scripts/charger_synthetique.py --path Generateur-data-fictive/outputs/typical_seed_20261103
python scripts/recette_synthetique.py --controle distributions   # puis grand-livre, oracle, rapport
```

Le chargeur rejoue `sql/schema.sql`, `plafonds.sql` et `vues.sql`, vide puis recharge `finance_ve01` (et
aucune autre base) ; la recette compare les vues `rapport.*` à l'oracle du générateur et écrit
`adapter_report.md`. Le paquet lui-même n'ouvre aucune connexion.
`pytest -q` lance aussi les multi-graines du marché, du comportement et du grand livre ; le test
d'anticipation du grand livre (21 graines, trois marchés par coupure) prend à lui seul une dizaine de
minutes : `pytest -q -k "not anticipation_grand_livre"` pour un passage rapide.

L'étape `behaviour` lit les plafonds fiscaux dans `sql/plafonds.sql` du projet (droit public, canada.ca
cité), seule source : le générateur le cherche dans les dossiers au-dessus de la configuration et en
recopie le contenu dans `data/tax_limits.csv`.

Toute la chaîne se rejoue à l'identique : mêmes configuration, graine et versions (Python, numpy) →
mêmes CSV octet pour octet.

## Architecture

| Moteur | Module | Rôle |
|---|---|---|
| A. Univers | `universe.py` | institutions, comptes, fonds, expositions, allocations cibles |
| B. Marchés | `market.py`, `benchmarks.py` | facteurs latents, régimes de Markov, GARCH, sauts ; VL des fonds ; repères composites, de politique, de contexte et de catégorie ; indépendants du portefeuille |
| C. Épargnant | `behaviour.py`, `fiscal.py` | capacité d'épargne latente et phases, PAC par compte, mois atypiques, ponctuels, retraits, revues et prudence après une baisse, journal d'événements ; droits CELI, CELIAPP, REER du personnage fictif |
| D. Grand livre | `ledger.py` | ordres par fonds (PAC selon la cible, ponctuels vers les fonds sous-pondérés, retraits au prorata), parts en millièmes, frais de compte mensuels par palier, rééquilibrages imparfaits (nouvelle cible, dérive lue la veille), positions et valeurs quotidiennes ; seule source des parts détenues |
| F. Adaptateur | `adapter.py` | distributions tirées par archétype (VL ex = VL totale × Π (1 − taux), rendement total inchangé), parts publiées = parts du grand livre ÷ k, réinvestissements, frais, arbitrages et libellés de la v1, profils, repères, avis REER : tables de `finance_ve01` en CSV |
| E. Mesures et contrôles | `performance.py`, `validation.py` | TWR quotidien chaîné (compte, institution, portefeuille, sur valeurs et flux agrégés), MWR par année et depuis l'ouverture, réconciliation au cent, contrefactuel passif (mêmes flux, repère de politique ou de contexte) ; invariants de chaque étape ; ne tire rien |

Chaque moteur tire dans son propre flux (`numpy.random.SeedSequence(seed).spawn`) : modifier le
comportement ne déplace ni l'univers ni les marchés. `scenario.market_seed` (scénario `vitrine`) donne au seul
flux des marchés une graine propre : l'univers reste celui de la graine principale. Cette graine est choisie par
`scripts/choisir_graine_marche.py`, sur un critère de TWR global écrit d'avance : le marché de `vitrine` est
favorable par choix, celui de `typical` est tiré sans sélection.
