# Fabric notebook source
# ---------------------------------------------------------------------------
# nb_20_gold
# ---------------------------------------------------------------------------
# Silver -> Gold: Star Schema fuer das Semantikmodell.
#
# HERZSTUECK dieses Notebooks ist der Perioden-Fanout in Abschnitt 3. Er
# ersetzt die List.Generate-/ExpandListColumn-Konstruktion aus fct_opp und
# fct_retention. Der Unterschied ist nicht kosmetisch:
#
#   Power Query : erzeugt je Zeile eine Liste im Mashup-Engine-Speicher,
#                 seriell, nicht faltbar, bei jedem Modell-Refresh erneut.
#   Spark       : erzeugt ein Kreuzprodukt gegen eine Monatssequenz,
#                 partitioniert und parallel, einmal taeglich.
#
# Ausgang:
#   gold_dim_date, gold_dim_unit, gold_dim_opportunity, gold_dim_contract,
#   gold_dim_status, gold_dim_hfm_struktur, gold_dim_snapshot,
#   gold_fct_net_new_ity, gold_fct_crm_movement
# ---------------------------------------------------------------------------

# COMMAND ----------

# MAGIC %run nb_00_config

# COMMAND ----------

# --- Konfigurationsstand pruefen -------------------------------------------
# Fabric haelt eine eigene Kopie jedes Notebooks. Wird nb_00_config im Repo
# geaendert, aber in Fabric nicht neu importiert, laeuft %run stillschweigend
# gegen die ALTE Fassung - der Abbruch kommt dann erst spaeter als NameError
# auf eine Funktion, die es dort noch nicht gibt. Diese Pruefung zieht den
# Fehler an den Anfang und sagt, was zu tun ist.
BENOETIGTE_CONFIG_VERSION = 3
if globals().get("CONFIG_VERSION", 1) < BENOETIGTE_CONFIG_VERSION:
    raise ValueError(
        f"nb_00_config ist veraltet (v{globals().get('CONFIG_VERSION', 1)}, "
        f"benoetigt v{BENOETIGTE_CONFIG_VERSION}).\n"
        "In Fabric liegt noch eine aeltere Kopie. nb_00_config aus "
        "lakehouse/notebooks/nb_00_config.py neu importieren bzw. den "
        "Inhalt dort ersetzen, dann dieses Notebook erneut starten."
    )


from pyspark.sql import functions as F
from pyspark.sql import Window
from datetime import date

RUN_TS = spark.sql("SELECT current_timestamp() AS ts").collect()[0]["ts"]
RUN_DATE = RUN_TS.date()


# ===========================================================================
# 1. gold_dim_date - Fiskalkalender
# ===========================================================================
# Ersetzt drei identische M-Kalender. Bereich bewusst grosszuegig, damit
# Vorjahresvergleiche und Fanout-Horizont abgedeckt sind.
CAL_FROM = date(2020, 1, 1)
CAL_TO = date(2030, 12, 31)

dim_date = (
    spark.sql(
        f"SELECT explode(sequence(to_date('{CAL_FROM}'), to_date('{CAL_TO}'), interval 1 day)) AS datum"
    )
    .withColumn("jahr", F.year("datum"))
    .withColumn("monat_nr", F.month("datum"))
    .withColumn("monat", F.date_format("datum", "MMMM"))
    .withColumn("tag", F.dayofmonth("datum"))
    .withColumn("quartal", F.concat(F.lit("Q"), F.quarter("datum")))
    .withColumn("monat_erster", F.trunc("datum", "MM"))
)
dim_date = add_fiscal_columns(dim_date, "datum")
dim_date = (
    dim_date.withColumn("fy_quartal_nr", F.ceil(F.col("fy_period") / 3).cast("int"))
    .withColumn("fy_quartal", F.concat(F.lit("FQ"), F.col("fy_quartal_nr")))
    .withColumn("fy_periode", F.concat(F.lit("P"), F.lpad(F.col("fy_period").cast("string"), 2, "0")))
    .withColumn(
        "fy_jahr_monat",
        F.concat(F.col("fy_year").cast("string"), F.lit("-"),
                 F.lpad(F.col("fy_period").cast("string"), 2, "0")),
    )
    # Sortierschluessel: FY-Jahr und -Periode in einer Zahl, damit die
    # Monatsachse im Bericht ohne Zusatzspalte korrekt sortiert.
    .withColumn("fy_sort", F.col("fy_year") * 100 + F.col("fy_period"))
    # Kurzlabel fuer Achsen: "Okt 25"
    .withColumn(
        "fy_periode_label",
        F.concat(F.date_format("datum", "MMM"), F.lit(" "), F.date_format("datum", "yy")),
    )
    .withColumn("ist_vergangenheit", F.col("datum") < F.lit(RUN_DATE))
    # --- Relative Geschaeftsjahre ------------------------------------------
    # fy_offset ist die Grundlage fuer die Standardauswahl im Bericht.
    # Ein fester Filter auf "FY2026/27" muesste jeden Oktober von Hand
    # umgestellt werden - genau die Handarbeit, die dieser Bericht abloesen
    # soll. Ein Filter auf fy_offset = 1 wandert dagegen mit CURRENT_FY mit.
    .withColumn("fy_offset", (F.col("fy_year") - F.lit(CURRENT_FY)).cast("int"))
    .withColumn(
        "fy_relativ",
        F.when(F.col("fy_offset") == -1, F.lit("Vorjahr"))
        .when(F.col("fy_offset") == 0, F.lit("Laufendes Jahr"))
        # Das Budgetjahr ist der Zeitraum, auf den sich die Planung richtet:
        # was jetzt gewonnen wird, zahlt dort ein.
        .when(F.col("fy_offset") == 1, F.lit("Budgetjahr"))
        .when(F.col("fy_offset") == 2, F.lit("Folgejahr +2"))
        .otherwise(F.concat(F.lit("Offset "), F.col("fy_offset").cast("string"))),
    )
)
write_delta(dim_date, "gold_dim_date")


# ===========================================================================
# 2. gold_dim_status - Statusbuckets mit fester Sortierung und Farbrolle
# ===========================================================================
# Warum eine eigene Dimension: In den Altmodellen wurden Buckets als Strings
# durch die Measures gefiltert ([Sales_Status]="Won YTD" usw.). Damit war
# weder die Sortierung noch die Farbzuordnung stabil. Hier ist beides an
# Daten gebunden - die Farbrolle wird im Theme des Berichts aufgeloest.
status_rows = [
    # code,            label,             gruppe,  sortierung, sicherheit, farbrolle
    ("WON",            "Won",             "NEW",   10, "gesichert",   "nb-won"),
    ("EXPECTED_WIN",   "Expected Win",    "NEW",   20, "erwartet",    "nb-expected"),
    ("PIPELINE",       "Pipeline",        "NEW",   30, "unsicher",    "nb-pipeline"),
    ("NO_PROBABILITY", "Ohne Win-%",      "NEW",   40, "unbekannt",   "neutral"),
    ("LOST",           "Lost",            "LOST",  50, "gesichert",   "lb-lost"),
    ("EXPECTED_LOSS",  "Expected Loss",   "LOST",  60, "erwartet",    "lb-expected"),
    ("AT_RISK",        "At Risk",         "LOST",  70, "unsicher",    "lb-atrisk"),
    ("NO_RISK",        "No Risk",         "LOST",  80, "gesichert",   "neutral"),
]
dim_status = spark.createDataFrame(
    status_rows,
    "status_code string, status_label string, business_type string, status_sort int, "
    "sicherheitsgrad string, farbrolle string",
).withColumn("status_key", F.col("status_sort"))
write_delta(dim_status, "gold_dim_status")


