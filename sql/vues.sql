-- Vues lues par le rapport Power BI (mode Import) : droits par régime et par année, alerte de
-- dépassement, part mensuelle des versements. Règles et hypothèses : docs/regles-droits.md.
-- Aucun plafond ici : ils viennent de ref.plafond et ref.periode_reer (sql/plafonds.sql).
-- Une saisie ou un plafond manquant donne NULL, jamais zéro, et l'alerte affiche « saisie
-- manquante ». D'où les CASE autour de least() et greatest(), qui ignorent les NULL.
-- Rejouable : le schéma rapport est recréé en entier. Exécuté par pipeline.chargement, dans la même
-- transaction que le chargement, après schema.sql et plafonds.sql (seul : psql -1 -f sql/vues.sql).

DROP SCHEMA IF EXISTS rapport CASCADE;
CREATE SCHEMA rapport;

-- Versements de tous les comptes (achats PAC et ponctuels), sans les transferts entrants entre
-- institutions, qui ne consomment pas de droits. H1 : c'est le montant brut qui compte.
-- Plus les cotisations saisies hors export pour un compte connu (compte fermé, sans export) :
-- rang 0, nature « ponctuel » faute de détail, date approximative signalée dans la saisie.
-- periode : versement des 60 premiers jours de l'année civile ou non, borne R6 lue dans
-- ref.periode_reer (fin de l'année de déduction précédente). Seuls les versements REER de cette
-- période sont déductibles pour l'année précédente ; pour les autres régimes, c'est un repère.
CREATE VIEW rapport.versement AS
WITH v AS (
    SELECT t.compte_alias, t.date_negociation, t.rang, t.nature, t.montant_brut AS montant
    FROM fait.transaction t
    WHERE t.nature IN ('PAC', 'ponctuel')
      AND NOT EXISTS (SELECT 1 FROM ref.transfert_entrant e
                      WHERE e.compte_alias = t.compte_alias AND e.date_negociation = t.date_negociation
                        AND e.code_fonds = t.code_fonds AND e.montant = t.montant_brut)
    UNION ALL
    SELECT h.compte_alias, h.date_versement, 0, 'ponctuel', h.montant
    FROM ref.versement_hors_export h
    WHERE h.compte_alias IS NOT NULL
    UNION ALL
    -- Relevé saisi (Société 2) : retenues sur la paie, versements programmés, donc PAC
    SELECT compte_alias, date_versement, rang, 'PAC', montant
    FROM fait.releve_cotisation
)
SELECT v.compte_alias, c.genre AS regime, c.societe,
       v.date_negociation, date_trunc('month', v.date_negociation)::date AS mois,
       v.rang, v.nature, v.montant,
       extract(year FROM v.date_negociation)::smallint AS annee,
       CASE WHEN v.date_negociation <= p.fin THEN '60 premiers jours'
            -- Après mars, hors période même sans calendrier : 60ᵉ jour + report de week-end < 90 jours
            WHEN p.fin IS NULL AND extract(month FROM v.date_negociation) <= 3 THEN 'calendrier REER à compléter'
            ELSE 'Reste de l''année'
       END AS periode
FROM v
JOIN ref.compte c ON c.alias = v.compte_alias
LEFT JOIN ref.periode_reer p ON p.annee_deduction = extract(year FROM v.date_negociation) - 1;

-- Retraits de tous les comptes qui ont un alias, transferts directs déclarés exclus (R14) : ceux des exports, et les saisies hors export
-- rattachées à un compte (compte fermé). Montant positif. Un retrait CELI ne rend des droits que le
-- 1ᵉʳ janvier suivant (R3) : cette vue les montre, rapport.mouvement les compte.
CREATE VIEW rapport.retrait AS
SELECT t.compte_alias, c.genre AS regime, t.date_negociation AS date_retrait,
       t.montant_brut AS montant, extract(year FROM t.date_negociation)::smallint AS annee
FROM fait.transaction t
JOIN ref.compte c ON c.alias = t.compte_alias
WHERE t.nature = 'retrait'
  AND NOT EXISTS (SELECT 1 FROM ref.transfert_sortant e
                  WHERE e.compte_alias = t.compte_alias AND e.date_negociation = t.date_negociation
                    AND e.code_fonds = t.code_fonds AND e.montant = t.montant_brut)
UNION ALL
SELECT h.compte_alias, c.genre, h.date_retrait, h.montant, extract(year FROM h.date_retrait)::smallint
FROM ref.retrait_hors_export h
JOIN ref.compte c ON c.alias = h.compte_alias;

-- Mouvements des trois régimes : cotisations et retraits, des exports et hors export.
-- annee_droits = année civile, sauf REER : année de déduction (R6), soit la première période de
-- ref.periode_reer qui se termine à la date ou après ; NULL si la date dépasse le calendrier.
CREATE VIEW rapport.mouvement AS
WITH m AS (
    SELECT regime, compte_alias, date_negociation AS date_mouvement, rang, 'cotisation' AS sens, montant
    FROM rapport.versement
    WHERE regime IN ('CELI', 'CELIAPP', 'REER')
    UNION ALL
    SELECT c.genre, t.compte_alias, t.date_negociation, t.rang, 'retrait', t.montant_brut
    FROM fait.transaction t
    JOIN ref.compte c ON c.alias = t.compte_alias
    WHERE t.nature = 'retrait' AND c.genre IN ('CELI', 'CELIAPP', 'REER')
      AND NOT EXISTS (SELECT 1 FROM ref.transfert_sortant e   -- transfert direct, R14
                      WHERE e.compte_alias = t.compte_alias AND e.date_negociation = t.date_negociation
                        AND e.code_fonds = t.code_fonds AND e.montant = t.montant_brut)
    UNION ALL
    -- Hors export sans compte seulement : celles d'un compte connu sont déjà dans rapport.versement
    SELECT regime, NULL, date_versement, 0, 'cotisation', montant
    FROM ref.versement_hors_export
    WHERE compte_alias IS NULL
    UNION ALL
    SELECT regime, compte_alias, date_retrait, 0, 'retrait', montant
    FROM ref.retrait_hors_export
)
SELECT m.*,
       CASE WHEN m.regime = 'REER'
            THEN (SELECT p.annee_deduction FROM ref.periode_reer p
                  WHERE p.fin >= m.date_mouvement ORDER BY p.fin LIMIT 1)
            ELSE extract(year FROM m.date_mouvement)::smallint
       END AS annee_droits
FROM m;

-- Totaux par régime et par année de droits
CREATE VIEW rapport.total_annuel AS
SELECT regime, annee_droits AS annee,
       coalesce(sum(montant) FILTER (WHERE sens = 'cotisation'), 0) AS cotisations,
       coalesce(sum(montant) FILTER (WHERE sens = 'retrait'), 0) AS retraits
FROM rapport.mouvement
WHERE annee_droits IS NOT NULL
GROUP BY regime, annee_droits;

-- CELI. R1, R5a : plafonds cumulés depuis la première année de résidence (NULL s'il en manque
-- un). R3 : moins les cotisations des années passées, plus leurs retraits ; un retrait de
-- l'année ne rend rien avant le 1ᵉʳ janvier suivant. R2 : tous les CELI ensemble.
CREATE VIEW rapport.droits_celi AS
WITH premiere AS (
    SELECT valeur AS annee FROM ref.parametre WHERE cle = 'celi_premiere_annee'
),
annees AS (
    SELECT generate_series(min(annee), extract(year FROM current_date)::int)::smallint AS annee
    FROM rapport.total_annuel WHERE regime = 'CELI'
),
cumul AS (
    SELECT a.annee,
           CASE WHEN count(pl.annee) = a.annee - min(pr.annee) + 1 THEN sum(pl.montant) END AS plafonds
    FROM annees a
    CROSS JOIN premiere pr
    LEFT JOIN ref.plafond pl
           ON pl.regime = 'CELI' AND pl.rubrique = 'plafond_annuel' AND pl.annee BETWEEN pr.annee AND a.annee
    GROUP BY a.annee
)
SELECT 'CELI'::text AS regime, a.annee,
       c.plafonds - coalesce(p.cotisations, 0) + coalesce(p.retraits, 0) AS droits_debut,
       coalesce(t.cotisations, 0) AS cotisations, coalesce(t.retraits, 0) AS retraits
FROM annees a
LEFT JOIN cumul c USING (annee)
LEFT JOIN rapport.total_annuel t ON t.regime = 'CELI' AND t.annee = a.annee
LEFT JOIN LATERAL (SELECT sum(x.cotisations) AS cotisations, sum(x.retraits) AS retraits
                   FROM rapport.total_annuel x
                   WHERE x.regime = 'CELI' AND x.annee < a.annee) p ON true;

-- CELIAPP, année civile (R11), calcul récursif d'une année sur l'autre.
-- R8 : l'année d'ouverture, le plafond annuel. Ensuite, le plus petit de :
--   R9  plafond annuel + report des droits inutilisés (borné à report_max) − excédent de l'année précédente ;
--   R10 plafond à vie − tout ce qui a été versé avant + excédent de l'année précédente.
-- Non traités, faute de cas : retraits désignés et droits de participation rétablis.
CREATE VIEW rapport.droits_celiapp AS
WITH RECURSIVE limites AS (
    SELECT (SELECT montant FROM ref.plafond WHERE regime = 'CELIAPP' AND rubrique = 'report_max') AS report_max,
           (SELECT montant FROM ref.plafond WHERE regime = 'CELIAPP' AND rubrique = 'plafond_vie') AS plafond_vie
),
base AS (
    SELECT a.annee::smallint AS annee, pl.montant AS plafond,
           coalesce(t.cotisations, 0) AS cotisations, coalesce(t.retraits, 0) AS retraits
    FROM ref.parametre o
    CROSS JOIN generate_series(o.valeur, extract(year FROM current_date)::int) AS a (annee)
    LEFT JOIN ref.plafond pl ON pl.regime = 'CELIAPP' AND pl.rubrique = 'plafond_annuel' AND pl.annee = a.annee
    LEFT JOIN rapport.total_annuel t ON t.regime = 'CELIAPP' AND t.annee = a.annee
    WHERE o.cle = 'celiapp_ouverture'
),
d AS (
    SELECT b.annee,
           CASE WHEN b.plafond IS NOT NULL AND l.plafond_vie IS NOT NULL
                THEN least(b.plafond, l.plafond_vie)::numeric END AS droits_debut,
           b.cotisations, b.retraits, 0::numeric AS verse_avant
    FROM base b CROSS JOIN limites l
    WHERE b.annee = (SELECT min(annee) FROM base)
    UNION ALL
    SELECT b.annee,
           CASE WHEN b.plafond IS NOT NULL AND l.report_max IS NOT NULL AND l.plafond_vie IS NOT NULL
                     AND d.droits_debut IS NOT NULL
                THEN least(b.plafond + least(l.report_max, greatest(d.droits_debut - d.cotisations, 0))
                                     - greatest(d.cotisations - d.droits_debut, 0),
                           l.plafond_vie - (d.verse_avant + d.cotisations)
                                         + greatest(d.cotisations - d.droits_debut, 0)) END,
           b.cotisations, b.retraits, d.verse_avant + d.cotisations
    FROM d
    JOIN base b ON b.annee = d.annee + 1
    CROSS JOIN limites l
)
SELECT 'CELIAPP'::text AS regime, annee, droits_debut, cotisations, retraits FROM d;

-- REER, par année de déduction (R6). Droits disponibles = maximum déductible − cotisations
-- inutilisées (H3, R13). Les inutilisées de la première année viennent de l'avis ; les suivantes
-- sont reconstruites : inutilisées + cotisations de la période − déduction demandée (ligne 20800).
-- inutilisees_avis reste à côté pour le contrôle C2.
CREATE VIEW rapport.droits_reer AS
WITH RECURSIVE base AS (
    SELECT a.annee::smallint AS annee, v.maximum_deductible, v.cotisations_inutilisees AS inutilisees_avis,
           v.deduction_20800, coalesce(t.cotisations, 0) AS cotisations, coalesce(t.retraits, 0) AS retraits
    FROM (SELECT min(annee) AS debut
          FROM (SELECT annee_deduction AS annee FROM ref.reer_avis
                UNION ALL SELECT annee FROM rapport.total_annuel WHERE regime = 'REER') u) s
    CROSS JOIN generate_series(s.debut, extract(year FROM current_date)::int) AS a (annee)
    LEFT JOIN ref.reer_avis v ON v.annee_deduction = a.annee
    LEFT JOIN rapport.total_annuel t ON t.regime = 'REER' AND t.annee = a.annee
),
r AS (
    SELECT b.*, b.inutilisees_avis::numeric AS inutilisees
    FROM base b WHERE b.annee = (SELECT min(annee) FROM base)
    UNION ALL
    SELECT b.*, r.inutilisees + r.cotisations - r.deduction_20800
    FROM r JOIN base b ON b.annee = r.annee + 1
)
SELECT 'REER'::text AS regime, annee, maximum_deductible - inutilisees AS droits_debut,
       cotisations, retraits, maximum_deductible, inutilisees, inutilisees_avis
FROM r;

-- Les trois régimes. droits_restants négatif = excédent en fin de période.
CREATE VIEW rapport.droits AS
SELECT regime, annee, droits_debut, cotisations, retraits, droits_debut - cotisations AS droits_restants
FROM rapport.droits_celi
UNION ALL
SELECT regime, annee, droits_debut, cotisations, retraits, droits_debut - cotisations FROM rapport.droits_celiapp
UNION ALL
SELECT regime, annee, droits_debut, cotisations, retraits, droits_debut - cotisations FROM rapport.droits_reer;

-- Excédent après chaque mouvement, dans l'ordre des dates (cotisations d'abord à date égale :
-- l'ordre prudent). Une cotisation consomme d'abord les droits, le reste devient excédent.
-- Un retrait CELI réduit l'excédent sans rendre de droits dans l'année (R3, R4) ; les retraits
-- CELIAPP et REER ne changent rien ici. n = 0 : état au début de l'année.
CREATE VIEW rapport.excedent AS
WITH RECURSIVE ev AS (
    SELECT m.regime, m.annee_droits AS annee, m.date_mouvement, m.sens, m.montant,
           row_number() OVER (PARTITION BY m.regime, m.annee_droits
                              ORDER BY m.date_mouvement, m.sens, m.compte_alias, m.rang) AS n
    FROM rapport.mouvement m
    WHERE m.annee_droits IS NOT NULL AND (m.sens = 'cotisation' OR m.regime = 'CELI')
),
etat AS (
    SELECT d.regime, d.annee, 0::bigint AS n, NULL::date AS date_mouvement,
           greatest(d.droits_debut, 0) AS droits, greatest(-d.droits_debut, 0) AS excedent
    FROM rapport.droits d
    WHERE d.droits_debut IS NOT NULL
    UNION ALL
    SELECT e.regime, e.annee, ev.n, ev.date_mouvement,
           CASE WHEN ev.sens = 'cotisation' THEN greatest(e.droits - ev.montant, 0) ELSE e.droits END,
           CASE WHEN ev.sens = 'cotisation' THEN e.excedent + greatest(ev.montant - e.droits, 0)
                ELSE greatest(e.excedent - ev.montant, 0) END
    FROM etat e
    JOIN ev ON ev.regime = e.regime AND ev.annee = e.annee AND ev.n = e.n + 1
)
SELECT * FROM etat;

-- Alerte par régime et par année. CELI (R4) et CELIAPP (R12) : alerte dès le premier dollar.
-- REER (R7) : avertissement jusqu'à la marge, alerte au-delà.
CREATE VIEW rapport.alerte AS
WITH x AS (
    SELECT regime, annee, max(excedent) AS excedent_max,
           min(coalesce(date_mouvement, make_date(annee, 1, 1))) FILTER (WHERE excedent > 0) AS premier_depassement
    FROM rapport.excedent
    GROUP BY regime, annee
),
dernier AS (
    SELECT DISTINCT ON (regime, annee) regime, annee, excedent AS excedent_actuel
    FROM rapport.excedent
    ORDER BY regime, annee, n DESC
),
hors_calendrier AS (
    SELECT count(*) AS n FROM rapport.mouvement WHERE regime = 'REER' AND annee_droits IS NULL
),
marge AS (
    SELECT montant FROM ref.plafond WHERE regime = 'REER' AND rubrique = 'marge_excedent'
)
SELECT d.regime, d.annee, d.droits_debut, d.cotisations, d.retraits, d.droits_restants,
       x.excedent_max, dn.excedent_actuel, x.premier_depassement,
       CASE
           WHEN d.regime = 'REER' AND (SELECT n FROM hors_calendrier) > 0 THEN 'calendrier REER à compléter'
           WHEN d.droits_debut IS NULL THEN 'saisie manquante'
           WHEN d.regime = 'REER' AND (SELECT montant FROM marge) IS NULL THEN 'saisie manquante'
           WHEN d.regime = 'REER' AND x.excedent_max > (SELECT montant FROM marge) THEN 'alerte'
           WHEN d.regime = 'REER' AND x.excedent_max > 0 THEN 'avertissement'
           WHEN x.excedent_max > 0 THEN 'alerte'
           ELSE 'aucune'
       END AS niveau
FROM rapport.droits d
LEFT JOIN x USING (regime, annee)
LEFT JOIN dernier dn USING (regime, annee);

-- Dimensions du rapport. Le compte sans son numéro : le rapport ne voit que l'alias.
-- statut : « Actif » ou « Fermé en AAAA » (année de ferme_le, saisie dans comptes.csv).
CREATE VIEW rapport.compte AS
SELECT alias AS compte_alias, genre AS regime, coalesce(societe, 'non attribuée') AS societe,
       CASE WHEN ferme_le IS NULL THEN 'Actif'
            ELSE 'Fermé en ' || extract(year FROM ferme_le)::int END AS statut,
       -- Ordre d'affichage des régimes : enregistrés d'abord, non enregistré en dernier
       CASE genre WHEN 'CELI' THEN 1 WHEN 'CELIAPP' THEN 2 WHEN 'REER' THEN 3 ELSE 4 END AS ordre_regime
FROM ref.compte;

-- R15. Date d'arrêté du rapport : la plus ancienne des dates de fin des derniers Historiques
-- chargés et des derniers relevés saisis. Un compte en retard retarde tout le rapport : aucun mois
-- n'apparaît à moitié chargé. Une ligne ; aucune avant le premier chargement.
CREATE VIEW rapport.arrete AS
SELECT min(fin) AS date_arrete
FROM (SELECT fin FROM fait.historique
      UNION ALL
      SELECT max(fin) FROM fait.releve GROUP BY compte_alias) f
HAVING count(*) > 0;

-- Années présentes dans les droits ou dans les versements, plus l'année de la date d'arrêté (R15),
-- pour que « En cours » existe avant le premier versement de l'année.
-- periode : libellé du segment Année. « En cours » pour l'année de la date d'arrêté (R15) :
-- la sélection enregistrée sur ce libellé passe seule à l'année suivante.
CREATE VIEW rapport.annee AS
SELECT a.annee,
       CASE WHEN a.annee = extract(year FROM r.date_arrete) THEN 'En cours' ELSE a.annee::text END AS periode
FROM (SELECT annee FROM rapport.droits
      UNION
      SELECT annee FROM rapport.versement
      UNION
      SELECT annee FROM rapport.retrait
      UNION
      SELECT extract(year FROM date_arrete)::smallint FROM rapport.arrete) a
     LEFT JOIN rapport.arrete r ON true;

-- Calendrier : un jour par ligne, du 1ᵉʳ janvier de la première année au 31 décembre de la
-- dernière année de rapport.annee, pour que chaque jour ait son année dans la table Année du modèle.
-- Table de dates du modèle (axe des mois, futur TWR mensuel). Mois = premier jour du mois.
-- mois_ecoule : mois antérieur ou égal au mois de la date d'arrêté (R15) ; les KPI s'arrêtent là.
CREATE VIEW rapport.calendrier AS
SELECT j::date AS date,
       extract(year FROM j)::smallint AS annee,
       date_trunc('month', j)::date AS mois,
       extract(month FROM j)::smallint AS numero_mois,
       'T' || extract(quarter FROM j) AS trimestre,
       coalesce(date_trunc('month', j) <= date_trunc('month', r.date_arrete), false) AS mois_ecoule
FROM (SELECT min(annee) AS premiere, max(annee) AS derniere FROM rapport.annee) b
     CROSS JOIN LATERAL generate_series(make_date(b.premiere, 1, 1), make_date(b.derniere, 12, 31),
                                        interval '1 day') AS j
     LEFT JOIN rapport.arrete r ON true;

-- Part mensuelle des versements, tous comptes : dans le total du mois, et dans le total de la
-- même nature (PAC ou ponctuel) du mois.
CREATE VIEW rapport.part_mensuelle AS
SELECT mois, compte_alias, regime, societe, nature, sum(montant) AS montant,
       sum(montant) / sum(sum(montant)) OVER (PARTITION BY mois) AS part_du_mois,
       sum(montant) / sum(sum(montant)) OVER (PARTITION BY mois, nature) AS part_de_la_nature
FROM rapport.versement
GROUP BY mois, compte_alias, regime, societe, nature;

-- ============================================================================================
-- Performance (itération 4). Règles P1 à P9 : docs/regles-performance.md. Comptes avec export
-- seulement : une saisie hors export n'a pas de valeur marchande (P4).
-- ============================================================================================

-- P1 : un point de valorisation par compte et par mois, la dernière date de frais de gestion ou de
-- Rapport du mois ; à date égale, le Rapport (VM exacte) l'emporte ('rapport' > 'frais').
CREATE VIEW rapport.point AS
SELECT DISTINCT ON (compte_alias, mois) compte_alias, mois, date_point, source
FROM (SELECT compte_alias, date_trunc('month', date_negociation)::date AS mois,
             date_negociation AS date_point, 'frais' AS source
      FROM fait.transaction WHERE nature = 'frais'
      UNION
      SELECT compte_alias, date_trunc('month', date_valorisation)::date, date_valorisation, 'rapport'
      FROM fait.sommaire) d
ORDER BY compte_alias, mois, date_point DESC, source DESC;

-- P2 : valeur marchande par fonds au point. Rapport : la ligne du Sommaire. Frais : parts restantes
-- après la dernière transaction du fonds à la date du point (rang départage une même journée), au
-- prix de cette transaction, arrondi au cent par fonds. perime : prix de plus de 31 jours.
CREATE VIEW rapport.valorisation AS
SELECT p.compte_alias, p.mois, p.date_point, p.source, f.code_fonds, f.parts, f.prix, f.date_prix,
       f.valeur_marchande, p.date_point - f.date_prix > 31 AS perime
FROM rapport.point p
CROSS JOIN LATERAL (
    SELECT s.code_fonds, s.nb_actions AS parts, s.prix_action AS prix, s.date_valorisation AS date_prix,
           s.valeur_marchande
    FROM fait.sommaire s
    WHERE p.source = 'rapport' AND s.compte_alias = p.compte_alias AND s.date_valorisation = p.date_point
    UNION ALL
    SELECT t.code_fonds, t.parts_restantes, t.prix_part, t.date_negociation,
           round(t.parts_restantes * t.prix_part, 2)
    FROM (SELECT DISTINCT ON (t.code_fonds) t.code_fonds, t.parts_restantes, t.prix_part, t.date_negociation
          FROM fait.transaction t
          WHERE t.compte_alias = p.compte_alias AND t.date_negociation <= p.date_point
          ORDER BY t.code_fonds, t.date_negociation DESC, t.rang DESC) t
    WHERE p.source = 'frais' AND t.parts_restantes <> 0
) f;

-- P3 à P6 et P9, par compte et par mois. Sous-période : du point du mois précédent (exclu) au point
-- du mois (inclus). Premier mois : depuis la veille de la première transaction, VM début = 0.
CREATE VIEW rapport.performance AS
WITH vm AS (
    SELECT compte_alias, mois, date_point, sum(valeur_marchande) AS vm
    FROM rapport.valorisation
    GROUP BY compte_alias, mois, date_point
),
periode AS (
    SELECT v.compte_alias, v.mois,
           coalesce(lag(v.date_point) OVER w, o.ouverture - 1) AS date_debut, v.date_point AS date_fin,
           coalesce(lag(v.vm) OVER w, 0) AS vm_debut, v.vm AS vm_fin
    FROM vm v
    JOIN (SELECT compte_alias, min(date_negociation) AS ouverture
          FROM fait.transaction GROUP BY compte_alias) o USING (compte_alias)
    WINDOW w AS (PARTITION BY v.compte_alias ORDER BY v.date_point)
),
m AS (
    SELECT p.compte_alias, p.mois,
           -- P3 : flux externes au brut
           coalesce(sum(t.montant_brut) FILTER (WHERE t.nature IN ('PAC', 'ponctuel')), 0) AS versements,
           coalesce(sum(t.montant_brut) FILTER (WHERE t.nature = 'retrait'), 0) AS retraits,
           -- P9 : frais de gestion au brut (taxes incluses) + déductions sur achats
           coalesce(sum(t.montant_brut) FILTER (WHERE t.nature = 'frais'), 0)
             + coalesce(sum(t.deductions) FILTER (WHERE t.nature IN ('PAC', 'ponctuel')), 0) AS frais,
           coalesce(sum(t.montant_brut) FILTER (WHERE t.nature = 'revenu'), 0) AS distributions,
           -- P6 : Σ wᵢ·Fᵢ, wᵢ = part de la sous-période qui reste après le flux (0 le jour du point)
           coalesce(sum(CASE t.nature WHEN 'retrait' THEN -t.montant_brut ELSE t.montant_brut END
                        * (p.date_fin - t.date_negociation) / (p.date_fin - p.date_debut)::numeric)
                    FILTER (WHERE t.nature IN ('PAC', 'ponctuel', 'retrait')), 0) AS flux_pondere
    FROM periode p
    LEFT JOIN fait.transaction t
           ON t.compte_alias = p.compte_alias
          AND t.date_negociation > p.date_debut AND t.date_negociation <= p.date_fin
    GROUP BY p.compte_alias, p.mois
),
-- P17 : compte à relevé saisi (Société 2). Une sous-période par période du relevé, de la veille de
-- l'ouverture (exclue) au gain (inclus) ; VM début = solde d'ouverture, VM fin = clôture. Frais du
-- fonds compris dans le gain, donc frais et distributions à 0 ; gain = variation de prix. Capital
-- net : cotisations hors export du compte antérieures au relevé, plus les cotisations du relevé.
releve AS (
    SELECT r.compte_alias, r.debut - 1 AS date_debut, r.fin AS date_fin, r.ouverture, r.gain, r.cloture,
           coalesce(c.versements, 0) AS versements, coalesce(c.flux_pondere, 0) AS flux_pondere,
           coalesce((SELECT sum(h.montant) FROM ref.versement_hors_export h
                     WHERE h.compte_alias = r.compte_alias
                       AND h.date_versement < (SELECT min(x.debut) FROM fait.releve x
                                               WHERE x.compte_alias = r.compte_alias)), 0) AS capital_initial
    FROM fait.releve r
    LEFT JOIN (SELECT c.compte_alias, c.debut, sum(c.montant) AS versements,
                      sum(c.montant * (r.fin - c.date_versement) / (r.fin - r.debut + 1)::numeric) AS flux_pondere
               FROM fait.releve_cotisation c
               JOIN fait.releve r USING (compte_alias, debut)
               GROUP BY c.compte_alias, c.debut) c USING (compte_alias, debut)
)
SELECT p.compte_alias, p.mois, extract(year FROM p.mois)::smallint AS annee, p.date_debut, p.date_fin,
       p.vm_debut, p.vm_fin, m.versements, m.retraits, m.versements - m.retraits AS flux, m.frais,
       m.distributions,
       -- Terme qui ferme la cascade : VM fin − VM début − flux + frais − distributions
       p.vm_fin - p.vm_debut - (m.versements - m.retraits) + m.frais - m.distributions AS variation_prix,
       sum(m.versements - m.retraits) OVER c AS capital_net,                -- P4
       p.vm_fin - sum(m.versements - m.retraits) OVER c AS gain_net,        -- P5
       p.vm_fin - p.vm_debut - (m.versements - m.retraits) AS numerateur,   -- P6
       p.vm_debut + m.flux_pondere AS denominateur,
       (p.vm_fin - p.vm_debut - (m.versements - m.retraits)) / nullif(p.vm_debut + m.flux_pondere, 0) AS rendement
FROM periode p
JOIN m USING (compte_alias, mois)
WINDOW c AS (PARTITION BY p.compte_alias ORDER BY p.date_fin)
UNION ALL
SELECT r.compte_alias, date_trunc('month', r.date_fin)::date, extract(year FROM r.date_fin)::smallint,
       r.date_debut, r.date_fin, r.ouverture, r.cloture, r.versements, 0, r.versements, 0, 0,
       r.gain,
       r.capital_initial + sum(r.versements) OVER c,
       r.cloture - r.capital_initial - sum(r.versements) OVER c,
       r.gain,
       r.ouverture + r.flux_pondere,
       r.gain / nullif(r.ouverture + r.flux_pondere, 0)
FROM releve r
WINDOW c AS (PARTITION BY r.compte_alias ORDER BY r.date_fin);

-- P8 : Dietz de l'agrégat, mois par mois (somme des numérateurs ÷ somme des dénominateurs)
CREATE VIEW rapport.performance_globale AS
SELECT mois, annee, sum(vm_debut) AS vm_debut, sum(vm_fin) AS vm_fin, sum(versements) AS versements,
       sum(retraits) AS retraits, sum(frais) AS frais, sum(distributions) AS distributions,
       sum(capital_net) AS capital_net, sum(gain_net) AS gain_net,
       sum(numerateur) AS numerateur, sum(denominateur) AS denominateur,
       sum(numerateur) / nullif(sum(denominateur), 0) AS rendement
FROM rapport.performance
GROUP BY mois, annee;

-- P7, P8, P9 : TWR et taux de frais annualisé de l'année, par compte et global (compte_alias vide).
-- Un mois au rendement vide (dénominateur nul) compte pour 0 %, comme 1 + BLANK en DAX.
CREATE VIEW rapport.rendement_annuel AS
WITH x AS (
    SELECT compte_alias, annee, rendement, frais, vm_fin FROM rapport.performance
    UNION ALL
    SELECT NULL, annee, rendement, frais, vm_fin FROM rapport.performance_globale
)
SELECT compte_alias, annee, count(*) AS points,
       exp(sum(ln(1 + coalesce(rendement, 0)))) - 1 AS twr,
       sum(frais) AS frais, avg(vm_fin) AS vm_moyenne,
       sum(frais) / nullif(avg(vm_fin), 0) * 12 / count(*) AS taux_frais
FROM x
GROUP BY compte_alias, annee;

-- Cascade de l'année par compte : VM au dernier point de l'année précédente, puis les termes de
-- sa variation ; leur somme (total du visuel en cascade) est la VM au dernier point de l'année.
CREATE VIEW rapport.cascade AS
WITH a AS (
    SELECT compte_alias, annee, (array_agg(vm_debut ORDER BY date_fin))[1] AS vm_debut,
           sum(versements) AS versements, sum(retraits) AS retraits, sum(frais) AS frais,
           sum(distributions) AS distributions, sum(variation_prix) AS variation_prix
    FROM rapport.performance
    GROUP BY compte_alias, annee
)
SELECT a.compte_alias, a.annee, e.ordre, e.etape, e.montant
FROM a
CROSS JOIN LATERAL (VALUES (1, 'VM au début', a.vm_debut), (2, 'Versements', a.versements),
                           (3, 'Retraits', -a.retraits), (4, 'Frais', -a.frais),
                           (5, 'Distributions', a.distributions), (6, 'Variation de prix', a.variation_prix)
                   ) AS e (ordre, etape, montant);

-- ============================================================================================
-- Stratégie (itération 5). Règles S1 à S6 : docs/regles-strategie.md. Composition publique des
-- fonds (pub.*, profils mensuels de la Société 1) pondérée par la VM des comptes (rapport.valorisation, P2).
-- ============================================================================================

-- Ordre d'affichage des catégories, un seul par libellé : « Revenu fixe » se trie de même en classe
-- et en style. Table Catégorie du modèle.
CREATE VIEW rapport.categorie AS
SELECT * FROM (VALUES
    ('Classe d''actif', 'Actions', 1), ('Classe d''actif', 'Revenu fixe', 5), ('Classe d''actif', 'Alternatifs', 6),
    ('Classe d''actif', 'Trésorerie', 7), ('Classe d''actif', 'Non ventilé', 9),
    ('Style', 'Dividendes', 2), ('Style', 'Croissance', 3), ('Style', 'Mixte', 4), ('Style', 'Revenu fixe', 5),
    ('Style', 'Alternatifs', 6), ('Style', 'Trésorerie', 7), ('Style', 'Non ventilé', 9),
    ('Géographie', 'Canada', 1), ('Géographie', 'États-Unis', 2), ('Géographie', 'Autres pays', 3),
    ('Géographie', 'Trésorerie et non ventilé', 8)
) AS c (axe, categorie, ordre);

-- S3 à S5 : poids de chaque fonds, par profil, axe et catégorie, ramenés à 1 par fonds et par axe (S2)
CREATE VIEW rapport.composition AS
WITH p AS (
    SELECT pr.code_fa, pr.date_donnees, pr.type_fonds LIKE 'Marché monétaire%' AS monetaire,
           EXISTS (SELECT 1 FROM pub.profil_ligne l WHERE (l.code_fa, l.date_donnees) = (pr.code_fa, pr.date_donnees)
                   AND l.section = 'actuelle') AS a_actuelle,
           EXISTS (SELECT 1 FROM pub.profil_ligne l WHERE (l.code_fa, l.date_donnees) = (pr.code_fa, pr.date_donnees)
                   AND l.section = 'actif') AS a_actif,
           EXISTS (SELECT 1 FROM pub.profil_ligne l WHERE (l.code_fa, l.date_donnees) = (pr.code_fa, pr.date_donnees)
                   AND l.section = 'actif' AND l.parent = 'Actions') AS geo_actif
    FROM pub.profil pr
),
-- S3 : classes d'actif. Marché monétaire : 100 % Trésorerie. Portefeuilles : lignes de classe de la
-- répartition actuelle (jamais la cible). Fonds d'actions : répartition de l'actif ; à défaut, la
-- ligne de trésorerie de la répartition sectorielle, le reste en actions.
classe_brute AS (
    SELECT code_fa, date_donnees, 'Trésorerie' AS categorie, 100::numeric AS poids FROM p WHERE monetaire
    UNION ALL
    SELECT l.code_fa, l.date_donnees,
           CASE l.libelle WHEN 'Titres à revenu fixe' THEN 'Revenu fixe' WHEN 'Actions' THEN 'Actions'
                          WHEN 'Alternatifs' THEN 'Alternatifs' ELSE 'Trésorerie' END, l.poids
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND p.a_actuelle AND l.section = 'actuelle' AND l.parent IS NULL
    UNION ALL
    SELECT l.code_fa, l.date_donnees, CASE l.libelle WHEN 'Actions' THEN 'Actions' ELSE 'Trésorerie' END, l.poids
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND NOT p.a_actuelle AND p.a_actif AND l.section = 'actif' AND l.parent IS NULL
    UNION ALL
    SELECT l.code_fa, l.date_donnees, CASE WHEN l.libelle LIKE 'Trésorerie%' THEN 'Trésorerie' ELSE 'Actions' END,
           l.poids
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND NOT p.a_actuelle AND NOT p.a_actif AND l.section = 'secteur'
),
classe AS (
    SELECT code_fa, date_donnees, categorie,
           sum(poids) / sum(sum(poids)) OVER (PARTITION BY code_fa, date_donnees) AS poids
    FROM classe_brute GROUP BY code_fa, date_donnees, categorie
),
tresorerie AS (
    SELECT p.code_fa, p.date_donnees, coalesce(c.poids, 0) AS part
    FROM p LEFT JOIN classe c ON (c.code_fa, c.date_donnees, c.categorie) = (p.code_fa, p.date_donnees, 'Trésorerie')
),
-- S4 : géographie. Marché monétaire : trésorerie. Fonds d'actions dont la répartition de l'actif
-- détaille les actions par pays : ces sous-postes, plus la trésorerie. Sinon : la répartition par
-- pays ou par région, publiée hors trésorerie, étalée sur la part non investie en trésorerie (S3).
geo_brute AS (
    SELECT code_fa, date_donnees, 'Trésorerie et non ventilé' AS categorie, 1::numeric AS poids FROM p WHERE monetaire
    UNION ALL
    SELECT l.code_fa, l.date_donnees, g.categorie, l.poids / 100
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees) JOIN ref.geographie g USING (libelle)
    WHERE NOT p.monetaire AND p.geo_actif AND l.section = 'actif' AND l.parent = 'Actions'
    UNION ALL
    SELECT l.code_fa, l.date_donnees, 'Trésorerie et non ventilé', l.poids / 100
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND p.geo_actif AND l.section = 'actif' AND l.parent IS NULL AND l.libelle <> 'Actions'
    UNION ALL
    SELECT l.code_fa, l.date_donnees, g.categorie,
           l.poids / sum(l.poids) OVER (PARTITION BY l.code_fa, l.date_donnees) * (1 - t.part)
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees) JOIN ref.geographie g USING (libelle)
    JOIN tresorerie t USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND NOT p.geo_actif AND l.section = 'pays'
    UNION ALL
    SELECT t.code_fa, t.date_donnees, 'Trésorerie et non ventilé', t.part
    FROM tresorerie t JOIN p USING (code_fa, date_donnees)
    WHERE NOT p.monetaire AND NOT p.geo_actif
),
-- S5 : style. Portefeuilles : chaque fonds sous-jacent de la répartition actuelle, classé par
-- ref.style. Autres fonds : les classes S3, la part en actions prenant le style du fonds.
style_brute AS (
    SELECT l.code_fa, l.date_donnees, s.style AS categorie, l.poids
    FROM pub.profil_ligne l JOIN p USING (code_fa, date_donnees)
    JOIN ref.style s ON s.type = 'sous-jacent' AND s.cle = l.libelle
    WHERE p.a_actuelle AND NOT p.monetaire AND l.section = 'actuelle' AND l.parent IS NOT NULL
    UNION ALL
    SELECT c.code_fa, c.date_donnees, CASE c.categorie WHEN 'Actions' THEN s.style ELSE c.categorie END, c.poids
    FROM classe c JOIN p USING (code_fa, date_donnees)
    JOIN ref.style s ON s.type = 'fonds' AND s.cle = c.code_fa
    WHERE NOT p.a_actuelle OR p.monetaire
),
axes AS (
    SELECT 'Classe d''actif' AS axe, code_fa, date_donnees, categorie, poids FROM classe
    UNION ALL
    SELECT 'Géographie', code_fa, date_donnees, categorie, sum(poids) FROM geo_brute GROUP BY 2, 3, 4
    UNION ALL
    SELECT 'Style', code_fa, date_donnees, categorie, sum(poids) FROM style_brute GROUP BY 2, 3, 4
)
SELECT axe, code_fa, date_donnees, categorie,
       poids / sum(poids) OVER (PARTITION BY axe, code_fa, date_donnees) AS poids
