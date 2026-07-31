# Fabric notebook source
# ---------------------------------------------------------------------------
# nb_00_config
# ---------------------------------------------------------------------------
# Zentrale Konfiguration der Net-New-ITY-Pipeline.
#
# Dieses Notebook wird von nb_10_silver / nb_20_gold / nb_30_quality per
#   %run nb_00_config
# eingebunden. Es schreibt keine Tabellen, sondern stellt ausschliesslich
# Konstanten und Hilfsfunktionen bereit.
#
# WARUM ZENTRAL: In den Altmodellen lagen dieselben Stichtage als
# Power-Query-Parameter (Est_Close_Date_A/E, Est_Opening_Date_A/E,
# Geschaeftsjahresbeginn) in drei Modellen parallel und konnten auseinanderlaufen.
# Hier existieren sie genau einmal.
# ---------------------------------------------------------------------------

from datetime import date
from pyspark.sql import functions as F
from pyspark.sql import types as T

# ===========================================================================
# 0. Zeitzone
# ===========================================================================
# Die Fabric-Kapazitaet der Gruppe laeuft in UK-Zeit, der Power BI Service in
# UTC. Berlin liegt gegenueber UK durchgehend eine, gegenueber UTC je nach
# Sommerzeit ein bis zwei Stunden vorn.
#
# Ohne diese Einstellung interpretiert Spark alle TIMESTAMP-Werte in UK-Zeit.
# Kritisch ist das nicht wegen der Anzeige, sondern weil current_timestamp()
# den Stichtag jedes Ladelaufs bestimmt: ein Lauf zwischen 00:00 und 01:00
# Berliner Zeit bekaeme das Datum des Vortags, fiele in die Vortagspartition,
# ueberschriebe dort den echten Vortagsstand und loeschte einen Tag Historie
# aus den Bewegungstabellen. Bei einem Nachtplan oder einem Retry nach
# Mitternacht passiert das unbemerkt.
#
# Gegenstueck auf der Dataflow-Seite: dataflows/fn_berlin_now.m
spark.conf.set("spark.sql.session.timeZone", "Europe/Berlin")

# ===========================================================================
# 1. Geschaeftsjahr
# ===========================================================================
# Das Geschaeftsjahr der Gruppe laeuft vom 1. Oktober bis zum 30. September.
# Konvention (identisch zu SAP "Fiscal_Year" und zur Alt-DIM_DATE):
#   FY_YEAR = Kalenderjahr, in dem das Geschaeftsjahr BEGINNT.
#   FY2025 == "FY2025/26" == 01.10.2025 - 30.09.2026
#   FY_PERIOD 1 = Oktober ... FY_PERIOD 12 = September
FY_START_MONTH = 10

# Aktuelles Planungs-/Berichtsjahr (CY im Sinne der Group Guidance)
CURRENT_FY = 2025                      # = FY2025/26
PRIOR_FY = CURRENT_FY - 1              # = FY2024/25
NEXT_FY = CURRENT_FY + 1               # = FY2026/27

# Abgeleitete Stichtage. Ersetzen die vier PQ-Parameter der Altmodelle:
#   Est_Close_Date_A   -> CY_START
#   Est_Close_Date_E   -> CY_END
#   Est_Opening_Date_A -> NY_START
#   Est_Opening_Date_E -> NY_END
CY_START = date(CURRENT_FY, FY_START_MONTH, 1)          # 2025-10-01
CY_END = date(CURRENT_FY + 1, FY_START_MONTH - 1, 30)   # 2026-09-30
NY_START = date(NEXT_FY, FY_START_MONTH, 1)             # 2026-10-01
NY_END = date(NEXT_FY + 1, FY_START_MONTH - 1, 30)      # 2027-09-30

# Horizont des Perioden-Fanouts. Alles danach wird verworfen.
# Entspricht dem Cut-off #date(2027,9,30) aus fct_opp / fct_retention.
FANOUT_END = NY_END

