# Règles de valorisation et de performance appliquées

Une ligne par règle appliquée par les vues de performance de `sql/vues.sql`, où chaque identifiant
est cité en commentaire. Ces règles sont des conventions de calcul, sans source externe ; chacune a
été validée par le responsable avec le contrat de l'itération qui l'a introduite (P1 à P9 : itération 4 ;
P10 à P16 : itération 7a ; P17 : itération 8). Dans ce dépôt, elles s'appliquent au jeu fictif.

## Règles

| # | Règle | Effet dans les vues |
|---|---|---|
| P1 | Point de valorisation d'un compte pour un mois : la dernière de ses dates de frais de gestion et de sommaire dans ce mois. Si le sommaire et les frais tombent le même jour, le sommaire l'emporte. Un seul point par mois | `rapport.point` : une ligne par compte et par mois |
| P2 | Valeur marchande au point. Point de frais : Σ parts restantes × prix de la dernière transaction de chaque fonds à cette date, arrondi au cent par fonds. Point de sommaire : valeur marchande du sommaire. Un fonds détenu dont le prix a plus de 31 jours est signalé | `rapport.valorisation` : compte × fonds × point, avec la date du prix |
| P3 | Flux externes : achats PAC et ponctuels au montant brut (entrée) et retraits au montant brut (sortie), transferts entre institutions compris. Les distributions réinvesties, les frais et les échanges entre fonds sont internes : ils font partie du rendement | Colonnes `versements`, `retraits` et `flux` de `rapport.performance` |
| P4 | Capital net : cumul des flux externes depuis l'ouverture, pour les seuls comptes qui ont un export ou un relevé saisi (P17). Les saisies hors export d'un compte sans valeur marchande en sont exclues | Colonne `capital_net` de `rapport.performance` |
| P5 | Gain net = valeur marchande − capital net, au point | Colonne `gain_net` de `rapport.performance` |
| P6 | Rendement du mois (Dietz modifié) : r = (VM fin − VM début − F) ÷ (VM début + Σ wᵢ·Fᵢ). La sous-période va du point du mois précédent (exclu) au point du mois (inclus) ; wᵢ = (fin − date du flux) ÷ (fin − début), en jours. Premier mois d'un compte : VM début = 0, début = veille de la première transaction. Dénominateur nul : rendement vide | Colonnes `numerateur`, `denominateur` et `rendement` de `rapport.performance` |
| P7 | TWR de l'année : produit des (1 + r) des mois de l'année, moins 1. La première sous-période part du dernier point de l'année précédente : l'année va de point de frais à point de frais | `rapport.rendement_annuel` ; mesure DAX `TWR` |
| P8 | TWR global : pour chaque mois, Σ numérateurs ÷ Σ dénominateurs des comptes (Dietz de l'agrégat, et non moyenne des taux), puis chaînage comme en P7. Les points des comptes d'un même mois peuvent différer de quelques jours | `rapport.performance_globale`, ligne `compte_alias` vide de `rapport.rendement_annuel` ; la même mesure `TWR` suit tout filtre de comptes |
| P9 | Frais : montant brut des lignes « Frais de gestion » (taxes incluses), plus les déductions sur achats. Taux annualisé = frais de l'année ÷ moyenne des VM aux points de l'année × 12 ÷ nombre de points | Colonne `frais` de `rapport.performance`, `taux_frais` de `rapport.rendement_annuel` ; mesure `Taux de frais annualisé` |
| P17 | Compte à relevé saisi à la main (institution sans export). Une sous-période par période du relevé, de la veille du solde d'ouverture (exclue) au gain qui la clôt (inclus), rattachée au mois de sa fin ; VM début = solde d'ouverture, VM fin = ouverture + cotisations + gain. Flux = cotisations (PAC), au poids de P6. Frais et distributions : 0, car compris dans le gain du fonds ; le taux de frais du global en est dilué. Une période de deux mois laisse le mois intermédiaire sans VM. Hors repère (P16) et hors stratégie, faute de composition du fonds | Branche `releve` de `rapport.performance` ; le lecteur du relevé contrôle le chaînage des soldes au cent. Le jeu fictif n'exerce pas ce cas |

## Risque mesuré et performance comparée

### Points de lecture

- **Date de réinvestissement = date ex-distribution** (hypothèse vérifiée sur les données : les jours de
  distribution, l'écart entre le fonds et son repère ne redevient normal qu'une fois la distribution ajoutée).
- **Rendement quotidien avant frais du compte, TWR après.** Les frais de gestion du compte sont prélevés
  en rachetant des parts : ils réduisent le nombre de parts, pas le prix. Ils ne figurent donc pas dans
  le rendement quotidien (P11, P12), mais dans le TWR (P6, P9). Sur une année, l'écart entre le TWR
  global et le rendement quotidien chaîné est du même ordre que le taux de frais annualisé (P9), plus un
  effet de bornes : le TWR va de point à point, l'année civile du 1ᵉʳ janvier au 31 décembre. Les écarts
  au repère de P15 comparent donc les fonds avant frais du compte ; P16 compare le portefeuille après.

### Règles

| # | Règle | Effet dans les vues |
|---|---|---|
| P10 | Prix quotidien d'un fonds : clôture non ajustée de la source publique. À une date sans cours public, le prix des exports. Une date sans aucun prix n'a pas de ligne : le rendement suivant couvre les deux jours. La clôture ajustée d'un fonds n'est jamais lue : elle dépend des distributions de la source, qui peuvent être fausses ou manquantes. vE01 : clôtures synthétiques (`SYN-…`) | `rapport.prix_quotidien` (colonne `source`) |
| P11 | Rendement total quotidien d'un fonds : r = (P + D) ÷ P de la veille − 1, entre deux dates de prix consécutives. D = distribution par part à la date de réinvestissement = Σ montants réinvestis ÷ Σ parts détenues à la clôture de la veille, tous comptes et options confondus. Un fonds n'a de rendement que les jours où il était détenu la veille | `rapport.distribution`, `rapport.rendement_fonds` |
| P12 | Rendement quotidien d'un périmètre (compte, régime, global, fonds, ou tout filtre) : Σ VM(veille) × r ÷ Σ VM(veille). VM(veille) = parts à la clôture de la veille × prix de la veille, sans arrondi, car c'est un poids. Les flux externes n'entrent pas dans le rendement, et les corrélations entre fonds sont comprises. Le repère quotidien du périmètre se pondère de la même façon | `rapport.parts`, `rapport.rendement_quotidien`, `rapport.rendement_perimetre` ; mesure `Rendement du jour` |
| P13 | Volatilité : écart-type d'échantillon des rendements quotidiens × √252. Deux fenêtres : depuis le début, et 12 mois glissants jusqu'à la dernière date de rendement. Sous 60 rendements : vide, affiché « historique insuffisant » | `rapport.risque_mesure` (`volatilite`) ; mesures `Volatilité …` |
| P14 | Pire baisse : plus forte chute entre un sommet et le creux qui suit, sur l'indice cumulé Π(1 + r) de la fenêtre. La valeur de départ (1) compte comme sommet, datée de la veille du premier rendement. Sans baisse : 0, sans dates. À égalité, le premier creux | `rapport.risque_mesure` (`pire_baisse`, `date_sommet`, `date_creux`) ; mesures `Pire baisse …` |
| P15 | Repère d'un fonds : composite pondéré (`ref.repere`). Le composite est rééquilibré chaque jour : r = Σ poids × variation de la composante entre les deux dates du fonds (dernier cours connu à chaque date). Rendement d'une fenêtre : (Π(1 + r))^(252 ÷ n) − 1 si n ≥ 252, sinon cumulé. Écart = rendement du périmètre − rendement du repère, sur les mêmes dates. Chaîne d'exploitation : chaque indice du repère publié dans le rapport annuel du fonds est remplacé par un substitut gratuit, sur sa clôture ajustée, écarts connus notés. vE01 : repères synthétiques de catégorie | `rapport.repere_quotidien`, `rapport.risque_mesure` (`rendement`, `rendement_repere`, `ecart`, `annualise`) |
| P16 | Repère du portefeuille sur les sous-périodes du TWR (P1, P6). Pour chaque compte, chaque mois et chaque fonds : poids = VM du fonds au point de début, ou au point de fin pour un mois sans VM de début (premier mois). Rendement = Π(1 + repère quotidien du fonds) sur ]début, fin] − 1. Repère d'un périmètre pour un mois = Σ poids × rendement ÷ Σ poids, chaîné comme le TWR. Écart = TWR − repère | `rapport.repere_mensuel` ; mesures `Repère TWR`, `Écart au repère TWR` |

## Cascade de l'année

Elle n'introduit pas de nouvelle règle : elle décompose la variation de VM avec P2, P3 et P9.

VM au dernier point de l'année précédente + versements − retraits − frais + distributions + variation
de prix = VM au dernier point de l'année.

La variation de prix est le terme qui ferme l'égalité : elle regroupe la hausse et la baisse des prix
des parts. Une distribution ne change pas la VM le jour où elle est versée (le prix baisse, les parts
augmentent) : la montrer à part sépare le revenu distribué du mouvement de prix. Vue : `rapport.cascade`.