FROM axes;

-- S1 : profil applicable à chaque fonds détenu, à chaque point : le dernier profil dont la date
-- de données précède ou égale le point. Sans profil : date_profil vide (S2, « Non ventilé »).
-- dernier : le point est le dernier du compte. cle_fonds (S7) : le code FA, ou le code détenu sans profil.
CREATE VIEW rapport.valorisation_profil AS
SELECT v.compte_alias, v.mois, v.date_point, v.code_fonds, v.valeur_marchande, c.code_fa,
       coalesce(c.code_fa, v.code_fonds) AS cle_fonds,
       (SELECT max(pr.date_donnees) FROM pub.profil pr
        WHERE pr.code_fa = c.code_fa AND pr.date_donnees <= v.date_point) AS date_profil,
       v.date_point = (SELECT max(p.date_point) FROM rapport.point p WHERE p.compte_alias = v.compte_alias) AS dernier
FROM rapport.valorisation v
LEFT JOIN pub.profil_code c USING (code_fonds);

-- S2 : exposition = Σ VM × poids, par compte, point, fonds (S7), axe et catégorie. La somme des
-- catégories d'un axe égale la VM du compte au point.
CREATE VIEW rapport.exposition AS
WITH e AS (
    SELECT v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds AS code_fa, c.axe, c.categorie,
           v.valeur_marchande * c.poids AS montant
    FROM rapport.valorisation_profil v
    JOIN rapport.composition c ON (c.code_fa, c.date_donnees) = (v.code_fa, v.date_profil)
    UNION ALL
    SELECT v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds, a.axe,
           CASE a.axe WHEN 'Géographie' THEN 'Trésorerie et non ventilé' ELSE 'Non ventilé' END, v.valeur_marchande
    FROM rapport.valorisation_profil v
    CROSS JOIN (VALUES ('Classe d''actif'), ('Style'), ('Géographie')) AS a (axe)
    WHERE v.date_profil IS NULL
)
-- montant arrondi au millionième de dollar : un numeric à très grande échelle (poids géographiques)
-- peut dépasser le décimal du pilote de Power BI, qui le reçoit alors vide
SELECT e.compte_alias, e.mois, e.date_point, e.dernier, e.code_fa, e.axe, e.categorie, c.ordre,
       round(sum(e.montant), 6) AS montant
