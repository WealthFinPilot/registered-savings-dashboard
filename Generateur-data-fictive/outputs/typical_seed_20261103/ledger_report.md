# Grand livre — typical_seed_20261103

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER

Graine 20261103, horizon 2021-11-01 → 2026-10-30. Chaque apport est investi le jour même à la VL de clôture (encaisse nulle) : un PAC suit la cible du compte, un ponctuel comble d'abord les fonds sous-pondérés à la veille, un retrait vend au prorata des valeurs de la veille. Les frais de compte (`FRAIS`) sont prélevés au dernier jour ouvrable du mois par rachat de parts ; le RFG est déjà dans la VL et n'est pas facturé une seconde fois. Parts à 3 décimales : le résidu d'arrondi reste dans la valeur.

## Flux et valeur par année et par société

Résultat de placement = valeur de fin − valeur de début − apports + retraits + frais (avant frais de compte, après RFG). Valeur au dernier jour ouvrable de l'année ; la dernière ligne de chaque société est l'arrêté.

| Société | Année | Apports | Retraits | Frais | Résultat de placement | Valeur de fin |
|---|---|---:|---:|---:|---:|---:|
| Société 1 | 2023 | 420 $ | 0 $ | 0 $ | 1 $ | 421 $ |
| Société 1 | 2024 | 9 150 $ | 0 $ | 52 $ | −227 $ | 9 292 $ |
| Société 1 | 2025 | 3 880 $ | 0 $ | 122 $ | 667 $ | 13 717 $ |
| Société 1 | 2026 (arrêté 2026-10-30) | 3 750 $ | 0 $ | 135 $ | 8 $ | 17 340 $ |
| Société 2 | 2024 | 4 337 $ | 0 $ | 19 $ | −24 $ | 4 294 $ |
| Société 2 | 2025 | 2 646 $ | 0 $ | 49 $ | 123 $ | 7 014 $ |
| Société 2 | 2026 (arrêté 2026-10-30) | 2 620 $ | 0 $ | 58 $ | 419 $ | 9 995 $ |
| Société 3 | 2021 | 1 580 $ | 0 $ | 3 $ | −3 $ | 1 574 $ |
| Société 3 | 2022 | 12 000 $ | 0 $ | 90 $ | 0 $ | 13 484 $ |
| Société 3 | 2023 | 12 653 $ | 1 400 $ | 265 $ | 2 146 $ | 26 618 $ |
| Société 3 | 2024 | 3 690 $ | 0 $ | 322 $ | −2 203 $ | 27 783 $ |
| Société 3 | 2025 | 2 490 $ | 0 $ | 390 $ | 3 333 $ | 33 216 $ |
| Société 3 | 2026 (arrêté 2026-10-30) | 2 170 $ | 0 $ | 353 $ | −1 408 $ | 33 625 $ |

Patrimoine à l'arrêté : 60 960 $ = apports 61 385 $ − retraits 1 400 $ − frais 1 858 $ + résultat de placement 2 833 $.

## Frais de compte

Taux annualisé = frais de l'année ÷ moyenne des valeurs de fin de mois × 12 ÷ nombre de mois. Palier : actif du ménage chez la société sous 100 000 $ (taux `account_fee_low_pct` des fonds) ou au-delà (`account_fee_high_pct`).

| Société | Année | Frais | Taux annualisé | Palier à l'arrêté |
|---|---|---:|---:|---|
| Société 1 | 2023 | 0,36 $ | 1,0 % |  |
| Société 1 | 2024 | 52,31 $ | 1,0 % |  |
| Société 1 | 2025 | 121,91 $ | 1,0 % |  |
| Société 1 | 2026 | 135,27 $ | 1,0 % | sous le palier |
| Société 2 | 2024 | 18,91 $ | 0,8 % |  |
| Société 2 | 2025 | 48,69 $ | 0,8 % |  |
| Société 2 | 2026 | 57,74 $ | 0,8 % | sous le palier |
| Société 3 | 2021 | 2,62 $ | 1,3 % |  |
| Société 3 | 2022 | 90,14 $ | 1,3 % |  |
| Société 3 | 2023 | 264,53 $ | 1,2 % |  |
| Société 3 | 2024 | 322,28 $ | 1,2 % |  |
| Société 3 | 2025 | 390,37 $ | 1,3 % |  |
| Société 3 | 2026 | 352,64 $ | 1,3 % | sous le palier |

## Rééquilibrages

Dérive = ½ Σ |poids − cible|, en points : la part de la valeur qu'il faudrait déplacer. « Veille » : ce que la décision a lu ; « clôture » : après l'échange, aux VL du jour.

