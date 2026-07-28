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
      │              stg_opportunity_unit               vom Dataflow angelegt
      │
      ▼  Notebook, idempotent
Lakehouse ──► fct_opportunity / fct_retention       (Append, partitioniert)
      │           │
      │           │  Notebook, Spark SQL
      │           ├─► fct_*_current   → Ist-Stand
      │           └─► fct_*_changes   → Änderungshistorie
      ▼
Semantic Model (Import, PBIP)
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
`fct_*_changes`-Tabellen verdichten sie auf die Snapshots, in denen sich fachlich
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

Die `stg_*`-Tabellen werden **nicht** vorab angelegt. Sie sind das Ziel der
Dataflow-Queries und entstehen beim ersten Lauf; jeder weitere Lauf
überschreibt sie vollständig. Nur die historientragenden Tabellen stehen in
`01_create_tables.sql`, weil deren Schema über Jahre stabil bleiben muss.

**Namenskonvention:** Der Queryname im Dataflow entspricht immer seiner
Zieltabelle (`stg_opportunity` → `stg_opportunity`). Die Umbenennung auf
`fct_*` bzw. `map_*` passiert erst in der Historisierung. Ein Query, der
`fct_opportunity` heißt, aber nach `stg_opportunity` schreibt, lädt
zuverlässig zur falschen Verdrahtung ein.

### Namen in der Faktenzeile statt in Dimensionen

Die elf `dim_opp_*` Tabellen des Altmodells waren eigene CRM-Abfragen auf
dieselben Entities. Sie entfallen ersatzlos: `02_load_snapshot.py` löst die
Lookup-IDs beim Laden gegen `stg_lkp_*` auf und schreibt den Klartext in die
Faktenzeile (`owner_name`, `territory`, `sector`, …).

Drei Gründe, in dieser Reihenfolge:

- **Historische Richtigkeit.** Eine Dimension trägt nur den aktuellen Namen.
  Wird ein Territory umbenannt oder eine Opportunity umverteilt, zeigte auch
  der Snapshot von vor drei Monaten den heutigen Stand — der Tagesstand wäre
  nicht mehr das, was er behauptet zu sein. In der Faktenzeile ist jeder
  Snapshot in sich geschlossen.
- **Kein CRM-Zugriff aus Desktop.** Der Dataflow bleibt der einzige
  Kontaktpunkt; Desktop liest nur den SQL-Endpoint. Das umgeht auch die
  Zscaler-Sperre, die die Bearbeitung CRM-gebundener Dimensionen verhinderte.
- **Keine berechneten Tabellen** — Voraussetzung für Direct Lake.

Die Attribute laufen bis in `fct_budget_effect` durch. Ohne das hätte der
Nettoeffekt keinen Bezug zu Territory oder Sektor: die Tabelle ist über
`entity_id` an nichts anschließbar, weil dort Opportunity- und Contract-IDs
nebeneinander stehen. Denormalisiert kostet es nichts, weil die Werte über
die Phasierung ohnehin mitkommen.

Der Join gehört in die **Historisierung**, nicht in die abgeleitete Schicht.
Ein Join erst in `03_derived_tables.sql` würde die heutigen Namen rückwirkend
über die gesamte Historie legen. Und er gehört nach **Spark**, nicht nach M:
ein `Table.NestedJoin` gegen mehrere Dataverse-Entitäten faltet nicht mehr
und macht den Vollextrakt langsam.

### ITY-Logik im Lakehouse, nicht im Modell

Die Monatsphasierung liegt in `fct_opp_phasing`, `fct_retention_phasing` und
`fct_budget_effect` — als Delta-Tabellen, erzeugt von
`03_derived_tables.sql`. Sie lag zunächst als berechnete DAX-Tabelle im
Semantic Model; der Umzug nach Spark hat drei Gründe:

- **Direct Lake verträgt keine berechneten Tabellen.** Solange die Phasierung
  in DAX liegt, ist das Modell auf Import festgelegt.
