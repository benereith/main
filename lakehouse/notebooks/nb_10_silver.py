# Fabric notebook source
# ---------------------------------------------------------------------------
# nb_10_silver
# ---------------------------------------------------------------------------
# Bronze -> Silver: typisieren, bereinigen, fachlich filtern, historisieren.
#
# Eingang  : bronze_crm_opportunity, bronze_crm_contract, bronze_crm_account,
#            bronze_crm_territory
# Ausgang  : silver_opportunity, silver_contract, silver_*_history,
#            silver_dq_reject
#
# Die SAP-Tabellen laufen NICHT ueber diese Schicht: bronze_sap_unit und
# bronze_sap_revenue gehen unveraendert nach nb_20_gold.
#
# Zwei Dinge passieren hier, die es in den Altmodellen nicht gab:
#   1. SCD2-Historisierung. Jeder Ladelauf schreibt einen Snapshot; geaenderte
#      Attribute erzeugen eine neue Version. Damit wird die Frage
#      "Was hat sich seit dem letzten CRM-Call veraendert?" beantwortbar.
#   2. Explizite Business Rules aus der Group Guidance (Feb 2025), statt
#      impliziter if-Kaskaden in Power Query.
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

RUN_TS = spark.sql("SELECT current_timestamp() AS ts").collect()[0]["ts"]
RUN_DATE = RUN_TS.date()
print(f"Silver-Lauf {RUN_TS}")


# ===========================================================================
# 1. Opportunity (New Business)
# ===========================================================================
# Fachliche Filter - uebernommen aus fct_opp, aber jetzt begruendet:
#
#   a) statecodename <> 'Verloren'
#      Verlorene Opportunities sind kein New Business. Sie gehen NICHT in die
#      Lost-Business-Betrachtung ein - Lost Business betrifft ausschliesslich
#      BESTEHENDE Vertraege (Guidance S. 5: "termination of a contract to
#      provide a service which we previously provided").
#
#   b) salesstage not in ('Nobid','Turndown/Lost','Universe')
#      'Universe' = unqualifizierter Markt, 'Nobid'/'Turndown' = nicht verfolgt.
#      Keine Pipeline im Sinne des Forecasts.
#
#   c) openingdate >= CY_START (oder NULL)
#      Opportunities, deren Mobilisierung vor dem laufenden GJ liegt, wirken
#      nicht mehr auf das ITY des laufenden Jahres.
#
#   d) estimatedclosedate >= CY_START
#      Analog fuer den Entscheidungszeitpunkt.
#
#   e) openingdate IS NOT NULL
#      Ohne Mobilisierungsdatum ist keine Periodenverteilung moeglich. Diese
#      Zeilen werden NICHT stillschweigend verworfen, sondern in
#      gold_dq_checks als Regel DQ-OPP-001 protokolliert (siehe nb_30_quality).

# Erwartete Felder EINMAL absichern, statt an jeder Zugriffsstelle einzeln.
# Trennung nach Wirkung (Begruendung siehe pruefe_pflichtfelder in
# nb_00_config): fehlt ein Attribut, bleibt die Kennzahl richtig; fehlt ein
# Treiberfeld, waere das Ergebnis stillschweigend falsch.
OPP_PFLICHT = [
    "opportunityid",
    "cgplc_openingdate",     # Periodenverteilung
    "estimatedclosedate",    # Entscheidungszeitpunkt, Cluster-Zuordnung
    "cgplc_revenueity",      # ITY-Betrag
    "cgplc_win",             # Gewichtung
]
OPP_OPTIONAL = {
    "name": "string",
    "statecodename": "string",
    "cgplc_salesstagename": "string",
    "cgplc_wondate": "date",
    "actualclosedate": "date",
    "createdon": "timestamp",
    "modifiedon": "timestamp",
    "cgplc_bgpercent": "double",
    "cgplc_revenuearo": "decimal(19,4)",
    "cgplc_revenuearo_base": "decimal(19,4)",
    "cgplc_revenueity_base": "decimal(19,4)",
    "accountid": "string",
    "cgplc_territoryid": "string",
    "owneridname": "string",
}

