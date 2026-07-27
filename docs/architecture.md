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

### Harmonisierung erst auf Effektebene

Opportunities und Retention-Contracts werden **nicht** zu einer Quelltabelle
zusammengeführt. Es sind unterschiedliche Geschäftsobjekte mit fast disjunkten
Attributen — Sales Stage, Win-%, Sektor, Territory auf der einen Seite,
Retention-Wahrscheinlichkeit, Vertragsende, Entscheidungsdatum, SAP-ID auf der
anderen. Ein Union daraus wäre eine breite Tabelle mit hälftig leeren Zeilen,
die Änderungsverfolgung müsste je Typ andere Felder vergleichen, und die
Leading KPIs sind ohnehin typspezifisch.

Zusammengeführt wird dort, wo die Semantik tatsächlich konvergiert: bei der
Budgetwirkung. `fct_budget_effect` vereinigt die beiden Phasing-Tabellen auf
ihrer gemeinsamen Achse **Periode × SAP-Betrieb**, mit `effect_type` als
Diskriminator. Da die Vorzeichen bereits im Phasing gesetzt sind, ist
`SUM(Budget_Value)` unmittelbar der Nettoeffekt; New Business und Retention
sind Filter auf derselben Tabelle statt zweier separater Measures.

Diese Achse ist keine Neuerfindung — das Altmodell verknüpft beide Fakten
bereits über `dim_sap_master_data_unit.betrieb` (Retention direkt über
`cgplc_sapid`, Opportunities über `Mapping Unit` aus der SharePoint-Excel) und
über `Period_Date` mit `dim_date`. Die neue Struktur macht diese vorhandene
Konformität nur explizit.

### Das manuelle Mapping ist strukturell notwendig

`map_opportunity_unit` lässt sich **nicht** durch CRM-Daten ersetzen. Die
Zuordnung wird im Budget- und Forecast-Prozess von Hand gepflegt, weil die
betroffenen Units noch nicht gewonnen sind — es gibt für sie weder einen
Vertrag im CRM noch einen Betrieb in den SAP-Stammdaten. Das Mapping trägt
eine vorausschauende Annahme, die in keinem Quellsystem steht.

Daraus folgen drei Dinge für das Modell:

- **Die Mappingtabelle wird historisiert**, wie die Fakten. Sie ist ein
  manueller Input in offizielle Budgetzahlen; ohne Snapshot ließe sich eine
  abgeschlossene Budgetrunde nach der nächsten Pflegerunde nicht mehr
  reproduzieren.
- **`dim_unit` vereinigt SAP-Stammdaten mit den nur im Mapping vorkommenden
  Units** und unterscheidet sie über `unit_status` (`In Betrieb` / `Geplant`).
  Eine Dimension allein aus den SAP-Stammdaten würde genau die geplanten Units
  in die Blank-Zeile fallen lassen — also den Teil, um den es im Net New Budget
  geht. `Planned Unit Effect` macht diesen Anteil direkt sichtbar.
- **Der Pflegestand wird messbar.** `Unmapped Effect`, `Unmapped
  Opportunities` und `Unmapped Share` zeigen, welches Volumen noch keinem
  Betrieb zugeordnet ist, solange eine Runde offen ist.

Die CRM-eigene Brücke über `cgplc_contractid` → `cgplc_sapid` bleibt als
Rückfallebene hinter dem Mapping. Sie greift für Opportunities, die einen
bestehenden Vertrag betreffen (Neuausschreibung eines laufenden Objekts), und
schließt dort Lücken — sie ersetzt das Mapping aber nicht, weil sie für echte
Net-New-Units definitionsgemäß leer läuft.

### Sektor über beide Effektarten

`dim_sap_master_data_unit` trägt `sektor` und `bezeichnung_bezirk`. Die
Retention erbt den Sektor darüber (`fct_retention[sektor]`), auf der
Opportunity-Seite kommt er aus dem CRM. Der Nettoeffekt ist damit nach Sektor
schneidbar, solange die Unit in SAP existiert. Für geplante Units bleibt der
Sektor leer — falls das im Report stört, müsste die Mappingdatei eine
Sektor-Spalte mitführen.