- **Prüfbarkeit.** Als Delta-Tabelle lässt sich eine einzelne Opportunity
  herausgreifen und ihre Monatszeilen gegen den Altbericht rechnen
  (`04_pruefung.sql`). In DAX war zwischen Rohdaten und Measure nichts
  einsehbar — genau das hat die Fehlersuche an den New-Business-Werten
  unnötig teuer gemacht.
- **Einmal täglich** statt bei jedem Modell-Refresh.

Der Betrachtungszeitraum steht in `cfg_horizont`, einer einzeiligen Tabelle.
Sie ersetzt die vier `Est_*`-Parameter des Altmodells.

**Vorzeichen bleiben im Measure.** Die Tabellen führen ausschließlich
positive Beträge; ob der ITY-Anteil negativ in den Nettoeffekt eingeht, ist
Darstellungskonvention und steht in `Netto Budgeteffekt`.

**Eine Abweichung zur DAX-Fassung:** Opportunities ohne `statecodename` oder
ohne `cgplc_salesstagename` fallen jetzt heraus. SQL und Power Query behandeln
den Vergleich mit `NULL` gleich — die zwischenzeitliche DAX-Fassung hat sie
fälschlich behalten, weil `BLANK() IN {…}` in DAX `FALSE` ergibt.

Zwei Dinge ändern sich bewusst:

- **Kein hart codierter Cutoff mehr.** Horizont und ITY-Grenze leiten sich aus
  `dim_date` ab. Im Altmodell standen `#date(2027, 9, 30)` und die Parameter
  `Est_Close_Date_*` an fünf Stellen verteilt; der Betrachtungszeitraum wird
  jetzt an genau einer Stelle gepflegt.
- **Keine Row-Explosion im Ladeprozess.** Der Extrakt bleibt bei einer Zeile
  je Opportunity, die Expansion passiert erst im Modell.

**Achtung bei den Filtern.** Weil der Extrakt bewusst *ohne* Datumsfilter
zieht, muss die Phasierung die Untergrenze selbst setzen — sonst erzeugt jede
Opportunity aus abgeschlossenen Jahren volle Budgetwirkung über den ganzen
Horizont. `fct_opp_phasing` bildet deshalb alle drei Filter des Altmodells ab:

| Altmodell (Power Query) | Phasierung (DAX) |
|---|---|
| `cgplc_openingdate >= Est_Close_Date_A` | `>= MIN(dim_date[Datum])` |
| `estimatedclosedate >= Est_Close_Date_A` | `>= MIN(dim_date[Datum])` |
| `statecodename <> "Verloren"`, Stage-Ausschlüsse | unverändert |

Die Verlagerung der Fachlogik ins Modell ist nur dann wertneutral, wenn sie
**vollständig** ist. Ein weggelassener Filter fällt hier nicht als Fehler auf,
sondern als stille Überzeichnung.

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
  geht. `Effekt geplante Units` macht diesen Anteil direkt sichtbar.
- **Der Pflegestand wird messbar.** `Unmapped Effekt`, `Unmapped
  Opportunities` und `Unmapped Anteil` zeigen, welches Volumen noch keinem
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

### Import statt Direct Lake

Das Zielbild sah zunächst Direct Lake vor. Ausgeliefert ist ein
**Import**-Modell, und zwar aus einem harten Grund: Direct Lake unterstützt
keine berechneten Spalten und keine berechneten Tabellen auf
Direct-Lake-Tabellen. Genau darauf beruht dieses Modell — die ITY-Phasierung,
`fct_budget_effect`, `dim_unit` und alle abgeleiteten Dimensionen sind
DAX-Tabellen, dazu Spalten wie `win_status`, `Ret_Status`, `days_to_decision`.

Fachlich ist Import hier unkritisch: die Quelle wechselt genau einmal täglich,
ein Refresh nach dem Notebook-Lauf genügt. Der Preis ist ein Refresh-Schritt
mehr und Speicher im Modell statt im Lakehouse.

