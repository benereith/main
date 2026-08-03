// =============================================================================
// Flash Dataflow (Gen2) – BEx-Abrufe aus dem Fabric Lakehouse statt aus Excel
// =============================================================================
//
// Aufbau / Reihenfolge der Abfragen:
//
//   Parameter        : Upload_Monat, Upload_Jahr, P_* (Lakehouse, SharePoint)
//   Funktionen       : fn_ExcelSheet1, fn_LakehouseTabelle, fn_D6Datei
//   Staging (nur Ref): BEx_Abruf_RGF, BEx_Abruf_RTD, D6_LM, Input_D6, SAP_Stammdaten
//   Zwischenschritt  : BEx_Abruf, D6_Timestamp
//   Ziel-Entität     : Flash_Export        <- einziges "Enable Staging/Load"-Ziel
//
// WICHTIG für die Performance in Gen2:
//   - Nur Flash_Export als Ausgabe-Entität aktivieren.
//   - "Enable Staging" bei BEx_Abruf_RGF / BEx_Abruf_RTD / SAP_Stammdaten AN lassen,
//     bei allen Funktions- und Parameterabfragen AUS.
//   - Die alten Hilfsabfragen ("Beispieldatei", "Beispieldatei (2)/(3)",
//     "Parameter", "Parameter (2)", "... transformieren", "Datei transformieren
//     (2)/(3)") ersatzlos löschen – sie werden hier nicht mehr gebraucht.
//
// =============================================================================


// -----------------------------------------------------------------------------
// PARAMETER
// -----------------------------------------------------------------------------

// Upload_Monat
let
  Upload_Monat = 2 meta [
    IsParameterQuery = true,
    IsParameterQueryRequired = true,
    Type = type number,
    List = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
  ]
in
  Upload_Monat

// Upload_Jahr
// Wird für die Dateiauswahl im D6-Ordner gebraucht (Dateiname = yyyyMMdd_...).
// Dadurch funktioniert auch der Jahreswechsel (Januar -> Vormonat = Dezember Vorjahr).
let
  Upload_Jahr = Date.Year(DateTime.LocalNow()) meta [
    IsParameterQuery = true,
    IsParameterQueryRequired = true,
    Type = type number
  ]
in
  Upload_Jahr

// P_SharePointSite
let
  P_SharePointSite = "https://cpgplc.sharepoint.com/sites/GroupControlling" meta [
    IsParameterQuery = true,
    IsParameterQueryRequired = true,
    Type = type text
  ]
in
  P_SharePointSite

// P_WorkspaceId
// Workspace, in dem das Lakehouse mit den BEx-Daten liegt.
let
  P_WorkspaceId = "ddc66bda-5a20-49f0-be6e-b68e17a1cc90" meta [
    IsParameterQuery = true,
    IsParameterQueryRequired = true,
    Type = type text
  ]
in
  P_WorkspaceId

// P_LakehouseId
// <<< ANPASSEN >>> GUID des Lakehouse (Fabric -> Lakehouse -> URL-Segment nach /lakehouses/).
let
  P_LakehouseId = "00000000-0000-0000-0000-000000000000" meta [
    IsParameterQuery = true,
    IsParameterQueryRequired = true,
    Type = type text
  ]
in
  P_LakehouseId

// P_Tabelle_RGF / P_Tabelle_RTD
// <<< ANPASSEN >>> Namen der Delta-Tabellen im Lakehouse.
let
  P_Tabelle_RGF = "bex_flash_actuals_rgf" meta [
    IsParameterQuery = true, IsParameterQueryRequired = true, Type = type text
  ]
in
  P_Tabelle_RGF

let
  P_Tabelle_RTD = "bex_flash_actuals_rtd" meta [
    IsParameterQuery = true, IsParameterQueryRequired = true, Type = type text
  ]
in
  P_Tabelle_RTD

// P_ZeitversatzStunden
// Ersetzt den fest verdrahteten "+2 Stunden" im Flash_Export.
// SharePoint liefert UTC; im Winter ist der Versatz 1, im Sommer 2.
// Siehe Kommentar bei D6_Timestamp für die automatische Variante.
let
  P_ZeitversatzStunden = 2 meta [
    IsParameterQuery = true, IsParameterQueryRequired = true, Type = type number
  ]