FROM e
JOIN rapport.categorie c USING (axe, categorie)
GROUP BY e.compte_alias, e.mois, e.date_point, e.dernier, e.code_fa, e.axe, e.categorie, c.ordre;

-- S6 : par compte et par point, VM couverte par un profil et Σ VM × RFG (RFG pondéré =
-- vm_rfg ÷ vm_profil), et dates des profils appliqués.
CREATE VIEW rapport.cout AS
SELECT v.compte_alias, v.mois, v.date_point, v.dernier, sum(v.valeur_marchande) AS vm,
       coalesce(sum(v.valeur_marchande) FILTER (WHERE v.date_profil IS NOT NULL), 0) AS vm_profil,
       round(coalesce(sum(v.valeur_marchande * pr.rfg / 100), 0), 6) AS vm_rfg,
       min(v.date_profil) AS premier_profil, max(v.date_profil) AS dernier_profil
FROM rapport.valorisation_profil v
LEFT JOIN pub.profil pr ON (pr.code_fa, pr.date_donnees) = (v.code_fa, v.date_profil)
GROUP BY v.compte_alias, v.mois, v.date_point, v.dernier;

-- S6 : coût de la stratégie au dernier point, global, par régime et par compte. RFG pondéré + taux
-- de frais de gestion de l'année du dernier point (P9, calculé comme la mesure DAX : frais × 12 ÷
-- (moyenne des VM mensuelles du périmètre × nombre de mois)).
CREATE VIEW rapport.cout_perimetre AS
WITH annee AS (SELECT max(annee) AS annee FROM rapport.performance),
c AS (
    SELECT c.*, k.genre AS regime FROM rapport.cout c JOIN ref.compte k ON k.alias = c.compte_alias WHERE c.dernier
),
r AS (
    SELECT CASE WHEN grouping(regime) = 1 THEN 'global' WHEN grouping(compte_alias) = 1 THEN 'régime' ELSE 'compte' END
               AS niveau,
           CASE WHEN grouping(regime) = 1 THEN 'global' WHEN grouping(compte_alias) = 1 THEN regime ELSE compte_alias END
               AS perimetre,
           sum(vm_rfg) / nullif(sum(vm_profil), 0) AS rfg_pondere
    FROM c GROUP BY GROUPING SETS ((), (regime), (regime, compte_alias))
),
pm AS (   -- P9 par périmètre : mois de l'année, VM et frais du mois sommés sur les comptes
    SELECT CASE WHEN grouping(k.genre) = 1 THEN 'global' WHEN grouping(p.compte_alias) = 1 THEN k.genre
                ELSE p.compte_alias END AS perimetre,
           p.mois, sum(p.vm_fin) AS vm, sum(p.frais) AS frais
    FROM rapport.performance p JOIN ref.compte k ON k.alias = p.compte_alias CROSS JOIN annee a
    WHERE p.annee = a.annee
    GROUP BY GROUPING SETS ((p.mois), (k.genre, p.mois), (k.genre, p.compte_alias, p.mois))
),
f AS (
    SELECT perimetre, sum(frais) * 12 / nullif(avg(vm) * count(*), 0) AS taux_frais FROM pm GROUP BY perimetre
)
SELECT r.niveau, r.perimetre, r.rfg_pondere, f.taux_frais, r.rfg_pondere + f.taux_frais AS cout_total
FROM r LEFT JOIN f USING (perimetre);

