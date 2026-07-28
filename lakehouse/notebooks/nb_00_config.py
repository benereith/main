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


print(
    f"Konfiguration geladen | CY = FY{CURRENT_FY}/{str(CURRENT_FY + 1)[2:]} "
    f"({CY_START} - {CY_END}) | Fanout-Ende {FANOUT_END}"
)
