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

# --- Parameterzelle (im Notebook als "Parameter" markieren) --------------
# Die Pipeline setzt diesen Wert. True nur fuer bewusste Nachladungen eines
# aelteren Standes von Hand.
allow_stale_snapshot = False

from datetime import datetime
from zoneinfo import ZoneInfo

from pyspark.sql import functions as F
from delta.tables import DeltaTable

# Die Fabric-Kapazitaet laeuft in der Zeitzone der Gruppe (UK). Ohne diese
# Einstellung interpretiert und zeigt Spark alle TIMESTAMP-Werte in UK-Zeit,
# loaded_at laege im Winter eine und im Sommer zwei Stunden daneben.
# Betrifft nur die Darstellung und das Casting - der gespeicherte Zeitpunkt
# ist davon unabhaengig -, aber genau darueber wird geprueft und gelesen.
spark.conf.set("spark.sql.session.timeZone", "Europe/Berlin")

# Lookups, die als Klartextnamen in die Opportunity-Zeile wandern.
# (Staging-Tabelle, ID-Spalte in fct_opportunity, Zielspalte)
#
# Der Join passiert HIER und nicht in der abgeleiteten Schicht: nur so
# steht der Name in der historisierten Zeile. Ein Join erst in
# 03_derived_tables.sql wuerde die heutigen Namen rueckwirkend ueber die
# gesamte Historie legen und den Snapshot entwerten.
LOOKUPS = [
    ("stg_lkp_owner",           "ownerid",                  "owner_name"),
    ("stg_lkp_account",         "accountid",                "account_name"),
    ("stg_lkp_account",         "parentaccountid",          "parent_account_name"),
    ("stg_lkp_territory",       "cgplc_territoryid",        "territory"),
    ("stg_lkp_sector",          "cgplc_sectorlookup",       "sector"),
    ("stg_lkp_subsector",       "cgplc_subsector",          "subsector"),
    ("stg_lkp_contracttype",    "cgplc_contracttypelookup", "contracttype"),
    ("stg_lkp_currentsupplier", "cgplc_currentsupplier",    "currentsupplier"),
    ("stg_lkp_contract",        "cgplc_contractid",         "contract_name"),
]

SNAPSHOT_TABLES = [
    ("stg_opportunity", "fct_opportunity", "opportunityid"),
    ("stg_retention", "fct_retention", "cgplc_cgcontractid"),
    ("stg_opportunity_unit", "map_opportunity_unit", "opportunityid"),
]


def mit_namen(src):
    """Loest die Lookup-IDs gegen die stg_lkp_*-Tabellen auf.

    LEFT JOIN, damit eine fehlende Zuordnung die Zeile nicht verliert -
    ein unaufgeloester Name ist ein Datenqualitaetsthema, kein Grund,
    die Opportunity aus dem Snapshot zu werfen.
    """
    for staging, id_spalte, ziel in LOOKUPS:
        lkp = (
            spark.read.table(staging)
            .select(F.col("Id").alias("_lkp_id"), F.col("Name").alias(ziel))
            .dropDuplicates(["_lkp_id"])
        )
        src = src.join(lkp, src[id_spalte] == lkp["_lkp_id"], "left").drop("_lkp_id")
    return src


def load_snapshot(staging_table: str, target_table: str, business_key: str) -> None:
    src = spark.read.table(staging_table)
    if target_table == "fct_opportunity":
        src = mit_namen(src)

    snapshot_dates = [r[0] for r in src.select("snapshot_date").distinct().collect()]
    if len(snapshot_dates) != 1:
        raise ValueError(
            f"{staging_table}: erwartet genau ein snapshot_date, gefunden {snapshot_dates}"
        )
    snapshot_date = snapshot_dates[0]

    # Der Dataflow schreibt mit Replace. Schlaegt er fehl, bleibt der Stand
    # des Vortags in der Staging-Tabelle stehen - fachlich unauffaellig, denn
    # der Load waere idempotent und wuerde die Vortagspartition einfach neu
    # schreiben. Genau das ist die Gefahr: der Lauf meldet Erfolg, es
    # entsteht aber kein neuer Snapshot, und der Bericht zeigt alte Zahlen
    # als aktuell. Deshalb hier hart pruefen statt sich auf die
    # Abhaengigkeit in der Pipeline allein zu verlassen.
    heute_berlin = datetime.now(ZoneInfo("Europe/Berlin")).date()
    if snapshot_date != heute_berlin and not allow_stale_snapshot:
        raise ValueError(
            f"{staging_table}: snapshot_date ist {snapshot_date}, erwartet "
            f"{heute_berlin} (Berliner Zeit). Der Dataflow hat vermutlich nicht "
            "erfolgreich geschrieben. Fuer eine bewusste Nachladung "
            "allow_stale_snapshot=True setzen."
        )

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
