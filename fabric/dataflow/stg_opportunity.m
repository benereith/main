// =====================================================================
// Dataflow Gen2 - Query: stg_opportunity
// Der Queryname entspricht der Zieltabelle - die Historisierung
// nach fct_* bzw. map_* uebernimmt 02_load_snapshot.py.
// Quelle : Dataverse / Dynamics CRM, Entity "opportunity"
// Ziel   : Lakehouse-Tabelle stg_opportunity (Destination: REPLACE)
// Lauf   : taeglich
//
// NICHT direkt nach fct_opportunity schreiben. Die Historisierung uebernimmt
// 02_load_snapshot.py, das die Tagespartition vorher loescht und den Lauf
// damit wiederholbar macht. Ein Append aus dem Dataflow wuerde bei jedem
// Retry einen zweiten Snapshot desselben Tages anhaengen und alle Summen
// verdoppeln.
//
// Die Staging-Tabelle muss nicht vorab angelegt werden - das Ziel eines
// Dataflows entsteht beim ersten Lauf. Nur die Zieltabellen der
// Historisierung sind in 01_create_tables.sql explizit typisiert.
//
// Grundsatz: VOLLEXTRAKT.
//   - kein Statusfilter (auch Verloren / Nobid / Turndown / Universe)
//   - kein Datumsfilter (kein Est_Close_Date_A / _E)
//   - keine Monats-Expansion, keine ITY-Berechnung, kein SharePoint-Join
// Alle abgeleiteten Groessen entstehen im Semantic Model (DAX).
// =====================================================================
let
    Quelle =
        CommonDataService.Database(
            "cpgplc.crm.dynamics.com",
            [CreateNavigationProperties = null]
        ),

    Opportunity = Quelle{[Schema = "dbo", Item = "opportunity"]}[Data],

    // --- Nur die fachlich benoetigten Rohspalten -----------------------
    // statecodename / statuscodename bleiben drin: sie sind der Grund,
    // warum wir vollextrahieren (Statuswechsel nachvollziehbar machen).
    Spalten =
        Table.SelectColumns(
            Opportunity,
            {
                // Schluessel & Beziehungen
                "opportunityid",
                "accountid",
                "parentaccountid",
                "ownerid",
                "cgplc_territoryid",
                "cgplc_contractid",

                // Klassifizierung
                "name",
                "statecodename",
                "statuscodename",
                "cgplc_salesstagename",
                "cgplc_contracttypelookup",
                "cgplc_sectorlookup",
                "cgplc_subsector",
                "cgplc_currentsupplier",

                // Datumsfelder
                "estimatedclosedate",
                "cgplc_openingdate",
                "cgplc_wondate",

                // Kennzahlen
                "cgplc_revenuearo",
                "cgplc_revenuearo_base",
                "cgplc_revenueity",
                "cgplc_revenueity_base",
                "cgplc_win",
                "cgplc_bgpercent",

                // CRM-Audit (fuer Change Tracking im Lakehouse)
                "createdon",
                "modifiedon"
            },
            MissingField.UseNull
        ),

    // --- Nur Typisierung, keine Fachlogik ------------------------------
    Typen =
        Table.TransformColumnTypes(
            Spalten,
            {
                {"opportunityid", type text},
                {"accountid", type text},
                {"parentaccountid", type text},
                {"ownerid", type text},
                {"cgplc_territoryid", type text},
                {"cgplc_contractid", type text},
                {"name", type text},
                {"statecodename", type text},
                {"statuscodename", type text},
                {"cgplc_salesstagename", type text},
                {"cgplc_contracttypelookup", type text},
                {"cgplc_sectorlookup", type text},
                {"cgplc_subsector", type text},
                {"cgplc_currentsupplier", type text},
                {"estimatedclosedate", type date},
                {"cgplc_openingdate", type date},
                {"cgplc_wondate", type date},
                {"cgplc_revenuearo", Currency.Type},
                {"cgplc_revenuearo_base", Currency.Type},
                {"cgplc_revenueity", Currency.Type},
                {"cgplc_revenueity_base", Currency.Type},
                {"cgplc_win", type number},
                {"cgplc_bgpercent", type number},
                {"createdon", type datetime},
                {"modifiedon", type datetime}
            }
        ),

    // --- cgplc_win auf Dezimalquote normalisieren ----------------------
    // CRM liefert 0..100, das Modell rechnet mit 0..1.
    // Einzige verbleibende Transformation: rein technisch, nicht fachlich.
    WinQuote =
        Table.TransformColumns(
            Typen,
            {{"cgplc_win", each if _ = null then null else _ / 100, type number}}
        ),

    // --- Snapshot-Stempel fuer die Historisierung ----------------------
    // Einmal je Lauf auswerten, nicht je Zeile: ein Ladelauf, der ueber
    // Mitternacht laeuft, wuerde sonst zwei verschiedene snapshot_date
    // erzeugen und den Grain der Snapshot-Partition zerreissen.
    // Der Versatz wird hier bewusst abgeschnitten: das Lakehouse-Ziel eines
    // Dataflow Gen2 unterstuetzt datetimezone nicht. Uebrig bleibt die
    // Berliner Ortszeit als naiver Zeitstempel - passend zur
    // Session-Zeitzone, die 02_load_snapshot.py auf Europe/Berlin setzt.
    Ladezeit = DateTime.From(fn_berlin_now()),
    Snapshot = DateTime.Date(Ladezeit),

    MitSnapshot =
        Table.AddColumn(WinQuote, "snapshot_date", each Snapshot, type date),

    MitLadezeit =
        Table.AddColumn(MitSnapshot, "loaded_at", each Ladezeit, type datetime)
in
    MitLadezeit
