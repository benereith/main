// ===========================================================================
// Dataflow Gen2  ·  df_map_unit_assignment  ->  bronze_map_unit_assignment
// ===========================================================================
// Zweck : Gepflegtes Mapping, das CRM-Vorgaenge einem SAP-(Plan-)Betrieb
//         zuordnet. Die fachliche Information, WOHIN ein Vorgang gehoert,
//         haengt am Sektor und Subsektor - deshalb ist das Mapping primaer
//         darueber geschluesselt.
//
// WARUM EINE MAPPING-TABELLE UND KEIN CRM-FELD
// cgplc_sapid ist am Vorgang nur lueckenhaft gepflegt, und die SAP-Nummer am
// Konto ist ein Debitor, kein Betrieb. Die Zuordnung "dieser Sektor/Subsektor
// plant auf jenem Planbetrieb" ist Controlling-Wissen und gehoert in eine
// Tabelle, die das Controlling pflegt - wie bisher Mapping_Planwerke.xlsx,
// nur dass die Datei jetzt versioniert geladen und ihre Aufloesung im Fakt
// nachvollziehbar protokolliert wird (Spalte werk_zuordnung).
//
// AUFBAU DER EXCEL-TABELLE (Tabelle1, Spaltennamen exakt so):
//   entity_id   optional  opportunityid oder cgplc_cgcontractid fuer
//                         Einzelfall-Ausnahmen. Gewinnt vor allem anderen.
//   sektor      optional  Sektor als ANZEIGENAME (cgplc_sectorlookupname),
//                         z. B. "Healthcare" - nicht die GUID
//   subsektor   optional  Subsektor als ANZEIGENAME (cgplc_subsectorname)
//   werk        Pflicht   SAP-Betriebsnummer (Ziel der Zuordnung)
//   kommentar   optional  Begruendung der Zuordnung
//
// AUFLOESUNGSREIHENFOLGE (umgesetzt in nb_20_gold, Abschnitt 5d):
//   1. entity_id-Ausnahme aus dieser Tabelle
//   2. cgplc_sapid am Vorgang selbst
//   3. Mapping ueber (sektor, subsektor)
//   4. Mapping ueber (sektor) - Zeilen mit leerem subsektor
//   5. NULL -> Regel DQ-MAP-001
//
// Ziel    : lakehouse_group_controlling / bronze_map_unit_assignment
// Modus   : Ersetzen (das Mapping ist ein Stammdatum, keine Historie)
// Zeitplan: taeglich 05:00, zusammen mit den CRM-Extrakten
// ===========================================================================
let
    Quelle = SharePoint.Contents(
        "https://cpgplc.sharepoint.com/sites/GroupControlling", [ApiVersion = 15]
    ),
    Dokumente = Quelle{[Name = "Shared Documents"]}[Content],
    Ordner1 = Dokumente{[Name = "Group Controlling"]}[Content],
    Ordner2 = Ordner1{[Name = "Net New ITY"]}[Content],
    Ordner3 = Ordner2{[Name = "08_Budget"]}[Content],
    Datei = Ordner3{[Name = "Mapping_Planwerke.xlsx"]}[Content],
    Arbeitsmappe = Excel.Workbook(Datei, null, true),
    Blatt = Arbeitsmappe{[Item = "Tabelle1", Kind = "Sheet"]}[Data],
    MitKopfzeile = Table.PromoteHeaders(Blatt, [PromoteAllScalars = true]),

    // Nur Zeilen mit Zielbetrieb sind gueltige Mappings.
    NurGueltige = Table.SelectRows(
        MitKopfzeile, each [werk] <> null and [werk] <> ""
    ),

    // Leere Strings zu null normalisieren, damit die Aufloesung in Spark
    // nicht zwischen "" und null unterscheiden muss.
    Normalisiert = Table.TransformColumns(
        NurGueltige,
        {
            {"entity_id", each if _ = "" then null else Text.Trim(Text.From(_)), type nullable text},
            {"sektor", each if _ = "" then null else Text.Trim(Text.From(_)), type nullable text},
            {"subsektor", each if _ = "" then null else Text.Trim(Text.From(_)), type nullable text}
        }
    ),
    Typisiert = Table.TransformColumnTypes(Normalisiert, {{"werk", Int64.Type}}),

    // Eine Zeile muss ENTWEDER eine Ausnahme (entity_id) ODER ein
    // Sektor-Mapping sein. Zeilen ohne beides waeren nicht aufloesbar.
    Plausibel = Table.SelectRows(
        Typisiert, each [entity_id] <> null or [sektor] <> null
    ),

    MitSnapshot = Table.AddColumn(
        Plausibel, "snapshot_date", each Date.From(DateTime.FixedLocalNow()), type date
    )
in
    MitSnapshot
