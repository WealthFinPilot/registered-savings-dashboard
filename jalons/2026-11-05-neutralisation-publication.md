# Contrat de jalon — Neutralisation du format fictif et publication propre

- **Projet :** DashBoard-Finance vE01
- **Ouvert le :** 2026-11-05
- **Contrat validé par le responsable :** oui, le 2026-11-05 (dépôt GitHub supprimé par le responsable le même jour)
- **Statut :** accepté

## Objectif

Donner au jeu fictif des libellés de transaction et des codes d'option qui lui sont propres, sans aucun
emprunt à un format d'export existant, puis publier le dépôt avec un historique qui ne contient que
l'état assaini. Les montants, dates et positions du jeu fictif ne changent pas : seuls des libellés et
des codes changent, et ils n'entrent pas dans le modèle sémantique.

## Livrables

| Livrable | Chemin |
|---|---|
| Libellés et natures neutres | `Generateur-data-fictive/src/synthetic_finance/adapter.py` (`LIBELLES`, `NATURES`, échanges) |
| Codes d'option neutres : `FA`, `FR`, `FM` (frais d'acquisition, de rachat, modérés) | `sql/schema.sql` (contrainte de `pub.profil_code`), `adapter.py` |
| Commentaires et descriptions alignés | `sql/schema.sql`, `rapport/…/tables/Détention.tmdl`, `Generateur-data-fictive/docs/contrat_donnees.md` |
| Sorties régénérées (mêmes graines) | `Generateur-data-fictive/outputs/typical_seed_20261103/`, `…/vitrine_seed_20261103/` |
| Comparateur de sorties | `Generateur-data-fictive/scripts/comparer_sorties.py` |
| Balayage étendu : motifs privés supplémentaires lus dans un fichier hors suivi (`motifs-prives.txt`, exclu par `.gitignore`) ; `jalons/` ajouté au périmètre projet | `Generateur-data-fictive/scripts/balayage_fuite.py`, `.gitignore` |
| Dépôt GitHub recréé, historique réduit à l'état assaini | `origin` |

Nouveaux libellés : « Achat — versement programmé » (PAC), « Achat — versement ponctuel » (ponctuel),
« Distribution réinvestie » (revenu), « Arbitrage — achat depuis <fonds> » (interne, +1),
« Arbitrage — vente vers <fonds> » (interne, −1), « Frais de gestion » (frais), « Rachat — retrait »
(retrait).

Preuves sous `jalons/preuves/neutralisation-publication/`. Interpréteur : `Generateur-data-fictive/.venv`.

## Critères d'acceptation

| # | Critère | Preuve |
|---|---|---|
| C1 | **Plus aucun emprunt de format.** `ref.nature` des deux sorties ne contient que les sept motifs ci-dessus ; `pub.profil_code` n'a que des options `FA`, `FR` ou `FM`, et la contrainte SQL n'admet que ces trois valeurs. Les deux balayages (générateur, projet avec `jalons/`) rendent « AUCUNE FUITE », famille « motifs privés supplémentaires » comprise, et n'impriment aucun motif | `outputs/*/finance_ve01/ref.nature.csv`, `pub.profil_code.csv`, `sql/schema.sql` ; `balayage_fuite.py` et `--perimetre projet` → `fuite.txt` |
| C2 | **Seuls les libellés changent.** Pour les deux graines, chaque CSV régénéré est identique à sa version d'avant le jalon, sauf la colonne `libelle` de `fait.transaction` et `fait.historique` et la colonne `motif` de `ref.nature` ; nature, signe, montants, dates et parts sont identiques ligne à ligne. `validate` passe sur les deux sorties ; `pytest -q -k "not anticipation_grand_livre"` passe | `comparer_sorties.py` → `sorties.txt` ; `validate` → `validate.txt` ; `pytest` → `pytest.txt` |
| C3 | **Chaîne SQL et rapport inchangés en chiffres.** `charger_synthetique.py` charge la sortie vitrine sans erreur ; `recette_synthetique.py` rend OK pour `distributions`, `grand-livre`, `oracle` et `rapport` ; `figer.py` (Desktop fermé) laisse chaque bloc figé des `tables/*.tmdl` identique à l'octet près ; seule la description de `Détention.tmdl` change | sorties → `chargement.txt`, `recette.txt`, `figer.txt` ; `git diff --stat -- rapport/` → `diff-rapport.txt` |
| C4 | **Historique publié propre.** Le dépôt `origin` recréé ne contient aucun commit antérieur à ce jalon ; l'audit de tout l'historique publié (motifs des listes privées et motifs supplémentaires, partitions figées décompressées) compte 0 occurrence ; le dépôt reste privé jusqu'au passage en public par le responsable | `git log origin/main --oneline` et audit → `historique.txt` ; `gh repo view --json visibility` → `visibilite.txt` |

## Hors périmètre

- Renommer la colonne `code_fa` (terme générique « frais d'acquisition », présente dans le schéma, les
  vues et le modèle).
- Recette visuelle dans Desktop : les blocs figés étant identiques (C3), aucun chiffre ne peut changer.
- Passage du dépôt en public : décision et geste du responsable.
- L'ancien historique reste en local sur une branche jamais poussée ; il n'est pas détruit.

## Modifications du contrat

- 2026-11-05, C3 : la description de `Cotisation REER.tmdl` change aussi (une parenthèse sur le type de compte
  des saisies sans compte, trouvée par le balayage étendu). Comme celle de `Détention.tmdl`, c'est une
  description `///`, hors de tout bloc figé ; les 18 partitions restent inchangées.
