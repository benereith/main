// ===========================================================================
// Dataflow Gen2  ·  df_map_unit_assignment
//                   ->  stg_map_unit_assignment  ->  bronze_map_unit_assignment
// ===========================================================================
// Zweck : Gepflegtes Mapping, das CRM-Vorgaenge einem SAP-(Plan-)Betrieb
//         zuordnet. Quelle ist Mapping_Planwerke.xlsx (SharePoint,
//         Group Controlling / Net New ITY / 08_Budget) - dieselbe Datei, die
//         das Altmodell als dim_opp_mapping live in fct_opp gejoint hat.
// Ziel  : lakehouse_group_controlling / stg_map_unit_assignment
// Modus : REPLACE. Die Historisierung nach bronze_map_unit_assignment
//         uebernimmt nb_05_snapshot.py.
// Lauf  : taeglich, gemeinsam mit den CRM-Extrakten
//
// WARUM DAS MAPPING STRUKTURELL NOTWENDIG IST
// Es laesst sich NICHT durch CRM-Daten ersetzen. Die Zuordnung wird im
// Budget- und Forecast-Prozess von Hand gepflegt, weil die betroffenen Units
// noch nicht gewonnen sind - fuer sie existiert weder ein Vertrag im CRM noch
// ein Betrieb in den SAP-Stammdaten. Das Mapping traegt eine vorausschauende
// Annahme, die in keinem Quellsystem steht.
//
// WARUM ES HISTORISIERT WIRD
// Es ist ein manueller Input in offizielle Budgetzahlen. Ohne Snapshot laesst
// sich eine abgeschlossene Budgetrunde nach der naechsten Pflegerunde nicht
// mehr reproduzieren. Deshalb laeuft es durch dieselbe Staging-Historisierung
// wie die Fakten.
//
// SPALTEN DER EXCEL (Tabelle1)
// Die Datei traegt historisch zwei Spalten; die Sektorspalten sind die
// Erweiterung, ueber die kuenftig zugeordnet wird:
//   dim_opp_name[opportunityid]  bestehend, optional  Einzelfall-Ausnahme
//   Mapping Unit                 bestehend, Pflicht   SAP-Betriebsnummer
//   sektor                       neu, optional        Sektor als ANZEIGENAME
//   subsektor                    neu, optional        Subsektor als ANZEIGENAME
//   kommentar                    neu, optional        Begruendung
// Die Sektorspalten sind ueber SafeRename optional: solange sie fehlen,
// arbeitet das Mapping wie bisher rein ueber die Opportunity-ID.
//
// AUFLOESUNGSREIHENFOLGE (nb_20_gold, Abschnitt 5d):
//   1. Einzelfall-Ausnahme ueber opportunityid
//   2. Mapping ueber (sektor, subsektor)
//   3. Mapping ueber (sektor)
//   4. CRM-Bruecke cgplc_sapid am Vorgang - RUECKFALLEBENE hinter dem Mapping
//   5. NULL -> Regel DQ-MAP-001
//
// Die CRM-Bruecke steht bewusst HINTER dem Mapping: sie greift nur fuer
// Opportunities, die einen bestehenden Vertrag betreffen (Neuausschreibung
// eines laufenden Objekts), und laeuft fuer echte Net-New-Units
// definitionsgemaess leer. Das gepflegte Mapping ist die fachlich
// massgebliche Quelle, nicht der Rueckfall.
// ===========================================================================
let
    Quelle = SharePoint.Contents(
        "https://cpgplc.sharepoint.com/sites/GroupControlling", [ApiVersion = 15]
    ),
    Dokumente   = Quelle{[Name = "Shared Documents"]}[Content],
    Controlling = Dokumente{[Name = "Group Controlling"]}[Content],
    NetNewITY   = Controlling{[Name = "Net New ITY"]}[Content],
    Budget      = NetNewITY{[Name = "08_Budget"]}[Content],
    Datei       = Budget{[Name = "Mapping_Planwerke.xlsx"]}[Content],

    Mappe  = Excel.Workbook(Datei, null, true),
    Blatt  = Mappe{[Item = "Tabelle1", Kind = "Sheet"]}[Data],
    Header = Table.PromoteHeaders(Blatt, [PromoteAllScalars = true]),

    // Bestandsspalten: Namen exakt wie in der Datei. MissingField.Error ist
    // Absicht - fehlen sie, ist die Datei umgebaut worden und das muss
    // auffallen, nicht stillschweigend zu einem leeren Mapping fuehren.
    Umbenannt = Table.RenameColumns(
        Header,
        {
            {"dim_opp_name[opportunityid]", "opportunityid"},
            {"Mapping Unit", "sap_unit"}
        },
        MissingField.Error
    ),

    // Sektorspalten: optional, damit die Erweiterung schrittweise erfolgen
    // kann. Fehlen sie, werden sie als leere Spalten ergaenzt.
    Vorhanden = Table.ColumnNames(Umbenannt),
    MitSektor = if List.Contains(Vorhanden, "sektor")
        then Umbenannt
        else Table.AddColumn(Umbenannt, "sektor", each null, type nullable text),
    MitSubsektor = if List.Contains(Table.ColumnNames(MitSektor), "subsektor")
        then MitSektor
        else Table.AddColumn(MitSektor, "subsektor", each null, type nullable text),
    MitKommentar = if List.Contains(Table.ColumnNames(MitSubsektor), "kommentar")
        then MitSubsektor
        else Table.AddColumn(MitSubsektor, "kommentar", each null, type nullable text),

    Spalten = Table.SelectColumns(
        MitKommentar, {"opportunityid", "sektor", "subsektor", "sap_unit", "kommentar"}
    ),

    Typen = Table.TransformColumnTypes(
        Spalten,
        {
            {"opportunityid", type nullable text},
            {"sektor", type nullable text},
            {"subsektor", type nullable text},
            {"sap_unit", Int64.Type},
            {"kommentar", type nullable text}
        }
    ),

    // Leerstrings zu null normalisieren, damit die Aufloesung in Spark nicht
    // zwischen "" und null unterscheiden muss.
    Normalisiert = Table.TransformColumns(
        Typen,
        {
            {"opportunityid", each if _ = "" then null else Text.Trim(_), type nullable text},
            {"sektor", each if _ = "" then null else Text.Trim(_), type nullable text},
            {"subsektor", each if _ = "" then null else Text.Trim(_), type nullable text}
        }
    ),

    // Ohne Zielbetrieb ist eine Zeile kein Mapping. Und sie muss ENTWEDER
    // eine Ausnahme (opportunityid) ODER eine Sektorregel sein - sonst ist
    // sie nicht aufloesbar.
    Gueltig = Table.SelectRows(
        Normalisiert,
        each [sap_unit] <> null
            and ([opportunityid] <> null or [sektor] <> null)
    ),

    // Der Grain je Aufloesungsstufe muss eindeutig sein, sonst vervielfacht
    // der Join in nb_20_gold die Faktenzeilen.
    EindeutigId = Table.Distinct(
        Table.SelectRows(Gueltig, each [opportunityid] <> null), {"opportunityid"}
    ),
    EindeutigSektor = Table.Distinct(
        Table.SelectRows(Gueltig, each [opportunityid] = null), {"sektor", "subsektor"}
    ),
    Bereinigt = Table.Combine({EindeutigId, EindeutigSektor}),

    // Einmal je Lauf auswerten, nicht je Zeile - siehe fn_berlin_now.
    Ladezeit = DateTime.From(fn_berlin_now()),
    Snapshot = DateTime.Date(Ladezeit),

    MitLadezeit = Table.AddColumn(Bereinigt, "loaded_at", each Ladezeit, type datetime),
    MitSnapshot = Table.AddColumn(MitLadezeit, "snapshot_date", each Snapshot, type date)
in
    MitSnapshot
