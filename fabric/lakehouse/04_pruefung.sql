-- =====================================================================
-- Pruefabfragen zur Phasierung
--
-- !! AUSFUEHRUNG: Notebook, %%sql - oder im SQL Analytics Endpoint,
-- !! dort sind diese Abfragen lesend und damit zulaessig.
--
-- Zweck: die Rechnung nachvollziehbar machen. Genau das fehlte, solange
-- die Phasierung in DAX lag - zwischen Rohdaten und Measure war nichts
-- einsehbar. Jede Abfrage hier beantwortet eine konkrete Frage.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Ist der Horizont gesetzt? Genau eine Zeile erwartet.
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS zeilen, MIN(fy_start) AS fy_start, MIN(fy_ende) AS fy_ende
FROM cfg_horizont;


-- ---------------------------------------------------------------------
-- 2. Grain: je Entitaet und Periode genau eine Zeile.
--    Leeres Ergebnis = in Ordnung.
-- ---------------------------------------------------------------------
SELECT effect_type, entity_id, period_date, COUNT(*) AS zeilen
FROM fct_budget_effect
GROUP BY effect_type, entity_id, period_date
HAVING COUNT(*) > 1
ORDER BY zeilen DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- 3. Vorzeichen: die Phasing-Tabellen fuehren nur positive Betraege.
--    Leeres Ergebnis = in Ordnung.
-- ---------------------------------------------------------------------
SELECT effect_type, COUNT(*) AS negative_zeilen,
       MIN(ity_value) AS min_ity, MIN(aro_value) AS min_aro
FROM fct_budget_effect
WHERE ity_value < 0 OR aro_value < 0
GROUP BY effect_type;


-- ---------------------------------------------------------------------
-- 4. Einzelfall durchrechnen.
--    <ID> ersetzen - liefert die Monatszeilen einer Opportunity mit
--    allen Zwischengroessen. Das ist die Abfrage fuer den Abgleich
--    gegen den Altbericht.
-- ---------------------------------------------------------------------
SELECT
    o.opportunityid,
    o.name,
    o.cgplc_openingdate,
    o.estimatedclosedate,
    o.cgplc_win,
    o.cgplc_revenueity,
    o.cgplc_revenuearo,
    p.calc_ity_months,
    p.phasenwechsel,
    p.ity_cluster,
    p.period_date,
    CASE WHEN p.period_date <= p.phasenwechsel THEN 'ITY' ELSE 'ARO' END AS phase,
    p.ity_value,
    p.aro_value,
    CASE WHEN p.period_date <= p.phasenwechsel THEN p.ity_value ELSE p.aro_value END
        AS wirksamer_betrag
FROM fct_opp_phasing p
JOIN fct_opportunity_current o USING (opportunityid)
WHERE o.opportunityid = '<ID>'
ORDER BY p.period_date;


-- ---------------------------------------------------------------------
-- 5. Kontrolle der Aufteilung je Opportunity:
--    Summe der ITY-Perioden muss den gewichteten ITY-Betrag ergeben,
--    Summe der ARO-Perioden ueber zwoelf Monate den gewichteten ARO.
--    Abweichungen > 0,01 deuten auf einen Fehler in calc_ity_months.
-- ---------------------------------------------------------------------
SELECT
    p.opportunityid,
    o.cgplc_revenueity * o.cgplc_win                       AS weighted_ity,
    SUM(CASE WHEN p.period_date <= p.phasenwechsel
             THEN p.ity_value ELSE 0 END)                  AS summe_ity_perioden,
    p.calc_ity_months,
    ROUND(
        o.cgplc_revenueity * o.cgplc_win
        - SUM(CASE WHEN p.period_date <= p.phasenwechsel THEN p.ity_value ELSE 0 END),
        2)                                                 AS differenz