opp_raw = nur_letzter_snapshot(
    spark.table("bronze_crm_opportunity"), "bronze_crm_opportunity"
)
pruefe_pflichtfelder(opp_raw, "bronze_crm_opportunity", OPP_PFLICHT)
opp_raw = ergaenze_spalten(opp_raw, OPP_OPTIONAL, "bronze_crm_opportunity")

opp = (
    opp_raw
    # --- Typisierung -------------------------------------------------------
    .withColumn("estimatedclosedate", F.to_date("estimatedclosedate"))
    .withColumn("cgplc_openingdate", F.to_date("cgplc_openingdate"))
    .withColumn("cgplc_wondate", F.to_date("cgplc_wondate"))
    .withColumn("actualclosedate", F.to_date("actualclosedate"))
    .withColumn("createdon", F.to_timestamp("createdon"))
    .withColumn("modifiedon", F.to_timestamp("modifiedon"))
    # CRM liefert Win-% als 0..100, das Modell rechnet mit 0..1.
    .withColumn("win_probability", F.col("cgplc_win").cast("double") / 100.0)
    .withColumn("bg_percent", F.col("cgplc_bgpercent").cast("double"))
    .withColumn("revenue_aro", F.col("cgplc_revenuearo").cast("decimal(19,4)"))
    .withColumn("revenue_ity", F.col("cgplc_revenueity").cast("decimal(19,4)"))
    .withColumn("revenue_aro_base", F.col("cgplc_revenuearo_base").cast("decimal(19,4)"))
    .withColumn("revenue_ity_base", F.col("cgplc_revenueity_base").cast("decimal(19,4)"))
)

opp_filtered = opp.filter(
    nicht_in(opp, "statecodename", EXCLUDED_STATE_NAMES)
    & nicht_in(opp, "cgplc_salesstagename", EXCLUDED_SALES_STAGES)
    & (F.col("estimatedclosedate") >= F.lit(CY_START))
    & (
        (F.col("cgplc_openingdate") >= F.lit(CY_START))
        | F.col("cgplc_openingdate").isNull()
    )
)

# Zeilen ohne Mobilisierungsdatum separat ablegen (DQ), nicht verwerfen.
opp_no_opening = opp_filtered.filter(F.col("cgplc_openingdate").isNull())
opp_valid = opp_filtered.filter(F.col("cgplc_openingdate").isNotNull())