in
  P_ZeitversatzStunden


// -----------------------------------------------------------------------------
// FUNKTIONEN
// -----------------------------------------------------------------------------

// fn_ExcelSheet1
// Ersetzt die vier bisherigen, inhaltsgleichen "Datei transformieren"-Funktionen.
(Datei as binary, optional Blatt as text) as table =>
let
  Blattname = Blatt ?? "Sheet1",
  Quelle = Excel.Workbook(Datei, null, true),
  Navigation = Quelle{[Item = Blattname, Kind = "Sheet"]}[Data],
  #"Höher gestufte Header" = Table.PromoteHeaders(Navigation, [PromoteAllScalars = true])
in
  #"Höher gestufte Header"

// fn_LakehouseTabelle
// Zentraler Einstieg ins Lakehouse. HierarchicalNavigation = true liefert die
// Navigation Workspace -> Lakehouse -> Tabelle; Filter/Spaltenauswahl darauf
// werden nach Delta zurückgefaltet (Query Folding), es wird also nicht die
// ganze Tabelle in die Mashup-Engine gezogen.
(TabellenName as text) as table =>
let
  Quelle = Lakehouse.Contents([HierarchicalNavigation = true]),
  Workspace = Quelle{[workspaceId = P_WorkspaceId]}[Data],
  LH = Workspace{[lakehouseId = P_LakehouseId]}[Data],
  Tabelle = LH{[Id = TabellenName, ItemKind = "Table"]}[Data]
in
  Tabelle

// fn_D6Ordner
// Der Navigationspfad war bisher sechsmal kopiert – jetzt einmal.
() as table =>
let
  Quelle = SharePoint.Contents(P_SharePointSite, [ApiVersion = 15]),
  Dokumente = Quelle{[Name = "Shared Documents"]}[Content],
  GC = Dokumente{[Name = "Group Controlling"]}[Content],
  Flash = GC{[Name = "Flash"]}[Content],
  Input = Flash{[Name = "01_Input"]}[Content],
  D6 = Input{[Name = "D6"]}[Content]
in
  D6

// fn_D6Datei
// Liefert die aktuellste D6-Datei eines Monats als Record [Content, Erstellt].
// Ersetzt den hart codierten Dateinamen "20260605_Input_D6_2.XLSX" in D6_LM.
// Annahme: Dateiname beginnt mit yyyyMMdd (wie in allen bisherigen Dateien).
(Jahr as number, Monat as number) as record =>
let
  Praefix = Text.From(Number.Round(Jahr)) & Text.PadStart(Text.From(Number.Round(Monat)), 2, "0"),
  Ordner = fn_D6Ordner(),
  Kandidaten = Table.SelectRows(Ordner, each
      [Attributes]?[Hidden]? <> true
      and not Text.StartsWith([Name], "~$")
      and Text.EndsWith([Name], ".xlsx", Comparer.OrdinalIgnoreCase)
      and Text.StartsWith([Name], Praefix)),
  Sortiert = Table.Sort(Kandidaten, {{"Date created", Order.Descending}}),
  Treffer =
    if Table.IsEmpty(Sortiert) then
      error Error.Record(
        "D6-Datei fehlt",
        "Im Ordner 01_Input/D6 liegt keine Datei mit dem Präfix " & Praefix & ".",
        Praefix)
    else
      Sortiert{0}