Der Weg zu Direct Lake bleibt offen und ist eine eigene Ausbaustufe: Phasierung
und `fct_budget_effect` müssten als Delta-Tabellen in `03_derived_tables.sql`
entstehen, die Dimensionen ebenso. Das Modell enthielte dann nur noch physische
Tabellen und Measures. Das ist der sauberere Endzustand — er verlangt aber,
die Phasierungslogik von DAX nach Spark SQL zu übersetzen und gegenzurechnen.

Die Materialisierung der Ableitungen (`fct_*_current`, `fct_*_changes`) bleibt
davon unberührt sinnvoll: sie hält die Modellabfragen schlank und ist die
Voraussetzung für einen späteren Wechsel auf Direct Lake.

### Zeitzone: alles auf Europe/Berlin

Die Fabric-Kapazität der Gruppe läuft in UK-Zeit, `TODAY()`/`NOW()` im Power
BI Service laufen in UTC. Berlin liegt gegenüber UK durchgehend eine Stunde,
gegenüber UTC je nach Sommerzeit ein bis zwei Stunden vorn. Alle Zeitstempel
werden deshalb explizit auf Berlin gerechnet:

| Stelle | Vorher | Jetzt |
|---|---|---|
| `snapshot_date` (3 Dataflow-Queries) | `DateTimeZone.FixedLocalNow()` → UK | `fn_berlin_now()` |
| `loaded_at` (3 Dataflow-Queries) | `DateTimeZone.FixedUtcNow()` → UTC | `fn_berlin_now()`, Versatz abgeschnitten |
| Lakehouse-Notebook | Session-Zeitzone der Kapazität | `spark.sql.session.timeZone = Europe/Berlin` |
| `days_to_decision` | `TODAY()` → UTC | Berliner Stichtag inline |
| Report-Stichtag | – | Measure `Heute Berlin` |

Warum das mehr als Kosmetik ist: `snapshot_date` ist Partitionsschlüssel
**und** fachlicher Schlüssel der Änderungserkennung. Ein Lauf um 00:30
Berliner Zeit hätte in UK-Zeit den Vortag bekommen — der Snapshot wäre in die
Vortagespartition gefallen, hätte dort den echten Vortagsstand überschrieben
und in `fct_*_changes` einen Tag Historie ausgelöscht. Bei einem
Nachtplan oder einem Retry nach Mitternacht wäre das unbemerkt passiert.

M kennt keine Zeitzonendatenbank, deshalb liegt die EU-Sommerzeitregel
explizit in `fn_berlin_now` (letzter Sonntag im März 01:00 UTC bis letzter
Sonntag im Oktober 01:00 UTC), in DAX dieselbe Regel noch einmal. Beide
Varianten wurden stundenweise über 2024–2035 gegen die IANA-Zeitzonendaten
geprüft — keine Abweichung.

