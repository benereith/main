# CRM Reporting - Zielarchitektur

Ablösung des direkten CRM-Calls aus dem Power-BI-Report "Net New Budget"
durch eine historisierte Lakehouse-Strecke.

## Warum der Umbau

Der Altstand ruft bei jedem Refresh Dataverse direkt ab
(`CommonDataService.Database("cpgplc.crm.dynamics.com", …)`) und erledigt in
Power Query gleichzeitig die gesamte Fachlogik: Filterung, Gewichtung,
ITY-Monatsphasierung per `List.Generate` und einen Live-Join gegen eine
SharePoint-Excel. Jede Opportunity wird dabei in bis zu 24 Monatszeilen
expandiert, bevor überhaupt eine Zahl im Report steht.

Drei Konsequenzen:

- Refreshdauer und CRM-Last steigen mit jedem Reportlauf.
- Es gibt keinen Zeitverlauf. Der Report kennt nur den Stand von jetzt.
- Die Filter (`statecodename <> "Verloren"`, Stage-Ausschlüsse, Datumsfenster)
  werfen genau die Datensätze weg, aus denen sich Frühindikatoren ableiten
  ließen.

## Zielbild

```
Dataverse (Dynamics CRM)
      │  täglich, Vollextrakt ohne Filter
      ▼
Dataflow Gen2 ──► stg_opportunity / stg_retention   (Replace)
      │
      ▼  Notebook, idempotent
Lakehouse ──► fct_opportunity / fct_retention       (Append, partitioniert)
      │           │
      │           ├─► vw_*_current   → Ist-Stand
      │           └─► vw_*_changes   → Änderungshistorie
      ▼
Semantic Model (Direct Lake)
      │  ITY-Phasing + Dimensionen als DAX
      ▼
Report + Leading KPIs
```

## Grundsatzentscheidungen

### Vollextrakt statt gefiltertem Abzug

Der Dataflow zieht **alle** Opportunities und **alle** Contracts, unabhängig
von Status, Sales Stage und Datum. Die fachlichen Einschränkungen des
Altmodells wandern in die DAX-Phasingtabellen, wo sie nur die Budgetwirkung
begrenzen — nicht den Datenbestand.

Damit werden Auswertungen möglich, die vorher strukturell ausgeschlossen
waren: Win Rate braucht die verlorenen Opportunities, Stage-Bewegungen
brauchen die Datensätze auch nach dem Ausscheiden, und ein Datensatz, der
heute aus dem Filter fällt, bleibt im Zeitverlauf sichtbar.

### Historisierung als täglicher Vollsnapshot

Jede Zeile trägt ein `snapshot_date`, die Delta-Tabelle ist danach
partitioniert. Ein Tageslauf ist ein vollständiges Abbild des CRM.

Vollsnapshot statt SCD2, weil er einfach zu betreiben und zu prüfen ist:
eine Partition pro Tag, kein Merge-Zustand, jede historische Auswertung ist
ein simpler Filter. Der Speicherbedarf ist bei diesen Mengengerüsten
unkritisch — Delta komprimiert die weitgehend identischen Tagesstände stark.

Die Auswertung läuft trotzdem nicht gegen die volle Historie: die
`vw_*_changes`-Views verdichten sie auf die Snapshots, in denen sich fachlich
etwas geändert hat. Das ist die Datenbasis der Leading KPIs.

### Idempotenz über Staging

Der Dataflow schreibt mit **Replace** in `stg_*`, das Notebook übernimmt
mit **Append** nach `fct_*` und löscht vorher die Partition des jeweiligen
Snapshot-Datums.

Grund: Ein Dataflow-Append hängt bei jedem Lauf Zeilen an. Läuft er an einem
Tag zweimal — Retry nach Timeout, manueller Refresh — stehen zwei Snapshots
mit identischem `snapshot_date` in der Tabelle und jede Summe verdoppelt sich,
ohne dass es auffällt. Der Umweg über Staging macht den Tageslauf beliebig
wiederholbar.

### Keine Dimensionen im Lakehouse

Das Lakehouse hält ausschließlich die zwei Faktentabellen. Die elf `dim_opp_*`
Tabellen des Altmodells waren eigene CRM-Abfragen auf dieselben Entities und
sind als `DISTINCT`-Ableitungen aus den Fakten vollständig ersetzbar
(`02_calculated_columns.dax`). Der Dataflow bleibt damit der einzige
Kontaktpunkt zum CRM.

### ITY-Logik im Semantic Model