in
  [Content = Treffer[Content], Erstellt = Treffer[#"Date created"]]


// -----------------------------------------------------------------------------
// BEX – jetzt aus dem Lakehouse
// -----------------------------------------------------------------------------
//
// Beide Abfragen liefern bewusst dasselbe Schema:
//     Werk (Int64) | Kostenart (text: "UPC" | "Revenue") | Budget | FC | Act
// RTD kennt kein Budget/Act -> 0. Dadurch lassen sich beide Tabellen unten
// einfach anhängen und gruppieren, statt sie zu joinen.
//
// <<< ANPASSEN >>> Die Quellspaltennamen (werk, kostenart, budget, fc_version,
// act) an die tatsächlichen Lakehouse-Spalten anpassen. Falls RGF und RTD im
// Lakehouse in EINER Tabelle mit Spalte "version" liegen, siehe Hinweis unten.

// BEx_Abruf_RGF
let
  Quelle = fn_LakehouseTabelle(P_Tabelle_RGF),

  // Erst filtern, dann Spalten wählen – beides faltet nach Delta zurück.
  #"Gefilterte Zeilen" = Table.SelectRows(Quelle, each
      [kostenart] = "Operating Profit ink" or [kostenart] = "Total Revenue inkl."),
  #"Spalten auswählen" = Table.SelectColumns(#"Gefilterte Zeilen",
      {"werk", "kostenart", "budget", "fc_version", "act"}),
  #"Umbenannte Spalten" = Table.RenameColumns(#"Spalten auswählen", {
      {"werk", "Werk"}, {"kostenart", "Kostenart"}, {"budget", "Budget"},
      {"fc_version", "FC"}, {"act", "Act"}}),

  #"Geänderter Spaltentyp" = Table.TransformColumnTypes(#"Umbenannte Spalten", {
      {"Werk", Int64.Type}, {"Kostenart", type text},
      {"Budget", type number}, {"FC", type number}, {"Act", type number}}),

  // Kostenart auf Kurzschlüssel mappen. Replacer.ReplaceText hat vorher auf
  // Teilstrings ersetzt – die Record-Lookup-Variante trifft nur exakt.
  KostenartMap = [#"Operating Profit ink" = "UPC", #"Total Revenue inkl." = "Revenue"],
  #"Kostenart gemappt" = Table.TransformColumns(#"Geänderter Spaltentyp",
      {{"Kostenart", each Record.FieldOrDefault(KostenartMap, _, _), type text}}),

  #"Ersetzter Wert" = Table.ReplaceValue(#"Kostenart gemappt", null, 0,
      Replacer.ReplaceValue, {"Budget", "FC", "Act"})
in
  #"Ersetzter Wert"

// BEx_Abruf_RTD
let
  Quelle = fn_LakehouseTabelle(P_Tabelle_RTD),

  #"Gefilterte Zeilen" = Table.SelectRows(Quelle, each
      [kostenart] = "Operating Profit ink" or [kostenart] = "Total Revenue inkl."),
  #"Spalten auswählen" = Table.SelectColumns(#"Gefilterte Zeilen",
      {"werk", "kostenart", "fc_version"}),
  #"Umbenannte Spalten" = Table.RenameColumns(#"Spalten auswählen", {
      {"werk", "Werk"}, {"kostenart", "Kostenart"}, {"fc_version", "FC"}}),

  #"Geänderter Spaltentyp" = Table.TransformColumnTypes(#"Umbenannte Spalten", {
      {"Werk", Int64.Type}, {"Kostenart", type text}, {"FC", type number}}),

  KostenartMap = [#"Operating Profit ink" = "UPC", #"Total Revenue inkl." = "Revenue"],
  #"Kostenart gemappt" = Table.TransformColumns(#"Geänderter Spaltentyp",
      {{"Kostenart", each Record.FieldOrDefault(KostenartMap, _, _), type text}}),

  #"Ersetzter Wert" = Table.ReplaceValue(#"Kostenart gemappt", null, 0,
      Replacer.ReplaceValue, {"FC"}),

  // Schema an RGF angleichen, damit unten Table.Combine funktioniert.
  #"Budget/Act ergänzt" = Table.AddColumn(
      Table.AddColumn(#"Ersetzter Wert", "Budget", each 0, type number),
      "Act", each 0, type number),
  #"Spaltenreihenfolge" = Table.SelectColumns(#"Budget/Act ergänzt",
      {"Werk", "Kostenart", "Budget", "FC", "Act"})
in
  #"Spaltenreihenfolge"