-- S6 : actif agrégé du ménage chez chaque société au dernier point de chaque compte, tranche de frais
-- de gestion et distance au seuil de 100 000 $ : un seuil par société, chacune ayant ses propres
-- frais de gestion
CREATE VIEW rapport.seuil AS
SELECT k.societe, sum(c.vm) AS vm_menage,
       CASE WHEN sum(c.vm) >= 100000 THEN 'Plus de 100 000 $' ELSE 'Moins de 100 000 $' END AS tranche,
       greatest(100000 - sum(c.vm), 0) AS distance
FROM rapport.cout c JOIN ref.compte k ON k.alias = c.compte_alias
WHERE c.dernier
GROUP BY k.societe;

-- ============================================================================================
-- Fonds et risque (itération 6). Règles S7 à S10 : docs/regles-strategie.md.
-- ============================================================================================

-- S7 : dimension des fonds de fonds.csv. Type et niveau de risque : ceux du profil le plus récent,
-- pour l'affichage ; les mesures prennent le niveau du profil applicable à chaque point (S1, S8).
CREATE VIEW rapport.fonds AS
SELECT f.code_fa, f.nom_court, f.profil, f.ordre_profil, f.mandat,
       coalesce(p.type_fonds, 'Sans profil') AS type_fonds, coalesce(p.profil_risque, 'Non coté') AS risque,
       coalesce(r.rang, 9) AS ordre_risque
