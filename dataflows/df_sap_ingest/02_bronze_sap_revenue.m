// ===========================================================================
// Dataflow Gen2 "df_sap_ingest"  ·  Abfrage: bronze_sap_revenue
// ===========================================================================
// Ist-, Budget- und Forecast-Umsaetze aus V_SAP_EXPORTS_cleansed im
// SAP-Warehouse "Reporting".
//
// Ziel  : lakehouse_group_controlling / bronze_sap_revenue
// Modus : REPLACE (Ziel in den Dataflow-Einstellungen auf "Ersetzen" stellen)
//
// KEINE HISTORISIERUNG: die View ist bereits der gepflegte Ist-/Planstand je
// Periode. Ein Tagessnapshot darueber wuerde dieselben Buchungen taeglich
// vervielfachen. nb_05_snapshot fasst diese Tabelle deshalb nicht an.
// ===========================================================================
//
// ZWEI KATEGORIEN JE WERK UND PERIODE
// Die Abfrage liefert dieselbe Kennzahl zweimal, unterschieden durch die
// Spalte "kategorie":
//   Revenue  nur Ertragskonten (Level_2_Key = Total Revenue)
//   UP       ohne Kontenabgrenzung, also der gesamte Buchungsstoff
//
// ACHTUNG - das verdoppelt die Zeilen je Werk/Periode/Version. JEDE Kennzahl,
// die auf 'FCT Umsatz'[Monatswert] summiert, MUSS deshalb auf eine Kategorie
// filtern; sonst zaehlt sie Revenue und UP zusammen. Alle bestehenden
// Kennzahlen tun das (Kategorie = "Revenue"), damit sich ihre Werte durch
// diese Erweiterung nicht aendern.
//
// WARUM Value.NativeQuery UND NICHT SCHRITTE IM EDITOR
// Die Aggregation (GROUP BY) laeuft damit garantiert im SQL-Warehouse, nicht
// in der Mashup-Engine. Das hat drei Wirkungen:
//   1. Es kommt bereits verdichtet an - eine Zeile je Werk, Version,
//      Geschaeftsjahr, Periode und Kategorie statt einer je Buchungskonto.
//   2. Der Grain ist damit an der Quelle eindeutig. Dubletten, gegen die die
//      Kennzahlen sonst mit SUMMARIZE/AVERAGE absichern muessen, entstehen
//      hier gar nicht erst.
//   3. HAVING SUM(Value) <> 0 wirft Nullzeilen weg, bevor sie uebertragen
//      werden.
// Ueber den Editor zusammengeklickt wuerde derselbe Ablauf das Falten
// verlieren, sobald ein Schritt nicht uebersetzbar ist - und dann liefe die
// Aggregation nach dem vollstaendigen Download lokal.
//
// SPALTENNAMEN: bewusst wie in der Quelle (Fiscal_Year, Period, Object_group,
// SAP_Version, Value). Die Umbenennung auf die Modellnamen passiert an genau
// einer Stelle, in nb_20_gold. Werttyp und Periodendatum werden dort ebenfalls
// abgeleitet und deshalb hier nicht mitgeliefert - zwei Definitionen
// derselben Groesse laufen sonst auseinander.
// ===========================================================================
let
    // Servername des SAP-Warehouse
    SapServer = "3w3wftkijo6ujehh4fb2eleovu-tuq7lxe5lznu7hpei5nzy67o3e.datawarehouse.fabric.microsoft.com",

    Quelle = Sql.Database(SapServer, "Reporting"),

    // Untergrenze der geladenen Geschaeftsjahre. Das Vorjahr wird gebraucht,
    // weil [Net New ITY] den Vorjahresanteil abzieht und die Metrik-Zuordnung
    // PY-Groessen kennt - ohne FY-1 im Extrakt blieben beide leer.
    // Nach oben bewusst offen: die Planjahressicht (metric_id_ny) rechnet
    // gegen das Folgejahr, und Plandaten reichen weiter als das laufende Jahr.
    AktuellesGJ = 2025,   // Mit CURRENT_FY in nb_00_config gleichhalten.
    AbGeschaeftsjahr = Number.ToText(AktuellesGJ - 1),

    SQL =
        "WITH AggregatedData AS (
            -- Revenue: nur Ertragskonten
            SELECT
                'Revenue' AS kategorie,
                base.Object_group,
                base.SAP_Version,
                base.Fiscal_Year,
                base.Period,
                SUM(base.Value) AS Value
            FROM V_SAP_EXPORTS_cleansed AS base
            LEFT JOIN tab_accounts_hierarchy AS hier
                ON base.Account = hier.Kostenart
            WHERE base.Object_type = 'OR'
              AND hier.Level_2_Key = 'IS10000_T - Total Revenue inkl. IFRS/ NEUTRA/MGMT'
              AND base.Fiscal_Year >= " & AbGeschaeftsjahr & "
            GROUP BY base.Object_group, base.SAP_Version, base.Fiscal_Year, base.Period
            HAVING SUM(base.Value) <> 0

            UNION ALL

            -- UP: ohne Kontenabgrenzung
            SELECT
                'UP' AS kategorie,
                base.Object_group,
                base.SAP_Version,
                base.Fiscal_Year,
                base.Period,
                SUM(base.Value) AS Value
            FROM V_SAP_EXPORTS_cleansed AS base
            WHERE base.Object_type = 'OR'
              AND base.Fiscal_Year >= " & AbGeschaeftsjahr & "
            GROUP BY base.Object_group, base.SAP_Version, base.Fiscal_Year, base.Period
            HAVING SUM(base.Value) <> 0
        )
        SELECT kategorie, Object_group, SAP_Version, Fiscal_Year, Period, Value
        FROM AggregatedData",

    Ergebnis = Value.NativeQuery(Quelle, SQL),

    Typen = Table.TransformColumnTypes(
        Ergebnis,
        {
            {"kategorie", type text},
            {"Object_group", Int64.Type},
            {"SAP_Version", type text},
            {"Fiscal_Year", Int64.Type},
            {"Period", Int64.Type}
        }
    ),

    // Werke, die sich nicht als Zahl lesen lassen, sind keine Betriebe und
    // finden im Modell ohnehin keinen Anschluss.
    OhneFehler = Table.RemoveRowsWithErrors(Typen, {"Object_group"}),

    MitLadezeit = Table.AddColumn(
        OhneFehler, "loaded_at", each DateTime.From(fn_berlin_now()), type datetime
    ),
    MitDiagnose = Table.AddColumn(
        MitLadezeit, "_fehlende_felder", each "", type text
    )
in
    MitDiagnose