- 2026-11-05, C1 et C3 : le diff du modèle n'est enregistré que par ses lignes ajoutées. Les lignes retirées
  contiennent les motifs à effacer et auraient été publiées dans la preuve.
- 2026-11-05, livrables : `balayage_fuite.py` lit aussi les fichiers qui ne sont pas en UTF-8 (deux sorties de
  console de `jalons/preuves/`, en encodage mixte), sans quoi le périmètre `jalons/` ne pouvait pas être balayé.
- 2026-11-05, C3 : dans `chargement.txt`, le chemin absolu du poste devant `sql/*.sql` (messages de psql) est
  retiré après coup ; le reste de la sortie est brut. Un chemin absolu porte un nom d'utilisateur.
- 2026-11-05, C4 : `donnees_fictives/` (référentiels hérités du premier jeu, utilisés par aucun script) est
  retiré avant la publication ; le générateur produit ses propres `ref.geographie` et `ref.risque`.

## Verdicts

### 2026-11-05 — evaluateur-jalon, passage 1

```
JALON    : Neutralisation du format fictif et publication propre (DashBoard-Finance vE01)
VERDICT  : ACCEPTÉ
CRITÈRES :
- [C1] PASS (attesté) — Constaté par moi : `ref.nature.csv` des deux sorties = exactement les 7 motifs du contrat (lignes 2-8). `pub.profil_code.csv` : 14 lignes sur 14 en `FA` dans chaque sortie. `sql/schema.sql:194` : `CHECK (option_achat IN ('FA', 'FR', 'FM'))`. Les deux balayages sont lus dans `fuite.txt:17` et `:35` (« AUCUNE FUITE », ligne « motifs privés supplémentaires : 0 », aucun motif imprimé), mais je ne les ai pas relancés.
- [C2] PASS (attesté) — `sorties.txt:51` et `:103` : « AUCUNE DIFFÉRENCE HORS COLONNES PERMISES ». Seules `fait.transaction.libelle` (1088 et 1141 lignes) et `ref.nature.motif` (6 lignes) diffèrent. J'ai relu `comparer_sorties.py:47-62` : la comparaison est ligne à ligne et colonne par colonne, sans exclusion implicite. `validate.txt` : réussi sur les deux sorties. `pytest.txt:6` : 240 passed, 21 deselected.
- [C3] PASS (attesté) — `chargement.txt:83-175` : 18 tables chargées, tous les contrôles PASS (45 vues). `recette.txt` : distributions, grand-livre, oracle et rapport à code de sortie 0. `figer.txt` : 18 « inchangée », confirmé par `grep -c` dans `diff-rapport.txt:8-9`. `diff-rapport.txt:2-3` : seuls `Cotisation REER.tmdl` et `Détention.tmdl` changent, une ligne chacun, des descriptions `///`, conformément à la modification de contrat du 2026-11-05.
- [C4] PASS (attesté) — `historique.txt:1-2` : un seul commit sur `origin/main`. `historique.txt:8-9` : 445 blobs texte, « AUCUNE FUITE ». `visibilite.txt:2` : `"visibility":"PRIVATE"`. `.git/config:9` : `origin` pointe vers `registered-savings-dashboard`. Les trois branches `archive/*` ont `pushRemote = ne-jamais-pousser`. `.gitignore:17` exclut `motifs-prives.txt`.
HORS CONTRAT :
- `Generateur-data-fictive/scripts/audit_historique.py:49-50` : `except Exception: pass` autour de la décompression des partitions figées. Si elle échoue sur un `.tmdl`, ses partitions ne sont pas auditées, et l'audit affiche quand même « AUCUNE FUITE ». De même `:43-44` : un `git cat-file` en échec fait sauter le blob sans message.
- `jalons/preuves/neutralisation-publication/diff-rapport.txt:1` : le diff est limité à `rapport/DashBoard-Finance.SemanticModel`. Le contrat C3 vise `rapport/`, donc `DashBoard-Finance.Report` (PBIR) n'est pas couvert par cette preuve.
- `pub.profil_code.csv` est « identique » avant et après le jalon (`sorties.txt:32` et `:84`). Les codes `FA`, `FR`, `FM` étaient donc déjà ceux du générateur, et seule la contrainte de `schema.sql` portait l'ancien format. Cohérent avec le contrat, mais le critère ne prouve rien sur le « avant » du côté du générateur.
À VÉRIFIER PAR SÉBASTIEN : tout est attesté (sorties de commandes produites par l'exécutant, sans exécution de ma part). Pour contrôler, relance `balayage_fuite.py` (sans option, puis avec `--perimetre projet`) et `audit_historique.py . origin/main`. Fais aussi `git ls-remote origin` et `gh repo view --json visibility`. Le nom d'utilisateur du chemin absolu retiré à la main dans `chargement.txt` (déclaré au contrat) n'est pas contrôlable ici, mais `jalons/` est dans le périmètre du balayage projet.
```

Suite donnée après le verdict : remarque 1 corrigée (`audit_historique.py` compte un fichier non lu ou une
partition non décompressée comme un échec ; relancé sur `origin/main` : aucune fuite, aucun fichier illisible).
Remarque 2 : les fichiers PBIR modifiés dans l'arbre de travail sont des retouches Desktop du responsable, non
commitées, hors de ce jalon. Remarque 3 : le générateur n'émettait que `FA`, avant comme après ; seule la
contrainte SQL portait l'ancien format, comme prévu.