# --- Ableitungen -----------------------------------------------------------
# ity_cluster: Wann faellt die ENTSCHEIDUNG, und wohin wirkt sie dadurch?
#   "unknown Roll" -> Abschluss im LAUFENDEN GJ. Der Umsatz faellt ueberwiegend
#                     erst im Folgejahr an (Mobilisierung folgt der
#                     Entscheidung), rollt also ins naechste Jahr hinueber.
#   "unknown ITY"  -> Abschluss im FOLGEJAHR. Wirkung entsteht innerhalb des
#                     Folgejahres selbst.
# Uebernommen aus fct_opp; Bezeichner beibehalten fuer Vergleichbarkeit mit
# den Altreports.
#
# Achtung Leserichtung: der Name benennt die WIRKUNG aus Sicht des Budgetjahrs,
# nicht den Abschlusszeitpunkt. Ein "unknown Roll" wird also JETZT gewonnen und
# zahlt auf das naechste Jahr ein - das ist die Groesse, die auf der Seite
# "Roll-Budget" gegen das Budget laeuft.
opp_silver = (
    opp_valid.withColumn(
        "ity_cluster",
        F.when(F.col("estimatedclosedate") <= F.lit(CY_END), F.lit("unknown Roll"))
        .when(
            (F.col("estimatedclosedate") >= F.lit(NY_START))
            & (F.col("estimatedclosedate") <= F.lit(NY_END)),
            F.lit("unknown ITY"),
        )
        .otherwise(F.lit(None)),
    )
    # --- Statusbucket (Default; im Bericht ueber What-if uebersteuerbar) ----
    .withColumn(
        "status_code",
        F.when(F.col("win_probability") >= WIN_THRESHOLD_WON, F.lit("WON"))
        .when(F.col("win_probability") >= WIN_THRESHOLD_EXPECTED, F.lit("EXPECTED_WIN"))
        .when(F.col("win_probability").isNotNull(), F.lit("PIPELINE"))
        .otherwise(F.lit("NO_PROBABILITY")),
    )
    # --- Gewichtete Werte --------------------------------------------------
    # Guidance MAP131 = ARO der ersten 12 Monate, MAP141a = ITY-Anteil davon.
    .withColumn("weighted_aro", F.col("revenue_aro") * F.col("win_probability"))
    .withColumn("weighted_ity", F.col("revenue_ity") * F.col("win_probability"))
    # --- Periodengeruest ---------------------------------------------------
    .withColumn("calc_start_date", month_start(F.col("cgplc_openingdate")))
    .withColumn("calc_first_fy_end", first_fy_end(F.col("cgplc_openingdate")))
    .withColumn(
        "calc_ity_months",
        months_between_inclusive(F.col("calc_start_date"), F.col("calc_first_fy_end")),
    )
    # --- Effektiver ITY-Beitrag --------------------------------------------
    # Der Betrag, den die Opportunity tatsaechlich zum Net New ITY ihres
    # ERSTEN Geschaeftsjahres beitraegt - gewichtet und inklusive der
    # ARO-Ersatzregel. Er ist damit deckungsgleich mit dem, was nb_20_gold
    # fuer value_layer = "ITY" aufsummiert.
    #
    # WOZU: die Bewegungsanalyse (gold_fct_crm_movement) verglich bisher
    # revenue_ity - den UNGEWICHTETEN CRM-Wert. Eine Aenderung der
    # Win-Wahrscheinlichkeit von 80 auf 95 Prozent bewegte diesen Wert nicht,
    # die Spalte "Bewegung Wert" blieb auf 0, obwohl sich der Beitrag zum
    # Forecast sehr wohl geaendert hatte. Bei Eroeffnung im Folgejahr stand
    # dort zusaetzlich durchgaengig 0, weil CRM den ITY-Wert gegen das
    # laufende Jahr rechnet.
    #
    # Bedingung und Ersatzwert sind identisch zu nb_20_gold, Abschnitt 5a
    # (ITY_LEER_WEIL_FOLGEJAHR). Aendert sich die Regel dort, muss sie hier
    # mitgezogen werden - DQ-FCT-003 vergleicht beide Seiten gegeneinander.
    .withColumn(
        "ity_ersatz_aro",
        (F.col("calc_start_date") > F.lit(CY_END))
        & (F.coalesce(F.col("revenue_ity"), F.lit(0.0)) == 0),
    )
    .withColumn(
        "weighted_ity_effektiv",
        F.when(
            F.col("ity_ersatz_aro"),
            F.coalesce(F.col("weighted_aro"), F.lit(0.0)) / F.lit(12.0)
            * F.col("calc_ity_months"),
        ).otherwise(F.coalesce(F.col("weighted_ity"), F.lit(0.0))),
    )
    .withColumn("snapshot_date", F.lit(RUN_DATE))
    .withColumn("loaded_at", F.lit(RUN_TS))
)