`loaded_at` wird als **naiver** Zeitstempel in Berliner Ortszeit gespeichert,
nicht mit Zeitzonenversatz: das Lakehouse-Ziel eines Dataflow Gen2 unterstützt
den Typ `datetimezone` nicht ("Diese Spalte kann nicht eingeschlossen werden,
da ihr Typ nicht unterstützt wird"). `fn_berlin_now` liefert weiterhin
`datetimezone` — der Versatz wird zum Rechnen gebraucht, aber vor dem
Schreiben per `DateTime.From` abgeschnitten. Zusammen mit der auf
`Europe/Berlin` gesetzten Spark-Session bleibt die Wanduhrzeit über die
ganze Strecke konsistent.

Der Preis: in der Stunde der Zeitumstellung im Oktober ist ein naiver
Zeitstempel nicht eindeutig — 02:30 gibt es zweimal. Für ein reines
Audit-Feld ist das folgenlos; `snapshot_date` ist davon nicht betroffen, weil
es ein reines Datum ist. Wer Eindeutigkeit braucht, müsste `loaded_at` in UTC
führen und die Anzeige der Session-Zeitzone überlassen.

Zusätzlich werden `snapshot_date` und `loaded_at` jetzt **einmal je Lauf**
ausgewertet statt je Zeile. Vorher hätte ein Ladelauf über Mitternacht zwei
verschiedene `snapshot_date` in einer Staging-Tabelle erzeugt und den
Grain-Check im Notebook hart auf Fehler laufen lassen.

### Auto-Date/Time aus

Das Altmodell trägt 13 `LocalDateTable_*` Tabellen, erzeugt durch
Auto-Date/Time auf jeder Datumsspalte. Mit `dim_date` als einziger
Datumstabelle entfallen sie.

## Ausführung: was läuft wo

Die SQL-Dateien sind **Spark SQL**, nicht T-SQL. Sie laufen im Fabric-Notebook
in einer `%%sql`-Zelle — nicht im SQL Analytics Endpoint des Lakehouse.

| Schritt | Datei | Umgebung | Rhythmus |
|---|---|---|---|
| 1 | `fabric/dataflow/*.m` | Dataflow Gen2 | täglich |
| 2 | `01_create_tables.sql` | Notebook, `%%sql` | einmalig |
| 3 | `02_load_snapshot.py` | Notebook, PySpark | täglich |
| 4 | `03_derived_tables.sql` | Notebook, `%%sql` | täglich, nach Schritt 3 |
| 5 | `powerbi/CRM Net New Budget.pbip` | Power BI Desktop | Refresh nach Schritt 4 |

Der SQL Analytics Endpoint spricht T-SQL und ist für das Lakehouse **lesend**.
Dort scheitern die Skripte schon an `CREATE TABLE IF NOT EXISTS` (T-SQL kennt
kein `IF NOT EXISTS` in `CREATE TABLE` → Meldung 156), ebenso an `USING
DELTA`, `PARTITIONED BY`, dem nullsicheren Vergleich `<=>` und der
`WINDOW`-Klausel. Tabellen im Lakehouse entstehen ausschließlich über Spark.
Der Endpoint bleibt für Ad-hoc-Abfragen nützlich — die von Spark angelegten
Tabellen erscheinen dort automatisch.

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
| `fabric/dataflow/stg_opportunity.m` | Dataflow-Gen2-Query, Vollextrakt Opportunities |
| `fabric/dataflow/stg_retention.m` | Dataflow-Gen2-Query, Vollextrakt Contracts |
| `fabric/dataflow/stg_opportunity_unit.m` | Mapping Opportunity → SAP-Betrieb aus SharePoint |
| `fabric/dataflow/stg_lookups.m` | Lookup-Queries für die Klartextnamen |
| `fabric/dataflow/fn_berlin_now.m` | Zeitstempel auf Europe/Berlin (Laden deaktivieren) |
| `fabric/lakehouse/04_pruefung.sql` | Neun Abfragen zum Gegenrechnen |
| `fabric/lakehouse/01_create_tables.sql` | Delta-Tabellen, partitioniert nach `snapshot_date` |
| `fabric/lakehouse/02_load_snapshot.py` | Idempotenter Tageslauf Staging → Fakt |
| `fabric/lakehouse/03_derived_tables.sql` | Ist-Stand und Änderungshistorie als Delta-Tabellen |
| `powerbi/CRM Net New Budget.pbip` | PBIP-Projekt: Semantic Model + Bericht |
| `powerbi/README.md` | Parameter, Voraussetzungen, Speichermodus |
| `fabric/pipeline/pipeline-content.json` | Orchestrierung des Tageslaufs |
| `docs/pipeline.md` | Ablauf, Zeitplan, Fehlerbehandlung |
| `fabric/semantic-model/01_ity_phasing.dax` | ITY-Monatsphasierung und vereinigte Effekttabelle |
| `fabric/semantic-model/02_calculated_columns.dax` | Klassifizierungen und abgeleitete Dimensionen |
| `fabric/semantic-model/03_measures.dax` | Bestandsmeasures und Leading KPIs |

## Leading KPIs

Die Kennzahlen, die erst durch Historisierung und Vollextrakt möglich werden:

| KPI | Aussage | Voraussetzung |
|---|---|---|
| Pipeline Coverage | Deckt die gewichtete Pipeline den Plan? | offen, braucht `Revenues` |
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
