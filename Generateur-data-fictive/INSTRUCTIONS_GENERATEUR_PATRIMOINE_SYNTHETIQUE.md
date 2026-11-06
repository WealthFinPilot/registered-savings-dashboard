# Cahier des charges — Générateur de patrimoine financier synthétique

> **Destinataire :** agent de développement (Claude Code ou équivalent)  
> **Mission :** concevoir, implémenter, tester et documenter un générateur de données financières **entièrement fictives**, mais économiquement, comportementalement et comptablement cohérentes, pour éprouver un tableau de bord Power BI de gestion patrimoniale.  
> **Nature du document :** spécification d'objectifs et de garde-fous. Les exemples chiffrés donnent des ordres de grandeur, **pas** un scénario à recopier.

## 0. Instruction fondamentale à l'agent

Ne génère **pas** une série de lignes inventées manuellement par un LLM. Conçois **un moteur de simulation exécutable** et reproductible, où les chiffres proviennent de modèles probabilistes, d'événements et d'une comptabilité déterministe.

Le réalisme recherché ne correspond ni à une distribution uniforme ni à du hasard sans contraintes : il résulte de **contraintes financières strictes + comportements humains imparfaits + processus de marché corrélés + événements rares**.

**Ne cherche surtout pas à fabriquer une stratégie gagnante.** Un scénario peut sous-performer, surperformer temporairement, subir une perte ou connaître une longue stagnation. La cohérence est obligatoire ; la performance ne l'est pas.

Traite tout résultat comme **SYNTHÉTIQUE / NON RÉEL / NON CONSTITUTIF D'UN CONSEIL FINANCIER**. N'utilise aucune donnée patrimoniale personnelle, aucun compte véritable, aucun identifiant réel et aucune connexion aux systèmes financiers de production.

### Ordre de travail

1. Inspecter le schéma et les besoins du projet **sans ouvrir ni ingérer de véritables données financières confidentielles**. Se limiter au code, aux modèles de données, aux contrats d'import et aux exemples déjà anonymisés.
2. Établir un contrat de données : quelles tables, colonnes, clés et conventions le dashboard attend-il ? Si le contrat ne peut pas être déduit sans consulter des données sensibles, produire un schéma autonome et un adaptateur documenté.
3. Construire le moteur et les tests en environnement isolé.
4. Générer plusieurs scénarios reproductibles, sélectionner **un scénario par seed préalablement choisie** (pas par qualité du rendement), puis valider et exporter.
5. Remettre les fichiers, un rapport de qualité et les commandes pour reproduire le jeu de données.

