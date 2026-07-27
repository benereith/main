-- =====================================================================
-- Lakehouse-Views auf die historisierten Faktentabellen.
--
-- Das Semantic Model laedt NICHT die volle Historie, sondern:
--   vw_opportunity_current / vw_retention_current  -> Ist-Stand, Basis der Report-Zahlen
--   vw_opportunity_changes / vw_retention_changes  -> nur Aenderungszeilen, Basis der Leading KPIs
-- =====================================================================


-- ---------------------------------------------------------------------
-- Aktueller Stand: der jeweils juengste Snapshot
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_opportunity_current AS
SELECT *
FROM fct_opportunity
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM fct_opportunity);

CREATE OR REPLACE VIEW vw_retention_current AS
SELECT *
FROM fct_retention
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM fct_retention);


-- ---------------------------------------------------------------------
-- Aenderungshistorie Opportunities
-- Eine Zeile je Snapshot, in dem sich fachlich etwas geaendert hat,
-- plus die jeweils vorherigen Werte der beobachteten Felder.
-- Damit sind Stage-Wechsel, Wertaenderungen und Terminverschiebungen
-- direkt auswertbar, ohne die komplette Snapshot-Historie zu scannen.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_opportunity_changes AS
WITH ranked AS (
    SELECT
        snapshot_date,
        opportunityid,
        name,
        ownerid,
        cgplc_sectorlookup,
        cgplc_territoryid,

        statecodename,
        statuscodename,
        cgplc_salesstagename,
        cgplc_win,
        cgplc_revenuearo,
        cgplc_revenueity,
        estimatedclosedate,
        cgplc_openingdate,

        LAG(statecodename)        OVER w AS prev_statecodename,
        LAG(statuscodename)       OVER w AS prev_statuscodename,
        LAG(cgplc_salesstagename) OVER w AS prev_salesstagename,
        LAG(cgplc_win)            OVER w AS prev_win,
        LAG(cgplc_revenuearo)     OVER w AS prev_revenuearo,
        LAG(cgplc_revenueity)     OVER w AS prev_revenueity,
        LAG(estimatedclosedate)   OVER w AS prev_estimatedclosedate,
        LAG(snapshot_date)        OVER w AS prev_snapshot_date
    FROM fct_opportunity
    WINDOW w AS (PARTITION BY opportunityid ORDER BY snapshot_date)
)
SELECT
    *,
    CASE WHEN prev_snapshot_date IS NULL THEN TRUE ELSE FALSE END AS is_new,
    CASE
        WHEN prev_salesstagename IS NOT NULL
         AND prev_salesstagename <> cgplc_salesstagename THEN TRUE
        ELSE FALSE
    END AS stage_changed,
    cgplc_revenuearo - prev_revenuearo AS delta_revenuearo,
    cgplc_revenueity - prev_revenueity AS delta_revenueity,
    cgplc_win        - prev_win        AS delta_win,
    DATEDIFF(estimatedclosedate, prev_estimatedclosedate) AS delta_closedate_days
FROM ranked
WHERE prev_snapshot_date IS NULL
   OR NOT (
        statecodename        <=> prev_statecodename
    AND statuscodename       <=> prev_statuscodename
    AND cgplc_salesstagename <=> prev_salesstagename
    AND cgplc_win            <=> prev_win
    AND cgplc_revenuearo     <=> prev_revenuearo
    AND cgplc_revenueity     <=> prev_revenueity
    AND estimatedclosedate   <=> prev_estimatedclosedate
   );


-- ---------------------------------------------------------------------
-- Aenderungshistorie Retention-Contracts
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_retention_changes AS
WITH ranked AS (
    SELECT
        snapshot_date,
        cgplc_cgcontractid,
        cgplc_name,
        cgplc_sapid,

        statuscodename,
        statecodename,
        cgplc_reasonforriskname,
        cgplc_retentionprobability,
        cgplc_lastfyrevenuearo,
        cgplc_revenuearo,
        cgplc_contractenddate,
        cgplc_decisiondate,
        cgplc_forecastdecisiondate,

        LAG(statuscodename)             OVER w AS prev_statuscodename,
        LAG(cgplc_reasonforriskname)    OVER w AS prev_reasonforriskname,
        LAG(cgplc_retentionprobability) OVER w AS prev_retentionprobability,
        LAG(cgplc_lastfyrevenuearo)     OVER w AS prev_lastfyrevenuearo,
        LAG(cgplc_contractenddate)      OVER w AS prev_contractenddate,
        LAG(cgplc_forecastdecisiondate) OVER w AS prev_forecastdecisiondate,
        LAG(snapshot_date)              OVER w AS prev_snapshot_date
    FROM fct_retention
    WINDOW w AS (PARTITION BY cgplc_cgcontractid ORDER BY snapshot_date)
)
SELECT
    *,
    CASE WHEN prev_snapshot_date IS NULL THEN TRUE ELSE FALSE END AS is_new,
    cgplc_retentionprobability - prev_retentionprobability AS delta_retentionprobability,
    cgplc_lastfyrevenuearo     - prev_lastfyrevenuearo     AS delta_lastfyrevenuearo,
    DATEDIFF(cgplc_contractenddate, prev_contractenddate)  AS delta_contractenddate_days
FROM ranked
WHERE prev_snapshot_date IS NULL
   OR NOT (
        statuscodename             <=> prev_statuscodename
    AND cgplc_reasonforriskname    <=> prev_reasonforriskname
    AND cgplc_retentionprobability <=> prev_retentionprobability
    AND cgplc_lastfyrevenuearo     <=> prev_lastfyrevenuearo
    AND cgplc_contractenddate      <=> prev_contractenddate
    AND cgplc_forecastdecisiondate <=> prev_forecastdecisiondate
   );
