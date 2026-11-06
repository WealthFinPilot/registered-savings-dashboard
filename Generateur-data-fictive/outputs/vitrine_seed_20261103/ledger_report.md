# Grand livre — vitrine_seed_20261103

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER

Graine 20261103, horizon 2021-11-01 → 2026-10-30. Chaque apport est investi le jour même à la VL de clôture (encaisse nulle) : un PAC suit la cible du compte, un ponctuel comble d'abord les fonds sous-pondérés à la veille, un retrait vend au prorata des valeurs de la veille. Les frais de compte (`FRAIS`) sont prélevés au dernier jour ouvrable du mois par rachat de parts ; le RFG est déjà dans la VL et n'est pas facturé une seconde fois. Parts à 3 décimales : le résidu d'arrondi reste dans la valeur.

## Flux et valeur par année et par société

Résultat de placement = valeur de fin − valeur de début − apports + retraits + frais (avant frais de compte, après RFG). Valeur au dernier jour ouvrable de l'année ; la dernière ligne de chaque société est l'arrêté.

| Société | Année | Apports | Retraits | Frais | Résultat de placement | Valeur de fin |
|---|---|---:|---:|---:|---:|---:|
| Société 1 | 2023 | 420 $ | 0 $ | 0 $ | 7 $ | 427 $ |
| Société 1 | 2024 | 9 150 $ | 0 $ | 53 $ | −424 $ | 9 099 $ |
| Société 1 | 2025 | 3 720 $ | 0 $ | 116 $ | −565 $ | 12 138 $ |
| Société 1 | 2026 (arrêté 2026-10-30) | 23 575 $ | 0 $ | 302 $ | 3 148 $ | 38 559 $ |
| Société 2 | 2024 | 4 337 $ | 0 $ | 19 $ | −118 $ | 4 199 $ |
| Société 2 | 2025 | 2 646 $ | 0 $ | 46 $ | 244 $ | 7 043 $ |
| Société 2 | 2026 (arrêté 2026-10-30) | 2 645 $ | 0 $ | 58 $ | −26 $ | 9 604 $ |
| Société 3 | 2021 | 1 580 $ | 0 $ | 3 $ | 16 $ | 1 593 $ |
| Société 3 | 2022 | 12 000 $ | 0 $ | 100 $ | 1 040 $ | 14 533 $ |
| Société 3 | 2023 | 12 653 $ | 1 400 $ | 290 $ | 4 814 $ | 30 310 $ |
| Société 3 | 2024 | 3 690 $ | 0 $ | 412 $ | −991 $ | 32 597 $ |
| Société 3 | 2025 | 2 490 $ | 0 $ | 421 $ | 427 $ | 35 093 $ |
| Société 3 | 2026 (arrêté 2026-10-30) | 27 240 $ | 0 $ | 633 $ | 5 147 $ | 66 847 $ |

Patrimoine à l'arrêté : 115 010 $ = apports 106 145 $ − retraits 1 400 $ − frais 2 454 $ + résultat de placement 12 719 $.

## Frais de compte

Taux annualisé = frais de l'année ÷ moyenne des valeurs de fin de mois × 12 ÷ nombre de mois. Palier : actif du ménage chez la société sous 100 000 $ (taux `account_fee_low_pct` des fonds) ou au-delà (`account_fee_high_pct`).

| Société | Année | Frais | Taux annualisé | Palier à l'arrêté |
|---|---|---:|---:|---|
| Société 1 | 2023 | 0,37 $ | 1,0 % |  |
| Société 1 | 2024 | 53,41 $ | 1,0 % |  |
| Société 1 | 2025 | 115,55 $ | 1,0 % |  |
| Société 1 | 2026 | 302,28 $ | 1,1 % | sous le palier |
| Société 2 | 2024 | 18,88 $ | 0,8 % |  |
| Société 2 | 2025 | 46,48 $ | 0,8 % |  |
| Société 2 | 2026 | 58,01 $ | 0,8 % | sous le palier |
| Société 3 | 2021 | 2,63 $ | 1,3 % |  |
| Société 3 | 2022 | 100,03 $ | 1,3 % |  |
| Société 3 | 2023 | 290,50 $ | 1,3 % |  |
| Société 3 | 2024 | 411,89 $ | 1,2 % |  |
| Société 3 | 2025 | 420,95 $ | 1,2 % |  |
| Société 3 | 2026 | 632,53 $ | 1,2 % | sous le palier |

## Rééquilibrages

Dérive = ½ Σ |poids − cible|, en points : la part de la valeur qu'il faudrait déplacer. « Veille » : ce que la décision a lu ; « clôture » : après l'échange, aux VL du jour.