### Zeitzone: alles auf Europe/Berlin

Die Fabric-Kapazität der Gruppe läuft in UK-Zeit, `TODAY()`/`NOW()` im Power
BI Service laufen in UTC. Berlin liegt gegenüber UK durchgehend eine Stunde,
gegenüber UTC je nach Sommerzeit ein bis zwei Stunden vorn. Alle Zeitstempel
werden deshalb explizit auf Berlin gerechnet:

| Stelle | Vorher | Jetzt |
|---|---|---|
| `snapshot_date` (3 Dataflow-Queries) | `DateTimeZone.FixedLocalNow()` → UK | `fn_berlin_now()` |
| `loaded_at` (3 Dataflow-Queries) | `DateTimeZone.FixedUtcNow()` → UTC | `fn_berlin_now()`, mit Versatz gespeichert |
| Lakehouse-Notebook | Session-Zeitzone der Kapazität | `spark.sql.session.timeZone = Europe/Berlin` |
| `days_to_decision` | `TODAY()` → UTC | Berliner Stichtag inline |
| Report-Stichtag | – | Measure `Heute Berlin` |

Warum das mehr als Kosmetik ist: `snapshot_date` ist Partitionsschlüssel
**und** fachlicher Schlüssel der Änderungserkennung. Ein Lauf um 00:30
Berliner Zeit hätte in UK-Zeit den Vortag bekommen — der Snapshot wäre in die
Vortagespartition gefallen, hätte dort den echten Vortagsstand überschrieben
und in `vw_*_changes` einen Tag Historie ausgelöscht. Bei einem
Nachtplan oder einem Retry nach Mitternacht wäre das unbemerkt passiert.

M kennt keine Zeitzonendatenbank, deshalb liegt die EU-Sommerzeitregel
explizit in `fn_berlin_now` (letzter Sonntag im März 01:00 UTC bis letzter
Sonntag im Oktober 01:00 UTC), in DAX dieselbe Regel noch einmal. Beide
Varianten wurden stundenweise über 2024–2035 gegen die IANA-Zeitzonendaten
geprüft — keine Abweichung.

Zusätzlich werden `snapshot_date` und `loaded_at` jetzt **einmal je Lauf**
ausgewertet statt je Zeile. Vorher hätte ein Ladelauf über Mitternacht zwei
verschiedene `snapshot_date` in einer Staging-Tabelle erzeugt und den
Grain-Check im Notebook hart auf Fehler laufen lassen.

### Auto-Date/Time aus

Das Altmodell trägt 13 `LocalDateTable_*` Tabellen, erzeugt durch
Auto-Date/Time auf jeder Datumsspalte. Mit `dim_date` als einziger
Datumstabelle entfallen sie.

## Offene Punkte vor dem Bau

- **Szenario/Version in `Mapping_Planwerke.xlsx`.** Wenn Budget- und
  Forecast-Runde unterschiedliche Zuordnungen brauchen, reicht der aktuelle
  Grain `opportunityid → sap_unit` nicht: die eine Runde überschreibt die
  andere. Dann braucht die Datei eine Szenariospalte und die Tabelle einen
  entsprechend erweiterten Schlüssel.
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
| `fabric/dataflow/map_opportunity_unit.m` | Mapping Opportunity → SAP-Betrieb aus SharePoint |
| `fabric/dataflow/fn_berlin_now.m` | Zeitstempel auf Europe/Berlin (Laden deaktivieren) |
| `fabric/lakehouse/01_create_tables.sql` | Delta-Tabellen, partitioniert nach `snapshot_date` |
| `fabric/lakehouse/02_load_snapshot.py` | Idempotenter Tageslauf Staging → Fakt |
| `fabric/lakehouse/03_views.sql` | Ist-Stand- und Änderungsviews |
| `fabric/semantic-model/01_ity_phasing.dax` | ITY-Monatsphasierung und vereinigte Effekttabelle |
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
