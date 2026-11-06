# Comportement de l'épargnant — typical_seed_20261103

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER

Graine 20261103, horizon 2021-11-01 → 2026-10-30. Flux externes en CAD : `PAC` et `PONCTUEL` > 0, `RETRAIT` < 0 ; les frais de compte (`FRAIS`) viennent au J4 avec le grand livre.

Le moteur tire une capacité d'épargne latente qui ne change qu'à des décisions datées (phases, ouvertures, ajustements, revues) ; entre deux décisions, le PAC de chaque compte reste constant. Ponctuels, retraits, mois atypiques et pauses naissent de processus de Poisson ; chacun a son événement dans le journal. Le marché n'est lu que dans le passé (repli du repère actions mondiales arrêté la veille d'une décision).

## Personnage fictif

- Première année d'admissibilité au CELI : 2016 ; aucun CELI antérieur à l'horizon.
- Revenu gagné : 2020 75 400 $, 2021 75 200 $, 2022 81 200 $, 2023 96 000 $, 2024 98 400 $, 2025 101 000 $, 2026 102 300 $.
- Droits REER inutilisés à la fin de 2020 : 7 062 $.
- Plafonds : `sql/plafonds.sql` (SHA-256 `f684edbf9cb3…`), recopiés dans `tax_limits.csv`.

## Chronologie des événements

