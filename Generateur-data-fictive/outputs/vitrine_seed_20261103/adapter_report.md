# Rapport de l'adaptateur vers finance_ve01 (J6)

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER. Écrit par `scripts/recette_synthetique.py --controle rapport` depuis la base chargée et les exports.

Base `finance_ve01`, arrêté du 2026-10-30. Le rapport Power BI figé n'est pas touché tant que `scripts/figer.py` ne tourne pas (J7).

## 1. Distributions par fonds et par année

Taux = somme des taux versés dans l'année (fraction de la VL avant versement), revenu courant + gains en capital de décembre ; la plage de `[adapter.yield_pct]` ne porte que sur le revenu courant, les gains en capital sont une part tirée du gain de l'année au-delà de ce revenu. Réinvesti = montants des lignes « Distribution réinvestie » des comptes. Natures : dernier exercice publié (`pub.rapport_annuel`, exercice au 30 septembre), part de chaque nature.

| Fonds | Archétype | Fréquence | 2021 revenu + gains / réinvesti | 2022 revenu + gains / réinvesti | 2023 revenu + gains / réinvesti | 2024 revenu + gains / réinvesti | 2025 revenu + gains / réinvesti | 2026 revenu + gains / réinvesti | Revenus / dividendes / gains en capital |
|---|---|---|---|---|---|---|---|---|---|
| F101 | conservateur | monthly | 0.41% + 0.00% / 0.00 $ | 2.84% + 0.75% / 0.00 $ | 2.60% + 1.00% / 2.49 $ | 2.64% + 0.00% / 61.89 $ | 2.74% + 0.00% / 114.20 $ | 2.23% + 0.00% / 251.68 $ | 66% / 34% / 0% |
| F102 | equilibre | annual | 1.81% + 0.00% / 0.00 $ | 2.04% + 1.70% / 0.00 $ | 2.00% + 0.82% / 0.00 $ | 2.68% + 0.68% / 0.00 $ | 1.64% + 0.00% / 0.00 $ | — / 0.00 $ | 44% / 56% / 0% |
| F103 | croissance | annual | 2.16% + 0.08% / 0.00 $ | 1.30% + 0.45% / 0.00 $ | 2.36% + 0.39% / 2.53 $ | 1.19% + 0.00% / 24.33 $ | 2.05% + 0.00% / 56.44 $ | — / 0.00 $ | 14% / 86% / 0% |
| F104 | actions_canadiennes | annual | 2.59% + 0.88% / 0.00 $ | 2.18% + 1.50% / 0.00 $ | 2.63% + 3.39% / 0.00 $ | 2.95% + 0.00% / 0.00 $ | 2.43% + 0.05% / 0.00 $ | — / 0.00 $ | 3% / 94% / 3% |
| F105 | actions_mondiales | annual | — / 0.00 $ | 1.24% + 1.22% / 0.00 $ | 0.98% + 2.84% / 0.70 $ | 1.12% + 0.26% / 12.78 $ | 1.13% + 1.54% / 27.88 $ | — / 0.00 $ | 3% / 41% / 57% |
| F106 | dividendes_canadiens | monthly | 0.71% + 0.73% / 0.00 $ | 3.92% + 2.29% / 0.00 $ | 4.15% + 4.64% / 5.49 $ | 3.98% + 0.00% / 42.79 $ | 3.89% + 0.00% / 132.28 $ | 3.41% + 0.00% / 357.21 $ | 3% / 97% / 0% |
| F201 | obligations_canadiennes | monthly | 0.47% + 0.00% / 0.00 $ | 2.81% + 0.00% / 0.00 $ | 2.96% + 0.50% / 0.00 $ | 2.86% + 0.10% / 14.54 $ | 2.87% + 0.00% / 34.04 $ | 2.39% + 0.00% / 41.50 $ | 100% / 0% / 0% |
| F202 | actifs_reels | monthly | 0.54% + 0.46% / 0.00 $ | 3.77% + 1.18% / 0.00 $ | 3.71% + 0.28% / 0.00 $ | 3.78% + 0.00% / 26.27 $ | 4.27% + 0.00% / 70.63 $ | 3.33% + 0.00% / 82.68 $ | 86% / 14% / 0% |
| F203 | conservateur | monthly | 0.41% + 0.00% / 0.00 $ | 2.17% + 0.50% / 0.00 $ | 2.14% + 0.74% / 0.00 $ | 2.13% + 0.00% / 12.70 $ | 2.27% + 0.49% / 41.09 $ | 1.85% + 0.00% / 38.73 $ | 57% / 27% / 17% |
| F204 | equilibre | annual | 1.67% + 0.47% / 0.00 $ | 2.06% + 0.01% / 0.00 $ | 2.02% + 1.79% / 0.00 $ | 1.77% + 0.27% / 22.00 $ | 1.95% + 0.32% / 41.67 $ | — / 0.00 $ | 38% / 48% / 14% |
| F301 | monetaire | monthly | — / 0.00 $ | 0.12% + 0.00% / 0.00 $ | 2.02% + 0.00% / 21.66 $ | 1.48% + 0.00% / 57.60 $ | 1.50% + 0.00% / 74.73 $ | 1.36% + 0.00% / 122.27 $ | 100% / 0% / 0% |
| F302 | actions_americaines | annual | 1.25% + 0.03% / 6.96 $ | 1.10% + 0.81% / 101.89 $ | 1.46% + 4.68% / 567.99 $ | 0.97% + 0.04% / 102.89 $ | 1.28% + 2.37% / 408.45 $ | — / 0.00 $ | 1% / 34% / 65% |
| F303 | actions_canadiennes | annual | 3.06% + 1.07% / 43.50 $ | 2.82% + 2.30% / 347.48 $ | 3.05% + 3.29% / 740.87 $ | 3.90% + 0.00% / 491.16 $ | 3.78% + 0.00% / 464.25 $ | — / 0.00 $ | 3% / 97% / 0% |
| F304 | petites_cap_nord_americaines | annual | 1.03% + 0.24% / 0.00 $ | 0.84% + 1.08% / 42.83 $ | 0.95% + 3.73% / 236.41 $ | 1.06% + 0.00% / 60.74 $ | 0.99% + 0.00% / 62.86 $ | — / 0.00 $ | 4% / 96% / 0% |

