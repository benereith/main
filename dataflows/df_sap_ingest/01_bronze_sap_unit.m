// ===========================================================================
// Dataflow Gen2 "df_sap_ingest"  ·  Abfrage: bronze_sap_unit
// ===========================================================================
// Betriebsstammdaten aus dem bestehenden Gen1-Dataflow "sap_master_data_unit"
// - dieselbe Quelle, die die Altmodelle als dim_sap_master_data_unit genutzt
// haben. Hier wird sie unveraendert uebernommen, nicht neu aufgebaut.
//
// Ziel  : lakehouse_group_controlling / bronze_sap_unit
// Modus : REPLACE (Ziel in den Dataflow-Einstellungen auf "Ersetzen" stellen)
//
// KEINE HISTORISIERUNG. Anders als die CRM-Extrakte laeuft diese Tabelle
// NICHT ueber stg_* und nb_05_snapshot: es gibt keine snapshot_date-Spalte
// und keine Tagespartition. Der Grund ist fachlich - Betriebsstammdaten sind
// ein Ist-Stand, keine Bewegung. Fuer die Frage "was hat sich seit dem letzten
// CRM-Call geaendert" zaehlen Opportunities und Vertraege, nicht die
// Werksliste. Ein Snapshot waere reiner Speicherverbrauch.
//
// Deshalb heisst das Ziel direkt bronze_sap_unit (nicht stg_sap_unit):
// nb_05_snapshot fasst diese Tabelle nicht an, nb_10_silver liest sie direkt.
// ===========================================================================
//
// EINRICHTUNG DER QUELLE
// Die Navigation zu einem Gen1-Dataflow enthaelt Arbeitsbereichs- und
// Dataflow-GUIDs, die je Mandant verschieden sind. Sie lassen sich nicht
// sinnvoll fest eintragen. Vorgehen im Dataflow-Editor:
//   Daten abrufen -> Dataflows -> Arbeitsbereich waehlen ->
//   sap_master_data_unit -> Entitaet waehlen
// Power Query erzeugt dabei genau die beiden ersten Schritte unten. Danach
// den erzeugten Code durch diese Datei ersetzen und nur Quelle/Navigation
// stehen lassen.
// ===========================================================================
let
    // --- Von "Daten abrufen" erzeugte Schritte -----------------------------
    // Beide Zeilen beim Einrichten durch die generierte Navigation ersetzen.
    Quelle = PowerPlatform.Dataflows(null),
    Navigation = Quelle{[Id = "Workspaces"]}[Data],

    // Ab hier unveraendert lassen.
    // Die Stammdaten kommen bereits typisiert aus dem Gen1-Dataflow; ein
    // erneutes Table.TransformColumnTypes wuerde nur Fehlerquellen schaffen.
    Stammdaten = Navigation,

    // Nur die Spalten, die Silver/Gold tatsaechlich brauchen. Fehlende Felder
    // werden uebersprungen statt zu einem Abbruch zu fuehren - dasselbe
    // SafeSelect-Muster wie bei den CRM-Abfragen, damit ein umbenanntes Feld
    // den Lauf nicht kippt.
    GewuenschteSpalten = {
        "betrieb",                            // Werksnummer, Primaerschluessel
        "bezeichnung_betrieb",
        "buchungskreis",
        "sektor",
        "vertragsbeginn",
        "schliessung",
        "bezeichnung_vertragsart",
        "bezeichnung_region",
        "bezeichnung_management",
        "bezeichnung_verantwortungsbereich",  // steuert die HFM-Sektor-Logik
        "bezeichnung_branche",
        "bezeichnung_kundengruppe",
        "bundesland",
        "stadt",
        "cause_of_change",                    // Net-New-Hierarchie
        "bezeichnung_cause_of_change",
        "cause_of_change_fy",
        "cause_of_change_ny"
    },

    VorhandeneSpalten = Table.ColumnNames(Stammdaten),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),

    // Reissleine. SafeSelect ist dafuer gedacht, EINZELNE fehlende Felder zu
    // ueberspringen. Fehlt dagegen der Primaerschluessel "betrieb", zeigt die
    // Navigation nicht auf die Stammdatentabelle - typischerweise, weil die
    // Platzhalterzeilen oben nicht ersetzt wurden und noch die Arbeitsbereichs-
    // liste geliefert wird. Ohne diese Pruefung entstuende eine Tabelle mit
    // nur loaded_at und _fehlende_felder, und der Fehler faende sich erst
    // Schritte spaeter in nb_10_silver wieder.
    Geprueft =
        if not List.Contains(VorhandeneSpalten, "betrieb") then
            error Error.Record(
                "Quelle liefert keine Betriebsstammdaten",
                "Die Spalte 'betrieb' fehlt - die Navigation zeigt nicht auf "
                    & "sap_master_data_unit. Die beiden Platzhalterschritte "
                    & "'Quelle' und 'Navigation' am Anfang dieser Abfrage ueber "
                    & "'Daten abrufen -> Dataflows' neu erzeugen.",
                "Gefundene Spalten: " & Text.Combine(VorhandeneSpalten, ", ")
            )
        else
            Stammdaten,

    Selektiert = Table.SelectColumns(Geprueft, Auswahl),

    // Ladezeitpunkt zur Nachvollziehbarkeit. KEIN snapshot_date - siehe oben.
    MitLadezeit = Table.AddColumn(
        Selektiert, "loaded_at", each DateTime.From(fn_berlin_now()), type datetime
    ),
    MitDiagnose = Table.AddColumn(
        MitLadezeit, "_fehlende_felder", each Text.Combine(Fehlend, ","), type text
    )
in
    MitDiagnose
