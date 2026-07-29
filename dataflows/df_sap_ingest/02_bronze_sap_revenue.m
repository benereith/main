// ===========================================================================
// Dataflow Gen2 "df_sap_ingest"  ·  Abfrage: bronze_sap_revenue
// ===========================================================================
// Ist-, Budget- und Forecast-Umsaetze aus der SQL-View V_SAP_EXPORTS_cleansed
// im SAP-Warehouse "Reporting" - dieselbe Quelle wie in den Altmodellen.
//
// Ziel  : lakehouse_group_controlling / bronze_sap_revenue
// Modus : REPLACE (Ziel in den Dataflow-Einstellungen auf "Ersetzen" stellen)
//
// KEINE HISTORISIERUNG, aus demselben Grund wie bei bronze_sap_unit: die View
// ist bereits der gepflegte Ist-/Planstand je Periode. Ein Tagessnapshot
// darueber wuerde dieselben Buchungen taeglich vervielfachen, ohne eine Frage
// zu beantworten, die nicht schon ueber fy_year/fy_period beantwortbar waere.
// nb_05_snapshot fasst diese Tabelle deshalb nicht an.
//
// SPALTENNAMEN NICHT UMBENENNEN. nb_20_gold liest Fiscal_Year, Period,
// Object_group, SAP_Version und Value woertlich in dieser Schreibweise.
// ===========================================================================
let
    // Servername des SAP-Warehouse. Beim Einrichten einmal eintragen bzw. als
    // Dataflow-Parameter hinterlegen, damit DEV/PROD getauscht werden kann.
    SapServer = "SAP-WAREHOUSE-SERVER-HIER-EINTRAGEN",

    Quelle = Sql.Database(SapServer, "Reporting"),
    View = Quelle{[Schema = "dbo", Item = "V_SAP_EXPORTS_cleansed"]}[Data],

    // --- Mengenbegrenzung an der Quelle -----------------------------------
    // Die View reicht historisch weit zurueck; der Bericht braucht Vorjahr,
    // laufendes Jahr und Folgejahr. Der Filter steht bewusst VOR allen
    // weiteren Schritten, damit er als WHERE an SQL Server durchgereicht wird
    // (Query Folding) und nicht erst nach dem Laden greift. Genau das ging in
    // den Altmodellen verloren und machte die Aktualisierung langsam.
    AktuellesGJ = 2025,   // 2025 = FY2025/26. Mit CURRENT_FY in
                          // lakehouse/notebooks/nb_00_config.py gleichhalten.
    Gefiltert = Table.SelectRows(
        View,
        each [Fiscal_Year] >= AktuellesGJ - 1 and [Fiscal_Year] <= AktuellesGJ + 1
    ),

    // Nur die von nb_20_gold gelesenen Spalten. Schreibweise beibehalten.
    GewuenschteSpalten = {
        "Fiscal_Year",   // Geschaeftsjahr
        "Period",        // Periode 1..12, P1 = Oktober
        "Object_group",  // Werk / Betrieb
        "SAP_Version",   // 0 = Ist, 20 = Budget, RGF/R12 = Forecast, 90 = Plan
        "Value"          // Betrag, von SAP negativ geliefert (Vorzeichenumkehr
                         // passiert zentral in nb_20_gold)
    },

    VorhandeneSpalten = Table.ColumnNames(Gefiltert),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),

    // Reissleine, siehe 01_bronze_sap_unit.m. Ohne Object_group und Value ist
    // die Tabelle fuer gold_fct_revenue wertlos; besser hier abbrechen als
    // eine Tabelle mit zwei Hilfsspalten zu schreiben.
    Pflicht = {"Fiscal_Year", "Period", "Object_group", "Value"},
    FehlendPflicht = List.Difference(Pflicht, VorhandeneSpalten),
    Geprueft =
        if List.Count(FehlendPflicht) > 0 then
            error Error.Record(
                "Quelle liefert keine Umsatzdaten",
                "Pflichtspalte(n) fehlen: " & Text.Combine(FehlendPflicht, ", ")
                    & ". Zeigt die Abfrage wirklich auf V_SAP_EXPORTS_cleansed? "
                    & "Schreibweise der Spalten beachten - nb_20_gold liest sie "
                    & "woertlich.",
                "Gefundene Spalten: " & Text.Combine(VorhandeneSpalten, ", ")
            )
        else
            Gefiltert,

    Selektiert = Table.SelectColumns(Geprueft, Auswahl),

    MitLadezeit = Table.AddColumn(
        Selektiert, "loaded_at", each DateTime.From(fn_berlin_now()), type datetime
    ),
    MitDiagnose = Table.AddColumn(
        MitLadezeit, "_fehlende_felder", each Text.Combine(Fehlend, ","), type text
    )
in
    MitDiagnose
