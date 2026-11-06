# Contrat de jalon — Générateur synthétique, J3 : comportements et événements

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03 (H1 et H2 confirmées)
- **Statut :** accepté (C5 constaté par le responsable le 2026-11-04)

## Objectif

Construire le moteur de comportement du cahier des charges (§ 5 et § 3.2) : un épargnant fictif
dont les décisions découlent de variables latentes (capacité d'épargne, tolérance au risque,
besoins de liquidités) et d'un journal d'événements, et non de montants tirés mois par mois. Il
produit les flux externes `PAC`, `PONCTUEL` et `RETRAIT`, les changements de cible par compte et les
droits de cotisation par régime, dans le respect des restrictions fiscales. Il ne lit le marché que
dans le passé : aucune décision ne connaît un prix futur.

## Livrables

| Livrable | Chemin |
|---|---|
| Moteur de comportement (capacité latente, phases, ventilation, ponctuels, retraits, révisions de cible) | `Generateur-data-fictive/src/synthetic_finance/behaviour.py` |
| Droits de cotisation (CELI, CELIAPP, REER), plafonds lus dans `sql/plafonds.sql` | `Generateur-data-fictive/src/synthetic_finance/fiscal.py` |
| Paramètres de comportement et du personnage fictif, commentés | `Generateur-data-fictive/configs/base.toml`, sections `[behaviour]` et `[persona]` |
| Étape `behaviour` de la CLI, contrôles ajoutés au validateur | `Generateur-data-fictive/src/synthetic_finance/cli.py`, `validation.py` |
| Tests du comportement, de la sûreté fiscale, multi-graines, reproductibilité | `Generateur-data-fictive/tests/test_behaviour.py`, `test_tax_safety.py`, `test_behaviour_seeds.py`, `test_reproducibility.py` |
| Rapport de comportement | `Generateur-data-fictive/outputs/typical_seed_20261103/behaviour_report.md` |
| Export, graine 20261103 | `Generateur-data-fictive/outputs/typical_seed_20261103/data/events.csv`, `external_movements.csv`, `contribution_room.csv`, `allocation_targets_history.csv` (lignes ajoutées) |
| Contrat de données et README à jour | `Generateur-data-fictive/docs/contrat_donnees.md`, `README.md` |

Toutes les commandes se lancent depuis `Generateur-data-fictive/` avec `.venv/Scripts/python`.
Preuves sous `jalons/preuves/generateur-j3-comportements/`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Exécution, grain et intégrité.** `generate --stage behaviour` puis `validate` s'exécutent sans erreur ; le validateur affiche chaque contrôle un par un. `external_movements.csv` ne contient que `PAC`, `PONCTUEL` et `RETRAIT` (`FRAIS` relève du J4), une ligne par compte et par versement, `amount_cad` à 2 décimales, > 0 pour les apports et < 0 pour les retraits. Chaque mouvement porte un compte existant, une date ouvrable comprise entre l'ouverture du compte et `end_date` (et avant `closed_at` s'il y en a une). Chaque `PONCTUEL`, chaque `RETRAIT`, chaque changement de niveau de PAC et chaque nouvelle cible de compte renvoie à un `event_id` existant de `events.csv`, daté au plus tard le jour de son effet. Aucune clé en double, aucune référence orpheline. | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage behaviour` puis `python -m synthetic_finance validate --path outputs/typical_seed_20261103` → `generate-validate.txt` |
| C2 | **Restrictions des régimes (bloquant), sur la graine 20261103 et les graines 1 à 20.** Aucun `RETRAIT` sur un REER ni sur un CELIAPP. Aucun versement CELIAPP avant `celiapp_available_from` ni avant l'ouverture du compte. Pour chaque régime et chaque année, cotisations ≤ droits disponibles, recalculés par le test indépendamment de `fiscal.py` : CELI = plafonds annuels cumulés depuis la première année d'admissibilité fictive, moins les cotisations, plus les retraits de l'année précédente ; CELIAPP = 8 000 $ par an, report plafonné, 40 000 $ à vie ; REER = maximum déductible fictif (18 % du revenu fictif de l'année précédente, plafonné au maximum annuel en dollars) plus les droits inutilisés, années de déduction selon `ref.periode_reer`. Tous les plafonds viennent de `sql/plafonds.sql` (le plafond REER en dollars y est ajouté, sourcé canada.ca par `documentaliste`) ; aucun montant fiscal dans le code Python ni dans `base.toml`. Échecs : 0 sur 21 exécutions. | `pytest -q tests/test_tax_safety.py -rA` → `pytest-fiscal.txt` ; lecture de `fiscal.py`, `sql/plafonds.sql` |
| C3 | **Comportement plausible.** Graine 20261103, chaque point bloquant ; graines 1 à 20, taux d'échec de chaque point imprimé, bloquant seulement pour (f) et (g). (a) Médiane du PAC total mensuel, sur les mois où un compte est ouvert, entre 500 et 1 000 $. (b) De 2 à 5 événements de phase d'épargne sur l'horizon. (c) Au moins un plateau de 6 mois ou plus au même PAC total ; aucun compte au PAC identique sur toute sa durée ; aucune suite de 12 hausses mensuelles consécutives du PAC total. (d) Au moins un mois atypique (PAC suspendu ou réduit d'au moins 30 %) ; mois sans aucun PAC ≤ 15 % des mois après la première ouverture. (e) Ponctuels : montants de 100 à 10 000 $, aucun mois civil qui en reçoive un chaque année. (f) Au plus 30 % des montants ponctuels sont des multiples de 500 $. (g) Retraits : chacun ≤ 50 % des apports nets du compte à sa date ; au moins un retrait sur l'horizon dans au moins la moitié des 20 graines. (h) Parts des institutions dans les PAC de l'horizon : aucune à moins de 2 points de 1/3 pour toutes. | `pytest -q tests/test_behaviour.py tests/test_behaviour_seeds.py -rA` → `pytest-comportement.txt` |
| C4 | **Aucune anticipation, reproductibilité, non-régression.** Un test remplace toutes les VL et tous les indices postérieurs à une date t (plusieurs t tirés) par ceux d'une autre graine : événements, mouvements et cibles datés avant t restent identiques. Deux exécutions à graine égale donnent des CSV identiques (SHA-256), une autre graine des mouvements différents. Les CSV des étapes `universe` et `markets` produits à l'étape `behaviour` sont identiques à ceux du commit `8aeaff6`. Le balayage de fuite, étendu aux nouveaux fichiers, ne trouve rien et le moteur n'ouvre aucune connexion réseau. | `pytest -q tests/test_behaviour.py::test_aucune_anticipation tests/test_reproducibility.py` → `repro.txt` ; `git diff --stat 8aeaff6 -- Generateur-data-fictive/outputs/typical_seed_20261103/data/` (lignes des fichiers J1-J2) → `non-regression.txt` ; `python scripts/balayage_fuite.py` → `fuite.txt` |
| C5 | **Lecture par le responsable.** `behaviour_report.md` donne : la chronologie des événements ; le PAC total mois par mois ; un tableau année × institution × régime (PAC, ponctuels, retraits) ; les droits par régime et par année (droits au début, cotisations, retraits, droits restants) ; les changements de cible avec leur événement déclencheur. Le responsable juge que l'histoire ressemble à celle d'un épargnant imparfait : ni liste régulière, ni chaos sans cause. | `outputs/typical_seed_20261103/behaviour_report.md`, lu par le responsable |