| Événement | Date | Type | Compte | Description | Effet |
|---|---|---|---|---|---|
| E0001 | 2021-11-19 | ouverture de compte | REER-1 | ouverture du REER-1 chez Société 3 | PAC total 0 → 830 $ |
| E0002 | 2021-12-03 | ajustement de PAC | REER-1 | ajustement du PAC du REER-1 | PAC 830 → 750 $ |
| E0003 | 2022-02-07 | phase d'épargne | — | reprise de l'épargne | capacité ×1.10 ; PAC total 750 → 970 $ |
| E0004 | 2022-02-25 | revue annuelle | REER-1 | revue du REER-1 | cible F302 35 %, F303 65 % → F302 40 %, F303 60 % |
| E0006 | 2022-03-01 | mois atypique | — | PAC suspendus ce mois-ci (dépense imprévue) | PAC total du mois 970 $ → 0 $ |
| E0007 | 2022-03-14 | ouverture de compte | CELI-1 | ouverture du CELI-1 chez Société 3 | PAC total 970 → 1000 $ |
| E0008 | 2022-10-24 | phase d'épargne | — | hausse de revenus | capacité ×1.22 ; PAC total 1000 → 1220 $ |
| E0009 | 2022-11-25 | ponctuel : cadeau | REER-1 | cadeau versé au REER-1 | +700.00 $ |
| E0010 | 2022-12-12 | revue annuelle | CELI-1 | revue du CELI-1 | cible F302 40 %, F303 25 %, F304 35 % → F302 35 %, F303 30 %, F304 35 % |
| E0012 | 2023-05-10 | ponctuel : remboursement d'impôt | REER-1 | remboursement d'impôt versé au REER-1 | +1652.55 $ |
| E0013 | 2023-05-15 | phase d'épargne | — | pression budgétaire | capacité ×0.71 ; PAC total 1220 → 810 $ |
| E0014 | 2023-06-01 | prudence après une baisse | REER-1 | repli de 17% du repère actions mondiales : le REER-1 passe à une cible plus prudente | cible F302 40 %, F303 60 % → F301 20 %, F302 35 %, F303 45 % ; actions 98% → 78% |
| E0016 | 2023-06-26 | ajout d'un fonds | CELI-1 | revue du CELI-1, ajout de F301 | cible F302 35 %, F303 30 %, F304 35 % → F301 15 %, F302 30 %, F303 20 %, F304 35 % ; PAC 520 → 430 $ |
| E0018 | 2023-09-12 | dépense imprévue | CELI-1 | dépense imprévue, retrait du CELI-1 | −1400.00 $ |
| E0019 | 2023-10-16 | phase d'épargne | — | nouveau projet (achat d'une première habitation) | capacité ×0.98 ; PAC total 720 → 825 $ |
| E0020 | 2023-11-28 | ouverture de compte | CELI-2 | ouverture du CELI-2 chez Société 1 | PAC total 825 → 880 $ |
| E0021 | 2023-12-07 | ouverture de compte | CELIAPP-1 | ouverture du CELIAPP-1 chez Société 1 | PAC total 880 → 840 $ |
| E0022 | 2024-01-01 | mois atypique | — | PAC suspendus ce mois-ci (dépense imprévue) | PAC total du mois 840 $ → 0 $ |
| E0023 | 2024-01-19 | ouverture de compte | COMP-1 | ouverture du COMP-1 chez Société 2 | PAC total 840 → 845 $ |
| E0024 | 2024-06-24 | ponctuel : remboursement d'impôt | COMP-1 | remboursement d'impôt versé au COMP-1 | +1636.62 $ |
| E0025 | 2024-07-01 | retour à la cible | REER-1 | le REER-1 revient à sa cible d'avant la baisse | cible F301 20 %, F302 35 %, F303 45 % → F302 40 %, F303 60 % |
| E0027 | 2024-07-04 | ponctuel : prime | CELI-2 | prime versée au CELI-2 | +5500.00 $ |
| E0028 | 2024-07-22 | revue annuelle | COMP-1 | revue du COMP-1 | PAC 250 → 300 $ |
| E0029 | 2024-11-29 | ponctuel : argent disponible | CELI-1 | argent disponible versé au CELI-1 | +1390.00 $ |
| E0030 | 2024-12-02 | mois atypique | — | PAC suspendus ce mois-ci (dépense imprévue) | PAC total du mois 895 $ → 0 $ |
| E0031 | 2024-12-09 | ajustement de PAC | CELI-2 | ajustement du PAC du CELI-2 | PAC 90 → 100 $ |
| E0032 | 2025-01-01 | pause de PAC | CELIAPP-1 | pause du PAC du CELIAPP-1 pendant 1 mois | −275 $ par mois jusqu'à la reprise |
| E0033 | 2025-01-28 | ouverture de compte | REER-2 | ouverture du REER-2 chez Société 2 | PAC total 905 → 800 $ ; compte sans PAC (ponctuels seulement) |
| E0034 | 2025-02-18 | revue annuelle | CELIAPP-1 | revue du CELIAPP-1 | PAC 300 → 325 $ |
| E0035 | 2025-03-11 | ajustement de PAC | CELI-2 | ajustement du PAC du CELI-2 | PAC 70 → 60 $ |
| E0036 | 2025-03-25 | revue annuelle | CELI-2 | revue du CELI-2 | PAC 60 → 50 $ |
| E0037 | 2025-05-07 | ponctuel : remboursement d'impôt | REER-2 | remboursement d'impôt versé au REER-2 | +295.58 $ |
| E0038 | 2025-07-15 | revue annuelle | CELI-1 | revue du CELI-1 | cible F301 15 %, F302 30 %, F303 20 %, F304 35 % → F301 15 %, F302 35 %, F303 20 %, F304 30 % ; PAC 150 → 140 $ |
| E0040 | 2025-09-11 | revue annuelle | COMP-1 | revue du COMP-1 | PAC 200 → 225 $ |
| E0041 | 2025-10-01 | mois atypique | — | PAC suspendus ce mois-ci (dépense imprévue) | PAC total du mois 820 $ → 0 $ |
| E0042 | 2026-04-09 | ponctuel : remboursement d'impôt | REER-2 | remboursement d'impôt versé au REER-2 | +394.86 $ |
| E0043 | 2026-08-24 | revue annuelle | REER-1 | revue du REER-1 | PAC 80 → 70 $ |
| E0044 | 2026-09-22 | revue annuelle | COMP-1 | revue du COMP-1 | cible F201 20 %, F202 30 %, F203 25 %, F204 25 % → F201 35 %, F202 25 %, F203 20 %, F204 20 % ; PAC 225 → 200 $ |
| E0046 | 2026-10-26 | revue annuelle | CELIAPP-1 | revue du CELIAPP-1 | PAC 325 → 375 $ |

## PAC total, mois par mois

Depuis la première ouverture (2021-11-19) : médiane 820 $ par mois ; 4 mois sans aucun PAC sur 60 (6,7 %). « 0 » = mois sans PAC.

