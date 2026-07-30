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


# Fehlende Vorgaengertabelle heisst: der Lauf davor ist gescheitert oder wurde
# nie ausgefuehrt. Die rohe TABLE_OR_VIEW_NOT_FOUND nennt zwar den Tabellennamen,
# aber nicht die Ursache - deshalb hier eine Meldung, die auf das verursachende
# Notebook zeigt statt auf die Qualitaetspruefung, die nur das Opfer ist.
VORAUSSETZUNGEN = {
    "gold_fct_net_new_ity": "nb_20_gold",
    "silver_opportunity": "nb_10_silver",
    "silver_contract": "nb_10_silver",
    "silver_dq_reject": "nb_10_silver",
}
_fehlend = [t for t in VORAUSSETZUNGEN if not spark.catalog.tableExists(t)]
if _fehlend:
    raise ValueError(
        "Vorgaengertabelle(n) fehlen: " + ", ".join(sorted(_fehlend)) + ".\n"
        "Verursachendes Notebook: "
        + ", ".join(sorted({VORAUSSETZUNGEN[t] for t in _fehlend}))
        + " - dort die Fehlermeldung des letzten Laufs pruefen.\n"
        "nb_30_quality selbst ist nicht die Ursache; es liest nur."
    )

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
# DQ-FCT-004  Konforme Attribute nur einseitig befuellt
# ---------------------------------------------------------------------------
# Diese Regel adressiert eine ganze FEHLERKLASSE, nicht einen Einzelfall.
#
# Sektor, Subsektor, Vertragsart, Kunde, Verantwortlicher und die
# Betriebsnummer liegen auf dem Fakt, weil sie fuer BEIDE Geschaeftsarten
# gelten sollen. Ist eine dieser Spalten auf einer Seite systematisch leer,
# filtert ein Datenschnitt darauf nur die andere Haelfte - und liefert eine
# falsche Zahl ohne jedes Fehlerbild. Genau dieser Fall lag vor, als
# gold_dim_contract Sektor und Subsektor nicht selektierte und der Fakt
# sap_id nur fuer Vertraege fuehrte.
#
# Schwelle: Eine Seite gilt als "systematisch leer", wenn dort ueber 95 % der
# Werte fehlen, waehrend die andere Seite zu mindestens 50 % gefuellt ist.
# Einzelne Luecken sind normal und werden bewusst nicht gemeldet.
KONFORME_ATTRIBUTE = [
    ("sector", "Sektor"),
    ("subsector", "Subsektor"),
    ("contract_type", "Vertragsart"),
    ("account_name", "Kunde"),
    ("owner_name", "Verantwortlicher"),
    ("sap_id", "Werk"),
]

fuellgrad = (
    fct.groupBy("business_type")
    .agg(*[
        (F.count(F.col(spalte)) / F.count(F.lit(1))).alias(spalte)
        for spalte, _ in KONFORME_ATTRIBUTE
    ])
    .collect()
)
grade = {zeile["business_type"]: zeile.asDict() for zeile in fuellgrad}

einseitig = []
for spalte, anzeige in KONFORME_ATTRIBUTE:
    neu = grade.get("NEW", {}).get(spalte)
    verloren = grade.get("LOST", {}).get(spalte)
    if neu is None or verloren is None:
        continue
    if (neu < 0.05 and verloren >= 0.5) or (verloren < 0.05 and neu >= 0.5):
        leere_seite = "NEW" if neu < 0.05 else "LOST"
        einseitig.append(
            (spalte, anzeige, leere_seite, round(neu * 100, 1), round(verloren * 100, 1))
        )