FROM ref.fonds f
LEFT JOIN LATERAL (SELECT pr.type_fonds, pr.profil_risque FROM pub.profil pr
                   WHERE pr.code_fa = f.code_fa ORDER BY pr.date_donnees DESC LIMIT 1) p ON true
LEFT JOIN ref.risque r ON r.libelle = p.profil_risque;

-- S8 : niveaux de risque, du plus faible au plus élevé, plus « Non coté » (fonds sans profil)
CREATE VIEW rapport.niveau_risque AS
SELECT libelle AS risque, rang AS ordre FROM ref.risque
UNION ALL
SELECT 'Non coté', 9;

-- S7, S8 : VM par compte, point et fonds (options de frais regroupées sous le code pivot), avec le
-- niveau de risque du profil applicable (S1). vm_rang = VM × rang et vm_cotee = VM, vides pour un
-- fonds « Non coté » : indice = Σ vm_rang ÷ Σ vm_cotee.
CREATE VIEW rapport.detention AS
SELECT v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds AS code_fa,
       coalesce(pr.profil_risque, 'Non coté') AS risque,
       sum(v.valeur_marchande) AS valeur_marchande,
       sum(v.valeur_marchande * r.rang) AS vm_rang,
       sum(v.valeur_marchande) FILTER (WHERE r.rang IS NOT NULL) AS vm_cotee
