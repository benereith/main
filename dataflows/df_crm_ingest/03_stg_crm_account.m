// ===========================================================================
// Dataflow Gen2 "df_crm_ingest"  ·  Abfrage: stg_crm_account
// ===========================================================================
// Ersetzt die dim_opp_account/dim_opp_parent-Tabellen des Altmodells, die
// per "Duplikate entfernen" aus dem Fakt erzeugt wurden - fachlich falsch,
// weil Konten ohne offene Opportunity dabei fehlten und Attribute aus dem
// Fakt statt aus der Quelle gelesen wurden.
// Ziel    : lakehouse_group_controlling / stg_crm_account
// Modus   : REPLACE in die Staging-Tabelle (Historisierung: nb_05_snapshot.py)
// Zeitplan: taeglich 05:00
// Benoetigt die Funktionsquery fn_berlin_now (00_fn_berlin_now.m) im selben
// Dataflow.
// ===========================================================================
let
    Quelle = CommonDataService.Database(
        "cpgplc.crm.dynamics.com",
        [CreateNavigationProperties = null]
    ),
    account = Quelle{[Schema = "dbo", Item = "account"]}[Data],

    GewuenschteSpalten = {
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

    VorhandeneSpalten = Table.ColumnNames(account),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),
    Selektiert = Table.SelectColumns(account, Auswahl),

    // Einmal je LAUF auswerten, nicht je Zeile - siehe fn_berlin_now.
    Ladezeit = DateTime.From(fn_berlin_now()),
    Snapshot = DateTime.Date(Ladezeit),

    MitSnapshot = Table.AddColumn(Selektiert, "loaded_at", each Ladezeit, type datetime),
    MitSnapshotDatum = Table.AddColumn(MitSnapshot, "snapshot_date", each Snapshot, type date),
    MitDiagnose = Table.AddColumn(
        MitSnapshotDatum, "_fehlende_felder", each Text.Combine(Fehlend, ","), type text
    )
in
    MitDiagnose
