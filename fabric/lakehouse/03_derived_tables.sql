-- =====================================================================
-- Abgeleitete Tabellen fuer das Semantic Model
--
-- !! AUSFUEHRUNG: Fabric-NOTEBOOK, Zelle auf Spark SQL (%%sql).
-- !! NICHT im SQL Analytics Endpoint - siehe 01_create_tables.sql.
-- !! Laeuft taeglich NACH 02_load_snapshot.py.
--
-- Warum Tabellen und nicht Views:
-- Ein Direct-Lake-Semantikmodell liest Delta-Tabellen. Views sind dort
-- nicht nutzbar - das Modell fiele auf DirectQuery zurueck und verloere
-- genau den Vorteil, wegen dem die Strecke auf Direct Lake ausgelegt ist.
-- Die Ableitungen werden deshalb einmal taeglich materialisiert. Da die
-- Quelle ohnehin nur einmal taeglich wechselt, kostet das nichts.
--
--   fct_opportunity_current / fct_retention_current
--       Ist-Stand, Basis der Report-Zahlen
--   fct_opportunity_changes / fct_retention_changes
--       nur Aenderungszeilen, Basis der Leading KPIs
-- =====================================================================



-- ---------------------------------------------------------------------
-- Aktueller Stand: der jeweils juengste Snapshot
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fct_opportunity_current
USING DELTA AS
SELECT *
FROM fct_opportunity
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM fct_opportunity);

CREATE OR REPLACE TABLE fct_retention_current
USING DELTA AS
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
CREATE OR REPLACE TABLE fct_opportunity_changes
USING DELTA AS
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
CREATE OR REPLACE TABLE fct_retention_changes
USING DELTA AS
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


-- ---------------------------------------------------------------------
-- Aktueller Mappingstand
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE map_opportunity_unit_current
USING DELTA AS
SELECT *
FROM map_opportunity_unit
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM map_opportunity_unit);


-- =====================================================================
-- ITY-PHASIERUNG
--
-- Loest eine Zeile je Opportunity bzw. Contract in Monatsperioden auf.
-- Lag bis hierher als berechnete DAX-Tabelle im Semantic Model. Drei
-- Gruende fuer den Umzug nach Spark:
--
--   1. Direct Lake vertraegt keine berechneten Tabellen. Solange die
--      Phasierung in DAX liegt, ist das Modell auf Import festgelegt.
--   2. Als Delta-Tabelle ist das Ergebnis pruefbar - man kann eine
--      einzelne Opportunity herausgreifen und ihre Monatszeilen gegen
--      den Altbericht rechnen. In DAX ist zwischen Rohdaten und Measure
--      nichts einsehbar.
--   3. Einmal taeglich statt bei jedem Modell-Refresh.
--
-- VORZEICHEN: Diese Tabellen speichern ausschliesslich POSITIVE
-- Betraege. Ob der ITY-Anteil negativ in den Nettoeffekt eingeht, ist
-- eine Darstellungskonvention und bleibt im Measure.
--
-- Geschaeftsjahr: 1. Oktober bis 30. September.
-- Horizont: cfg_horizont, eine Zeile.
-- =====================================================================


-- ---------------------------------------------------------------------
-- fct_opp_phasing
-- Grain: 1 Zeile je (opportunityid, period_date)
--
-- Filter wie im Altmodell. Achtung auf die NULL-Semantik: Zeilen ohne
-- statecodename oder ohne cgplc_salesstagename fallen heraus, weil ein
-- Vergleich mit NULL nicht wahr wird. Das entspricht Power Query - die
-- zwischenzeitliche DAX-Fassung hat sie faelschlich behalten.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fct_opp_phasing
USING DELTA AS
WITH h AS (
    SELECT fy_start, fy_ende FROM cfg_horizont LIMIT 1
),
perioden AS (
    SELECT explode(
               sequence(trunc(h.fy_start, 'MM'), trunc(h.fy_ende, 'MM'), INTERVAL 1 MONTH)
           ) AS period_date
    FROM h
),
basis AS (
    SELECT
        o.opportunityid,
        o.cgplc_contractid,
        o.estimatedclosedate,
        trunc(o.cgplc_openingdate, 'MM')                                  AS start_date,
        make_date(year(add_months(o.cgplc_openingdate, -9)) + 1, 9, 30)   AS phasenwechsel,
        o.cgplc_revenuearo * o.cgplc_win                                  AS weighted_aro,
        o.cgplc_revenueity * o.cgplc_win                                  AS weighted_ity
    FROM fct_opportunity_current o
    CROSS JOIN h
    WHERE o.cgplc_openingdate  IS NOT NULL
      AND o.estimatedclosedate IS NOT NULL
      AND o.cgplc_openingdate  >= h.fy_start
      AND o.estimatedclosedate >= h.fy_start
      AND o.statecodename        <> 'Verloren'
      AND o.cgplc_salesstagename NOT IN ('Nobid', 'Turndown/Lost', 'Universe')
),
mit_laufzeit AS (
    SELECT
        b.*,
        (year(b.phasenwechsel) - year(b.start_date)) * 12
            + month(b.phasenwechsel) - month(b.start_date) + 1            AS calc_ity_months
    FROM basis b
),
mit_werten AS (
    SELECT
        m.*,
        -- Der ITY-Betrag verteilt sich auf die Monate bis zum ersten
        -- Geschaeftsjahresende, der ARO-Betrag immer auf zwoelf.
        CASE WHEN m.weighted_ity IS NULL OR m.weighted_ity = 0 OR m.calc_ity_months <= 0
             THEN 0 ELSE m.weighted_ity / m.calc_ity_months END           AS ity_value,
        CASE WHEN m.weighted_aro IS NULL OR m.weighted_aro = 0
             THEN 0 ELSE m.weighted_aro / 12 END                          AS aro_value
    FROM mit_laufzeit m
)
SELECT
    w.opportunityid,
    COALESCE(mu.sap_unit, r.cgplc_sapid)                                  AS sap_unit,
    p.period_date,
    w.estimatedclosedate                                                  AS referenzdatum,
    CASE
        WHEN w.estimatedclosedate <= make_date(year(add_months(h.fy_start, -9)) + 1, 9, 30)
            THEN 'Roll'
        WHEN w.estimatedclosedate <= make_date(year(add_months(h.fy_start, -9)) + 2, 9, 30)
            THEN 'ITY'
    END                                                                   AS ity_cluster,
    w.calc_ity_months,
    w.phasenwechsel,
    CAST(w.ity_value AS DOUBLE)                                           AS ity_value,
    CAST(w.aro_value AS DOUBLE)                                           AS aro_value
