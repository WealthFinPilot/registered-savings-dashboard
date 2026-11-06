# Contrat de données — générateur synthétique

> Données SYNTHÉTIQUES / NON RÉELLES / NON CONSTITUTIVES D'UN CONSEIL FINANCIER.

Ce document fixe ce que le générateur exporte et comment ces exports alimenteront le rapport
Power BI existant (base `finance_ve01`, vues `rapport.*`). Il est établi à partir du schéma
(`sql/schema.sql`), des vues (`sql/vues.sql`) et du modèle sémantique, sans aucune donnée réelle.

## 1. Conventions

| Sujet | Convention |
|---|---|
| Fichiers | CSV UTF-8, séparateur virgule, fin de ligne LF, en-tête obligatoire, un fichier par table dans `data/` |
| Nombres | Point décimal, aucun symbole ni séparateur de milliers ; nombre de décimales fixé par colonne (`export.SCHEMAS`) |
| Dates | ISO 8601 (`AAAA-MM-JJ`) ; valeur vide = NULL |
| Monnaie | CAD partout ; un fonds investi à l'étranger reste valorisé en CAD, l'exposition aux devises est un attribut (`fx_exposure_pct`) |
| Pourcentages | 0 à 100 dans les colonnes `*_pct` et `weight` / `target_weight` ; 0 à 1 dans `risk_appetite` et `savings_weight_prior` |
| Signe des flux (J3-J4) | `amount_cad > 0` pour `PAC` et `PONCTUEL` ; `< 0` pour `RETRAIT` et `FRAIS` |
| Encaisse (J4) | Nulle en fin de journée : un apport est investi le jour même à la VL de clôture ; `cash_cad` est exporté, à 0. Parts à 3 décimales : le résidu d'arrondi d'un ordre, \|parts × VL − montant\|, reste dans la valeur, borné à 0,0005 × VL + 0,005 $ |
| VL (J2) | `nav_total_return` : VL synthétique en rendement total, distributions réinvesties implicitement. Le grand livre tient ses parts dans cette VL. La VL ex-distribution, les distributions par part et la conversion des parts (parts ex = parts × VL totale ÷ VL ex) que le rapport consomme sont dérivées par l'adaptateur du J6 (VL ex = VL totale × Π (1 − taux de distribution)), sans changer le rendement total |
| Calendrier (J2) | Jours ouvrables du lundi au vendredi, du `start_date` au `end_date` ; jours fériés non modélisés |
| Repères (J2) | Indice en rendement total, base 100 au premier jour ouvrable de l'horizon, frais passifs déduits |
| Mode fiscal (J3) | `conservative_synthetic` : plafonds lus dans `sql/plafonds.sql` (contenu de `ref.plafond` et `ref.periode_reer`, droit public, canada.ca), recopiés dans `tax_limits` ; situation personnelle (première année CELI, revenu, droits REER inutilisés au départ) fictive et tirée. Le scénario `typical` ne dépasse jamais les droits |
| Événements (J3) | Tout mouvement porte l'`event_id` de la décision qui l'a fixé (ouverture, phase, ajustement, mois atypique, ponctuel, dépense). Une nouvelle cible de compte se rattache à son événement par (`account_id`, `effective_date`) = (`account_id`, `date`) d'un événement `revue_annuelle`, `ajout_fonds`, `prudence_marche` ou `retour_cible` |
| Reproductibilité | Graine + configuration résolue (empreinte SHA-256 dans `manifest.json`) → CSV identiques octet pour octet |

## 2. Tables exportées

État : ✅ livrée, ⏳ jalon à venir.

