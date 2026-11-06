# Contrat de jalon — Générateur synthétique, J7 : bascule du rapport

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-04
- **Contrat validé par le responsable :** oui, le 2026-11-04 (suppression de `cours_fnb.py` et report de H3 à la publication confirmés)
- **Statut :** ouvert

## Objectif

Faire passer le rapport figé sur le jeu synthétique du générateur indépendant (J1 à J6, chargé dans
`finance_ve01`), puis retirer l'ancien générateur calé sur des FNB réels. Après ce jalon, aucun cours
réel ne reste dans le rapport ni dans le code. La chaîne documentée est celle du générateur indépendant.

Le modèle sémantique est validé depuis longtemps dans la v1 et n'est pas modifié. La recette DAX se
limite à vérifier que le gel et l'actualisation ne perdent rien : une requête par mesure de l'écart à la
v1 (seuil par société), plus la valeur marchande et les droits.

## Livrables

| Livrable | Chemin |
|---|---|
| Partitions refigées sur le jeu synthétique | `rapport/DashBoard-Finance.SemanticModel/definition/tables/*.tmdl` |
| Segment Année recalé sur 2021 à 2026, si l'affichage l'exige | `rapport/DashBoard-Finance.Report/definition/pages/7c4e2a9b1d6f3e8a5b20/visuals/1a7f3c9e2b4d6a8c0e15/visual.json` |
| Retrait de l'ancien générateur et du téléchargeur de cours réels | `generateur/generer.py`, `scripts/cours_fnb.py` (supprimés par `git rm`) |
| Chaîne de production et outillage à jour | `CLAUDE.md` (§ Objectif, § Chaîne de production), `README.md` |
| Balayage de fuite étendu au projet : `rapport/` (hors `StaticResources/RegisteredResources`), `sql/`, `scripts/`, `README.md` | `Generateur-data-fictive/scripts/balayage_fuite.py` (option de périmètre) |

Preuves sous `jalons/preuves/generateur-j7-bascule/`. Interpréteur : `Generateur-data-fictive/.venv`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Gel complet et rejouable.** `figer.py` s'exécute Desktop fermé, sans erreur, et nomme chaque partition figée. Après le gel, aucun `PostgreSQL.Database` ne reste dans le TMDL. Un second passage immédiat ne change aucun octet (`git diff --stat` vide entre les deux). | `python scripts/figer.py` → `figer.txt` (deux passages et le `git diff --stat` entre eux) ; `grep -c PostgreSQL.Database` sur `tables/` → `figer.txt` |
| C2 | **Actualisation sans base, chiffres conservés.** Le rapport s'ouvre et s'actualise dans Desktop sans erreur. Quatre requêtes DAX par le MCP `powerbi-modeling` donnent, au cent près, les mêmes valeurs que les vues SQL du même jour. Les quatre requêtes : `[Valeur marchande à date]` ; `SUMMARIZECOLUMNS(Compte[Société], "vm", [Valeur marchande à date], "actif", [Actif agrégé du ménage], "tranche", [Tranche de frais de gestion])` ; `CALCULATE([Droits restants], Droits[Régime] = "REER", Droits[annee] = 2026)` ; `[Actif agrégé du ménage]` sans filtre de société. Valeurs SQL de comparaison : `rapport.arrete`, `rapport.seuil`, `rapport.alerte`. | Actualisation : le responsable ; requêtes et résultats DAX → `dax.txt` ; requêtes SQL → `sql.txt` |
| C3 | **Rapport lisible sur le nouveau jeu.** Le segment Année montre six boutons, de 2021 à 2026, sans libellé tronqué. Les autres visuels gardent leur position. Aucune page n'affiche d'erreur de visuel. Un visuel vide ne s'accepte que s'il est expliqué par le jeu, par exemple Société 1 et Société 2 avant leur ouverture fin 2023. | le responsable, à l'écran |
| C4 | **Ancien générateur retiré, chaîne documentée.** `generateur/generer.py` et `scripts/cours_fnb.py` n'existent plus dans l'arbre. Aucun fichier suivi ne les cite, sauf l'historique des contrats de `jalons/`. `CLAUDE.md` et `README.md` décrivent la chaîne `generate --stage adapter` → `charger_synthetique.py` → `recette_synthetique.py` → `figer.py` → Desktop. | `git grep -n "generer.py\|cours_fnb" -- ':!jalons'` → `retrait.txt` (vide attendu) ; `CLAUDE.md`, `README.md` |
| C5 | **Aucune fuite dans le rapport livré.** Le balayage étendu au projet ne trouve ni symbole, ni nom de FNB réel, ni nom, code ou numéro de la v1. Il couvre les partitions figées, décompressées avant la recherche : le JSON est en deflate et en base64, donc invisible à une recherche directe. | `python scripts/balayage_fuite.py --perimetre projet` → `fuite.txt` |