## Hypothèses à confirmer

- **H1 — Capacité d'épargne :** de 500 à 1 000 $ par mois pour l'ensemble du patrimoine (§ 5.1 et
  configuration du cahier des charges). Conséquence : sur l'horizon 2021-11 → 2026-10, avec les comptes
  du J1 (Société 1 et 2 ouvertes fin 2023 et début 2024), le patrimoine final tournera autour de 40 à
  60 k$ selon le marché, loin des ~200 k$ du jeu de `generateur/generer.py`.
- **H2 — Dépassements de droits :** aucun dans `typical` (C2). L'alerte de dépassement du rapport
  sera couverte par le scénario `adversarial` (J6). Un apport qui dépasserait les droits est
  réorienté vers un COMP ouvert, ou reporté, et l'événement est journalisé.
- **H3 — Retraits et solde :** sans grand livre (J4), le J3 ne connaît pas la valeur marchande d'un
  compte. Garde-fou : un retrait ≤ 50 % des apports nets du compte à sa date ; le J4 vérifiera la
  faisabilité réelle (aucune part négative) et échouera explicitement sinon.
- **H4 — Signal de marché :** les décisions (prudence passagère après une baisse, report d'un
  ponctuel) ne lisent que le repli observé jusqu'à la veille d'un repère, jamais une VL future.
- **H5 — Personnage fictif :** première année d'admissibilité au CELI, revenu annuel et maximum
  déductible REER tirés de lois (graine), jamais écrits à la main ; ils restent cohérents d'une
  année sur l'autre.

## Hors périmètre

Ordres d'achat et de vente, ventilation des PAC par fonds, positions, encaisse, frais de compte
(`FRAIS`) et rééquilibrages déclenchés par la dérive des positions (J4). TWR, MWR, contrefactuel
passif (J5). Scénarios `stress` et `adversarial`, adaptateur vers `finance_ve01` (J6). Transferts
interrégimes, retraits admissibles du CELIAPP, fermeture de compte. Les comptes et fonds du J1 ne
changent pas ; l'ancien `generateur/generer.py` n'est ni modifié ni supprimé.

## Modifications du contrat

