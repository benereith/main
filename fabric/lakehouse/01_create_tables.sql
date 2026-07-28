-- =====================================================================
-- Lakehouse: Faktentabellen (historisiert)
--
-- !! AUSFUEHRUNG: Fabric-NOTEBOOK, Zelle auf Spark SQL (%%sql).
-- !! NICHT im SQL Analytics Endpoint des Lakehouse ausfuehren.
--
-- Der SQL Analytics Endpoint spricht T-SQL und ist fuer das Lakehouse
-- lesend. Dort scheitert schon "CREATE TABLE IF NOT EXISTS" (Meldung 156,
-- T-SQL kennt kein IF NOT EXISTS in CREATE TABLE), ebenso "USING DELTA"
-- und "PARTITIONED BY". Tabellen im Lakehouse entstehen ausschliesslich
-- ueber Spark.
--
-- Nur Fakten - keine Dimensionen. Dimensionen entstehen im Semantic Model.
--
-- Die Staging-Tabellen stg_opportunity, stg_retention und
-- stg_opportunity_unit fehlen hier bewusst: sie sind das Ziel der
-- Dataflow-Gen2-Queries und entstehen bei deren erstem Lauf automatisch.
-- Sie sind transient - jeder Lauf ueberschreibt sie vollstaendig (Replace),
-- ihr Schema darf der Dataflow bestimmen. Explizit typisiert werden nur die
-- Tabellen hier, weil sie die Historie tragen und ueber Jahre stabil
-- bleiben muessen.
--
-- Historisierung: taeglicher Vollsnapshot, partitioniert nach snapshot_date.
-- Grain fct_opportunity : 1 Zeile je (snapshot_date, opportunityid)
-- Grain fct_retention   : 1 Zeile je (snapshot_date, cgplc_cgcontractid)
-- =====================================================================

CREATE TABLE IF NOT EXISTS fct_opportunity (
    snapshot_date               DATE,

    opportunityid               STRING,
    accountid                   STRING,
    parentaccountid             STRING,
    ownerid                     STRING,
    cgplc_territoryid           STRING,
    cgplc_contractid            STRING,

    name                        STRING,
    statecodename               STRING,
    statuscodename              STRING,
    cgplc_salesstagename        STRING,
    cgplc_contracttypelookup    STRING,
    cgplc_sectorlookup          STRING,
    cgplc_subsector             STRING,
    cgplc_currentsupplier       STRING,

    estimatedclosedate          DATE,
    cgplc_openingdate           DATE,
    cgplc_wondate               DATE,

    cgplc_revenuearo            DECIMAL(19,4),
    cgplc_revenuearo_base       DECIMAL(19,4),
    cgplc_revenueity            DECIMAL(19,4),
    cgplc_revenueity_base       DECIMAL(19,4),
    cgplc_win                   DOUBLE,
    cgplc_bgpercent             DOUBLE,

    createdon                   TIMESTAMP,
    modifiedon                  TIMESTAMP,
    loaded_at                   TIMESTAMP
)
USING DELTA
PARTITIONED BY (snapshot_date);


CREATE TABLE IF NOT EXISTS fct_retention (
    snapshot_date               DATE,

    cgplc_cgcontractid          STRING,
    cgplc_sapid                 BIGINT,

    cgplc_name                  STRING,
    statuscodename              STRING,
    statecodename               STRING,
    cgplc_reasonforriskname     STRING,

    cgplc_contractenddate       DATE,
    cgplc_decisiondate          DATE,
    cgplc_forecastdecisiondate  DATE,
    cgplc_operationstartdate    TIMESTAMP,

    cgplc_revenuearo            DECIMAL(19,4),
    cgplc_currentrevenuearo     DECIMAL(19,4),
    cgplc_lastfyrevenuearo      DECIMAL(19,4),
    cgplc_retentionprobability  DOUBLE,

    createdon                   TIMESTAMP,
    modifiedon                  TIMESTAMP,
    loaded_at                   TIMESTAMP
)
USING DELTA
PARTITIONED BY (snapshot_date);


-- ---------------------------------------------------------------------
-- Mapping Opportunity -> SAP-Betrieb (manuell gepflegt, SharePoint).
-- Historisiert, weil das Mapping ein manueller Input in offizielle
-- Budgetzahlen ist: ohne Snapshot ist eine abgeschlossene Budgetrunde
-- nach der naechsten Pflegerunde nicht mehr reproduzierbar.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS map_opportunity_unit (
    snapshot_date               DATE,
    opportunityid               STRING,
    sap_unit                    BIGINT,
    loaded_at                   TIMESTAMP
)
USING DELTA
PARTITIONED BY (snapshot_date);


-- ---------------------------------------------------------------------
-- Betrachtungszeitraum. Die einzige Stelle, an der der Horizont steht -
-- er steuert die Phasierung in 03_derived_tables.sql.
--
-- Ersetzt die vier Est_*-Parameter des Altmodells. Nach einer Aenderung
-- 03_derived_tables.sql neu laufen lassen.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cfg_horizont (
    fy_start                    DATE,
    fy_ende                     DATE
)
USING DELTA;

-- Einmalig befuellen (und nur so aendern - kein zweiter Datensatz):
-- TRUNCATE TABLE cfg_horizont;
-- INSERT INTO cfg_horizont VALUES (DATE'2025-10-01', DATE'2027-09-30');