## Hypothèses à confirmer

- **H1 — Répartition des gestes :** j'exécute `figer.py` et les requêtes. Le responsable ouvre le PBIP,
  clique sur Actualiser et contrôle les visuels. Ensuite, je me connecte au port de `msmdsrv`.
- **H2 — Données publiques locales :** `donnees_publiques/yahoo/` (hors git) reste sur le poste, parce que
  le balayage y lit les symboles réels qu'il recherche. Le supprimer, ou en extraire une liste de motifs,
  est un arbitrage du responsable.
- **H3 — Historique git :** les commits antérieurs contiennent des partitions figées avec des cours de FNB
  réels. Le J7 ne réécrit pas l'historique. Avant tout remote public, il faudra publier depuis un
  historique propre (branche orpheline ou squash), à décider au moment de la publication.
- **H4 — Seuil de 100 000 $ :** aucune société n'en approche (17 à 34 k$). « Tranche de frais de gestion »
  affichera « Moins de 100 000 $ » partout. Le cas haut relève du scénario `stress` du J8.
- **H5 — Jour de gel :** `rapport.droits_*` génère les années jusqu'à `current_date`. Le gel et
  `sql.txt` se font le même jour.

## Hors périmètre

Toute modification du modèle, des mesures, des relations ou de `sql/*.sql`. Un écart qui l'exigerait est
signalé, pas corrigé. Recette DAX au-delà des quatre requêtes de C2. Refonte de la disposition des pages
(seul le segment Année se recale). Scénarios `stress` et `adversarial`, dictionnaire, parcours de
démonstration (J8). Remote, publication et nettoyage de l'historique git.

## Modifications du contrat

Les deux du 2026-11-04, en cours de travail : **à valider par le responsable**. Aucun critère ne change.

- **Hors périmètre, `sql/schema.sql` (commentaire seulement).** Le balayage étendu (C5) trouve, en commentaire au
  l.138 de `sql/schema.sql`, un motif de la liste privée. Il est présent depuis le premier commit `da802d8`. La parenthèse est retirée, aucune instruction SQL
  ne change. La règle « aucune modification de `sql/*.sql` » vise le calcul, pas un commentaire qui enfreint la
  règle de publication du `CLAUDE.md`.
- **C5, jeton « DAX » exempté dans le périmètre projet.** La liste des familles d'indices réels contient « DAX ».
  Dans le rapport et dans les commentaires SQL, ce jeton désigne le langage du modèle (4 occurrences, toutes de
  ce sens), et une recherche par jeton ne distingue pas les deux sens. L'exemption ne vaut que pour
  `--perimetre projet`. Le périmètre du générateur garde les 18 motifs.

Trois autres, le 2026-11-04 au soir, à la reprise après le J6b : **à valider par le responsable**. Aucun critère ne change.

- **Jeu figé : `vitrine` au lieu de `typical`.** Le J6b, accepté après l'ouverture de ce contrat, a chargé dans
  `finance_ve01` le scénario `vitrine` (`outputs/vitrine_seed_20261103`, graine de marché 19). Les preuves du
  commit `b653879` portaient sur `typical` : elles sont toutes rejouées sur `vitrine`. H4 devient : 9,6 à 40,4 k$
  par société, 66,9 k$ au total, toujours sous le seuil de 100 000 $. `README.md` et les défauts de `--path` de
  `charger_synthetique.py` et `recette_synthetique.py` pointent sur `vitrine`.
- **C1, `figer.py` nomme chaque partition.** Il ne nommait que les fichiers réécrits : un passage sans changement
  ne nommait rien. Il affiche désormais, pour chaque fichier, la vue figée, la taille et « refigée » ou
  « inchangée ». Le calcul du gel ne change pas (même empreinte du diff avant et après la retouche).
- **C3, segment Année.** Le visuel est un segment en liste déroulante, pas en boutons : « six boutons » se lit
  « six valeurs » (2021 à 2025 et « En cours »). Il suit la table `Année` figée ; aucune retouche du `visual.json`.
- **H5, jour du gel.** PostgreSQL tourne en GMT : à 23 h, heure locale du 2026-11-04, `current_date` vaut déjà
  2026-11-05. Le gel et `sql.txt` sont faits sur la même `current_date` de la base (2026-11-05).

## Verdicts