check(
    "DQ-FCT-004", "ERROR",
    "Konformes Attribut nur fuer eine Geschaeftsart befuellt",
    spark.createDataFrame(
        einseitig,
        "spalte string, attribut string, leere_seite string, fuellgrad_new double, "
        "fuellgrad_lost double",
    ) if einseitig else spark.createDataFrame([], "spalte string"),
    "nb_20_gold pruefen: das Attribut fehlt in opp_base bzw. con_base. "
    "Ein Datenschnitt darauf wuerde nur eine Haelfte der Net-New-Rechnung filtern.",
)
if einseitig:
    for spalte, anzeige, seite, fn, fl in einseitig:
        print(f"       -> {anzeige} ({spalte}): NEW {fn} %, LOST {fl} % - leer auf {seite}")

# ---------------------------------------------------------------------------
# DQ-NEW-001  ITY-Wert ueber die ARO-Ersatzregel gebildet
# ---------------------------------------------------------------------------
# INFO, kein Fehler. cgplc_revenueity ist im CRM gegen das LAUFENDE
# Geschaeftsjahr gerechnet; bei Mobilisierung im Folgejahr steht dort
# systematisch 0. nb_20_gold setzt fuer diese Faelle ARO/12 als Monatsrate an
# (Abschnitt 5a, ITY_LEER_WEIL_FOLGEJAHR), sonst faellt das gesamte erste
# Vertragsjahr auf null.
#
# Diese Regel macht sichtbar, WIE VIEL Volumen ueber die Ersatzregel laeuft.
# Ein hoher Anteil ist normal, solange der Geschaeftsjahreswechsel bevorsteht -
# er sollte nach dem Wechsel aber deutlich zurueckgehen, weil CRM die
# ITY-Werte dann gegen das neue laufende Jahr fuehrt. Bleibt der Anteil hoch,
# ist cgplc_revenueity im CRM nicht nachgepflegt worden.
ersatz = fct.filter(
    (F.col("business_type") == "NEW")
    & (F.col("ity_quelle") == "ARO-Ersatz (Eroeffnung Folgejahr)")
) if "ity_quelle" in fct.columns else spark.createDataFrame([], "entity_id string")

check(
    "DQ-NEW-001", "INFO",
    "Perioden, deren ITY-Wert aus ARO/12 statt aus cgplc_revenueity stammt",
    ersatz,
    "Normal vor dem Geschaeftsjahreswechsel. Bleibt der Anteil danach hoch, "
    "cgplc_revenueity im CRM nachpflegen.",
)
if "ity_quelle" in fct.columns:
    betroffen = ersatz.select("entity_id").distinct().count()
    volumen = ersatz.agg(F.sum("amount_weighted")).collect()[0][0] or 0
    print(f"       -> {betroffen:,} Opportunities, {volumen:,.0f} EUR gewichtet")

# ---------------------------------------------------------------------------
# DQ-SIL-001  Grain der Silver-Schicht verletzt
# ---------------------------------------------------------------------------
# Silver ist die GEGENWART: genau ein Datensatz je Geschaeftsschluessel. Steht
# ein Schluessel mehrfach da, wurde die Bronze-Historie ungefiltert gelesen -
# bronze_* ist append-only, nach n Ladelaeufen also n Zeilen je Vorgang.
#
# Genau dieser Fehler ist aufgetreten und hat gold_fct_net_new_ity am zweiten
# Ladetag verdoppelt. Er war von aussen nicht erkennbar: Gold schreibt ein
# einheitliches snapshot_date = RUN_DATE, die doppelten Zeilen sehen also aus
# wie echte Daten. Keine der bisherigen Regeln konnte das fangen - DQ-SNP-001
# prueft die Bronze-Seite, wo die Dopplung fachlich RICHTIG ist.
#
# ERROR, nicht WARNING: jede Summe im Bericht waere um den Faktor n falsch.
for tabelle, schluessel in [
    ("silver_opportunity", "opportunityid"),
    ("silver_contract", "cgplc_cgcontractid"),
]:
    if not spark.catalog.tableExists(tabelle):
        continue
    mehrfach = (
        spark.table(tabelle).groupBy(schluessel).count().filter(F.col("count") > 1)
    )
    check(
        f"DQ-SIL-001-{schluessel}", "ERROR",
        f"{tabelle}: Schluessel {schluessel} kommt mehrfach vor "
        f"(Silver muss genau eine Zeile je Vorgang fuehren)",
        mehrfach,
        "nb_10_silver liest die Bronze-Tabelle ohne nur_letzter_snapshot() - "
        "ohne diesen Filter vervielfacht sich jede Summe mit der Zahl der "
        "bisherigen Ladelaeufe.",
    )