## 2. TWR Dietz du rapport contre TWR quotidien du J5

Dietz : `rapport.rendement_annuel` (compte, global), Dietz mensuel de la société chaîné (Σ numérateurs ÷ Σ dénominateurs de `rapport.performance`). TWR : `performance_periods`. Cause donnée pour tout écart de plus de 0,5 point : les mois de même signe qui en portent au moins 80 %, chaque mois comparé au TWR quotidien chaîné sur le même mois, avec son motif.

| Niveau | Entité | Année | Dietz | TWR | Écart (pt) | Cause (écart > 0,5 pt) |
|---|---|---|---|---|---|---|
| global | Global | 2021 | 0.51% | 1.75% | -1.235 | 2021-12 -0.93 pt, flux de 92% de la valeur de début : pondération de Dietz ; 2021-11 -0.32 pt, premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés (Σ -1.25 pt sur -1.24) |
| global | Global | 2022 | 14.27% | 14.06% | +0.214 |  |
| global | Global | 2023 | 17.92% | 17.72% | +0.204 |  |
| global | Global | 2024 | -1.65% | -1.57% | -0.079 |  |
| global | Global | 2025 | -0.53% | -0.51% | -0.028 |  |
| global | Global | 2026 | 7.45% | 7.57% | -0.125 |  |
| société | Société 1 | 2023 | 1.96% | 2.59% | -0.636 | 2023-12 -0.64 pt, premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés (Σ -0.64 pt sur -0.64) |
| société | Société 1 | 2024 | -0.85% | -0.13% | -0.723 | 2024-02 -1.01 pt, flux de 85% de la valeur de début : pondération de Dietz (Σ -1.01 pt sur -0.72) |
| société | Société 1 | 2025 | -5.28% | -5.16% | -0.114 |  |
| société | Société 1 | 2026 | 9.17% | 9.17% | +0.007 |  |
| société | Société 2 | 2024 | -2.31% | -2.58% | +0.264 |  |
| société | Société 2 | 2025 | 3.08% | 2.99% | +0.084 |  |
| société | Société 2 | 2026 | -0.41% | -0.32% | -0.084 |  |
| société | Société 3 | 2021 | 0.51% | 1.75% | -1.235 | 2021-12 -0.93 pt, flux de 92% de la valeur de début : pondération de Dietz ; 2021-11 -0.32 pt, premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés (Σ -1.25 pt sur -1.24) |
| société | Société 3 | 2022 | 14.27% | 14.06% | +0.214 |  |
| société | Société 3 | 2023 | 17.92% | 17.73% | +0.190 |  |
| société | Société 3 | 2024 | -3.54% | -3.54% | -0.001 |  |
| société | Société 3 | 2025 | 0.22% | 0.23% | -0.018 |  |
| société | Société 3 | 2026 | 7.60% | 7.79% | -0.184 |  |
| compte | CELI-1 | 2022 | 6.63% | 5.83% | +0.796 | 2022-05 +0.64 pt, flux de 103% de la valeur de début : pondération de Dietz (Σ +0.64 pt sur +0.80) |
| compte | CELI-1 | 2023 | 18.70% | 18.46% | +0.237 |  |
| compte | CELI-1 | 2024 | -4.45% | -4.44% | -0.006 |  |
| compte | CELI-1 | 2025 | 1.65% | 1.67% | -0.019 |  |
| compte | CELI-1 | 2026 | 6.66% | 7.07% | -0.408 |  |
| compte | CELI-2 | 2023 | 2.85% | 2.68% | +0.173 |  |
| compte | CELI-2 | 2024 | 0.06% | 0.57% | -0.511 | 2024-02 -1.06 pt, flux de 72% de la valeur de début : pondération de Dietz (Σ -1.06 pt sur -0.51) |
| compte | CELI-2 | 2025 | -3.84% | -3.83% | -0.005 |  |
| compte | CELI-2 | 2026 | 9.20% | 9.25% | -0.050 |  |
| compte | CELIAPP-1 | 2023 | 1.54% | 1.22% | +0.318 |  |
| compte | CELIAPP-1 | 2024 | -1.33% | -0.46% | -0.866 | 2024-02 -0.97 pt, flux de 90% de la valeur de début : pondération de Dietz (Σ -0.97 pt sur -0.87) |
| compte | CELIAPP-1 | 2025 | -7.07% | -6.85% | -0.222 |  |
| compte | CELIAPP-1 | 2026 | 9.04% | 9.00% | +0.033 |  |
| compte | COMP-1 | 2024 | -2.31% | -2.58% | +0.264 |  |
| compte | COMP-1 | 2025 | 3.02% | 2.96% | +0.060 |  |
| compte | COMP-1 | 2026 | -0.34% | -0.25% | -0.087 |  |
| compte | REER-1 | 2021 | 0.51% | 1.75% | -1.235 | 2021-12 -0.93 pt, flux de 92% de la valeur de début : pondération de Dietz ; 2021-11 -0.32 pt, premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés (Σ -1.25 pt sur -1.24) |
| compte | REER-1 | 2022 | 16.48% | 16.53% | -0.045 |  |
| compte | REER-1 | 2023 | 17.36% | 17.16% | +0.199 |  |
| compte | REER-1 | 2024 | -2.72% | -2.73% | +0.005 |  |
| compte | REER-1 | 2025 | -1.27% | -1.25% | -0.022 |  |
| compte | REER-1 | 2026 | 10.36% | 10.38% | -0.019 |  |
| compte | REER-2 | 2025 | 4.65% | 4.55% | +0.092 |  |
| compte | REER-2 | 2026 | -1.52% | -1.45% | -0.070 |  |

