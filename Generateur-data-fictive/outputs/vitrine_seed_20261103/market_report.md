# Marchés synthétiques — vitrine_seed_20261103

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER

Graine 20261103, horizon 2021-11-01 → 2026-10-30 (1305 jours ouvrables, lundi à vendredi, fériés non modélisés). VL en rendement total (distributions réinvesties), en CAD ; repères base 100.

Modèle : facteurs latents (actions par région, taux Canada et reste du monde, pente, crédit, change USD/CAD, styles, actifs réels), régimes tirés d'une chaîne de Markov, variance commune GARCH(1,1), chocs Student-t et sauts rares des deux signes. Aucune date ni aucun rendement annuel n'est imposé : la trajectoire ci-dessous est celle de la graine de marché 19, retenue parmi les graines 1 à 50 sur un critère de TWR global écrit d'avance (scénario vitrine, `scripts/choisir_graine_marche.py`) : marché favorable choisi, non tiré au hasard.

## Régimes

| Début | Fin | Régime | Jours ouvrables |
|---|---|---|---:|
| 2021-11-01 | 2022-12-26 | expansion | 301 |
| 2022-12-27 | 2023-08-24 | ralentissement | 173 |
| 2023-08-25 | 2023-12-07 | crise | 75 |
| 2023-12-08 | 2024-07-31 | reprise | 169 |
| 2024-08-01 | 2026-10-21 | expansion | 580 |
| 2026-10-22 | 2026-10-30 | ralentissement | 7 |

Temps passé : expansion 67,5 %, ralentissement 13,8 %, crise 5,7 %, reprise 13,0 %.

## Fonds

\* année incomplète (début de l'horizon, lancement du fonds ou fin de l'horizon). Écart au composite = rendement annualisé du fonds − celui de son repère composite passif, sur les mêmes jours : il cumule l'alpha tiré, le bruit propre et l'écart de frais (RFG − frais passifs). Écart à la catégorie = même calcul contre le repère de catégorie (repère du fonds dans le rapport) : il ajoute l'écart de composition (style, géographie, part d'actions).

| Fonds | Début | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Annualisé | Volatilité | Repli max | Écart au composite | Écart à la catégorie |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F101 Portefeuille prudence (Société 1) | 2021-11-01 | +0,7 % * | +7,0 % | +11,4 % | +0,3 % | +1,6 % | +2,9 % * | +4,5 % | 4,6 % | −6,5 % | −1,2 % | −2,1 % |
| F102 Portefeuille pondéré (Société 1) | 2021-11-01 | +2,1 % * | +12,9 % | +17,9 % | +4,1 % | −2,9 % | +5,5 % * | +7,4 % | 6,5 % | −10,1 % | −0,3 % | −0,8 % |
| F103 Portefeuille dynamique (Société 1) | 2021-11-01 | +3,6 % * | +13,7 % | +16,9 % | +0,6 % | −6,4 % | +9,6 % * | +7,0 % | 9,9 % | −19,4 % | −3,0 % | −3,6 % |
| F104 Actions du Canada (Société 1) | 2021-11-01 | +13,8 % * | +17,2 % | +25,3 % | −5,4 % | +4,8 % | +15,5 % * | +13,3 % | 11,3 % | −19,0 % | +3,4 % | +3,6 % |
| F105 Actions planétaires (Société 1) | 2022-02-09 | — | +8,4 % * | +17,2 % | +7,2 % | +6,4 % | +20,2 % * | +12,0 % | 10,8 % | −14,1 % | +0,4 % | +0,1 % |
| F106 Rendement de dividendes Canada (Société 1) | 2021-11-01 | +10,6 % * | +16,9 % | +27,3 % | +0,6 % | −9,7 % | +15,4 % * | +11,1 % | 11,8 % | −21,0 % | +0,8 % | +1,4 % |
| F201 Revenu fixe canadien (Société 2) | 2021-11-01 | −0,9 % * | +2,2 % | +7,7 % | +3,4 % | +2,9 % | +1,5 % * | +3,2 % | 4,1 % | −5,0 % | +0,0 % | −0,4 % |
| F202 Actifs réels et infrastructures (Société 2) | 2021-11-01 | +5,7 % * | +15,8 % | +6,2 % | −12,5 % | +3,1 % | −9,9 % * | +1,1 % | 10,1 % | −21,5 % | −0,5 % | +1,0 % |
| F203 Portefeuille prudence (Société 2) | 2021-11-01 | +1,4 % * | +8,7 % | +8,5 % | +2,2 % | +4,7 % | +6,6 % * | +6,2 % | 4,3 % | −5,7 % | +1,0 % | −0,4 % |
| F204 Portefeuille pondéré (Société 2) | 2021-11-01 | +3,4 % * | +9,4 % | +15,9 % | +1,3 % | +4,2 % | +5,4 % * | +7,6 % | 6,6 % | −8,9 % | −0,8 % | −0,7 % |
| F301 Marché monétaire (Société 3) | 2022-12-16 | — | +0,1 % * | +2,0 % | +1,5 % | +1,5 % | +1,4 % * | +1,6 % | 0,1 % | −0,0 % | −0,0 % | +0,0 % |
| F302 Actions des États-Unis (Société 3) | 2021-11-01 | +1,9 % * | +13,6 % | +24,1 % | +1,6 % | +14,7 % | +13,6 % * | +13,2 % | 12,4 % | −16,3 % | −0,5 % | −1,0 % |
| F303 Actions du Canada (Société 3) | 2021-11-01 | +7,6 % * | +21,3 % | +20,6 % | −4,0 % | −8,7 % | +13,0 % * | +8,9 % | 11,2 % | −24,8 % | −1,0 % | −0,8 % |
| F304 Petites sociétés nord-américaines (Société 3) | 2021-11-01 | +2,1 % * | +5,9 % | +20,6 % | −9,3 % | +0,1 % | +3,4 % * | +4,0 % | 11,8 % | −21,8 % | −8,3 % | −8,7 % |