Die Monatsphasierung liegt in `fct_opp_phasing` und `fct_retention_phasing`
(`01_ity_phasing.dax`) und bildet die Power-Query-Logik fachlich unverändert
ab, inklusive Vorzeichenkonvention: ITY-Phase negativ, ARO-Phase positiv,
Retention durchgängig negativ.

Zwei Dinge ändern sich bewusst:

- **Kein hart codierter Cutoff mehr.** Horizont und ITY-Grenze leiten sich aus
  `dim_date` ab. Im Altmodell standen `#date(2027, 9, 30)` und die Parameter
  `Est_Close_Date_*` an fünf Stellen verteilt; der Betrachtungszeitraum wird
  jetzt an genau einer Stelle gepflegt.
- **Keine Row-Explosion im Ladeprozess.** Der Extrakt bleibt bei einer Zeile
  je Opportunity, die Expansion passiert erst im Modell.

### Auto-Date/Time aus

Das Altmodell trägt 13 `LocalDateTable_*` Tabellen, erzeugt durch
Auto-Date/Time auf jeder Datumsspalte. Mit `dim_date` als einziger
Datumstabelle entfallen sie.

## Offene Punkte vor dem Bau

- **`dim_opp_mapping`** (SharePoint-Excel `Mapping_Planwerke.xlsx`, Spalte
  `Mapping Unit`) ist im Altmodell in `fct_opp` hineingejoint. Als
  Mapping-Tabelle gehört sie nicht in die Faktenstrecke — Vorschlag: eigener
  Dataflow in eine Lakehouse-Tabelle `map_opportunity_unit`, Beziehung im
  Semantic Model statt Join im Ladeprozess. Zu klären: Pflegeprozess und
  Aktualisierungsfrequenz.
- **`Revenues` / `SAP_Stammdaten`** (Quelle des `90_Value`-Measures und des
  Abgleichs SAP gegen CRM) bleiben vorerst unangetastet. Wenn `Pipeline
  Coverage` produktiv gehen soll, muss geklärt sein, ob `90_Value` in
  derselben Granularität und Währung vorliegt.
- **Startzeit des Dataflows** so legen, dass er vor dem
  Direct-Lake-Zugriff der ersten Nutzer durch ist.
- **Aufbewahrungsdauer** der Snapshots: unbegrenzt oder rollierend
  (z. B. 24 Monate täglich, davor monatlich verdichtet).

## Dateien

| Pfad | Zweck |
|---|---|
| `fabric/dataflow/fct_opportunity.m` | Dataflow-Gen2-Query, Vollextrakt Opportunities |
| `fabric/dataflow/fct_retention.m` | Dataflow-Gen2-Query, Vollextrakt Contracts |
| `fabric/lakehouse/01_create_tables.sql` | Delta-Tabellen, partitioniert nach `snapshot_date` |
| `fabric/lakehouse/02_load_snapshot.py` | Idempotenter Tageslauf Staging → Fakt |
| `fabric/lakehouse/03_views.sql` | Ist-Stand- und Änderungsviews |
| `fabric/semantic-model/01_ity_phasing.dax` | ITY-Monatsphasierung als berechnete Tabellen |
| `fabric/semantic-model/02_calculated_columns.dax` | Klassifizierungen und abgeleitete Dimensionen |
| `fabric/semantic-model/03_measures.dax` | Bestandsmeasures und Leading KPIs |

## Leading KPIs

Die Kennzahlen, die erst durch Historisierung und Vollextrakt möglich werden:

| KPI | Aussage | Voraussetzung |
|---|---|---|
| Pipeline Coverage | Deckt die gewichtete Pipeline den Plan? | — |
| Net New Pipeline (30d) | Wächst die Pipeline nach? | Historisierung |
| Pipeline Value Movement | Organisches Wachstum oder nachträgliche Abwertung? | Historisierung |
| Stage Movements | Bewegt sich die Pipeline überhaupt? | Historisierung |
| Close Date Slippage | Werden Abschlüsse systematisch verschoben? | Historisierung |
| Stale Pipeline ARO | Volumen ohne Fortschritt seit 90 Tagen | Historisierung |
| Win Rate (Wert/Anzahl) | Qualität der Pipeline | Vollextrakt |
| Avg Sales Cycle | Wie lange dauert ein Abschluss? | Vollextrakt |
| At Risk Share | Anteil gefährdeter Bestandsumsätze | — |
| Decisions Due 90d | Operativer Handlungsbedarf | — |
| Retention Probability Movement | Verschlechtert sich die Einschätzung? | Historisierung |
