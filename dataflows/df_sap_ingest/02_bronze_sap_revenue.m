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
    SapServer = "3w3wftkijo6ujehh4fb2eleovu-tuq7lxe5lznu7hpei5nzy67o3e.datawarehouse.fabric.microsoft.com",

    Quelle = Sql.Database(SapServer, "Reporting"),
    View = Quelle{[Schema = "dbo", Item = "V_SAP_EXPORTS_cleansed"]}[Data],

    // Kontenhierarchie aus derselben Quelle - liefert die Ertragsabgrenzung.
    HierarchieTabelle = Quelle{[Schema = "dbo", Item = "tab_accounts_hierarchy"]}[Data],

    // --- Mengenbegrenzung und Abgrenzung an der Quelle ---------------------
    // Alle Filter stehen bewusst VOR allen weiteren Schritten, damit sie als
    // WHERE bzw. JOIN an SQL Server durchgereicht werden (Query Folding) und
    // nicht erst nach dem Laden greifen. Genau das ging in den Altmodellen
    // verloren und machte die Aktualisierung langsam.
    AktuellesGJ = 2025,   // 2025 = FY2025/26. Mit CURRENT_FY in
                          // lakehouse/notebooks/nb_00_config.py gleichhalten.

    // 1. Geschaeftsjahre: Vorjahr, laufendes Jahr, Folgejahr.
    //    Das Vorjahr wird gebraucht, weil [Net New ITY] den Vorjahresanteil
    //    abzieht - ohne FY-1 im Extrakt waere dieser Abzug immer 0.
    GefiltertNachJahr = Table.SelectRows(
        View,
        each [Fiscal_Year] >= AktuellesGJ - 1 and [Fiscal_Year] <= AktuellesGJ + 1
    ),

    // 2. Nur Ergebnisobjekte (Object_type = "OR"). Andere Objektarten sind
    //    keine Betriebe und wuerden die Werk-Zuordnung verfaelschen.
    GefiltertNachObjectType = Table.SelectRows(
        GefiltertNachJahr, each [Object_type] = "OR"
    ),

    // 3./4. Kontenhierarchie anhaengen, um auf Ertragskonten abzugrenzen.
    EingebetteterJoin = Table.NestedJoin(
        GefiltertNachObjectType, {"Account"},
        HierarchieTabelle, {"Kostenart"},
        "hier", JoinKind.LeftOuter
    ),
    ExpandierteHierarchie = Table.ExpandTableColumn(
        EingebetteterJoin, "hier", {"Level_2_Key"}, {"Level_2_Key"}
    ),

    // 5. Nur Total Revenue. Ohne diese Abgrenzung liefe der gesamte
    //    Kontenplan in die Umsatzkennzahlen - inklusive Kosten.
    Gefiltert = Table.SelectRows(
        ExpandierteHierarchie,
        each [Level_2_Key] = "IS10000_T - Total Revenue inkl. IFRS/ NEUTRA/MGMT"
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
