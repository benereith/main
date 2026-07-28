// =====================================================================
// Dataflow Gen2 - Lookup-Queries
//
// Ziel: je eine Lakehouse-Tabelle stg_lkp_* (Destination: REPLACE)
// Lauf: taeglich, gemeinsam mit stg_opportunity
//
// Diese Queries ersetzen KEINE Dimensionen im Modell. Sie liefern die
// Klartextnamen, die 02_load_snapshot.py in die Faktenzeile schreibt.
//
// Warum die Namen in die Faktentabelle und nicht in Dimensionen:
//
//   1. Historisierung. Eine Dimension traegt immer nur den aktuellen
//      Namen. Wird ein Territory umbenannt oder eine Opportunity einem
//      neuen Owner zugeordnet, zeigte auch der Snapshot von vor drei
//      Monaten den heutigen Stand - der Tagesstand waere nicht mehr das,
//      was er behauptet zu sein.
//   2. Kein CRM-Zugriff aus Power BI Desktop noetig. Der Dataflow ist
//      der einzige Kontaktpunkt, Desktop liest nur den SQL-Endpoint.
//   3. Keine berechneten Tabellen im Modell - Voraussetzung fuer
//      Direct Lake.
//
// Der Join gehoert bewusst NICHT hierher: ein Table.NestedJoin gegen
// mehrere Dataverse-Entitaeten faltet nicht mehr und macht den
// Vollextrakt langsam. Diese Queries ziehen flach, Spark joint.
// =====================================================================


// ---------------------------------------------------------------------
// Dataverse  -  gemeinsame Verbindung, "Laden deaktivieren"
// ---------------------------------------------------------------------
let
    Quelle =
        CommonDataService.Database(
            "cpgplc.crm.dynamics.com",
            [CreateNavigationProperties = false]
        )
in
    Quelle


// ---------------------------------------------------------------------
// fnLookupDimension  -  Funktionsquery, "Laden deaktivieren"
// Unveraendert uebernommen.
// ---------------------------------------------------------------------
(TabellenName as text, IdSpalte as text, NameSpalte as text) as table =>
let
    Tabelle   = Dataverse{[Schema = "dbo", Item = TabellenName]}[Data],
    Spalten   = Table.SelectColumns(Tabelle, {IdSpalte, NameSpalte}),
    Umbenannt = Table.RenameColumns(Spalten, {{IdSpalte, "Id"}, {NameSpalte, "Name"}}),
    Gefiltert = Table.SelectRows(Umbenannt, each [Id] <> null),
    Eindeutig = Table.Distinct(Gefiltert)
in
    Eindeutig


// =====================================================================
// Lookup-Queries. Jede schreibt nach stg_lkp_<name>, Destination Replace.
//
// !! Die vier mit ZU PRUEFEN markierten Entitaets- und Spaltennamen sind
// !! nach Dataverse-Konvention geraten (Custom Entity cgplc_<x> mit
// !! Schluessel cgplc_<x>id und Primaerfeld cgplc_name). Die Beziehungen
// !! im Modell belegen nur, dass es Lookups sind - nicht, wie die
// !! Zielentitaeten heissen. Vor dem ersten Lauf im CRM gegenpruefen.
// =====================================================================


// --- stg_lkp_owner ---------------------------------------------------
let
    Quelle = fnLookupDimension("systemuser", "systemuserid", "fullname")
in
    Quelle


// --- stg_lkp_account -------------------------------------------------
let
    Quelle = fnLookupDimension("account", "accountid", "name")
in
    Quelle


// --- stg_lkp_territory -----------------------------------------------
let
    Quelle = fnLookupDimension("territory", "territoryid", "name")
in
    Quelle


// --- stg_lkp_contract ------------------------------------------------
// Fuer cgplc_contractid - die Bruecke Opportunity -> Retention-Contract.
let
    Quelle = fnLookupDimension("cgplc_cgcontract", "cgplc_cgcontractid", "cgplc_name")
in
    Quelle


// --- stg_lkp_sector --------------------------------------------------
// ZU PRUEFEN: Entitaet und Spaltennamen
let
    Quelle = fnLookupDimension("cgplc_sector", "cgplc_sectorid", "cgplc_name")
in
    Quelle


// --- stg_lkp_subsector -----------------------------------------------
// ZU PRUEFEN: Entitaet und Spaltennamen
let
    Quelle = fnLookupDimension("cgplc_subsector", "cgplc_subsectorid", "cgplc_name")
in
    Quelle


// --- stg_lkp_contracttype --------------------------------------------
// ZU PRUEFEN: Entitaet und Spaltennamen
let
    Quelle = fnLookupDimension("cgplc_contracttype", "cgplc_contracttypeid", "cgplc_name")
in
    Quelle


// --- stg_lkp_currentsupplier -----------------------------------------
// ZU PRUEFEN: Entitaet und Spaltennamen
let
    Quelle = fnLookupDimension("cgplc_currentsupplier", "cgplc_currentsupplierid", "cgplc_name")
in
    Quelle
