-- ===========================================================================
-- gold_fct_net_new_ity  ·  T-SQL-Variante des Perioden-Fanouts
-- ===========================================================================
-- Diese Datei ist die ALTERNATIVE zu nb_20_gold.py fuer den Fall, dass die
-- Gold-Schicht in einem Fabric Warehouse (statt in einem Lakehouse mit
-- Spark-Notebooks) gebaut wird. Fachlich identisch, gleiche Spaltennamen,
-- gleiche Vorzeichenkonvention.
--
-- Der entscheidende Unterschied zum Altzustand: der Fanout entsteht durch
-- einen JOIN gegen eine Monatstabelle, nicht durch List.Generate je Zeile.
-- Der Optimizer kann das parallelisieren; Power Query konnte das nie.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 0. Parameter  (einzige Stelle, an der Stichtage gepflegt werden)
-- ---------------------------------------------------------------------------
DECLARE @CURRENT_FY  INT  = 2025;                    -- FY2025/26
DECLARE @CY_START    DATE = DATEFROMPARTS(@CURRENT_FY,     10, 1);
DECLARE @CY_END      DATE = DATEFROMPARTS(@CURRENT_FY + 1,  9, 30);
DECLARE @NY_START    DATE = DATEFROMPARTS(@CURRENT_FY + 1, 10, 1);
DECLARE @FANOUT_END  DATE = DATEFROMPARTS(@CURRENT_FY + 2,  9, 30);

-- ---------------------------------------------------------------------------
-- 1. Monatsgeruest
-- ---------------------------------------------------------------------------
WITH monate AS (
    SELECT DISTINCT
        DATEFROMPARTS(YEAR(datum), MONTH(datum), 1) AS period_date
    FROM gold_dim_date
    WHERE datum BETWEEN @CY_START AND @FANOUT_END
),

-- ---------------------------------------------------------------------------
-- 2. New Business - Basis je Opportunity
-- ---------------------------------------------------------------------------
-- calc_first_fy_end bildet die M-Formel
--   #date(Date.Year(Date.AddMonths(d, -9)) + 1, 9, 30)
-- nach: 9 Monate zurueck, Jahr + 1, 30.09.
opp AS (
    SELECT
        o.opportunityid                                   AS entity_id,
        o.name                                            AS entity_name,
        'OPPORTUNITY'                                     AS entity_type,
        'NEW'                                             AS business_type,
        o.status_code,
        o.ity_cluster,
        o.win_probability                                 AS probability,
        o.revenue_aro,
        o.revenue_ity,
        o.weighted_aro,
        o.weighted_ity,
        DATEFROMPARTS(YEAR(o.cgplc_openingdate), MONTH(o.cgplc_openingdate), 1)
                                                          AS event_month,
        DATEFROMPARTS(YEAR(DATEADD(MONTH, -9, o.cgplc_openingdate)) + 1, 9, 30)
                                                          AS calc_first_fy_end,
        o.cgplc_openingdate                               AS driver_date,
        o.estimatedclosedate                              AS decision_date
    FROM silver_opportunity AS o
    WHERE o.cgplc_openingdate IS NOT NULL
),
opp_mit_monaten AS (
    SELECT
        opp.*,
        -- Anzahl Monate von event_month bis calc_first_fy_end, beide inklusive
        (YEAR(calc_first_fy_end) - YEAR(event_month)) * 12
            + MONTH(calc_first_fy_end) - MONTH(event_month) + 1  AS calc_ity_months
    FROM opp
),
fct_new AS (
    SELECT
        o.entity_id, o.entity_name, o.entity_type, o.business_type,
        o.status_code, o.ity_cluster, o.probability,
        m.period_date,
        o.event_month, o.driver_date, o.decision_date,
        o.calc_first_fy_end, o.calc_ity_months,
        (YEAR(m.period_date) - YEAR(o.event_month)) * 12
            + MONTH(m.period_date) - MONTH(o.event_month) + 1     AS period_index,
        -- ITY-Phase = erstes Geschaeftsjahr, danach Dauerzustand (ARO)
        CASE WHEN m.period_date <= o.calc_first_fy_end
             THEN 'ITY' ELSE 'ARO' END                            AS value_layer,
        CASE WHEN m.period_date <= o.calc_first_fy_end
             THEN CASE WHEN o.calc_ity_months > 0
                       THEN ISNULL(o.weighted_ity, 0) / o.calc_ity_months
                       ELSE 0 END
             ELSE ISNULL(o.weighted_aro, 0) / 12.0 END            AS amount_weighted,
        CASE WHEN m.period_date <= o.calc_first_fy_end
             THEN CASE WHEN o.calc_ity_months > 0
                       THEN ISNULL(o.revenue_ity, 0) / o.calc_ity_months
                       ELSE 0 END
             ELSE ISNULL(o.revenue_aro, 0) / 12.0 END             AS amount_unweighted,
        CASE WHEN m.period_date <= o.calc_first_fy_end
             THEN 'MAP141a' ELSE 'MAP131' END                     AS hfm_account
    FROM opp_mit_monaten AS o
    INNER JOIN monate AS m
        ON m.period_date >= o.event_month
       AND m.period_date <= @FANOUT_END
),