# Geschaeftsjahr, auf das sich die gepflegte Budgetdatei bezieht - in der
# Konvention DIESES Repositories (Kalenderjahr des FY-BEGINNS).
#
# ACHTUNG, ZWEI KONVENTIONEN: Die Excel selbst traegt in ihrer Spalte
# "Geschäftsjahr" den Wert 2026 und bezeichnet damit dasselbe Jahr, das hier
# 2025 heisst. Der Beleg steht in der Datei: als "Neueroeffnung" gilt dort
# alles ab dem 01.10.2025, und das ist der erste Tag von FY2025/26.
# Die Altabfrage schrieb die 2026 als Konstante in den Datenstrom - genau die
# Sorte Jahreskonstante, die dieses Repository sonst abgeloest hat.
#
# BEI EINER NEUEN BUDGETRUNDE mit CURRENT_FY hochziehen bzw. auf das Jahr
# setzen, fuer das die Datei geplant ist. Ein falscher Wert faellt nicht als
# Fehler auf, sondern nur daran, dass Budget und CRM-Pipeline in verschiedenen
# Geschaeftsjahren liegen und die Budgetkennzahlen leer bleiben.
BUDGET_FY = CURRENT_FY

# ===========================================================================
# 1a. Aufbewahrung der Gold-Historie
# ===========================================================================
# gold_fct_net_new_ity wird je Ladelauf um einen vollstaendigen Tagesstand
# ERGAENZT statt ersetzt (siehe schreibe_snapshot). Nur so laesst sich im
# Bericht ein frueherer Stand der Pipeline abrufen.
#
# Unbegrenzt waechst die Tabelle allerdings linear mit den Tagen: der Fanout
# erzeugt je Vorgang bis zu 24 Monatszeilen, taeglich neu. Deshalb ein
# Aufbewahrungsfenster:
#   · die letzten GOLD_HISTORIE_TAGE Tage vollstaendig - das ist der Bereich,
#     in dem "wie sah die Pipeline letzte Woche aus?" gefragt wird;
#   · jeder Monatsletzte dauerhaft - Monatsstaende sind die Bezugspunkte, auf
#     die sich Abstimmungen und Budgetrunden spaeter berufen.
# Beides zusammen haelt die Tabelle in einer festen Groessenordnung, ohne die
# Vergleichspunkte zu verlieren, die tatsaechlich gebraucht werden.
GOLD_HISTORIE_TAGE = 90

# ===========================================================================
# 2. Fachliche Schwellen
# ===========================================================================
# Diese Werte definieren die DEFAULT-Buckets in der Gold-Schicht. Im Bericht
# koennen sie ueber What-if-Parameter uebersteuert werden (siehe
# docs/03_berechnungslogik.md, Abschnitt "Szenarien") - die Gold-Schicht
# liefert dafuer die Rohwahrscheinlichkeit mit.
WIN_THRESHOLD_EXPECTED = 0.80   # ab hier "Expected Win" (< 1.0)
WIN_THRESHOLD_WON = 1.00        # Win-% == 100 % -> "Won"
RETENTION_THRESHOLD_EXPECTED_LOSS = 0.20   # <= 20 % Retention -> "Expected Loss"
RETENTION_THRESHOLD_LOST = 0.00            # 0 % Retention -> "Lost"

# Sales-Stages, die keine belastbare Pipeline darstellen und ausgefiltert werden.
# Uebernommen aus fct_opp (CRM Call).
EXCLUDED_SALES_STAGES = ["Nobid", "Turndown/Lost", "Universe"]
EXCLUDED_STATE_NAMES = ["Verloren"]

# Nur aktive Vertraege gehen in die Retention-Betrachtung ein (aus fct_retention).
ACTIVE_CONTRACT_STATUS = ["Aktiv"]

# ===========================================================================
# 3. Betriebstypen (aus dim_sap_master_data_unit)
# ===========================================================================
# "Plan-Betriebe" sind Platzhalter-Kostenstellen, in denen unknown Business
# geplant wird. Sie duerfen nicht als reale Betriebe gezaehlt werden.
PLANBETRIEBE_ROLL = [
    127, 1678, 1680, 1682, 1684, 1686, 1688, 1690, 1692, 1694, 1696, 1862, 1863,
    2119, 4350, 4590, 5200, 5226, 7133, 7120, 7937, 8535, 8849, 9736, 9747,
    9876, 9937, 7905,
]
PLANBETRIEBE_ITY = [
    1679, 1681, 1683, 1685, 1687, 1689, 1691, 1693, 1695, 7933, 8385, 8386,
    9911, 9913, 9916, 9920, 9922, 9924, 9926, 9933, 9936, 9940, 9944, 9945,
    9946, 9947, 9950, 9952, 1860, 4408,
]

