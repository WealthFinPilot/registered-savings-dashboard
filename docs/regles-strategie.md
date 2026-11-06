# Règles de stratégie appliquées

Une ligne par règle appliquée par les vues de stratégie de `sql/vues.sql`, où chaque identifiant est
cité en commentaire. Source de la composition dans la chaîne d'exploitation : les profils mensuels
publics des fonds (PDF), archivés et extraits par le pipeline ; dans la vE01, les tables `pub.profil*`
produites par le générateur. Ces règles sont des conventions de calcul, validées par le responsable
avec le contrat de leur itération (S1 à S6 : itération 5 ; S7 à S10 : itération 6 ; S11 à S14 :
itération 7b).

## Règles

| # | Règle | Effet dans les vues |
|---|---|---|
| S1 | Profil applicable à un fonds, à un point de valorisation (P1) : le dernier profil archivé dont la date de données précède ou égale le point | `rapport.valorisation_profil`, colonne `date_profil` |
| S2 | Transparence : exposition (compte, point, axe, catégorie) = Σ VM du fonds au point (P2) × poids du fonds dans la catégorie. Un seul niveau : les profils des portefeuilles agrègent déjà leurs sous-jacents. Poids ramenés à 100 % par fonds et par axe, pour que la somme d'un axe égale la VM. Fonds détenu sans profil : « Non ventilé » (« Trésorerie et non ventilé » en géographie) | `rapport.composition` (normalisation), `rapport.exposition` |
| S3 | Classes d'actif : Actions, Revenu fixe, Alternatifs, Trésorerie. Fonds de marché monétaire : 100 % Trésorerie. Portefeuilles : lignes de classe de la répartition actuelle, jamais la cible. Fonds d'actions : répartition de l'actif ; à défaut, la ligne de trésorerie de la répartition sectorielle, le reste en actions | `rapport.composition`, axe « Classe d'actif » |
| S4 | Géographie : Canada, États-Unis, Autres pays, Trésorerie et non ventilé, par `ref.geographie`. Fonds dont la répartition de l'actif détaille les actions par pays : ces sous-postes, plus la trésorerie. Sinon : la répartition par pays ou par région, étalée sur la part hors trésorerie (S3), la trésorerie allant à « Trésorerie et non ventilé ». « Amérique du Nord » va à « Trésorerie et non ventilé » : la publication ne permet pas de la partager | `rapport.composition`, axe « Géographie » |
| S5 | Style : Dividendes, Croissance, Mixte, Revenu fixe, Alternatifs, Trésorerie, par `ref.style` (classement saisi à la main : aucune source publique ne donne le style). Portefeuilles : chaque fonds sous-jacent de la répartition actuelle prend son style. Autres fonds : classes S3, la part en actions prenant le style du fonds | `rapport.composition`, axe « Style » |
| S6 | Coût de la stratégie au dernier point : RFG pondéré par la VM couverte par un profil, plus le taux de frais de gestion de l'année du dernier point (P9). Tranche de frais de gestion : actif agrégé à moins ou plus de 100 000 $ ; distance au seuil = max(0 ; 100 000 $ − actif agrégé). Un seuil **par société**, chacune ayant sa propre grille de frais | `rapport.cout`, `rapport.cout_perimetre`, `rapport.seuil` |
| S7 | Fonds : une ligne par code pivot (`ref.fonds.code_fa`) ; les autres codes du même fonds s'y rattachent par `pub.profil_code`, un fonds détenu sans profil garde son propre code. Attributs stables saisis à la main : nom court, profil ordinal (Épargne 1, Revenu 2, Conservateur 3, Modéré 4, Croissance 5, Actions 6), mandat déclaré. Type de fonds et niveau de risque : lus dans le profil, jamais saisis | `rapport.fonds`, colonne `cle_fonds` de `rapport.valorisation_profil`, colonne `code_fa` de `rapport.exposition`, `rapport.detention` et `rapport.ecart` |
| S8 | Profil de risque : rang du niveau publié du profil applicable (S1) par `ref.risque` (Faible 1, Faible-Moyen 2, Moyen 3, Moyen-Élevé 4, Élevé 5). Répartition de la VM par niveau, la somme égalant la VM ; fonds sans profil : « Non coté ». Indice = Σ VM × rang ÷ Σ VM cotée, la part non cotée étant affichée. Moyenne d'une échelle ordinale : un repère, pas une mesure de volatilité | `rapport.niveau_risque`, `rapport.detention` (`vm_rang`, `vm_cotee`) |
| S9 | Répartition stratégique : section « cible » du profil applicable, ramenée aux classes de S3 et à 100 % ; sans cible, 100 % dans la classe du type (Actions → Actions, marché monétaire → Trésorerie). Un profil sans cible d'un autre type est refusé à l'extraction. Pondération par la VM, comme S2 ; fonds sans profil : « Non ventilé » | `rapport.cible`, `rapport.ecart` (`strategique`) |
| S10 | Écart tactique = répartition actuelle (S3) − répartition stratégique (S9), par classe, en points de VM ; la somme des écarts d'un périmètre est nulle | `rapport.ecart` (`actuel`, `ecart`) |
| S11 | Dernier exercice publié d'un fonds : l'exercice clos le 30 septembre le plus récent parmi les rapports annuels de la direction sur le rendement (RDRF) archivés ; tableau de la série détenue, ou tableau unique sans libellé de série | `rapport.rapport_fonds` (`exercice`) |
| S12 | Nature des distributions d'un fonds : part de chaque nature (revenus hors dividendes, dividendes, gains en capital, remboursement de capital) = distribution par part de la nature ÷ somme des quatre natures imprimées, sur le dernier exercice (S11) ; les parts somment à 100 %. Exercice sans distribution : quatre parts vides. Composition publique par part du fonds, pas un feuillet fiscal | `rapport.rapport_fonds` (`part_*`, `distribue`) |
| S13 | RFO, taux de rotation et parts par nature pondérés : Σ VM du fonds au dernier point × valeur ÷ Σ VM des fonds qui ont cette valeur (pondération de S6). Nature : seuls les fonds qui ont distribué sur leur dernier exercice. Rotation « s.o. » : fonds exclu. Part de la VM sans RDRF affichée à côté | `rapport.detention_rapport`, `rapport.rapport_perimetre` |
| S14 | Contrôles d'un RDRF, bloquants (rien n'est écrit) : \|somme des natures − total imprimé\| ≤ 0,01 $ × nombre de natures non nulles (arrondi au cent de chaque ligne) ; RFG ≤ RFG avant abandons ; nom lu égal au nom du profil mensuel du même code ; dernier exercice clos un 30 septembre ; RDRF archivé pour chaque fonds détenu | Extraction des RDRF ; `pub.rapport_annuel` |

## Contrôles de l'extraction des profils (chaîne d'exploitation)

Bloquants, rien n'est écrit en cas d'écart : chaque section d'un profil somme à 100 % ± 1 point ; les
sous-postes d'une classe somment à la classe ± 1 point ; un profil sans répartition par classe ou sans
géographie est refusé ; tout fonds sous-jacent, pays ou région absent des tables de référence est
refusé ; le mois le plus récent couvre tous les fonds détenus, à une seule date de données ; chaque code
détenu se rattache à une ligne de la table des fonds ; chaque niveau de risque publié figure dans la
table des risques ; un profil sans répartition cible a un type à classe unique (S9).

## Contrôles de l'extraction des RDRF (chaîne d'exploitation)

Ceux de S14, sur chaque exercice extrait. Cas traités par le lecteur : un tableau par série de parts ;
un fonds qui n'a qu'un tableau sans libellé de série ; une rotation « s.o. » ; des nombres coupés par
l'extraction du texte (« 37 ,34 ») . Un fonds de masquage, interrogé
sans être détenu pour ne pas révéler les fonds détenus, n'a pas de profil mensuel : son nom n'est pas contrôlé. Un repère sans cours à une date de prix d'un
fonds détenu est refusé (P15).
