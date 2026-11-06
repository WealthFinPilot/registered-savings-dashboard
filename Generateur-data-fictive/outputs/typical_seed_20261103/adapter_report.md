# Rapport de l'adaptateur vers finance_ve01 (J6)

> SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER. Écrit par `scripts/recette_synthetique.py --controle rapport` depuis la base chargée et les exports.

Base `finance_ve01`, arrêté du 2026-10-30. Le rapport Power BI figé n'est pas touché tant que `scripts/figer.py` ne tourne pas (J7).

## 1. Distributions par fonds et par année

Taux = somme des taux versés dans l'année (fraction de la VL avant versement), revenu courant + gains en capital de décembre ; la plage de `[adapter.yield_pct]` ne porte que sur le revenu courant, les gains en capital sont une part tirée du gain de l'année au-delà de ce revenu. Réinvesti = montants des lignes « Distribution réinvestie » des comptes. Natures : dernier exercice publié (`pub.rapport_annuel`, exercice au 30 septembre), part de chaque nature.

| Fonds | Archétype | Fréquence | 2021 revenu + gains / réinvesti | 2022 revenu + gains / réinvesti | 2023 revenu + gains / réinvesti | 2024 revenu + gains / réinvesti | 2025 revenu + gains / réinvesti | 2026 revenu + gains / réinvesti | Revenus / dividendes / gains en capital |
|---|---|---|---|---|---|---|---|---|---|
| F101 | conservateur | monthly | 0.41% + 0.00% / 0.00 $ | 2.84% + 0.00% / 0.00 $ | 2.60% + 0.04% / 0.52 $ | 2.64% + 0.00% / 60.43 $ | 2.74% + 0.00% / 149.59 $ | 2.23% + 0.00% / 161.85 $ | 67% / 33% / 0% |
| F102 | equilibre | annual | 1.81% + 0.00% / 0.00 $ | 2.04% + 0.00% / 0.00 $ | 2.00% + 0.00% / 0.00 $ | 2.68% + 0.00% / 0.00 $ | 1.64% + 0.00% / 0.00 $ | — / 0.00 $ | 45% / 55% / 0% |
| F103 | croissance | annual | 2.16% + 0.00% / 0.00 $ | 1.30% + 0.00% / 0.00 $ | 2.36% + 0.09% / 2.22 $ | 1.19% + 0.00% / 26.67 $ | 2.05% + 0.34% / 76.32 $ | — / 0.00 $ | 14% / 73% / 14% |
| F104 | actions_canadiennes | annual | 2.59% + 0.00% / 0.00 $ | 2.18% + 0.00% / 0.00 $ | 2.63% + 2.27% / 0.00 $ | 2.95% + 0.00% / 0.00 $ | 2.43% + 0.97% / 0.00 $ | — / 0.00 $ | 2% / 69% / 29% |
| F105 | actions_mondiales | annual | — / 0.00 $ | 1.24% + 0.00% / 0.00 $ | 0.98% + 0.00% / 0.18 $ | 1.12% + 0.00% / 11.02 $ | 1.13% + 0.78% / 21.30 $ | — / 0.00 $ | 0% / 59% / 41% |
| F106 | dividendes_canadiens | monthly | 0.71% + 0.26% / 0.00 $ | 3.92% + 0.32% / 0.00 $ | 4.15% + 1.51% / 1.97 $ | 3.98% + 0.00% / 40.56 $ | 3.89% + 0.59% / 113.84 $ | 3.41% + 0.00% / 120.91 $ | 2% / 85% / 13% |
| F201 | obligations_canadiennes | monthly | 0.47% + 0.00% / 0.00 $ | 2.81% + 0.73% / 0.00 $ | 2.96% + 0.00% / 0.00 $ | 2.86% + 0.00% / 13.30 $ | 2.87% + 0.00% / 32.70 $ | 2.39% + 0.00% / 42.96 $ | 100% / 0% / 0% |
| F202 | actifs_reels | monthly | 0.54% + 0.10% / 0.00 $ | 3.77% + 0.00% / 0.00 $ | 3.71% + 0.00% / 0.00 $ | 3.78% + 0.00% / 27.36 $ | 4.27% + 0.17% / 85.02 $ | 3.33% + 0.00% / 88.49 $ | 82% / 14% / 5% |
| F203 | conservateur | monthly | 0.41% + 0.00% / 0.00 $ | 2.17% + 0.00% / 0.00 $ | 2.14% + 0.00% / 0.00 $ | 2.13% + 0.00% / 12.47 $ | 2.27% + 0.00% / 32.23 $ | 1.85% + 0.00% / 35.11 $ | 69% / 31% / 0% |
| F204 | equilibre | annual | 1.67% + 0.00% / 0.00 $ | 2.06% + 0.00% / 0.00 $ | 2.02% + 1.00% / 0.00 $ | 1.77% + 0.00% / 19.26 $ | 1.95% + 0.12% / 38.33 $ | — / 0.00 $ | 41% / 53% / 6% |
| F301 | monetaire | monthly | — / 0.00 $ | — / 0.00 $ | 0.07% + 0.00% / 1.81 $ | 0.22% + 0.00% / 6.20 $ | 0.58% + 0.00% / 16.74 $ | 1.05% + 0.00% / 32.62 $ | 100% / 0% / 0% |
| F302 | actions_americaines | annual | 1.25% + 0.09% / 7.49 $ | 1.10% + 0.00% / 52.61 $ | 1.46% + 0.24% / 150.37 $ | 0.97% + 0.00% / 95.55 $ | 1.28% + 1.52% / 340.19 $ | — / 0.00 $ | 0% / 45% / 55% |
| F303 | actions_canadiennes | annual | 3.06% + 0.00% / 31.27 $ | 2.82% + 0.00% / 180.12 $ | 3.05% + 4.02% / 662.44 $ | 3.90% + 0.00% / 395.63 $ | 3.78% + 2.42% / 771.86 $ | — / 0.00 $ | 1% / 60% / 39% |
| F304 | petites_cap_nord_americaines | annual | 1.03% + 0.00% / 0.00 $ | 0.84% + 0.00% / 18.61 $ | 0.95% + 0.34% / 56.70 $ | 1.06% + 0.00% / 53.19 $ | 0.99% + 1.96% / 163.49 $ | — / 0.00 $ | 0% / 33% / 67% |