// -----------------------------------------------------------------------------
// Variante, falls RGF und RTD im Lakehouse in EINER Tabelle mit Versionsspalte
// liegen – dann BEx_Abruf_RGF/RTD löschen und BEx_Abruf direkt so aufbauen:
//
//   Quelle = fn_LakehouseTabelle("bex_flash_actuals"),
//   Gefiltert = Table.SelectRows(Quelle, each
//       ([kostenart] = "Operating Profit ink" or [kostenart] = "Total Revenue inkl.")
//       and ([version] = "RGF" or [version] = "RTD")),
//   ... danach identisch ab Schritt "Gruppiert" weiter.
// -----------------------------------------------------------------------------


// BEx_Abruf
// Ersetzt NestedJoin + Expand + Unpivot + Pivot durch zweimal Gruppieren.
// Ergebnis: eine Zeile je Werk mit den sechs Kennzahlspalten.
let
  Kombiniert = Table.Combine({BEx_Abruf_RGF, BEx_Abruf_RTD}),

  // FC gesamt = FC(RGF) + FC(RTD). Über die Gruppierung statt über einen Join:
  // ein Werk, das nur in einer der beiden Quellen vorkommt, behält dadurch
  // seinen Wert (der alte LeftOuter-Join lieferte hier FC = null, siehe Notes).
  Gruppiert = Table.Group(Kombiniert, {"Werk", "Kostenart"}, {
      {"Budget", each List.Sum([Budget]) ?? 0, type number},
      {"FC",     each List.Sum([FC]) ?? 0,     type number},
      {"Act",    each List.Sum([Act]) ?? 0,    type number}}),

  // Kennzahlen in Zielspalten aufteilen (statt Unpivot/Pivot).
  Aufgeteilt = Table.AddColumn(Gruppiert, "Kz", each
      let IstRevenue = [Kostenart] = "Revenue" in [
        Revenue_Budget          = if IstRevenue then [Budget] else 0,
        Revenue_FC_Version_RGF  = if IstRevenue then [FC]     else 0,
        Revenue_Act             = if IstRevenue then [Act]    else 0,
        UPC_Budget              = if IstRevenue then 0 else [Budget],
        UPC_FC_Version_RGF      = if IstRevenue then 0 else [FC],
        UPC_Act                 = if IstRevenue then 0 else [Act]
      ]),

  Kennzahlen = {"Revenue_Budget", "Revenue_FC_Version_RGF", "Revenue_Act",
                "UPC_Budget", "UPC_FC_Version_RGF", "UPC_Act"},

  Erweitert = Table.ExpandRecordColumn(Aufgeteilt, "Kz", Kennzahlen, Kennzahlen),

  // Skalierung auf TEUR (früher der Schritt "Skaliert" vor dem Pivot).
  ProWerk = Table.Group(Erweitert, {"Werk"},
      List.Transform(Kennzahlen, (Spalte) =>
          {Spalte, (t) => (List.Sum(Table.Column(t, Spalte)) ?? 0) / 1000, type number}))
in
  ProWerk


// -----------------------------------------------------------------------------
// D6 (SharePoint)
// -----------------------------------------------------------------------------

// D6_Datei_Aktuell / D6_Datei_Vormonat
// Einmal auflösen, damit die Ordnerliste nicht mehrfach von SharePoint kommt.
let
  D6_Datei_Aktuell = fn_D6Datei(Upload_Jahr, Upload_Monat)
in
  D6_Datei_Aktuell

let
  Vormonat = if Upload_Monat = 1 then 12 else Upload_Monat - 1,
  Vorjahr  = if Upload_Monat = 1 then Upload_Jahr - 1 else Upload_Jahr,
  D6_Datei_Vormonat = fn_D6Datei(Vorjahr, Vormonat)
in
  D6_Datei_Vormonat

// D6_Timestamp
// Skalar statt einer Spalte, die vorher per FillDown/FillUp über die ganze
// Tabelle gezogen wurde.
//
// Automatische Sommerzeit statt festem Versatz (optional):
//   DateTimeZone.RemoveZone(DateTimeZone.ToLocal(DateTime.AddZone(Roh, 0)))
// funktioniert nur, wenn die Gateway-/Kapazitätszeitzone stimmt – deshalb
// bleibt hier der explizite Parameter.
let
  Roh = D6_Datei_Aktuell[Erstellt],
  D6_Timestamp = Roh + #duration(0, P_ZeitversatzStunden, 0, 0)