# --- Lookups anreichern ----------------------------------------------------
# KEIN Join gegen systemuser: die Entitaet ist im Mandanten nicht abrufbar.
# Der Klarname des Verantwortlichen kommt als owneridname direkt an der
# Opportunity mit - das genuegt fuer Filter und Anzeige.
acct_raw = ergaenze_spalten(
    nur_letzter_snapshot(spark.table("bronze_crm_account"), "bronze_crm_account"),
    {"accountid": "string", "name": "string", "cgplc_sapid": "string"},
    "bronze_crm_account",
)
acct = acct_raw.select(
    F.col("accountid"),
    F.col("name").alias("account_name"),
    F.col("cgplc_sapid").alias("account_sap_id"),
)
terr_raw = ergaenze_spalten(
    nur_letzter_snapshot(spark.table("bronze_crm_territory"), "bronze_crm_territory"),
    {"territoryid": "string", "name": "string"},
    "bronze_crm_territory",
)
terr = terr_raw.select(
    F.col("territoryid").alias("cgplc_territoryid"),
    F.col("name").alias("territory_name"),
)

opp_silver = (
    opp_silver.join(acct, "accountid", "left")
    .join(terr, "cgplc_territoryid", "left")
    .withColumn("owner_name", spalte_oder_null(opp_silver, "owneridname"))
)

write_delta(opp_silver, "silver_opportunity", mode="overwrite")


# ===========================================================================
# 2. Contract / Retention (Lost Business)
# ===========================================================================
# Fachliche Regeln - aus fct_retention, begruendet:
#
#   a) statuscodename = 'Aktiv'
#      Nur laufende Vertraege koennen verloren gehen.
#
#   b) Ersatz-Enddatum: contractenddate ?? decisiondate + 3 Monate
#      Viele Evergreen-Vertraege haben kein Enddatum. Die Guidance stellt auf
#      das ENTSCHEIDUNGSDATUM ab (S. 2: "based on contract decision dates
#      (as per CRM), not the operations mobilisation or closure date"); die
#      3 Monate bilden die uebliche Kuendigungsfrist bis zur Demobilisierung ab.
#
#   c) Enddatum im Fenster [CY_START, NY_END]
#      Ausserhalb wirkt der Vertrag nicht auf CY/NY.

CON_PFLICHT = [
    "cgplc_cgcontractid",
    "cgplc_lastfyrevenuearo",      # Verlustbetrag
    "cgplc_retentionprobability",  # Gewichtung
]
CON_OPTIONAL = {
    "cgplc_name": "string",
    "statuscodename": "string",
    "cgplc_contractenddate": "date",
    "cgplc_decisiondate": "date",
    "cgplc_forecastdecisiondate": "date",
    "cgplc_operationstartdate": "date",
    "cgplc_revenuearo": "decimal(19,4)",
    "cgplc_reasonforriskname": "string",
}

con_raw = nur_letzter_snapshot(
    spark.table("bronze_crm_contract"), "bronze_crm_contract"
)
pruefe_pflichtfelder(con_raw, "bronze_crm_contract", CON_PFLICHT)
# Vor dem Ergaenzen merken: danach existiert die Spalte immer (ggf. als NULL).
HAT_VERTRAGSSTATUS = "statuscodename" in con_raw.columns
con_raw = ergaenze_spalten(con_raw, CON_OPTIONAL, "bronze_crm_contract")

con = (
    con_raw.withColumn("cgplc_contractenddate", F.to_date("cgplc_contractenddate"))
    .withColumn("cgplc_decisiondate", F.to_date("cgplc_decisiondate"))
    .withColumn("cgplc_forecastdecisiondate", F.to_date("cgplc_forecastdecisiondate"))
    .withColumn("cgplc_operationstartdate", F.to_date("cgplc_operationstartdate"))
    .withColumn(
        "retention_probability", F.col("cgplc_retentionprobability").cast("double") / 100.0
    )
    .withColumn("revenue_aro", F.col("cgplc_revenuearo").cast("decimal(19,4)"))
    .withColumn("last_fy_revenue_aro", F.col("cgplc_lastfyrevenuearo").cast("decimal(19,4)"))
)

# Einschlussfilter, nicht Ausschluss: ohne statuscodename laesst sich "aktiv"
# nicht bestimmen. Dann lieber ALLE Vertraege behalten und laut darauf
# hinweisen - ein stiller Filter auf NULL wuerde das komplette Lost Business
# verschwinden lassen, und der Bericht saehe dabei voellig unauffaellig aus.
if HAT_VERTRAGSSTATUS:
    con = con.filter(F.col("statuscodename").isin(ACTIVE_CONTRACT_STATUS))