## 2. TWR Dietz du rapport contre TWR quotidien du J5

Dietz : `rapport.rendement_annuel` (compte, global), Dietz mensuel de la société chaîné (Σ numérateurs ÷ Σ dénominateurs de `rapport.performance`). TWR : `performance_periods`. Cause donnée pour tout écart de plus de 0,5 point : les mois de même signe qui en portent au moins 80 %, chaque mois comparé au TWR quotidien chaîné sur le même mois, avec son motif.

| Niveau | Entité | Année | Dietz | TWR | Écart (pt) | Cause (écart > 0,5 pt) |
|---|---|---|---|---|---|---|
| global | Global | 2021 | -0.72% | -0.44% | -0.284 |  |
| global | Global | 2022 | -12.84% | -12.20% | -0.645 | 2022-01 -0.85 pt, flux de 48% de la valeur de début : pondération de Dietz (Σ -0.85 pt sur -0.65) |
| global | Global | 2023 | 7.17% | 7.13% | +0.039 |  |
| global | Global | 2024 | -8.82% | -8.75% | -0.073 |  |
| global | Global | 2025 | 7.99% | 7.97% | +0.020 |  |
| global | Global | 2026 | -2.56% | -2.55% | -0.011 |  |
| société | Société 1 | 2023 | 0.30% | 1.76% | -1.457 | 2023-12 -1.46 pt, premier mois : valeur de début nulle, Dietz sur les seuls apports pondérés (Σ -1.46 pt sur -1.46) |
| société | Société 1 | 2024 | -5.70% | -5.39% | -0.316 |  |
| société | Société 1 | 2025 | 5.21% | 5.19% | +0.027 |  |
| société | Société 1 | 2026 | -0.82% | -0.77% | -0.053 |  |
| société | Société 2 | 2024 | -3.44% | -3.40% | -0.038 |  |
| société | Société 2 | 2025 | 2.17% | 2.15% | +0.017 |  |
| société | Société 2 | 2026 | 3.89% | 4.00% | -0.110 |  |
| société | Société 3 | 2021 | -0.72% | -0.44% | -0.284 |  |
| société | Société 3 | 2022 | -12.84% | -12.20% | -0.645 | 2022-01 -0.85 pt, flux de 48% de la valeur de début : pondération de Dietz (Σ -0.85 pt sur -0.65) |
| société | Société 3 | 2023 | 7.19% | 7.14% | +0.050 |  |
| société | Société 3 | 2024 | -9.27% | -9.27% | +0.000 |  |
| société | Société 3 | 2025 | 10.22% | 10.22% | +0.002 |  |
| société | Société 3 | 2026 | -5.06% | -5.07% | +0.005 |  |
| compte | CELI-1 | 2022 | -3.46% | -2.10% | -1.362 | 2022-07 -0.67 pt, flux de 38% de la valeur de début : pondération de Dietz ; 2022-09 -0.62 pt, flux de 21% de la valeur de début : pondération de Dietz (Σ -1.28 pt sur -1.36) |
| compte | CELI-1 | 2023 | 4.81% | 4.53% | +0.281 |  |
| compte | CELI-1 | 2024 | -8.61% | -8.61% | -0.002 |  |
| compte | CELI-1 | 2025 | 9.80% | 9.81% | -0.007 |  |
| compte | CELI-1 | 2026 | -4.88% | -4.89% | +0.010 |  |
| compte | CELI-2 | 2023 | 1.90% | 1.77% | +0.135 |  |
| compte | CELI-2 | 2024 | -5.77% | -5.56% | -0.205 |  |
| compte | CELI-2 | 2025 | 4.47% | 4.47% | -0.008 |  |
| compte | CELI-2 | 2026 | -0.39% | -0.36% | -0.023 |  |
| compte | CELIAPP-1 | 2023 | -0.45% | -0.36% | -0.083 |  |
| compte | CELIAPP-1 | 2024 | -6.44% | -6.51% | +0.075 |  |
| compte | CELIAPP-1 | 2025 | 6.10% | 6.08% | +0.027 |  |
| compte | CELIAPP-1 | 2026 | -1.27% | -1.16% | -0.117 |  |
| compte | COMP-1 | 2024 | -3.44% | -3.40% | -0.038 |  |
| compte | COMP-1 | 2025 | 2.17% | 2.11% | +0.064 |  |
| compte | COMP-1 | 2026 | 3.95% | 4.02% | -0.074 |  |
| compte | REER-1 | 2021 | -0.72% | -0.44% | -0.284 |  |
| compte | REER-1 | 2022 | -11.61% | -11.41% | -0.203 |  |
| compte | REER-1 | 2023 | 9.65% | 9.74% | -0.096 |  |
| compte | REER-1 | 2024 | -9.86% | -9.86% | -0.001 |  |
| compte | REER-1 | 2025 | 10.69% | 10.68% | +0.014 |  |
| compte | REER-1 | 2026 | -5.26% | -5.25% | -0.007 |  |
| compte | REER-2 | 2025 | -0.33% | -0.36% | +0.024 |  |
| compte | REER-2 | 2026 | 2.90% | 3.38% | -0.481 |  |

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
| CELI | 2025 | 39770.00 | 2240.00 | 37530.00 | aucune |
| CELI | 2026 | 44530.00 | 1900.00 | 42630.00 | aucune |
| CELIAPP | 2023 | 8000.00 | 300.00 | 7700.00 | aucune |
| CELIAPP | 2024 | 15700.00 | 2750.00 | 12950.00 | aucune |
| CELIAPP | 2025 | 16000.00 | 3250.00 | 12750.00 | aucune |
| CELIAPP | 2026 | 16000.00 | 3250.00 | 12750.00 | aucune |
| REER | 2021 | 20633.94 | 3300.00 | 17333.94 | aucune |
| REER | 2022 | 30869.94 | 4920.00 | 25949.94 | aucune |
| REER | 2023 | 40565.94 | 4872.55 | 35693.39 | aucune |
| REER | 2024 | 52973.39 | 880.00 | 52093.39 | aucune |
| REER | 2025 | 69805.39 | 1175.58 | 68629.81 | aucune |
| REER | 2026 | 86809.81 | 1004.86 | 85804.95 | aucune |

