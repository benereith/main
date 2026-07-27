-- =====================================================================
-- Lakehouse: Faktentabellen (historisiert)
-- Nur Fakten - keine Dimensionen. Dimensionen entstehen im Semantic Model.
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