| Année | janv. | févr. | mars | avr. | mai | juin | juil. | août | sept. | oct. | nov. | déc. | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 |  |  |  |  |  |  |  |  |  |  | 830 | 750 | 1 580 $ |
| 2022 | 750 | 970 | 0 | 1000 | 1000 | 1000 | 1000 | 1000 | 1000 | 1140 | 1220 | 1220 | 11 300 $ |
| 2023 | 1220 | 1220 | 1220 | 1220 | 1050 | 810 | 720 | 720 | 720 | 755 | 825 | 940 | 11 420 $ |
| 2024 | 0 | 845 | 845 | 845 | 845 | 845 | 845 | 895 | 895 | 895 | 895 | 0 | 8 650 $ |
| 2025 | 630 | 825 | 815 | 805 | 805 | 805 | 805 | 795 | 795 | 0 | 820 | 820 | 8 720 $ |
| 2026 | 820 | 820 | 820 | 820 | 820 | 820 | 820 | 810 | 810 | 785 |  |  | 8 145 $ |

## Flux par année, institution et régime

| Année | Institution | Régime | PAC | Ponctuels | Retraits |
|---|---|---|---:|---:|---:|
| 2021 | Société 3 | REER | 1 580 $ | 0 $ | 0 $ |
| 2022 | Société 3 | CELI | 6 280 $ | 0 $ | 0 $ |
| 2022 | Société 3 | REER | 5 020 $ | 700 $ | 0 $ |
| 2023 | Société 1 | CELI | 120 $ | 0 $ | 0 $ |
| 2023 | Société 1 | CELIAPP | 300 $ | 0 $ | 0 $ |
| 2023 | Société 3 | CELI | 6 940 $ | 0 $ | −1 400 $ |
| 2023 | Société 3 | REER | 4 060 $ | 1 653 $ | 0 $ |
| 2024 | Société 1 | CELI | 900 $ | 5 500 $ | 0 $ |
| 2024 | Société 1 | CELIAPP | 2 750 $ | 0 $ | 0 $ |
| 2024 | Société 2 | COMP | 2 700 $ | 1 637 $ | 0 $ |
| 2024 | Société 3 | CELI | 1 500 $ | 1 390 $ | 0 $ |
| 2024 | Société 3 | REER | 800 $ | 0 $ | 0 $ |
| 2025 | Société 1 | CELI | 630 $ | 0 $ | 0 $ |
| 2025 | Société 1 | CELIAPP | 3 250 $ | 0 $ | 0 $ |
| 2025 | Société 2 | COMP | 2 350 $ | 0 $ | 0 $ |
| 2025 | Société 2 | REER | 0 $ | 296 $ | 0 $ |
| 2025 | Société 3 | CELI | 1 610 $ | 0 $ | 0 $ |
| 2025 | Société 3 | REER | 880 $ | 0 $ | 0 $ |
| 2026 | Société 1 | CELI | 500 $ | 0 $ | 0 $ |
| 2026 | Société 1 | CELIAPP | 3 250 $ | 0 $ | 0 $ |
| 2026 | Société 2 | COMP | 2 225 $ | 0 $ | 0 $ |
| 2026 | Société 2 | REER | 0 $ | 395 $ | 0 $ |
| 2026 | Société 3 | CELI | 1 400 $ | 0 $ | 0 $ |
| 2026 | Société 3 | REER | 770 $ | 0 $ | 0 $ |

Sur l'horizon : PAC 49 815 $, ponctuels 11 570 $, retraits −1 400 $. Part des PAC par institution : Société 1 23,5 %, Société 2 14,6 %, Société 3 61,9 %.
Ponctuels : 7, de 296 $ à 5 500 $ ; multiples de 500 $ : 1 sur 7.

## Droits de cotisation

Année civile pour le CELI et le CELIAPP, année de déduction pour le REER (une cotisation de janvier ou février compte pour l'année précédente si sa période n'est pas close).