# ===========================================================================
# 3. gold_dim_hfm_struktur - Net-New-Hierarchie + HFM-Kontenzuordnung
# ===========================================================================
# 1:1 uebernommen aus DIM_Struktur der Altmodelle, ergaenzt um die
# ARO-/ITY-Konten aus der Group Guidance (Feb 2025, S. 3).
hfm_rows = [
    # metric_id, metric, parent_id, sort, lvl1_label, lvl2_label, lvl3_label, lvl4_label, is_leaf, hfm_account, hfm_beschreibung
    (1, "PY revenue from contracts won PY", 3, 11, "Net New Business", "New Business", "New Business Roll", "PY revenue from contracts won PY", True, "MAP111a", "Trading revenue reported in prior year for contracts won in prior years"),
    (2, "CY revenue from contracts won PY", 3, 12, "Net New Business", "New Business", "New Business Roll", "CY revenue from contracts won PY", True, "MAP111b", "Trading revenue reported in current year for contracts won in prior years"),
    (3, "New Business Roll", 5, 13, "Net New Business", "New Business", "New Business Roll", "New Business Roll", False, None, None),
    (4, "New Business ITY", 5, 14, "Net New Business", "New Business", "New Business ITY", "New Business ITY", True, "MAP111c", "Trading revenue reported in current year for contracts won in current year"),
    (5, "New Business", 11, 15, "Net New Business", "New Business", None, None, False, "MAP111d", "New Business (Reported) - berechnet aus MAP111a/b/c"),
    (6, "Lost Business Roll", 10, 21, "Net New Business", "Lost Business", "Lost Business Roll", "Lost Business Roll", True, "MAP112a", "Trading PY minus CY for contracts lost in prior years"),
    (7, "PY revenue from contracts lost CY", 9, 22, "Net New Business", "Lost Business", "Lost Business ITY", "PY revenue from contracts lost CY", True, "MAP112b", "Trading reported in prior year for contracts lost in current year"),
    (8, "CY revenue from contracts lost CY", 9, 23, "Net New Business", "Lost Business", "Lost Business ITY", "CY revenue from contracts lost CY", True, "MAP112c", "Trading reported in current year for contracts lost in current year"),
    (9, "Lost Business ITY", 10, 24, "Net New Business", "Lost Business", "Lost Business ITY", "Lost Business ITY", False, None, None),
    (10, "Lost Business", 11, 25, "Net New Business", "Lost Business", None, None, False, "MAP112d", "Lost Business (Reported) - berechnet aus MAP112a/b/c"),
    (11, "Net New Business", None, 50, "Net New Business", None, None, None, False, None, "New minus Lost"),
    (99, "Like for Like", None, 99, "Like for Like", None, None, None, True, None, "Nicht als New/Lost klassifizierbar"),
    # Forward-Indikatoren (ARO/ITY) - im Altmodell nicht als Dimension gepflegt
    (131, "New Business Revenue (ARO)", None, 60, "Forward Indicator", "New Business", None, None, True, "MAP131", "ARO der ersten 12 Monate von Vertraegen, die im laufenden Jahr gewonnen wurden"),
    (141, "New Business Revenue (ITY)", None, 61, "Forward Indicator", "New Business", None, None, True, "MAP141a", "In-the-year-Wirkung von MAP131, typisch < 12 Monate"),
    (136, "Lost Business Revenue (ARO)", None, 70, "Forward Indicator", "Lost Business", None, None, True, "MAP136", "ARO der letzten 12 Monate von Vertraegen, die im laufenden Jahr gekuendigt wurden"),
    (143, "Lost Business Revenue (ITY)", None, 71, "Forward Indicator", "Lost Business", None, None, True, "MAP141c", "In-the-year-Wirkung von MAP136, typisch < 12 Monate"),
]
dim_hfm = spark.createDataFrame(
    hfm_rows,
    "metric_id int, metric string, parent_id int, sort int, level1_label string, "
    "level2_label string, level3_label string, level4_label string, is_leaf boolean, "
    "hfm_account string, hfm_beschreibung string",
)
write_delta(dim_hfm, "gold_dim_hfm_struktur")


# ===========================================================================
# 4. gold_dim_unit / gold_dim_opportunity / gold_dim_contract
# ===========================================================================
# Wie in nb_30_quality: die rohe TABLE_OR_VIEW_NOT_FOUND nennt nur den
# Tabellennamen, nicht das Notebook, das sie haette schreiben sollen.
VORAUSSETZUNGEN = {
    "bronze_sap_unit": "Dataflow df_sap_ingest, Abfrage bronze_sap_unit",
    "silver_opportunity": "nb_10_silver (Abschnitt 1)",
    "silver_contract": "nb_10_silver (Abschnitt 2)",
}
_fehlend = [t for t in VORAUSSETZUNGEN if not spark.catalog.tableExists(t)]
if _fehlend:
    raise ValueError(
        "Vorgaengertabelle(n) fehlen: " + ", ".join(sorted(_fehlend)) + ".\n"
        + "\n".join(f"  {t} <- {VORAUSSETZUNGEN[t]}" for t in sorted(_fehlend))
        + "\nDen jeweils genannten Schritt zuerst fehlerfrei durchlaufen lassen."
    )

# Die Betriebsstammdaten kommen UNVERAENDERT aus Bronze. Es gibt keine
# Silver-Stufe mehr fuer diese Tabelle: sie hat nichts bereinigt oder
# gefiltert, sondern nur die vier unten stehenden Spalten ergaenzt - und dabei
# ueber eine Auswahlliste jede neue Quellspalte stillschweigend liegen lassen.
#
# ALLE Spalten der Quelle bleiben erhalten. Was hier passiert, ist
# ausschliesslich ADDITIV: vier abgeleitete Spalten und der Unit-Status. Keine
# Spalte wird weggelassen, umbenannt oder umgerechnet.
unit = spark.table("bronze_sap_unit")

# Tabelle da, aber ohne Fachspalten: das passiert, wenn die Quellnavigation in
# df_sap_ingest nicht auf sap_master_data_unit zeigt. Uebrig bleiben dann nur
# loaded_at und _fehlende_felder. Ohne diese Pruefung waere die Rohmeldung ein
# UNRESOLVED_COLUMN auf 'betrieb' und zeigte auf dieses Notebook statt auf den
# Dataflow. (Stand frueher in nb_10_silver, Abschnitt 3.)
UNIT_PFLICHT = ["betrieb", "bezeichnung_betrieb", "sektor"]
_fehlt = [s for s in UNIT_PFLICHT if s not in unit.columns]
if _fehlt:
    raise ValueError(
        "bronze_sap_unit enthaelt keine Betriebsstammdaten.\n"
        f"Fehlende Pflichtspalten: {', '.join(_fehlt)}\n"
        f"Vorhandene Spalten: {', '.join(unit.columns)}\n"
        "Ursache liegt im Dataflow df_sap_ingest, Abfrage bronze_sap_unit: die "
        "Navigationsschritte am Anfang der Abfrage muessen auf "
        "sap_master_data_unit zeigen."
    )