## Repères

| Repère | Début | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Annualisé | Volatilité | Repli max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R-POL-I1 — Politique Société 1 (intermédiaire) | 2021-11-01 | +2,9 % * | +12,1 % | +17,2 % | +0,3 % | +3,2 % | +8,0 % * | +8,3 % | 6,7 % | −11,1 % |
| R-POL-I2 — Politique Société 2 (prudent) | 2021-11-01 | +3,4 % * | +11,1 % | +10,9 % | −2,3 % | +2,5 % | +3,2 % * | +5,5 % | 5,4 % | −8,6 % |
| R-POL-I3 — Politique Société 3 (dynamique) | 2021-11-01 | +3,6 % * | +15,4 % | +24,4 % | −0,6 % | +5,6 % | +14,2 % * | +11,8 % | 10,1 % | −15,6 % |
| R-ACT-MONDE — Repère actions mondiales | 2021-11-01 | +2,4 % * | +13,6 % | +22,8 % | +3,7 % | +7,4 % | +14,6 % * | +12,3 % | 10,7 % | −13,5 % |
| R-EQUILIBRE — Repère équilibré | 2021-11-01 | +1,4 % * | +9,7 % | +16,4 % | +2,0 % | +4,1 % | +7,3 % * | +7,8 % | 6,0 % | −7,9 % |
| R-CAT-ACT-AMN — Repère de catégorie — Actions nord-américaines, marché large | 2021-11-01 | +3,0 % * | +14,5 % | +25,0 % | +1,1 % | +7,1 % | +15,9 % * | +12,6 % | 10,4 % | −14,8 % |
| R-CAT-ACT-CAN — Repère de catégorie — Actions du Canada, marché large | 2021-11-01 | +5,8 % * | +17,6 % | +24,1 % | −6,1 % | +0,5 % | +10,8 % * | +9,7 % | 11,2 % | −19,5 % |
| R-CAT-ACT-MONDE — Repère de catégorie — Actions planétaires, marché large | 2021-11-01 | +2,4 % * | +13,6 % | +22,8 % | +3,7 % | +7,4 % | +14,6 % * | +12,3 % | 10,7 % | −13,5 % |
| R-CAT-ACT-US — Repère de catégorie — Actions des États-Unis, marché large | 2021-11-01 | +1,5 % * | +12,9 % | +25,4 % | +5,3 % | +10,9 % | +18,7 % * | +14,2 % | 11,4 % | −13,3 % |
| R-CAT-ACTIFS-REELS — Repère de catégorie — Actifs réels | 2021-11-01 | +8,5 % * | +15,8 % | +4,2 % | −18,5 % | −0,7 % | −5,2 % * | +0,1 % | 10,3 % | −29,0 % |
| R-CAT-CROISSANCE — Repère de catégorie — Profil croissance | 2021-11-01 | +2,9 % * | +13,5 % | +21,4 % | +1,0 % | +5,3 % | +12,0 % * | +10,7 % | 9,2 % | −13,0 % |
| R-CAT-EQUILIBRE — Repère de catégorie — Profil équilibré | 2021-11-01 | +1,6 % * | +10,3 % | +17,2 % | +1,8 % | +4,3 % | +7,9 % * | +8,2 % | 6,5 % | −8,7 % |
| R-CAT-MONETAIRE — Repère de catégorie — Marché monétaire | 2021-11-01 | +0,3 % * | +2,1 % | +1,9 % | +1,5 % | +1,7 % | +1,3 % * | +1,7 % | 0,0 % | +0,0 % |
| R-CAT-OBL-CAN — Repère de catégorie — Revenu fixe canadien, marché large | 2021-11-01 | −1,1 % * | +4,1 % | +9,7 % | +3,7 % | +2,3 % | +0,1 % * | +3,6 % | 4,8 % | −6,2 % |
| R-CAT-PRUDENT — Repère de catégorie — Profil prudent | 2021-11-01 | +0,7 % * | +8,1 % | +14,4 % | +2,4 % | +3,6 % | +5,3 % * | +6,6 % | 5,0 % | −6,3 % |
| R-F101 — Repère composite passif de F101 | 2021-11-01 | +1,6 % * | +7,8 % | +12,2 % | +1,5 % | +2,7 % | +4,1 % * | +5,7 % | 4,1 % | −5,9 % |
| R-F102 — Repère composite passif de F102 | 2021-11-01 | +1,8 % * | +10,3 % | +15,7 % | +1,7 % | +3,9 % | +7,2 % * | +7,7 % | 6,1 % | −8,6 % |
| R-F103 — Repère composite passif de F103 | 2021-11-01 | +2,5 % * | +14,3 % | +20,6 % | −0,2 % | +4,9 % | +11,0 % * | +10,0 % | 9,0 % | −13,1 % |
| R-F104 — Repère composite passif de F104 | 2021-11-01 | +5,8 % * | +17,0 % | +21,9 % | −3,5 % | +1,1 % | +10,9 % * | +10,0 % | 10,2 % | −18,4 % |
| R-F105 — Repère composite passif de F105 | 2021-11-01 | +2,1 % * | +12,5 % | +21,0 % | +4,3 % | +7,8 % | +13,8 % * | +11,8 % | 10,4 % | −13,2 % |
| R-F106 — Repère composite passif de F106 | 2021-11-01 | +6,4 % * | +20,2 % | +21,5 % | −3,7 % | +1,0 % | +9,7 % * | +10,3 % | 10,1 % | −19,1 % |
| R-F201 — Repère composite passif de F201 | 2021-11-01 | −0,7 % * | +3,4 % | +8,1 % | +3,4 % | +2,3 % | +0,2 % * | +3,2 % | 4,0 % | −4,9 % |
| R-F202 — Repère composite passif de F202 | 2021-11-01 | +7,7 % * | +15,4 % | +6,1 % | −15,3 % | +0,2 % | −2,9 % * | +1,6 % | 9,3 % | −23,2 % |
| R-F203 — Repère composite passif de F203 | 2021-11-01 | +1,8 % * | +7,0 % | +10,9 % | +1,2 % | +2,9 % | +3,2 % * | +5,2 % | 4,0 % | −6,0 % |
| R-F204 — Repère composite passif de F204 | 2021-11-01 | +3,0 % * | +12,7 % | +14,3 % | +2,5 % | +3,6 % | +7,8 % * | +8,4 % | 6,2 % | −8,7 % |
| R-F301 — Repère composite passif de F301 | 2021-11-01 | +0,3 % * | +2,1 % | +1,9 % | +1,5 % | +1,7 % | +1,4 % * | +1,7 % | 0,0 % | +0,0 % |
| R-F302 — Repère composite passif de F302 | 2021-11-01 | +1,3 % * | +13,8 % | +26,4 % | +2,9 % | +10,4 % | +17,5 % * | +13,7 % | 11,6 % | −15,2 % |
| R-F303 — Repère composite passif de F303 | 2021-11-01 | +5,8 % * | +17,1 % | +22,3 % | −3,9 % | +1,0 % | +10,9 % * | +9,9 % | 10,4 % | −18,6 % |
| R-F304 — Repère composite passif de F304 | 2021-11-01 | +2,9 % * | +14,5 % | +24,8 % | +0,3 % | +6,9 % | +15,2 % * | +12,2 % | 10,3 % | −14,9 % |

