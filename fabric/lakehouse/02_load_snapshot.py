"""
Fabric Notebook: taeglicher Snapshot-Load Staging -> historisierte Faktentabelle.

Ablauf der Pipeline:
    Dataflow Gen2 (Destination = Replace)  ->  stg_opportunity / stg_retention
    dieses Notebook (idempotenter Append)  ->  fct_opportunity / fct_retention

Warum Staging statt direktem Append aus dem Dataflow:
Ein Dataflow-Append haengt bei jedem Lauf Zeilen an. Laeuft der Dataflow an
einem Tag zweimal (Retry, manueller Refresh), stehen zwei Snapshots mit
identischem snapshot_date in der Tabelle und jede Summe verdoppelt sich.
Dieses Notebook loescht die Partition des Snapshot-Datums, bevor es schreibt -
der Tageslauf ist damit beliebig oft wiederholbar.
"""

from pyspark.sql import functions as F
from delta.tables import DeltaTable

# Die Fabric-Kapazitaet laeuft in der Zeitzone der Gruppe (UK). Ohne diese
# Einstellung interpretiert und zeigt Spark alle TIMESTAMP-Werte in UK-Zeit,
# loaded_at laege im Winter eine und im Sommer zwei Stunden daneben.
# Betrifft nur die Darstellung und das Casting - der gespeicherte Zeitpunkt
# ist davon unabhaengig -, aber genau darueber wird geprueft und gelesen.
spark.conf.set("spark.sql.session.timeZone", "Europe/Berlin")

SNAPSHOT_TABLES = [
    ("stg_opportunity", "fct_opportunity", "opportunityid"),
    ("stg_retention", "fct_retention", "cgplc_cgcontractid"),
    ("stg_opportunity_unit", "map_opportunity_unit", "opportunityid"),
]


def load_snapshot(staging_table: str, target_table: str, business_key: str) -> None:
    src = spark.read.table(staging_table)

    snapshot_dates = [r[0] for r in src.select("snapshot_date").distinct().collect()]
    if len(snapshot_dates) != 1:
        raise ValueError(
            f"{staging_table}: erwartet genau ein snapshot_date, gefunden {snapshot_dates}"
        )
    snapshot_date = snapshot_dates[0]

    duplicates = (
        src.groupBy(business_key).count().filter(F.col("count") > 1).count()
    )
    if duplicates:
        raise ValueError(
            f"{staging_table}: {duplicates} doppelte Werte in {business_key} - "
            "der Snapshot-Grain ist verletzt."
        )

    target = DeltaTable.forName(spark, target_table)
    target.delete(F.col("snapshot_date") == F.lit(snapshot_date))

    src.select(spark.read.table(target_table).columns).write.format("delta").mode(
        "append"
    ).saveAsTable(target_table)

    print(f"{target_table}: {src.count()} Zeilen fuer {snapshot_date} geschrieben.")


for staging, target, key in SNAPSHOT_TABLES:
    load_snapshot(staging, target, key)