# Optionale Stammdatenfelder ergaenzen, damit ein einzelnes fehlendes Attribut
# den Lauf nicht kippt. Die Liste beschraenkt NICHT die Auswahl - alle
# uebrigen Quellspalten laufen ohnehin unveraendert mit.
unit = ergaenze_spalten(
    unit,
    {
        "buchungskreis": "string", "vertragsbeginn": "date", "schliessung": "date",
        "bezeichnung_vertragsart": "string", "bezeichnung_region": "string",
        "bezeichnung_management": "string", "bezeichnung_verantwortungsbereich": "string",
        "bezeichnung_branche": "string", "bezeichnung_kundengruppe": "string",
        "bundesland": "string", "stadt": "string",
        "cause_of_change": "int", "bezeichnung_cause_of_change": "string",
        "cause_of_change_fy": "int", "cause_of_change_ny": "int",
    },
    "bronze_sap_unit",
)

# Diese vier Spalten entstehen erst hier, weil sie Wissen brauchen, das nicht
# in den SAP-Stammdaten steht: die Planbetriebslisten aus nb_00_config und die
# HFM-Sektor-Harmonisierung.
#
# betriebstyp ist dabei die wichtigste: die Kennzahlen [Roll Budget],
# [ITY Budget], [Unknown ITY Budget] und [Budget Net New (SAP)] grenzen
# darueber ab. Faellt sie weg, liefern alle vier stillschweigend leere Werte.
dim_unit_sap = (
    unit.withColumn(
        "werk_bezeichnung",
        F.concat(
            F.lpad(F.col("betrieb").cast("string"), 4, "0"),
            F.lit(" - "),
            F.col("bezeichnung_betrieb"),
        ),
    )
    .withColumn(
        "betriebstyp",
        F.when(F.col("betrieb").isin(PLANBETRIEBE_ROLL), F.lit("Plan-Betriebe Roll"))
        .when(F.col("betrieb").isin(PLANBETRIEBE_ITY), F.lit("Plan-Betriebe ITY"))
        .otherwise(F.lit("Real-Betriebe")),
    )
    .withColumn(
        "known_unknown",
        F.when(F.col("betriebstyp") == "Real-Betriebe", F.lit("known")).otherwise(
            F.lit("unknown")
        ),
    )
    # HFM-Sektor-Harmonisierung (aus dim_sap_master_data_unit uebernommen)
    .withColumn(
        "hfm_sektor",
        F.when(
            F.col("bezeichnung_verantwortungsbereich") == "Food Services",
            F.when(F.col("sektor").isin("SE", "RE", "ED"), F.lit("HC"))
            .when(F.col("sektor").isin("OV", "RT"), F.lit("BU"))
            .otherwise(F.col("sektor")),
        )
        .when(
            F.col("bezeichnung_verantwortungsbereich") == "Support Service",
            F.when(F.col("sektor") == "OV", F.lit("BU")).otherwise(F.col("sektor")),
        )
        .otherwise(F.col("sektor")),
    )
    .dropDuplicates(["betrieb"])
    .withColumn("unit_status", F.lit("In Betrieb"))
)

# Spaltensatz der Dimension - ergibt sich jetzt aus der Quelle statt aus einer
# gepflegten Liste. Wird nur noch gebraucht, um die geplanten Units unten
# typgerecht aufzufuellen.
DIM_UNIT_SPALTEN = dim_unit_sap.columns

# --- Geplante Units aus dem Mapping ergaenzen ------------------------------
# Eine Dimension allein aus den SAP-Stammdaten laesst genau die Units in die
# Blank-Zeile fallen, um die es im Net New Business geht: Betriebe, die noch
# nicht gewonnen sind und deshalb in SAP nicht existieren. Sie stehen
# ausschliesslich im gepflegten Mapping.
#
# unit_status unterscheidet beide Herkuenfte, damit im Bericht sichtbar
# bleibt, welcher Anteil des Effekts auf geplanten Units liegt.
if spark.catalog.tableExists("bronze_map_unit_assignment"):
    mapping_alle = spark.table("bronze_map_unit_assignment")
    letzter_stand = mapping_alle.agg(F.max("snapshot_date")).collect()[0][0]
    geplante = (
        mapping_alle.filter(F.col("snapshot_date") == F.lit(letzter_stand))
        .select(F.col("sap_unit").alias("betrieb"))
        .distinct()
        .join(dim_unit_sap.select("betrieb"), "betrieb", "left_anti")
        .withColumn(
            "werk_bezeichnung",
            F.concat(F.lpad(F.col("betrieb").cast("string"), 4, "0"),
                     F.lit(" - Geplante Unit")),
        )
        .withColumn("unit_status", F.lit("Geplant"))
        .withColumn("betriebstyp", F.lit("Plan-Betriebe ITY"))
        .withColumn("known_unknown", F.lit("unknown"))
    )
    # Fehlende Attributspalten typgerecht ergaenzen, damit unionByName greift.
    schema = {f.name: f.dataType for f in dim_unit_sap.schema.fields}
    for spalte in DIM_UNIT_SPALTEN:
        if spalte not in geplante.columns:
            geplante = geplante.withColumn(spalte, F.lit(None).cast(schema[spalte]))
    dim_unit = dim_unit_sap.unionByName(geplante.select(dim_unit_sap.columns))
    print(f"  gold_dim_unit: {geplante.count():,} geplante Units ergaenzt")
else:
    dim_unit = dim_unit_sap

write_delta(dim_unit, "gold_dim_unit")

opp = spark.table("silver_opportunity")
write_delta(
    opp.select(
        F.col("opportunityid"),
        F.col("name").alias("opportunity_name"),
        "account_name", "owner_name", "territory_name",
        F.col("cgplc_salesstagename").alias("sales_stage"),
        # Lookups als ANZEIGENAME, nicht als GUID: der TDS-Endpunkt liefert
        # in cgplc_sectorlookup nur die GUID; der lesbare Wert steht in der
        # ...name-Begleitspalte. name_oder_id() nimmt den Namen und faellt auf
        # die ID zurueck, falls die Namensspalte im Mandanten fehlt.
        name_oder_id(opp, "cgplc_contracttypelookup").alias("contract_type"),
        name_oder_id(opp, "cgplc_sectorlookup").alias("sector"),
        name_oder_id(opp, "cgplc_subsector").alias("subsector"),
        name_oder_id(opp, "cgplc_currentsupplier").alias("current_supplier"),
        F.col("cgplc_contractid").alias("contract_id"),
        "ity_cluster", "status_code",
        F.col("estimatedclosedate").alias("est_close_date"),
        F.col("cgplc_openingdate").alias("opening_date"),
        F.col("cgplc_wondate").alias("won_date"),
        "win_probability", "revenue_aro", "revenue_ity", "bg_percent",
        "calc_ity_months",
    ).dropDuplicates(["opportunityid"]),
    "gold_dim_opportunity",
)

