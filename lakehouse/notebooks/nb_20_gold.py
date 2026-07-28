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

# MAGIC %run nb_00_config

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
unit = spark.table("silver_unit")
write_delta(
    unit.select(
        "betrieb", "werk_bezeichnung", "bezeichnung_betrieb", "buchungskreis",
        "sektor", "hfm_sektor", "betriebstyp", "known_unknown", "vertragsbeginn",
        "schliessung", "bezeichnung_vertragsart", "bezeichnung_region",
        "bezeichnung_management", "bezeichnung_verantwortungsbereich",
        "bezeichnung_branche", "bezeichnung_kundengruppe", "bundesland", "stadt",
        "cause_of_change", "bezeichnung_cause_of_change",
        "cause_of_change_fy", "cause_of_change_ny",
    ).dropDuplicates(["betrieb"]),
    "gold_dim_unit",
)

opp = spark.table("silver_opportunity")
write_delta(
    opp.select(
        F.col("opportunityid"),
        F.col("name").alias("opportunity_name"),
        "account_name", "owner_name", "territory_name",
        F.col("cgplc_salesstagename").alias("sales_stage"),
        F.col("cgplc_contracttypelookup").alias("contract_type"),
        F.col("cgplc_sectorlookup").alias("sector"),
        F.col("cgplc_subsector").alias("subsector"),
        F.col("cgplc_currentsupplier").alias("current_supplier"),
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
        spalte_oder_null(con, "cgplc_sectorlookup").alias("sector"),
        spalte_oder_null(con, "cgplc_subsector").alias("subsector"),
        spalte_oder_null(con, "cgplc_contracttypelookup").alias("contract_type"),
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
    spalte_oder_null(silver_opp, "cgplc_sectorlookup").alias("sector"),
    spalte_oder_null(silver_opp, "cgplc_subsector").alias("subsector"),
    spalte_oder_null(silver_opp, "cgplc_contracttypelookup").alias("contract_type"),
    "account_name", "owner_name",
    # Betriebsnummer, sofern direkt am Vorgang gepflegt. Das ist nur Stufe 2
    # der Aufloesungskette - die eigentliche Zuordnung passiert in Abschnitt
    # 5d ueber die Mapping-Tabelle (Sektor/Subsektor -> Planbetrieb).
    # Die SAP-Nummer des Kontos wird bewusst NICHT als Ersatz verwendet:
    # sie ist ein Debitor, kein Betrieb.
    spalte_oder_null(silver_opp, "cgplc_sapid", "int").alias("sap_id_crm"),
)

fct_new = (
    opp_base.join(months, F.col("period_date") >= F.col("event_month"))
    .filter(F.col("period_date") <= F.lit(FANOUT_END))
    .withColumn(
        "ity_rate",
        F.when(
            (F.col("calc_ity_months") > 0) & F.col("weighted_ity").isNotNull(),
            F.col("weighted_ity") / F.col("calc_ity_months"),
        ).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "aro_rate",
        F.when(F.col("weighted_aro").isNotNull(), F.col("weighted_aro") / F.lit(12.0)).otherwise(
            F.lit(0.0)
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
            F.when(F.col("calc_ity_months") > 0,
                   F.coalesce(F.col("revenue_ity"), F.lit(0.0)) / F.col("calc_ity_months")).otherwise(F.lit(0.0)),
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
        spark.table("bronze_crm_account")
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
    spalte_oder_null(silver_con, "cgplc_sectorlookup").alias("sector"),
    spalte_oder_null(silver_con, "cgplc_subsector").alias("subsector"),
    spalte_oder_null(silver_con, "cgplc_contracttypelookup").alias("contract_type"),
    spalte_oder_null(silver_con, "account_name").alias("account_name"),
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
)

COMMON = [
    "entity_id", "entity_name", "entity_type", "business_type", "status_code",
    "ity_cluster", "probability", "period_date", "value_layer", "hfm_account",
    "amount_weighted", "amount_unweighted", "event_month", "driver_date",
    "decision_date", "calc_first_fy_end", "calc_ity_months",
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
# cgplc_sapid ist am Vorgang nur lueckenhaft gepflegt. Die fachliche
# Information, WOHIN ein Vorgang gehoert, haengt am Sektor und Subsektor und
# wird vom Controlling in bronze_map_unit_assignment gepflegt (Quelle:
# Mapping_Planwerke.xlsx, siehe dataflows/df_map_unit_assignment.m).
#
# Aufloesungskette, erste Treffer gewinnt:
#   1. AUSNAHME     entity_id-Zeile der Mapping-Tabelle (Einzelfall schlaegt
#                   alles - dafuer ist eine Ausnahme da)
#   2. CRM          cgplc_sapid am Vorgang selbst
#   3. MAPPING S+S  Mapping-Zeile mit passendem Sektor UND Subsektor
#   4. MAPPING S    Mapping-Zeile mit passendem Sektor, subsektor leer
#   5. NULL         -> Regel DQ-MAP-001
#
# Die Herkunft wird als werk_zuordnung mitgefuehrt. Damit ist im Bericht je
# Vorgang sichtbar, ob eine Zahl auf gepflegten CRM-Daten oder auf dem
# Mapping beruht - und die Nachpflege laesst sich priorisieren.
if spark.catalog.tableExists("bronze_map_unit_assignment"):
    mapping = spark.table("bronze_map_unit_assignment")

    map_entity = (
        mapping.filter(F.col("entity_id").isNotNull())
        .select(F.col("entity_id"), F.col("werk").alias("werk_ausnahme"))
        .dropDuplicates(["entity_id"])
    )
    map_subsektor = (
        mapping.filter(F.col("entity_id").isNull() & F.col("subsektor").isNotNull())
        .select(
            F.col("sektor").alias("m2_sektor"),
            F.col("subsektor").alias("m2_subsektor"),
            F.col("werk").alias("werk_subsektor"),
        )
        .dropDuplicates(["m2_sektor", "m2_subsektor"])
    )
    map_sektor = (
        mapping.filter(F.col("entity_id").isNull() & F.col("subsektor").isNull())
        .select(F.col("sektor").alias("m3_sektor"), F.col("werk").alias("werk_sektor"))
        .dropDuplicates(["m3_sektor"])
    )

    fct = (
        fct.join(map_entity, "entity_id", "left")
        .join(
            map_subsektor,
            (F.col("sector") == F.col("m2_sektor"))
            & (F.col("subsector") == F.col("m2_subsektor")),
            "left",
        )
        .join(map_sektor, F.col("sector") == F.col("m3_sektor"), "left")
    )
else:
    # Mapping-Tabelle (noch) nicht geladen: Kette degradiert auf Stufe 2.
    # Kein Abbruch - die Luecken werden von DQ-MAP-001 gezaehlt.
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
            F.col("sap_id_crm").cast("int"),
            F.col("werk_subsektor"),
            F.col("werk_sektor"),
        ),
    )
    .withColumn(
        "werk_zuordnung",
        F.when(F.col("werk_ausnahme").isNotNull(), F.lit("Ausnahme (Mapping)"))
        .when(F.col("sap_id_crm").isNotNull(), F.lit("CRM direkt"))
        .when(F.col("werk_subsektor").isNotNull(), F.lit("Mapping Sektor/Subsektor"))
        .when(F.col("werk_sektor").isNotNull(), F.lit("Mapping Sektor"))
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
# Die Zuordnung folgt DIM_Struktur:
#   1 = PY revenue from contracts won PY      (MAP111a)
#   2 = CY revenue from contracts won PY      (MAP111b)
#   4 = New Business ITY                      (MAP111c)
#   6 = Lost Business Roll                    (MAP112a)
#   7 = PY revenue from contracts lost CY     (MAP112b)
#   8 = CY revenue from contracts lost CY     (MAP112c)
#  99 = Like for Like
def fn_map_coch(fy_col, coch_col):
    """Cause-of-Change -> MetricId der Net-New-Hierarchie."""
    return (
        F.when(coch_col == 3, F.lit(6))
        .when((fy_col == PRIOR_FY) & (coch_col == 1), F.lit(1))
        .when((fy_col == CURRENT_FY) & (coch_col == 1), F.lit(2))
        .when((fy_col == CURRENT_FY) & (coch_col == 2), F.lit(4))
        .when((fy_col == PRIOR_FY) & (coch_col == 4), F.lit(7))
        .when((fy_col == CURRENT_FY) & (coch_col == 4), F.lit(8))
        .otherwise(F.lit(99))
    )


rev = spark.table("bronze_sap_revenue")

# Monatswert und YTD je Werk/Version/Geschaeftsjahr
w_ytd = Window.partitionBy("werk", "version", "fy_year").orderBy("fy_period").rowsBetween(
    Window.unboundedPreceding, Window.currentRow
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

unit_coch = spark.table("silver_unit").select(
    F.col("betrieb").alias("werk"), "cause_of_change", "cause_of_change_fy",
    "cause_of_change_ny", "betriebstyp",
)

rev = (
    rev.join(unit_coch, "werk", "left")
    .withColumn("metric_id", fn_map_coch(F.col("fy_year"), F.col("cause_of_change")))
    .withColumn("metric_id_fy", fn_map_coch(F.col("fy_year"), F.col("cause_of_change_fy")))
    .withColumn("metric_id_ny", fn_map_coch(F.col("fy_year"), F.col("cause_of_change_ny")))
    # Vorzeichen: SAP liefert Ertraege negativ. Wir drehen einmal zentral,
    # damit im Bericht nirgends mehr "*-1" steht.
    .withColumn("betrag_monat", -F.col("betrag_monat"))
    .withColumn("betrag_ytd", -F.col("betrag_ytd"))
    .withColumn("monat_index", (F.col("fy_year") * 12 + F.col("fy_period")).cast("int"))
    .select(
        "werk", "fy_year", "fy_period", "monat_index", "period_date",
        "werttyp", "version", "werttyp_version", "betrag_monat", "betrag_ytd",
        "metric_id", "metric_id_fy", "metric_id_ny", "betriebstyp",
    )
)
write_delta(rev, "gold_fct_revenue", partition_by=["fy_year"])


# ===========================================================================
# 6. gold_fct_crm_movement - Was hat sich seit dem letzten Snapshot geaendert?
# ===========================================================================
# Speist die Berichtsseite "CRM-Bewegung". Grain: eine Zeile je Entitaet und
# Aenderungszeitpunkt, mit Vorher-/Nachher-Wert der ueberwachten Groessen.
def build_movement(hist_table, key_col, entity_type, business_type, value_col, prob_col):
    h = spark.table(hist_table)
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
            .otherwise(F.lit("Sonstiges")),
        )
    )


mv_new = build_movement(
    "silver_opportunity_history", "opportunityid", "OPPORTUNITY", "NEW",
    "revenue_ity", "win_probability",
)
mv_lost = build_movement(
    "silver_contract_history", "cgplc_cgcontractid", "CONTRACT", "LOST",
    "last_fy_revenue_aro", "retention_probability",
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
