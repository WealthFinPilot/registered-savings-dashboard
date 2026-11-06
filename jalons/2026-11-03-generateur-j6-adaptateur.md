# Contrat de jalon — Générateur synthétique, J6 : adaptateur vers `finance_ve01`

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03 (découpage J6 / J7 / J8 et H1 confirmés)
- **Statut :** accepté (modifications de C2 et C3 validées et C5 constaté par le responsable le 2026-11-04)

## Objectif

Verser le jeu synthétique des J1 à J5 dans `finance_ve01`, dans les tables que lisent déjà les vues
`rapport.*`, sans changer ni les vues ni le modèle (contrat de données, § 3). L'adaptateur dérive les
distributions de la VL en rendement total sans changer le rendement total (décision H4 du J4), puis on
mesure, sur la base chargée, l'écart entre le Dietz modifié mensuel du rapport et l'oracle TWR du J5.

Découpage proposé de la fin du § 12 : **J6** adaptateur et recette SQL (ce contrat) ; **J7** bascule du
rapport (`figer.py`, actualisation dans Desktop, recette DAX, segment Année, retrait de
`generateur/generer.py`) ; **J8** scénarios `stress` et `adversarial`, dictionnaire, parcours de
démonstration.

## Livrables

| Livrable | Chemin |
|---|---|
| Adaptateur : tables de `finance_ve01` en CSV, sans base de données (distributions, VL ex, conversion des parts, libellés, profils, repères, avis REER) | `Generateur-data-fictive/src/synthetic_finance/adapter.py` |
| Paramètres des distributions, commentés | `Generateur-data-fictive/configs/base.toml`, section `[adapter]` |
| Étape `adapter` de la CLI, contrôles ajoutés au validateur | `Generateur-data-fictive/src/synthetic_finance/cli.py`, `validation.py` |
| Chargeur : rejoue `sql/schema.sql`, `plafonds.sql`, `vues.sql`, vide puis charge par `COPY`, refuse toute base autre que `finance_ve01` | `scripts/charger_synthetique.py` |
| Recette SQL contre l'oracle (lit la base et les CSV du générateur, n'importe pas `adapter.py`) | `scripts/recette_synthetique.py` |
| Tests de l'adaptateur, multi-graines, reproductibilité | `Generateur-data-fictive/tests/test_adapter.py`, `test_adapter_seeds.py`, `test_reproducibility.py` |
| Rapport de l'adaptateur | `Generateur-data-fictive/outputs/typical_seed_20261103/adapter_report.md` |
| Export, graine 20261103 | `Generateur-data-fictive/outputs/typical_seed_20261103/finance_ve01/<schéma>.<table>.csv` |
| Contrat de données et README à jour | `Generateur-data-fictive/docs/contrat_donnees.md`, `README.md` |