## 3. Requêtes de recette SQL

```sql
SELECT * FROM rapport.arrete;
```

| date_arrete |
|---|
| 2026-10-30 |

```sql
SELECT regime, annee, droits_debut, cotisations, droits_restants, niveau FROM rapport.alerte ORDER BY 1, 2;
```

| regime | annee | droits_debut | cotisations | droits_restants | niveau |
|---|---|---|---|---|---|
| CELI | 2022 | 40500.00 | 6280.00 | 34220.00 | aucune |
| CELI | 2023 | 40720.00 | 7060.00 | 33660.00 | aucune |
| CELI | 2024 | 42060.00 | 9290.00 | 32770.00 | aucune |
| CELI | 2025 | 39770.00 | 2330.00 | 37440.00 | aucune |
| CELI | 2026 | 44440.00 | 47000.00 | -2560.00 | alerte |
| CELIAPP | 2023 | 8000.00 | 300.00 | 7700.00 | aucune |
| CELIAPP | 2024 | 15700.00 | 2750.00 | 12950.00 | aucune |
| CELIAPP | 2025 | 16000.00 | 3000.00 | 13000.00 | aucune |
| CELIAPP | 2026 | 16000.00 | 2975.00 | 13025.00 | aucune |
| REER | 2021 | 20633.94 | 3300.00 | 17333.94 | aucune |
| REER | 2022 | 30869.94 | 4920.00 | 25949.94 | aucune |
| REER | 2023 | 40565.94 | 4872.55 | 35693.39 | aucune |
| REER | 2024 | 52973.39 | 880.00 | 52093.39 | aucune |
| REER | 2025 | 69805.39 | 1175.58 | 68629.81 | aucune |
| REER | 2026 | 86809.81 | 1074.86 | 85734.95 | aucune |