Frais passifs et composition :

- R-POL-I1 : 0,07 % par an — cibles du 2023-11-28 : F101 25 % | F102 35 % | F103 10 % | F104 15 % | F105 5 % | F106 10 %
- R-POL-I2 : 0,08 % par an — cibles du 2024-01-19 : F201 15 % | F202 25 % | F203 15 % | F204 45 %
- R-POL-I3 : 0,08 % par an — cibles du 2021-11-19 : F302 30 % | F303 40 % | F304 30 %
- R-ACT-MONDE : 0,08 % par an — equity 100 %
- R-EQUILIBRE : 0,07 % par an — equity 55 % | fixed_income 40 % | cash 5 %
- R-CAT-PRUDENT : 0,07 % par an — equity 40 % | fixed_income 55 % | cash 5 % ; archétypes conservateur
- R-CAT-EQUILIBRE : 0,07 % par an — equity 60 % | fixed_income 37 % | cash 3 % ; archétypes equilibre
- R-CAT-CROISSANCE : 0,08 % par an — equity 90 % | fixed_income 8 % | cash 2 % ; archétypes croissance
- R-CAT-ACT-CAN : 0,08 % par an — equity 100 % ; archétypes actions_canadiennes, dividendes_canadiens
- R-CAT-ACT-US : 0,08 % par an — equity 100 % ; archétypes actions_americaines
- R-CAT-ACT-AMN : 0,08 % par an — equity 100 % ; archétypes petites_cap_nord_americaines
- R-CAT-ACT-MONDE : 0,08 % par an — equity 100 % ; archétypes actions_mondiales, technologie_mondiale
- R-CAT-OBL-CAN : 0,06 % par an — fixed_income 100 % ; archétypes obligations_canadiennes
- R-CAT-MONETAIRE : 0,03 % par an — cash 100 % ; archétypes monetaire
- R-CAT-ACTIFS-REELS : 0,12 % par an — other 100 % ; archétypes actifs_reels
- Composites : frais passifs de 0,07 % (F101), 0,07 % (F102), 0,08 % (F103), 0,08 % (F104), 0,08 % (F105), 0,08 % (F106), 0,06 % (F201), 0,11 % (F202), 0,07 % (F203), 0,07 % (F204), 0,03 % (F301), 0,08 % (F302), 0,08 % (F303), 0,08 % (F304).

