// =====================================================================
// Dataflow Gen2 - Query: fct_retention
// Quelle : Dataverse / Dynamics CRM, Entity "cgplc_cgcontract"
// Ziel   : Lakehouse-Tabelle stg_retention (Destination: REPLACE)
// Lauf   : taeglich
//
// NICHT direkt nach fct_retention schreiben. Die Historisierung uebernimmt
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
//   - kein Statusfilter (statuscodename <> "Aktiv" wird NICHT gefiltert)
//   - kein Datumsfilter auf cgplc_contractenddate
//   - keine Monats-Expansion, keine Retention-Gewichtung
// Alle abgeleiteten Groessen entstehen im Semantic Model (DAX).
// =====================================================================
let
    Quelle =
        CommonDataService.Database(
            "cpgplc.crm.dynamics.com",
            [CreateNavigationProperties = null]
        ),

    Contract = Quelle{[Schema = "dbo", Item = "cgplc_cgcontract"]}[Data],

    // --- Nur die fachlich benoetigten Rohspalten -----------------------
    Spalten =
        Table.SelectColumns(
            Contract,
            {
                // Schluessel & Beziehungen
                "cgplc_cgcontractid",
                "cgplc_sapid",

                // Klassifizierung
                "cgplc_name",
                "statuscodename",
                "statecodename",
                "cgplc_reasonforriskname",

                // Datumsfelder
                "cgplc_contractenddate",
                "cgplc_decisiondate",
                "cgplc_forecastdecisiondate",
                "cgplc_operationstartdate",

                // Kennzahlen
                "cgplc_revenuearo",
                "cgplc_currentrevenuearo",
                "cgplc_lastfyrevenuearo",
                "cgplc_retentionprobability",

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
                {"cgplc_cgcontractid", type text},
                {"cgplc_sapid", Int64.Type},
                {"cgplc_name", type text},
                {"statuscodename", type text},
                {"statecodename", type text},
                {"cgplc_reasonforriskname", type text},
                {"cgplc_contractenddate", type date},
                {"cgplc_decisiondate", type date},
                {"cgplc_forecastdecisiondate", type date},
                {"cgplc_operationstartdate", type datetime},
                {"cgplc_revenuearo", Currency.Type},
                {"cgplc_currentrevenuearo", Currency.Type},
                {"cgplc_lastfyrevenuearo", Currency.Type},
                {"cgplc_retentionprobability", type number},
                {"createdon", type datetime},
                {"modifiedon", type datetime}
            }
        ),

    // --- Fehlerhafte Datumswerte neutralisieren statt Zeilen zu loeschen
    // Das alte Modell warf Zeilen per Table.RemoveRowsWithErrors weg.
    // Im Vollextrakt wollen wir die Zeile behalten und nur das Feld leeren.
    DatumBereinigt =
        Table.ReplaceErrorValues(
            Typen,
            {
                {"cgplc_contractenddate", null},
                {"cgplc_decisiondate", null},
                {"cgplc_forecastdecisiondate", null},
                {"cgplc_operationstartdate", null}
            }
        ),

    // --- retentionprobability auf Dezimalquote normalisieren -----------
    // CRM liefert 0..100, das Modell rechnet mit 0..1.
    RetQuote =
        Table.TransformColumns(
            DatumBereinigt,
            {{"cgplc_retentionprobability", each if _ = null then null else _ / 100, type number}}
        ),

    // --- Snapshot-Stempel fuer die Historisierung ----------------------
    // Einmal je Lauf auswerten, nicht je Zeile: ein Ladelauf, der ueber
    // Mitternacht laeuft, wuerde sonst zwei verschiedene snapshot_date
    // erzeugen und den Grain der Snapshot-Partition zerreissen.
    Ladezeit = fn_berlin_now(),
    Snapshot = DateTime.Date(DateTime.From(Ladezeit)),

    MitSnapshot =
        Table.AddColumn(RetQuote, "snapshot_date", each Snapshot, type date),

    MitLadezeit =
        Table.AddColumn(MitSnapshot, "loaded_at", each Ladezeit, type datetimezone)
in
    MitLadezeit
