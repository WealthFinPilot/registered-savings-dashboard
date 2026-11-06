# Contrat de jalon — Générateur synthétique, J5 : rendements et repères

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03
- **Statut :** accepté (modifications de C2 et C4 validées et C5 constaté par le responsable le 2026-11-03)

## Objectif

Construire le moteur E du cahier des charges (§ 7, § 8, § 10 « Performances », jalon 5 du § 12) : les
mesures calculées **après** la simulation, à partir du seul grand livre du J4 et des repères du J2. TWR
quotidien chaîné aux niveaux compte, institution et portefeuille consolidé ; MWR (XIRR) par année civile
et depuis l'ouverture ; réconciliation variation du patrimoine = apports nets + résultat de placement −
frais ; contrefactuel passif qui reçoit les mêmes flux externes aux mêmes dates. Le moteur E ne modifie
aucune table des J1 à J4.

Rôle pour la suite : le rapport Power BI calcule son TWR en Dietz modifié mensuel chaîné
(`rapport.performance`, `rapport.rendement_annuel`). Les tables du J5 sont l'oracle indépendant contre
lequel l'adaptateur du J6 mesurera cet écart ; elles ne remplacent pas les vues SQL.

## Livrables

| Livrable | Chemin |
|---|---|
| Moteur des mesures (TWR, MWR, réconciliation, contrefactuel) | `Generateur-data-fictive/src/synthetic_finance/performance.py` |
| Paramètres des mesures et du contrefactuel, commentés | `Generateur-data-fictive/configs/base.toml`, section `[performance]` |
| Étape `performance` de la CLI, contrôles ajoutés au validateur | `Generateur-data-fictive/src/synthetic_finance/cli.py`, `validation.py` |
| Recalcul indépendant (n'importe pas `performance.py`) et tests | `Generateur-data-fictive/tests/criteres_performance.py`, `test_performance.py`, `test_performance_seeds.py`, `test_reproducibility.py` |
| Rapport des rendements | `Generateur-data-fictive/outputs/typical_seed_20261103/performance_report.md` |
| Export, graine 20261103 | `outputs/typical_seed_20261103/data/performance_daily.csv`, `performance_periods.csv`, `counterfactual_daily.csv` |
| Contrat de données et README à jour | `Generateur-data-fictive/docs/contrat_donnees.md`, `README.md` |

Toutes les commandes se lancent depuis `Generateur-data-fictive/` avec `.venv/Scripts/python`.
Preuves sous `jalons/preuves/generateur-j5-rendements/`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Exécution, grain et intégrité.** `generate --stage performance` puis `validate` s'exécutent sans erreur ; le validateur affiche chaque contrôle un par un. `performance_daily` : une ligne par entité × jour ouvrable où l'entité a au moins un compte ouvert, `entity_type` ∈ {`account`, `institution`, `portfolio`} ; colonnes `market_value_cad` (V⁺, après flux), `net_external_flow_cad` (F : PAC + PONCTUEL + RETRAIT du jour, **sans** `FRAIS`), `fees_cad` (FRAIS du jour, ≤ 0), `daily_twr`, `cumulative_twr`. Au niveau compte, `market_value_cad` = `total_value_cad` de `account_values_daily` ; aux niveaux institution et portefeuille, = Σ des comptes au cent. `performance_periods` : une ligne par entité × période (chaque année civile tronquée à l'ouverture et à l'arrêté, plus « depuis l'ouverture »). `counterfactual_daily` : une ligne par entité contrefactuelle × repère × jour ouvrable. Aucune clé en double, aucune référence orpheline. | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage performance` puis `python -m synthetic_finance validate --path outputs/typical_seed_20261103` → `generate-validate.txt` |
| C2 | **TWR (bloquant), recalculé par le test sans importer `performance.py`, graine 20261103 et graines 1 à 20.** Formule : V⁻ₜ = V⁺ₜ − Fₜ ; rₜ = V⁻ₜ ÷ V⁺ₜ₋₁ − 1, vide quand V⁺ₜ₋₁ = 0 (compte qui vient d'ouvrir : le premier rendement est celui du lendemain du premier apport) ; TWR cumulé = Π(1 + rₜ) − 1. Les frais réduisent V⁻ₜ : ils ne sont jamais neutralisés comme un flux. Égalité au recalcul : 1e-9 par jour. TWR institution et portefeuille recalculés depuis les valeurs et flux agrégés ; l'écart avec la moyenne pondérée et avec la moyenne simple des TWR des comptes est imprimé. Scénarios de contrôle sur la graine 20261103 (infrastructure du J4) : VL constantes et frais à 0 → TWR cumulé = 0 à 1e-9 à tous les niveaux ; VL constantes avec frais → TWR < 0 et égal au produit des (1 − frais du jour ÷ V⁻ avant frais), à 1e-9. Versement sans saut : un PONCTUEL de 1 000 000 $ ajouté sur un compte COMP un jour t tiré, grand livre rejoué → `daily_twr` du jour t inchangé à 1e-12, et celui des jours suivants à moins de 1e-6 (résidu d'arrondi des parts), à tous les niveaux. | `pytest -q tests/test_performance.py tests/test_performance_seeds.py -rA -k "twr"` → `pytest-twr.txt` |
| C3 | **MWR et réconciliation (bloquant).** Pour chaque entité × période de `performance_periods` : valeur de fin = valeur de début + apports − retraits + frais (≤ 0) + résultat de placement, au cent ; le résultat de placement recalculé par le test comme Σ parts détenues à la veille × variation de VL (méthode du J4) égale celui du moteur, écart ≤ somme des résidus d'arrondi. MWR : taux XIRR (Act/365, flux de l'épargnant : apports < 0, retraits > 0, valeur de début < 0, valeur de fin > 0 ; FRAIS hors flux), recalculé par le test avec un solveur indépendant (bissection) à 1e-6 ; annualisé si la période dure au moins 365 jours, sinon taux de la période, drapeau `mwr_annualized`. MWR vide avec motif écrit (`aucun changement de signe`, `plusieurs racines`, `non convergé`) plutôt qu'un taux inventé ; le nombre de vides par motif est imprimé pour les 21 graines. Sur les 21 graines, nombre de périodes où TWR et MWR sont de signes opposés imprimé (diagnostic, sans quota). | `pytest -q tests/test_performance.py tests/test_performance_seeds.py -rA -k "mwr or reconciliation"` → `pytest-mwr.txt` |
| C4 | **Contrefactuel passif, non-biais, reproductibilité, non-régression.** Contrefactuel de chaque institution dans son repère de politique `R-POL-<institution_id>` ; portefeuille = Σ des trois, plus deux contrefactuels de contexte sur tous les flux du portefeuille (`R-ACT-MONDE`, `R-EQUILIBRE`). Chacun reçoit exactement les PAC, PONCTUEL et RETRAIT de son périmètre, aux mêmes dates et montants (test : calendriers identiques) ; aucun `FRAIS` de compte (seuls les frais passifs, déjà dans `index_total_return`). Propriétés : TWR d'un contrefactuel = rendement de son indice sur la même période, à 1e-9 ; VL constantes → valeur finale = Σ flux nets au cent ; aucun RETRAIT infaisable sur les 21 graines, sinon échec explicite. Non-biais : la date de composition de chaque `R-POL` précède le premier flux de son institution (politique fixée d'avance) ; écart annualisé institution − politique et sa décomposition (frais : RFG pondéré + FRAIS − frais passifs ; reste : alpha, allocation, rééquilibrages) imprimés pour les 21 graines × 3 institutions, sans seuil. Deux exécutions à graine égale → CSV identiques (SHA-256). Les 19 CSV présents au commit `c6288c3` sont identiques octet pour octet (test SHA-256 contre `git show`). Balayage de fuite : rien. | `pytest -q tests/test_performance.py tests/test_performance_seeds.py tests/test_reproducibility.py -rA -k "contrefactuel or biais or test_reproducibility"` → `repro.txt` ; `git diff --stat c6288c3 -- Generateur-data-fictive/outputs/typical_seed_20261103/data/` → `non-regression.txt` ; `python scripts/balayage_fuite.py` → `fuite.txt` |
| C5 | **Lecture par le responsable.** `performance_report.md` donne : un tableau entité × année (valeur de début, apports, retraits, frais, résultat de placement, valeur de fin, TWR, MWR) pour les trois sociétés et le portefeuille ; la comparaison à chaque politique en TWR et en dollars (contrefactuel), avec la décomposition de l'écart ; l'allocation effective (actions / obligations / encaisse, régions) au 31 décembre de chaque année et à l'arrêté, par société, pondérée par l'encours ; un parcours vérifiable à la main, compte → mouvement → ordres → positions → valeur → rendement, sur le jour d'un gros apport, montrant l'absence de saut du TWR. Le responsable juge les rendements plausibles pour les marchés du J2 et l'écart aux politiques expliqué sans « victoire » non justifiée. | `outputs/typical_seed_20261103/performance_report.md`, lu par le responsable |

## Hypothèses à confirmer

- **H1 — Ordre journalier :** celui du J4 (flux à la VL de clôture, FRAIS en fin de journée le dernier
  jour ouvrable du mois). V⁻ₜ = V⁺ₜ − Fₜ est donc exact, au résidu d'arrondi des parts près ; les FRAIS
  du jour pèsent sur le rendement du jour.
- **H2 — Niveaux :** compte, institution, portefeuille consolidé (§ 7.2). Ni régime ni fonds : le TWR
  d'une position est le rendement de sa VL, déjà dans `fund_prices_daily` ; le rapport agrège par régime
  en DAX à partir des comptes.
- **H3 — Contrefactuel sans frais de compte :** l'épargnant passif paie les frais passifs du repère,
  pas les `FRAIS` de compte de la société. Comparaison « ce que l'épargnant aurait eu », écart de frais
  imputé explicitement dans la décomposition. Parts du contrefactuel en précision double, valeur arrondie
  au cent à l'export.
- **H4 — Allocation effective :** dans le rapport seulement (C5), pas de table CSV : le modèle Power BI la
  recalcule déjà depuis les positions et les expositions (`Exposition`). Une table ne servirait qu'en cas de
  recette comparée au J6.
- **H5 — Pas de nouvel aléa :** le J5 ne tire rien. Aucun flux pseudoaléatoire ajouté, hors le jour t du
  test de versement sans saut (tiré dans le test, pas dans le moteur).

## Hors périmètre

Distributions et VL ex-distribution, adaptateur vers `finance_ve01`, comparaison au Dietz modifié du
rapport (J6). Scénarios `stress` et `adversarial` (J6). Volatilité, pire baisse et risque : déjà dans
`rapport.risque_mesure`, côté SQL. Change, transferts interrégimes. Les tables des J1 à J4 ne changent pas
(C4).

## Modifications du contrat

Toutes du 2026-11-03, en cours de travail. Les deux premières corrigent une tolérance impossible à tenir ;
elles remplacent un seuil fixe par une borne calculée jour par jour, jamais par un simple relâchement.

- **C2, marché plat (erreur du contrat).** « TWR cumulé = 0 à 1e-9 » et « égal au produit des (1 − frais ÷
  V⁻) à 1e-9 » sont impossibles avec la formule même du contrat. V⁻ = V⁺ − F porte le résidu d'arrondi
  des parts de chaque ordre du J4 (jusqu'à 0,0005 × VL + 0,005 $ par ordre) et celui des valeurs au cent.
  Sur un compte de quelques centaines de dollars, cela fait 1e-5 par jour, pas 1e-9. Contrôle retenu,
  chaque jour et à chaque niveau : |r × V⁺ de la veille − frais du jour| ≤ Σ |parts × VL − montant| des
  ordres du jour + 0,005 $ par ligne de position la veille et le jour. Pour le cumul : |1 + TWR − Π(1 + frais
  ÷ V⁺ de la veille)| ≤ Σ des bornes quotidiennes ÷ V⁺. Le plus grand |TWR cumulé| à l'arrêté sans frais est
  imprimé (2,6e-4 pour une institution, graine 20261103).
- **C2, versement sans saut (erreur du contrat).** Jour t : « inchangé à 1e-12 » remplacé par la même
  borne de résidu, celle des deux exécutions. Jours suivants : « moins de 1e-6 d'écart avec l'exécution
  de référence » est faux. Le ponctuel va d'abord aux fonds sous-pondérés (J4), la composition du compte
  change, et ses rendements suivants changent légitimement. Contrôle retenu, plus fort : sur toute
  l'exécution modifiée, chaque jour et à chaque niveau, r × V⁺ de la veille = Σ parts détenues la veille ×
  variation de VL + frais du jour, à la borne de résidu près. Ce même contrôle s'applique aussi à la graine
  20261103 et aux graines 1 à 20 (`test_twr_rendement_du_marche`, `test_twr_graine`). Le jour t est tiré
  hors des fins de mois : les FRAIS du jour portent sur la valeur après apport et changeraient r à bon
  droit.
- **C2, entités non touchées.** Ajout : une entité qui ne contient pas le compte modifié garde un rendement
  identique le jour t.
- **C4, contrefactuel du portefeuille.** Identifiant `R-POL` pour la somme des trois contrefactuels de
  politique. Ce n'est pas un repère de `benchmarks` : le validateur l'admet nommément, le contrat de
  données le documente.
- **C3, motifs de MWR vides.** Sur les 21 graines, 103 périodes sur 1 368 ont `aucun changement de
  signe` : des comptes ouverts mais jamais alimentés, sans aucun flux ni valeur sur la période. La
  graine 17 a même une institution entière dans ce cas (trois comptes, aucun apport, comportement du
  J3). Elle est omise de la décomposition de l'écart (aucun rendement), et le test l'imprime.

## Verdicts

### 2026-11-03

```text
JALON    : Générateur synthétique, J5 : rendements et repères
VERDICT  : ACCEPTÉ (sous réserve de la confirmation des modifications du contrat sur C2, voir ci-dessous)
CRITÈRES :
- [C1] PASS (attesté) — generate-validate.txt:30-63 : 5 étapes générées, 33 contrôles [PASS] affichés un par un, dont performance_grain (9279 lignes, 10 entités), performance_periodes (53) et performance_contrefactuel (6654). Les comptes de lignes recoupent `non-regression.txt` (9280, 54 et 6655 avec l'en-tête). Le code correspond : `performance.py:78-98` (jours où ≥1 compte présent, FRAIS à part). En-têtes de `performance_daily.csv`, `counterfactual_daily.csv` et `performance_periods.csv` conformes.
- [C2] PASS (attesté), avec réserve — pytest-twr.txt:108 : 26 passed. Graines 20261103 et 1 à 20 : pire écart au recalcul 5.0e-11 (seuil 1e-9). Écart avec les moyennes pondérée et simple imprimé (lignes 5, 20, 23…). `criteres_performance.py` n'importe pas `performance.py` (seul `export.lire_csv`). Réserve : le texte du critère n'est pas respecté à la lettre (voir Modifications, contrat l.76-94). Les contrôles « marché plat » et « versement sans saut » utilisent une borne de résidu calculée, pas 1e-9 / 1e-12 / 1e-6. Exemple : TWR cumulé jusqu'à 2,6e-4 sans frais ; écart de 2,9e-6 le jour du versement de 1 M$ (borne 2,6e-5, pytest-twr.txt:17). Les graines 6, 13, 14 et 20 atteignent 99-100 % de leur borne : zéro marge.
- [C3] PASS (attesté) — pytest-mwr.txt:211 : 46 passed. Résultat de placement : pire écart à 98 % de sa borne (graine 13, jamais au-delà). Bissection à ≤ 5.0e-11. Motifs imprimés pour les 21 graines (l.163 : 1265 ok, 103 « aucun changement de signe », 66 périodes de signes opposés). Cas limites : « plusieurs racines » et « aucun changement de signe » testés (l.12-13). Recomptage manuel de la réconciliation sur `performance_periods.csv` l.3-4 : 0 + 1580 − 2,62 − 3,09 = 1574,29 et 1574,29 + 12000 − 90,14 + 0,26 = 13484,41, exact. Le motif « non convergé » existe dans `performance.py:140,164` mais n'est testé nulle part.
- [C4] PASS (attesté) — repro.txt:302 : 41 passed. Flux identiques et TWR contrefactuel = indice à 5.0e-11 (21 graines). VL constantes : valeur = flux nets au cent (l.8-13). Retrait infaisable : échec explicite (l.16, `performance.py:206`). R-POL daté avant le premier apport (l.19-21). Décomposition imprimée pour 62 institutions × graines (63 moins la graine 17 I2, expliqué l.138). SHA-256 de deux processus identiques (l.234-256) ; 19 CSV identiques au commit c6288c3 (l.259) ; `non-regression.txt` ne montre que 3 ajouts ; `fuite.txt:15` : AUCUNE FUITE.
- [C5] À CONSTATER PAR LE RESPONSABLE — preuve : performance_report.md, lu par le responsable.
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE :
1. Confirmer que tu valides les modifications de C2 et de C4 du bloc « Modifications du contrat » (l.73-101). Le contrat est daté « validé 2026-11-03 », mais rien n'indique que ces modifications, faites en cours de travail, aient été approuvées. Si tu refuses les bornes de résidu, C2 devient FAIL.
2. Toutes les preuves de C1 à C4 sont des sorties enregistrées par l'exécutant, non rejouées. Contrôle en 2 minutes : `.venv/Scripts/python -m pytest -q tests/test_performance.py -k twr` depuis `Generateur-data-fictive/`.
3. C5 : lire `performance_report.md`.
```

Modifications du contrat (C2, C4) validées par le responsable le 2026-11-03 ; C5 constaté : jalon accepté.