# ===========================================================================
# 4. Speicherorte
# ===========================================================================
LAKEHOUSE = "lakehouse_group_controlling"
BRONZE = "bronze"      # Tabellen-Praefix
SILVER = "silver"
GOLD = "gold"

# ===========================================================================
# 5. Hilfsfunktionen
# ===========================================================================


def add_fiscal_columns(df, date_col: str, prefix: str = ""):
    """Ergaenzt fy_year / fy_period / fy_label fuer eine Datumsspalte.

    FY_YEAR  = Kalenderjahr des FY-Beginns (Oktober-Regel)
    FY_PERIOD= 1 (Okt) .. 12 (Sep)
    FY_LABEL = "FY2025/26"

    Identisch zur Logik der Alt-DIM_DATE, aber genau einmal implementiert.
    """
    m = F.month(F.col(date_col))
    y = F.year(F.col(date_col))
    fy_year = F.when(m >= FY_START_MONTH, y).otherwise(y - 1)
    fy_period = F.when(m >= FY_START_MONTH, m - (FY_START_MONTH - 1)).otherwise(
        m + (12 - FY_START_MONTH + 1)
    )
    return (
        df.withColumn(f"{prefix}fy_year", fy_year.cast("int"))
        .withColumn(f"{prefix}fy_period", fy_period.cast("int"))
        # LINEARER Monatsindex. Unverzichtbar fuer die Szenario-Verschiebung:
        # fy_year*100 + fy_period ist NICHT linear (202512 -> 202601 = Sprung 89),
        # fy_year*12 + fy_period schon (24312 -> 24313 = Sprung 1). Damit wird
        # "verschiebe um n Monate" zu einer reinen Subtraktion in DAX.
        .withColumn(f"{prefix}monat_index", (fy_year * 12 + fy_period).cast("int"))
        .withColumn(
            f"{prefix}fy_label",
            F.concat(
                F.lit("FY"),
                fy_year.cast("string"),
                F.lit("/"),
                F.substring((fy_year + 1).cast("string"), 3, 2),
            ),
        )
    )


def first_fy_end(date_col):
    """Ende des ERSTEN Geschaeftsjahres, in das ein Ereignis faellt.

    Uebernimmt exakt die Formel aus fct_opp / fct_retention:
        #date(Date.Year(Date.AddMonths(d, -9)) + 1, 9, 30)

    Warum das funktioniert: 9 Monate zurueck verschiebt Oktober..Dezember ins
    Vorjahr; +1 Jahr und der 30.09. liefern dann das Ende des FY, in dem d liegt.
        d = 2026-01-15 -> 2025-04-15 -> 2025+1 -> 2026-09-30  (FY2025/26) OK
        d = 2025-11-01 -> 2025-02-01 -> 2025+1 -> 2026-09-30  (FY2025/26) OK
        d = 2025-09-01 -> 2024-12-01 -> 2024+1 -> 2025-09-30  (FY2024/25) OK
    """
    shifted = F.add_months(date_col, -9)
    return F.make_date(F.year(shifted) + 1, F.lit(9), F.lit(30))


def month_start(date_col):
    """Erster Tag des Monats - Normalform aller Periodenschluessel."""
    return F.trunc(date_col, "MM")


def months_between_inclusive(start_col, end_col):
    """Anzahl Monate von start bis end EINSCHLIESSLICH beider Randmonate.

    Entspricht der M-Formel
        (Year(e)-Year(s))*12 + Month(e) - Month(s) + 1
    """
    return (
        (F.year(end_col) - F.year(start_col)) * 12
        + F.month(end_col)
        - F.month(start_col)
        + 1
    ).cast("int")