```sql
SELECT c.societe, round(sum(p.vm_fin)) FROM rapport.performance p JOIN ref.compte c ON c.alias = p.compte_alias WHERE (p.compte_alias, p.date_fin) IN (SELECT compte_alias, max(date_fin) FROM rapport.performance GROUP BY 1) GROUP BY 1 ORDER BY 1;
```

| societe | round |
|---|---|
| Société 1 | 17340 |
| Société 2 | 9995 |
| Société 3 | 33625 |

```sql
SELECT coalesce(compte_alias, 'GLOBAL'), annee, round(twr * 100, 2) FROM rapport.rendement_annuel ORDER BY 1, 2;
```

| coalesce | annee | round |
|---|---|---|
| CELI-1 | 2022 | -3.46 |
| CELI-1 | 2023 | 4.81 |
| CELI-1 | 2024 | -8.61 |
| CELI-1 | 2025 | 9.80 |
| CELI-1 | 2026 | -4.88 |
| CELI-2 | 2023 | 1.90 |
| CELI-2 | 2024 | -5.77 |
| CELI-2 | 2025 | 4.47 |
| CELI-2 | 2026 | -0.39 |
| CELIAPP-1 | 2023 | -0.45 |
| CELIAPP-1 | 2024 | -6.44 |
| CELIAPP-1 | 2025 | 6.10 |
| CELIAPP-1 | 2026 | -1.27 |
| COMP-1 | 2024 | -3.44 |
| COMP-1 | 2025 | 2.17 |
| COMP-1 | 2026 | 3.95 |
| GLOBAL | 2021 | -0.72 |
| GLOBAL | 2022 | -12.84 |
| GLOBAL | 2023 | 7.17 |
| GLOBAL | 2024 | -8.82 |
| GLOBAL | 2025 | 7.99 |
| GLOBAL | 2026 | -2.56 |
| REER-1 | 2021 | -0.72 |
| REER-1 | 2022 | -11.61 |
| REER-1 | 2023 | 9.65 |
| REER-1 | 2024 | -9.86 |
| REER-1 | 2025 | 10.69 |
| REER-1 | 2026 | -5.26 |
| REER-2 | 2025 | -0.33 |
| REER-2 | 2026 | 2.90 |

