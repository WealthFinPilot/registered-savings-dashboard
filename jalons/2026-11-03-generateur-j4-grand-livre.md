# Contrat de jalon — Générateur synthétique, J4 : grand livre

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-03
- **Contrat validé par le responsable :** oui, le 2026-11-03 (H4 : distributions au J6)
- **Statut :** accepté (C5 constaté par le responsable le 2026-11-03)

## Objectif

Construire le moteur D du cahier des charges (§ 2, § 6, § 10, jalon 4 du § 12) : le grand livre, seule
source de vérité des parts, de l'encaisse et des flux. Il traduit les mouvements du J3 en ordres par
fonds, tient les positions jour par jour, prélève les frais de compte (`FRAIS`), exécute les
rééquilibrages, valorise chaque compte et se réconcilie au cent près. Il ne lit que le passé : une
décision de rééquilibrage ne connaît que la clôture de la veille.

## Livrables

| Livrable | Chemin |
|---|---|
| Moteur du grand livre (ordres, parts, encaisse, frais, rééquilibrages, valorisations) | `Generateur-data-fictive/src/synthetic_finance/ledger.py` |
| Paramètres du grand livre et des rééquilibrages, commentés | `Generateur-data-fictive/configs/base.toml`, section `[ledger]` |
| Étape `ledger` de la CLI, contrôles ajoutés au validateur | `Generateur-data-fictive/src/synthetic_finance/cli.py`, `validation.py` |
| Tests comptables, frais, marché plat, anticipation, multi-graines, reproductibilité | `Generateur-data-fictive/tests/test_ledger.py`, `test_ledger_seeds.py`, `test_reproducibility.py` |
| Rapport du grand livre | `Generateur-data-fictive/outputs/typical_seed_20261103/ledger_report.md` |
| Export, graine 20261103 | `outputs/typical_seed_20261103/data/internal_trades.csv`, `positions_daily.csv`, `account_values_daily.csv` ; lignes `FRAIS` dans `external_movements.csv` ; événements `reequilibrage` dans `events.csv` |
| Contrat de données et README à jour | `Generateur-data-fictive/docs/contrat_donnees.md`, `README.md` |