con = spark.table("silver_contract")
write_delta(
    con.select(
        F.col("cgplc_cgcontractid").alias("contract_key"),
        F.col("cgplc_name").alias("contract_name"),
        F.col("cgplc_sapid").alias("sap_id"),
        F.col("cgplc_reasonforriskname").alias("risk_reason"),
        F.col("cgplc_decisiondate").alias("decision_date"),
        F.col("cgplc_forecastdecisiondate").alias("forecast_decision_date"),
        F.col("cgplc_operationstartdate").alias("operation_start_date"),
        # Sektor und Subsektor MUESSEN hier stehen, damit die Lost-Seite nach
        # denselben Merkmalen auswertbar ist wie die New-Seite. Fehlen sie,
        # wirkt ein Sektorfilter nur auf die Haelfte der Net-New-Rechnung -
        # und zwar ohne Fehlerbild, nur mit falscher Zahl.
        name_oder_id(con, "cgplc_sectorlookup").alias("sector"),
        name_oder_id(con, "cgplc_subsector").alias("subsector"),
        name_oder_id(con, "cgplc_contracttypelookup").alias("contract_type"),
        spalte_oder_null(con, "owneridname").alias("owner_name"),
        "adj_end_date", "ity_cluster", "status_code", "ly_aro_status",
        "retention_probability", "revenue_aro", "last_fy_revenue_aro",
        "calc_ity_months",
    ).dropDuplicates(["contract_key"]),
    "gold_dim_contract",
)


# ===========================================================================
# 5. gold_fct_net_new_ity - der Perioden-Fanout
# ===========================================================================
# Grain: eine Zeile je (Entitaet, Monat).
#
# Vorzeichenkonvention - HIER wird der Wildwuchs der Altmodelle aufgeloest:
#   amount_signed   NEW  = positiv,  LOST = negativ
#                   => Net New ITY  = SUM(amount_signed), ohne *-1 in Measures
#   amount_abs      immer positiver Betrag (fuer Groessenvergleiche)
# In den Altmodellen wurde teils in M (*-1 in fct_opp/fct_retention), teils in
# DAX (Retention_ITY = SUM(...)*-1) gedreht - mit dem Ergebnis, dass dasselbe
# Vorzeichen je nach Measure unterschiedlich war.

# Monatssequenz einmal materialisieren; gegen sie wird gejoint.
months = spark.sql(
    f"SELECT explode(sequence(to_date('{CY_START}'), to_date('{FANOUT_END}'), interval 1 month)) AS period_date"
)

# --- Konforme Attribute ----------------------------------------------------
# Diese fuenf Merkmale werden fuer BEIDE Geschaeftsarten befuellt und liegen
# deshalb auf dem Fakt, nicht nur in den Dimensionen.
#
# Grund: 'DIM Opportunity' und 'DIM Vertrag' sind getrennte Dimensionen. Ein
# Datenschnitt auf 'DIM Opportunity'[Sektor] filtert nur die New-Zeilen; die
# Lost-Zeilen laufen unverandert durch, weil sie an dieser Dimension gar nicht
# haengen. Das Ergebnis waere ein "Net New ITY im Sektor Healthcare", das das
# gesamte Lost Business aller Sektoren enthaelt - falsch, ohne Fehlermeldung.
#
# Mit den Attributen auf dem Fakt wirkt ein Datenschnitt auf beide Haelften.
# Die Dimensionen behalten dieselben Felder fuer die Detailsichten.
KONFORME_ATTRIBUTE = ["sector", "subsector", "contract_type", "account_name", "owner_name"]

# --- 5a. New Business ------------------------------------------------------
# Monatsraten:
#   ity_rate = weighted_ity / calc_ity_months   (Wirkung im ERSTEN GJ)
#   aro_rate = weighted_aro / 12                (Dauerzustand ab 2. GJ)
# Ab dem Monat nach calc_first_fy_end greift die ARO-Rate, davor die ITY-Rate.
silver_opp = spark.table("silver_opportunity")
opp_base = silver_opp.select(
    F.col("opportunityid").alias("entity_id"),
    F.col("name").alias("entity_name"),
    F.lit("OPPORTUNITY").alias("entity_type"),
    F.lit("NEW").alias("business_type"),
    "status_code", "ity_cluster",
    F.col("win_probability").alias("probability"),
    "revenue_aro", "revenue_ity", "weighted_aro", "weighted_ity",
    F.col("calc_start_date").alias("event_month"),
    "calc_first_fy_end", "calc_ity_months",
    F.col("cgplc_openingdate").alias("driver_date"),
    F.col("estimatedclosedate").alias("decision_date"),
    # Anzeigenamen statt GUIDs - Voraussetzung dafuer, dass das
    # Sektor-Mapping (Abschnitt 5d) greift: Mapping_Planwerke.xlsx ist ueber
    # Namen geschluesselt.
    name_oder_id(silver_opp, "cgplc_sectorlookup").alias("sector"),
    name_oder_id(silver_opp, "cgplc_subsector").alias("subsector"),
    name_oder_id(silver_opp, "cgplc_contracttypelookup").alias("contract_type"),
    "account_name", "owner_name",
    # Betriebsnummer, sofern direkt am Vorgang gepflegt. Das ist nur Stufe 2
    # der Aufloesungskette - die eigentliche Zuordnung passiert in Abschnitt
    # 5d ueber die Mapping-Tabelle (Sektor/Subsektor -> Planbetrieb).
    # Die SAP-Nummer des Kontos wird bewusst NICHT als Ersatz verwendet:
    # sie ist ein Debitor, kein Betrieb.
    spalte_oder_null(silver_opp, "cgplc_sapid", "int").alias("sap_id_crm"),
)

# ITY-Ersatzregel bei Eroeffnung im Folgejahr
# ---------------------------------------------------------------------------
# cgplc_revenueity ist im CRM gegen das LAUFENDE Geschaeftsjahr gerechnet.
# Liegt die Mobilisierung komplett im naechsten GJ, steht dort deshalb
# systematisch 0 - nicht weil kein Umsatz entsteht, sondern weil er im
# laufenden Jahr nicht anfaellt.
#
# Ohne Gegenmassnahme faellt genau das erste Vertragsjahr auf 0: der Fanout
# stuft alle Perioden bis calc_first_fy_end als value_layer = "ITY" ein und
# multipliziert sie mit einer ITY-Rate von 0. Erst ab dem zweiten Jahr greift
# aro_rate. Ein "unknown Roll", der im November des Folgejahres eroeffnet,
# erzeugt so elf Monate ohne Umsatz.
#
# Ersatzwert ist ARO/12, nicht ARO/calc_ity_months: ARO ist definitionsgemaess
# der Umsatz der ersten zwoelf Vertragsmonate, die Monatsrate also unabhaengig
# davon, wie viele Monate ins erste GJ fallen.
#
# Die Bedingung ist bewusst eng: nur wenn die Eroeffnung NACH dem Ende des
# laufenden GJ liegt UND CRM keinen ITY-Wert fuehrt. Eine Opportunity, die
# spaet im laufenden Jahr eroeffnet, hat einen kleinen, aber echten ITY-Wert -
# der darf nicht ueberschrieben werden.
ITY_LEER_WEIL_FOLGEJAHR = (F.col("event_month") > F.lit(CY_END)) & (
    F.coalesce(F.col("revenue_ity"), F.lit(0.0)) == 0
)