```sql
SELECT c.societe, round(sum(p.vm_fin)) FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias WHERE (p.compte_alias, p.date_fin) IN (SELECT compte_alias, max(date_fin) FROM rapport.performance GROUP BY 1) GROUP BY 1 ORDER BY 1;
```

| societe | round |
|---|---|
| Société 1 | 38559 |
| Société 2 | 9604 |
| Société 3 | 66847 |

```sql
SELECT coalesce(compte_alias, 'GLOBAL'), annee, round(twr * 100, 2) FROM rapport.rendement_annuel ORDER BY 1, 2;
```

| coalesce | annee | round |
|---|---|---|
| CELI-1 | 2022 | 6.63 |
| CELI-1 | 2023 | 18.70 |
| CELI-1 | 2024 | -4.45 |
| CELI-1 | 2025 | 1.65 |
| CELI-1 | 2026 | 6.66 |
| CELI-2 | 2023 | 2.85 |
| CELI-2 | 2024 | 0.06 |
| CELI-2 | 2025 | -3.84 |
| CELI-2 | 2026 | 9.20 |
| CELIAPP-1 | 2023 | 1.54 |
| CELIAPP-1 | 2024 | -1.33 |
| CELIAPP-1 | 2025 | -7.07 |
| CELIAPP-1 | 2026 | 9.04 |
| COMP-1 | 2024 | -2.31 |
| COMP-1 | 2025 | 3.02 |
| COMP-1 | 2026 | -0.34 |
| GLOBAL | 2021 | 0.51 |
| GLOBAL | 2022 | 14.27 |
| GLOBAL | 2023 | 17.92 |
| GLOBAL | 2024 | -1.65 |
| GLOBAL | 2025 | -0.53 |
| GLOBAL | 2026 | 7.45 |
| REER-1 | 2021 | 0.51 |
| REER-1 | 2022 | 16.48 |
| REER-1 | 2023 | 17.36 |
| REER-1 | 2024 | -2.72 |
| REER-1 | 2025 | -1.27 |
| REER-1 | 2026 | 10.36 |
| REER-2 | 2025 | 4.65 |
| REER-2 | 2026 | -1.52 |

```sql
SELECT niveau, perimetre, fenetre, n, round(volatilite::numeric, 4), round(rendement::numeric, 4), round(rendement_repere::numeric, 4), round(pire_baisse::numeric, 4) FROM rapport.risque_mesure ORDER BY 3, 1, 2;
```