FROM mit_werten w
CROSS JOIN h
JOIN perioden p
  ON p.period_date >= w.start_date
LEFT JOIN map_opportunity_unit_current mu
  ON mu.opportunityid = w.opportunityid
LEFT JOIN fct_retention_current r
  ON r.cgplc_cgcontractid = w.cgplc_contractid;


-- ---------------------------------------------------------------------
-- fct_retention_phasing
-- Grain: 1 Zeile je (cgplc_cgcontractid, period_date), maximal 12
-- Perioden ab dem Monat nach Vertragsende.
--
-- Die Retention kennt keine ITY/ARO-Trennung - ein verlorener Vertrag
-- wirkt in jeder Periode gleich. Beide Wertspalten tragen deshalb
-- denselben Betrag.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fct_retention_phasing
USING DELTA AS
WITH h AS (
    SELECT fy_start, fy_ende FROM cfg_horizont LIMIT 1
),
perioden AS (
    SELECT explode(
               sequence(trunc(h.fy_start, 'MM'), trunc(h.fy_ende, 'MM'), INTERVAL 1 MONTH)
           ) AS period_date
    FROM h
),
basis AS (
    SELECT
        c.cgplc_cgcontractid,
        c.cgplc_sapid,
        -- Ersatzlogik aus dem Altmodell: fehlt das Vertragsende, gilt
        -- das Entscheidungsdatum plus drei Monate.
        COALESCE(c.cgplc_contractenddate, add_months(c.cgplc_decisiondate, 3)) AS end_date_raw,
        c.cgplc_lastfyrevenuearo * (1 - c.cgplc_retentionprobability)          AS weighted_ly_aro
    FROM fct_retention_current c
    WHERE c.statuscodename = 'Aktiv'
),
gefiltert AS (
    SELECT b.*, h.fy_start, h.fy_ende
    FROM basis b
    CROSS JOIN h
    WHERE b.end_date_raw IS NOT NULL
      AND b.end_date_raw >= h.fy_start
      AND b.end_date_raw <= h.fy_ende
),
mit_eckdaten AS (
    SELECT
        g.*,
        add_months(trunc(g.end_date_raw, 'MM'), 1)                            AS calc_end_date,
        make_date(year(add_months(g.end_date_raw, -9)) + 1, 9, 30)            AS phasenwechsel,
        CASE WHEN g.weighted_ly_aro IS NULL OR g.weighted_ly_aro = 0
             THEN 0 ELSE g.weighted_ly_aro / 12 END                           AS monatswert
    FROM gefiltert g
)
SELECT
    e.cgplc_cgcontractid,
    e.cgplc_sapid                                                             AS sap_unit,
    p.period_date,
    e.end_date_raw                                                            AS referenzdatum,
    CASE
        WHEN e.end_date_raw <= make_date(year(add_months(e.fy_start, -9)) + 1, 9, 30)
            THEN 'Roll'
        WHEN e.end_date_raw <= make_date(year(add_months(e.fy_start, -9)) + 2, 9, 30)
            THEN 'ITY'
    END                                                                       AS ity_cluster,
    CAST(12 AS INT)                                                           AS calc_ity_months,
    e.phasenwechsel,
    CAST(e.monatswert AS DOUBLE)                                              AS ity_value,
    CAST(e.monatswert AS DOUBLE)                                              AS aro_value
FROM mit_eckdaten e
JOIN perioden p
  ON p.period_date >= e.calc_end_date
 AND p.period_date <= add_months(e.calc_end_date, 11);


-- ---------------------------------------------------------------------
-- fct_budget_effect
-- Grain: 1 Zeile je (effect_type, entity_id, period_date)
--
-- Harmonisierung auf die gemeinsame Achse Periode x SAP-Betrieb. Die
-- Quelltabellen bleiben getrennt - Opportunity und Contract sind
-- unterschiedliche Geschaeftsobjekte mit disjunkten Attributen.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fct_budget_effect
USING DELTA AS
SELECT
    'New Business'      AS effect_type,
    opportunityid       AS entity_id,
    sap_unit,
    period_date,
    referenzdatum,
    ity_cluster,
    phasenwechsel,
    ity_value,
    aro_value
FROM fct_opp_phasing
UNION ALL
SELECT
    'Retention'         AS effect_type,
    cgplc_cgcontractid  AS entity_id,
    sap_unit,
    period_date,
    referenzdatum,
    ity_cluster,
    phasenwechsel,
    ity_value,
    aro_value
FROM fct_retention_phasing;