fct_new = (
    opp_base.join(months, F.col("period_date") >= F.col("event_month"))
    .filter(F.col("period_date") <= F.lit(FANOUT_END))
    # aro_rate MUSS vor ity_rate stehen - ity_rate greift im Ersatzfall darauf zu.
    .withColumn(
        "aro_rate",
        F.when(F.col("weighted_aro").isNotNull(), F.col("weighted_aro") / F.lit(12.0)).otherwise(
            F.lit(0.0)
        ),
    )
    .withColumn(
        "ity_rate",
        F.when(ITY_LEER_WEIL_FOLGEJAHR, F.col("aro_rate"))
        .when(
            (F.col("calc_ity_months") > 0) & F.col("weighted_ity").isNotNull(),
            F.col("weighted_ity") / F.col("calc_ity_months"),
        )
        .otherwise(F.lit(0.0)),
    )
    # Herkunft der ITY-Rate mitfuehren, damit im Bericht und in DQ-NEW-001
    # nachvollziehbar bleibt, welches Volumen ueber die Ersatzregel laeuft.
    .withColumn(
        "ity_quelle",
        F.when(ITY_LEER_WEIL_FOLGEJAHR, F.lit("ARO-Ersatz (Eroeffnung Folgejahr)")).otherwise(
            F.lit("CRM-ITY")
        ),
    )
    # value_layer trennt ITY-Phase (erstes GJ) vom Dauerzustand (ARO).
    .withColumn(
        "value_layer",
        F.when(F.col("period_date") <= F.col("calc_first_fy_end"), F.lit("ITY")).otherwise(
            F.lit("ARO")
        ),
    )
    .withColumn(
        "amount_weighted",
        F.when(F.col("value_layer") == "ITY", F.col("ity_rate")).otherwise(F.col("aro_rate")),
    )
    .withColumn(
        "amount_unweighted",
        F.when(
            F.col("value_layer") == "ITY",
            # Gleiche Ersatzregel ungewichtet, sonst laufen gewichtete und
            # ungewichtete Sicht auseinander.
            F.when(
                ITY_LEER_WEIL_FOLGEJAHR,
                F.coalesce(F.col("revenue_aro"), F.lit(0.0)) / F.lit(12.0),
            )
            .when(
                F.col("calc_ity_months") > 0,
                F.coalesce(F.col("revenue_ity"), F.lit(0.0)) / F.col("calc_ity_months"),
            )
            .otherwise(F.lit(0.0)),
        ).otherwise(F.coalesce(F.col("revenue_aro"), F.lit(0.0)) / F.lit(12.0)),
    )
    .withColumn(
        "hfm_account",
        F.when(F.col("value_layer") == "ITY", F.lit("MAP141a")).otherwise(F.lit("MAP131")),
    )
)

# --- 5b. Lost Business -----------------------------------------------------
# Monatsrate = weighted_ly_aro / 12. Maximal 12 Perioden ab calc_end_date -
# danach ist der Vertrag vollstaendig aus der Basis heraus und wird zu
# "Like for Like" (Guidance S. 5: keine Doppelzaehlung ueber 12 Monate hinaus).
silver_con = spark.table("silver_contract")

# Kundenname des Vertrags, sofern die Verknuepfung zum Konto gepflegt ist.
# Der Vertrag traegt den Kunden nur als Fremdschluessel; ohne diesen Join
# bliebe 'Kunde' auf der Lost-Seite leer, waehrend er auf der New-Seite
# gefuellt ist - genau die Halb-Befuellung, die zu falschen Filtern fuehrt.
if "cgplc_accountid" in silver_con.columns:
    silver_con = silver_con.join(
        ergaenze_spalten(
            nur_letzter_snapshot(
                spark.table("bronze_crm_account"), "bronze_crm_account"
            ),
            {"accountid": "string", "name": "string"},
            "bronze_crm_account",
        )
        .select(
            F.col("accountid").alias("cgplc_accountid"),
            F.col("name").alias("account_name"),
        )
        .dropDuplicates(["cgplc_accountid"]),
        "cgplc_accountid",
        "left",
    )

con_base = silver_con.select(
    F.col("cgplc_cgcontractid").alias("entity_id"),
    F.col("cgplc_name").alias("entity_name"),
    F.lit("CONTRACT").alias("entity_type"),
    F.lit("LOST").alias("business_type"),
    "status_code", "ity_cluster",
    (F.lit(1.0) - F.col("retention_probability")).alias("probability"),
    F.col("revenue_aro"),
    F.col("last_fy_revenue_aro").alias("revenue_ity"),
    F.col("last_fy_revenue_aro").alias("weighted_aro_src"),
    "weighted_ly_aro",
    F.col("calc_end_date").alias("event_month"),
    "calc_first_fy_end", "calc_ity_months",
    F.col("adj_end_date").alias("driver_date"),
    F.col("cgplc_decisiondate").alias("decision_date"),
    F.col("cgplc_sapid").alias("sap_id_crm"),
    # Dieselben konformen Attribute wie auf der New-Seite.
    name_oder_id(silver_con, "cgplc_sectorlookup").alias("sector"),
    name_oder_id(silver_con, "cgplc_subsector").alias("subsector"),
    name_oder_id(silver_con, "cgplc_contracttypelookup").alias("contract_type"),
    # Kundenname: bevorzugt aus dem Konto-Join, ersatzweise der Anzeigename
    # des Lookups direkt am Vertrag.
    F.coalesce(
        spalte_oder_null(silver_con, "account_name"),
        spalte_oder_null(silver_con, "cgplc_accountidname"),
    ).alias("account_name"),
    spalte_oder_null(silver_con, "owneridname").alias("owner_name"),
)

fct_lost = (
    con_base.join(months, F.col("period_date") >= F.col("event_month"))
    .filter(F.col("period_date") <= F.lit(FANOUT_END))
    .withColumn(
        "period_index",
        months_between_inclusive(F.col("event_month"), F.col("period_date")),
    )
    .filter(F.col("period_index") <= 12)   # Deckel: 12 Perioden
    .withColumn("aro_rate", F.coalesce(F.col("weighted_ly_aro"), F.lit(0.0)) / F.lit(12.0))
    .withColumn(
        "value_layer",
        F.when(F.col("period_date") <= F.col("calc_first_fy_end"), F.lit("ITY")).otherwise(
            F.lit("ARO")
        ),
    )
    .withColumn("amount_weighted", F.col("aro_rate"))
    .withColumn(
        "amount_unweighted",
        F.coalesce(F.col("weighted_aro_src"), F.lit(0.0)) / F.lit(12.0),
    )
    .withColumn(
        "hfm_account",
        F.when(F.col("value_layer") == "ITY", F.lit("MAP141c")).otherwise(F.lit("MAP136")),
    )
    # Lost Business kennt die ITY-Ersatzregel nicht: der Verlustwert stammt aus
    # dem Vorjahres-ARO und ist unabhaengig davon, in welchem GJ der Vertrag
    # endet. Die Spalte wird trotzdem gefuehrt, damit beide Haelften denselben
    # Spaltensatz haben (Voraussetzung fuer unionByName).
    .withColumn("ity_quelle", F.lit("CRM-ARO (Vorjahr)"))
)

COMMON = [
    "entity_id", "entity_name", "entity_type", "business_type", "status_code",
    "ity_cluster", "probability", "period_date", "value_layer", "hfm_account",
    "amount_weighted", "amount_unweighted", "event_month", "driver_date",
    "decision_date", "calc_first_fy_end", "calc_ity_months", "ity_quelle",
]

# Beide Seiten liefern jetzt denselben Spaltensatz. Es gibt keine Spalte mehr,
# die nur fuer eine Geschaeftsart gefuellt ist - halb befuellte Attribute sind
# schlimmer als fehlende, weil sie zum Filtern einladen und dabei still die
# jeweils andere Haelfte durchlassen.
FAKT_SPALTEN = COMMON + ["period_index", "sap_id_crm"] + KONFORME_ATTRIBUTE