| niveau | perimetre | fenetre | n | round | round | round | round |
|---|---|---|---|---|---|---|---|
| compte | CELI-1 | 12 mois | 261 | 0.0697 | 0.0814 | 0.1244 | -0.0565 |
| compte | CELI-2 | 12 mois | 261 | 0.0573 | 0.0812 | 0.0985 | -0.0456 |
| compte | CELIAPP-1 | 12 mois | 261 | 0.0651 | 0.0709 | 0.0946 | -0.0544 |
| compte | COMP-1 | 12 mois | 261 | 0.0367 | 0.0216 | 0.0373 | -0.0437 |
| compte | REER-1 | 12 mois | 261 | 0.0709 | 0.0986 | 0.1109 | -0.0401 |
| compte | REER-2 | 12 mois | 261 | 0.0445 | 0.0072 | 0.0392 | -0.0539 |
| fonds | F101 | 12 mois | 261 | 0.0353 | 0.0377 | 0.0636 | -0.0256 |
| fonds | F103 | 12 mois | 261 | 0.0761 | 0.0629 | 0.1157 | -0.0724 |
| fonds | F105 | 12 mois | 261 | 0.0824 | 0.1743 | 0.1374 | -0.0505 |
| fonds | F106 | 12 mois | 261 | 0.1046 | 0.0967 | 0.1050 | -0.0781 |
| fonds | F201 | 12 mois | 261 | 0.0320 | 0.0380 | 0.0243 | -0.0247 |
| fonds | F202 | 12 mois | 261 | 0.0853 | -0.0650 | -0.0212 | -0.1368 |
| fonds | F203 | 12 mois | 261 | 0.0315 | 0.0790 | 0.0636 | -0.0184 |
| fonds | F204 | 12 mois | 261 | 0.0488 | 0.0494 | 0.0842 | -0.0348 |
| fonds | F301 | 12 mois | 261 | 0.0012 | 0.0162 | 0.0158 | -0.0003 |
| fonds | F302 | 12 mois | 261 | 0.0973 | 0.1440 | 0.1686 | -0.0711 |
| fonds | F303 | 12 mois | 261 | 0.0932 | 0.0941 | 0.1050 | -0.0669 |
| fonds | F304 | 12 mois | 261 | 0.0958 | 0.0440 | 0.1460 | -0.1107 |
| global | global | 12 mois | 261 | 0.0596 | 0.0779 | 0.1062 | -0.0449 |
| régime | CELI | 12 mois | 261 | 0.0631 | 0.0845 | 0.1125 | -0.0516 |
| régime | CELIAPP | 12 mois | 261 | 0.0651 | 0.0709 | 0.0946 | -0.0544 |
| régime | COMP | 12 mois | 261 | 0.0367 | 0.0216 | 0.0373 | -0.0437 |
| régime | REER | 12 mois | 261 | 0.0696 | 0.0947 | 0.1080 | -0.0405 |
| compte | CELI-1 | depuis le début | 1194 | 0.0968 | 0.0706 | 0.1094 | -0.1541 |
| compte | CELI-2 | depuis le début | 750 | 0.0658 | 0.0385 | 0.0577 | -0.1103 |
| compte | CELIAPP-1 | depuis le début | 744 | 0.0696 | 0.0181 | 0.0408 | -0.1245 |
| compte | COMP-1 | depuis le début | 713 | 0.0440 | 0.0079 | -0.0009 | -0.0636 |
| compte | REER-1 | depuis le début | 1288 | 0.0955 | 0.0919 | 0.0983 | -0.1624 |
| compte | REER-2 | depuis le début | 387 | 0.0503 | 0.0282 | 0.0401 | -0.0539 |
| fonds | F101 | depuis le début | 750 | 0.0406 | 0.0210 | 0.0437 | -0.0463 |
| fonds | F103 | depuis le début | 750 | 0.0924 | 0.0210 | 0.0735 | -0.1938 |
| fonds | F105 | depuis le début | 750 | 0.1001 | 0.1264 | 0.0993 | -0.1407 |
| fonds | F106 | depuis le début | 750 | 0.1110 | 0.0324 | 0.0288 | -0.2006 |
| fonds | F201 | depuis le début | 713 | 0.0362 | 0.0241 | 0.0165 | -0.0305 |
| fonds | F202 | depuis le début | 713 | 0.0907 | -0.0578 | -0.0758 | -0.1971 |
| fonds | F203 | depuis le début | 713 | 0.0375 | 0.0463 | 0.0323 | -0.0303 |
| fonds | F204 | depuis le début | 713 | 0.0583 | 0.0324 | 0.0403 | -0.0643 |
| fonds | F301 | depuis le début | 874 | 0.0012 | 0.0150 | 0.0154 | -0.0003 |
| fonds | F302 | depuis le début | 1288 | 0.1239 | 0.1226 | 0.1336 | -0.1632 |
| fonds | F303 | depuis le début | 1288 | 0.1125 | 0.0849 | 0.0918 | -0.2479 |
| fonds | F304 | depuis le début | 1194 | 0.1208 | 0.0308 | 0.1200 | -0.2185 |
| global | global | depuis le début | 1288 | 0.0906 | 0.0867 | 0.1021 | -0.1497 |
| régime | CELI | depuis le début | 1194 | 0.0936 | 0.0730 | 0.1058 | -0.1355 |
| régime | CELIAPP | depuis le début | 744 | 0.0696 | 0.0181 | 0.0408 | -0.1245 |
| régime | COMP | depuis le début | 713 | 0.0440 | 0.0079 | -0.0009 | -0.0636 |
| régime | REER | depuis le début | 1288 | 0.0952 | 0.0912 | 0.0977 | -0.1624 |

## 4. Valeur marchande par société à l'arrêté

| Société | VM | Part |
|---|---|---|
| Société 1 | 38,558.98 $ | 33.5% |
| Société 2 | 9,603.97 $ | 8.4% |
| Société 3 | 66,847.08 $ | 58.1% |
| Total | 115,010.03 $ | 100 % |

Seuil de frais par société (`rapport.seuil`) : Société 1 38558.98 $ (Moins de 100 000 $) ; Société 2 9603.97 $ (Moins de 100 000 $) ; Société 3 66847.08 $ (Moins de 100 000 $).

