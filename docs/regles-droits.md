# Règles de droits de cotisation appliquées

Une ligne par règle appliquée par `sql/vues.sql`, où chaque identifiant est cité en commentaire ; les
plafonds de `sql/plafonds.sql` renvoient à leur numéro de règle. Les montants sont des plafonds
publics. Pages consultées en octobre 2026, en anglais. Préfixe commun des URL :
`https://www.canada.ca/en/revenue-agency/services/tax/`.

L'outil signale, il ne conseille pas : ces règles servent à calculer un solde et une alerte, pas à
recommander une cotisation.

## Règles sourcées

| # | Régime | Règle | Effet dans les vues | Page (préfixe omis) |
|---|---|---|---|---|
| R1 | CELI | Plafond annuel : 5 000 $ de 2009 à 2012, 5 500 $ en 2013 et 2014, 10 000 $ en 2015, 5 500 $ de 2016 à 2018, 6 000 $ de 2019 à 2022, 6 500 $ en 2023, 7 000 $ de 2024 à 2026 | `ref.plafond`, rubrique `plafond_annuel` | `registered-plans-administrators/pspa/mp-rrsp-dpsp-tfsa-limits-ympe.html` ; 2026 : `individuals/topics/tax-free-savings-account/contributing/calculate-room.html` (« The TFSA dollar limit for 2026 is $7,000. ») |
| R2 | CELI | Les droits sont personnels et communs à tous les CELI de la personne | Droits calculés par régime, tous comptes CELI confondus, toutes sociétés confondues | `.../tax-free-savings-account/contributing/calculate-room.html` (« whether you have one TFSA or several ») |
| R3 | CELI | Droits au 1ᵉʳ janvier = droits inutilisés de l'année précédente + plafond de l'année + retraits de l'année précédente. Un retrait ne rend des droits que le 1ᵉʳ janvier suivant | Un retrait de l'année N entre dans les droits de N+1, jamais dans ceux de N | `.../tax-free-savings-account/contributing/calculate-room.html` ; `.../tax-free-savings-account/contributing/before.html` (« added back … the next calendar year on January 1 ») |
| R4 | CELI | Tout excédent est imposé à 1 % par mois sur l'excédent le plus élevé du mois, dès le premier dollar | Alerte dès 0,01 $ d'excédent, sans marge | `.../tax-free-savings-account/tax-payable-on-tfsas/examples-tax-payable-on-excess-tfsa-amount.html` (« from the first $1 ») |
| R5 | CELI | Les droits s'accumulent à partir de l'année des 18 ans, même sans compte ouvert | Année de départ du cumul des plafonds : paramètre `celi_premiere_annee` (voir H2) | `.../tax-free-savings-account/contributing/before.html` (« starts to accumulate when you turn 18 ») |
| R5a | CELI | Aucun droit ne s'accumule pour une année entière de non-résidence, même à 18 ans ou plus ; l'année où la personne est résidente une partie de l'année donne le plafond annuel complet, sans prorata. Le critère est la résidence aux fins de l'impôt, pas la citoyenneté | Le cumul des plafonds part de la première année de résidence fiscale à 18 ans ou plus | `individuals/topics/tax-free-savings-account/non-resident.html` (« not accumulate any new … contribution room for any year in which you are a non-resident ») ; `.../tax-free-savings-account/opening.html` |
| R6 | REER | Une cotisation versée jusqu'au 60ᵉ jour de l'année est déductible pour l'année précédente ; si ce jour tombe un samedi ou un dimanche, la période se termine le premier jour ouvrable suivant. Fins publiées : 3 mars 2025 (année 2024), 2 mars 2026 (année 2025). Année 2026 : 1ᵉʳ mars 2027, calculé par la règle (60ᵉ jour, un lundi), non encore publié à la consultation | `ref.periode_reer` ; droits REER suivis par année de déduction | `businesses/topics/completing-slips-summaries/financial-slips-summaries/rrsp-contribution-receipt-return/contribution-year.html` |
| R7 | REER | Un excédent de cotisations inutilisées sur le maximum déductible est toléré jusqu'à 2 000 $ (personne de 18 ans ou plus) ; au-delà, impôt de 1 % par mois | Avertissement sous 2 000 $, alerte au-delà | `individuals/topics/rrsps-related-plans/contributing-a-rrsp-prpp/what-happens-you-over-your-rrsp-prpp-deduction-limit.html` (« plus $2,000 ») |
| R8 | CELIAPP | Droits de participation de 8 000 $ l'année d'ouverture du premier CELIAPP ; aucun droit avant | Départ des droits CELIAPP à l'année d'ouverture (paramètre `celiapp_ouverture`) | `individuals/topics/first-home-savings-account/contributing-your-fhsa.html` (« in the year you open your first FHSA is $8,000 ») |
| R9 | CELIAPP | Les années suivantes, le report des droits inutilisés est plafonné à 8 000 $ | `report_max` borne le report d'une année à l'autre | même page (formule : « the lesser of: a) $8,000 plus your FHSA participation room carryforward … ») |
| R10 | CELIAPP | Plafond à vie de 40 000 $, diminué de toutes les cotisations et de tous les transferts depuis un REER | Les droits d'une année ne dépassent jamais 40 000 $ moins le cumul versé | même page (formule : « b) $40,000 minus all of your contributions to your FHSAs and transfers from your RRSPs ») |
| R11 | CELIAPP | Une cotisation des 60 premiers jours ne se déduit pas pour l'année précédente : les droits CELIAPP se suivent par année civile | Pas de calendrier des 60 jours pour le CELIAPP | `individuals/topics/first-home-savings-account/tax-deductions-fhsa-contributions.html` (« cannot be deducted ») |
| R12 | CELIAPP | Un excédent est imposé à 1 % par mois sur l'excédent le plus élevé du mois ; la page ne mentionne aucune marge | Alerte dès 0,01 $ d'excédent | `individuals/topics/first-home-savings-account/what-happens-contribute-transfer-too-much.html` |
| R13 | REER | L'état du maximum déductible de l'avis de cotisation donne le maximum déductible de l'année et la ligne « Unused RRSP contributions previously reported and available to deduct » ; son titre est « RRSP deduction limit and available contribution room statement » | `ref.reer_avis` : une ligne par année de déduction, une colonne par libellé de l'état | `individuals/topics/rrsps-related-plans/contributing-a-rrsp-prpp/what-unused-rrsp-prpp-contributions.html` ; guide T4040, `forms-publications/publications/t4040/rrsps-other-registered-plans-retirement.html` |
| R14 | CELI, REER, CELIAPP | Un transfert direct entre deux comptes du même régime n'est ni une cotisation ni un retrait : CELI « the funds you move will not affect your TFSA contribution room » et « not considered a withdrawal » ; REER (T2033) « do not claim a deduction », ni impôt retenu ni T4RSP ; CELIAPP « without reducing your FHSA participation room ». Un transfert indirect (retrait puis dépôt) reste un retrait suivi d'une cotisation. Non dit par les pages : effet d'un transfert REER direct sur les droits de déduction (lecture retenue : aucun) ; plafonds CELIAPP lors d'un transfert direct | Le retrait côté source et l'achat côté destination sont déclarés dans une saisie de transferts : ils sortent des retraits, des versements et des droits. Les autres cas restent comptés : compte non enregistré vers CELI = cotisation, CELI vers compte non enregistré = retrait (R3) | `individuals/topics/tax-free-savings-account/transfer.html` ; `individuals/topics/rrsps-related-plans/transferring/property-unmatured-rrsp.html` ; `businesses/topics/completing-slips-summaries/t4rsp-t4rif-information-returns/transfer-funds.html` ; `individuals/topics/first-home-savings-account/withdrawals-transfers-out-your-fhsas.html` |