| Événement | Date | Compte | Cause | Échange | Dérive à la veille | Dérive à la clôture |
|---|---|---|---|---:|---:|---:|
| E0005 | 2022-02-25 | REER-1 | revue annuelle | 174,91 $ | 5,14 | 0,08 |
| E0011 | 2022-12-12 | CELI-1 | revue annuelle | 164,48 $ | 4,52 | 1,79 |
| E0015 | 2023-06-26 | CELI-1 | ajout d'un fonds | 1 591,52 $ | 16,49 | 2,31 |
| E0018 | 2023-09-29 | REER-1 | ajout d'un fonds | 1 896,11 $ | 15,00 | 0,19 |
| E0033 | 2025-02-18 | CELIAPP-1 | revue annuelle | 498,67 $ | 20,59 | 4,28 |
| E0035 | 2025-03-25 | CELI-2 | revue annuelle | 441,96 $ | 11,40 | 4,60 |
| E0038 | 2025-07-18 | CELI-2 | dérive de 5.3 points, au-delà du seuil de 3.5 points | 240,10 $ | 5,30 | 1,76 |
| E0040 | 2025-09-30 | CELI-1 | dérive de 3.9 points, au-delà du seuil de 3.4 points | 454,51 $ | 3,92 | 1,26 |
| E0042 | 2025-12-04 | REER-1 | dérive de 5.6 points, au-delà du seuil de 5.0 points | 706,94 $ | 5,64 | 1,48 |
| E0049 | 2026-10-21 | CELIAPP-1 | revue annuelle | 462,46 $ | 10,12 | 4,78 |

## Parcours vérifiables à la main

Compte → mouvement → ordres → positions → valeur. Parts de clôture = parts de la veille ± ordres du jour (et frais si le jour est une fin de mois) ; valeur = parts × VL, arrondie au cent.

### Un PAC

M00001 du 2021-11-23, REER-1 chez Société 3 : PAC de 830,00 $, événement E0001 (ouverture du REER-1 chez Société 3). Autres mouvements du compte ce jour-là : aucun.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000001 | F302 | BUY | 9,860 | 29,463333 | 290,50 $ |
| T000002 | F303 | BUY | 63,172 | 8,540236 | 539,50 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F302 | 0,000 | 9,860 | 29,463333 | 290,51 $ |
| F303 | 0,000 | 63,172 | 8,540236 | 539,50 $ |

Valeur du REER-1 : 0,00 $ à la clôture du 2021-11-22, 830,01 $ à la clôture du 2021-11-23.

### Un retrait

M00081 du 2023-09-12, CELI-1 chez Société 3 : RETRAIT de −1 400,00 $, événement E0016 (dépense imprévue, retrait du CELI-1). Autres mouvements du compte ce jour-là : aucun.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000211 | F301 | SELL | 17,433 | 10,169724 | 177,29 $ |
| T000212 | F302 | SELL | 12,509 | 35,358840 | 442,31 $ |
| T000213 | F303 | SELL | 24,720 | 11,551059 | 285,54 $ |
| T000214 | F304 | SELL | 18,765 | 26,371302 | 494,86 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F301 | 161,525 | 144,092 | 10,169724 | 1 465,38 $ |
| F302 | 113,977 | 101,468 | 35,358840 | 3 587,79 $ |
| F303 | 226,934 | 202,214 | 11,551059 | 2 335,79 $ |
| F304 | 171,137 | 152,372 | 26,371302 | 4 018,25 $ |

Valeur du CELI-1 : 12 970,31 $ à la clôture du 2023-09-11, 11 407,21 $ à la clôture du 2023-09-12.

### Un rééquilibrage

E0011 du 2022-12-12 : rééquilibrage du CELI-1 vers sa nouvelle cible (revue annuelle) ; échange de 164.48 $ (56% de l'écart) ; dérive 4.5 → 2.0 points, à la clôture de la veille.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000106 | F302 | SELL | 5,137 | 32,019104 | 164,48 $ |
| T000107 | F303 | BUY | 11,501 | 10,771702 | 123,88 $ |
| T000108 | F304 | BUY | 1,597 | 25,425619 | 40,60 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F302 | 79,558 | 74,421 | 32,019104 | 2 382,89 $ |
| F303 | 160,601 | 172,102 | 10,771702 | 1 853,83 $ |
| F304 | 86,524 | 88,121 | 25,425619 | 2 240,53 $ |

Valeur du CELI-1 : 6 488,01 $ à la clôture du 2022-12-09, 6 477,25 $ à la clôture du 2022-12-12.

## Contrôles

| Contrôle | Statut | Détail |
|---|---|---|
| grand_livre_ordres | pass | 1548 ordres : BUY ou SELL, parts > 0, VL du jour, aucun frais de transaction, un lien chacun (mouvement ou rééquilibrage) ; résidu d'arrondi max 0.0264 $, total 9.01 $ |
| grand_livre_ordres_dates | pass | chaque ordre dans la vie de son compte, sur un fonds lancé ; chaque achat sur un fonds de la cible en vigueur |
| grand_livre_mouvements | pass | 449 mouvements, chacun exécuté une fois (apport = achats, retrait ou frais = ventes) ; 10 rééquilibrages à ventes = achats ; 236 FRAIS < 0 en fin de mois |
| grand_livre_positions | pass | 17103 positions : parts = cumul des ordres, jamais négatives, valeur = parts × VL au cent ; 5207 valeurs de compte = Σ positions, encaisse nulle |