| Événement | Date | Compte | Cause | Échange | Dérive à la veille | Dérive à la clôture |
|---|---|---|---|---:|---:|---:|
| E0005 | 2022-02-25 | REER-1 | revue annuelle | 158,90 $ | 4,94 | 0,33 |
| E0011 | 2022-12-12 | CELI-1 | revue annuelle | 272,31 $ | 7,16 | 2,55 |
| E0015 | 2023-06-01 | REER-1 | prudence après une baisse | 1 850,42 $ | 20,00 | 2,79 |
| E0017 | 2023-06-26 | CELI-1 | ajout d'un fonds | 1 634,52 $ | 15,99 | 0,12 |
| E0026 | 2024-07-01 | REER-1 | retour à la cible | 1 828,13 $ | 16,94 | 3,41 |
| E0039 | 2025-07-15 | CELI-1 | revue annuelle | 658,35 $ | 6,48 | 2,74 |
| E0045 | 2026-09-22 | COMP-1 | revue annuelle | 857,60 $ | 14,61 | 4,90 |

## Parcours vérifiables à la main

Compte → mouvement → ordres → positions → valeur. Parts de clôture = parts de la veille ± ordres du jour (et frais si le jour est une fin de mois) ; valeur = parts × VL, arrondie au cent.

### Un PAC

M00001 du 2021-11-23, REER-1 chez Société 3 : PAC de 830,00 $, événement E0001 (ouverture du REER-1 chez Société 3). Autres mouvements du compte ce jour-là : aucun.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000001 | F302 | BUY | 25,835 | 11,244424 | 290,50 $ |
| T000002 | F303 | BUY | 13,768 | 39,185368 | 539,50 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F302 | 0,000 | 25,835 | 11,244424 | 290,50 $ |
| F303 | 0,000 | 13,768 | 39,185368 | 539,50 $ |

Valeur du REER-1 : 0,00 $ à la clôture du 2021-11-22, 830,00 $ à la clôture du 2021-11-23.

### Un retrait

M00081 du 2023-09-12, CELI-1 chez Société 3 : RETRAIT de −1 400,00 $, événement E0018 (dépense imprévue, retrait du CELI-1). Autres mouvements du compte ce jour-là : aucun.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000220 | F301 | SELL | 19,259 | 9,992716 | 192,45 $ |
| T000221 | F302 | SELL | 41,472 | 10,504668 | 435,65 $ |
| T000222 | F303 | SELL | 7,117 | 39,641085 | 282,11 $ |
| T000223 | F304 | SELL | 66,676 | 7,345769 | 489,79 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F301 | 172,272 | 153,013 | 9,992716 | 1 529,02 $ |
| F302 | 373,095 | 331,623 | 10,504668 | 3 483,59 $ |
| F303 | 63,716 | 56,599 | 39,641085 | 2 243,65 $ |
| F304 | 597,242 | 530,566 | 7,345769 | 3 897,42 $ |

Valeur du CELI-1 : 12 522,59 $ à la clôture du 2023-09-11, 11 153,68 $ à la clôture du 2023-09-12.

### Un rééquilibrage

E0011 du 2022-12-12 : rééquilibrage du CELI-1 vers sa nouvelle cible (revue annuelle) ; échange de 272.31 $ (56% de l'écart) ; dérive 7.2 → 3.1 points, à la clôture de la veille.

| Ordre | Fonds | Sens | Parts | VL | Montant |
|---|---|---|---:|---:|---:|
| T000106 | F302 | SELL | 23,458 | 11,608194 | 272,31 $ |
| T000107 | F303 | BUY | 6,568 | 34,624123 | 227,40 $ |
| T000108 | F304 | BUY | 5,776 | 7,775078 | 44,91 $ |

| Fonds | Parts à la veille | Parts à la clôture | VL du jour | Valeur à la clôture |
|---|---:|---:|---:|---:|
| F302 | 245,545 | 222,087 | 11,608194 | 2 578,03 $ |
| F303 | 48,758 | 55,326 | 34,624123 | 1 915,61 $ |
| F304 | 299,266 | 305,042 | 7,775078 | 2 371,73 $ |

Valeur du CELI-1 : 6 779,07 $ à la clôture du 2022-12-09, 6 865,37 $ à la clôture du 2022-12-12.

## Contrôles

| Contrôle | Statut | Détail |
|---|---|---|
| grand_livre_ordres | pass | 1507 ordres : BUY ou SELL, parts > 0, VL du jour, aucun frais de transaction, un lien chacun (mouvement ou rééquilibrage) ; résidu d'arrondi max 0.0216 $, total 7.56 $ |
| grand_livre_ordres_dates | pass | chaque ordre dans la vie de son compte, sur un fonds lancé ; chaque achat sur un fonds de la cible en vigueur |
| grand_livre_mouvements | pass | 446 mouvements, chacun exécuté une fois (apport = achats, retrait ou frais = ventes) ; 7 rééquilibrages à ventes = achats ; 236 FRAIS < 0 en fin de mois |
| grand_livre_positions | pass | 17189 positions : parts = cumul des ordres, jamais négatives, valeur = parts × VL au cent ; 5207 valeurs de compte = Σ positions, encaisse nulle |