Toutes les commandes se lancent depuis `Generateur-data-fictive/` avec `.venv/Scripts/python`.
Preuves sous `jalons/preuves/generateur-j4-grand-livre/`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Exécution, grain et intégrité.** `generate --stage ledger` puis `validate` s'exécutent sans erreur ; le validateur affiche chaque contrôle un par un. `internal_trades` : une ligne par ordre exécuté, `side` ∈ {`BUY`, `SELL`}, `units` à 3 décimales et > 0, `unit_price` = VL du fonds ce jour-là, `gross_amount_cad` à 2 décimales, `fee_cad` = 0 (aucun frais de transaction) ; chaque ordre renvoie soit à un `movement_id` (PAC, PONCTUEL, RETRAIT, FRAIS), soit à un `event_id` de type `reequilibrage`. Aucun ordre sur un fonds avant son lancement, hors des dates d'existence du compte, ni sur un fonds absent de la cible en vigueur du compte (sauf vente d'un fonds retiré de la cible). `positions_daily` : un enregistrement par compte × fonds détenu × jour ouvrable ; `account_values_daily` : un par compte ouvert × jour ouvrable. Aucune clé en double, aucune référence orpheline. | `python -m synthetic_finance generate --config configs/typical.toml --seed 20261103 --out outputs/typical_seed_20261103 --stage ledger` puis `python -m synthetic_finance validate --path outputs/typical_seed_20261103` → `generate-validate.txt` |
| C2 | **Comptabilité (bloquant), graine 20261103 et graines 1 à 20, recalculée par le test sans importer `ledger.py`.** Parts : `units_t = units_(t-1) + achats − ventes` sur chaque compte × fonds ; aucune part ni encaisse négative ; aucune vente au-delà des parts détenues. Encaisse : nulle en fin de journée, sauf le résidu d'arrondi des parts, borné à 0,0005 × VL par ordre et imprimé. Chaque apport du jour = somme des achats qu'il déclenche ; chaque `RETRAIT` et chaque `FRAIS` = somme des ventes qu'il déclenche ; un rééquilibrage a des ventes et des achats de même total (au résidu près) et ne crée aucun flux externe. Valorisation : `market_value_cad` = parts × VL arrondi au cent ; `total_value_cad` = Σ valeurs + encaisse. Identité patrimoniale, par compte et au total : valeur finale = Σ apports − Σ retraits − Σ frais + résultat de placement (Σ parts détenues × variation de VL), écart ≤ somme des résidus d'arrondi. Chaque mouvement externe se retrouve exactement une fois dans les ordres. Aucun `RETRAIT` infaisable (valeur du compte insuffisante) : 0 sur 21 exécutions ; un retrait infaisable fait échouer le moteur avec un message explicite. | `pytest -q tests/test_ledger.py tests/test_ledger_seeds.py -rA -k "compta"` → `pytest-compta.txt` |
| C3 | **Frais de compte et marché plat (bloquant).** `FRAIS` : prélèvement mensuel au dernier jour ouvrable du mois, par compte, = Σ des valeurs des fonds du compte ce jour × taux annuel du fonds ÷ 12, arrondi au cent ; taux bas (`account_fee_low_pct`) si l'actif agrégé du ménage chez la société dépasse `fee_tier_threshold_cad` (100 000 $, seuil par société, comme `rapport.seuil`), taux haut sinon. Les frais sont recalculés par le test et égaux au cent ; aucun frais au titre du RFG (déjà dans la VL). Deux scénarios de contrôle sur la graine 20261103 : VL constantes et taux de frais à 0 → valeur finale = Σ flux externes nets, au résidu d'arrondi près ; VL constantes avec frais → valeur finale = Σ flux externes nets − Σ `FRAIS`, et les `FRAIS` ne figurent dans aucun total d'apports ou de retraits. | `pytest -q tests/test_ledger.py -rA -k "frais or plat"` → `pytest-frais.txt` ; lecture de `ledger.py` |
| C4 | **Rééquilibrages imparfaits, aucune anticipation, reproductibilité, non-régression.** Un rééquilibrage ne naît que d'un changement de cible du J3 (`revue_annuelle`, `ajout_fonds`, `prudence_marche`, `retour_cible`) ou d'une dérive constatée à la clôture de la veille au-delà d'un seuil tiré ; chacun a son événement `reequilibrage` qui cite sa cause et la dérive mesurée. Sur la graine 20261103, au moins un rééquilibrage incomplet (dérive résiduelle > 0) et au moins une dérive au-delà du seuil laissée sans suite un temps (inertie) ; nombre de rééquilibrages par année imprimé pour les 21 graines. Anticipation : le test du J3 étendu au grand livre (21 graines, coupures tirées et jour / veille de chaque rééquilibrage, trois marchés de remplacement) laisse identiques ordres, positions, frais et événements datés au plus tard t, et une hausse dès la veille d'un rééquilibrage dû à la dérive le supprime. Deux exécutions à graine égale donnent des CSV identiques (SHA-256). Les CSV des étapes `universe` et `markets` sont identiques à ceux du commit `c45e250` ; ceux du J3 aussi, à deux exceptions près : `external_movements.csv` reçoit les lignes `FRAIS`, `events.csv` les événements `reequilibrage` (identifiants renumérotés dans l'ordre chronologique) ; le test compare le contenu J3 hors identifiants et le trouve identique. Balayage de fuite étendu : rien. | `pytest -q tests/test_ledger.py -rA -k "reequilibrage or anticipation" tests/test_reproducibility.py` → `repro.txt` ; `git diff --stat c45e250 -- Generateur-data-fictive/outputs/typical_seed_20261103/data/` → `non-regression.txt` ; `python scripts/balayage_fuite.py` → `fuite.txt` |
| C5 | **Lecture par le responsable.** `ledger_report.md` donne : un tableau année × société (apports, retraits, frais, résultat de placement, valeur au 31 décembre et à l'arrêté) ; le taux de frais annualisé par société et le palier appliqué ; la liste des rééquilibrages avec cause, dérive avant et après ; trois parcours vérifiables à la main, compte → mouvement → ordres → positions → valeur (un PAC, un retrait, un rééquilibrage). Le responsable juge que les montants et la chronologie sont plausibles pour l'épargnant du J3. | `outputs/typical_seed_20261103/ledger_report.md`, lu par le responsable |

## Hypothèses à confirmer

- **H1 — Encaisse nulle :** un apport est investi le jour même à la VL de clôture, ventilé selon la
  cible du compte en vigueur ce jour-là ; parts à 3 décimales (`fait.transaction.parts_negociees`
  est en `numeric(14, 3)`), d'où le résidu d'arrondi borné de C2. Pas de délai de règlement.
- **H2 — Frais de compte :** les taux `account_fee_low_pct` / `account_fee_high_pct` du J1 sont des
  taux annuels hors taxes ; aucune taxe de vente n'est modélisée (un taux de TPS/TVH serait un montant
  fiscal à sourcer, hors de `sql/plafonds.sql`). Prélevés par rachat de parts au prorata des fonds du
  compte.
- **H3 — Rééquilibrage :** un changement de cible déclenche un échange partiel (fraction tirée), le
  reste de l'écart étant résorbé par l'orientation des apports vers les fonds sous-pondérés ; la dérive
  n'est regardée qu'à intervalle tiré (inertie), jamais tous les jours. Un retrait vend au prorata des
  positions.
- **H4 — Distributions :** hors du J4. Les positions sont tenues en parts de la VL en rendement
  total ; la VL ex-distribution, les distributions par part et la conversion des parts (parts ex =
  parts × VL totale ÷ VL ex) passent à l'adaptateur du J6, qui en a seul l'usage. Le contrat de données
  sera corrigé en ce sens.
- **H5 — Patrimoine :** conséquence de H1 du J3, la valeur à l'arrêté tournera autour de 40 à 60 k$
  selon le marché ; le grand livre ne recalibre rien.

## Hors périmètre

TWR, MWR, `performance_daily`, contrefactuel passif (J5). Distributions et VL ex-distribution (H4,
J6). Scénarios `stress` et `adversarial`, adaptateur vers `finance_ve01` (J6). Frais de transaction,
taxes de vente, change, transferts interrégimes, fermeture de compte. Les événements, mouvements et
cibles du J3 ne changent pas, à part l'ajout des `FRAIS` et des `reequilibrage` (C4).

## Modifications du contrat

Toutes du 2026-11-03, en cours de travail ; aucune n'abaisse une exigence.

- **C3, sens des paliers (erreur du contrat).** Le contrat disait « taux bas (`account_fee_low_pct`) si
  l'actif dépasse le seuil ». C'est l'inverse : au J1 et dans le contrat de données, `account_fee_low_pct`
  est le taux *sous* le palier (`frais_moins`, le plus élevé) et `account_fee_high_pct` le taux au-delà
  (`frais_plus`). Le moteur et le test appliquent `account_fee_low_pct` sous 100 000 $ et
  `account_fee_high_pct` à partir de 100 000 $ (`>=`, comme `rapport.seuil`).
- **C2, borne du résidu.** 0,0005 × VL par ordre couvre l'arrondi des parts d'un ordre en montant. Une
  vente de toutes les parts d'un fonds (sortie de la cible, retrait qui épuise un fonds) part en parts et
  son montant est arrondi au cent : jusqu'à 0,005 $ de plus. Borne retenue : 0,0005 × VL + 0,005 $ par ordre.
- **C3, frais minuscules.** Un frais inférieur à un millième de la part la moins chère du compte ne peut pas
  être prélevé en parts : il n'est pas prélevé. Le test applique la même règle et compare au cent.
- **C4, anticipation.** Un apport du jour t s'exécute à la VL de clôture de t (H1) : ses parts et son prix
  dépendent forcément du marché de t, et le frais de fin de mois aussi. Le test compare donc au plus tard t
  les décisions (événements ; mouvements hors `FRAIS` ; fonds, sens et lien des ordres du jour t), et
  strictement avant t les ordres complets, les `FRAIS`, les positions et les valeurs.
- **C4, sensibilité.** Une hausse uniforme ne change pas les poids d'un compte, donc pas sa dérive. Le
  marché qui supprime un rééquilibrage dû à la dérive est une hausse (ou une baisse) propre à chaque fonds,
  dès la veille, qui ramène les poids du compte sur sa cible ; un rééquilibrage dont un fonds visé n'est pas
  détenu est écarté du contrôle (aucune VL ne peut le ramener) et compté.
- **Correction du J3, hors critère.** Le comportement pouvait verser un PAC de 0,01 $ quand les droits
  CELIAPP étaient presque épuisés : inexécutable en parts (graines 53 et 105 sur un balayage de 201). Un
  reliquat de droits sous `behaviour.min_pac` est désormais réorienté en entier. Les sorties du J3 sur
  les 21 graines de contrôle sont inchangées.
- **C4, commande de preuve.** Le `-k "reequilibrage or anticipation"` du contrat s'applique aussi à
  `tests/test_reproducibility.py` et en écarterait tous les tests. Commande exécutée :
  `pytest -q tests/test_ledger.py tests/test_reproducibility.py -rA -k "reequilibrage or anticipation or test_reproducibility"`.
- **C4, balayage de fuite.** Deux valeurs de compte synthétiques (`account_values_daily.csv`) avaient une
  partie entière égale à un motif de la liste privée : coïncidence numérique, pas une fuite. Le
  balayage écartait déjà un code précédé d'un point (partie décimale) ; il écarte désormais aussi un code
  suivi de « .chiffre » (partie entière d'un montant). Les autres motifs sont inchangés.

## Verdicts

### 2026-11-03

```text
JALON    : Générateur synthétique, J4 : grand livre
VERDICT  : ACCEPTÉ (C5 laissé au responsable, hors verdict)
CRITÈRES :
- [C1] PASS (attesté) — generate-validate.txt:26-55 : 4 contrôles du grand livre PASS (1507 ordres, 446 mouvements, 17189 positions, 5207 valeurs de compte), « Validation : réussie ». Le code du validateur contrôle bien ce que le contrat énonce (validation.py:557-659) : VL du jour, fee_cad = 0, lien unique, achats dans la cible, positions = cumul des ordres. Les décimales (dec3/dec2/dec6) sont imposées par le schéma d'export (export.py:66-72).
- [C2] PASS (attesté) — pytest-compta.txt:96 : 23 passed (graine 20261103 et graines 1 à 20, plus le retrait infaisable, refusé avec le message « 1000000.00 $ demandés, le CELI-1 vaut 12553.68 $ »). Le recalcul est indépendant : tests/criteres_grand_livre.py n'importe pas ledger.py (lignes 1 et 10, seul `export.lire_csv` est importé). Il rejoue les parts, vérifie le lien de chaque mouvement et l'identité patrimoniale (l.105-115). Écarts à l'arrêté de 0,01 $ à 0,67 $, sous le résidu cumulé. La borne par ordre (0,0005 × VL + 0,005 $) n'est pas affirmée dans le test : elle l'est dans le validateur (validation.py:574).
- [C3] PASS (attesté) — pytest-frais.txt:5-8 : 236 FRAIS recalculés = 236, 1857.77 $, aucun écart. Marché plat sans frais : écart +0,40 $ (borne 2,81 $). Marché plat avec frais : valeur = flux − FRAIS (écart +0,43 $) et PAC / PONCTUEL / RETRAIT inchangés. Lecture de ledger.py:244-262 : `>=` seuil → account_fee_high_pct, sinon account_fee_low_pct, arrondi au cent, aucun frais de RFG.
- [C4] PASS (attesté) — repro.txt:211 : 36 passed. Rééquilibrages imparfaits : 5 incomplets et une dérive de 30 jours ouvrables laissée sans suite (l.5). Rééquilibrages par année : 21 graines imprimées (l.8-28). Anticipation : 21 graines × 3 marchés, chaque dérive supprimée quand les VL de la veille ramènent les poids sur la cible (l.31-91). Reproductibilité : tests deux processus passés (l.198-210). Non-régression : non-regression.txt:1-8 (seuls events.csv et external_movements.csv changent dans data/ depuis c45e250) ; repro.txt:173 (14 CSV identiques, 39 événements et 210 mouvements du J3 identiques hors identifiants, 7 reequilibrage et 236 FRAIS ajoutés). Fuite : fuite.txt:15 « AUCUNE FUITE ». Les 7 événements de events.csv citent cause et dérive avant → après (events.csv:6,12,16...).
- [C5] À CONSTATER PAR LE RESPONSABLE — la preuve nomme « lu par le responsable » (ledger_report.md).
HORS CONTRAT : aucun
À VÉRIFIER PAR LE RESPONSABLE : (1) C5 : lire outputs/typical_seed_20261103/ledger_report.md, et juger si les montants et la chronologie sont plausibles. (2) Le palier haut des frais (account_fee_high_pct, au-delà de 100 000 $) n'est jamais exercé : sur la graine typique tous les ménages restent « sous le palier » (ledger_report.md:38,41,47) et le test des frais ne porte que sur cette graine. Le code est correct à la lecture (ledger.py:254), mais aucun test n'en prouve la branche. (3) Les sorties sont attestées, non rejouées : relancer `pytest -q tests/test_ledger.py tests/test_ledger_seeds.py -k compta` et `python -m synthetic_finance validate --path outputs/typical_seed_20261103` depuis Generateur-data-fictive/. (4) La correction du J3 (réorientation d'un reliquat de droits sous `behaviour.min_pac`), annoncée « inchangée sur les 21 graines », n'a pas de fichier de preuve propre : seule la graine 20261103 est couverte par le test de non-régression.
```

C5 constaté par le responsable le 2026-11-03 : rapport du grand livre lu, montants et chronologie jugés plausibles.
