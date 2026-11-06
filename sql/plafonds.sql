-- Plafonds publics des régimes enregistrés et calendrier REER des 60 jours.
-- Valeurs publiques seulement, chacune sourcée dans docs/regles-droits.md (n° de règle en commentaire).
-- Rejouable : tables recréées si absentes, contenu remplacé. Exécuté par pipeline.chargement,
-- dans la même transaction que le chargement (seul : psql -1 -f sql/plafonds.sql).
-- Aucun plafond ne s'écrit ailleurs : sql/vues.sql lit ces deux tables.

CREATE SCHEMA IF NOT EXISTS ref;

-- Un montant par régime, rubrique et année. annee NULL = valeur sans millésime (plafond à vie, marge).
CREATE TABLE IF NOT EXISTS ref.plafond (
    regime    text NOT NULL CHECK (regime IN ('CELI', 'CELIAPP', 'REER')),
    rubrique  text NOT NULL CHECK (rubrique IN ('plafond_annuel', 'report_max', 'plafond_vie', 'marge_excedent')),
    annee     smallint,
    montant   numeric(14, 2) NOT NULL,
    regle     text NOT NULL,                    -- n° de ligne dans docs/regles-droits.md
    UNIQUE NULLS NOT DISTINCT (regime, rubrique, annee)
);

-- Année de déduction REER : une cotisation appartient à la première année dont la période se
-- termine à sa date ou après. Seule la fin est stockée ; le début est la fin de l'année précédente.
CREATE TABLE IF NOT EXISTS ref.periode_reer (
    annee_deduction  smallint PRIMARY KEY,
    fin              date NOT NULL UNIQUE,
    regle            text NOT NULL
);

DELETE FROM ref.plafond;
DELETE FROM ref.periode_reer;

-- R1. Plafond annuel CELI, 2009 à 2026
INSERT INTO ref.plafond (regime, rubrique, annee, montant, regle) VALUES
    ('CELI', 'plafond_annuel', 2009,  5000, 'R1'),
    ('CELI', 'plafond_annuel', 2010,  5000, 'R1'),
    ('CELI', 'plafond_annuel', 2011,  5000, 'R1'),
    ('CELI', 'plafond_annuel', 2012,  5000, 'R1'),
    ('CELI', 'plafond_annuel', 2013,  5500, 'R1'),
    ('CELI', 'plafond_annuel', 2014,  5500, 'R1'),
    ('CELI', 'plafond_annuel', 2015, 10000, 'R1'),
    ('CELI', 'plafond_annuel', 2016,  5500, 'R1'),
    ('CELI', 'plafond_annuel', 2017,  5500, 'R1'),
    ('CELI', 'plafond_annuel', 2018,  5500, 'R1'),
    ('CELI', 'plafond_annuel', 2019,  6000, 'R1'),
    ('CELI', 'plafond_annuel', 2020,  6000, 'R1'),
    ('CELI', 'plafond_annuel', 2021,  6000, 'R1'),
    ('CELI', 'plafond_annuel', 2022,  6000, 'R1'),
    ('CELI', 'plafond_annuel', 2023,  6500, 'R1'),
    ('CELI', 'plafond_annuel', 2024,  7000, 'R1'),
    ('CELI', 'plafond_annuel', 2025,  7000, 'R1'),
    ('CELI', 'plafond_annuel', 2026,  7000, 'R1');

-- R8 à R10. CELIAPP : 8 000 $ par an, report plafonné à 8 000 $, 40 000 $ à vie. Régime ouvrable
-- dès le 2023-04-01, 8 000 $ l'année d'ouverture (consulté le 2026-11-02) :
-- https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/rrsps-related-plans/important-dates-rrsp-rrif-rdsp.html
-- https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2023/saving-first-home-find-out-how-first-home-savings-account-can-help.html
INSERT INTO ref.plafond (regime, rubrique, annee, montant, regle) VALUES
    ('CELIAPP', 'plafond_annuel', 2023, 8000, 'R8'),
    ('CELIAPP', 'plafond_annuel', 2024, 8000, 'R8'),
    ('CELIAPP', 'plafond_annuel', 2025, 8000, 'R8'),
    ('CELIAPP', 'plafond_annuel', 2026, 8000, 'R8'),
    ('CELIAPP', 'report_max',     NULL, 8000, 'R9'),
    ('CELIAPP', 'plafond_vie',    NULL, 40000, 'R10');

-- R7. REER : excédent toléré sans impôt jusqu'à 2 000 $
INSERT INTO ref.plafond (regime, rubrique, annee, montant, regle) VALUES
    ('REER', 'marge_excedent', NULL, 2000, 'R7');

-- R11. REER : plafond annuel en dollars de l'année de déduction N, appliqué à 18 % du revenu gagné
-- de N − 1 (consulté le 2026-11-03). Lu par le générateur synthétique ; aucune vue ne s'en sert.
-- https://www.canada.ca/en/revenue-agency/services/tax/registered-plans-administrators/pspa/mp-rrsp-dpsp-tfsa-limits-ympe.html
-- https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/rrsps-related-plans/contributing-a-rrsp-prpp/contributions-affect-your-rrsp-prpp-deduction-limit.html
INSERT INTO ref.plafond (regime, rubrique, annee, montant, regle) VALUES
    ('REER', 'plafond_annuel', 2020, 27230, 'R11'),
    ('REER', 'plafond_annuel', 2021, 27830, 'R11'),
    ('REER', 'plafond_annuel', 2022, 29210, 'R11'),
    ('REER', 'plafond_annuel', 2023, 30780, 'R11'),
    ('REER', 'plafond_annuel', 2024, 31560, 'R11'),
    ('REER', 'plafond_annuel', 2025, 32490, 'R11'),
    ('REER', 'plafond_annuel', 2026, 33810, 'R11');

-- R6. Fin de la période de cotisation de chaque année de déduction (60ᵉ jour, reporté au
-- jour ouvrable suivant s'il tombe un samedi ou un dimanche). 2026 : date calculée par la règle,
-- pas encore publiée. Ajouter l'année suivante chaque mois de janvier. Dates 2019 à 2025 (consulté le 2026-11-02) :
-- https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/completing-slips-summaries/financial-slips-summaries/rrsp-contribution-receipt-return/contribution-year.html
INSERT INTO ref.periode_reer (annee_deduction, fin, regle) VALUES
    (2019, DATE '2020-03-02', 'R6'),
    (2020, DATE '2021-03-01', 'R6'),
    (2021, DATE '2022-03-01', 'R6'),
    (2022, DATE '2023-03-01', 'R6'),
    (2023, DATE '2024-02-29', 'R6'),
    (2024, DATE '2025-03-03', 'R6'),
    (2025, DATE '2026-03-02', 'R6'),
    (2026, DATE '2027-03-01', 'R6 (calculée)');
