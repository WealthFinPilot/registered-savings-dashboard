# Histoire du projet

> **Toutes les données de ce dépôt sont fictives.** Épargnant, sociétés (Société 1 à 3), comptes (CELI-1,
> REER-2…), fonds (F101 à F304), cours, repères, versements et avis de cotisation sortent du générateur
> [`Generateur-data-fictive/`](../Generateur-data-fictive/), à partir d'une graine fixe. Ce document
> raconte la **méthode** de construction du tableau de bord : l'ordre des étapes, les décisions et leurs
> raisons, les contrôles. Les exemples cités sont pris dans le jeu fictif ; aucun ne décrit une
> personne, un compte, un fonds ou une institution réels.
>
> Le pipeline d'ingestion de la version d'exploitation (lecture des exports, extraction de PDF
> publics, cours, chargement PostgreSQL) existe, mais **n'est pas présenté ici, pour des raisons de
> confidentialité** : il traite des données réelles. Ce dépôt en décrit la méthode, les outils et
> l'architecture ; le rapport publié est alimenté par le générateur fictif.

Documents liés : [architecture.md](architecture.md) (chaîne de données, schéma du pipeline et outils) ; règles de calcul citées par
`sql/vues.sql` : [regles-droits.md](regles-droits.md), [regles-performance.md](regles-performance.md),
[regles-strategie.md](regles-strategie.md).

## Sommaire