fct_new_sel = fct_new.withColumn(
    "period_index", months_between_inclusive(F.col("event_month"), F.col("period_date"))
).select(*FAKT_SPALTEN)

fct_lost_sel = fct_lost.select(*FAKT_SPALTEN)

fct = fct_new_sel.unionByName(fct_lost_sel)

# --- 5d. Werk-Zuordnung ueber die Mapping-Tabelle --------------------------
# Die fachliche Information, WOHIN ein Vorgang gehoert, haengt am Sektor und
# Subsektor und wird vom Controlling in Mapping_Planwerke.xlsx gepflegt
# (-> bronze_map_unit_assignment, siehe dataflows/df_map_unit_assignment.m).
#
# Aufloesungskette, erster Treffer gewinnt:
#   1. AUSNAHME     Mapping-Zeile mit opportunityid (Einzelfall schlaegt alles)
#   2. MAPPING S+S  Mapping-Zeile mit passendem Sektor UND Subsektor
#   3. MAPPING S    Mapping-Zeile mit passendem Sektor, subsektor leer
#   4. CRM-BRUECKE  cgplc_sapid am Vorgang selbst
#   5. NULL         -> Regel DQ-MAP-001
#
# WARUM DIE CRM-BRUECKE GANZ HINTEN STEHT
# Sie greift nur fuer Opportunities, die einen BESTEHENDEN Vertrag betreffen
# (Neuausschreibung eines laufenden Objekts). Fuer echte Net-New-Units laeuft
# sie definitionsgemaess leer - dort gibt es weder Vertrag im CRM noch Betrieb
# in SAP. Das gepflegte Mapping traegt die vorausschauende Annahme und ist
# damit die fachlich massgebliche Quelle; die CRM-Bruecke schliesst nur
# Restluecken. Stuende sie vor dem Mapping, wuerde ein veralteter
# cgplc_sapid-Eintrag eine bewusst gepflegte Zuordnung ueberstimmen.
#
# Das Mapping ist HISTORISIERT (snapshot_date). Verwendet wird der jeweils
# juengste Stand - eine abgeschlossene Budgetrunde bleibt ueber den Snapshot
# trotzdem reproduzierbar.
#
# Die Herkunft wird als werk_zuordnung mitgefuehrt: im Bericht ist je Vorgang
# sichtbar, welche Stufe gegriffen hat, und die Nachpflege laesst sich
# priorisieren.
if spark.catalog.tableExists("bronze_map_unit_assignment"):
    mapping_alle = spark.table("bronze_map_unit_assignment")
    letzter_stand = mapping_alle.agg(F.max("snapshot_date")).collect()[0][0]
    mapping = mapping_alle.filter(F.col("snapshot_date") == F.lit(letzter_stand))
    print(f"  Mapping-Stand: {letzter_stand}")

    map_ausnahme = (
        mapping.filter(F.col("opportunityid").isNotNull())
        .select(
            F.col("opportunityid").alias("entity_id"),
            F.col("sap_unit").alias("werk_ausnahme"),
        )
        .dropDuplicates(["entity_id"])
    )
    map_subsektor = (
        mapping.filter(F.col("opportunityid").isNull() & F.col("subsektor").isNotNull())
        .select(
            F.col("sektor").alias("m2_sektor"),
            F.col("subsektor").alias("m2_subsektor"),
            F.col("sap_unit").alias("werk_subsektor"),
        )
        .dropDuplicates(["m2_sektor", "m2_subsektor"])
    )
    map_sektor = (
        mapping.filter(F.col("opportunityid").isNull() & F.col("subsektor").isNull())
        .select(
            F.col("sektor").alias("m3_sektor"),
            F.col("sap_unit").alias("werk_sektor"),
        )
        .dropDuplicates(["m3_sektor"])
    )

    fct = (
        fct.join(map_ausnahme, "entity_id", "left")
        .join(
            map_subsektor,
            (F.col("sector") == F.col("m2_sektor"))
            & (F.col("subsector") == F.col("m2_subsektor")),
            "left",
        )
        .join(map_sektor, F.col("sector") == F.col("m3_sektor"), "left")
    )
else:
    # Mapping-Tabelle (noch) nicht geladen: Kette degradiert auf die
    # CRM-Bruecke. Kein Abbruch - die Luecken zaehlt DQ-MAP-001.
    print("  ! bronze_map_unit_assignment fehlt - Werk-Zuordnung nur aus cgplc_sapid")
    fct = (
        fct.withColumn("werk_ausnahme", F.lit(None).cast("int"))
        .withColumn("werk_subsektor", F.lit(None).cast("int"))
        .withColumn("werk_sektor", F.lit(None).cast("int"))
    )

fct = (
    fct.withColumn(
        "sap_id",
        F.coalesce(
            F.col("werk_ausnahme"),
            F.col("werk_subsektor"),
            F.col("werk_sektor"),
            F.col("sap_id_crm").cast("int"),
        ),
    )
    .withColumn(
        "werk_zuordnung",
        F.when(F.col("werk_ausnahme").isNotNull(), F.lit("Mapping Einzelfall"))
        .when(F.col("werk_subsektor").isNotNull(), F.lit("Mapping Sektor/Subsektor"))
        .when(F.col("werk_sektor").isNotNull(), F.lit("Mapping Sektor"))
        .when(F.col("sap_id_crm").isNotNull(), F.lit("CRM-Bruecke"))
        .otherwise(F.lit("Nicht zugeordnet")),
    )
    .drop("werk_ausnahme", "werk_subsektor", "werk_sektor",
          "m2_sektor", "m2_subsektor", "m3_sektor", "sap_id_crm")
)

fct = add_fiscal_columns(fct, "period_date")
fct = (
    fct.withColumn("fy_sort", F.col("fy_year") * 100 + F.col("fy_period"))
    # Vorzeichen: NEW positiv, LOST negativ -> Net New = einfache Summe
    .withColumn(
        "amount_signed",
        F.when(F.col("business_type") == "LOST", -F.col("amount_weighted")).otherwise(
            F.col("amount_weighted")
        ).cast("decimal(19,4)"),
    )
    # Gleiche Vorzeichenregel fuer den ungewichteten Wert. Existiert als
    # eigene Spalte, damit die Bewertungsbasis "Vollwert" im Bericht eine
    # einfache Summe bleibt und keine Zeilen-Iteration ueber den Fakt braucht.
    .withColumn(
        "amount_unweighted_signed",
        F.when(F.col("business_type") == "LOST", -F.col("amount_unweighted")).otherwise(
            F.col("amount_unweighted")
        ).cast("decimal(19,4)"),
    )
    .withColumn("amount_abs", F.abs(F.col("amount_weighted")).cast("decimal(19,4)"))
    .withColumn("amount_weighted", F.col("amount_weighted").cast("decimal(19,4)"))
    .withColumn("amount_unweighted", F.col("amount_unweighted").cast("decimal(19,4)"))
    .withColumn("snapshot_date", F.lit(RUN_DATE))
    .withColumn("loaded_at", F.lit(RUN_TS))
)

write_delta(fct, "gold_fct_net_new_ity", partition_by=["fy_year"])


