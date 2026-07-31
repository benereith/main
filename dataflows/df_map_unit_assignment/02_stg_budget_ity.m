// ===========================================================================
// Dataflow Gen2 "df_map_unit_assignment"  ·  Abfrage: stg_budget_ity
// ===========================================================================
// Budgetannahmen zum unknown-ITY-Effekt aus der gepflegten Planungsdatei
// 2026_04_29_Planung_unknown_ITY_Effekt.xlsx (SharePoint, Group Controlling /
// Net New ITY / 08_Budget).
// Ziel  : lakehouse_group_controlling / stg_budget_ity
// Modus : REPLACE. Die Historisierung nach bronze_budget_ity uebernimmt
//         nb_05_snapshot.py.
// Lauf  : taeglich, gemeinsam mit stg_map_unit_assignment
// Benoetigt die Funktionsquery fn_berlin_now (00_fn_berlin_now.m) im selben
// Dataflow.
//
// WARUM DIESE ABFRAGE HIER UND NICHT IM SEMANTIKMODELL
// Bisher lud die Modelltabelle 'CRM Data' diese Excel bei JEDER Aktualisierung
// direkt von SharePoint - mit der gesamten Fachlogik (Periodenraster, YTD,
// Werkableitung, Eroeffnungsregel) in Power Query. Das hatte drei Folgen:
//   1. Der Bericht haengt an SharePoint. Ist die Datei gesperrt, umbenannt
//      oder der Ordner umgezogen, scheitert die Modellaktualisierung - nicht
//      der Ladelauf, in dem der Fehler hingehoert.
//   2. Kein Stichtag. Welcher Stand der Datei in einer Zahl steckt, war nicht
//      feststellbar, und eine abgeschlossene Budgetrunde nach der naechsten
//      Pflegerunde nicht mehr reproduzierbar.
//   3. Die Periodenlogik lag ein zweites Mal in Power Query, obwohl derselbe
//      Fanout im Lakehouse bereits existiert.
// Diese Abfrage laedt deshalb nur noch die ROHZEILEN. Raster, Kumulation und
// Werkableitung passieren in nb_10_silver / nb_20_gold, gemeinsam mit allem
// anderen.
//
// WARUM IM DATAFLOW df_map_unit_assignment
// Gleiche Quelle, gleicher Fehlerfall: dieselbe SharePoint-Site, dieselbe
// Bibliothek, derselbe Ordner 08_Budget wie Mapping_Planwerke.xlsx. Nach der
// Faustregel aus dataflows/README.md gehoeren beide damit in einen Dataflow;
// ein vierter Dataflow braechte eine zusaetzliche Aktivitaet in der Pipeline,
// ohne einen Fehlerfall zu entkoppeln.
//
// AUFBAU DER EXCEL
// Zwei Blaetter mit identischem Spaltensatz, "NB Rohdaten" (New Business) und
// "LB Rohdaten" (Lost Business). Beide werden gestapelt; aus welchem Blatt
// eine Zeile stammt, traegt die Spalte nb_lb.
//   bezeichnung_management   Managementeinheit
//   bezeichnung_region       Region
//   Werk - Bezeichnung       "1234 - Klartext", Betriebsnummer in den ersten
//                            vier Zeichen
//   ity_cluster              unknown ITY / unknown Roll
//   name                     Bezeichnung des Vorgangs
//   Info                     Freitext, endet auf das Eroeffnungsdatum
//   FY_JahrMonat             Periode; massgeblich sind die letzten beiden
//                            Zeichen = FY-Periode 1-12 (1 = Oktober)
//   ity_effect               Budgetierter Effekt des Monats in EUR
//
// Die Kopfzeile des zweiten Blattes wird beim Stapeln zu einer Datenzeile und
// unten ueber bezeichnung_management wieder entfernt - dieselbe Bereinigung
// wie in der Altabfrage.
// ===========================================================================
let
    Quelle = SharePoint.Contents(
        "https://cpgplc.sharepoint.com/sites/GroupControlling", [ApiVersion = 15]
    ),
    Dokumente   = Quelle{[Name = "Shared Documents"]}[Content],
    Controlling = Dokumente{[Name = "Group Controlling"]}[Content],
    NetNewITY   = Controlling{[Name = "Net New ITY"]}[Content],
    Budget      = NetNewITY{[Name = "08_Budget"]}[Content],
    Datei       = Budget{[Name = "2026_04_29_Planung_unknown_ITY_Effekt.xlsx"]}[Content],

    Mappe = Excel.Workbook(Datei),

    // Beide Rohdatenblaetter, sonst nichts. Auswertungsblaetter der Datei
    // enthalten Zwischensummen und wuerden doppelt zaehlen.
    Blaetter = Table.SelectRows(
        Mappe, each ([Name] = "NB Rohdaten" or [Name] = "LB Rohdaten")
    ),
    Gestapelt = Table.ExpandTableColumn(
        Blaetter,
        "Data",
        {"Column1", "Column2", "Column3", "Column4", "Column5", "Column6",
         "Column7", "Column8", "Column9", "Column10", "Column11"}
    ),
    Header = Table.PromoteHeaders(Gestapelt, [PromoteAllScalars = true]),

    // Die erste Spalte traegt nach PromoteHeaders den Blattnamen der ERSTEN
    // Zeile als Spaltennamen ("NB Rohdaten"); ihr Inhalt ist je Zeile das
    // Blatt, aus dem sie stammt.
    Umbenannt = Table.RenameColumns(
        Header, {{"NB Rohdaten", "nb_lb"}, {"Werk - Bezeichnung", "werk_bezeichnung"}},
        MissingField.Error
    ),

    // Kopfzeile des zweiten Blattes und Leerzeilen entfernen.
    Zeilen = Table.SelectRows(
        Umbenannt,
        each [bezeichnung_management] <> null
            and [bezeichnung_management] <> ""
            and [bezeichnung_management] <> "bezeichnung_management"
    ),

    Spalten = Table.SelectColumns(
        Zeilen,
        {"nb_lb", "bezeichnung_management", "bezeichnung_region", "werk_bezeichnung",
         "ity_cluster", "name", "Info", "FY_JahrMonat", "ity_effect"}
    ),

    // FY_JahrMonat bleibt als Text erhalten, damit im Lakehouse nachvollziehbar
    // ist, woraus die Periode abgeleitet wurde. Die Ableitung selbst (letzte
    // zwei Zeichen) passiert in nb_10_silver.
    Typen = Table.TransformColumnTypes(
        Spalten,
        {
            {"nb_lb", type text},
            {"bezeichnung_management", type text},
            {"bezeichnung_region", type text},
            {"werk_bezeichnung", type text},
            {"ity_cluster", type text},
            {"name", type text},
            {"Info", type text},
            {"FY_JahrMonat", type text},
            {"ity_effect", type number}
        }
    ),
    MitPeriodeText = Table.RenameColumns(Typen, {{"FY_JahrMonat", "fy_jahrmonat"}}),

    // Einmal je Lauf auswerten, nicht je Zeile - siehe fn_berlin_now.
    Ladezeit = DateTime.From(fn_berlin_now()),
    Snapshot = DateTime.Date(Ladezeit),

    MitLadezeit = Table.AddColumn(MitPeriodeText, "loaded_at", each Ladezeit, type datetime),
    MitSnapshot = Table.AddColumn(MitLadezeit, "snapshot_date", each Snapshot, type date)
in
    MitSnapshot