in
  D6_Timestamp

// D6_Spalten
// Feste Spaltenliste der D6-Datei – einmal definiert, in Input_D6 verwendet.
let
  D6_Spalten = {"Buchungskreis", "Flash", "Abg.", "Niederlassung", "Bezirk", "Werk",
                "Name 1", "Geschl.", "Exp.", "Bud.NS", "Bud.UP", "Flash NS", "Flash UP",
                "Diff.NS", "Diff.UP", "Kum.Bud.NS", "Kum.Bud.UP", "Kum.Act.+Flash NS",
                "Kum.Act.+Flash UP", "Kum.Diff.NS", "Kum.Diff.UP"}
in
  D6_Spalten

// D6_LM
// Vormonatsdatei: Werke ohne Abrechnung und ohne Flash.
let
  Transformiert = fn_ExcelSheet1(D6_Datei_Vormonat[Content]),

  // Leerwerte kamen je nach Datei als "" ODER als null an – ?? fängt beides ab.
  #"Gefilterte Zeilen" = Table.SelectRows(Transformiert, each
      ([#"Abg."] ?? "") = "" and ([Flash] ?? "") = ""),
  #"Nur Werk" = Table.SelectColumns(#"Gefilterte Zeilen", {"Werk"}),
  #"Geänderter Spaltentyp" = Table.TransformColumnTypes(#"Nur Werk", {{"Werk", Int64.Type}}),
  #"Eindeutige Werke" = Table.Distinct(#"Geänderter Spaltentyp")
in
  #"Eindeutige Werke"

// Input_D6
let
  Transformiert = fn_ExcelSheet1(D6_Datei_Aktuell[Content]),

  #"Spalten auswählen" = Table.SelectColumns(Transformiert, D6_Spalten, MissingField.Error),

  #"Geänderter Spaltentyp" = Table.TransformColumnTypes(#"Spalten auswählen", {
      {"Buchungskreis", Int64.Type}, {"Flash", type text}, {"Abg.", type text},
      {"Niederlassung", type text}, {"Bezirk", type text}, {"Werk", Int64.Type},
      {"Name 1", type text}, {"Geschl.", type text}, {"Exp.", type text},
      {"Bud.NS", type number}, {"Bud.UP", type number}, {"Flash NS", type number},
      {"Flash UP", type number}, {"Diff.NS", type number}, {"Diff.UP", type number},
      {"Kum.Bud.NS", type number}, {"Kum.Bud.UP", type number},
      {"Kum.Act.+Flash NS", type number}, {"Kum.Act.+Flash UP", type number},
      {"Kum.Diff.NS", type number}, {"Kum.Diff.UP", type number}}),

  KeineAbrechnung = List.Buffer(D6_LM[Werk]),

  #"Status hinzugefügt" = Table.AddColumn(#"Geänderter Spaltentyp", "Status", each
      if ([#"Abg."] ?? "") = "A" then "Abgerechnet"
      else if ([Flash] ?? "") = "X" then "Flash"
      else if List.Contains(KeineAbrechnung, [Werk]) then "keine Abrechnung"
      else "offen", type text),

  // Nur was Flash_Export tatsächlich braucht.
  #"Finale Spalten" = Table.SelectColumns(#"Status hinzugefügt",
      {"Werk", "Bezirk", "Flash NS", "Flash UP", "Status"})
in
  #"Finale Spalten"


// -----------------------------------------------------------------------------
// STAMMDATEN
// -----------------------------------------------------------------------------