FROM rapport.valorisation_profil v
LEFT JOIN pub.profil pr ON (pr.code_fa, pr.date_donnees) = (v.code_fa, v.date_profil)
LEFT JOIN ref.risque r ON r.libelle = pr.profil_risque
GROUP BY v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds, coalesce(pr.profil_risque, 'Non coté');

-- S9 : répartition stratégique de chaque profil, dans les classes de S3, ramenée à 1. Section
-- « cible » si le profil en a une ; sinon la classe du type (Actions, ou Trésorerie pour un fonds de
-- marché monétaire). Un autre type sans cible est refusé par pipeline.profils.
CREATE VIEW rapport.cible AS
WITH c AS (
    SELECT l.code_fa, l.date_donnees,
           CASE l.libelle WHEN 'Titres à revenu fixe' THEN 'Revenu fixe' WHEN 'Actions' THEN 'Actions'
                          WHEN 'Alternatifs' THEN 'Alternatifs' ELSE 'Trésorerie' END AS categorie, l.poids
    FROM pub.profil_ligne l
    WHERE l.section = 'cible' AND l.parent IS NULL
    UNION ALL
    SELECT p.code_fa, p.date_donnees, CASE WHEN p.type_fonds LIKE 'Marché monétaire%' THEN 'Trésorerie' ELSE 'Actions' END,
           100
    FROM pub.profil p
    WHERE NOT EXISTS (SELECT 1 FROM pub.profil_ligne l
                      WHERE (l.code_fa, l.date_donnees) = (p.code_fa, p.date_donnees) AND l.section = 'cible')
)
SELECT code_fa, date_donnees, categorie, sum(poids) / sum(sum(poids)) OVER (PARTITION BY code_fa, date_donnees) AS poids
FROM c GROUP BY code_fa, date_donnees, categorie;

-- S9, S10 : par compte, point, fonds et classe d'actif : montant actuel (S2, S3), montant
-- stratégique (VM × poids cible, S9) et écart tactique = actuel − stratégique. Fonds sans profil :
-- « Non ventilé » des deux côtés, écart nul. La somme des écarts d'un périmètre est nulle.
CREATE VIEW rapport.ecart AS
WITH s AS (
    SELECT v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds AS code_fa, c.categorie,
           v.valeur_marchande * c.poids AS montant
    FROM rapport.valorisation_profil v
    JOIN rapport.cible c ON (c.code_fa, c.date_donnees) = (v.code_fa, v.date_profil)
    UNION ALL
    SELECT v.compte_alias, v.mois, v.date_point, v.dernier, v.cle_fonds, 'Non ventilé', v.valeur_marchande
    FROM rapport.valorisation_profil v
    WHERE v.date_profil IS NULL
),
strategique AS (
    SELECT compte_alias, mois, date_point, dernier, code_fa, categorie, round(sum(montant), 6) AS montant
    FROM s GROUP BY compte_alias, mois, date_point, dernier, code_fa, categorie
),
actuel AS (
    SELECT compte_alias, mois, date_point, dernier, code_fa, categorie, montant
    FROM rapport.exposition WHERE axe = 'Classe d''actif'
)
SELECT compte_alias, mois, date_point, dernier, code_fa, categorie, k.ordre,
       coalesce(a.montant, 0) AS actuel, coalesce(s.montant, 0) AS strategique,
       coalesce(a.montant, 0) - coalesce(s.montant, 0) AS ecart
