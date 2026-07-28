# Fabric notebook source
# ---------------------------------------------------------------------------
# nb_30_quality
# ---------------------------------------------------------------------------
# Datenqualitaetsregeln. Schreibt gold_dq_checks und bricht die Pipeline ab,
# wenn eine Regel der Stufe ERROR verletzt ist - BEVOR das Semantikmodell
# aktualisiert wird.
#
# Die Regeln adressieren genau die Fehlerbilder, die in den Altmodellen zu
# manueller Nacharbeit gefuehrt haben.
# ---------------------------------------------------------------------------

# MAGIC %run nb_00_config

from pyspark.sql import functions as F

RUN_TS = spark.sql("SELECT current_timestamp() AS ts").collect()[0]["ts"]
RUN_DATE = RUN_TS.date()

results = []


def check(rule_id: str, severity: str, beschreibung: str, df_violations, hinweis: str):
    """Registriert eine Regel und ihre Verstoesse.

    severity: ERROR   -> Pipeline bricht ab, Semantikmodell wird nicht aktualisiert
              WARNING -> wird im Bericht auf der Seite Datenqualitaet gezeigt
              INFO    -> reine Kennzahl
    """
    n = df_violations.count()
    results.append(
        (rule_id, severity, beschreibung, n, hinweis, RUN_DATE)
    )
    flag = "OK  " if n == 0 else ("FAIL" if severity == "ERROR" else "WARN")
    print(f"[{flag}] {rule_id} ({severity}): {n:,} Verstoesse - {beschreibung}")
    return n


fct = spark.table("gold_fct_net_new_ity")
opp = spark.table("silver_opportunity")
con = spark.table("silver_contract")
rej = spark.table("silver_dq_reject")

# ---------------------------------------------------------------------------
# DQ-OPP-001  Opportunity ohne Mobilisierungsdatum
# ---------------------------------------------------------------------------
# Ohne cgplc_openingdate ist keine Periodenverteilung moeglich. Im Altmodell
# wurden diese Zeilen in fct_opp stillschweigend gefiltert
# (#"Gefilterte Zeilen 3") - der Wert verschwand ohne Spur.
check(
    "DQ-OPP-001", "WARNING",
    "Opportunity ohne Mobilisierungsdatum (cgplc_openingdate)",
    rej.filter(F.col("dq_rule") == "DQ-OPP-001"),
    "Mobilisierungsdatum im CRM nachpflegen, sonst faellt der ITY-Effekt aus dem Forecast.",
)

# ---------------------------------------------------------------------------
# DQ-OPP-002  Opportunity mit ARO aber ohne ITY
# ---------------------------------------------------------------------------
check(
    "DQ-OPP-002", "WARNING",
    "Opportunity mit ARO-Umsatz, aber ohne ITY-Umsatz",
    opp.filter((F.col("revenue_aro") > 0) & (F.coalesce(F.col("revenue_ity"), F.lit(0)) == 0)),
    "cgplc_revenueity im CRM ergaenzen - sonst wird der ITY-Effekt mit 0 gerechnet.",
)

# ---------------------------------------------------------------------------
# DQ-OPP-003  ITY groesser als ARO
# ---------------------------------------------------------------------------
# Der ITY-Wert ist definitionsgemaess der Anteil des ARO, der im ersten
# Geschaeftsjahr anfaellt - er kann den ARO nicht uebersteigen.
check(
    "DQ-OPP-003", "ERROR",
    "ITY-Umsatz groesser als ARO-Umsatz (fachlich unmoeglich)",
    opp.filter(F.col("revenue_ity") > F.col("revenue_aro") * 1.001),
    "CRM-Datensatz korrigieren: MAP141a kann MAP131 nicht uebersteigen (Guidance S. 3).",
)

# ---------------------------------------------------------------------------
# DQ-OPP-004  ITY-Rate weicht stark von ARO/12 ab
# ---------------------------------------------------------------------------
# Erwartung: ITY / ITY-Monate ~ ARO / 12. Grosse Abweichungen deuten auf
# falsch gepflegte ITY-Werte hin. Toleranz bewusst weit (Faktor 2), damit
# nur echte Ausreisser auffallen.
ity_rate = F.col("revenue_ity") / F.col("calc_ity_months")
aro_rate = F.col("revenue_aro") / F.lit(12.0)
check(
    "DQ-OPP-004", "WARNING",
    "Monatliche ITY-Rate weicht um mehr als Faktor 2 von ARO/12 ab",
    opp.filter(
        (F.col("calc_ity_months") > 0)
        & (F.col("revenue_aro") > 0)
        & (F.col("revenue_ity") > 0)
        & ((ity_rate > aro_rate * 2) | (ity_rate < aro_rate / 2))
    ),
    "Plausibilitaet von cgplc_revenueity gegen cgplc_revenuearo pruefen.",
)

# ---------------------------------------------------------------------------
# DQ-OPP-005  Win-% ausserhalb 0..100
# ---------------------------------------------------------------------------
check(
    "DQ-OPP-005", "ERROR",
    "Win-Wahrscheinlichkeit ausserhalb 0-100 %",
    opp.filter((F.col("win_probability") < 0) | (F.col("win_probability") > 1)),
    "cgplc_win im CRM korrigieren.",
)

# ---------------------------------------------------------------------------
# DQ-OPP-006  Mobilisierung vor Entscheidung
# ---------------------------------------------------------------------------
check(
    "DQ-OPP-006", "WARNING",
    "Mobilisierungsdatum liegt vor dem erwarteten Abschlussdatum",
    opp.filter(F.col("cgplc_openingdate") < F.col("estimatedclosedate")),
    "Termine im CRM pruefen - Reihenfolge Entscheidung -> Mobilisierung.",
)