| Table | Grain | Clé | Jalon |
|---|---|---|---|
| `institutions` | 1 par institution | `institution_id` | ✅ J1 |
| `accounts` | 1 par compte | `account_id` ; `account_alias` unique | ✅ J1 |
| `funds` | 1 par fonds | `fund_id` ; `fund_name` unique | ✅ J1 |
| `fund_exposures` | 1 par fonds × classe × géographie × style | les quatre colonnes | ✅ J1 |
| `fund_exposures_by_axis` | 1 par fonds × axe × catégorie (vue agrégée) | `fund_id, axis, category` | ✅ J1 |
| `fund_strategic_targets` | 1 par fonds × classe d'actifs (mandat déclaré) | `fund_id, asset_class` | ✅ J1 |
| `allocation_targets_history` | 1 par cible × fonds × date d'effet | `effective_date, level, institution_id, account_id, fund_id` | ✅ J1 (cibles initiales), J3 (révisions des comptes, ajoutées après) |
| `fund_prices_daily` | 1 par fonds et jour ouvrable, du lancement (ou du début de l'horizon) à la fin | `date, fund_id` | ✅ J2 |
| `benchmarks` | 1 par repère | `benchmark_id` | ✅ J2 |
| `benchmarks_daily` | 1 par repère et jour ouvrable de l'horizon | `date, benchmark_id` | ✅ J2 |
| `market_regimes_daily` | 1 par jour ouvrable | `date` | ✅ J2 |
| `events` | 1 par événement | `event_id` | ✅ J3 |
| `external_movements` | 1 par mouvement externe ou frais | `movement_id` | ✅ J3 (`PAC`, `PONCTUEL`, `RETRAIT`) ; ✅ J4 (`FRAIS`, identifiants renumérotés) |
| `contribution_room` | 1 par régime enregistré × année (de déduction pour le REER) | `regime, year` | ✅ J3 |
| `persona` | 1 par année civile du personnage fictif | `year` | ✅ J3 |
| `tax_limits` | 1 par plafond ou fin de période REER lus | `regime, rubric, year` | ✅ J3 |
| `internal_trades` | 1 par ordre exécuté | `trade_id` | ✅ J4 |
| `positions_daily` | 1 par compte × fonds détenu × jour ouvrable | `date, account_id, fund_id` | ✅ J4 |
| `account_values_daily` | 1 par compte ouvert × jour ouvrable | `date, account_id` | ✅ J4 |
| `performance_daily` | 1 par entité (compte, institution, portefeuille) × jour où elle a un compte ouvert | `date, entity_type, entity_id` | ✅ J5 |
| `performance_periods` | 1 par entité × année civile, plus « depuis l'ouverture » | `entity_type, entity_id, period` | ✅ J5 |
| `counterfactual_daily` | 1 par contrefactuel (entité × repère) × jour de l'entité | `date, entity_type, entity_id, benchmark_id` | ✅ J5 |
| `simulation_manifest` | 1 par exécution | — | ✅ `manifest.json` |

### 2.1 Colonnes livrées au J1

**`institutions`** : `institution_id` (I1 à I3), `name` (« Société N »), `strategy_profile`
(`prudent`, `balanced`, `growth` : intention de départ), `opened_at` (ouverture du premier compte),
`choice_reason`, `risk_appetite` (variable latente tirée : part en actions visée), `fee_level`
(multiplicateur latent des frais), `savings_weight_prior` (poids d'épargne a priori, logistique-normale
tronquée ; le comportement du J3 le fera évoluer).

**`accounts`** : `account_id` (C01…, par ordre d'ouverture), `institution_id`, `regime` (`CELI`,
`CELIAPP`, `REER`, `COMP`), `account_alias` (`<RÉGIME>-<n>` : un compte, jamais une catégorie légale),
`opened_at`, `closed_at` (vide au J1).

**`funds`** : identité (`fund_id` F<institution><rang>, `institution_id`, `archetype`, `fund_name`
marqué « (fictif) », `currency`, `inception_date`) ; risque indicatif `risk_profile_hint` (échelle
Faible … Élevé, celle de `ref.risque`) ; frais `mer_pct` (RFG, déduit de la VL), `account_fee_low_pct` et
`account_fee_high_pct` (frais de compte facturés à part, sous et au-delà du palier
`fee_tier_threshold_cad` par institution), `fee_policy` ; `distribution_frequency` ; change
`equity_fx_hedged`, `fx_exposure_pct` ; taux `duration_years`, `rate_sensitivity` (part de revenu fixe ×
durée) ; `top10_weight_pct`, `trading_cost_pct` (RFO), `turnover_pct` ; `eligible_regimes`.

Les frais de la VL (`mer_pct`) ne seront jamais facturés une seconde fois dans `FRAIS` : `FRAIS` ne
porte que les frais de compte.

**`fund_exposures`** : poids en % au dix-millième ; la somme des cellules d'un fonds vaut 100 et
chaque axe (marge) aussi. Les catégories absentes de l'archétype ne sont jamais tirées (pas de 0,0003 %
d'émergents dans un fonds d'obligations canadiennes).

