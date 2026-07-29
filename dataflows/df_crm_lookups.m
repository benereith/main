// ===========================================================================
// Dataflow Gen2  ·  df_crm_lookups  ->  stg_crm_account
//                                       stg_crm_territory
// ===========================================================================
// Zweck : Die Nachschlagetabellen, die im Altmodell als dim_opp_* aus dem
//         Fakt heraus per "Duplikate entfernen" erzeugt wurden. Das war
//         fachlich falsch - Kunden, die in KEINER offenen Opportunity
//         vorkommen, fehlten in der Dimension, und Attribute wurden aus dem
//         Fakt statt aus der Quelle gelesen.
//
// BEWUSST NICHT EXTRAHIERT:
//   systemuser  Im Mandanten nicht abrufbar. Verzichtbar: der Klarname des
//               Verantwortlichen kommt als owneridname direkt an der
//               Opportunity bzw. am Vertrag mit.
//   audit       Die Audit-Entitaet ist im Mandanten fuer opportunity nicht
//               aktiviert. Die Bewegungsanalyse (gold_fct_crm_movement)
//               arbeitet deshalb ausschliesslich mit den Tagessnapshots aus
//               silver_*_history - das ist der tragende Mechanismus, nicht
//               ein Notbehelf. Sollte Audit spaeter aktiviert werden, laesst
//               sich die feinere Historie ergaenzen, ohne dass sich am
//               Datenmodell etwas aendert.
//
// Dieses Skript enthaelt zwei Abfragen. In Dataflow Gen2 werden sie als zwei
// getrennte Abfragen angelegt; der gemeinsame Quell-Schritt wird als
// Funktion referenziert.
// ===========================================================================

// ---------------------------------------------------------------------------
// Gemeinsame Quelle  (Abfrage: fnDataverse)
// ---------------------------------------------------------------------------
// let
//     fnDataverse = (entitaet as text) as table =>
//         let
//             Quelle = CommonDataService.Database(
//                 "cpgplc.crm.dynamics.com", [CreateNavigationProperties = null]
//             ),
//             Tabelle = Quelle{[Schema = "dbo", Item = entitaet]}[Data]
//         in
//             Tabelle
// in
//     fnDataverse


// ---------------------------------------------------------------------------
// Abfrage 1: stg_crm_account
// ---------------------------------------------------------------------------
let
    account = fnDataverse("account"),
    Gewuenscht = {
        "accountid",                 // Primaerschluessel
        "name",                      // Kundenname
        "parentaccountid",           // Konzernstruktur
        "cgplc_sapid",               // SAP-Debitor (Debitor, KEIN Betrieb -
                                     // deshalb nicht fuer die Werk-Zuordnung
                                     // verwendet, siehe df_map_unit_assignment)
        "cgplc_sectorlookup",        // Sektor
        "cgplc_subsector",           // Subsektor
        "cgplc_territoryid",         // Vertriebsgebiet
        "industrycode",              // Branche
        "customertypecode",          // Kundenart
        "address1_city",             // Ort
        "address1_stateorprovince",  // Bundesland
        "address1_postalcode",       // PLZ
        "statecode",
        "statecodename",
        "createdon",
        "modifiedon"
    },
    Auswahl = List.Intersect({Gewuenscht, Table.ColumnNames(account)}),
    Selektiert = Table.SelectColumns(account, Auswahl),
    // Zeitstempel einmal je Lauf, auf Berliner Zeit - siehe fn_berlin_now.m.
    Snapshot = DateTime.Date(DateTime.From(fn_berlin_now())),
    MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Snapshot, type date)
in
    MitSnapshot


// ---------------------------------------------------------------------------
// Abfrage 2: stg_crm_territory
// ---------------------------------------------------------------------------
// let
//     terr = fnDataverse("territory"),
//     Gewuenscht = { "territoryid", "name", "parentterritoryid", "managerid" },
//     Auswahl = List.Intersect({Gewuenscht, Table.ColumnNames(terr)}),
//     Selektiert = Table.SelectColumns(terr, Auswahl),
//     Snapshot = DateTime.Date(DateTime.From(fn_berlin_now())),
//     MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Snapshot, type date)
// in
//     MitSnapshot