## Corrélations des rendements journaliers

Sur les jours communs aux deux séries. Fonds, puis politiques et repères de contexte.

| | F101 | F102 | F103 | F104 | F105 | F106 | F201 | F202 | F203 | F204 | F301 | F302 | F303 | F304 | R-POL-I1 | R-POL-I2 | R-POL-I3 | R-ACT-MONDE | R-EQUILIBRE | R-CAT-PRUDENT | R-CAT-EQUILIBRE | R-CAT-CROISSANCE | R-CAT-ACT-CAN | R-CAT-ACT-US | R-CAT-ACT-AMN | R-CAT-ACT-MONDE | R-CAT-OBL-CAN | R-CAT-MONETAIRE | R-CAT-ACTIFS-REELS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F101 | 1 | 0,79 | 0,74 | 0,65 | 0,74 | 0,63 | 0,42 | 0,55 | 0,82 | 0,76 | −0,00 | 0,69 | 0,65 | 0,69 | 0,85 | 0,84 | 0,79 | 0,77 | 0,87 | 0,87 | 0,87 | 0,81 | 0,68 | 0,75 | 0,79 | 0,77 | 0,42 | −0,03 | 0,55 |
| F102 | 0,79 | 1 | 0,79 | 0,66 | 0,82 | 0,62 | 0,30 | 0,57 | 0,80 | 0,79 | −0,00 | 0,76 | 0,68 | 0,74 | 0,88 | 0,85 | 0,85 | 0,85 | 0,90 | 0,87 | 0,90 | 0,88 | 0,71 | 0,82 | 0,86 | 0,85 | 0,30 | −0,05 | 0,57 |
| F103 | 0,74 | 0,79 | 1 | 0,69 | 0,86 | 0,65 | 0,10 | 0,59 | 0,72 | 0,78 | 0,00 | 0,81 | 0,70 | 0,79 | 0,88 | 0,82 | 0,89 | 0,89 | 0,87 | 0,79 | 0,88 | 0,91 | 0,76 | 0,86 | 0,90 | 0,89 | 0,09 | −0,07 | 0,58 |
| F104 | 0,65 | 0,66 | 0,69 | 1 | 0,63 | 0,78 | 0,05 | 0,51 | 0,63 | 0,73 | 0,01 | 0,59 | 0,84 | 0,67 | 0,83 | 0,73 | 0,82 | 0,65 | 0,72 | 0,64 | 0,73 | 0,76 | 0,89 | 0,62 | 0,78 | 0,65 | 0,04 | −0,04 | 0,49 |
| F105 | 0,74 | 0,82 | 0,86 | 0,63 | 1 | 0,58 | 0,07 | 0,58 | 0,73 | 0,75 | −0,01 | 0,87 | 0,63 | 0,80 | 0,87 | 0,80 | 0,89 | 0,96 | 0,89 | 0,80 | 0,90 | 0,94 | 0,67 | 0,94 | 0,92 | 0,96 | 0,07 | −0,08 | 0,57 |
| F106 | 0,63 | 0,62 | 0,65 | 0,78 | 0,58 | 1 | 0,06 | 0,48 | 0,60 | 0,68 | −0,05 | 0,55 | 0,78 | 0,63 | 0,78 | 0,69 | 0,77 | 0,60 | 0,67 | 0,60 | 0,68 | 0,71 | 0,83 | 0,58 | 0,72 | 0,60 | 0,05 | −0,05 | 0,47 |
| F201 | 0,42 | 0,30 | 0,10 | 0,05 | 0,07 | 0,06 | 1 | 0,06 | 0,49 | 0,26 | 0,05 | 0,05 | 0,03 | 0,05 | 0,22 | 0,33 | 0,06 | 0,07 | 0,38 | 0,57 | 0,33 | 0,11 | 0,04 | 0,06 | 0,06 | 0,07 | 0,97 | 0,02 | 0,06 |
| F202 | 0,55 | 0,57 | 0,59 | 0,51 | 0,58 | 0,48 | 0,06 | 1 | 0,60 | 0,55 | −0,02 | 0,54 | 0,52 | 0,56 | 0,64 | 0,78 | 0,63 | 0,61 | 0,60 | 0,55 | 0,61 | 0,63 | 0,55 | 0,59 | 0,63 | 0,61 | 0,06 | −0,02 | 0,91 |
| F203 | 0,82 | 0,80 | 0,72 | 0,63 | 0,73 | 0,60 | 0,49 | 0,60 | 1 | 0,77 | 0,03 | 0,67 | 0,64 | 0,67 | 0,85 | 0,87 | 0,77 | 0,76 | 0,88 | 0,89 | 0,87 | 0,80 | 0,67 | 0,73 | 0,77 | 0,76 | 0,48 | −0,03 | 0,62 |
| F204 | 0,76 | 0,79 | 0,78 | 0,73 | 0,75 | 0,68 | 0,26 | 0,55 | 0,77 | 1 | 0,02 | 0,72 | 0,75 | 0,75 | 0,89 | 0,87 | 0,86 | 0,78 | 0,87 | 0,83 | 0,87 | 0,85 | 0,81 | 0,76 | 0,84 | 0,78 | 0,27 | −0,05 | 0,53 |
| F301 | −0,00 | −0,00 | 0,00 | 0,01 | −0,01 | −0,05 | 0,05 | −0,02 | 0,03 | 0,02 | 1 | −0,03 | −0,03 | −0,00 | −0,01 | 0,01 | −0,01 | −0,02 | 0,00 | 0,02 | −0,00 | −0,01 | 0,00 | −0,02 | −0,02 | −0,02 | 0,06 | 0,21 | −0,01 |
| F302 | 0,69 | 0,76 | 0,81 | 0,59 | 0,87 | 0,55 | 0,05 | 0,54 | 0,67 | 0,72 | −0,03 | 1 | 0,60 | 0,78 | 0,81 | 0,75 | 0,86 | 0,90 | 0,83 | 0,74 | 0,84 | 0,88 | 0,64 | 0,92 | 0,89 | 0,90 | 0,05 | −0,06 | 0,54 |
| F303 | 0,65 | 0,68 | 0,70 | 0,84 | 0,63 | 0,78 | 0,03 | 0,52 | 0,64 | 0,75 | −0,03 | 0,60 | 1 | 0,69 | 0,85 | 0,75 | 0,85 | 0,66 | 0,73 | 0,65 | 0,74 | 0,78 | 0,92 | 0,63 | 0,80 | 0,66 | 0,02 | −0,05 | 0,50 |
| F304 | 0,69 | 0,74 | 0,79 | 0,67 | 0,80 | 0,63 | 0,05 | 0,56 | 0,67 | 0,75 | −0,00 | 0,78 | 0,69 | 1 | 0,84 | 0,77 | 0,87 | 0,83 | 0,81 | 0,72 | 0,82 | 0,86 | 0,74 | 0,83 | 0,87 | 0,83 | 0,05 | −0,07 | 0,55 |
| R-POL-I1 | 0,85 | 0,88 | 0,88 | 0,83 | 0,87 | 0,78 | 0,22 | 0,64 | 0,85 | 0,89 | −0,01 | 0,81 | 0,85 | 0,84 | 1 | 0,93 | 0,97 | 0,90 | 0,96 | 0,90 | 0,97 | 0,97 | 0,90 | 0,88 | 0,96 | 0,90 | 0,22 | −0,06 | 0,63 |
| R-POL-I2 | 0,84 | 0,85 | 0,82 | 0,73 | 0,80 | 0,69 | 0,33 | 0,78 | 0,87 | 0,87 | 0,01 | 0,75 | 0,75 | 0,77 | 0,93 | 1 | 0,88 | 0,83 | 0,92 | 0,89 | 0,92 | 0,89 | 0,80 | 0,80 | 0,87 | 0,83 | 0,34 | −0,03 | 0,81 |
| R-POL-I3 | 0,79 | 0,85 | 0,89 | 0,82 | 0,89 | 0,77 | 0,06 | 0,63 | 0,77 | 0,86 | −0,01 | 0,86 | 0,85 | 0,87 | 0,97 | 0,88 | 1 | 0,92 | 0,92 | 0,82 | 0,94 | 0,98 | 0,90 | 0,92 | 0,99 | 0,92 | 0,05 | −0,07 | 0,62 |
| R-ACT-MONDE | 0,77 | 0,85 | 0,89 | 0,65 | 0,96 | 0,60 | 0,07 | 0,61 | 0,76 | 0,78 | −0,02 | 0,90 | 0,66 | 0,83 | 0,90 | 0,83 | 0,92 | 1 | 0,93 | 0,83 | 0,94 | 0,98 | 0,69 | 0,98 | 0,96 | 1,00 | 0,07 | −0,07 | 0,60 |
| R-EQUILIBRE | 0,87 | 0,90 | 0,87 | 0,72 | 0,89 | 0,67 | 0,38 | 0,60 | 0,88 | 0,87 | 0,00 | 0,83 | 0,73 | 0,81 | 0,96 | 0,92 | 0,92 | 0,93 | 1 | 0,97 | 1,00 | 0,96 | 0,78 | 0,90 | 0,93 | 0,93 | 0,38 | −0,06 | 0,59 |
| R-CAT-PRUDENT | 0,87 | 0,87 | 0,79 | 0,64 | 0,80 | 0,60 | 0,57 | 0,55 | 0,89 | 0,83 | 0,02 | 0,74 | 0,65 | 0,72 | 0,90 | 0,89 | 0,82 | 0,83 | 0,97 | 1 | 0,96 | 0,87 | 0,69 | 0,80 | 0,83 | 0,83 | 0,59 | −0,04 | 0,53 |
| R-CAT-EQUILIBRE | 0,87 | 0,90 | 0,88 | 0,73 | 0,90 | 0,68 | 0,33 | 0,61 | 0,87 | 0,87 | −0,00 | 0,84 | 0,74 | 0,82 | 0,97 | 0,92 | 0,94 | 0,94 | 1,00 | 0,96 | 1 | 0,97 | 0,79 | 0,91 | 0,95 | 0,94 | 0,34 | −0,06 | 0,60 |
| R-CAT-CROISSANCE | 0,81 | 0,88 | 0,91 | 0,76 | 0,94 | 0,71 | 0,11 | 0,63 | 0,80 | 0,85 | −0,01 | 0,88 | 0,78 | 0,86 | 0,97 | 0,89 | 0,98 | 0,98 | 0,96 | 0,87 | 0,97 | 1 | 0,83 | 0,95 | 0,99 | 0,98 | 0,11 | −0,07 | 0,62 |
| R-CAT-ACT-CAN | 0,68 | 0,71 | 0,76 | 0,89 | 0,67 | 0,83 | 0,04 | 0,55 | 0,67 | 0,81 | 0,00 | 0,64 | 0,92 | 0,74 | 0,90 | 0,80 | 0,90 | 0,69 | 0,78 | 0,69 | 0,79 | 0,83 | 1 | 0,66 | 0,84 | 0,69 | 0,03 | −0,05 | 0,54 |
| R-CAT-ACT-US | 0,75 | 0,82 | 0,86 | 0,62 | 0,94 | 0,58 | 0,06 | 0,59 | 0,73 | 0,76 | −0,02 | 0,92 | 0,63 | 0,83 | 0,88 | 0,80 | 0,92 | 0,98 | 0,90 | 0,80 | 0,91 | 0,95 | 0,66 | 1 | 0,96 | 0,98 | 0,06 | −0,07 | 0,58 |
| R-CAT-ACT-AMN | 0,79 | 0,86 | 0,90 | 0,78 | 0,92 | 0,72 | 0,06 | 0,63 | 0,77 | 0,84 | −0,02 | 0,89 | 0,80 | 0,87 | 0,96 | 0,87 | 0,99 | 0,96 | 0,93 | 0,83 | 0,95 | 0,99 | 0,84 | 0,96 | 1 | 0,96 | 0,06 | −0,07 | 0,61 |
| R-CAT-ACT-MONDE | 0,77 | 0,85 | 0,89 | 0,65 | 0,96 | 0,60 | 0,07 | 0,61 | 0,76 | 0,78 | −0,02 | 0,90 | 0,66 | 0,83 | 0,90 | 0,83 | 0,92 | 1,00 | 0,93 | 0,83 | 0,94 | 0,98 | 0,69 | 0,98 | 0,96 | 1 | 0,07 | −0,07 | 0,60 |
| R-CAT-OBL-CAN | 0,42 | 0,30 | 0,09 | 0,04 | 0,07 | 0,05 | 0,97 | 0,06 | 0,48 | 0,27 | 0,06 | 0,05 | 0,02 | 0,05 | 0,22 | 0,34 | 0,05 | 0,07 | 0,38 | 0,59 | 0,34 | 0,11 | 0,03 | 0,06 | 0,06 | 0,07 | 1 | 0,03 | 0,05 |
| R-CAT-MONETAIRE | −0,03 | −0,05 | −0,07 | −0,04 | −0,08 | −0,05 | 0,02 | −0,02 | −0,03 | −0,05 | 0,21 | −0,06 | −0,05 | −0,07 | −0,06 | −0,03 | −0,07 | −0,07 | −0,06 | −0,04 | −0,06 | −0,07 | −0,05 | −0,07 | −0,07 | −0,07 | 0,03 | 1 | 0,00 |
| R-CAT-ACTIFS-REELS | 0,55 | 0,57 | 0,58 | 0,49 | 0,57 | 0,47 | 0,06 | 0,91 | 0,62 | 0,53 | −0,01 | 0,54 | 0,50 | 0,55 | 0,63 | 0,81 | 0,62 | 0,60 | 0,59 | 0,53 | 0,60 | 0,62 | 0,54 | 0,58 | 0,61 | 0,60 | 0,05 | 0,00 | 1 |

## Contrôles

| Contrôle | Statut | Détail |
|---|---|---|
| marche_calendrier | pass | 1305 jours ouvrables (lundi à vendredi) du 2021-11-01 au 2026-10-30, 4 régimes visités |
| marche_grain_vl | pass | 17904 VL : une par fonds et jour ouvrable, du lancement (ou du début de l'horizon) à la fin, aucune avant le lancement |
| marche_grain_reperes | pass | 37845 indices : une ligne par repère et jour ouvrable de l'horizon, 29 repères |
| marche_valeurs_positives | pass | VL et indices finis, strictement positifs, en CAD |
| marche_reperes | pass | 14 composites (frais passifs < RFG du fonds), 3 politiques (frais < RFG pondéré), 2 repères de contexte, 10 repères de catégorie (frais passifs < RFG de chaque fonds comparé), base 100 |

## Diagnostics

- Aucune anomalie détectée.