**`fund_strategic_targets`** : mandat déclaré (valeurs rondes) ; l'allocation effective de
`fund_exposures` est tirée autour. L'écart entre les deux alimente l'écart tactique du rapport.

**`allocation_targets_history`** : `level = institution` (politique de l'institution, à son
ouverture) ou `account` (sous-ensemble de la politique, à l'ouverture du compte) ; `target_weight`
multiple de 5 %, total 100 par cible.

### 2.2 Colonnes livrées au J2

**`fund_prices_daily`** : `date`, `fund_id`, `nav_total_return` (6 décimales), `currency` (`CAD`). Aucune
VL avant `inception_date` ; un fonds lancé pendant l'horizon démarre à `markets.funds.launch_nav`.

**`benchmarks`** : `benchmark_id`, `benchmark_type`, `benchmark_name` (marqué « (fictif) »), `fund_id`,
`institution_id`, `passive_fee_pct` (% par an), `composition` (texte lisible). Trois familles :

| `benchmark_type` | Identifiant | Composition | Rattachement |
|---|---|---|---|
| `composite` | `R-<fund_id>` | expositions du fonds, alpha nul, aucun bruit propre | `fund_id` |
| `policy` | `R-POL-<institution_id>` | cibles initiales de l'institution (`allocation_targets_history`, `level = institution`), rééquilibrage quotidien des composites | `institution_id` |
| `sensitivity` | `R-ACT-MONDE`, `R-EQUILIBRE` | compositions fixées d'avance dans `markets.benchmarks` | — |
| `category` | `R-CAT-<CLÉ>` | composition fixe de `markets.benchmarks.category.<clé>`, style « marché large » ; produit seulement si un fonds de l'univers en relève | archétypes listés dans la catégorie |

Frais passifs par classe d'actifs (`markets.benchmarks.passive_fee_pct`), toujours inférieurs au RFG du
fonds comparé ; la validation le contrôle.

**`benchmarks_daily`** : `date`, `benchmark_id`, `index_total_return` (6 décimales, base 100), `currency`.

**`market_regimes_daily`** : `date`, `regime` (`expansion`, `ralentissement`, `crise`, `reprise`). Régime
latent tiré, exporté pour l'audit : le rapport n'en a pas besoin.

### 2.3 Colonnes livrées au J3

**`events`** : `event_id` (E0001…, ordre chronologique), `date`, `event_type`, `institution_id` et
`account_id` (vides si l'événement touche tout le patrimoine), `description` (texte court), `scenario_impact`
(effet prévu : PAC avant → après, montant, cible avant → après). Types : `ouverture_compte`, `phase_epargne`
(hausse de revenus, pression budgétaire, nouveau projet, reprise de l'épargne), `ajustement_pac`,
`revue_annuelle`, `ajout_fonds`, `prudence_marche`, `retour_cible`, `mois_atypique` (suspension, réduction,
report), `pause_pac`, `prime`, `argent_disponible`, `cadeau`, `remboursement_impot`, `depense_imprevue`,
`plafond_atteint`. Les revues sans effet (inertie) ne sont pas journalisées.

**`external_movements`** : `movement_id` (M00001…, ordre chronologique), `date` (jour ouvrable), `account_id`,
`movement_type` (`PAC`, `PONCTUEL`, `RETRAIT`), `amount_cad` (2 décimales, > 0 apport, < 0 retrait),
`event_id`. Un PAC est une ligne par compte et par prélèvement ; sa ventilation par fonds viendra des ordres
du J4, sans nouveau flux externe. Retraits : CELI et COMP seulement, au plus 50 % des apports nets du compte à
leur date (le J3 ne connaît pas la valeur marchande ; le J4 vérifiera la faisabilité en parts).

**`contribution_room`** : `regime` (`CELI`, `CELIAPP`, `REER`), `year`, `new_room_cad` (plafond annuel ; REER :
moindre de 18 % du revenu gagné de l'année précédente et du plafond en dollars), `room_start_cad`,
`contributions_cad`, `withdrawals_cad` (CELI : rendus aux droits le 1er janvier suivant), `room_end_cad`
(jamais négatif). Règles détaillées dans `src/synthetic_finance/fiscal.py`.

**`persona`** : `year`, `earned_income_cad` (revenu gagné fictif, de l'année précédant l'horizon à la fin),
`celi_eligible`, `reer_unused_end_cad` (droits REER inutilisés à la fin de l'année précédant l'horizon, une
seule ligne). Alimentera `ref.reer_avis` et `ref.parametre` (J6).

**`tax_limits`** : `regime`, `rubric` (`plafond_annuel`, `report_max`, `plafond_vie`, `marge_excedent`,
`fin_periode`), `year`, `amount_cad`, `period_end` (fin de période REER), `rule` (n° de règle de
`sql/plafonds.sql`). L'empreinte SHA-256 de la source est dans `manifest.json` (`inputs.tax_limits`).

### 2.4 Colonnes livrées au J4

L'étape `ledger` réécrit deux tables du J3 sans en changer le contenu : `events` reçoit les événements
`reequilibrage`, `external_movements` les lignes `FRAIS` ; les identifiants des deux tables sont renumérotés
dans l'ordre chronologique (un `event_id` du J3 peut donc changer de numéro, jamais de contenu).

**`internal_trades`** : `trade_id` (T000001…, ordre chronologique), `date`, `account_id`, `fund_id`, `side`
(`BUY`, `SELL`), `units` (3 décimales, > 0), `unit_price` (VL de clôture du jour, 6 décimales),
`gross_amount_cad` (2 décimales), `fee_cad` (0 : aucun frais de transaction), `movement_id` (ordre d'un
`PAC`, `PONCTUEL`, `RETRAIT` ou `FRAIS`) ou `event_id` (ordre d'un `reequilibrage`), jamais les deux. Un
apport = la somme de ses achats ; un retrait ou un frais = la somme de ses ventes ; un rééquilibrage, ventes
= achats, sans flux externe.

**`positions_daily`** : `date`, `account_id`, `fund_id`, `units` (cumul des ordres), `market_value_cad`
(parts × VL, au cent). Une ligne par fonds détenu à la clôture.

**`account_values_daily`** : `date`, `account_id`, `cash_cad` (0), `invested_value_cad` (Σ des positions),
`total_value_cad`. Une ligne par compte ouvert et par jour ouvrable, à 0 avant le premier apport.

**`FRAIS`** (`external_movements`) : au dernier jour ouvrable du mois, par compte, Σ des valeurs des fonds ×
taux annuel du fonds ÷ 12, arrondi au cent, prélevé par rachat de parts au prorata. Taux
`account_fee_low_pct` si l'actif du ménage chez la société est sous `fee_tier_threshold_cad`,
`account_fee_high_pct` à partir du seuil (comme `rapport.seuil`). Un frais inférieur à un millième de la part
la moins chère du compte n'est pas prélevé. `event_id` vide : un frais ne naît d'aucune décision.

**`events`, type `reequilibrage`** : un échange (ventes, puis achats du même montant) décidé sur la clôture de
la veille, exécuté à la VL du jour. Deux causes : une nouvelle cible du J3 (`revue_annuelle`, `ajout_fonds`,
`prudence_marche`, `retour_cible`, même compte et même date), ou un regard sur la dérive (½ Σ |poids − cible|,
en points), programmé d'avance (`ledger.drift_check_months`), qui la trouve au-delà du seuil du compte
(`ledger.drift_threshold_pts`). L'échange corrige toute la dérive (`full_rebalance_probability`) ou une
fraction tirée (`rebalance_fraction`) ; sous `rebalance_min_cad`, rien n'est fait. `scenario_impact` donne
le montant prévu, la fraction et la dérive avant → après, à la clôture de la veille.

Exécution des apports : un `PAC` suit la cible du compte en vigueur ; un `PONCTUEL` comble d'abord les fonds
sous-pondérés à la clôture de la veille ; un `RETRAIT` vend au prorata des valeurs de la veille et fait échouer
le moteur (`GrandLivreError`) si le compte ne vaut pas le montant demandé.

### 2.5 Colonnes livrées au J5

Mesures calculées après la simulation, sur le seul grand livre et les repères : l'étape `performance` ne tire
rien et ne modifie aucune table des J1 à J4. Rendements en fraction (0,01 = 1 %), 10 décimales.

**`performance_daily`** : `date`, `entity_type` (`account`, `institution`, `portfolio`), `entity_id`
(`account_id`, `institution_id` ou `PORTFOLIO`), `market_value_cad` (V⁺ : Σ des `total_value_cad` de ses comptes
ouverts, après flux), `net_external_flow_cad` (F : PAC + PONCTUEL + RETRAIT du jour ; jamais les FRAIS),
`fees_cad` (FRAIS du jour, ≤ 0), `daily_twr` (r = (V⁺ − F) ÷ V⁺ de la veille − 1 ; vide le jour qui suit une
valeur nulle, en particulier le jour d'ouverture), `cumulative_twr` (Π(1 + r) − 1 depuis l'ouverture). Les flux
s'exécutant à la VL de clôture, V⁺ − F est la valeur avant flux, au résidu d'arrondi des parts près ; les FRAIS y
restent et réduisent le rendement. Une institution et le portefeuille se calculent sur les valeurs et flux
agrégés, jamais en moyennant des TWR.

**`performance_periods`** : `entity_type`, `entity_id`, `period` (année, ou `inception`), `start_date` (dernière
clôture avant la période, ou jour d'ouverture si l'entité ouvre dans la période), `end_date`, `days`,
`start_value_cad` (0 si l'entité ouvre dans la période), `contributions_cad` (PAC + PONCTUEL), `withdrawals_cad`
(RETRAIT, ≥ 0), `fees_cad` (≤ 0), `investment_result_cad` (fin − début − apports + retraits − frais),
`end_value_cad`, `twr` (Π(1 + r) − 1 sur la période ; vide sans aucun rendement), `mwr`, `mwr_annualized`,
`mwr_status`. MWR : taux ρ qui annule Σ c (1 + ρ)^(−τ), flux vus de l'épargnant (valeur de début et apports
< 0, retraits et valeur de fin > 0, FRAIS hors flux), τ en années de 365 jours ; une période de moins de
`performance.annualize_min_days` jours rend le taux de la période (`mwr_annualized` faux). Racines cherchées dans
`performance.mwr_bounds` ; `mwr` vide quand `mwr_status` vaut `aucun changement de signe` (période sans valeur ni
flux, par exemple un compte ouvert jamais alimenté), `plusieurs racines` ou `non convergé`.

**`counterfactual_daily`** : `date`, `entity_type`, `entity_id`, `benchmark_id`, `market_value_cad`,
`net_external_flow_cad`, `daily_twr`, `cumulative_twr`. Les mêmes PAC, PONCTUEL et RETRAIT que l'entité, aux
mêmes dates, placés dans un repère à l'indice de clôture (parts en précision double, valeur arrondie au cent) ;
aucun FRAIS de compte, seuls les frais passifs déjà dans l'indice. Institution : `R-POL-<institution_id>` ;
portefeuille : `R-POL` (somme des trois contrefactuels de politique, identifiant propre au J5) et les repères de
contexte `performance.context_benchmarks`. Un retrait au-delà de la valeur du contrefactuel arrête le moteur
(`PerformanceError`).

### 2.6 Catégories

| Axe | Codes exportés | Catégorie du rapport (`rapport.categorie`) |
|---|---|---|
| Classe d'actifs | `equity`, `fixed_income`, `cash`, `other` | Actions, Revenu fixe, Trésorerie, Alternatifs |
| Géographie | `canada`, `united_states`, `europe`, `asia_pacific`, `emerging`, `other` | Canada, États-Unis, Autres pays (les quatre derniers) ; la trésorerie passe en « Trésorerie et non ventilé » par sa classe |
| Style | `broad_market`, `value`, `quality`, `growth`, `dividend`, `fixed_income`, `cash`, `real_assets` | Mixte (les trois premiers), Croissance, Dividendes, Revenu fixe, Trésorerie, Alternatifs |

## 3. Correspondance avec `finance_ve01` (adaptateur du J6) ✅

L'adaptateur écrit dans les tables que lisent déjà les vues ; ni les vues ni le modèle ne changent. Il relit les
CSV de `data/` et écrit `finance_ve01/<schéma>.<table>.csv` (colonnes et ordre de chargement : `adapter.TABLES`),
plus `finance_ve01/distributions.csv`, journal des versements hors base (`date`, `fund_id`, `rate`,
`per_unit_income`, `per_unit_capital_gain`, `nav_total_return`, `nav_ex_before`). Le chargement se fait hors du
paquet (`scripts/charger_synthetique.py`, à la racine du projet).

Règles telles que livrées :

- **Distributions** (section `[adapter]`, flux pseudoaléatoire `adapter`, un sous-flux par fonds) : rendement
  distribué annuel tiré uniformément dans la plage de l'archétype ; versement mensuel (dernier jour ouvrable du
  mois, taux ÷ 12) ou annuel (jour ouvrable tiré du 20 au 31 décembre), bruit log-normal par versement ; en
  décembre, part tirée du gain de l'année au-delà du rendement versé, en gains en capital ; le monétaire verse
  chaque mois tout son gain (VL ex à peu près constante). Taux τ = fraction de la VL avant versement :
  k(d) = k(d−) × (1 − τ), VL ex = VL totale × k, distribution par part = VL totale × k(d−) × τ.
- **Parts publiées** : round(U ÷ k, 3) après chaque opération, U = parts du grand livre ; ni dérive ni rendement
  fictif. Un versement donne une ligne « Distribution réinvestie » par compte détenteur la veille,
  montant = parts de la veille × distribution par part, au cent ; aucune ligne si le montant et la variation de
  parts sont nuls (versement de moins d'un cent, invisible au rapport ce jour-là).
  À une même date : versements, puis ordres du jour.
- **Libellés** (propres au jeu fictif) : `PAC` « Achat — versement programmé », `PONCTUEL` « Achat — versement ponctuel », `RETRAIT`
  « Rachat — retrait », `FRAIS` « Frais de gestion » (une ligne par fonds vendu), rééquilibrage « Arbitrage — vente vers
  <fonds> » (vente) et « Arbitrage — achat depuis <fonds> » (achat), contrepartie = le plus gros ordre de sens opposé du même événement.
- **Profils** : un seul par fonds, daté du début de l'horizon (expositions constantes au J1), donc applicable à
  tous les points. Monétaire : section `secteur` ; fonds d'actions : `actif` (actions, trésorerie), style du
  fonds = style dominant de ses actions ; autres : `actuelle` (classes, sous-jacents par style) et `cible`
  (`fund_strategic_targets`) ; tous sauf le monétaire : `pays` (géographie hors trésorerie).
- **`ref.fonds`** : `nom_court` = « <fund_id> – <nom> » ; profil Épargne, Revenu ou Actions pour un mandat d'une
  seule classe, sinon Conservateur, Modéré ou Croissance selon que actions + autres font moins de 45, moins de
  70 ou plus ; mandat Canada (≥ 65 % hors trésorerie), Marchés émergents (≥ 50 %), Amérique du Nord (Canada +
  États-Unis ≥ 85 %), sinon Mondial.
- **`ref.symbole`** : la colonne `nom_yahoo` du schéma est écrite `nom` (nom du fonds) dans le fichier, pour qu'aucun
  nom de source de cours réelle n'entre dans le paquet ; le chargeur la verse dans `nom_yahoo`.
- **Cours** : `SYN-<fund_id>` (clôture = VL ex à 4 décimales) ; `SYN-<benchmark_id>` pour chaque repère
  (clôture et clôture ajustée = indice).
- **Avis REER** : maximum déductible = droits du J3 au début de l'année de déduction ; toute cotisation déduite
  l'année même ; cotisations inutilisées nulles la première année.

| Table de `finance_ve01` | Source synthétique | Règle |
|---|---|---|
| `ref.compte` | `accounts`, `institutions` | `alias` = `account_alias` ; `numero` = `FICT-<account_id>` ; `genre` = `regime` ; `societe` = `name` ; `ferme_le` = `closed_at` |
| `ref.fonds` | `funds`, expositions | `code_fa` = `fund_id` ; `nom_court` dérivé du nom ; `profil` (Épargne … Actions) et `mandat` (Mondial, Canada, Amérique du Nord, Marchés émergents) dérivés des parts par classe et par géographie |
| `pub.profil` | `funds` | `rfg` = `mer_pct` ; `frais_moins` / `frais_plus` = frais de compte sous / au-delà du palier ; `profil_risque` = `risk_profile_hint` ; `type_fonds` dérivé de la classe dominante |
| `pub.profil_ligne` | `fund_exposures`, `fund_strategic_targets` | `actuelle` (classes, sous-postes par style) et `cible` pour les fonds multiclasses ; `actif` (actions et trésorerie) pour les fonds d'actions ; `pays` par région |
| `ref.style`, `ref.geographie` | catégories du § 2.6 | libellés des sous-postes et des régions ajoutés aux tables de correspondance |
| `pub.cours`, `ref.symbole` | `fund_prices_daily` | `cloture` = VL synthétique ; symbole fictif par fonds |
| `ref.repere`, `pub.cours` (`cloture_ajustee`) | `benchmarks`, `benchmarks_daily` | repères synthétiques, tirés des mêmes facteurs que les fonds : `ref.repere` d'un fonds = le repère de catégorie de son archétype `R-CAT-<CLÉ>` (J6b ; le composite reste livré pour l'oracle du J5) ; politiques et repères de contexte pour les comparaisons de stratégie |
| `fait.transaction`, `fait.historique` | `external_movements`, `internal_trades` | `PAC` → « Achat — versement programmé », une ligne par fonds ; `PONCTUEL` → « Achat — versement ponctuel » ; `RETRAIT` → « Rachat — retrait » ; `FRAIS` → « Frais de gestion » ; distributions → « Distribution réinvestie » ; arbitrages → « Arbitrage — achat depuis » / « Arbitrage — vente vers » |
| `fait.sommaire` | `positions_daily` | positions à l'arrêté, parts converties en VL ex-distribution |
| `pub.rapport_annuel` | `funds`, distributions | distributions par part et par exercice (1ᵉʳ octobre au 30 septembre) : revenu courant en dividendes pour la part actions, en revenus pour le reste ; gains en capital de décembre ; aucun remboursement de capital ; `rfg` = `rfg_avant` = `mer_pct`, `rfo` = `trading_cost_pct`, `rotation` = `turnover_pct` |
| `ref.reer_avis`, `ref.parametre` | personnage fictif (J3) | maximum déductible reconstruit d'une année sur l'autre ; première année CELI fictive |
| `fait.releve`, `fait.releve_cotisation`, `ref.*_hors_export`, `ref.transfert_*` | — | vides : aucun compte sans export, aucun transfert interrégimes modélisé |

## 4. Écarts assumés au cahier des charges

- Configuration en TOML (`tomllib`, bibliothèque standard) plutôt qu'en YAML : une dépendance en moins.
- Deux tables de plus : `fund_exposures_by_axis` (vues agrégées demandées au § 3.3) et
  `fund_strategic_targets` (mandat déclaré, nécessaire à l'écart tactique du rapport).
- Distributions : la VL exportée est en rendement total (MVP du § 4, hypothèse H3 du contrat J2) et le
  grand livre tient ses parts dans cette VL. Le rapport consommant des distributions, la VL ex-distribution,
  les distributions par part et la conversion des parts seront dérivées par l'adaptateur du J6 (décision
  du contrat J4, H4), de façon cohérente avec le rendement total ; jamais ajoutées en plus.
- Un seul facteur de change (USD contre CAD) pour toute devise étrangère ; il s'applique à la part non
  couverte `fx_exposure_pct`. Aucune série de change exportée.
- Taux : taux fantôme d'Ornstein-Uhlenbeck, taux observé = softplus du fantôme (lissage
  `lower_bound_smoothing_bp`). Les taux restent positifs sans aucune borne ; le monétaire peut rendre
  un peu moins que zéro quand le taux court passe sous son RFG.
- Jours fériés non modélisés.
- Horizon de 60 mois, du 2021-11-01 au 2026-10-30, paramétrable.
- Plafonds fiscaux : lus dans `sql/plafonds.sql`, hors du dossier du générateur, parce que c'est la seule
  source du projet (aucun plafond ne s'écrit ailleurs) ; le chemin n'est pas écrit dans le code, il est
  cherché au-dessus de la configuration. Le plafond REER en dollars (règle R11) y a été ajouté au J3.
- Trois tables de plus au J3 : `contribution_room`, `persona`, `tax_limits` (droits et situation fictive,
  vérifiables sans base de données).
- Retraits bornés à 50 % des apports nets du compte faute de valorisation avant le grand livre ; le J4
  vérifie leur faisabilité en valeur (aucun échec sur les 21 graines de contrôle).
- Aucune taxe de vente sur les frais de compte (un taux de TPS/TVH serait un montant fiscal à sourcer) ;
  aucun frais de transaction.
- Un versement plafonné par les droits dont le reliquat versable est sous `behaviour.min_pac` est réorienté
  en entier (correction faite au J4 : le J3 pouvait verser un PAC de 0,01 $, inexécutable en parts).
- TWR quotidien au lieu du Dietz modifié mensuel du rapport (`rapport.performance`) : les tables du J5 sont
  l'oracle indépendant contre lequel le J6 mesurera l'écart, elles ne remplacent pas les vues SQL. Le résidu
  d'arrondi des parts (J4) reste dans la valeur, donc dans le rendement : sur un marché plat sans frais, le TWR
  cumulé d'une institution s'écarte de 0 de 3e-4 au plus sur la graine 20261103.
- Écart Dietz – TWR (J6) : mesuré par `scripts/recette_synthetique.py --controle oracle` et commenté dans
  `adapter_report.md` ; aucune vue n'est modifiée pour le réduire.
- Distributions par part de `pub.rapport_annuel` arrondies au cent (colonnes `numeric(10, 2)`) : un fonds qui
  verse moins d'un demi-cent par part sur un exercice y paraît sans distribution.
- Allocation effective dans `performance_report.md` seulement, sans table : le modèle Power BI la recalcule
  depuis les positions et les expositions.
- Contrefactuel sans frais de compte : il paie les frais passifs de son repère, ce que l'épargnant passif aurait
  payé ; l'écart de frais est imputé à part dans la décomposition du rapport.