```sql
SELECT niveau, perimetre, fenetre, n, round(volatilite::numeric, 4), round(rendement::numeric, 4), round(rendement_repere::numeric, 4), round(pire_baisse::numeric, 4) FROM rapport.risque_mesure ORDER BY 3, 1, 2;
```

| niveau | perimetre | fenetre | n | round | round | round | round |
|---|---|---|---|---|---|---|---|
| compte | CELI-1 | 12 mois | 261 | 0.0963 | -0.0006 | -0.0076 | -0.1008 |
| compte | CELI-2 | 12 mois | 261 | 0.0737 | 0.0244 | 0.0233 | -0.0792 |
| compte | CELIAPP-1 | 12 mois | 261 | 0.0714 | 0.0153 | 0.0158 | -0.0691 |
| compte | COMP-1 | 12 mois | 261 | 0.0581 | 0.0333 | 0.0437 | -0.0440 |
| compte | REER-1 | 12 mois | 261 | 0.1091 | -0.0025 | -0.0137 | -0.1079 |
| compte | REER-2 | 12 mois | 261 | 0.0668 | 0.0361 | 0.0471 | -0.0537 |
| fonds | F101 | 12 mois | 261 | 0.0472 | 0.0273 | 0.0365 | -0.0377 |
| fonds | F103 | 12 mois | 261 | 0.1095 | 0.0589 | 0.0215 | -0.1192 |
| fonds | F105 | 12 mois | 261 | 0.1103 | 0.0148 | 0.0337 | -0.1186 |
| fonds | F106 | 12 mois | 261 | 0.1177 | -0.0320 | -0.0214 | -0.1282 |
| fonds | F201 | 12 mois | 261 | 0.0443 | 0.0450 | 0.0516 | -0.0578 |
| fonds | F202 | 12 mois | 261 | 0.1242 | 0.0717 | 0.0682 | -0.1126 |
| fonds | F203 | 12 mois | 261 | 0.0473 | 0.0157 | 0.0365 | -0.0475 |
| fonds | F204 | 12 mois | 261 | 0.0698 | 0.0081 | 0.0308 | -0.0615 |
| fonds | F301 | 12 mois | 261 | 0.0009 | 0.0122 | 0.0126 | -0.0002 |
| fonds | F302 | 12 mois | 261 | 0.1257 | 0.0027 | -0.0045 | -0.1274 |
| fonds | F303 | 12 mois | 261 | 0.1219 | -0.0068 | -0.0214 | -0.1007 |
| fonds | F304 | 12 mois | 261 | 0.1213 | -0.0061 | -0.0104 | -0.1288 |
| global | global | 12 mois | 261 | 0.0839 | 0.0111 | 0.0068 | -0.0865 |
| régime | CELI | 12 mois | 261 | 0.0882 | 0.0067 | 0.0014 | -0.0945 |
| régime | CELIAPP | 12 mois | 261 | 0.0714 | 0.0153 | 0.0158 | -0.0691 |
| régime | COMP | 12 mois | 261 | 0.0581 | 0.0333 | 0.0437 | -0.0440 |
| régime | REER | 12 mois | 261 | 0.1071 | -0.0001 | -0.0107 | -0.1056 |
| compte | CELI-1 | depuis le début | 1194 | 0.1711 | 0.0072 | 0.0027 | -0.2431 |
| compte | CELI-2 | depuis le début | 750 | 0.0713 | 0.0105 | 0.0139 | -0.0956 |
| compte | CELIAPP-1 | depuis le début | 744 | 0.0705 | 0.0021 | 0.0046 | -0.0997 |
| compte | COMP-1 | depuis le début | 713 | 0.0530 | 0.0170 | 0.0286 | -0.0579 |
| compte | REER-1 | depuis le début | 1288 | 0.1655 | -0.0049 | -0.0071 | -0.3215 |
| compte | REER-2 | depuis le début | 387 | 0.0687 | 0.0280 | 0.0328 | -0.0672 |
| fonds | F101 | depuis le début | 750 | 0.0451 | -0.0011 | 0.0153 | -0.0798 |
| fonds | F103 | depuis le début | 750 | 0.0994 | 0.0329 | 0.0148 | -0.1234 |
| fonds | F105 | depuis le début | 750 | 0.1110 | 0.0080 | 0.0206 | -0.1594 |
| fonds | F106 | depuis le début | 750 | 0.1238 | 0.0076 | 0.0025 | -0.2335 |
| fonds | F201 | depuis le début | 713 | 0.0403 | 0.0032 | 0.0159 | -0.0942 |
| fonds | F202 | depuis le début | 713 | 0.1094 | 0.0639 | 0.0681 | -0.1126 |
| fonds | F203 | depuis le début | 713 | 0.0443 | -0.0009 | 0.0131 | -0.0777 |
| fonds | F204 | depuis le début | 713 | 0.0683 | -0.0066 | 0.0120 | -0.0895 |
| fonds | F301 | depuis le début | 891 | 0.0009 | 0.0051 | 0.0062 | -0.0008 |
| fonds | F302 | depuis le début | 1288 | 0.2002 | -0.0129 | -0.0362 | -0.2985 |
| fonds | F303 | depuis le début | 1288 | 0.1723 | 0.0001 | 0.0151 | -0.3449 |
| fonds | F304 | depuis le début | 1194 | 0.1829 | -0.0038 | -0.0001 | -0.2671 |
| global | global | depuis le début | 1288 | 0.1611 | -0.0089 | -0.0068 | -0.3232 |
| régime | CELI | depuis le début | 1194 | 0.1688 | 0.0077 | 0.0068 | -0.2431 |
| régime | CELIAPP | depuis le début | 744 | 0.0705 | 0.0021 | 0.0046 | -0.0997 |
| régime | COMP | depuis le début | 713 | 0.0530 | 0.0170 | 0.0286 | -0.0579 |
| régime | REER | depuis le début | 1288 | 0.1651 | -0.0046 | -0.0067 | -0.3215 |

## 4. Valeur marchande par société à l'arrêté

| Société | VM | Part |
|---|---|---|
| Société 1 | 17,339.93 $ | 28.4% |
| Société 2 | 9,995.26 $ | 16.4% |
| Société 3 | 33,624.73 $ | 55.2% |
| Total | 60,959.92 $ | 100 % |

Seuil de frais par société (`rapport.seuil`) : Société 1 17339.93 $ (Moins de 100 000 $) ; Société 2 9995.26 $ (Moins de 100 000 $) ; Société 3 33624.73 $ (Moins de 100 000 $).

