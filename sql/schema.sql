-- Schéma de la base finance (PostgreSQL 18, localhost).
-- Rejouable : chaque objet est créé s'il n'existe pas. Aucune donnée ici.
--   ref  : tables de référence, rechargées à chaque exécution depuis donnees/reference/
--   fait : données des exports (transactions du dernier Historique, sommaires de tous les Rapports)

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS fait;

-- Un compte par numéro ; le numéro ne sort jamais de cette table (livrables sous alias)
CREATE TABLE IF NOT EXISTS ref.compte (
    alias       text PRIMARY KEY,               -- CELI-1, REER-1…
    numero      text UNIQUE,                    -- vide pour un compte fermé, sans export
    genre       text NOT NULL,                  -- tel que lu en A1 : CELI, CELIAPP, REER, COMP
    societe     text,                           -- société de gestion (Société 1, 2 ou 3, fictives), saisie à la main ; vide tant qu'inconnue
    ferme_le    date                            -- date de fermeture ; vide = compte actif
);
-- Bases créées avant la prise en compte des comptes fermés
ALTER TABLE ref.compte ALTER COLUMN numero DROP NOT NULL;
ALTER TABLE ref.compte ADD COLUMN IF NOT EXISTS ferme_le date;

-- Libellé de transaction -> nature et sens des parts. Le motif est un préfixe :
-- « Arbitrage — achat depuis » couvre tout fonds source.
CREATE TABLE IF NOT EXISTS ref.nature (
    motif       text PRIMARY KEY,
    nature      text NOT NULL CHECK (nature IN ('PAC', 'ponctuel', 'revenu', 'interne', 'frais', 'retrait')),
    signe       smallint NOT NULL CHECK (signe IN (-1, 1)),
    cotisation  boolean NOT NULL                -- consomme des droits (avant correction des transferts)
);

-- Achats qui sont des transferts directs entre institutions : ils ne consomment pas de droits
-- (l'export ne les distingue pas d'une cotisation). Vide à ce jour.
CREATE TABLE IF NOT EXISTS ref.transfert_entrant (
    compte_alias      text NOT NULL REFERENCES ref.compte (alias),
    date_negociation  date NOT NULL,
    code_fonds        text NOT NULL,
    montant           numeric(14, 2) NOT NULL,
    note              text,
    PRIMARY KEY (compte_alias, date_negociation, code_fonds)
);

-- Retraits qui sont des transferts directs vers un autre compte du même régime (CELI vers CELI, REER
-- vers REER, CELIAPP vers CELIAPP) : ni retrait ni cotisation pour les droits (R14). Même clé que
-- la ligne « Rachat — retrait » de l'export. Vide à ce jour.
CREATE TABLE IF NOT EXISTS ref.transfert_sortant (
    compte_alias      text NOT NULL REFERENCES ref.compte (alias),
    date_negociation  date NOT NULL,
    code_fonds        text NOT NULL,
    montant           numeric(14, 2) NOT NULL,
    note              text,
    PRIMARY KEY (compte_alias, date_negociation, code_fonds)
);

-- Paramètres des droits, une ligne par clé (docs/regles-droits.md, R5a et R8)
CREATE TABLE IF NOT EXISTS ref.parametre (
    cle     text PRIMARY KEY CHECK (cle IN ('celi_premiere_annee', 'celiapp_ouverture')),
    valeur  smallint NOT NULL,                  -- une année
    note    text
);