-- ---------------------------------------------------------------------------
-- 3. Lost Business - Basis je Vertrag
-- ---------------------------------------------------------------------------
-- event_month = ERSTER Monat OHNE Umsatz (Monat nach Vertragsende).
-- Deckel bei 12 Perioden: danach ist der Vertrag vollstaendig aus der Basis
-- heraus und zaehlt als "Like for Like" (Guidance S. 5).
con AS (
    SELECT
        c.cgplc_cgcontractid                              AS entity_id,
        c.cgplc_name                                      AS entity_name,
        'CONTRACT'                                        AS entity_type,
        'LOST'                                            AS business_type,
        c.status_code,
        c.ity_cluster,
        1.0 - c.retention_probability                     AS probability,
        c.revenue_aro,
        c.last_fy_revenue_aro                             AS revenue_ity,
        c.weighted_ly_aro,
        DATEADD(MONTH, 1,
            DATEFROMPARTS(YEAR(c.adj_end_date), MONTH(c.adj_end_date), 1))
                                                          AS event_month,
        DATEFROMPARTS(YEAR(DATEADD(MONTH, -9, c.adj_end_date)) + 1, 9, 30)
                                                          AS calc_first_fy_end,
        c.adj_end_date                                    AS driver_date,
        c.cgplc_decisiondate                              AS decision_date
    FROM silver_contract AS c
),
fct_lost AS (
    SELECT
        c.entity_id, c.entity_name, c.entity_type, c.business_type,
        c.status_code, c.ity_cluster, c.probability,
        m.period_date,
        c.event_month, c.driver_date, c.decision_date, c.calc_first_fy_end,
        (YEAR(c.calc_first_fy_end) - YEAR(c.event_month)) * 12
            + MONTH(c.calc_first_fy_end) - MONTH(c.event_month) + 1 AS calc_ity_months,
        (YEAR(m.period_date) - YEAR(c.event_month)) * 12
            + MONTH(m.period_date) - MONTH(c.event_month) + 1       AS period_index,
        CASE WHEN m.period_date <= c.calc_first_fy_end
             THEN 'ITY' ELSE 'ARO' END                              AS value_layer,
        ISNULL(c.weighted_ly_aro, 0) / 12.0                         AS amount_weighted,
        ISNULL(c.last_fy_revenue_aro, 0) / 12.0                     AS amount_unweighted,
        CASE WHEN m.period_date <= c.calc_first_fy_end
             THEN 'MAP141c' ELSE 'MAP136' END                       AS hfm_account
    FROM con AS c
    INNER JOIN monate AS m
        ON m.period_date >= c.event_month
       AND m.period_date <= @FANOUT_END
    WHERE (YEAR(m.period_date) - YEAR(c.event_month)) * 12
            + MONTH(m.period_date) - MONTH(c.event_month) + 1 <= 12
),

-- ---------------------------------------------------------------------------
-- 4. Vereinigung + Fiskalattribute + Vorzeichenkonvention
-- ---------------------------------------------------------------------------
vereint AS (
    SELECT entity_id, entity_name, entity_type, business_type, status_code,
           ity_cluster, probability, period_date, event_month, driver_date,
           decision_date, calc_first_fy_end, calc_ity_months, period_index,
           value_layer, amount_weighted, amount_unweighted, hfm_account
    FROM fct_new
    UNION ALL
    SELECT entity_id, entity_name, entity_type, business_type, status_code,
           ity_cluster, probability, period_date, event_month, driver_date,
           decision_date, calc_first_fy_end, calc_ity_months, period_index,
           value_layer, amount_weighted, amount_unweighted, hfm_account
    FROM fct_lost
)
SELECT
    v.*,
    -- Fiskaljahr = Kalenderjahr des FY-Beginns (Oktober-Regel)
    CASE WHEN MONTH(v.period_date) >= 10
         THEN YEAR(v.period_date) ELSE YEAR(v.period_date) - 1 END    AS fy_year,
    CASE WHEN MONTH(v.period_date) >= 10
         THEN MONTH(v.period_date) - 9 ELSE MONTH(v.period_date) + 3 END AS fy_period,
    -- Vorzeichen: NEW positiv, LOST negativ  =>  Net New = einfache Summe
    CAST(CASE WHEN v.business_type = 'LOST'
              THEN -v.amount_weighted ELSE v.amount_weighted END AS DECIMAL(19,4))
                                                                       AS amount_signed,
    CAST(ABS(v.amount_weighted) AS DECIMAL(19,4))                      AS amount_abs,
    CAST(GETDATE() AS DATE)                                            AS snapshot_date
INTO gold_fct_net_new_ity
FROM vereint AS v;
