# Fabric notebook source
# ---------------------------------------------------------------------------
# nb_05_snapshot
# ---------------------------------------------------------------------------
# Staging -> historisierte Bronze-Tabellen. Idempotenter Tageslauf.
#
#   Dataflow Gen2 (Destination = REPLACE)  ->  stg_*
#   dieses Notebook (Append je Partition)  ->  bronze_*
#
# WARUM DER UMWEG UEBER STAGING
# Ein Dataflow-Append haengt bei jedem Lauf Zeilen an. Laeuft der Dataflow an
# einem Tag zweimal - Retry nach Timeout, manueller Refresh - stehen zwei
# Snapshots mit identischem snapshot_date in der Tabelle und JEDE SUMME
# VERDOPPELT SICH, ohne dass es auffaellt. Kein Fehler, keine Warnung, nur
# falsche Zahlen.
#
# Dieses Notebook loescht die Partition des Snapshot-Datums, bevor es
# schreibt. Der Tageslauf ist damit beliebig oft wiederholbar.
#
# Uebernommen aus der Vorarbeit (Branch claude/crm-report-rebuild-1bwcfg,
# fabric/lakehouse/02_load_snapshot.py) und auf die Tabellennamen dieses
# Repositories angepasst.
# ---------------------------------------------------------------------------

# MAGIC %run nb_00_config

from datetime import datetime
from zoneinfo import ZoneInfo

from pyspark.sql import functions as F
from delta.tables import DeltaTable

# --- Parameterzelle (im Notebook als "Parameter" markieren) ----------------
# Die Pipeline setzt diesen Wert. True nur fuer bewusste Nachladungen eines
# aelteren Standes von Hand.
allow_stale_snapshot = False

# Die Fabric-Kapazitaet laeuft in der Zeitzone der Gruppe (UK). Ohne diese
# Einstellung interpretiert und zeigt Spark alle TIMESTAMP-Werte in UK-Zeit;
# loaded_at laege im Winter eine, im Sommer zwei Stunden daneben. Betrifft
# Darstellung und Casting - aber genau darueber wird geprueft und gelesen.
spark.conf.set("spark.sql.session.timeZone", "Europe/Berlin")

# (Staging-Tabelle, Zieltabelle, Geschaeftsschluessel)
SNAPSHOT_TABELLEN = [
    ("stg_crm_opportunity", "bronze_crm_opportunity", "opportunityid"),
    ("stg_crm_contract", "bronze_crm_contract", "cgplc_cgcontractid"),
    ("stg_map_unit_assignment", "bronze_map_unit_assignment", None),
]


def lade_snapshot(staging: str, ziel: str, schluessel: str | None) -> None:
    src = spark.read.table(staging)

    # --- Grain-Pruefung 1: genau ein snapshot_date je Lauf -----------------
    # Die Dataflows werten den Zeitstempel einmal je Lauf aus. Zwei Werte
    # bedeuten, dass der Extrakt ueber Mitternacht lief oder zwei Laeufe
    # ineinandergeschrieben haben.
    datumswerte = [r[0] for r in src.select("snapshot_date").distinct().collect()]
    if len(datumswerte) != 1:
        raise ValueError(
            f"{staging}: erwartet genau ein snapshot_date, gefunden {datumswerte}"
        )
    snapshot_date = datumswerte[0]

    # --- Wächter gegen einen stehengebliebenen Staging-Stand ---------------
    # Der Dataflow schreibt mit Replace. Schlaegt er fehl, bleibt der Stand
    # des Vortags in der Staging-Tabelle stehen - fachlich unauffaellig, denn
    # der Load waere idempotent und wuerde die Vortagspartition einfach neu
    # schreiben. GENAU DAS ist die Gefahr: der Lauf meldet Erfolg, es entsteht
    # aber kein neuer Snapshot, und der Bericht zeigt alte Zahlen als aktuell.
    heute_berlin = datetime.now(ZoneInfo("Europe/Berlin")).date()
    if snapshot_date != heute_berlin and not allow_stale_snapshot:
        raise ValueError(
            f"{staging}: snapshot_date ist {snapshot_date}, erwartet {heute_berlin} "
            "(Berliner Zeit). Der Dataflow hat vermutlich nicht erfolgreich "
            "geschrieben. Fuer eine bewusste Nachladung allow_stale_snapshot=True setzen."
        )

    # --- Grain-Pruefung 2: Geschaeftsschluessel eindeutig ------------------
    if schluessel:
        doppelte = src.groupBy(schluessel).count().filter(F.col("count") > 1).count()
        if doppelte:
            raise ValueError(
                f"{staging}: {doppelte} doppelte Werte in {schluessel} - "
                "der Snapshot-Grain ist verletzt."
            )

    # --- Idempotentes Schreiben --------------------------------------------
    if spark.catalog.tableExists(ziel):
        DeltaTable.forName(spark, ziel).delete(
            F.col("snapshot_date") == F.lit(snapshot_date)
        )
        # Spaltenreihenfolge des Ziels erzwingen, damit ein neues Quellfeld
        # nicht stillschweigend in die falsche Spalte laeuft.
        vorhandene = spark.read.table(ziel).columns
        fehlend = [c for c in vorhandene if c not in src.columns]
        for c in fehlend:
            src = src.withColumn(c, F.lit(None))
        src = src.select(vorhandene)
        src.write.format("delta").mode("append").saveAsTable(ziel)
    else:
        (
            src.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .partitionBy("snapshot_date")
            .saveAsTable(ziel)
        )

    print(f"  {ziel}: {src.count():,} Zeilen fuer {snapshot_date}")


print(f"Snapshot-Lauf {datetime.now(ZoneInfo('Europe/Berlin'))}")
for staging, ziel, key in SNAPSHOT_TABELLEN:
    if spark.catalog.tableExists(staging):
        lade_snapshot(staging, ziel, key)
    else:
        print(f"  ! {staging} fehlt - uebersprungen")

# Lookup-Tabellen ohne Historienbedarf werden direkt ersetzt.
for staging, ziel in [
    ("stg_crm_account", "bronze_crm_account"),
    ("stg_crm_territory", "bronze_crm_territory"),
]:
    if spark.catalog.tableExists(staging):
        write_delta(spark.read.table(staging), ziel, mode="overwrite")

print("Snapshot-Schicht fertig.")