| Régime | Année | Nouveaux droits | Droits au début | Cotisations | Retraits | Droits restants |
|---|---:|---:|---:|---:|---:|---:|
| CELI | 2021 | 6 000 $ | 34 500 $ | 0 $ | 0 $ | 34 500 $ |
| CELI | 2022 | 6 000 $ | 40 500 $ | 6 280 $ | 0 $ | 34 220 $ |
| CELI | 2023 | 6 500 $ | 40 720 $ | 7 060 $ | 1 400 $ | 33 660 $ |
| CELI | 2024 | 7 000 $ | 42 060 $ | 9 290 $ | 0 $ | 32 770 $ |
| CELI | 2025 | 7 000 $ | 39 770 $ | 2 240 $ | 0 $ | 37 530 $ |
| CELI | 2026 | 7 000 $ | 44 530 $ | 1 900 $ | 0 $ | 42 630 $ |
| CELIAPP | 2023 | 8 000 $ | 8 000 $ | 300 $ | 0 $ | 7 700 $ |
| CELIAPP | 2024 | 8 000 $ | 15 700 $ | 2 750 $ | 0 $ | 12 950 $ |
| CELIAPP | 2025 | 8 000 $ | 16 000 $ | 3 250 $ | 0 $ | 12 750 $ |
| CELIAPP | 2026 | 8 000 $ | 16 000 $ | 3 250 $ | 0 $ | 12 750 $ |
| REER | 2021 | 13 572 $ | 20 634 $ | 3 300 $ | 0 $ | 17 334 $ |
| REER | 2022 | 13 536 $ | 30 870 $ | 4 920 $ | 0 $ | 25 950 $ |
| REER | 2023 | 14 616 $ | 40 566 $ | 4 873 $ | 0 $ | 35 693 $ |
| REER | 2024 | 17 280 $ | 52 973 $ | 880 $ | 0 $ | 52 093 $ |
| REER | 2025 | 17 712 $ | 69 805 $ | 1 176 $ | 0 $ | 68 630 $ |
| REER | 2026 | 18 180 $ | 86 810 $ | 1 005 $ | 0 $ | 85 805 $ |

## Changements de cible des comptes

| Date | Compte | Cible | Événement |
|---|---|---|---|
| 2021-11-19 | REER-1 | F302 35 %, F303 65 % | cible d'ouverture (J1) |
| 2022-02-25 | REER-1 | F302 40 %, F303 60 % | E0004 revue annuelle |
| 2022-03-14 | CELI-1 | F302 40 %, F303 25 %, F304 35 % | cible d'ouverture (J1) |
| 2022-12-12 | CELI-1 | F302 35 %, F303 30 %, F304 35 % | E0010 revue annuelle |
| 2023-06-01 | REER-1 | F301 20 %, F302 35 %, F303 45 % | E0014 prudence après une baisse |
| 2023-06-26 | CELI-1 | F301 15 %, F302 30 %, F303 20 %, F304 35 % | E0016 ajout d'un fonds |
| 2023-11-28 | CELI-2 | F101 45 %, F103 25 %, F105 15 %, F106 15 % | cible d'ouverture (J1) |
| 2023-12-07 | CELIAPP-1 | F101 50 %, F103 20 %, F106 30 % | cible d'ouverture (J1) |
| 2024-01-19 | COMP-1 | F201 20 %, F202 30 %, F203 25 %, F204 25 % | cible d'ouverture (J1) |
| 2024-07-01 | REER-1 | F302 40 %, F303 60 % | E0025 retour à la cible |
| 2025-01-28 | REER-2 | F201 15 %, F202 35 %, F204 50 % | cible d'ouverture (J1) |
| 2025-07-15 | CELI-1 | F301 15 %, F302 35 %, F303 20 %, F304 30 % | E0038 revue annuelle |
| 2026-09-22 | COMP-1 | F201 35 %, F202 25 %, F203 20 %, F204 20 % | E0044 revue annuelle |

## Contrôles

| Contrôle | Statut | Détail |
|---|---|---|
| comportement_types_et_signes | pass | 210 mouvements : 202 PAC, 7 ponctuels, 1 retraits ; apports > 0, retraits < 0, au cent (FRAIS : contrôles du grand livre) |
| comportement_comptes_et_dates | pass | chaque mouvement : compte connu, jour ouvrable, entre l'ouverture du compte et la fin de l'horizon |
| comportement_evenements | pass | 46 événements, clés uniques ; chaque mouvement et chacune des 7 nouvelles cibles de compte renvoient à un événement daté au plus tard le jour de l'effet |
| comportement_regimes | pass | aucun retrait de REER ni de CELIAPP ; aucun CELIAPP alimenté avant 2023-04-01 |
| comportement_droits | pass | 16 lignes régime × année : cotisations et retraits = mouvements, droits jamais dépassés, reports d'une année sur l'autre cohérents avec tax_limits |
| comportement_retraits_bornes | pass | 1 retraits, chacun ≤ 50% des apports nets du compte à sa date |

## Diagnostics

- Aucune anomalie détectée.
