// ===========================================================================
// Dataflow Gen2 "df_crm_ingest"  ·  Abfrage: stg_crm_territory
// ===========================================================================
// Vertriebsgebiete inkl. Hierarchie. Ersetzt dim_opp_territory des
// Altmodells (per "Duplikate entfernen" aus dem Fakt erzeugt).
// Ziel    : lakehouse_group_controlling / stg_crm_territory
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
    territory = Quelle{[Schema = "dbo", Item = "territory"]}[Data],

    GewuenschteSpalten = {
        "territoryid",       // Primaerschluessel
        "name",              // Bezeichnung
        "parentterritoryid", // Uebergeordnetes Gebiet
        "managerid"          // Verantwortlicher
    },

    VorhandeneSpalten = Table.ColumnNames(territory),
    Auswahl = List.Intersect({GewuenschteSpalten, VorhandeneSpalten}),
    Fehlend = List.Difference(GewuenschteSpalten, VorhandeneSpalten),
    Selektiert = Table.SelectColumns(territory, Auswahl),

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