// SAP_Stammdaten
let
  Quelle = PowerPlatform.Dataflows(null),
  Workspaces = Quelle{[Id = "Workspaces"]}[Data],
  Workspace = Workspaces{[workspaceId = "ddc66bda-5a20-49f0-be6e-b68e17a1cc90"]}[Data],
  Dataflow = Workspace{[dataflowId = "a65e47b1-6a8b-4cf2-8131-c90e55bf14c7"]}[Data],
  sap_master_data_unit_ = Dataflow{[entity = "sap_master_data_unit", version = ""]}[Data],

  Managements = {"Eurest", "Food Affairs", "Kanne", "Leonardi", "Medirest"},

  // 1. Zuerst filtern
  #"Gefilterte Zeilen" = Table.SelectRows(sap_master_data_unit_, each
      List.Contains(Managements, [bezeichnung_management]) and [verantwortungsbereich] = 1),

  // 2. Dann auf die tatsächlich benötigten Spalten reduzieren.
  //    "Werk - Bezeichnung" und "Betriebstyp" werden von Flash_Export nicht
  //    verwendet; sie stehen unten in einer eigenen Abfrage, falls sie für ein
  //    anderes Ziel gebraucht werden.
  #"Spalten auswählen" = Table.SelectColumns(#"Gefilterte Zeilen",
      {"betrieb", "bezeichnung_betrieb", "vertragsart", "innenauftragsart",
       "bezeichnung_management", "bezeichnung_region"})
in
  #"Spalten auswählen"

// SAP_Stammdaten_Erweitert
// Nur laden/aktivieren, wenn "Werk - Bezeichnung" bzw. "Betriebstyp" wirklich
// als Ausgabe gebraucht werden. Sonst diese Abfrage löschen.
let
  Quelle = PowerPlatform.Dataflows(null),
  Workspaces = Quelle{[Id = "Workspaces"]}[Data],
  Workspace = Workspaces{[workspaceId = "ddc66bda-5a20-49f0-be6e-b68e17a1cc90"]}[Data],
  Dataflow = Workspace{[dataflowId = "a65e47b1-6a8b-4cf2-8131-c90e55bf14c7"]}[Data],
  sap_master_data_unit_ = Dataflow{[entity = "sap_master_data_unit", version = ""]}[Data],

  Managements = {"Eurest", "Food Affairs", "Kanne", "Leonardi", "Medirest"},
  #"Gefilterte Zeilen" = Table.SelectRows(sap_master_data_unit_, each
      List.Contains(Managements, [bezeichnung_management]) and [verantwortungsbereich] = 1),

  PlanbetriebeRoll = List.Buffer({127, 1678, 1680, 1682, 1684, 1686, 1688, 1690, 1692, 1694,
      1696, 1862, 1863, 2119, 4350, 4590, 5200, 5226, 7133, 7120, 7937, 8535, 8849, 9736,
      9747, 9876, 9937}),
  PlanbetriebeITY = List.Buffer({1679, 1681, 1683, 1685, 1687, 1689, 1691, 1693, 1695, 7933,
      8385, 8386, 9911, 9913, 9916, 9920, 9922, 9924, 9926, 9933, 9936, 9940, 9944, 9945,
      9946, 9947, 9950, 9952}),
  PlanbetriebeLfL = List.Buffer({7123, 4424, 4923, 421, 20, 7, 21, 4950, 9707}),

  #"Werk - Bezeichnung" = Table.AddColumn(#"Gefilterte Zeilen", "Werk - Bezeichnung", each
      Text.PadStart(Text.From([betrieb], "de-DE"), 4, "0") & " - " & [bezeichnung_betrieb],
      type text),

  #"Betriebstyp hinzugefügt" = Table.AddColumn(#"Werk - Bezeichnung", "Betriebstyp", each
      if List.Contains(PlanbetriebeRoll, [betrieb]) then "Plan-Betriebe Roll"
      else if List.Contains(PlanbetriebeITY, [betrieb]) then "Plan-Betriebe ITY"
      else if List.Contains(PlanbetriebeLfL, [betrieb]) then "Plan-Betriebe LfL"
      else "Real-Betriebe", type text)
in
  #"Betriebstyp hinzugefügt"


// -----------------------------------------------------------------------------
// ZIEL-ENTITÄT
// -----------------------------------------------------------------------------