# ---------------------------------------------------------------------------
# DQ-SNP-001  Mehrere Ladelaeufe je Stichtag
# ---------------------------------------------------------------------------
# Waechter gegen den Fehler, den die Staging-Strecke verhindern soll: Wenn ein
# Dataflow-Append zweimal am selben Tag laeuft, stehen zwei Snapshots mit
# identischem snapshot_date in der Bronze-Tabelle und JEDE SUMME VERDOPPELT
# SICH - ohne Fehler, ohne Warnung, nur mit falschen Zahlen.
#
# Geprueft wird der Geschaeftsschluessel je Stichtag: er muss eindeutig sein.
for tabelle, schluessel in [
    ("bronze_crm_opportunity", "opportunityid"),
    ("bronze_crm_contract", "cgplc_cgcontractid"),
]:
    if not spark.catalog.tableExists(tabelle):
        continue
    doppelte = (
        spark.table(tabelle)
        .groupBy("snapshot_date", schluessel)
        .count()
        .filter(F.col("count") > 1)
    )
    check(
        f"DQ-SNP-001-{schluessel}", "ERROR",
        f"Doppelte Snapshot-Zeilen in {tabelle} (Grain snapshot_date + {schluessel})",
        doppelte,
        "nb_05_snapshot.py hat die Tagespartition nicht geloescht, oder der "
        "Dataflow schreibt mit Append statt Replace in die Staging-Tabelle.",
    )

# ---------------------------------------------------------------------------
# DQ-MAP-001  Vorgang ohne Zuordnung zu einem SAP-Betrieb
# ---------------------------------------------------------------------------
# Die Werk-Zuordnung laeuft ueber die Kette Ausnahme -> cgplc_sapid ->
# Mapping (Sektor/Subsektor) -> Mapping (Sektor). Greift keine Stufe, faellt
# der Vorgang in Auswertungen nach Region oder Management in die Leerzeile.
# Die Auswertung nach Sektor funktioniert weiterhin, weil der Sektor direkt
# am Vorgang haengt.
check(
    "DQ-MAP-001", "WARNING",
    "Vorgang ohne Zuordnung zu einem SAP-Betrieb (werk_zuordnung = Nicht zugeordnet)",
    fct.filter(F.col("sap_id").isNull()).select("entity_id").distinct(),
    "Sektor/Subsektor-Kombination in Mapping_Planwerke.xlsx ergaenzen "
    "(Spalten sektor, subsektor, Mapping Unit) oder Einzelfall ueber "
    "dim_opp_name[opportunityid] zuordnen.",
)

# ---------------------------------------------------------------------------
# DQ-MAP-002  Sektor/Subsektor-Kombination ohne Mapping-Zeile
# ---------------------------------------------------------------------------
# Aggregierte Sicht auf dieselbe Luecke: WELCHE Kombinationen fehlen in der
# Mapping-Tabelle? Eine Zeile je Kombination - das ist die Arbeitsliste fuer
# die Pflege von Mapping_Planwerke.xlsx, waehrend DQ-MAP-001 die betroffenen
# Vorgaenge zaehlt.
check(
    "DQ-MAP-002", "INFO",
    "Sektor/Subsektor-Kombination ohne Zeile in der Mapping-Tabelle",
    fct.filter(F.col("sap_id").isNull() & F.col("sector").isNotNull())
    .select("sector", "subsector").distinct(),
    "Fuer jede gelistete Kombination eine Zeile in Mapping_Planwerke.xlsx anlegen "
    "(sektor, subsektor, werk).",
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