FROM actuel a
FULL JOIN strategique s USING (compte_alias, mois, date_point, dernier, code_fa, categorie)
JOIN (SELECT categorie, ordre FROM rapport.categorie WHERE axe = 'Classe d''actif') k USING (categorie);

-- ============================================================================================
-- Risque mesuré et performance comparée (itération 7a). Règles P10 à P16 :
-- docs/regles-performance.md. Cours publics de Yahoo (pub.cours, pipeline.cours) ; parts,
-- distributions et prix de repli tirés des exports. Rendements en double précision.
-- ============================================================================================

-- P10 : prix quotidien de chaque fonds détenu (code FA, S7) : clôture Yahoo non ajustée ; à une date
-- sans cours Yahoo, le prix des exports (égal à Yahoo à 0,0001 $ près aux dates communes, contrôlé par
-- pipeline.cours). Une date sans aucun prix n'a pas de ligne : le rendement suivant couvre les deux jours.
CREATE VIEW rapport.prix_quotidien AS
WITH e AS (
    SELECT DISTINCT ON (1, 2) coalesce(pc.code_fa, x.code_fonds) AS code_fa, x.jour, x.prix
    FROM (SELECT code_fonds, date_negociation AS jour, prix_part AS prix FROM fait.transaction
          UNION ALL SELECT code_fonds, date_valorisation, prix_action FROM fait.sommaire) x
    LEFT JOIN pub.profil_code pc USING (code_fonds)
    WHERE x.prix > 0
    ORDER BY 1, 2, 3
),
y AS (
    SELECT s.code_fa, c.date_seance AS jour, c.cloture AS prix
    FROM ref.symbole s JOIN pub.cours c USING (symbole)
    WHERE s.code_fa IN (SELECT code_fa FROM e)
)
SELECT code_fa, jour, coalesce(y.prix, e.prix) AS prix, CASE WHEN y.prix IS NULL THEN 'exports' ELSE 'Yahoo' END AS source
FROM y FULL JOIN e USING (code_fa, jour);

-- Parts détenues par compte et par code de fonds après la dernière opération d'une date (rang
-- départage une même journée), valables de cette date (incluse) à la date d'opération suivante (exclue)
CREATE VIEW rapport.parts AS
WITH d AS (
    SELECT DISTINCT ON (compte_alias, code_fonds, date_negociation)
           compte_alias, code_fonds, date_negociation AS du, parts_restantes AS parts
    FROM fait.transaction
    ORDER BY compte_alias, code_fonds, date_negociation, rang DESC
)
SELECT d.compte_alias, d.code_fonds, coalesce(pc.code_fa, d.code_fonds) AS code_fa, d.du,
       coalesce(lead(d.du) OVER (PARTITION BY d.compte_alias, d.code_fonds ORDER BY d.du), 'infinity'::date) AS au,
       d.parts
FROM d
LEFT JOIN pub.profil_code pc USING (code_fonds);

-- P11 : distribution par part de chaque fonds, à la date de réinvestissement des exports :
-- Σ montants réinvestis ÷ Σ parts détenues à la clôture de la veille, tous comptes et options confondus
CREATE VIEW rapport.distribution AS
SELECT p.code_fa, t.date_negociation AS jour, sum(t.montant_brut) / sum(p.parts) AS par_part
FROM fait.transaction t
JOIN rapport.parts p ON p.compte_alias = t.compte_alias AND p.code_fonds = t.code_fonds
                    AND p.du < t.date_negociation AND p.au >= t.date_negociation
WHERE t.nature = 'revenu' AND p.parts > 0
GROUP BY p.code_fa, t.date_negociation;

-- P11 : rendement total de chaque fonds entre deux dates de prix consécutives (P10) :
-- (prix + distribution par part du jour) ÷ prix de la veille − 1
CREATE VIEW rapport.rendement_fonds AS
SELECT q.code_fa, q.jour, lag(q.jour) OVER w AS veille, q.prix, lag(q.prix) OVER w AS prix_veille,
       coalesce(d.par_part, 0) AS distribution,
       ((q.prix + coalesce(d.par_part, 0)) / lag(q.prix) OVER w - 1)::float8 AS rendement
FROM rapport.prix_quotidien q
LEFT JOIN rapport.distribution d USING (code_fa, jour)
WINDOW w AS (PARTITION BY q.code_fa ORDER BY q.jour);

-- P15 : rendement quotidien du repère de chaque fonds, rééquilibré chaque jour : Σ poids × variation
-- de la clôture ajustée du FNB entre les mêmes dates que le fonds (dernier cours connu à chaque date)
CREATE VIEW rapport.repere_quotidien AS
SELECT r.code_fa, r.jour, sum(rp.poids * (a1.v / a0.v - 1))::float8 AS rendement
FROM rapport.rendement_fonds r
JOIN ref.repere rp USING (code_fa)
CROSS JOIN LATERAL (SELECT c.cloture_ajustee AS v FROM pub.cours c
                    WHERE c.symbole = rp.symbole AND c.date_seance <= r.jour
                    ORDER BY c.date_seance DESC LIMIT 1) a1
CROSS JOIN LATERAL (SELECT c.cloture_ajustee AS v FROM pub.cours c
                    WHERE c.symbole = rp.symbole AND c.date_seance <= r.veille
                    ORDER BY c.date_seance DESC LIMIT 1) a0
WHERE r.veille IS NOT NULL
GROUP BY r.code_fa, r.jour;