# ===========================================================================
# 5c. gold_fct_revenue - SAP-Umsaetze (Ist / Budget / Forecast)
# ===========================================================================
# Uebernimmt die YTD-Fensterfunktion aus dem Altmodell (die war bereits
# richtig platziert: im SQL, nicht in Power Query) und ergaenzt sie um das
# CoC-Mapping auf die Net-New-Hierarchie.
#
# fn_map_coch ersetzt drei identische M-Funktionen aus den Altmodellen.
#
# CAUSE OF CHANGE (SAP-Stammdaten) - Bedeutung der Codes:
#   1 = im VORJAHR gewonnen   -> Roll ins Bezugsjahr
#   2 = im Bezugsjahr gewonnen -> New Business ITY
#   3 = im VORJAHR verloren   -> Lost Business Roll
#   4 = im Bezugsjahr verloren -> Lost Business ITY
#   5 = M&A                   -> keine Net-New-Groesse
#
# Zielmetriken laut DIM_Struktur:
#   1 = PY revenue from contracts won PY      (MAP111a)
#   2 = CY revenue from contracts won PY      (MAP111b)
#   4 = New Business ITY                      (MAP111c)
#   6 = Lost Business Roll                    (MAP112a)
#   7 = PY revenue from contracts lost CY     (MAP112b)
#   8 = CY revenue from contracts lost CY     (MAP112c)
#  99 = Like for Like  (auch der Auffangwert fuer alles Uebrige)
def fn_map_coch(fy_col, coch_col, bezugsjahr):
    """Cause-of-Change -> MetricId der Net-New-Hierarchie.

    BEZUGSJAHR IST EIN PARAMETER, KEINE KONSTANTE
    "CY" und "PY" in den Metriknamen sind relativ: ob eine Umsatzzeile als
    "current year" oder "prior year" zaehlt, haengt davon ab, aus welchem Jahr
    heraus man schaut. Genau dieser Bezug unterscheidet die drei Varianten
    cause_of_change / _fy / _ny voneinander.

    Frueher standen hier fest PRIOR_FY und CURRENT_FY. Damit traf fuer jede
    Zeile eines anderen Geschaeftsjahres KEINE der Jahresbedingungen, und alles
    fiel auf 99 durch - fuer das Budgetjahr blieben nur die beiden
    jahresunabhaengigen Faelle uebrig (coch 3 -> 6 und der Auffangwert 99).
    Das gesamte Planjahr war damit unzugeordnet, ohne dass es einen Fehler
    gab: 99 = "Like for Like" ist ein gueltiger Wert.

    coch == 3 bleibt bewusst jahresunabhaengig: Metrik 6 (Lost Business Roll,
    MAP112a) ist selbst schon eine Roll-Groesse und kennt keine CY/PY-Teilung.
    """
    vorjahr = bezugsjahr - 1
    return (
        F.when(coch_col == 3, F.lit(6))
        .when((fy_col == vorjahr) & (coch_col == 1), F.lit(1))
        .when((fy_col == bezugsjahr) & (coch_col == 1), F.lit(2))
        .when((fy_col == bezugsjahr) & (coch_col == 2), F.lit(4))
        .when((fy_col == vorjahr) & (coch_col == 4), F.lit(7))
        .when((fy_col == bezugsjahr) & (coch_col == 4), F.lit(8))
        .otherwise(F.lit(99))
    )


# bronze_sap_revenue kommt aus dem Dataflow df_sap_ingest (Abfrage
# bronze_sap_revenue, liest V_SAP_EXPORTS_cleansed) und wird dort mit
# ERSETZEN geschrieben - ohne Historisierung, weil die View bereits der
# gepflegte Ist-/Planstand je Periode ist.
#
# Fehlt die Tabelle, wird nur dieser Abschnitt uebersprungen: die bereits
# geschriebene gold_fct_net_new_ity bleibt gueltig, und die nachfolgenden
# CRM-Tabellen (gold_fct_crm_movement, gold_dim_snapshot) entstehen
# weiterhin. Ein Abbruch an dieser Stelle wuerde sie ohne fachlichen Grund
# mitreissen - der Net-New-Teil haengt nicht an den SAP-Umsaetzen.
if not spark.catalog.tableExists("bronze_sap_revenue"):
    print(
        "  WARNUNG: bronze_sap_revenue fehlt - gold_fct_revenue wird NICHT "
        "geschrieben. Budget-, Forecast- und Ist-Kennzahlen bleiben im "
        "Bericht leer; Net New ITY ist davon nicht betroffen. "
        "Dataflow df_sap_ingest aktualisieren (docs/06_deployment.md, Schritt 1)."
    )
else:
    rev = spark.table("bronze_sap_revenue")

    # Monatswert und YTD je Werk/Version/Geschaeftsjahr UND KATEGORIE.
    # Die Kategorie gehoert zwingend in die Partition: bronze_sap_revenue
    # liefert Revenue und UP als zwei Zeilenmengen auf derselben Granularitaet.
    # Ohne sie liefe der kumulierte Wert quer ueber beide und waere fuer keine
    # der beiden richtig.
    w_ytd = (
        Window.partitionBy("kategorie", "werk", "version", "fy_year")
        .orderBy("fy_period")
        .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    )

    rev = (
        rev.withColumn("fy_year", F.col("Fiscal_Year").cast("int"))
        .withColumn("fy_period", F.col("Period").cast("int"))
        .withColumn("werk", F.col("Object_group").cast("int"))
        .withColumn("version", F.col("SAP_Version").cast("string"))
        .withColumn(
            "werttyp", F.when(F.col("version") == "0", F.lit("Actual")).otherwise(F.lit("Plan"))
        )
        .withColumn("werttyp_version", F.concat_ws("_", F.col("werttyp"), F.col("version")))
        .withColumn("betrag_monat", F.col("Value").cast("decimal(19,4)"))
        # Periodendatum aus FY-Jahr und FY-Periode: P1 = Oktober des FY-Jahres
        .withColumn(
            "period_date",
            F.make_date(
                F.when(F.col("fy_period") <= 3, F.col("fy_year")).otherwise(F.col("fy_year") + 1),
                F.when(F.col("fy_period") <= 3, F.col("fy_period") + 9).otherwise(F.col("fy_period") - 3),
                F.lit(1),
            ),
        )
        .withColumn("betrag_ytd", F.sum("betrag_monat").over(w_ytd))
    )

    # Aus der bereits abgeleiteten Betriebsdimension, nicht erneut aus Bronze:
    # betriebstyp entsteht oben aus den Planbetriebslisten und muss hier
    # dieselbe Auspraegung haben wie in gold_dim_unit. Zweimal abgeleitet
    # liefe es beim naechsten Eingriff auseinander.
    #
    # dropDuplicates ist trotzdem NICHT optional: dieser Join steht auf der
    # Mengenseite der Umsaetze, und schon eine doppelte Betriebszeile
    # vervielfacht jede Umsatzzeile - lautlos, weil das Ergebnis wie echte
    # Daten aussieht.
    unit_coch = (
        dim_unit_sap.select(
            F.col("betrieb").alias("werk"), "cause_of_change", "cause_of_change_fy",
            "cause_of_change_ny", "betriebstyp",
        )
        .dropDuplicates(["werk"])
    )

    rev = (
        rev.join(unit_coch, "werk", "left")
        # Jede Variante bekommt das Bezugsjahr, aus dessen Sicht sie gepflegt
        # ist. cause_of_change und _fy blicken aus dem LAUFENDEN Jahr, _ny aus
        # dem FOLGEJAHR - deshalb liefert nur _ny fuer Zeilen des Budgetjahres
        # eine sinnvolle Zuordnung. Die Budgetkennzahlen setzen genau darauf
        # auf ("Mapping CoCh NY" im Altmodell).
        .withColumn(
            "metric_id",
            fn_map_coch(F.col("fy_year"), F.col("cause_of_change"), CURRENT_FY),
        )
        .withColumn(
            "metric_id_fy",
            fn_map_coch(F.col("fy_year"), F.col("cause_of_change_fy"), CURRENT_FY),
        )
        .withColumn(
            "metric_id_ny",
            fn_map_coch(F.col("fy_year"), F.col("cause_of_change_ny"), NEXT_FY),
        )
        # KEINE Vorzeichenumkehr. V_SAP_EXPORTS_cleansed liefert Ertraege
        # bereits mit dem fachlich richtigen Vorzeichen - die Bereinigung
        # passiert in der View, nicht hier. Eine frueher an dieser Stelle
        # stehende Umkehr (*-1) drehte die Werte ein zweites Mal und machte
        # Umsaetze negativ.
        #
        # NICHT VERWECHSELN mit der Vorzeichenkonvention der Faktentabelle
        # gold_fct_net_new_ity (Abschnitt 5): dort wird Lost Business bewusst
        # negativ gesetzt, damit Net New = einfache Summe ist. Das betrifft
        # CRM-Werte, nicht die SAP-Umsaetze hier.
        .withColumn("monat_index", (F.col("fy_year") * 12 + F.col("fy_period")).cast("int"))
        .select(
            # kategorie trennt Revenue (nur Ertragskonten) von UP (gesamter
            # Buchungsstoff). Beide liegen auf derselben Granularitaet - jede
            # Kennzahl muss darauf filtern, sonst summiert sie beide.
            "kategorie",
            "werk", "fy_year", "fy_period", "monat_index", "period_date",
            "werttyp", "version", "werttyp_version", "betrag_monat", "betrag_ytd",
            "metric_id", "metric_id_fy", "metric_id_ny", "betriebstyp",
            # Die rohen Cause-of-Change-Werte bleiben am Fakt, nicht nur die
            # daraus abgeleiteten metric_id*. Die Budgetlogik grenzt ueber die
            # Kombination Betriebstyp + cause_of_change_ny ab; laege eine der
            # beiden Spalten nur auf DIM Betrieb, muesste die Kennzahl den
            # Filter ueber zwei Tabellen legen - in DAX weder mit einem
            # einzelnen ALL() ausdrueckbar noch performant.
            "cause_of_change", "cause_of_change_fy", "cause_of_change_ny",
        )
    )
    write_delta(rev, "gold_fct_revenue", partition_by=["fy_year"])