FROM fct_opp_phasing p
JOIN fct_opportunity_current o USING (opportunityid)
GROUP BY p.opportunityid, o.cgplc_revenueity, o.cgplc_win, p.calc_ity_months
HAVING ABS(differenz) > 0.01
ORDER BY ABS(differenz) DESC
LIMIT 50;
-- Hinweis: Eine Abweichung ist erwartbar, wenn die ITY-Phase ueber den
-- Horizont hinausragt - dann fehlen Perioden am Ende. Der Vergleich
-- gilt nur fuer Opportunities, deren Phasenwechsel im Horizont liegt.


-- ---------------------------------------------------------------------
-- 6. Summen je Geschaeftsjahr und Effektart - die Zahlen fuer den
--    Abgleich gegen den Altbericht.
-- ---------------------------------------------------------------------
SELECT
    CASE WHEN month(period_date) >= 10
         THEN concat('FY', year(period_date), '/', substr(cast(year(period_date) + 1 AS STRING), 3, 2))
         ELSE concat('FY', year(period_date) - 1, '/', substr(cast(year(period_date) AS STRING), 3, 2))
    END                                                        AS fy,
    effect_type,
    ity_cluster,
    COUNT(DISTINCT entity_id)                                  AS entitaeten,
    ROUND(SUM(CASE WHEN period_date <= phasenwechsel
                   THEN ity_value ELSE 0 END), 2)              AS ity_volumen,
    ROUND(SUM(CASE WHEN period_date >  phasenwechsel
                   THEN aro_value ELSE 0 END), 2)              AS aro_volumen
FROM fct_budget_effect
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;


-- ---------------------------------------------------------------------
-- 7. Mappingpflege: welches Volumen haengt an keinem Betrieb?
-- ---------------------------------------------------------------------
SELECT
    effect_type,
    COUNT(DISTINCT entity_id)                                  AS entitaeten_ohne_betrieb,
    ROUND(SUM(ity_value + aro_value), 2)                       AS volumen_ohne_betrieb
FROM fct_budget_effect
WHERE sap_unit IS NULL
GROUP BY effect_type;


-- ---------------------------------------------------------------------
-- 8. Wie viele Opportunities gehen ueberhaupt in die Phasierung ein?
--    Die Differenz zeigt, was die Filter wegnehmen.
-- ---------------------------------------------------------------------
SELECT
    (SELECT COUNT(DISTINCT opportunityid) FROM fct_opportunity_current) AS im_extrakt,
    (SELECT COUNT(DISTINCT opportunityid) FROM fct_opp_phasing)         AS in_phasierung,
    (SELECT COUNT(DISTINCT cgplc_cgcontractid) FROM fct_retention_current) AS contracts_im_extrakt,
    (SELECT COUNT(DISTINCT cgplc_cgcontractid) FROM fct_retention_phasing) AS contracts_in_phasierung;


-- ---------------------------------------------------------------------
-- 9. Ausgeschlossene Opportunities mit Begruendung - zum Gegenlesen,
--    ob die Filter das Richtige treffen.
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN o.cgplc_openingdate IS NULL           THEN 'kein Opening Date'
        WHEN o.estimatedclosedate IS NULL          THEN 'kein Close Date'
        WHEN o.statecodename IS NULL               THEN 'kein Statecode'
        WHEN o.cgplc_salesstagename IS NULL        THEN 'keine Sales Stage'
        WHEN o.statecodename = 'Verloren'          THEN 'verloren'
        WHEN o.cgplc_salesstagename
             IN ('Nobid', 'Turndown/Lost', 'Universe') THEN concat('Stage: ', o.cgplc_salesstagename)
        WHEN o.cgplc_openingdate  < h.fy_start     THEN 'Opening vor Horizont'
        WHEN o.estimatedclosedate < h.fy_start     THEN 'Close vor Horizont'
        ELSE 'enthalten'
    END                                            AS grund,
    COUNT(*)                                       AS opportunities,
    ROUND(SUM(o.cgplc_revenuearo), 2)              AS aro_volumen
FROM fct_opportunity_current o
CROSS JOIN (SELECT fy_start FROM cfg_horizont LIMIT 1) h
GROUP BY 1
ORDER BY opportunities DESC;