-- P12 : par compte, fonds et date de rendement : VM à la clôture de la veille (parts × prix de la
-- veille, sans arrondi : c'est un poids), rendement du fonds et de son repère. Une ligne seulement si
-- le compte détenait le fonds la veille : la fenêtre d'un fonds commence à sa première détention.
CREATE VIEW rapport.rendement_quotidien AS
SELECT p.compte_alias, r.code_fa, r.jour, r.veille, (sum(p.parts) * r.prix_veille)::float8 AS vm_veille,
       r.rendement, q.rendement AS repere
FROM rapport.rendement_fonds r
JOIN rapport.parts p ON p.code_fa = r.code_fa AND p.du <= r.veille AND p.au > r.veille
LEFT JOIN rapport.repere_quotidien q ON (q.code_fa, q.jour) = (r.code_fa, r.jour)
WHERE r.veille IS NOT NULL AND p.parts > 0
GROUP BY p.compte_alias, r.code_fa, r.jour, r.veille, r.prix_veille, r.rendement, q.rendement;

-- P12 : rendement quotidien de chaque périmètre, fonds et repère : Σ VM(t−1) × r(t) ÷ Σ VM(t−1).
-- Niveaux : global, régime, compte, fonds (tous comptes).
CREATE VIEW rapport.rendement_perimetre AS
SELECT CASE grouping(k.genre, q.compte_alias, q.code_fa) WHEN 7 THEN 'global' WHEN 3 THEN 'régime'
                                                         WHEN 5 THEN 'compte' ELSE 'fonds' END AS niveau,
       coalesce(q.compte_alias, k.genre, q.code_fa, 'global') AS perimetre, q.jour, min(q.veille) AS veille,
       sum(q.vm_veille * q.rendement) / sum(q.vm_veille) AS rendement,
       sum(q.vm_veille * q.repere) / sum(q.vm_veille) AS repere
FROM rapport.rendement_quotidien q
JOIN ref.compte k ON k.alias = q.compte_alias
GROUP BY GROUPING SETS ((q.jour), (k.genre, q.jour), (q.compte_alias, q.jour), (q.code_fa, q.jour));

-- P13 (volatilité), P14 (pire baisse) et P15 (repère, écart) : par périmètre et par fenêtre (depuis
-- le début ; 12 mois glissants à la dernière date de rendement de la base) : nombre de rendements, volatilité (écart-type d'échantillon × √252, vide sous
-- 60 rendements), rendements du périmètre et du repère, annualisés à partir de 252 rendements
-- ((Π(1 + r))^(252 ÷ n) − 1, sinon cumulés), écart = périmètre − repère, pire baisse et ses dates.
-- Un sommet égal à la valeur de départ est daté de la veille du premier rendement de la fenêtre.
CREATE VIEW rapport.risque_mesure AS
WITH f AS (
    SELECT p.*, 'depuis le début' AS fenetre FROM rapport.rendement_perimetre p
    UNION ALL
    SELECT p.*, '12 mois' FROM rapport.rendement_perimetre p
    WHERE p.jour > (SELECT max(jour) FROM rapport.rendement_quotidien) - interval '1 year'
),
i AS (
    SELECT f.*, exp(sum(ln(1 + rendement)) OVER w) AS indice,
           min(veille) OVER (PARTITION BY niveau, perimetre, fenetre) AS depart
    FROM f WINDOW w AS (PARTITION BY niveau, perimetre, fenetre ORDER BY jour)
),
s AS (
    SELECT i.*, greatest(1, max(indice) OVER w) AS sommet
    FROM i WINDOW w AS (PARTITION BY niveau, perimetre, fenetre ORDER BY jour)
),
b AS (
    SELECT DISTINCT ON (niveau, perimetre, fenetre) niveau, perimetre, fenetre, indice / sommet - 1 AS pire_baisse,
           jour AS date_creux, sommet
    FROM s ORDER BY niveau, perimetre, fenetre, indice / sommet - 1, jour
),
a AS (
    SELECT niveau, perimetre, fenetre, count(*) AS n, min(depart) AS depart,
           CASE WHEN count(*) >= 60 THEN stddev_samp(rendement) * sqrt(252) END AS volatilite,
           exp(sum(ln(1 + rendement))) AS cumul, exp(sum(ln(1 + repere))) AS cumul_repere
    FROM i GROUP BY niveau, perimetre, fenetre
),
c AS (
    SELECT a.*, CASE WHEN n >= 252 THEN power(cumul, 252.0 / n) ELSE cumul END - 1 AS rendement,
           CASE WHEN n >= 252 THEN power(cumul_repere, 252.0 / n) ELSE cumul_repere END - 1 AS rendement_repere
    FROM a
)
SELECT c.niveau, c.perimetre, c.fenetre, c.n, c.n >= 252 AS annualise, c.volatilite, c.rendement, c.rendement_repere,
       c.rendement - c.rendement_repere AS ecart, least(b.pire_baisse, 0) AS pire_baisse,
       CASE WHEN b.pire_baisse < 0
            THEN coalesce((SELECT max(s.jour) FROM s
                           WHERE (s.niveau, s.perimetre, s.fenetre) = (b.niveau, b.perimetre, b.fenetre)
                             AND s.jour <= b.date_creux AND s.indice = b.sommet), c.depart) END AS date_sommet,
       CASE WHEN b.pire_baisse < 0 THEN b.date_creux END AS date_creux
FROM c JOIN b USING (niveau, perimetre, fenetre);

-- P16 : repère mensuel de chaque compte, fonds par fonds, sur les sous-périodes du TWR (P1, P6) :
-- poids = VM du fonds au point de début (au point de fin pour le premier mois, faute de VM de
-- début), rendement = Π(1 + repère quotidien du fonds) sur ]date_debut, date_fin] − 1.
-- Jointure puis agrégat, pas de sous-requête corrélée : le filtre sur le fonds ne descend pas à travers
-- le FULL JOIN de rapport.prix_quotidien, qui serait recalculé en entier pour chaque ligne (12 s contre 0,6 s).
CREATE VIEW rapport.repere_mensuel AS
WITH b AS (
    SELECT p.compte_alias, p.mois, v.cle_fonds AS code_fa, p.date_debut, p.date_fin,
           sum(v.valeur_marchande)::float8 AS poids
    FROM rapport.performance p
    JOIN rapport.valorisation_profil v
      ON v.compte_alias = p.compte_alias AND v.date_point = CASE WHEN p.vm_debut = 0 THEN p.date_fin ELSE p.date_debut END
    GROUP BY p.compte_alias, p.mois, v.cle_fonds, p.date_debut, p.date_fin
)
SELECT b.compte_alias, b.mois, b.code_fa, b.poids, exp(sum(ln(1 + q.rendement))) - 1 AS rendement
FROM b
LEFT JOIN rapport.repere_quotidien q ON q.code_fa = b.code_fa AND q.jour > b.date_debut AND q.jour <= b.date_fin
GROUP BY b.compte_alias, b.mois, b.code_fa, b.date_debut, b.date_fin, b.poids;

-- ============================================================================================
-- Frais d'opérations et nature des distributions (itération 7b). Règles S11 à S14 :
-- docs/regles-strategie.md. Source : pub.rapport_annuel, chargée par pipeline.rapports (S14).
-- ============================================================================================

-- S11 : dernier exercice publié de chaque fonds, le plus récent des RDRF archivés.
-- S12 : part de chaque nature = distribution par part de la nature ÷ somme des quatre natures ;
-- les parts somment à 1 ; un exercice sans distribution a quatre parts vides.
CREATE VIEW rapport.rapport_fonds AS
WITH d AS (
    SELECT DISTINCT ON (code_fa) *, revenus + dividendes + gains_capital + remb_capital AS natures
    FROM pub.rapport_annuel ORDER BY code_fa, exercice DESC
)
SELECT code_fa, exercice, rfo / 100 AS rfo, rotation / 100 AS rotation, natures > 0 AS distribue,
       revenus / nullif(natures, 0) AS part_revenus, dividendes / nullif(natures, 0) AS part_dividendes,
       gains_capital / nullif(natures, 0) AS part_gains_capital, remb_capital / nullif(natures, 0) AS part_remb_capital
FROM d;

-- S13 : VM de chaque fonds au dernier point de chaque compte, avec son RDRF (S11, S12). Les colonnes
-- vm_* portent la VM du fonds seulement s'il a la valeur : valeur pondérée = Σ vm × valeur ÷ Σ vm_*.
CREATE VIEW rapport.detention_rapport AS
SELECT d.compte_alias, k.genre AS regime, d.code_fa, sum(d.valeur_marchande) AS vm,
       r.code_fa IS NOT NULL AS avec_rdrf, r.exercice, r.rfo, r.rotation,
       r.part_revenus, r.part_dividendes, r.part_gains_capital, r.part_remb_capital,
       CASE WHEN r.rfo IS NOT NULL THEN sum(d.valeur_marchande) END AS vm_rfo,
       CASE WHEN r.rotation IS NOT NULL THEN sum(d.valeur_marchande) END AS vm_rotation,
       CASE WHEN r.distribue THEN sum(d.valeur_marchande) END AS vm_nature
FROM rapport.detention d
JOIN ref.compte k ON k.alias = d.compte_alias
LEFT JOIN rapport.rapport_fonds r USING (code_fa)
WHERE d.dernier
GROUP BY d.compte_alias, k.genre, d.code_fa, r.code_fa, r.exercice, r.rfo, r.rotation, r.distribue,
         r.part_revenus, r.part_dividendes, r.part_gains_capital, r.part_remb_capital;

-- S13 : valeurs pondérées par la VM au dernier point, global, par régime et par compte, et part de la
-- VM sans RDRF (pondération du RFG pondéré, S6)
CREATE VIEW rapport.rapport_perimetre AS
SELECT CASE WHEN grouping(regime) = 1 THEN 'global' WHEN grouping(compte_alias) = 1 THEN 'régime' ELSE 'compte' END
           AS niveau,
       CASE WHEN grouping(regime) = 1 THEN 'global' WHEN grouping(compte_alias) = 1 THEN regime ELSE compte_alias END
           AS perimetre,
       sum(vm * rfo) / nullif(sum(vm_rfo), 0) AS rfo,
       sum(vm * rotation) / nullif(sum(vm_rotation), 0) AS rotation,
       sum(vm * part_revenus) / nullif(sum(vm_nature), 0) AS part_revenus,
       sum(vm * part_dividendes) / nullif(sum(vm_nature), 0) AS part_dividendes,
       sum(vm * part_gains_capital) / nullif(sum(vm_nature), 0) AS part_gains_capital,
       sum(vm * part_remb_capital) / nullif(sum(vm_nature), 0) AS part_remb_capital,
       coalesce(sum(vm) FILTER (WHERE NOT avec_rdrf), 0) / nullif(sum(vm), 0) AS part_sans_rdrf
FROM rapport.detention_rapport
GROUP BY GROUPING SETS ((), (regime), (regime, compte_alias));