// Flash_Export
let
  Stammdaten = Table.SelectRows(SAP_Stammdaten, each [bezeichnung_region] <> "STADIA"),

  // Beide Join-Partner sind bereits auf die nötigen Spalten reduziert.
  D6 = Table.Buffer(Input_D6),
  BEx = Table.Buffer(BEx_Abruf),

  #"Join D6" = Table.NestedJoin(Stammdaten, {"betrieb"}, D6, {"Werk"}, "D6", JoinKind.LeftOuter),
  #"Erweitert D6" = Table.ExpandTableColumn(#"Join D6", "D6",
      {"Bezirk", "Flash NS", "Flash UP", "Status"}),

  #"Join BEx" = Table.NestedJoin(#"Erweitert D6", {"betrieb"}, BEx, {"Werk"}, "BEx", JoinKind.LeftOuter),
  #"Erweitert BEx" = Table.ExpandTableColumn(#"Join BEx", "BEx",
      {"Revenue_Budget", "Revenue_FC_Version_RGF", "Revenue_Act",
       "UPC_Budget", "UPC_FC_Version_RGF", "UPC_Act"}),

  FCVertragsarten = List.Buffer({"M", "PR", "XK", "XP"}),

  // Beide Adj-Spalten in einem Durchlauf – die Bedingungskette wird nur
  // einmal statt zweimal je Zeile ausgewertet.
  #"Adj-Werte" = Table.AddColumn(#"Erweitert BEx", "Adj", (Zeile) =>
      try
        let
          Ist = Zeile[innenauftragsart] = "I" or Zeile[innenauftragsart] = "N",
          Fc  = Zeile[Status] = "offen"
                or (Zeile[Status] = "Flash"
                    and List.Contains(FCVertragsarten, Zeile[vertragsart]))
        in
          if Ist then
            [Rev = Zeile[Revenue_Act], UP = Zeile[UPC_Act]]
          else if Zeile[Status] = "keine Abrechnung" then
            [Rev = Zeile[#"Flash NS"], UP = Zeile[#"Flash UP"]]
          else if Fc then
            [Rev = Zeile[Revenue_FC_Version_RGF], UP = Zeile[UPC_FC_Version_RGF]]
          else
            [Rev = Zeile[#"Flash NS"], UP = Zeile[#"Flash UP"]]
      otherwise [Rev = null, UP = null]),

  #"Adj erweitert" = Table.ExpandRecordColumn(#"Adj-Werte", "Adj",
      {"Rev", "UP"}, {"Adj Rev", "Adj UPC"}),

  // Timestamp als Skalar statt FillDown/FillUp über die ganze Tabelle.
  #"Timestamp hinzugefügt" = Table.AddColumn(#"Adj erweitert", "Timestamp",
      each D6_Timestamp, type datetime),

  #"Umbenannte Spalten" = Table.RenameColumns(#"Timestamp hinzugefügt", {
      {"betrieb", "Werk"}, {"bezeichnung_betrieb", "Werksbezeichnung"},
      {"Bezirk", "Region"}, {"vertragsart", "Vertragsart"}}),

  #"Finale Spalten" = Table.SelectColumns(#"Umbenannte Spalten",
      {"Werk", "Region", "Werksbezeichnung", "Vertragsart", "bezeichnung_region",
       "bezeichnung_management", "Status", "Adj Rev", "Adj UPC", "Revenue_Budget",
       "UPC_Budget", "Revenue_FC_Version_RGF", "UPC_FC_Version_RGF", "Timestamp"}),

  #"Geänderter Spaltentyp" = Table.TransformColumnTypes(#"Finale Spalten", {
      {"Werk", Int64.Type}, {"Region", type text}, {"Werksbezeichnung", type text},
      {"Vertragsart", type text}, {"bezeichnung_region", type text},
      {"bezeichnung_management", type text}, {"Status", type text},
      {"Adj Rev", type number}, {"Adj UPC", type number},
      {"Revenue_Budget", type number}, {"UPC_Budget", type number},
      {"Revenue_FC_Version_RGF", type number}, {"UPC_FC_Version_RGF", type number},
      {"Timestamp", type datetime}})
in
  #"Geänderter Spaltentyp"