-- Cotisations faites hors des exports (compte d'une autre institution) : elles consomment des droits.
-- compte_alias rattache la saisie à un compte connu du rapport (compte fermé) ; vide = sans compte.
CREATE TABLE IF NOT EXISTS ref.versement_hors_export (
    regime          text NOT NULL CHECK (regime IN ('CELI', 'CELIAPP', 'REER')),
    date_versement  date NOT NULL,
    montant         numeric(14, 2) NOT NULL CHECK (montant > 0),
    note            text,
    compte_alias    text REFERENCES ref.compte (alias)
);
ALTER TABLE ref.versement_hors_export ADD COLUMN IF NOT EXISTS compte_alias text REFERENCES ref.compte (alias);

-- Retraits faits hors des exports (autre institution) : rendent des droits le 1ᵉʳ janvier suivant (R3)
CREATE TABLE IF NOT EXISTS ref.retrait_hors_export (
    regime          text NOT NULL CHECK (regime IN ('CELI', 'CELIAPP', 'REER')),
    date_retrait    date NOT NULL,
    montant         numeric(14, 2) NOT NULL CHECK (montant > 0),
    note            text,
    compte_alias    text REFERENCES ref.compte (alias)
);
ALTER TABLE ref.retrait_hors_export ADD COLUMN IF NOT EXISTS compte_alias text REFERENCES ref.compte (alias);

-- État du maximum déductible REER, par année de déduction (avis de cotisation de l'année
-- précédente) et déduction demandée à la ligne 20800 de la déclaration de cette année.
-- Vide = pas encore connu. Les cotisations inutilisées ne servent qu'à la première année :
-- les suivantes sont reconstruites, et l'avis sert de contrôle (C2).
CREATE TABLE IF NOT EXISTS ref.reer_avis (
    annee_deduction          smallint PRIMARY KEY,
    maximum_deductible       numeric(14, 2),
    cotisations_inutilisees  numeric(14, 2),
    deduction_20800          numeric(14, 2),
    note                     text
);

-- Dernier Historique chargé par compte
CREATE TABLE IF NOT EXISTS fait.historique (
    compte_alias  text PRIMARY KEY REFERENCES ref.compte (alias),
    date_export   date NOT NULL,                -- cellule N1
    debut         date NOT NULL,                -- cellule M3, période demandée
    fin           date NOT NULL
);

-- Transactions du dernier Historique de chaque compte. rang = ordre chronologique dans le
-- fichier (1 = la plus ancienne) : il départage les opérations d'une même journée.
CREATE TABLE IF NOT EXISTS fait.transaction (
    compte_alias      text NOT NULL REFERENCES fait.historique (compte_alias),
    rang              integer NOT NULL,
    code_fonds        text NOT NULL,
    nom_fonds         text NOT NULL,
    date_negociation  date NOT NULL,
    date_processus    date NOT NULL,
    libelle           text NOT NULL,
    nature            text NOT NULL,
    signe             smallint NOT NULL,
    montant_brut      numeric(14, 2) NOT NULL,
    deductions        numeric(14, 2) NOT NULL,
    montant_net       numeric(14, 2) NOT NULL,
    prix_part         numeric(14, 4) NOT NULL,
    parts_negociees   numeric(14, 3) NOT NULL,
    parts_restantes   numeric(14, 3) NOT NULL,
    PRIMARY KEY (compte_alias, rang)
);

-- Sommaire financier de chaque Rapport : s'accumule, mois après mois (non régénérable)
CREATE TABLE IF NOT EXISTS fait.sommaire (
    compte_alias       text NOT NULL REFERENCES ref.compte (alias),
    date_valorisation  date NOT NULL,           -- cellule N1 du Rapport
    code_fonds         text NOT NULL,
    nom_fonds          text NOT NULL,
    nb_actions         numeric(14, 3) NOT NULL,
    prix_action        numeric(14, 4) NOT NULL,
    prix_moyen         numeric(14, 4) NOT NULL,
    valeur_comptable   numeric(14, 2) NOT NULL,
    valeur_marchande   numeric(14, 2) NOT NULL,
    PRIMARY KEY (compte_alias, date_valorisation, code_fonds)
);

-- Relevé saisi à la main d'un compte sans export : une ligne par période du relevé, d'un solde
-- d'ouverture au gain qui la clôt. Rechargé en entier depuis un classeur de saisie, dont le chargeur
-- contrôle le chaînage des soldes avant tout chargement. Vide dans le jeu fictif.
CREATE TABLE IF NOT EXISTS fait.releve (
    compte_alias  text NOT NULL REFERENCES ref.compte (alias),
    debut         date NOT NULL,                -- date du solde d'ouverture
    fin           date NOT NULL,                -- date du gain qui clôt la période
    fonds         text NOT NULL,                -- A1 du relevé
    ouverture     numeric(14, 2) NOT NULL,
    gain          numeric(14, 2) NOT NULL,      -- gain ou perte sur placements, après frais du fonds
    cloture       numeric(14, 2) NOT NULL,      -- ouverture + cotisations + gain
    PRIMARY KEY (compte_alias, debut)
);

-- Cotisations du relevé ; rang = ordre chronologique dans le compte (1 = la plus ancienne)
CREATE TABLE IF NOT EXISTS fait.releve_cotisation (
    compte_alias    text NOT NULL,
    rang            integer NOT NULL,
    debut           date NOT NULL,              -- période du relevé
    date_versement  date NOT NULL,
    montant         numeric(14, 2) NOT NULL CHECK (montant > 0),
    PRIMARY KEY (compte_alias, rang),
    FOREIGN KEY (compte_alias, debut) REFERENCES fait.releve (compte_alias, debut)
);

-- Journal des exécutions ; hors empreinte d'idempotence
CREATE TABLE IF NOT EXISTS fait.chargement (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    horodatage   timestamptz NOT NULL DEFAULT now(),
    historiques  integer NOT NULL,
    rapports     integer NOT NULL,
    lignes       integer NOT NULL
);

-- ============================================================================================
-- Stratégie (itération 5). pub : profils mensuels publics de la Société 1, rechargés en entier par
-- pipeline.profils depuis donnees/public/<société>/. Règles S1 à S6 : docs/regles-strategie.md.
-- ============================================================================================
CREATE SCHEMA IF NOT EXISTS pub;

-- Un profil par fonds (code de l'option FA) et par date de données (fin de mois)
CREATE TABLE IF NOT EXISTS pub.profil (
    code_fa        text NOT NULL,
    date_donnees   date NOT NULL,
    nom            text NOT NULL,
    type_fonds     text NOT NULL,               -- Actions, Équilibré, Marché monétaire canadien…
    profil_risque  text NOT NULL,               -- Faible … Élevé, tel qu'imprimé
    rfg            numeric(6, 2) NOT NULL,      -- %, frais internes au fonds
    frais_moins    numeric(6, 2) NOT NULL,      -- % : frais de gestion, actif agrégé du ménage < 100 000 $
    frais_plus     numeric(6, 2) NOT NULL,      -- % : au-delà de 100 000 $
    fichier        text NOT NULL,               -- AAAA-MM/<société>-<code>-profil.pdf
    PRIMARY KEY (code_fa, date_donnees)
);

-- Codes d'un même fonds selon l'option de frais d'acquisition : un seul prix ; code_fa = code pivot
CREATE TABLE IF NOT EXISTS pub.profil_code (
    code_fonds    text PRIMARY KEY,             -- tel qu'écrit dans fait.transaction
    code_fa       text NOT NULL,
    option_achat  text NOT NULL CHECK (option_achat IN ('FA', 'FR', 'FM'))   -- frais d'acquisition, de rachat, modérés
);

-- Lignes de répartition telles qu'imprimées. parent : classe d'un sous-poste (actif, actuelle)
CREATE TABLE IF NOT EXISTS pub.profil_ligne (
    code_fa       text NOT NULL,
    date_donnees  date NOT NULL,
    section       text NOT NULL CHECK (section IN ('secteur', 'actif', 'pays', 'revenu_fixe', 'cible', 'actuelle')),
    ordre         smallint NOT NULL,
    libelle       text NOT NULL,
    poids         numeric(6, 2) NOT NULL,       -- %
    parent        text,
    PRIMARY KEY (code_fa, date_donnees, section, ordre),
    FOREIGN KEY (code_fa, date_donnees) REFERENCES pub.profil (code_fa, date_donnees)
);

-- S5 : style d'un fonds sous-jacent (type sous-jacent, clé = libellé du profil) ou d'un fonds à
-- stratégie unique (type fonds, clé = code FA). Saisie : donnees/reference/styles_fonds.csv
CREATE TABLE IF NOT EXISTS ref.style (
    cle    text NOT NULL,
    type   text NOT NULL CHECK (type IN ('fonds', 'sous-jacent')),
    style  text NOT NULL CHECK (style IN ('Dividendes', 'Croissance', 'Mixte', 'Revenu fixe', 'Alternatifs', 'Trésorerie')),
    note   text,
    PRIMARY KEY (type, cle)
);
-- « Cœur » renommé « Mixte » le 2026-11-01 : la contrainte d'une base existante suit, ses lignes aussi
ALTER TABLE ref.style DROP CONSTRAINT IF EXISTS style_style_check;
UPDATE ref.style SET style = 'Mixte' WHERE style = 'Cœur';
ALTER TABLE ref.style ADD CONSTRAINT style_style_check
    CHECK (style IN ('Dividendes', 'Croissance', 'Mixte', 'Revenu fixe', 'Alternatifs', 'Trésorerie'));

-- S4 : pays ou région d'un profil -> catégorie géographique. Saisie : donnees/reference/geographie.csv
CREATE TABLE IF NOT EXISTS ref.geographie (
    libelle    text PRIMARY KEY,
    categorie  text NOT NULL CHECK (categorie IN ('Canada', 'États-Unis', 'Autres pays', 'Trésorerie et non ventilé'))
);

-- S7 : un fonds par code pivot (les autres options s'y rattachent par pub.profil_code ;
-- un fonds détenu sans profil garde son propre code). Attributs stables, saisis à la main : nom court,
-- profil ordinal, mandat déclaré. Saisie : donnees/reference/fonds.csv
CREATE TABLE IF NOT EXISTS ref.fonds (
    code_fa       text PRIMARY KEY,
    nom_court     text NOT NULL UNIQUE,
    profil        text NOT NULL,
    ordre_profil  smallint NOT NULL,
    mandat        text NOT NULL CHECK (mandat IN ('Mondial', 'Canada', 'Amérique du Nord', 'Marchés émergents')),
    note          text,
    CHECK (profil IN ('Épargne', 'Revenu', 'Conservateur', 'Modéré', 'Croissance', 'Actions')
           AND ordre_profil = CASE profil WHEN 'Épargne' THEN 1 WHEN 'Revenu' THEN 2 WHEN 'Conservateur' THEN 3
                                          WHEN 'Modéré' THEN 4 WHEN 'Croissance' THEN 5 ELSE 6 END)
);

-- S8 : rang de chaque niveau de risque publié dans les profils. Saisie : donnees/reference/risque.csv
CREATE TABLE IF NOT EXISTS ref.risque (
    libelle  text PRIMARY KEY,
    rang     smallint NOT NULL UNIQUE CHECK (rang BETWEEN 1 AND 5)
);

-- P10 : symbole Yahoo de chaque fonds de la plateforme, détenu ou non (les fonds non détenus masquent
-- à Yahoo la liste des fonds détenus). nom_yahoo : nom attendu, contrôlé à chaque chargement.
-- Saisie : donnees/reference/symboles.csv
CREATE TABLE IF NOT EXISTS ref.symbole (
    code_fa    text PRIMARY KEY,
    symbole    text NOT NULL UNIQUE,
    nom_yahoo  text NOT NULL
);

-- P15 : composite de FNB de chaque fonds détenu, une ligne par indice du repère publié dans le
-- rapport annuel de la direction ; le même FNB peut servir de substitut à deux indices.
-- Saisie : donnees/reference/reperes.csv
CREATE TABLE IF NOT EXISTS ref.repere (
    code_fa  text NOT NULL,
    indice   text NOT NULL,
    symbole  text NOT NULL,
    poids    numeric(6, 4) NOT NULL CHECK (poids > 0 AND poids <= 1),
    note     text,
    PRIMARY KEY (code_fa, indice)
);

-- P10, P15 : cours quotidiens de Yahoo, un par symbole et par date de séance (fuseau de la place).
-- cloture : non ajustée, seule utilisée pour un fonds Société 1 ; cloture_ajustee : seule utilisée pour un FNB.
CREATE TABLE IF NOT EXISTS pub.cours (
    symbole          text NOT NULL,
    date_seance      date NOT NULL,
    cloture          numeric(14, 4) NOT NULL,
    cloture_ajustee  numeric(18, 8),
    devise           text NOT NULL,
    PRIMARY KEY (symbole, date_seance)
);

-- S11, S12, S14 : faits saillants de la série détenue des rapports annuels de la direction (RDRF),
-- un par fonds de symboles.csv et par exercice imprimé, rechargés en entier par pipeline.rapports
-- depuis donnees/public/<société>/annuel/. Distributions en $ par part (positives) ; ratios en %.
CREATE TABLE IF NOT EXISTS pub.rapport_annuel (
    code_fa        text NOT NULL,
    exercice       date NOT NULL,               -- clôture de l'exercice (30 septembre)
    nom            text NOT NULL,               -- tel qu'imprimé en tête du RDRF
    revenus        numeric(10, 2) NOT NULL,     -- revenus hors dividendes
    dividendes     numeric(10, 2) NOT NULL,
    gains_capital  numeric(10, 2) NOT NULL,
    remb_capital   numeric(10, 2) NOT NULL,
    total          numeric(10, 2) NOT NULL,     -- distributions annuelles totales imprimées
    rfg            numeric(6, 2) NOT NULL,
    rfg_avant      numeric(6, 2) NOT NULL,      -- RFG avant abandons ou absorptions
    rfo            numeric(6, 2) NOT NULL,      -- ratio des frais d'opérations
    rotation       numeric(8, 2),               -- taux de rotation ; vide si « s.o. »
    fichier        text NOT NULL,               -- AAAA-MM-JJ/<code>.pdf
    PRIMARY KEY (code_fa, exercice)
);