- 2026-11-03 — Livrables, sans changement de critère : deux tables de plus, `persona.csv` (situation
  fictive par année) et `tax_limits.csv` (plafonds lus, recopiés), nécessaires pour que le recalcul
  indépendant de C2 se fasse sur les seuls CSV ; `sql/plafonds.sql` reçoit le plafond REER en dollars
  2020 à 2026 (règle R11, canada.ca vérifié par `documentaliste`), comme prévu en C2. Correction du
  rapport d'univers : la colonne « Allocation cible à l'ouverture » ne liste plus les révisions du J3.
- 2026-11-03 — Preuve de C4 renforcée, sans changement de critère, en réponse à la réserve du verdict :
  `test_aucune_anticipation` porte sur les 21 graines ; les coupures sont tirées une par sixième de
  l'horizon et s'ajoutent au jour et à la veille de chaque décision `prudence_marche` (19 décisions) ;
  trois marchés de remplacement (autre graine, hausse ×2, krach ×0,5) ; comparaison jusqu'au jour t
  inclus. Contrôle de sensibilité : une hausse dès la veille supprime chaque décision. Test de mutation
  (repli lu le jour même) : 8 échecs sur 8 graines porteuses de décisions. `repro.txt` régénéré.

## Verdicts

### 2026-11-03

```text
JALON    : Générateur synthétique, J3 : comportements et événements
VERDICT  : ACCEPTÉ (réserve : l'essentiel des preuves est attesté, voir plus bas)
CRITÈRES :
- [C1] PASS (attesté) — generate-validate.txt:41-47 : 6 contrôles `comportement_*` affichés un par un, tous PASS ; 210 mouvements = 202 PAC + 7 ponctuels + 1 retrait, aucun FRAIS. Lu moi-même : validation.py:416-457 contrôle types, signes, cent, jour ouvrable, compte, bornes d'ouverture, `closed_at`, `event_id` existant et daté au plus tard le jour du mouvement, cibles de compte sans événement. Limite : le lien « changement de niveau de PAC → event_id » n'est vérifié que par existence de l'`event_id` sur chaque mouvement. Échantillon lu dans external_movements.csv:3-5 (E0002, E0003), cohérent.
- [C2] PASS (attesté) — pytest-fiscal.txt:5-20 : 0/21 dépassement, 0/21 écart au recalcul, 0/21 retrait REER/CELIAPP. Lu moi-même : test_tax_safety.py:31-75 recalcule les droits de son côté, sans importer fiscal.py ; fiscal.py ne contient que `TAUX_REER = 0.18` (un taux, pas un montant) ; plafonds REER 2020-2026 dans sql/plafonds.sql:67-78 avec URL canada.ca ; test AST sans constante égale à un plafond (pytest-fiscal.txt:14-20).
- [C3] PASS (attesté) — pytest-comportement.txt:3-26 : (a) 820 $, (b) 4 phases, (c) plateau de 9 mois, (d) 4 mois atypiques et 4 mois sans PAC sur 60, (e) OK, (f) 14 %, (g) OK, (h) parts de 23,5 / 14,6 / 61,9 %. Taux d'échec par point imprimés sur 20 graines (:46-58), (f) et (g) à 0/20, retraits dans 15/20 graines (:61). Recompté dans behaviour_report.md : PAC 49 815 $ = somme des années, 7 ponctuels, 4 phases.
- [C4] PASS (attesté) — repro.txt : 11 passed ; non-regression.txt : seul allocation_targets_history.csv change, +22 lignes, 0 suppression ; fuite.txt:15 « AUCUNE FUITE », 52 fichiers balayés dont outputs/ et tests/ (balayage_fuite.py:31-32). Anticipation : voir la réserve.
- [C5] À CONSTATER PAR LE RESPONSABLE — la lecture est la sienne. Les cinq sections demandées sont présentes dans behaviour_report.md : chronologie l.16-58, PAC mensuel l.60-71, année × institution × régime l.73-100, droits l.105-126, cibles et événements l.128-144.
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE :
- Relancer `pytest -q tests/test_tax_safety.py tests/test_behaviour.py tests/test_behaviour_seeds.py tests/test_reproducibility.py` et `python -m synthetic_finance validate`. Je n'ai rien exécuté : C1 à C4 reposent sur les sorties enregistrées par l'exécutant.
- Réserve sur `test_aucune_anticipation` (test_behaviour.py:49-68) : les 4 coupures tirées (2024-12-27 à 2026-06-26) tombent toutes après la seule décision liée au marché de la graine typique, la prudence E0012 du 2023-06-01. Le test respecte la lettre du contrat mais ne met pas ce chemin à l'épreuve. Le code lit bien le repli au jour ouvrable strictement antérieur (behaviour.py:143-146), donc la garantie tient par construction, pas par le test.
- Lire behaviour_report.md (C5) : plateau de 9 mois, 4 mois à 0, 4 phases, un retrait de 1 400 $ et 7 ponctuels. Voir si l'histoire ressemble à celle d'un épargnant imparfait.
```

C5 constaté par le responsable le 2026-11-04.