def spalte_oder_null(df, name: str, typ: str = "string"):
    """Liefert die Spalte, falls vorhanden - sonst eine typisierte NULL-Spalte.

    WARUM: Ein Teil der CRM-Felder ist kundenspezifisch (cgplc_-Praefix) und im
    Mandanten nicht garantiert vorhanden - siehe docs/04_crm_feldkatalog.md,
    Kennzeichen [C]. Der Dataflow ueberspringt fehlende Felder bereits per
    SafeSelect; ohne dieses Gegenstueck wuerde das Notebook trotzdem mit
    AnalysisException abbrechen, sobald es eine dieser Spalten anfasst.

    So degradiert der Ladelauf stattdessen: das Attribut ist leer, die Kennzahl
    stimmt weiterhin.
    """
    return F.col(name).cast(typ) if name in df.columns else F.lit(None).cast(typ)


def nur_letzter_snapshot(df, quelle: str = ""):
    """Reduziert eine historisierte Bronze-Tabelle auf den juengsten Stichtag.

    WARUM DAS ZWINGEND NOETIG IST
    Die bronze_*-Tabellen sind append-only: nb_05_snapshot haengt je Ladelauf
    einen vollstaendigen Tagesstand an. Nach n Laeufen steht JEDE Opportunity
    n-mal in der Tabelle. Wer sie ohne Filter liest, bekommt keinen Fehler,
    sondern das n-Fache jeder Summe - am zweiten Tag also exakt das Doppelte.

    Genau dieser Fehler ist aufgetreten: silver_opportunity und
    silver_contract lasen die volle Historie, und ab dem zweiten Ladelauf
    verdoppelte sich gold_fct_net_new_ity. Auffallen konnte es nicht, weil
    Gold seinerseits ein einheitliches snapshot_date = RUN_DATE schreibt - die
    Dopplung entsteht eine Schicht frueher und ist im Ergebnis nicht mehr von
    echten Daten zu unterscheiden.

    ARBEITSTEILUNG DER SCHICHTEN
      bronze_*  Historie. Jeder Tagesstand bleibt erhalten.
      silver_*  GEGENWART. Genau ein Datensatz je Geschaeftsschluessel.
      *_history Veraenderung. Wird aus den Silver-Snapshots aufgebaut
                (append_history), nicht aus der Bronze-Historie gelesen.
    Diese Funktion ist die Grenze zwischen der ersten und der zweiten Zeile.
    """
    if "snapshot_date" not in df.columns:
        # bronze_sap_* werden bewusst nicht historisiert (Ersetzen je Lauf).
        return df

    letzter = df.agg(F.max("snapshot_date")).collect()[0][0]
    gefiltert = df.filter(F.col("snapshot_date") == F.lit(letzter))
    if quelle:
        print(f"  {quelle}: Stand {letzter}")
    return gefiltert


def ergaenze_spalten(df, spalten: dict, quelle: str = ""):
    """Ergaenzt fehlende OPTIONALE Spalten als typisierte NULL-Spalten.

    WARUM: spalte_oder_null() schuetzt nur die eine Stelle, an der es
    aufgerufen wird. Sobald irgendwo sonst ein direktes F.col(...) auf ein im
    Mandanten fehlendes cgplc_-Feld trifft, bricht der Lauf trotzdem mit
    AnalysisException ab - genau so geschehen bei cgplc_sapid auf
    bronze_crm_account. Diese Funktion setzt EINMAL direkt nach dem Lesen der
    Bronze-Tabelle alle erwarteten Spalten, danach ist jeder nachfolgende
    Zugriff sicher.

    Ergaenzt wird ausschliesslich; vorhandene Spalten bleiben unveraendert.
    """
    fehlend = {n: t for n, t in spalten.items() if n not in df.columns}
    for name, typ in fehlend.items():
        df = df.withColumn(name, F.lit(None).cast(typ))
    if fehlend:
        print(
            f"  HINWEIS {quelle}: {len(fehlend)} Feld(er) im Mandanten nicht "
            f"vorhanden, als NULL ergaenzt -> {', '.join(sorted(fehlend))}"
        )
    return df


