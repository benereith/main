// =====================================================================
// Dataflow Gen2 - Query: map_opportunity_unit
// Quelle : SharePoint, Mapping_Planwerke.xlsx (Group Controlling)
// Ziel   : Lakehouse-Tabelle map_opportunity_unit (Destination: REPLACE)
// Lauf   : taeglich, gemeinsam mit den Faktenqueries
//
// Ersetzt den Live-Join dim_opp_mapping, der bisher innerhalb von fct_opp
// ausgefuehrt wurde. Die Zuordnung Opportunity -> SAP-Betrieb ist eine
// gepflegte Mappingtabelle und gehoert nicht in die Faktenstrecke:
// als eigene Tabelle ist sie ueber eine Beziehung nutzbar, versionierbar
// und blockiert nicht den Ladelauf der Fakten, wenn SharePoint klemmt.
//
// Diese Tabelle ist NICHT durch CRM-Daten ersetzbar. Sie traegt die
// Zuordnung fuer Units, die noch nicht gewonnen sind - im Budget- und
// Forecast-Prozess manuell gepflegt. Diese Information existiert
// definitionsgemaess weder im CRM noch in den SAP-Stammdaten.
//
// Historisiert wie die Fakten: das Mapping ist ein manueller Input in
// offizielle Budgetzahlen. Ohne Snapshot laesst sich eine abgeschlossene
// Budgetrunde nach der naechsten Mappingpflege nicht mehr reproduzieren.
// =====================================================================
let
    Quelle =
        SharePoint.Contents(
            "https://cpgplc.sharepoint.com/sites/GroupControlling",
            [ApiVersion = 15]
        ),

    Dokumente   = Quelle{[Name = "Shared Documents"]}[Content],
    Controlling = Dokumente{[Name = "Group Controlling"]}[Content],
    NetNewITY   = Controlling{[Name = "Net New ITY"]}[Content],
    Budget      = NetNewITY{[Name = "08_Budget"]}[Content],
    Datei       = Budget{[Name = "Mapping_Planwerke.xlsx"]}[Content],

    Mappe   = Excel.Workbook(Datei, null, true),
    Blatt   = Mappe{[Item = "Tabelle1", Kind = "Sheet"]}[Data],
    Header  = Table.PromoteHeaders(Blatt, [PromoteAllScalars = true]),

    // Spaltennamen der Excel auf Modellkonvention bringen.
    // Die Quellspalte heisst dort woertlich "dim_opp_name[opportunityid]".
    Umbenannt =
        Table.RenameColumns(
            Header,
            {
                {"dim_opp_name[opportunityid]", "opportunityid"},
                {"Mapping Unit", "sap_unit"}
            },
            MissingField.Error
        ),

    Spalten = Table.SelectColumns(Umbenannt, {"opportunityid", "sap_unit"}),

    Typen =
        Table.TransformColumnTypes(
            Spalten,
            {{"opportunityid", type text}, {"sap_unit", Int64.Type}}
        ),

    // Nur vollstaendig gepflegte Zeilen uebernehmen.
    Bereinigt =
        Table.SelectRows(
            Typen,
            each [opportunityid] <> null
                and [opportunityid] <> ""
                and [sap_unit] <> null
        ),

    // Der Grain muss eindeutig sein, sonst vervielfacht die Beziehung
    // im Semantic Model die Opportunity-Zeilen.
    Eindeutig = Table.Distinct(Bereinigt, {"opportunityid"}),

    // Einmal je Lauf auswerten, nicht je Zeile - siehe fn_berlin_now.
    Ladezeit = fn_berlin_now(),
    Snapshot = DateTime.Date(DateTime.From(Ladezeit)),

    MitSnapshot =
        Table.AddColumn(Eindeutig, "snapshot_date", each Snapshot, type date),

    MitLadezeit =
        Table.AddColumn(MitSnapshot, "loaded_at", each Ladezeit, type datetimezone)
in
    MitLadezeit