else:
    print(
        "  WARNUNG bronze_crm_contract: statuscodename fehlt - Filter auf "
        "aktive Vertraege entfaellt, ALLE Vertraege gehen in Lost Business ein"
    )

con = con.withColumn(
    "adj_end_date",
    F.coalesce(F.col("cgplc_contractenddate"), F.add_months(F.col("cgplc_decisiondate"), 3)),
)

con_valid = con.filter(
    F.col("adj_end_date").isNotNull()
    & (F.col("adj_end_date") >= F.lit(CY_START))
    & (F.col("adj_end_date") <= F.lit(NY_END))
)

con_silver = (
    con_valid.withColumn(
        "ity_cluster",
        F.when(F.col("adj_end_date") <= F.lit(CY_END), F.lit("unknown Roll"))
        .when(F.col("adj_end_date") >= F.lit(NY_START), F.lit("unknown ITY"))
        .otherwise(F.lit(None)),
    )
    # --- Statusbucket ------------------------------------------------------
    # Achtung Leserichtung: retention_probability = Wahrscheinlichkeit, den
    # Vertrag zu BEHALTEN. Verlustwahrscheinlichkeit = 1 - retention.
    .withColumn(
        "status_code",
        F.when(F.col("retention_probability").isNull(), F.lit("NO_PROBABILITY"))
        .when(F.col("retention_probability") <= RETENTION_THRESHOLD_LOST, F.lit("LOST"))
        .when(
            F.col("retention_probability") <= RETENTION_THRESHOLD_EXPECTED_LOSS,
            F.lit("EXPECTED_LOSS"),
        )
        .when(F.col("retention_probability") < 1.0, F.lit("AT_RISK"))
        .otherwise(F.lit("NO_RISK")),
    )
    # Erwarteter Verlust = Vorjahres-ARO x Verlustwahrscheinlichkeit
    .withColumn(
        "weighted_ly_aro",
        F.col("last_fy_revenue_aro") * (F.lit(1.0) - F.col("retention_probability")),
    )
    # --- Periodengeruest ---------------------------------------------------
    # calc_end_date = ERSTER Monat OHNE Umsatz (Monatsanfang nach Vertragsende).
    .withColumn("calc_end_date", F.add_months(month_start(F.col("adj_end_date")), 1))
    .withColumn("calc_first_fy_end", first_fy_end(F.col("adj_end_date")))
    .withColumn(
        "calc_ity_months",
        months_between_inclusive(F.col("calc_end_date"), F.col("calc_first_fy_end")),
    )
    .withColumn(
        "ly_aro_status",
        F.when(F.col("last_fy_revenue_aro").isNull(), F.lit("Kein ARO im CRM")).otherwise(
            F.lit("ARO im CRM")
        ),
    )
    .withColumn("snapshot_date", F.lit(RUN_DATE))
    .withColumn("loaded_at", F.lit(RUN_TS))
)

write_delta(con_silver, "silver_contract", mode="overwrite")


# ===========================================================================
# 3. SAP-Stammdaten (Betriebe) - ENTFAELLT HIER
# ===========================================================================
# Frueher entstand an dieser Stelle silver_unit. Der Schritt ist entfallen:
# er hat nichts bereinigt, gefiltert oder historisiert, sondern nur vier
# abgeleitete Spalten ergaenzt (werk_bezeichnung, betriebstyp,
# known_unknown, hfm_sektor). Dafuer eine eigene Schicht zu durchlaufen
# kostete eine Tabelle, einen Schreibvorgang und eine Auswahlliste, in der
# jede neue Quellspalte stillschweigend liegen blieb.
#
# bronze_sap_unit geht jetzt unveraendert nach nb_20_gold; die Ableitungen
# passieren dort. Zwischen Bronze und Gold wird an dieser Tabelle nichts
# mehr veraendert - insbesondere wird keine Spalte mehr weggelassen.