# ---------------------------------------------------------------------------
# DQ-CON-001  Vertrag ohne Vorjahres-ARO
# ---------------------------------------------------------------------------
# Ohne cgplc_lastfyrevenuearo ist der Verlustwert 0 - der Vertrag verschwindet
# faktisch aus dem Lost-Business-Forecast.
check(
    "DQ-CON-001", "WARNING",
    "Aktiver Risikovertrag ohne Vorjahres-ARO (cgplc_lastfyrevenuearo)",
    con.filter(
        F.col("last_fy_revenue_aro").isNull()
        & (F.col("retention_probability") < 1.0)
    ),
    "Vorjahres-ARO im CRM nachpflegen, sonst wird der Verlust mit 0 EUR bewertet.",
)

# ---------------------------------------------------------------------------
# DQ-CON-002  Vertrag ohne Enddatum und ohne Entscheidungsdatum
# ---------------------------------------------------------------------------
check(
    "DQ-CON-002", "WARNING",
    "Vertrag ohne Vertragsende und ohne Entscheidungsdatum",
    spark.table("bronze_crm_contract").filter(
        F.col("cgplc_contractenddate").isNull() & F.col("cgplc_decisiondate").isNull()
    ),
    "Ohne beide Daten ist keine Periodenzuordnung moeglich (Guidance: Decision Date massgeblich).",
)

# ---------------------------------------------------------------------------
# DQ-CON-003  Retention-% ausserhalb 0..100
# ---------------------------------------------------------------------------
check(
    "DQ-CON-003", "ERROR",
    "Retention-Wahrscheinlichkeit ausserhalb 0-100 %",
    con.filter((F.col("retention_probability") < 0) | (F.col("retention_probability") > 1)),
    "cgplc_retentionprobability im CRM korrigieren.",
)

# ---------------------------------------------------------------------------
# DQ-FCT-001  Fanout-Luecken
# ---------------------------------------------------------------------------
# Jede Entitaet muss eine lueckenlose Monatskette haben. Luecken deuten auf
# Fehler im Fanout hin.
gaps = (
    fct.groupBy("entity_id")
    .agg(
        F.countDistinct("period_date").alias("n_perioden"),
        F.min("period_date").alias("von"),
        F.max("period_date").alias("bis"),
    )
    .withColumn(
        "erwartet",
        (F.months_between(F.col("bis"), F.col("von")) + 1).cast("int"),
    )
    .filter(F.col("n_perioden") != F.col("erwartet"))
)
check(
    "DQ-FCT-001", "ERROR",
    "Luecken in der Monatskette des Perioden-Fanouts",
    gaps,
    "nb_20_gold pruefen - die Monatssequenz ist unvollstaendig.",
)

# ---------------------------------------------------------------------------
# DQ-FCT-002  Vorzeichenkonvention verletzt
# ---------------------------------------------------------------------------
check(
    "DQ-FCT-002", "ERROR",
    "Vorzeichenkonvention verletzt (NEW muss >= 0, LOST muss <= 0 sein)",
    fct.filter(
        ((F.col("business_type") == "NEW") & (F.col("amount_signed") < 0))
        | ((F.col("business_type") == "LOST") & (F.col("amount_signed") > 0))
    ),
    "nb_20_gold, Abschnitt 5: amount_signed pruefen.",
)

# ---------------------------------------------------------------------------
# DQ-FCT-003  Rekonstruktion des ITY-Gesamtwerts
# ---------------------------------------------------------------------------
# Die Summe der ITY-Monatswerte einer Opportunity im ersten GJ muss dem
# gewichteten ITY-Wert entsprechen. Toleranz 1 Cent je Zeile.
recon = (
    fct.filter((F.col("business_type") == "NEW") & (F.col("value_layer") == "ITY"))
    .groupBy("entity_id")
    .agg(F.sum("amount_weighted").alias("summe_fanout"))
    .join(
        spark.table("silver_opportunity").select(
            F.col("opportunityid").alias("entity_id"), "weighted_ity"
        ),
        "entity_id",
    )
    .withColumn("abweichung", F.abs(F.col("summe_fanout") - F.col("weighted_ity")))
    .filter(F.col("abweichung") > 0.01)
)
check(
    "DQ-FCT-003", "ERROR",
    "Summe der ITY-Monatswerte weicht vom gewichteten ITY-Gesamtwert ab",
    recon,
    "Fanout-Logik pruefen: calc_ity_months oder der Wertebereich stimmen nicht.",
)

# ---------------------------------------------------------------------------
# DQ-MAP-001  Opportunity ohne Zuordnung zu einem SAP-Betrieb
# ---------------------------------------------------------------------------
# Ersetzt das SharePoint-Mapping dim_opp_mapping (Mapping_Planwerke.xlsx).
check(
    "DQ-MAP-001", "INFO",
    "Opportunity ohne Zuordnung zu einem Planbetrieb",
    opp.filter(F.col("account_sap_id").isNull()),
    "Zuordnung im CRM (cgplc_sapid) oder in der Mapping-Tabelle ergaenzen.",
)

# ---------------------------------------------------------------------------
# Ergebnis schreiben und ggf. abbrechen
# ---------------------------------------------------------------------------
dq = spark.createDataFrame(
    results,
    "regel_id string, schweregrad string, beschreibung string, anzahl_verstoesse long, "
    "hinweis string, pruef_datum date",
)
write_delta(dq, "gold_dq_checks", mode="append")

errors = [r for r in results if r[1] == "ERROR" and r[3] > 0]
if errors:
    raise Exception(
        "Datenqualitaetspruefung fehlgeschlagen:\n"
        + "\n".join(f"  {r[0]}: {r[3]:,} Verstoesse - {r[2]}" for r in errors)
    )

print("Alle ERROR-Regeln bestanden.")