# ===========================================================================
# 6. gold_fct_crm_movement - Was hat sich seit dem letzten Snapshot geaendert?
# ===========================================================================
# Speist die Berichtsseite "CRM-Bewegung". Grain: eine Zeile je Entitaet und
# Aenderungszeitpunkt, mit Vorher-/Nachher-Wert der ueberwachten Groessen.
def build_movement(hist_table, key_col, entity_type, business_type, value_col, prob_col):
    # Die Historientabelle waechst per Append. Wird eine neue ueberwachte
    # Groesse aufgenommen, fehlt sie in den bereits geschriebenen Zeilen -
    # bis nb_10_silver das naechste Mal mit mergeSchema angehaengt hat.
    # Ohne diese Absicherung braeche ein isolierter Gold-Lauf mit
    # UNRESOLVED_COLUMN ab.
    h = ergaenze_spalten(
        spark.table(hist_table), {value_col: "decimal(19,4)"}, hist_table
    )
    w = Window.partitionBy(key_col).orderBy("snapshot_date")
    return (
        h.withColumn("prev_value", F.lag(value_col).over(w))
        .withColumn("prev_probability", F.lag(prob_col).over(w))
        .withColumn("prev_status", F.lag("status_code").over(w))
        .withColumn("prev_snapshot_date", F.lag("snapshot_date").over(w))
        .filter(F.col("prev_snapshot_date").isNotNull())
        .select(
            F.col(key_col).alias("entity_id"),
            F.lit(entity_type).alias("entity_type"),
            F.lit(business_type).alias("business_type"),
            "snapshot_date", "prev_snapshot_date",
            F.col(value_col).cast("decimal(19,4)").alias("value_new"),
            F.col("prev_value").cast("decimal(19,4)").alias("value_old"),
            (F.col(value_col) - F.col("prev_value")).cast("decimal(19,4)").alias("value_delta"),
            F.col(prob_col).alias("probability_new"),
            F.col("prev_probability").alias("probability_old"),
            (F.col(prob_col) - F.col("prev_probability")).alias("probability_delta"),
            F.col("status_code").alias("status_new"),
            F.col("prev_status").alias("status_old"),
        )
        .withColumn(
            "aenderungsart",
            F.when(F.col("status_new") != F.col("status_old"), F.lit("Statuswechsel"))
            .when(F.abs(F.col("probability_delta")) > 0.001, F.lit("Wahrscheinlichkeit"))
            .when(F.abs(F.col("value_delta")) > 0.01, F.lit("Wert"))
            # Eine Zeile entsteht nur, wenn sich eine ueberwachte Groesse
            # geaendert hat. Trifft keiner der drei Faelle oben zu, war es
            # eines der uebrigen Felder - Termine oder Vertriebsphase.
            # "Sonstiges" allein liess den Leser genau hier ratlos zurueck.
            .otherwise(F.lit("Termin oder Vertriebsphase")),
        )
    )


# WELCHER WERT die Bewegung traegt, ist die entscheidende Festlegung hier:
# es muss die GEWICHTETE Groesse sein, also die, die im Bericht als Beitrag
# erscheint. Mit den ungewichteten Rohbetraegen (revenue_ity,
# last_fy_revenue_aro) zeigte die Tabelle bei einer reinen
# Wahrscheinlichkeitsaenderung eine Wertbewegung von 0 - fachlich falsch,
# denn der Forecastbeitrag aendert sich sehr wohl.
#
# weighted_ity_effektiv enthaelt zusaetzlich die ARO-Ersatzregel. Ohne sie
# stuenden dort bei Eroeffnung im Folgejahr durchgaengig 0 EUR, weil CRM den
# ITY-Wert gegen das laufende Geschaeftsjahr rechnet.
mv_new = build_movement(
    "silver_opportunity_history", "opportunityid", "OPPORTUNITY", "NEW",
    "weighted_ity_effektiv", "win_probability",
)
mv_lost = build_movement(
    "silver_contract_history", "cgplc_cgcontractid", "CONTRACT", "LOST",
    "weighted_ly_aro", "retention_probability",
)
write_delta(mv_new.unionByName(mv_lost), "gold_fct_crm_movement")


# ===========================================================================
# 7. gold_dim_snapshot - Liste der verfuegbaren Stichtage
# ===========================================================================
snaps = (
    spark.table("gold_fct_crm_movement")
    .select(F.col("snapshot_date").alias("snapshot_date"))
    .union(spark.table("gold_fct_net_new_ity").select("snapshot_date"))
    .distinct()
    .withColumn(
        "snapshot_label", F.date_format("snapshot_date", "dd.MM.yyyy")
    )
    .withColumn(
        "ist_aktuell",
        F.col("snapshot_date")
        == F.lit(spark.table("gold_fct_net_new_ity").agg(F.max("snapshot_date")).collect()[0][0]),
    )
)
write_delta(snaps, "gold_dim_snapshot")

print("Gold-Schicht fertig.")