1. [Le besoin](#le-besoin)
2. [Méthode de travail](#méthode-de-travail)
3. [Itération 1 — Lire avant de construire](#itération-1--lire-avant-de-construire)
4. [Itération 2 — Une base qu'on peut recharger cent fois](#itération-2--une-base-quon-peut-recharger-cent-fois)
5. [Itération 3 — Droits de cotisation : reconstruire, puis recouper](#itération-3--droits-de-cotisation--reconstruire-puis-recouper)
6. [Itération 4 — Patrimoine et rendement](#itération-4--patrimoine-et-rendement)
7. [Itération 5 — Stratégie par transparence](#itération-5--stratégie-par-transparence)
8. [Itération 6 — Fonds et risque](#itération-6--fonds-et-risque)
9. [Itération 7a — Cours, risque mesuré, repères](#itération-7a--cours-risque-mesuré-repères)
10. [Itération 7b — Rapports annuels de la direction](#itération-7b--rapports-annuels-de-la-direction)
11. [Itération 8 — Publication](#itération-8--publication)
12. [Des données fictives qui tiennent debout](#des-données-fictives-qui-tiennent-debout)
13. [Ce qui a été écarté](#ce-qui-a-été-écarté)
14. [Leçons](#leçons)

## Le besoin

L'épargnant fictif détient des comptes enregistrés (CELI, CELIAPP, REER) et non enregistrés (COMP)
répartis entre trois sociétés de fonds, chacune avec son conseiller. Aucun conseiller ne voit ce que
font les autres : deux d'entre eux peuvent remplir le même compte sans le savoir, ou bâtir la même
stratégie dans deux régimes différents.

Le tableau de bord répond à quatre questions, chaque mois :

1. Combien reste-t-il de droits CELI, CELIAPP et REER pour l'année, et qui y verse quoi ?
2. Quelle part des versements mensuels va dans chaque compte, versements programmés (PAC) et
   ponctuels distingués ?
3. Quel compte performe ou sous-performe par rapport à son repère ?
4. Les stratégies des sociétés se recouvrent-elles (mêmes classes d'actif, mêmes styles, dans des
   comptes différents) ?

La page 1 sort en PDF, la même pour tous les conseillers : chacun voit la stratégie des autres. Les
pages suivantes servent au pilotage personnel de l'épargnant.

**Contraintes posées au cadrage.**

- Aucune API chez les sociétés : l'ingestion part d'exports téléchargés à la main depuis le portail
  client.
- Confidentialité : aucune donnée hors du poste, sauf la publication dans Power BI Service, sur un
  tenant personnel. Pas de remote git pour une version qui porterait des données réelles.
- Budget zéro au-delà d'une licence Power BI Pro.
- Aller vite : une recette ciblée par mesure, pas de batterie de tests pour une ligne de DAX.

**Critères de réussite, à un an.** La routine mensuelle (déposer les exports, actualiser, publier,
exporter le PDF, l'envoyer) prend au plus 10 minutes de travail manuel. Un conseiller répond en
30 secondes, depuis la page 1, à « combien reste-t-il de droits cette année, et qui y verse quoi ? ».
Tout dépassement apparaît en alerte dans le PDF du mois où il se produit. Le critère « aucun
dépassement » a été écarté dès le cadrage : un dépassement assumé juge la décision d'investissement,
pas l'outil.

## Méthode de travail

- **Une itération, un contrat.** Chaque itération est bornée par un contrat de jalon : trois à cinq
  critères d'acceptation, écrits et validés **avant** le travail. À la clôture, un évaluateur
  indépendant, en lecture seule, rend un verdict par critère (PASS, FAIL ou NON VÉRIFIABLE), preuve à
  l'appui (fichier et ligne). Les contrats et preuves du générateur sont publiés dans
  [`../jalons/`](../jalons/).
- **Développement assisté par un agent de code** (Claude Code). Le responsable pilote : cadrage,
  arbitrages métier, recette visuelle dans Power BI Desktop. L'agent écrit le Python, le SQL, le DAX et
  le PBIR. Toute API dont la version compte, et toute règle fiscale, se vérifie dans la documentation
  officielle avant d'écrire : aucun plafond n'est saisi de mémoire.
- **Recette contre un calcul indépendant.** Chaque famille de vues SQL a un témoin réécrit sans SQL,
  avec une autre écriture des formules quand c'est possible. En DAX, une relation manquante affiche un
  chiffre plausible et faux, sans erreur : chaque mesure est recettée avant de construire son visuel.
- **Hypothèses marquées.** `[FAIT]`, `[HYPOTHÈSE]`, `[INCONNU]` : une hypothèse porte la conséquence de
  son échec et l'itération où elle sera levée.
- **Journal des décisions.** Une ligne par décision, avec sa raison et l'option écartée. Quand le
  responsable tranche contre la recommandation de l'agent, le journal le dit.

## Itération 1 — Lire avant de construire

Livrable sans code de production : une fiche d'analyse des exports, une décision de stockage
argumentée entre trois options, le plan des itérations suivantes. Raison : ne pas bâtir un pipeline
sur un format jamais vu.

**Quatre hypothèses, avec une condition d'arrêt du projet.**

| # | Hypothèse | Ce qui se passe si elle tombe |
|---|---|---|
| H1 | L'export donne, par compte et par mois, la valeur de début, la valeur de fin et les flux | Le TWR n'est pas calculable directement : il faut reconstruire les valeurs passées (parts × prix) |
| H2 | L'export donne les positions par fonds | Pas de cible pondérée par compte : une cible saisie à la main |
| H3 | Un libellé distingue versement programmé et ponctuel | La part mensuelle ne distingue plus PAC et ponctuels |
| H4 | Les exports se retéléchargent à volonté | Toute pièce non régénérable doit être archivée chaque mois et sauvegardée hors du poste |

La fiche d'analyse tranche chaque hypothèse sur pièces. Le point qui a le plus pesé sur la suite est H4 :
un **sommaire de positions** qui n'existe qu'à la date du jour est la seule source d'une valeur
marchande exacte. S'il n'est pas archivé le mois même, il est perdu ; la routine et la sauvegarde en
tiennent compte.

**Principes de lecture retenus**, valables pour tout export de portail :

- reconnaître la famille d'un fichier à son contenu (nom de feuille, en-tête), jamais à son nom de
  fichier, qui peut porter un numéro de compte ;
- localiser l'en-tête au lieu de supposer sa ligne ; lire une colonne par position ou par table de
  synonymes, jamais par son seul nom ;
- contrôler la continuité du solde de parts (solde précédent ± parts négociées) et l'absence de
  doublons avant toute écriture ;
- traiter le sens des parts par une table libellé → nature et signe, pas par le signe du montant.

**Limite assumée.** Un transfert entrant depuis une autre institution peut ressembler à une
cotisation, alors qu'un transfert direct ne consomme pas de droits. Parade : une table de transferts
saisie à la main.

**Décision de stockage.**

| Critère | A. Power Query direct | B. PostgreSQL local | C. PostgreSQL sur un VPS |
|---|---|---|---|
| Données au repos | Poste | Poste | Poste **et** hôte exposé à Internet |
| Étapes ajoutées à la routine | 0 | +1 (lancer le chargement) | +2 (téléverser, charger par tunnel SSH) |
| Nouvelle société | Une fonction M par format, lourde au-delà de deux | Un adaptateur Python par format, schéma commun | Comme B |
| Lisible par l'évaluateur | M en texte dans le PBIP | Python et SQL en clair | Comme B |

C est écartée d'office : elle ajoute un lieu de stockage exposé sans retirer le poste du risque. A était
la plus simple et la recommandation de l'agent. Le responsable a retenu B : un adaptateur par format
pour chaque société, du code lisible par l'évaluateur, un vrai volet Python et SQL. Coûts acceptés :
une étape de plus par mois, une base à installer et à sauvegarder. La condition de retour arrière est
écrite dans la décision : si la base pèse plus que prévu, revenir à A, le chargement Python servant
alors à produire un fichier propre.

## Itération 2 — Une base qu'on peut recharger cent fois

- **Chargement en deux temps, jamais mêlés.** D'abord tout lire et tout contrôler (format, compte
  connu, libellé connu) sans ouvrir la base ; ensuite tout écrire dans une seule transaction. Un écart
  arrête tout avec un code de sortie distinct : rien n'est écrit.
- **Règles de remplacement.** Le dernier relevé de chaque compte remplace ses transactions. Chaque
  sommaire remplace le sommaire de même clé (compte, date de valorisation) ; ceux des mois précédents
  restent.
- **Idempotence prouvée, pas affirmée.** Une empreinte de la base (nombre de lignes et MD5 par table)
  doit être identique après deux chargements des mêmes fichiers.
- **Contrôle de schéma éprouvé sur des classeurs fictifs** : colonne absente, colonne renommée,
  en-tête décalé d'une ligne. Chaque scénario associe un fichier valide et un fichier fautif : si le
  chargement écrivait avant d'avoir tout contrôlé, le fichier valide laisserait une trace en base.
- **Remarque hors contrat de l'évaluateur**, retenue : une ligne vide au milieu d'un tableau arrêtait
  la lecture sans message, et la suite disparaissait. Lecture durcie.
- **Quatre schémas** : `fait` (transactions, sommaires), `ref` (saisies manuelles : comptes et alias,
  libellé → nature, avis de cotisation, transferts), `pub` (sources publiques), `rapport` (vues lues par
  Power BI). Voir `sql/schema.sql`.
- **Sauvegarde chiffrée** : dump de la base et exports dans une archive AES-256 dont la liste des
  fichiers est chiffrée aussi, car les noms de fichiers d'export portent des numéros de compte. Le mot
  de passe n'est ni dans le script ni dans le dépôt.

## Itération 3 — Droits de cotisation : reconstruire, puis recouper

**Chaque règle est lue sur canada.ca et citée** ([regles-droits.md](regles-droits.md), R1 à R14).
Les pièges qui faussent un calcul naïf :

- un REER se suit par **année de déduction**, pas par année civile : une cotisation des 60 premiers
  jours peut se déduire pour l'année précédente ;
- un retrait CELI ne redonne des droits que le 1ᵉʳ janvier suivant : recotiser le montant retiré dans
  la même année crée un excédent invisible si la mesure rend les droits tout de suite ;
- l'excédent REER est toléré jusqu'à une marge fixée par l'ARC ; le CELI et le CELIAPP sont imposés dès
  le premier dollar ;
- CELIAPP : report des droits plafonné, plafond à vie, aucune période de 60 jours ;
- un transfert direct entre deux comptes du même régime n'est ni une cotisation ni un retrait.

**Reconstruire plutôt que recopier.** Partir du chiffre de l'ARC pour l'année en cours était plus
rapide, et c'était la recommandation de l'agent. Le responsable a choisi de reconstruire les droits
depuis l'ouverture des comptes : le chiffre de l'ARC devient un **contrôle indépendant** au lieu d'une
donnée d'entrée. Un écart résiduel désigne alors quelque chose de précis à chercher : une cotisation
faite hors des exports, un plafond mal saisi, un transfert pris pour une cotisation. D'où les saisies
« hors export », affichées comme telles dans le rapport.

**Où vit le calcul.** Droits et alertes sont des vues SQL ; le DAX se réduit à des sommes. Le calcul
reste lisible par l'évaluateur, il est recetté et rejoué chaque mois. Le témoin compte en cents
entiers : l'écart attendu est exactement nul. Il écrit la règle R3 autrement que la vue (droits
enchaînés d'une année sur l'autre, contre cumul des plafonds) : deux écritures qui doivent donner le
même chiffre.

**Livré** : PBIP dès le premier enregistrement, page 1 « Droits et versements », premier PDF. L'axe
d'analyse est la **société** : ce sont les sociétés qui sont en concurrence.

*Dans le jeu fictif* : année de départ du cumul CELI et avis REER fictifs (`ref.parametre`,
`ref.reer_avis`) ; un dépassement CELI en 2026 est provoqué exprès pour montrer l'alerte.

## Itération 4 — Patrimoine et rendement

- **TWR par la méthode de Dietz modifiée**, mois par mois, puis chaîné. L'export ne donne pas de fin
  de mois : le point de valorisation d'un compte est la dernière de ses dates de frais de gestion ou de
  sommaire dans le mois ([regles-performance.md](regles-performance.md), P1 à P9).
- **TWR d'un agrégat** = Dietz de l'agrégat (somme des numérateurs sur somme des dénominateurs), et non
  moyenne des taux des comptes.
- **TRI écarté** : il dépend du calendrier des versements de l'épargnant et pénaliserait une société
  pour une décision qui n'est pas la sienne.
- **Deux écritures pour la recette** : produit des (1 + r) dans le témoin, somme des logarithmes dans
  la vue SQL.
- **Cascade de l'année** : VM de début + versements − retraits − frais + distributions + variation de
  prix = VM de fin. La distribution est montrée à part : elle ne change pas la VM le jour du versement
  (le prix baisse, les parts augmentent), mais elle sépare le revenu du mouvement de prix.
- Choix de calcul : TWR et taux de frais chaînés en DAX pour suivre les segments ; les vues SQL servent
  de référence à la recette.

## Itération 5 — Stratégie par transparence

- **Source** : les profils mensuels publiés par les sociétés pour chaque fonds, qui donnent la
  répartition par classe d'actif, par pays ou région, et pour les portefeuilles la répartition par fonds
  sous-jacent. Dans la vE01, ces profils sont des tables `pub.profil*` produites par le générateur.
- **Contrainte qui dicte l'architecture** : un document publié à adresse fixe et remplacé chaque mois
  n'a pas d'historique en ligne. L'archive locale est le seul historique ; elle commence au premier
  téléchargement.
- **Extraction et contrôles bloquants** : texte extrait des PDF ; chaque section somme à 100 % ±
  1 point ; les sous-postes d'une classe somment à la classe ; tout pays, région ou fonds sous-jacent
  absent des tables de référence est refusé ; le mois le plus récent couvre tous les fonds détenus.
- **Transparence à un niveau**, sur trois axes : classe d'actif, géographie, style. Le style n'est pas
  publié : il est saisi à la main par fonds ([regles-strategie.md](regles-strategie.md), S1 à S6).
- **Coût de la stratégie** : RFG pondéré par la VM, plus le taux de frais de gestion du compte ;
  distance au seuil de 100 000 $ qui fait baisser les frais, par société.
- **Ce qui sort du poste** : le code public du fonds, dans l'adresse du document. Rien d'autre.

## Itération 6 — Fonds et risque

- **Dimension Fonds** : un même fonds peut exister sous plusieurs codes (options de frais
  d'acquisition), au même prix. Les codes se rattachent à un code pivot.
- **Type et niveau de risque lus dans les profils, jamais saisis** : une donnée publiée qui change
  doit changer dans le rapport sans intervention.
- **Indice de risque** = moyenne, pondérée par la VM, d'une échelle ordinale à cinq niveaux. Il est
  affiché comme un repère, pas comme une mesure de volatilité ; la part non cotée est montrée à côté.
- **Écart tactique** = répartition actuelle − répartition stratégique, par classe ; la somme des écarts
  d'un périmètre est nulle.
- **Premier cycle refusé par l'évaluateur** : le filtre de comptes ne s'appliquait pas partout, la VM
  détenue n'était pas recettée, le modèle livré n'avait pas été interrogé. Corrigé, accepté au second
  cycle.

## Itération 7a — Cours, risque mesuré, repères

**Étude de faisabilité avant le code.** Pour des cours quotidiens gratuits, plusieurs familles de
sources se comparent : API non officielles sans clé, bibliothèques qui les enveloppent, outils des
émetteurs (manuels), agrégateurs (historique payant ou extraction interdite), API officielles à forfait
gratuit (fonds communs souvent hors forfait). Critère décisif : **ne lire que la clôture non ajustée**.

- **Pourquoi pas le cours ajusté.** Le cours ajusté est calculé par la source à partir de ses propres
  distributions. Rapprochées des réinvestissements des exports, ces distributions peuvent être
  incomplètes ou fausses, et le cours ajusté hérite de leurs erreurs. Les distributions viennent donc
  des exports.
- **Trois façons de compter deux fois une distribution**, écrites pour ne pas y tomber : valoriser au
  cours ajusté des parts qui incluent déjà le réinvestissement ; ajouter les distributions à un gain
  qui les contient ; garder un réglage de bibliothèque qui remplace la clôture par le cours ajusté sans
  le dire (`auto_adjust=True` dans `yfinance`).
- **Fonds de masquage.** La liste interrogée contient aussi des fonds non détenus : les symboles
  demandés ne révèlent pas les fonds détenus.
- **Contrôles bloquants** : égalité avec les prix des exports aux dates communes, à 0,0001 $ près ; nom
  et devise attendus ; séance du jour écartée (cours provisoire) ; un repère sans cours à une date de
  prix d'un fonds détenu est refusé.
- **Repères** : les indices de référence sont payants. Le repère d'un fonds est un composite de
  substituts gratuits, rééquilibré chaque jour, et les écarts connus de chaque substitut sont notés à
  côté de la correspondance.
- **Hypothèse vérifiée par les données** : la date de réinvestissement est la date ex-distribution.
  Les jours de distribution, l'écart au repère redevient normal une fois la distribution ajoutée.
- **Fait affiché sur la page** : le rendement quotidien est avant frais du compte, le TWR après. Les
  frais sont prélevés par rachat de parts : ils réduisent les parts, pas le prix.
- Volatilité annualisée, pire baisse, écart au repère ; « historique insuffisant » sous 60 rendements
  ([regles-performance.md](regles-performance.md), P10 à P16).

*Dans la vE01* : cours et repères synthétiques (symboles `SYN-…`), tirés par le générateur ; aucun
cours réel, aucun FNB réel.

## Itération 7b — Rapports annuels de la direction

Les rapports annuels de la direction sur le rendement des fonds (RDRF) donnent, sur cinq exercices :
distributions par nature, RFG avant et après abandons, ratio des frais d'opérations (RFO), taux de
rotation.

- **Cas d'extraction que le lecteur traite** : un tableau par série de parts, d'où la nécessité de
  lire la bonne ; un tableau unique sans libellé de série ; une valeur « s.o. » ; un nombre coupé par
  l'extraction du texte (« 37 ,34 »).
- **Contrôles bloquants (S14)** : somme des natures égale au total imprimé, à l'arrondi près ; RFG au
  plus égal au RFG avant abandons ; nom lu égal au nom du profil mensuel ; exercice clos à la date
  attendue.
- **Cache du texte extrait**, indexé par l'empreinte SHA-256 du PDF et la version de la bibliothèque
  d'extraction : la réextraction de tous les documents archivés dominait la durée de la routine. Un PDF
  remplacé, ou une nouvelle version de la bibliothèque, réextrait.

*Dans la vE01* : `pub.rapport_annuel` est produite par le générateur.

## Itération 8 — Publication

- **Date d'arrêté** au lieu de `TODAY()` : la plus ancienne des dates de fin des derniers relevés
  chargés. Le PDF ne dépend plus du jour où on l'imprime, et un compte en retard retarde tout le
  rapport au lieu de fausser un total. Le segment Année se règle sur « En cours » et change d'année
  seul en janvier.
- **Hypothèse levée par la documentation** : un abonnement de Power BI Service ne peut pas viser des
  destinataires externes avec une licence Pro seule (capacité Premium payante exigée). Envoi manuel
  retenu : export PDF de la page active, routine écrite pas à pas.
- **Disposition mobile générée par script** : un `mobile.json` par visuel, déduit de la page de bureau
  en une colonne. Le rail de navigation est lui aussi régénéré par script.
- **Mise en page outillée** : un skill dédié produit le plan coté, la maquette et le contrôle de
  grille, puis écrit le PBIR en préservant les retouches faites dans Desktop. Règle constante : le
  modèle et le PBIR se modifient Desktop fermé, et une retouche manuelle du responsable ne s'annule
  jamais.
- **Audit du modèle** : mesures sans visuel ni dépendance supprimées. Une vue recalculée par jointure
  plutôt que ligne à ligne fait passer l'actualisation de 12 s à 0,4 s, à résultat égal.
- **Compte sans export** : le schéma accepte aussi un relevé saisi à la main, contrôlé par chaînage des
  soldes au cent (règle P17). La saisie minimale d'un mois tient en deux lignes : les cotisations et le
  solde de fin de mois. *Le jeu fictif n'exerce pas ce cas.*

## Des données fictives qui tiennent debout

**Pourquoi un générateur plutôt qu'un masquage.** Masquer des noms et des montants garde la structure :
dates d'ouverture, rythmes de versement, répartition entre sociétés. Une structure suffit à reconnaître
une personne. Un jeu publiable doit donc être produit, pas maquillé.

**Pourquoi le désordre ne s'écrit pas à la main.** Un premier jeu fictif, écrit à partir de listes, a
été rejeté : trop régulier, trop propre. Un modèle de langage produit spontanément des montants ronds,
des calendriers symétriques, des progressions lisses.

**Le générateur** ([`../Generateur-data-fictive/`](../Generateur-data-fictive/)), écrit sur cahier des
charges :

- des paramètres de stratégie par société, puis des événements tirés de distributions à graine fixe ;
  rien n'est écrit à la main au niveau des versements ;
- aucun fonds, indice ou FNB réel comme gabarit ; plafonds fiscaux lus dans `sql/plafonds.sql`, seule
  source ;
- toute la chaîne se rejoue à l'identique, octet pour octet ;
- sept jalons contractualisés (J1 à J7), publiés avec leurs preuves.

**Recette** : les vues `rapport.*` alimentées par le jeu fictif sont comparées à l'oracle du
générateur, qui calcule indépendamment les mêmes grandeurs.

**Balayage de fuite** : avant chaque publication, une recherche de motifs sensibles couvre le code, les
documents, les données et les partitions figées du modèle (décompressées avant la recherche). Les
motifs sont lus à l'exécution dans des listes conservées hors du dépôt, et la sortie n'imprime que des
nombres d'occurrences.

**Rapport figé** : chaque table est embarquée dans le modèle ; aucune base n'est requise pour l'ouvrir.

## Ce qui a été écarté

| Option | Raison |
|---|---|
| Stockage sur VPS | Ajoute un hôte exposé sans retirer le poste du risque |
| Page web sur le VPS pour le mobile | Données sensibles sur un hôte exposé ; l'application Power BI suffit |
| Orchestration n8n, modèle dbt | Aucun gain à ce volume ; tout reste sur le poste |
| TRI (XIRR) | Dépend du calendrier des versements de l'épargnant, pas de la gestion |
| Cours ajustés et distributions d'une source gratuite | Non fiables au rapprochement ; les exports font foi |
| DirectQuery, passerelle | Exports déposés à la main : une actualisation planifiée n'apporte rien, et publier après relecture évite des chiffres non recettés |
| Masquage de données réelles | La structure reste reconnaissable ; un générateur à graine la remplace |

## Leçons

1. **Lire les exports avant de concevoir.** L'itération sans code repère les pertes irréversibles,
   comme une valeur marchande que le portail ne régénère pas.
2. **Reconstruire, puis recouper.** Un chiffre officiel recopié ne contrôle rien ; reconstruit à côté,
   il révèle ce qui manque.
3. **Une règle fiscale non sourcée est une erreur différée.** Chaque plafond porte sa page canada.ca.
4. **Le contrat de jalon refuse ce qui « marche à l'écran ».** Un livrable visuellement correct peut
   échouer sur un filtre ou une recette manquants.
5. **La confidentialité se conçoit.** Archive chiffrée, fonds de masquage, preuves sans montant,
   générateur à graine, balayage de fuite : chaque sortie du poste est nommée et justifiée.
