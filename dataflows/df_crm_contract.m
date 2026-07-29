// ===========================================================================
// Dataflow Gen2  ·  df_crm_contract  ->  stg_crm_contract  ->  bronze_crm_contract
// ===========================================================================
// Zweck   : Rohextrakt der Dataverse-Entitaet "cgplc_cgcontract" (Bestands-
//           vertraege / Retention) in die Bronze-Schicht.
// Ziel    : lakehouse_group_controlling / stg_crm_contract
// Modus   : REPLACE in die Staging-Tabelle (Historisierung: nb_05_snapshot.py)
// Zeitplan: taeglich 05:00
//
// Der Altstand (fct_retention) holte 13 Spalten und filterte sofort auf
// statuscodename = "Aktiv". Damit war nicht mehr feststellbar, welche
// Vertraege ZWISCHEN zwei Laeufen inaktiv wurden - genau die Information,
// die fuer die Bewegungsanalyse gebraucht wird. Hier wird ungefiltert
// geladen; der Aktiv-Filter sitzt in nb_10_silver.
//
// Feldstatus wie in df_crm_opportunity.m: [B] bestaetigt, [C] kundenspezifisch.
// ===========================================================================
let
    Quelle = CommonDataService.Database(
        "cpgplc.crm.dynamics.com",
        [CreateNavigationProperties = null]
    ),
    vertrag = Quelle{[Schema = "dbo", Item = "cgplc_cgcontract"]}[Data],

    GewuenschteSpalten = {
        // --- Identitaet ----------------------------------------------------
        "cgplc_cgcontractid",            // [B] Primaerschluessel
        "cgplc_name",                    // [B] Vertragsbezeichnung
        "cgplc_sapid",                   // [B] SAP-Betriebsnummer (Join-Schluessel)
        "cgplc_accountid",               // [C] Kunde
        "cgplc_parentaccountid",         // [C] Konzernmutter
        "ownerid",                       // [S] Verantwortlicher
        "owneridname",                   // [S] Klarname
        "createdon",                     // [S] Anlage
        "modifiedon",                    // [S] letzte Aenderung

        // --- Status --------------------------------------------------------
        "statecode",                     // [S] Status (Code)
        "statecodename",                 // [S] Status (Klartext)
        "statuscode",                    // [S] Statusgrund (Code)
        "statuscodename",                // [B] Statusgrund (Klartext) - "Aktiv"

        // --- Termine -------------------------------------------------------
        "cgplc_contractstartdate",       // [C] Vertragsbeginn
        "cgplc_contractenddate",         // [B] Vertragsende
        "cgplc_decisiondate",            // [B] Entscheidungsdatum - MASSGEBLICH
                                         //     fuer CY/PY-Zuordnung laut Guidance S. 2
        "cgplc_forecastdecisiondate",    // [B] erwartetes Entscheidungsdatum
        "cgplc_operationstartdate",      // [B] Betriebsbeginn
        "cgplc_operationenddate",        // [C] Betriebsende / Demobilisierung
        "cgplc_noticeperiod",            // [C] Kuendigungsfrist in Monaten
        "cgplc_retenderdate",            // [C] naechste Ausschreibung

        // --- Werte ---------------------------------------------------------
        "cgplc_revenuearo",              // [B] aktueller ARO
        "cgplc_currentrevenuearo",       // [S] laufender Umsatz
        "cgplc_lastfyrevenuearo",        // [B] Vorjahres-ARO - Basis MAP136
        "cgplc_budgetrevenuearo",        // [C] Budget-ARO
        "cgplc_bgpercent",               // [C] Bruttomarge
        "transactioncurrencyid",         // [S] Waehrung
        "exchangerate",                  // [S] Kurs

        // --- Risiko --------------------------------------------------------
        "cgplc_retentionprobability",    // [B] Haltewahrscheinlichkeit 0-100
        "cgplc_reasonforriskname",       // [B] Risikogrund (Klartext)
        "cgplc_reasonforrisk",           // [C] Risikogrund (Optionset)
        "cgplc_riskcategory",            // [C] Risikokategorie
        "cgplc_competitorid",            // [C] konkurrierender Anbieter
        "cgplc_retentionactionplan",     // [C] Massnahmenplan

        // --- Klassifizierung -----------------------------------------------
        // Lookup-Namenspaare wie in df_crm_opportunity.m: GUID als Schluessel,
        // ...name-Spalte fuer Anzeige, Filter und das Sektor-Mapping.
        "cgplc_sectorlookup",            // [C] Sektor (GUID)
        "cgplc_sectorlookupname",        // [C] Sektor (Anzeigename)
        "cgplc_subsector",               // [C] Subsektor (GUID)
        "cgplc_subsectorname",           // [C] Subsektor (Anzeigename)
        "cgplc_contracttypelookup",      // [C] Vertragsart (GUID)
        "cgplc_contracttypelookupname",  // [C] Vertragsart (Anzeigename)
        "cgplc_territoryid",             // [C] Vertriebsgebiet (GUID)
        "cgplc_territoryidname",         // [C] Vertriebsgebiet (Anzeigename)
        "cgplc_accountidname",           // [C] Kunde (Anzeigename)
        "cgplc_parentaccountidname",     // [C] Konzernmutter (Anzeigename)
        "cgplc_competitoridname",        // [C] konkurrierender Anbieter (Anzeigename)
        "cgplc_riskcategoryname",        // [C] Risikokategorie (Klartext)
        "cgplc_numberofsites",           // [C] Anzahl Standorte
        "cgplc_headcount"                // [C] Mitarbeiterzahl
    },

    VorhandeneSpalten = Table.ColumnNames(vertrag),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),
    Selektiert = Table.SelectColumns(vertrag, Auswahl),

    // Einmal je LAUF auswerten, nicht je Zeile: ein Ladelauf ueber Mitternacht
    // erzeugte sonst zwei verschiedene snapshot_date in einer Staging-Tabelle
    // und liesse den Grain-Check im Notebook hart auf Fehler laufen.
    // Der Zonenversatz wird abgeschnitten - das Lakehouse-Ziel eines
    // Dataflow Gen2 unterstuetzt datetimezone nicht.
    Ladezeit = DateTime.From(fn_berlin_now()),
    Snapshot = DateTime.Date(Ladezeit),

    MitSnapshot = Table.AddColumn(
        Selektiert, "loaded_at", each Ladezeit, type datetime
    ),
    MitSnapshotDatum = Table.AddColumn(
        MitSnapshot, "snapshot_date", each Snapshot, type date
    ),
    MitDiagnose = Table.AddColumn(
        MitSnapshotDatum, "_fehlende_felder", each Text.Combine(Fehlend, ","), type text
    )
in
    MitDiagnose
