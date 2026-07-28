// ===========================================================================
// Dataflow Gen2  ·  df_crm_opportunity  ->  bronze_crm_opportunity
// ===========================================================================
// Zweck   : Rohextrakt der Dataverse-Entitaet "opportunity" in die
//           Bronze-Schicht des Lakehouse. KEINE fachliche Logik - alles
//           Rechnen passiert in nb_10_silver / nb_20_gold.
// Ziel    : lakehouse_group_controlling / bronze_crm_opportunity
// Modus   : Append (Snapshot je Lauf ueber snapshot_ts unterscheidbar)
// Zeitplan: taeglich 05:00
//
// UNTERSCHIED ZUM ALTZUSTAND
// Das Altmodell "CRM Call" holte 21 Spalten und filterte direkt in der
// Abfrage. Dadurch waren (a) alle nicht selektierten Felder dauerhaft
// unerreichbar und (b) die gefilterten Zeilen nicht mehr nachvollziehbar.
// Hier wird breit geladen und erst in Silver gefiltert.
//
// FELDSTATUS
//   [B] = bestaetigt, im Altmodell fct_opp bereits verwendet
//   [S] = Dataverse-Standardfeld der Entitaet opportunity
//   [C] = kundenspezifisches Feld (cgplc_-Praefix), Verfuegbarkeit im
//         Mandanten pruefen - siehe docs/04_crm_feldkatalog.md
// Felder, die im Mandanten nicht existieren, werden von SafeSelect
// stillschweigend uebersprungen, damit der Ladelauf nicht bricht.
// ===========================================================================
let
    Quelle = CommonDataService.Database(
        "cpgplc.crm.dynamics.com",
        [CreateNavigationProperties = null]
    ),
    opportunity = Quelle{[Schema = "dbo", Item = "opportunity"]}[Data],

    // -----------------------------------------------------------------------
    // Gewuenschte Felder. Reihenfolge = fachliche Gruppierung.
    // -----------------------------------------------------------------------
    GewuenschteSpalten = {
        // --- Identitaet ----------------------------------------------------
        "opportunityid",                 // [B] Primaerschluessel
        "name",                          // [B] Bezeichnung der Opportunity
        "accountid",                     // [B] Kunde
        "parentaccountid",               // [B] Konzernmutter
        "ownerid",                       // [B] Verantwortlicher (Lookup)
        "owneridname",                   // [S] Klarname des Verantwortlichen
        "opportunityratingcode",         // [S] A/B/C-Einstufung
        "customerid",                    // [S] Kunde (polymorph)

        // --- Termine -------------------------------------------------------
        "createdon",                     // [S] Anlage im CRM - Basis fuer Alterung
        "modifiedon",                    // [S] letzte Aenderung
        "estimatedclosedate",            // [B] erwartetes Entscheidungsdatum
        "actualclosedate",               // [S] tatsaechlicher Abschluss
        "cgplc_openingdate",             // [B] Mobilisierungs-/Eroeffnungsdatum
        "cgplc_wondate",                 // [B] Gewinndatum
        "cgplc_bidduedate",              // [C] Angebotsfrist
        "cgplc_contractstartdate",       // [C] Vertragsbeginn
        "cgplc_contractenddate",         // [C] Vertragsende
        "cgplc_mobilisationdate",        // [C] Mobilisierungsstart

        // --- Werte ---------------------------------------------------------
        "cgplc_revenuearo",              // [B] ARO - MAP131
        "cgplc_revenuearo_base",         // [B] ARO in Konzernwaehrung
        "cgplc_revenueity",              // [B] ITY - MAP141a
        "cgplc_revenueity_base",         // [B] ITY in Konzernwaehrung
        "estimatedvalue",                // [S] geschaetzter Auftragswert
        "estimatedvalue_base",           // [S] dito, Konzernwaehrung
        "budgetamount",                  // [S] Kundenbudget
        "cgplc_bgpercent",               // [B] Bruttomarge in %
        "cgplc_ebitpercent",             // [C] EBIT-Marge in %
        "cgplc_capexvalue",              // [C] Investitionsbedarf
        "cgplc_contractterm",            // [C] Laufzeit in Monaten
        "transactioncurrencyid",         // [S] Belegwaehrung
        "exchangerate",                  // [S] Umrechnungskurs

        // --- Wahrscheinlichkeit und Status ---------------------------------
        "cgplc_win",                     // [B] Win-Wahrscheinlichkeit 0-100
        "closeprobability",              // [S] Standard-Wahrscheinlichkeit
        "cgplc_salesstagename",          // [B] Vertriebsphase (Klartext)
        "salesstage",                    // [S] Vertriebsphase (Optionset)
        "salesstagecode",                // [S] Vertriebsphase (Code)
        "stepname",                      // [S] Prozessschritt
        "statecode",                     // [S] Status (Code)
        "statecodename",                 // [B] Status (Klartext)
        "statuscode",                    // [S] Statusgrund (Code)
        "statuscodename",                // [S] Statusgrund (Klartext)
        "cgplc_reasonforlossname",       // [C] Verlustgrund
        "cgplc_confidencelevel",         // [C] Konfidenzstufe des Vertriebs

        // --- Klassifizierung -----------------------------------------------
        // WICHTIG - Lookup-Namenspaare: Der TDS-Endpunkt liefert fuer jedes
        // Lookup-Feld foo die GUID in foo und den Anzeigenamen in fooname.
        // Beide werden geladen: die GUID als Schluessel, der Name fuer
        // Anzeige, Filter und das Sektor-Mapping (Mapping_Planwerke.xlsx ist
        // ueber Namen geschluesselt, nicht ueber GUIDs).
        "cgplc_contracttypelookup",      // [B] Vertragsart (GUID)
        "cgplc_contracttypelookupname",  // [S] Vertragsart (Anzeigename)
        "cgplc_sectorlookup",            // [B] Sektor (GUID)
        "cgplc_sectorlookupname",        // [S] Sektor (Anzeigename)
        "cgplc_subsector",               // [B] Subsektor (GUID)
        "cgplc_subsectorname",           // [S] Subsektor (Anzeigename)
        "cgplc_currentsupplier",         // [B] aktueller Anbieter (GUID)
        "cgplc_currentsuppliername",     // [S] aktueller Anbieter (Anzeigename)
        "cgplc_territoryid",             // [B] Vertriebsgebiet (GUID)
        "cgplc_territoryidname",         // [S] Vertriebsgebiet (Anzeigename)
        "cgplc_contractid",              // [B] verknuepfter Vertrag (GUID)
        "cgplc_contractidname",          // [S] verknuepfter Vertrag (Anzeigename)
        "accountidname",                 // [S] Kunde (Anzeigename)
        "parentaccountidname",           // [S] Konzernmutter (Anzeigename)
        "transactioncurrencyidname",     // [S] Waehrung (Anzeigename)
        "opportunityratingcodename",     // [S] A/B/C-Einstufung (Klartext)
        "cgplc_sapid",                   // [C] SAP-Betriebsnummer - Stufe 2 der
                                         //     Werk-Aufloesungskette
        "cgplc_businesstype",            // [C] New / Retention / Extension
        "cgplc_businesstypename",        // [C] dito, Klartext
        "cgplc_isretender",              // [C] Kennzeichen Ausschreibung Bestand
        "cgplc_numberofsites",           // [C] Anzahl Standorte
        "cgplc_headcount"                // [C] betroffene Mitarbeiterzahl
    },

    // -----------------------------------------------------------------------
    // SafeSelect: nimmt nur Spalten, die es in der Quelle tatsaechlich gibt.
    // Verhindert, dass ein einzelnes fehlendes cgplc_-Feld den ganzen
    // Ladelauf abbricht - der Feldkatalog kann so schrittweise wachsen.
    // -----------------------------------------------------------------------
    VorhandeneSpalten = Table.ColumnNames(opportunity),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),
    Selektiert = Table.SelectColumns(opportunity, Auswahl),

    // -----------------------------------------------------------------------
    // Nur der Ladezeitpunkt wird ergaenzt. Sonst nichts.
    // -----------------------------------------------------------------------
    MitSnapshot = Table.AddColumn(
        Selektiert, "snapshot_ts", each DateTime.FixedLocalNow(), type datetime
    ),
    MitSnapshotDatum = Table.AddColumn(
        MitSnapshot, "snapshot_date", each Date.From([snapshot_ts]), type date
    ),

    // Diagnose: fehlende Felder als Spalte mitfuehren, damit sie im
    // Monitoring sichtbar sind statt stillschweigend zu verschwinden.
    MitDiagnose = Table.AddColumn(
        MitSnapshotDatum,
        "_fehlende_felder",
        each Text.Combine(Fehlend, ","),
        type text
    )
in
    MitDiagnose