def pruefe_pflichtfelder(df, quelle: str, felder: list):
    """Bricht ab, wenn ein Schluessel- oder Treiberfeld fehlt.

    Abgrenzung zu ergaenze_spalten(): ein fehlendes ATTRIBUT (Kundenname,
    Sektor, Gebiet) laesst die Kennzahl richtig und nur die Aufrisssicht leer -
    das darf still durchlaufen. Ein fehlendes TREIBERFELD (Datum, Betrag,
    Wahrscheinlichkeit) oder ein fehlender Schluessel macht die Berechnung
    dagegen bedeutungslos: der Bericht zeigte dann lauter Nullen, ohne dass
    irgendwo ein Fehler sichtbar waere. Deshalb hier lieber laut abbrechen.
    """
    fehlend = [f for f in felder if f not in df.columns]
    if fehlend:
        raise ValueError(
            f"{quelle}: Pflichtfeld(er) fehlen: {', '.join(fehlend)}.\n"
            f"Ohne diese Felder ist die Periodenverteilung bedeutungslos.\n"
            f"Pruefen: SELECT DISTINCT _fehlende_felder FROM {quelle} "
            f"WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM {quelle});\n"
            f"Feldherkunft und Alternativen: docs/04_crm_feldkatalog.md"
        )


def nicht_in(df, spalte: str, werte):
    """NULL-sicherer Ausschlussfilter.

    ~F.col(x).isin(...) liefert bei NULL ebenfalls NULL, und NULL filtert die
    Zeile WEG. Fehlt das Feld im Mandanten komplett (alle Werte NULL), wuerde
    ein gewoehnlicher Ausschlussfilter also den gesamten Datenbestand
    verwerfen - ohne Fehlermeldung, mit leerem Bericht als Ergebnis. Unbekannt
    heisst hier deshalb ausdruecklich "nicht ausgeschlossen".
    """
    return F.coalesce(~spalte_oder_null(df, spalte).isin(werte), F.lit(True))


def name_oder_id(df, spalte: str):
    """Anzeigename eines Dataverse-Lookup-/Optionset-Felds, ersatzweise die ID.

    Der TDS-Endpunkt (CommonDataService.Database) liefert fuer jedes
    Lookup-Feld foo ZWEI Spalten: foo (GUID) und fooname (Anzeigename);
    analog fuer Optionsets (Code + Klartext). Fuer Anzeige, Filter und das
    Sektor-Mapping ist der NAME massgeblich - eine GUID im Slicer ist
    unlesbar, und die Mapping-Tabelle des Controllings ist ueber Namen
    geschluesselt. Die GUID bleibt, wo sie hingehoert: als Join-Schluessel.

    Faellt sauber zurueck, wenn die Namensspalte im Mandanten fehlt.
    """
    name_col = f"{spalte}name"
    hat_name = name_col in df.columns
    hat_id = spalte in df.columns
    if hat_name and hat_id:
        return F.coalesce(F.col(name_col), F.col(spalte).cast("string"))
    if hat_name:
        return F.col(name_col)
    return spalte_oder_null(df, spalte)


def write_delta(df, table_name: str, mode: str = "overwrite", partition_by=None):
    """Einheitlicher Schreibpfad mit Schema-Evolution."""
    writer = (
        df.write.format("delta")
        .mode(mode)
        .option("overwriteSchema", "true" if mode == "overwrite" else "false")
        .option("mergeSchema", "true" if mode == "append" else "false")
    )
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.saveAsTable(table_name)
    print(f"  -> {table_name}: {df.count():,} Zeilen ({mode})")