Commandes du générateur depuis `Generateur-data-fictive/` avec `.venv/Scripts/python` ; scripts de la
racine avec le même interpréteur (psycopg 3 ajouté en dépendance optionnelle `finance`),
`PYTHONIOENCODING=utf-8`, `PGPASSFILE=$APPDATA/postgresql/pgpass.conf`. Preuves sous
`jalons/preuves/generateur-j6-adaptateur/`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Exécution, chargement, intégrité.** `generate --stage adapter` puis `validate` s'exécutent sans erreur ; le validateur affiche chaque contrôle un par un. Le chargeur vérifie `current_database() = 'finance_ve01'` avant toute écriture et s'arrête sans rien écrire sinon (test sur une base nommée autrement). Après chargement : nombre de lignes de chaque table = nombre de lignes de son CSV ; `fait.transaction` = ordres de `internal_trades` + une ligne par réinvestissement de distribution ; `fait.sommaire` = positions non nulles à l'arrêté ; aucune clé orpheline ; `fait.releve`, `fait.releve_cotisation`, `ref.*_hors_export`, `ref.transfert_*` vides ; chaque vue `rapport.*` répond à un `SELECT count(*)` sans erreur, nombre de lignes imprimé. | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage adapter`, `validate`, puis `python scripts/charger_synthetique.py --path Generateur-data-fictive/outputs/typical_seed_20261103` → `chargement.txt` ; `pytest -q tests/test_adapter.py -rA -k "refus or integrite"` → `pytest-integrite.txt` |
| C2 | **Distributions sans rendement fictif (bloquant).** Pour chaque fonds et chaque jour, le rendement total de la vue `rapport.rendement_fonds` (prix ex à 4 décimales + distribution par part de `rapport.distribution`) égale le rendement de `nav_total_return`, écart ≤ borne d'arrondi calculée (0,00005 sur chaque prix et sur la distribution par part, rapportés au prix de la veille). Calendrier conforme à `distribution_frequency` (mensuelle : dernier jour ouvrable du mois ; annuelle : un jour de décembre) ; aucune distribution négative ; VL ex > 0. Valeur conservée : parts ex × VL ex = parts en rendement total × VL totale, à la borne d'arrondi des parts près, chaque jour et chaque compte. Graine 20261103 et graines 1 à 20. | `python scripts/recette_synthetique.py --controle distributions` → `distributions.txt` ; `pytest -q tests/test_adapter.py tests/test_adapter_seeds.py -rA -k "distribution"` → `pytest-distributions.txt` |
| C3 | **Le rapport retrouve le grand livre (bloquant).** Sur la base chargée : pour chaque compte et chaque point de `rapport.valorisation`, VM = `total_value_cad` du même jour, écart ≤ Σ lignes (parts × 0,00005 + 0,005 $) ; VM totale de `rapport.arrete` = Σ `account_values_daily` à l'arrêté, même borne. Par compte × année, versements PAC et ponctuels, retraits et frais de `rapport.performance` = `external_movements`, au cent. Par régime × année, cotisations et droits restants de `rapport.droits` = `contribution_room`, au cent ; tout plafond de `rapport.droits_*` lu dans `ref.plafond` ; `rapport.alerte` n'affiche aucun « calendrier REER à compléter ». | `python scripts/recette_synthetique.py --controle grand-livre` → `grand-livre.txt` |
| C4 | **Oracle Dietz contre TWR, reproductibilité, non-régression.** Tableau compte × année, société × année et global × année : TWR Dietz de `rapport.rendement_annuel` (ou de `rapport.performance` chaîné par société), TWR quotidien de `performance_periods`, écart en points ; diagnostic imprimé, sans seuil, avec la plus grande valeur absolue et son entité. Deux exécutions de l'adaptateur à graine égale → CSV identiques (SHA-256). Les 22 CSV de `data/` présents au commit `d6972b9` identiques octet pour octet. `sql/`, `rapport/` et `generateur/` inchangés (`git diff --stat`). Balayage de fuite étendu à `finance_ve01/` : rien. | `python scripts/recette_synthetique.py --controle oracle` → `oracle.txt` ; `pytest -q tests/test_reproducibility.py -rA` → `repro.txt` ; `git diff --stat d6972b9 -- Generateur-data-fictive/outputs/typical_seed_20261103/data/ sql/ rapport/ generateur/` → `non-regression.txt` ; `python scripts/balayage_fuite.py` → `fuite.txt` |
| C5 | **Lecture par le responsable.** `adapter_report.md` donne : distributions par fonds et par année (taux, montants réinvestis, part des revenus, dividendes et gains en capital) ; le tableau de C4 avec, pour chaque écart de plus de 0,5 point, sa cause identifiée (flux en milieu de mois, frais, distributions, premier mois) ; les sorties des cinq requêtes de recette SQL de `HANDOFF.md` § 4 ; la VM par société à l'arrêté. Le responsable juge l'écart Dietz – TWR acceptable pour un rapport mensuel et les taux de distribution plausibles par catégorie de fonds. | `outputs/typical_seed_20261103/adapter_report.md`, lu par le responsable |

## Hypothèses à confirmer

- **H1 — Taux de distribution :** tirés par l'adaptateur sur un flux pseudoaléatoire propre (`adapter`),
  autour d'un rendement annuel par archétype dans `[adapter]` (ordre de grandeur : monétaire au taux
  court du J2 moins le RFG, obligations 2,5 à 3,5 %, équilibrés 2 %, actions du Canada et dividendes
  2,5 à 3,5 %, actions mondiales 1 à 1,5 %, croissance et technologie 0 à 0,5 %), avec un bruit
  log-normal par versement. Les gains en capital versés en décembre par les fonds annuels sont tirés
  à part, nuls les années où le fonds a baissé. Le J2 ne change pas : seul le partage entre prix et
  distribution est tiré.