## Hypothèses

Aucune page ne les tranche ; chacune a été arbitrée par le responsable du projet.

| # | Hypothèse | Point ouvert |
|---|---|---|
| H1 | Le montant qui consomme des droits est le montant brut de l'achat, avant la colonne « Déductions » | Brut, ou net déclaré par l'institution à l'ARC : le rapprochement avec les droits de l'ARC tranche |
| H2 | Année de départ du cumul des plafonds CELI : paramètre `celi_premiere_annee`, aligné sur Mon dossier ARC (2016 dans le jeu fictif) | L'ARC laisse au particulier la vérification de ses droits (`.../tax-free-savings-account/contributing/overcontribute.html`) ; en cas de doute sur la résidence fiscale d'une année (R5a), le paramètre se corrige sans toucher aux vues |
| H3 | Droits disponibles REER = maximum déductible − cotisations inutilisées | Formule non écrite littéralement sur les pages lues ; elle correspond à la présentation de l'état des droits REER de Mon dossier ARC (« Moins cotisations inutilisées versées à un REER », puis « Voici vos droits de cotisation REER ») |

## Conventions du rapport

Règles propres au rapport, sans source fiscale.

| # | Règle | Effet dans les vues et le modèle |
|---|---|---|
| R15 | Date d'arrêté = la plus ancienne des dates de fin des derniers relevés chargés (exports et relevés saisis à la main) ; un compte en retard retarde tout le rapport. Mois écoulé : mois civil antérieur ou égal au mois de la date d'arrêté. Année en cours : année civile de la date d'arrêté | `rapport.arrete` ; `rapport.calendrier.mois_ecoule` arrête les KPI « cotisé cumulé » au dernier mois écoulé ; `rapport.annee.periode` vaut « En cours » pour l'année de la date d'arrêté, sélection enregistrée du segment Année. Remplace `TODAY()` et une année figée dans le segment |
