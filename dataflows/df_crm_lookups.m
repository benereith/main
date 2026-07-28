// ===========================================================================
// Dataflow Gen2  ·  df_crm_lookups  ->  bronze_crm_account
//                                       bronze_crm_systemuser
//                                       bronze_crm_territory
//                                       bronze_crm_stagehistory
// ===========================================================================
// Zweck : Die Nachschlagetabellen, die im Altmodell als dim_opp_* aus dem
//         Fakt heraus per "Duplikate entfernen" erzeugt wurden. Das war
//         fachlich falsch - Kunden, die in KEINER offenen Opportunity
//         vorkommen, fehlten in der Dimension, und Attribute wurden aus dem
//         Fakt statt aus der Quelle gelesen.
//
// Dieses Skript enthaelt vier Abfragen. In Dataflow Gen2 werden sie als vier
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
// Abfrage 1: bronze_crm_account
// ---------------------------------------------------------------------------
let
    account = fnDataverse("account"),
    Gewuenscht = {
        "accountid",                 // Primaerschluessel
        "name",                      // Kundenname
        "parentaccountid",           // Konzernstruktur
        "cgplc_sapid",               // SAP-Debitor / Betriebsnummer
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
    MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Date.From(DateTime.FixedLocalNow()), type date)
in
    MitSnapshot


// ---------------------------------------------------------------------------
// Abfrage 2: bronze_crm_systemuser
// ---------------------------------------------------------------------------
// let
//     usr = fnDataverse("systemuser"),
//     Gewuenscht = {
//         "systemuserid", "fullname", "internalemailaddress", "title",
//         "businessunitid", "territoryid", "isdisabled"
//     },
//     Auswahl = List.Intersect({Gewuenscht, Table.ColumnNames(usr)}),
//     Selektiert = Table.SelectColumns(usr, Auswahl),
//     MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Date.From(DateTime.FixedLocalNow()), type date)
// in
//     MitSnapshot


// ---------------------------------------------------------------------------
// Abfrage 3: bronze_crm_territory
// ---------------------------------------------------------------------------
// let
//     terr = fnDataverse("territory"),
//     Gewuenscht = { "territoryid", "name", "parentterritoryid", "managerid" },
//     Auswahl = List.Intersect({Gewuenscht, Table.ColumnNames(terr)}),
//     Selektiert = Table.SelectColumns(terr, Auswahl),
//     MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Date.From(DateTime.FixedLocalNow()), type date)
// in
//     MitSnapshot


// ---------------------------------------------------------------------------
// Abfrage 4: bronze_crm_stagehistory
// ---------------------------------------------------------------------------
// Die Audit-Entitaet liefert die tatsaechliche Stage-Historie einer
// Opportunity. Damit laesst sich beantworten, wie lange eine Opportunity in
// welcher Phase lag und wie sich die Win-% ueber die Zeit entwickelt hat -
// unabhaengig von unseren eigenen Tagessnapshots.
//
// HINWEIS: Die Entitaet "audit" muss im Mandanten fuer opportunity aktiviert
// sein. Ist sie es nicht, liefert diese Abfrage eine leere Tabelle; die
// Bewegungsanalyse faellt dann auf silver_*_history (Tagessnapshots) zurueck.
//
// let
//     audit = fnDataverse("audit"),
//     NurOpportunity = Table.SelectRows(audit, each [objecttypecode] = "opportunity"),
//     Gewuenscht = {
//         "auditid", "objectid", "objecttypecode", "createdon", "userid",
//         "operation", "attributemask", "changedata"
//     },
//     Auswahl = List.Intersect({Gewuenscht, Table.ColumnNames(NurOpportunity)}),
//     Selektiert = Table.SelectColumns(NurOpportunity, Auswahl),
//     MitSnapshot = Table.AddColumn(Selektiert, "snapshot_date", each Date.From(DateTime.FixedLocalNow()), type date)
// in
//     MitSnapshot