- **H2 — Prix publiés :** `pub.cours.cloture` = VL ex à 4 décimales sous un symbole fictif par fonds
  (`SYN-<fund_id>`) ; repères dans `pub.cours.cloture_ajustee` = `index_total_return` ; `ref.repere` d'un
  fonds = son composite `R-<fund_id>`, poids 1. Pas de cours aux jours fériés (le J2 n'en a pas).
- **H3 — Horizon :** celui du générateur, du 2021-11-01 au 2026-10-30. Le rapport aura les années
  2021 à 2026 ; Société 1 et Société 2 n'ouvrent qu'en 2023-11 et 2024-01 (univers du J1, accepté). Le
  critère « toutes les années pour les trois sociétés » de `HANDOFF.md` § 2 est caduc.
- **H4 — Frais de compte :** un `FRAIS` du grand livre → une ligne « Frais de gestion » par fonds vendu,
  `montant_brut` = montant de l'ordre, `deductions` = 0. Ces dates de fin de mois servent de points de
  valorisation à `rapport.point`, comme dans la v1.
- **H5 — Avis REER :** `ref.reer_avis` reconstruit d'une année sur l'autre depuis `persona`
  (revenu gagné, cotisations inutilisées) et les plafonds en dollars de `ref.plafond` ;
  `ref.parametre.celi_premiere_annee` = première année CELI admissible de `persona`.
- **H6 — Base remplacée :** le chargeur vide et recharge `finance_ve01` ; le jeu de
  `generateur/generer.py` qui s'y trouve disparaît. Le rapport figé n'est pas touché tant que
  `figer.py` ne tourne pas (J7) ; `generer.py` reste rejouable pour revenir en arrière.

## Hors périmètre

`figer.py`, actualisation dans Desktop, recette DAX, contrôle visuel, segment Année, retrait de
`generateur/generer.py` (J7). Scénarios `stress` et `adversarial`, dictionnaire, parcours de
démonstration (J8). Toute modification de `sql/vues.sql`, `sql/schema.sql` ou du modèle : un écart qui
l'exigerait est signalé, pas corrigé. Les tables des J1 à J5 ne changent pas (C4).

## Modifications du contrat

Les trois premières, du 2026-11-03, écrites en cours de travail, le responsable absent : **validées par le responsable
le 2026-11-04**. Elles corrigent une
borne d'arrondi incomplète, écrite à l'ouverture ; aucune ne relâche un contrôle au-delà de l'arrondi qu'il
mesure, et l'ancienne borne reste imprimée en diagnostic.

- **C2, distribution par part (erreur du contrat).** « 0,00005 […] sur la distribution par part » est faux :
  `rapport.distribution` ne lit pas une distribution par part arrondie à 4 décimales, elle la reconstruit comme
  Σ montants réinvestis ÷ Σ parts de la veille, et chaque montant est arrondi au cent. Terme retenu : 0,005 $ ×
  nombre de comptes qui reçoivent un réinvestissement ÷ Σ de leurs parts de la veille. Un jour de versement où
  aucun montant n'atteint le cent (graine 3 : monétaire, un détenteur de 14 parts, 0,0002 $ par part), aucune
  ligne n'existe et le rapport ne voit que le prix : terme = 0,005 $ × détenteurs de la veille ÷ Σ de leurs parts,
  ce jour-là seulement (jours du journal `distributions.csv`, lui-même recoupé par les sauts de VL ex ÷ VL totale).
  Graine 20261103 : aucun cas ; 21 graines : 2 cas, tous sur la graine 3.
- **C2, jours contrôlés (précision).** « Pour chaque fonds et chaque jour » : contrôlé les jours où le fonds est
  détenu la veille par au moins un compte, seuls jours que lit `rapport.rendement_quotidien` (risque et
  performance comparée). Un jour sans détenteur, `rapport.distribution` n'a rien à reconstruire ; le nombre de
  ces jours est imprimé.
- **C3, valorisations (erreur du contrat).** La borne « Σ lignes (parts × 0,00005 + 0,005 $) » oublie l'arrondi
  des parts publiées au millième, que C2 admet (« à la borne d'arrondi des parts près ») : parts ex = round(U ÷ k,
  3), soit jusqu'à 0,0005 part × VL ex par ligne. Graine 20261103 : 10 points sur 236 dépassent l'ancienne borne
  (écart de 0,02 à 0,04 $, pire 1,55 fois la borne) ; avec 0,0005 part × VL + parts × 0,00005 + 0,005 $ par ligne,
  aucun (pire 0,90). Borne bloquante retenue : la seconde ; la première reste imprimée en diagnostic.
- **H1, part des gains en capital (2026-11-04, décision du responsable sur recommandation).** Remarque hors
  contrat du premier verdict : F303 (actions du Canada) versait 9,49 % en 2023, dont 6,44 points de gains en
  capital. `[adapter] capital_gain_share` passe de [0 ; 0,4] à [0 ; 0,25] ; aucun critère ne change. Le tirage
  garde le même nombre de valeurs sur le flux `adapter`, seules les parts versées en décembre baissent. F303 :
  3,05 % + 4,02 % en 2023, 3,78 % + 2,42 % en 2025. Toutes les preuves sont rejouées le 2026-11-04.

## Verdicts

### 2026-11-03, premier passage

```text
JALON    : Générateur synthétique, J6 : adaptateur vers `finance_ve01`
VERDICT  : REFUSÉ

CRITÈRES :
- [C1] PASS (attesté) — `jalons/preuves/generateur-j6-adaptateur/chargement.txt` : 33 contrôles du validateur PASS, 18 tables base = CSV (ligne 160 et suivantes), 6 tables vides, 13 contrôles d'orphelins à 0, 45 vues répondent (ligne 250). Le garde-fou `verifier_base` s'exécute avant tout `psql` (`scripts/charger_synthetique.py:65-100`). `pytest-integrite.txt:6` : base `postgres` refusée, code 2, 0 appel, base inchangée.
- [C2] FAIL — La borne et le périmètre ont été modifiés par l'exécutant (contrat, « Modifications du contrat ») et le responsable ne les a pas validés. Sous la borne modifiée, `distributions.txt:2-5` donne PASS (attesté) avec un pire écart ÷ borne de 0,998. Le contrat annonce que l'ancienne borne reste imprimée en diagnostic ; `distributions.txt` n'a aucune ligne `[DIAG]`. Jours contrôlés : 10 513 jours fonds détenus la veille, contre un « chaque jour » dans le contrat validé. Graines 1 à 20 : `pytest-distributions.txt:77-100` (24 passed).
- [C3] FAIL — Avec la borne du contrat validé, 10 points dépassent (`grand-livre.txt:3` : pire écart ÷ borne 1,553, 10 au-delà). Le PASS ne tient que sous la borne élargie par l'exécutant (`grand-livre.txt:2`, 0,900), non validée. Le reste est conforme : arrêté (:14), flux au cent (:15), droits au cent (:16), plafonds (:17), `rapport.alerte` en niveau « aucune » × 15.
- [C4] PASS (attesté) — `oracle.txt:46` : 43 couples, écart maximal 1,471 pt (Société 1, 2023) ; diagnostic sans seuil. `repro.txt:115-139` : adaptateur reproductible à graine égale, 22 CSV identiques à `d6972b9`. `non-regression.txt` : diff vide sur `data/`, `sql/`, `rapport/` et `generateur/`. `fuite.txt:16` : AUCUNE FUITE ; `Generateur-data-fictive/scripts/balayage_fuite.py:31` balaie `outputs` en récursif, donc `finance_ve01/`.
- [C5] À CONSTATER PAR LE RESPONSABLE — Le contenu demandé figure dans `Generateur-data-fictive/outputs/typical_seed_20261103/adapter_report.md` : distributions par fonds et par année (§1), tableau Dietz/TWR avec une cause pour chacun des 4 écarts > 0,5 pt (§2), cinq requêtes (§3), VM par société (§4).

HORS CONTRAT :
- `adapter_report.md:53` : la cause donnée pour CELI-1 2022 (flux de 2022-07, −0,67 pt) n'explique que la moitié de l'écart de −1,362 pt. Le reste est sans cause identifiée, alors que C5 exige une cause par écart > 0,5 pt.
- `adapter_report.md:25` : le taux de distribution de F303 est de 9,49 % en 2023 et de 7,65 % en 2025, très au-dessus de la fourchette de H1 (2,5 à 3,5 % pour les actions du Canada). Un fonds de ce type affichera un rendement de distribution irréaliste dans le rapport.

À VÉRIFIER PAR LE RESPONSABLE :
- Valider ou rejeter les trois modifications du contrat (bornes de C2 et de C3, jours contrôlés de C2). Ce sont elles qui font passer C2 et C3.
- Toutes les sorties (chargement, distributions, grand livre, oracle, tests) viennent de l'exécutant : je n'ai rien exécuté. Pour les recontrôler, relancer les commandes du contrat et comparer avec `jalons/preuves/generateur-j6-adaptateur/`.
- Juger l'écart Dietz – TWR (moyenne 0,18 pt) et les taux de distribution par catégorie de fonds (C5).
```

Suite donnée le 2026-11-03 (le responsable absent) : le diagnostic manquant de C2 (ancienne borne) est ajouté à
`distributions.txt`. Le rapport sépare désormais taux de revenu et gains en capital, et donne pour chaque écart
de plus de 0,5 point les mois qui en portent au moins 80 %. Preuves rejouées. **Pas de second évaluateur** :
les FAIL de C2 et C3 ne tiennent qu'à la validation des modifications, qui revient au responsable. Un second
passage avant sa décision rendrait le même verdict et consommerait un cycle.

Le 2026-11-04 : le responsable valide les trois modifications de C2 et C3 et constate C5 (écart Dietz – TWR et
taux de distribution jugés acceptables, sous réserve de la baisse des gains en capital, voir *Modifications
du contrat*). Preuves rejouées après cette baisse ; second passage de l'évaluateur.

### 2026-11-04, second passage

```text
JALON    : Générateur synthétique, J6 : adaptateur vers `finance_ve01`
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté) — `jalons/preuves/generateur-j6-adaptateur/chargement.txt` : 33 contrôles du validateur PASS (l.34-72), 18 tables base = CSV (l.161-178, dont `fait.transaction` 1884/1884, `fait.sommaire` 21/21), 6 tables vides (l.181-186), 13 contrôles d'orphelins à 0 (l.189-201), 45 vues avec leur nombre de lignes (l.204-250). `adaptateur_parts` (l.70) : 1884 = 1507 ordres + 377 réinvestissements. `pytest-integrite.txt:6` : base `postgres` refusée, code 2, 0 appel psql/COPY, base inchangée. `scripts/charger_synthetique.py:65-68` : `verifier_base` lit `current_database()` avant `psql` et `COPY`.
- [C2] PASS (attesté) — `distributions.txt:2` : 10 513 jours fonds, pire écart ÷ borne 0,992. `:3` : l'ancienne borne est imprimée en `[DIAG]` (20,9, 26 jours au-delà), manque du premier passage corrigé. `:4` calendrier, `:5` signe (0 distribution négative, VL ex min. 5,7546 $), `:6` valeur conservée (0,956). Graines 1 à 20 : `pytest-distributions.txt:77-101`, 24 passed. Bornes modifiées validées par le responsable (contrat l.83-86, l.142).
- [C3] PASS (attesté) — `grand-livre.txt:2` : 236 points, pire écart ÷ borne 0,900, 0 au-delà. `:3-13` : ancienne borne en `[DIAG]`. Arrêté `:14` (écart 0,09 $ pour une borne de 0,3477 $), flux `:15` et droits `:16` au cent, plafonds `:17` (32 sur 32), `rapport.alerte` : 15 lignes au niveau « aucune ».
- [C4] PASS (attesté) — `oracle.txt:2-45` : tableau compte, société et global × année, 43 couples. `:46` : plus grand écart 1,457 pt (Société 1, 2023), diagnostic sans seuil. `repro.txt:156-159` : 18 passed, reproductibilité à graine égale. `non-regression.txt` : diff vide sur `data/`, `sql/`, `rapport/`, `generateur/`. `fuite.txt:16` : AUCUNE FUITE (92 fichiers, `outputs` inclus).
- [C5] À CONSTATER PAR LE RESPONSABLE — le contenu demandé est dans `adapter_report.md` : §1 distributions par fonds et par année, avec revenu, gains en capital et réinvesti (l.13-26). §2 tableau Dietz/TWR (l.34-76), les 4 écarts > 0,5 pt ont chacun une cause portant au moins 80 % de l'écart (l.35, 40, 48, 53). §3 les cinq requêtes. §4 VM par société (l.214-217).
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE :
- Je n'ai rien exécuté. Toutes les sorties (chargement, distributions, grand livre, oracle, pytest, répro, fuite, non-régression) sont des preuves de l'exécutant, donc « attesté ». Pour recontrôler : rejouer les commandes du contrat et comparer avec `jalons/preuves/generateur-j6-adaptateur/`.
- `chargement.txt` n'apparaît pas modifié dans `git status`, alors que `pub.cours` et `distributions.csv` ont changé après la baisse de `capital_gain_share`. Le contenu reste cohérent (mêmes comptes de lignes). `pytest-integrite.txt:6` montre un chargement daté du 2026-11-04 12:34. Si tu veux le certain, relance le chargeur.
- C5 : ton accord du 2026-11-04 était sous réserve de la baisse des gains en capital. Relis la ligne F303 de `adapter_report.md:25` : 3,05 % + 4,02 % en 2023 et 3,78 % + 2,42 % en 2025.
```

`chargement.txt` rejoué le 2026-11-04 et identique octet pour octet à sa version du commit `e02fd49` : la sortie
ne liste que des noms de fichiers et des nombres de lignes, inchangés par la baisse. C5 constaté par le responsable le
2026-11-04 ; jalon accepté.