Ne remplace jamais automatiquement les fichiers ou tables de production du tableau de bord. Le jeu synthétique doit être activable séparément (mode `synthetic` / dossier d'export dédié).

---

## 1. Résultat recherché

Simuler environ **60 mois** d'une histoire patrimoniale plausible, en dollars canadiens, dans laquelle une personne épargne, investit, change progressivement ses décisions et détient des placements auprès de **trois institutions distinctes**.

L'histoire finale doit permettre au tableau de bord de montrer :

- L'évolution du patrimoine financier et sa ventilation par institution, régime fiscal, sous-compte et fonds.
- Les versements réguliers (**PAC** : plan d'achat/cotisation périodique), versements exceptionnels, retraits et frais.
- Les expositions réelles (actions, obligations, liquidités ; régions ; styles ; devises si pertinent) et le risque, en tenant compte des fonds détenus **et de leurs poids effectifs dans le portefeuille**.
- Les rendements fond par fond et consolidés, dont **TWR** (time-weighted return) et, idéalement, **MWR/XIRR** (money-weighted return).
- Une comparaison équitable avec une stratégie passive de référence, **alimentée par les mêmes flux externes et aux mêmes dates**, sans biaiser les résultats.
- De vraies irrégularités : changements de rythme d'épargne, comptes ouverts en cours de route, périodes sans versement, déplacements d'allocations, frais hétérogènes et marchés parfois défavorables.

### Périmètre indicatif initial

| Dimension | Cible | Souplesse attendue |
|---|---|---|
| Horizon | 5 ans / ~60 mois | Dates paramétrables ; jours ouvrables pour la valorisation |
| Institutions | Exactement 3 | Trois offres et trois profils d'investissement distincts |
| Régimes fiscaux | CELI, CELIAPP, REER, COMP | `COMP` = compte non enregistré ; règles fiscales configurables |
| Sous-régimes/comptes | `CELI1`, `CELI2`, `REER1`, etc. | Plusieurs comptes du même régime, sans multiplication artificielle |
| Produits | Environ 15 fonds/FNB | 12 à 18 possibles via configuration ; produits rattachés à une institution |
| Mouvements externes/charges | `PAC`, `PONCTUEL`, `RETRAIT`, `FRAIS` | Distinguer des achats/ventes internes |
| Épargne récurrente | Ordre de grandeur : 500 à 1 000 CAD/mois **au total** | Avec périodes d'ajustement et exceptions plausibles |
| Versements exceptionnels | Occasionnels, généralement modestes | Échelle configurable, rarement importants |
| Retraits | Occasionnels ; **jamais de REER** dans ce scénario | Retraits couverts par la trésorerie/ventes ; traitement CELIAPP spécifique |

Ces chiffres sont des points de départ. **Ne force pas** systématiquement les allocations à une proportion précise ni les comportements à des fréquences identiques.

## 2. Architecture imposée : cinq moteurs indépendants

Séparer le générateur en composants testables, plutôt que mélanger toute la logique dans un script unique.

```text
CONFIGURATION + SEED
        │
        ├─ A. Univers de placement : institutions, comptes, fonds, expositions, frais
        │
        ├─ B. Marchés : facteurs macro/actifs, corrélations, volatilité, chocs, NAV
        │
        ├─ C. Épargnant : PAC, événements, arbitrages, retraits, changement de préférences
        │
        ├─ D. Grand livre : flux, ordres, unités, cash, frais, positions, valorisations
        │
        └─ E. Mesures et contrôles : TWR, MWR, exposition, références, réconciliation
        │
        ▼
EXPORTS NORMALISÉS + RAPPORT DE VALIDATION + PARAMÈTRES DE REPRODUCTION
```

**Principes de séparation :**

- Le moteur **marché** produit les prix **sans connaître** les versements et retraits de l'investisseur.
- Le moteur **comportement** ne voit que les informations disponibles **à la date de décision**, jamais les prix futurs.
- Le **grand livre** est la seule source de vérité pour les unités détenues, l'encaisse et les flux.
- Les tables Power BI sont **dérivées du grand livre**, pas calculées indépendamment les unes des autres.
- Les indicateurs de performance et les références sont calculés **après** la simulation, avec une méthodologie documentée.

Utiliser des flux pseudoaléatoires indépendants, par exemple `numpy.random.SeedSequence(seed).spawn(...)` pour `univers`, `marchés`, `comportements` et `événements`. Toute exécution avec la même configuration et la même seed doit donner exactement les mêmes données (dans un environnement logiciel fixé).

## 3. Univers financier plausible, sans proportions trop parfaites

### 3.1 Institutions et profils

Créer **3 institutions fictives** avec des catalogues partiellement distincts. Les noms peuvent être neutres (`Société A/B/C`) ; ils ne doivent pas ressembler à des comptes réels.

L'investisseur choisit chaque institution pour une raison vraisemblable : héritage de produits, frais, expérience, simplicité de gestion ou changement de stratégie.

Les trois approches doivent être **différentes, mais pas caricaturales** :

- Une institution à profil relativement prudent : davantage d'obligations et de fonds diversifiés.
- Une institution à profil intermédiaire : portefeuille équilibré/mondial.
- Une institution plus dynamique : davantage d'actions, parfois une concentration géographique ou sectorielle.

**Attention :** « prudent / intermédiaire / dynamique » sont des intentions de départ. Le risque réel se calcule à partir des positions, de leurs expositions et de leur volatilité/corrélation ; il ne doit pas être artificiellement égal à une étiquette.

Répartir les montants par institution avec une loi de pondération non uniforme (p. ex. *logistic-normal* ou Dirichlet avec concentrations asymétriques), influencée par les dates d'ouverture et la stratégie. Une institution peut représenter une part plus importante que les deux autres ; **ne jamais fixer 33/33/34 par défaut**. Éviter également les extrêmes absurdes ou les comptes entièrement vides, sauf scénario explicitement configuré.

Il peut exister des écarts entre **allocation cible** et **allocation effective** : les marchés et les versements les font dériver ; l'investisseur ne rééquilibre pas quotidiennement.

### 3.2 Régimes et sous-comptes

Inclure les quatre familles : `CELI`, `CELIAPP`, `REER`, `COMP`.

Chaque compte doit avoir un identifiant stable, un régime parent, un alias lisible (`CELI1`, `CELI2`, `REER1`…), une institution, une date d'ouverture et, éventuellement, une date de fermeture. `CELI1` et `CELI2` représentent des **comptes** d'une même famille fiscale, pas de nouvelles catégories légales.

Répartir les montants et les cotisations **de façon asymétrique**. Dans le scénario par défaut, le patrimoine et/ou les nouveaux versements peuvent privilégier les CELI, mais les autres régimes doivent rester crédibles. Le régime le plus alimenté peut changer au fil du temps.

Ne pas ouvrir un CELIAPP avant l'existence de ce régime au Canada (2023). Ne pas inventer une conformité fiscale : les plafonds de droits de cotisation au CELI, REER et CELIAPP dépendent de la situation individuelle et des règles applicables. **Deux modes sont permis** :

1. `fiscal_mode: conservative_synthetic` : plafonds de contribution **paramétrés explicitement** par année et par régime pour le personnage fictif, report des droits selon les règles implémentées, garde-fous, sans prétendre certifier l'admissibilité fiscale réelle.
2. `fiscal_mode: accounting_only` : mouvements et encours cohérents, avec **avertissement visible** « conformité fiscale non simulée ».

Par défaut, privilégier le premier **seulement si les règles et paramètres sont fiabilisés** ; sinon utiliser le second. Les retraits du CELIAPP doivent être **interdits par défaut**, sauf si l'on implémente explicitement un événement admissible et son traitement réglementaire. **Ne générer aucun retrait de REER**, règle absolue de ce scénario. Éviter les transferts interrégimes non modélisés fiscalement.

### 3.3 Fonds, expositions et frais

Créer ~15 fonds synthétiques répartis entre institutions (par exemple 4–6 produits chacune), avec des identifiants inventés et des caractéristiques distinctes. Les fonds sont des véhicules, pas des copies de FNB existants.

Pour chacun :

- `fund_id`, `institution_id`, `fund_name`, `currency`, `inception_date`, `risk_profile_hint` ;
- allocation **actions / obligations / liquidités / autres** en % ;
- géographie économique **Canada / États-Unis / Europe / Asie-Pacifique / émergents / autres**, en % ;
- style indicatif (`large_cap`, `value`, `growth`, `quality`, `dividend`, `broad_market`, `fixed_income`, etc.) ;
- concentration, sensibilité aux taux, exposition aux changes, volatilité attendue, frais de gestion ;
- conditions de disponibilité par institution et, si nécessaire, par régime.

**Ne pas confondre les axes.** La géographie et la catégorie d'actifs peuvent avoir chacune leur distribution à 100 % ; on ne doit pas additionner leurs colonnes comme s'il s'agissait du même axe. Pour des expositions de qualité supérieure, préférer une table `fund_exposures` à granularité `fund × asset_class × geography × style` avec des poids consolidables, et créer des vues agrégées par axe.

Créer des corrélations plausibles : deux fonds d'actions mondiales se ressemblent davantage qu'un fonds d'obligations court terme et un fonds d'actions émergentes. Éviter quinze trajectoires indépendantes, mais aussi quinze copies d'un même graphique.

Les frais intégrés à la **valeur liquidative synthétique** d'un fonds (MER/RFG simulé) ne doivent **pas** être facturés une seconde fois dans `FRAIS`. Les mouvements `FRAIS` servent aux frais de compte, plateforme, transaction ou conseil **distincts** des frais déjà déduits de la valeur liquidative.

## 4. Marchés : du désordre structuré, non du bruit blanc

Le moteur de prix doit être suffisamment réaliste pour tester les indicateurs, mais clairement présenté comme une **simulation**, non comme l'historique véritable des marchés.

### Mécanisme conseillé

Modèle multifactoriel, à pas **journalier ouvrable**, avec régimes économiques latents et volatilité variable :

\[
r_{i,t} = \alpha_i + \sum_{k} \beta_{i,k,t} f_{k,t} + \epsilon_{i,t} + J_{i,t}
\]

Où les facteurs peuvent représenter : actions mondiales, actions du Canada, taux/obligations, crédit, style croissance/valeur, devises. Les `beta` sont stables à court terme mais peuvent évoluer lentement. Les facteurs subissent des changements de régime (expansion, ralentissement, crise, reprise) **non calés sur des dates historiques obligatoires**.

Ajouter :

- Volatilité regroupée dans le temps (*volatility clustering*) ;
- Corrélations imparfaites et éventuellement changeantes ;
- Chocs rares, positifs **et** négatifs, avec sévérité et persistance variables ;
- Rendements non gaussiens si possible (queues épaisses, Student-t ou mélange de distributions) ;
- Expositions en devises avec conversion CAD cohérente, **si** cette complexité est activée ; sinon, fonds exclusivement valorisés en CAD et convention documentée.

Utiliser une construction mathématique valide pour les covariances (matrice positive semi-définie). Calculer les prix via des rendements logarithmiques ou un modèle qui garantit des prix strictement positifs. Autoriser des replis substantiels ; **ne pas plafonner mécaniquement toutes les pertes à un seuil confortable**. Une trajectoire invraisemblable doit être diagnostiquée, pas lissée silencieusement.

Le moteur génère une série de prix / VL **indépendamment du portefeuille**, que celui-ci détienne ou non les fonds à ce moment-là.

**Garde-fous anti-faux réalisme :** ne pas fabriquer une croissance régulière à +7 % chaque année ; ne pas imposer une année baissière à une date fixe ; ne pas forcer le portefeuille à battre le benchmark ; ne pas copier les valeurs de fonds réels sans source et sans annonce de cette dépendance.

### Dividendes et distributions

Pour le MVP, utiliser des **prix en rendement total**, distributions réinvesties implicitement. Ne pas ajouter ensuite des dividendes en espèces : cela compterait deux fois les rendements. Une version avancée peut introduire `cash_dividend` et des prix hors distributions, **avec une définition entièrement cohérente** des rendements totaux et du réinvestissement.

## 5. Comportement de l'épargnant : créer une vie financière plausible

Le générateur doit simuler des **décisions**, pas seulement tirer des montants aléatoires chaque mois.

### 5.1 PAC : trajectoire d'épargne

Pour le scénario de base, viser une capacité d'épargne régulière de l'ordre de **500–1 000 CAD/mois, globalement sur le portefeuille**, non par compte. Elle peut évoluer selon le temps et connaître des exceptions.

Recommandation : construire une **capacité d'épargne latente** ou un « budget mensuel » relativement persistant, puis y superposer :

- 2 à 5 phases au cours des cinq ans (hausse de revenus, nouveau projet, pression budgétaire, reprise de l'épargne…) ;
- des variations modestes et autocorrélées ;
- un ou plusieurs mois atypiques (PAC suspendu, réduit ou décalé) ;
- une ventilation asymétrique entre les comptes actifs ;
- des versements souvent arrondis à des montants usuels, **mais pas tous identiques**.

Éviter : montant exactement croissant chaque mois, PAC strictement proportionnel au poids de chaque institution, ou répartition en parts égales. Une stratégie peut avoir un **PAC fixe pendant huit mois**, puis changer après un événement ; c'est plus naturel que 60 montants totalement aléatoires.

Chaque PAC doit être rattaché à un compte et à une date. S'il est réparti sur plusieurs fonds, la ventilation doit être visible dans les ordres d'achat, sans compter à nouveau la cotisation.

### 5.2 Versements ponctuels

Créer quelques contributions exceptionnelles expliquées par un **événement latent** : prime, remboursement, argent disponible, changement de projet. Les montants doivent être proportionnels au patrimoine et à la capacité d'épargne simulés (par exemple, centaines à quelques milliers de dollars ; plus rarement davantage si justifié).

Ne pas créer spontanément de versement de **150 000 CAD** ou **1 million CAD** dans un scénario d'épargne de cet ordre de grandeur. Ne pas non plus générer un bonus identique tous les mois de décembre.

### 5.3 Retraits

Créer des retraits rares, liés à des besoins plausibles, avec prélèvement depuis des comptes éligibles et suffisamment provisionnés. **Interdire tous les retraits de REER**. Retraits du CELIAPP désactivés par défaut. Retraits du CELI ou COMP possibles sous réserve des règles du scénario.

Pour un compte investi, un retrait peut déclencher des **ventes de parts** puis un décaissement. Ces ventes internes ne sont pas un second retrait. Aucun compte ne doit présenter de parts négatives ou une encaisse négative non autorisée.

### 5.4 Rééquilibrages et erreurs humaines

L'investisseur n'est ni parfaitement optimal, ni totalement incohérent. Prévoir des décisions **occasionnelles**, déclenchées par des seuils de dérive, une revue annuelle, une modification de tolérance au risque ou un besoin de liquidités.

Permettre :

- Un rééquilibrage incomplet ou retardé ;
- Une modification des contributions vers certains fonds plutôt qu'une liquidation complète ;
- Une inertie d'investissement (*status quo*) ;
- Une préférence intermittente pour la prudence ou la croissance ;
- Une légère sous-diversification possible, mais pas une contradiction totale avec le profil annoncé.

Ne jamais donner au comportement futur la connaissance du meilleur fonds du mois suivant (*look-ahead bias*). Ne pas prétendre que tous les arbitrages sont rationnels a posteriori.

### 5.5 Événements

Créer un **journal d'événements explicatifs** fictifs : date, type, comptes concernés, impact prévu, éventuel commentaire très court. Exemples : ouverture du CELIAPP, hausse de capacité d'épargne, dépense imprévue, modification de cible, remplacement d'un fonds. Ces événements structurent la simulation ; ils ne doivent pas être des annotations inventées après coup pour justifier chaque courbe.

---

## 6. Modèle de données et traçabilité

Privilégier des tables normalisées avec identifiants stables, dates ISO 8601, montants en **CAD** et format décimal numérique (`.` dans les CSV, pas de `$` ni de séparateur de milliers). Export `UTF-8`, dictionnaire de données et convention claire de signe. Conserver les valeurs de calcul en précision suffisante et arrondir uniquement selon les règles du grand livre et à l'affichage.

### Tables minimales

| Table | Grain | Principales colonnes |
|---|---|---|
| `institutions` | 1/institution | `institution_id`, `name`, `strategy_profile`, `opened_at` |
| `accounts` | 1/compte | `account_id`, `institution_id`, `regime`, `account_alias`, `opened_at`, `closed_at` |
| `funds` | 1/fonds | `fund_id`, `institution_id`, `fund_name`, `currency`, `fee_policy`, `inception_date` |
| `fund_exposures` | 1/fonds × classe × région × style | `fund_id`, `asset_class`, `geography`, `style`, `weight` |
| `fund_prices_daily` | 1/fonds/jour ouvrable | `date`, `fund_id`, `nav_total_return`, `currency` |
| `external_movements` | 1/mouvement externe ou frais | `movement_id`, `date`, `account_id`, `movement_type`, `amount_cad`, `event_id` |
| `internal_trades` | 1/ordre exécuté | `trade_id`, `date`, `account_id`, `fund_id`, `side`, `units`, `unit_price`, `gross_amount_cad`, `fee_cad` |
| `positions_daily` | 1/compte × fonds × jour de valorisation | `date`, `account_id`, `fund_id`, `units`, `market_value_cad` |
| `account_values_daily` | 1/compte/jour | `date`, `account_id`, `cash_cad`, `invested_value_cad`, `total_value_cad` |
| `events` | 1/événement | `event_id`, `date`, `event_type`, `description`, `scenario_impact` |
| `allocation_targets_history` | 1/cible × période | `effective_date`, `institution_id`/`account_id`, `asset_class`/`fund_id`, `target_weight` |
| `benchmarks_daily` | 1/référence/jour | `date`, `benchmark_id`, `index_total_return`, `currency` |
| `performance_daily` | 1/niveau de consolidation/jour | `date`, `entity_type`, `entity_id`, `market_value_cad`, `net_external_flow_cad`, `daily_twr`, `cumulative_twr` |
| `simulation_manifest` | 1/exécution | `scenario_id`, `seed`, `config_hash`, `generated_at`, `version`, `synthetic_flag` |

Les clés étrangères et dates d'ouverture doivent être cohérentes. Les éventuels détails concernant les valeurs initiales ou les événements internes doivent être explicitement comptabilisés.

### Contrat des quatre types de mouvements

Les **quatre types métier** attendus sont :

| `movement_type` | Définition | Nature pour TWR |
|---|---|---|
| `PAC` | Apport régulier programmé sur un compte | **Flux externe positif** |
| `PONCTUEL` | Apport externe non récurrent | **Flux externe positif** |
| `RETRAIT` | Sortie de capital vers l'extérieur | **Flux externe négatif** |
| `FRAIS` | Coût distinct débité du patrimoine | **Charge de performance, pas apport/retrait externe** |

Documenter la convention de signe (`amount_cad > 0` pour les versements ; `< 0` pour retraits/frais, par exemple). **Ne pas** qualifier un ordre d'achat d'apport : un dépôt de 800 CAD puis un achat de 800 CAD = **un seul** flux externe de +800 CAD.

Les opérations `BUY`, `SELL`, rééquilibrages et transferts internes doivent être dans un **journal séparé** ; elles ne créent pas de performance et ne changent pas le capital externe consolidé. Un transfert entre deux comptes du patrimoine est neutre au niveau consolidé, même si chaque compte connaît un flux. Si les transferts ne sont pas nécessaires au MVP, ne pas en créer.

### Unités, valorisation et exactitude

- `units_t = units_(t-1) + bought_units - sold_units`, avec précision adaptée au produit.
- `invested_value_t = Σ_f (units_(f,t) × nav_(f,t) × fx_(f,t))` ; le FX vaut 1 pour un fonds en CAD.
- `account_value_t = invested_value_t + cash_t`.
- Les ventes ne peuvent pas dépasser les unités détenues ; les frais et retraits sont réellement débités.
- Le montant initial, s'il existe, doit provenir d'un **événement d'ouverture/solde initial documenté** et non d'une valorisation magique.
- Éviter les dates de transaction hors période d'existence des comptes/fonds.

**Solde initial :** configurable. Pour un patrimoine issu de cinq années d'épargne, un départ à 0 est permis, tout comme un capital préexistant modéré **avec origine enregistrée**. Ne pas injecter silencieusement une grosse somme pour rendre le graphique impressionnant.

---

## 7. Rendements : empêcher les calculs trompeurs

### 7.1 Conventions d'horodatage

Décider et documenter **un ordre journalier unique**, par exemple :

1. Report des encours post-flux de J−1.
2. Application du rendement de marché jusqu'à la clôture de J.
3. Débit des frais de compte de J (si applicable).
4. Calcul de la valorisation **avant flux externes** de J.
5. Exécution des apports, retraits et des achats/ventes au prix de clôture J.
6. Enregistrement du portefeuille **après flux** de J.

Les jours sans cotation doivent suivre une convention déterministe (report au prochain jour ouvrable, pas de rendement fictif pendant le week-end). Si une autre convention est retenue, elle doit être cohérente dans toutes les tables et tests.

### 7.2 TWR

Avec flux externes effectués **en fin de journée**, si `V_(t−1)^+` désigne la valeur post-flux au jour précédent et `V_t^-` la valeur au jour courant **avant flux externe** :

\[
r_t = \frac{V_t^-}{V_{t-1}^+} - 1, \qquad TWR_{0,T} = \prod_t(1+r_t)-1
\]

Cette formule suppose des valeurs définies et une gestion explicite des périodes où le patrimoine est nul ou nouvellement ouvert. Les **frais réduisent la valeur** et doivent donc affecter le rendement net ; ils ne doivent pas être neutralisés comme une contribution externe.

Calculer un TWR à plusieurs grains : fonds/position quand pertinent, compte, institution et portefeuille consolidé. **Le TWR consolidé se reconstruit avec les valorisations et les flux agrégés ; il ne s'obtient pas en faisant simplement la moyenne des TWR des institutions.**

### 7.3 MWR/XIRR

Calculer le taux pondéré par les flux à partir des dates et flux externes et de la valeur finale. Considérer la convention de signe de l'investisseur, les multiples solutions possibles et les cas sans solution numérique robuste. Une valeur `null` justifiée vaut mieux qu'un taux inventé.

### 7.4 Rendement, enrichissement et contribution

Ne pas confondre :

- Variation du patrimoine en dollars ;
- Montants nets investis (`PAC + PONCTUEL − RETRAIT`) ;
- Gains/pertes liés au marché et aux frais ;
- Performance TWR ;
- Performance MWR.

La validation doit réconcilier ces notions. Un patrimoine peut croître fortement parce que l'investisseur a beaucoup cotisé **alors que son TWR est négatif**.

## 8. Comparaison passive : objectif de contrôle, pas adversaire faible

Puisque le dashboard vise à opposer une **stratégie réellement suivie** à une stratégie **passive**, simuler séparément des références cohérentes et les rendre explicites.

Deux comparaisons complémentaires :

1. **Benchmark de politique d'investissement** : portefeuille passif diversifié représentant le profil de risque/les grandes expositions visées (par exemple équilibre actions-obligations comparable). Son allocation doit être définie à l'avance, pas optimisée après lecture des résultats.
2. **Benchmarks de sensibilité** : une référence actions mondiales plus dynamique et une référence équilibrée/prudente ; elles donnent du contexte, mais ne remplacent pas le benchmark principal ajusté au risque.

Pour tester un scénario « et si les mêmes dollars avaient été investis passivement ? », créer un **portefeuille contrefactuel** qui reçoit **les mêmes apports et retraits aux mêmes dates** ; les coûts et règles de rééquilibrage passif doivent être explicités. Ne pas mélanger cette comparaison en dollars avec la comparaison des seuls indices TWR.

Les références synthétiques doivent être générées à partir **des mêmes facteurs de marché** que les fonds, avec expositions passives et coûts propres ; ne pas les rendre artificiellement médiocres. Ne pas déclarer une victoire de la stratégie active sans expliquer différences de risque, devises, frais et répartition géographique.

## 9. Aléatoire maîtrisé et prévention des biais du LLM

### À FAIRE

- Utiliser un générateur pseudoaléatoire reconnu (`numpy.random.Generator`) et des distributions paramétrées, non le LLM pour écrire à la main les nombres.
- Prévoir des dépendances temporelles : état courant, dérive, événements, changement de régime.
- Créer des **variables latentes** (capacité d'épargne, aversion au risque, contexte de marché) qui influencent plusieurs décisions à la fois.
- Conserver des différences entre simulation des prix, décisions, exécution et mesure.
- Proposer plusieurs seeds pour vérifier la diversité **sans sélectionner uniquement les simulations flatteuses**.
- Rendre les scénarios auditables par un `manifest` et un `scenario_report`.

### À ÉVITER

- Pondérations identiques 33/33/34, fonds tous à 10 %, régimes exactement égaux.
- Quinze fonds ayant chacun une performance presque linéaire et une volatilité indépendante.
- Dates et montants trop réguliers, mais aussi chaos sans logique.
- Versements mensuels qui changent complètement sans raison d'un mois à l'autre.
- Retraits inexistants parce qu'ils compliquent le code, ou retraits qui créent un encours négatif.
- Rendements ou « bonnes années » décidés pour démontrer que l'investisseur est habile.
- Génération d'une table de performance sans passer par les valorisations réconciliées.
- Correction manuelle a posteriori des lignes qui ne « font pas joli » dans Power BI.

### Trois scénarios de test recommandés

- `typical`: plausible, désordonné, ni spécialement gagnant ni perdant.
- `stress`: baisse prolongée de marchés, hausse de volatilité, baisse transitoire de l'épargne, besoin de liquidité ; portefeuille reste solvable.
- `adversarial`: cas limites conçus pour casser le dashboard (compte ouvert en cours d'année, mois sans PAC, frais avec marché plat, retrait juste après une baisse, fonds jamais détenu, dates autour de clôtures annuelles).

**La seed contrôle le scénario ; le nom du scénario n'impose jamais une trajectoire de performance pré-écrite.** Dans un scénario de stress, on peut conditionner la distribution de risques ou activer un choc, mais on doit enregistrer clairement cette condition.

---

## 10. Contrôles automatiques et critères d'acceptation

Implémenter des tests unitaires, tests d'intégration et **tests de propriétés/invariants** (par exemple `pytest`, éventuellement `hypothesis`). Le générateur doit échouer avec un message explicite en cas d'incohérence ; ne jamais remplacer une valeur fautive par 0 silencieusement.

### Intégrité et comptabilité — BLOQUANT

- [ ] Exactement 3 institutions ; tous les comptes et fonds appartiennent à une institution connue.
- [ ] Les quatre régimes sont représentés de façon cohérente ; les alias de sous-comptes ne sont pas confondus avec le régime.
- [ ] Autour de 15 fonds distincts ; toutes les pondérations de catégories pertinentes totalisent 100 % dans chaque axe.
- [ ] Aucun retrait de REER ; aucun retrait de CELIAPP dans le MVP.
- [ ] Aucun compte, encaisse ou quantité de parts ne devient négatif, sauf mécanisme de crédit explicitement autorisé (non recommandé).
- [ ] Tout achat et toute vente ont une contrepartie dans l'encaisse ; aucun ordre sans fonds éligible et sans cotation.
- [ ] Toutes les valorisations se réconcilient au cent près, avec tolérances justifiées pour les unités et les prix.
- [ ] Tous les mouvements externes et frais se répercutent dans la valeur patrimoniale exactement une fois.
- [ ] Pas de doublons de clés, de références orphelines, de dates invalides ni de fonds valorisé avant son lancement.
- [ ] Le scénario généré est reproductible à l'identique à seed/config/version identiques.

### Performances — BLOQUANT

- [ ] Marché plat + aucun frais → TWR consolidé = 0 %, quels que soient les versements/retraits valides.
- [ ] Marché plat + frais distincts → TWR net négatif, sans faire passer les frais pour un flux externe.
- [ ] Simple contribution en fin de journée → pas de saut artificiel du TWR au jour de la contribution.
- [ ] Valeur du patrimoine = capital initial + flux nets + résultat de placement net de frais, selon convention comptable documentée.
- [ ] TWR consolidé recalculé depuis les encours et non depuis une moyenne arithmétique de TWR locaux.
- [ ] Le contrefactuel passif emploie le même calendrier de flux externes que la stratégie réelle simulée.
- [ ] Aucun usage de prix futurs dans les décisions de placement.

### Réalisme statistique — DIAGNOSTICS, PAS QUOTAS RIGIDES

Calculer et présenter, sans optimiser le scénario vers de « belles valeurs » :

- Poids d'encours de chaque institution et de chaque régime au début/à la fin.
- Concentration des fonds, exposition actions/obligations et régions pondérées par encours.
- Montant de PAC agrégé par mois, fréquence des mois sans PAC, changements de niveau de cotisation.
- Nombre et montant des ponctuels, retraits et frais ; fréquence des événements par année.
- Volatilité, drawdown maximal, corrélations croisées, rendement annuel des fonds et du portefeuille.
- TWR/MWR, contribution en dollars, poids des frais, divergence avec les benchmarks.
- Anomalies détectées (par exemple poids d'une institution supérieur à 95 %, PAC mensuels parfaitement identiques sur 60 mois, 3 fonds quasi identiques, frais incompatibles, mouvements trop gros comparés à la capacité d'épargne).

Ces anomalies déclenchent une **alerte** ou un rejet seulement si elles violent une contrainte définie. Ne pas « réparer » la simulation en redistribuant les pondérations à parts égales.

### Tests multi-seeds

Exécuter les validations sur au moins 20 seeds représentatives durant le développement, mesurer les taux d'échec et corriger les règles du moteur. Ne pas ne retenir que les seeds dont les rendements sont beaux. En livraison, conserver les seeds des exemples et leur rapport.

## 11. Exports et livrables de l'agent

### Arborescence suggérée

```text
synthetic_finance/
  README.md
  pyproject.toml                    # ou requirements.txt
  configs/
    base.yaml
    typical.yaml
    stress.yaml
    adversarial.yaml
  src/synthetic_finance/
    config.py
    universe.py
    market.py
    behaviour.py
    ledger.py
    performance.py
    benchmarks.py
    export.py
    validation.py
    cli.py
  tests/
    test_accounting.py
    test_movements.py
    test_tax_safety.py
    test_market.py
    test_performance.py
    test_reproducibility.py
  outputs/
    typical_seed_20261103/
      data/*.csv
      scenario_report.md
      data_dictionary.md
      manifest.json
      validation.json
```

### Interface en ligne de commande souhaitée

```bash
python -m synthetic_finance generate \
  --config configs/typical.yaml \
  --seed 20261103 \
  --out outputs/typical_seed_20261103

python -m synthetic_finance validate \
  --path outputs/typical_seed_20261103

python -m synthetic_finance report \
  --path outputs/typical_seed_20261103
```

L'interface exacte est libre ; fournir des commandes **fonctionnelles** avec le projet livré.

### Contenu de la configuration

```yaml
scenario:
  name: typical
  start_date: '2021-11-01'
  end_date: '2026-10-30'
  base_currency: CAD
  seed: 20261103

universe:
  institution_count: 3
  fund_count: 15
  regimes: [CELI, CELIAPP, REER, COMP]
  portfolio_strategy_profiles: [prudent, balanced, growth]
  allow_multiple_accounts_per_regime: true

savings:
  recurring_monthly_total_cad:
    typical_min: 500
    typical_max: 1000
  allow_pauses: true
  allow_step_changes: true
  allow_exceptional_contributions: true

withdrawals:
  prohibited_regimes: [REER, CELIAPP]
  require_available_assets: true
  frequency: occasional

markets:
  method: latent_multifactor_regime_switching
  resolution: business_daily
  allow_volatility_clusters: true
  allow_rare_shocks: true

accounting:
  fiscal_mode: accounting_only
  transaction_currency: CAD
  fund_prices: synthetic_total_return_nav
  external_flow_timing: end_of_day
  include_account_fees_in_net_performance: true

output:
  format: csv
  include_full_audit: true
  include_daily_valuations: true
```

Le YAML illustre des **intentions fonctionnelles** : l'agent doit définir et valider un vrai schéma de configuration. `typical_min` et `typical_max` sont des **repères pour le niveau usuel**, pas des bornes quotidiennes inviolables. Les dates sont un exemple et doivent être paramétrables.

### Livrables obligatoires

1. Code exécutable et configuration(s) commentée(s).
2. Données synthétiques **complètes** prêtes à importer (fichiers CSV/Parquet ou schéma compatible avec le projet).
3. `data_dictionary.md` : grain, clés, types, conventions, signe des flux, calculs, portée de chaque table.
4. `scenario_report.md` : histoire générée en quelques paragraphes, allocations, comportement, événements, diagnostics, sans présenter les résultats comme réels.
5. `validation.json` / rapport tests : contrôles exécutés, succès/échecs, avertissements et tolérances.
6. `manifest.json` : seed, hash de configuration, versions, période, horodatage de génération, drapeau `synthetic=true`.
7. Adaptateur Power BI si utile : correspondance entre colonnes synthétiques et modèle existant, sans modifier les sources privées.

## 12. Plan d'implémentation conseillé

**Jalon 1 — Contrat & univers :** schéma, 3 institutions, comptes, ~15 fonds, expositions, paramètres et validations de base. Faire vérifier les contraintes avant d'aller plus loin.

**Jalon 2 — Marchés :** générateur indépendant de NAV + benchmarks, corrélations/régimes, diagnostics de volatilité et reproductibilité.

**Jalon 3 — Comportements & événements :** PAC par phases, ponctuels, retraits, arbitrages imparfaits, restrictions des régimes.

**Jalon 4 — Grand livre :** apports/retraits, ordres, cash, unités, frais, valorisations et réconciliations quotidiennes. Ce jalon est prioritaire sur tout travail esthétique.

**Jalon 5 — Rendements & benchmarks :** TWR, MWR, allocation effective, contrefactuel passif et tests de non-biais.

**Jalon 6 — Export & revue :** QA multi-seeds, scénarios `typical`/`stress`/`adversarial`, dictionnaire, rapport, mapping Power BI, démonstration de quelques parcours vérifiables compte → mouvement → transaction → position → rendement.

Si une fonctionnalité avancée ralentit le MVP (fiscalité exhaustive, conversions multi-devises, distribution de dividendes, transactions interrégimes), **réduire le périmètre explicitement**, sans sacrifier la cohérence comptable ni inventer des résultats.

---

## 13. Définition de terminé

Le travail n'est pas terminé lorsque 15 fonds et 60 mois de données s'affichent dans Power BI. Il est terminé lorsqu'un tiers peut :

1. Relancer le générateur avec une seed et retrouver le même jeu de données.
2. Remonter depuis une valeur de portefeuille agrégée jusqu'aux unités de fonds, prix, flux, transactions et frais correspondants.
3. Comprendre pourquoi les trois institutions ont des approches différentes **sans proportions artificiellement égales**.
4. Observer des événements et un comportement d'épargne non linéaires, mais justifiables.
5. Recalculer indépendamment le TWR et vérifier qu'un versement n'a pas créé de rendement fictif.
6. Comparer la stratégie à un passif **approprié au risque**, et non à une référence choisie pour perdre.
7. Exécuter les tests et identifier les scénarios statistiquement atypiques sans les cacher.
8. Utiliser ce jeu sans jamais exposer ou remplacer des données financières personnelles.

### Consigne finale à Claude Code

**Commence par analyser le contrat de données existant et proposer une architecture brève. Ensuite, implémente réellement le générateur, ses tests et ses exports, par jalons. N'écris pas les données à la main. Ne privilégie ni la beauté du graphique ni une surperformance arbitraire. Le modèle doit produire un patrimoine qui ressemble à l'histoire imparfaite d'un épargnant, avec une comptabilité irréprochable.**