# ===========================================================================
# 4. SCD2-Historisierung der CRM-Kennzahlen
# ===========================================================================
# Ziel: pro Opportunity/Vertrag genau eine Zeile je Tag, an dem sich eine der
# ueberwachten Groessen geaendert hat. Daraus speist sich spaeter
# gold_fct_crm_movement (Seite "CRM-Bewegung" im Bericht).
#
# Ueberwachte Groessen New Business:
#   win_probability, revenue_aro, revenue_ity, estimatedclosedate,
#   cgplc_openingdate, cgplc_salesstagename
# Ueberwachte Groessen Lost Business:
#   retention_probability, last_fy_revenue_aro, adj_end_date,
#   cgplc_reasonforriskname

# weighted_ity_effektiv bzw. weighted_ly_aro sind die GEWICHTETEN Groessen -
# genau die, die im Bericht als Beitrag erscheinen. Ohne sie zeigte die
# Bewegungsanalyse eine Wahrscheinlichkeitsaenderung zwar an, meldete daneben
# aber eine Wertaenderung von 0: die ungewichteten Rohbetraege
# (revenue_ity, last_fy_revenue_aro) bleiben bei einer reinen
# Wahrscheinlichkeitsaenderung naemlich unveraendert.
TRACKED_OPP = [
    "win_probability", "revenue_aro", "revenue_ity", "weighted_ity_effektiv",
    "estimatedclosedate", "cgplc_openingdate", "cgplc_salesstagename",
    "status_code",
]
TRACKED_CON = [
    "retention_probability", "last_fy_revenue_aro", "weighted_ly_aro",
    "adj_end_date", "cgplc_reasonforriskname", "status_code",
]


def append_history(df, table_name: str, key_col: str, tracked_cols: list):
    """Haengt den Tagessnapshot an die Historientabelle an - aber nur, wenn
    sich mindestens eine ueberwachte Spalte gegenueber der letzten Version
    geaendert hat. So bleibt die Historie schlank und jede Zeile bedeutet
    tatsaechlich eine Aenderung.
    """
    cols = [key_col, "snapshot_date"] + tracked_cols
    today = df.select(*cols).withColumn(
        "row_hash", F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"),
                                                          F.lit("~")) for c in tracked_cols]), 256)
    )

    if spark.catalog.tableExists(table_name):
        hist = spark.table(table_name)
        latest = (
            hist.withColumn(
                "rn",
                F.row_number().over(
                    Window.partitionBy(key_col).orderBy(F.col("snapshot_date").desc())
                ),
            )
            .filter(F.col("rn") == 1)
            .select(F.col(key_col).alias("k"), F.col("row_hash").alias("prev_hash"))
        )
        changed = (
            today.join(latest, today[key_col] == latest["k"], "left")
            .filter(F.col("prev_hash").isNull() | (F.col("row_hash") != F.col("prev_hash")))
            .drop("k", "prev_hash")
        )
        write_delta(changed, table_name, mode="append")
    else:
        write_delta(today, table_name, mode="overwrite")


append_history(opp_silver, "silver_opportunity_history", "opportunityid", TRACKED_OPP)
append_history(con_silver, "silver_contract_history", "cgplc_cgcontractid", TRACKED_CON)

# DQ-Ausschuss ablegen
write_delta(
    opp_no_opening.select("opportunityid", "name", "estimatedclosedate",
                          "cgplc_salesstagename", "cgplc_revenueity")
    .withColumn("dq_rule", F.lit("DQ-OPP-001"))
    .withColumn("dq_message", F.lit("Opportunity ohne cgplc_openingdate - keine Periodenverteilung moeglich"))
    .withColumn("snapshot_date", F.lit(RUN_DATE)),
    "silver_dq_reject",
    mode="overwrite",
)

print("Silver-Schicht fertig.")