def schreibe_snapshot(df, table_name: str, snapshot_date, partition_by=None,
                      behalte_tage: int | None = None):
    """Haengt einen Tagesstand an eine historisierte GOLD-Tabelle an.

    WOZU
    Eine mit overwrite geschriebene Gold-Tabelle kennt nur den heutigen Stand.
    Die Frage "wie sah die Pipeline am 12. des Monats aus?" ist damit nicht
    beantwortbar - die Bronze-Historie enthaelt zwar die CRM-Rohstaende, aber
    nicht das, was der Bericht daraus rechnet. Genau diese Rueckschau braucht
    der Bericht, deshalb liegt die Historie hier und nicht nur eine Schicht
    tiefer.

    IDEMPOTENZ
    Wie nb_05_snapshot: die Partition des Stichtags wird geloescht, bevor
    geschrieben wird. Ein zweiter Lauf am selben Tag ersetzt den Tagesstand,
    statt ihn ein zweites Mal anzuhaengen - sonst verdoppelte sich jede Summe
    dieses Tages, ohne dass irgendwo ein Fehler entstuende.

    LESEREGEL FUER ALLE NACHGELAGERTEN SCHICHTEN
    Ab hier gilt fuer diese Tabelle dasselbe wie fuer bronze_*: wer sie ohne
    Stichtagsfilter summiert, bekommt die Summe ALLER Staende. Im Notebook
    uebernimmt das nur_letzter_snapshot(), im Semantikmodell die Kennzahl
    [Net New ITY (brutto)] ueber 'DIM Stichtag'.
    """
    from delta.tables import DeltaTable

    df = df.withColumn("snapshot_date", F.lit(snapshot_date))

    if spark.catalog.tableExists(table_name):
        DeltaTable.forName(spark, table_name).delete(
            F.col("snapshot_date") == F.lit(snapshot_date)
        )
        write_delta(df, table_name, mode="append")
    else:
        write_delta(df, table_name, mode="overwrite",
                    partition_by=partition_by or ["snapshot_date"])

    if behalte_tage is not None:
        beschneide_historie(table_name, behalte_tage)


def beschneide_historie(table_name: str, behalte_tage: int):
    """Loescht alte Tagesstaende, behaelt aber jeden Monatsletzten dauerhaft.

    Begruendung des Fensters siehe GOLD_HISTORIE_TAGE. Der Monatsletzte wird
    ueber last_day() bestimmt, nicht ueber "der juengste Stand des Monats":
    faellt ein Ladelauf am Monatsende aus, soll die Luecke sichtbar bleiben
    und nicht durch einen zufaellig aelteren Stand kaschiert werden, der dann
    dauerhaft als Monatsstand gilt.
    """
    from delta.tables import DeltaTable

    if not spark.catalog.tableExists(table_name):
        return

    tabelle = DeltaTable.forName(spark, table_name)
    grenze = F.date_sub(F.current_date(), behalte_tage)
    veraltet = (F.col("snapshot_date") < grenze) & (
        F.col("snapshot_date") != F.last_day(F.col("snapshot_date"))
    )
    vorher = spark.table(table_name).select("snapshot_date").distinct().count()
    tabelle.delete(veraltet)
    nachher = spark.table(table_name).select("snapshot_date").distinct().count()
    if vorher != nachher:
        print(
            f"  {table_name}: {vorher - nachher} Tagesstand/-staende aelter als "
            f"{behalte_tage} Tage entfernt, {nachher} verbleiben"
        )


def fy_period_to_date(fy_year_col, fy_period_col):
    """FY-Jahr + FY-Periode -> erster Tag des Kalendermonats.

    Umkehrung von add_fiscal_columns: P1 = Oktober des FY-Jahres, P4 = Januar
    des Folgejahres. Steht hier, weil sowohl die SAP-Umsaetze (nb_20_gold,
    Abschnitt 5c) als auch die Budgetdatei (Abschnitt 5e) ihre Perioden als
    Nummer 1-12 fuehren und beide denselben Datumsbezug brauchen.
    """
    return F.make_date(
        F.when(fy_period_col <= 3, fy_year_col).otherwise(fy_year_col + 1),
        F.when(fy_period_col <= 3, fy_period_col + 9).otherwise(fy_period_col - 3),
        F.lit(1),
    )


# Wird von den abhaengigen Notebooks geprueft. BEI JEDER AENDERUNG AN DEN
# HILFSFUNKTIONEN HOCHZAEHLEN - dann meldet ein veraltetes nb_00_config in
# Fabric sich selbst, statt die abhaengigen Notebooks mitten im Lauf mit
# einem NameError auf eine noch unbekannte Funktion abbrechen zu lassen.
CONFIG_VERSION = 4

print(
    f"Konfiguration geladen (v{CONFIG_VERSION}) | "
    f"CY = FY{CURRENT_FY}/{str(CURRENT_FY + 1)[2:]} "
    f"({CY_START} - {CY_END}) | Fanout-Ende {FANOUT_END} | "
    f"Budgetjahr FY{BUDGET_FY}/{str(BUDGET_FY + 1)[2:]} | "
    f"Gold-Historie {GOLD_HISTORIE_TAGE} Tage + Monatsletzte"
)
