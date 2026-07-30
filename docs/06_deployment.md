# 06 – Einrichtung und Betrieb

Von diesem Repository zum laufenden Bericht. Reihenfolge einhalten – jeder
Schritt setzt den vorherigen voraus.

---

## Voraussetzungen

| Was | Wofür |
|---|---|
| Fabric-Kapazität mit Lakehouse `lakehouse_group_controlling` | Bronze/Silver/Gold |
| Dataverse-Verbindung zu `cpgplc.crm.dynamics.com` | CRM-Extrakt |
| Verbindung zum SAP-Warehouse `Reporting` | Umsatzdaten |
| Power BI Desktop, Version 2024.09 oder neuer | PBIP mit TMDL und PBIR öffnen |
| Python 3.9+ | Generator und Prüfskripte |

Power BI Desktop: unter *Datei → Optionen → Vorschaufunktionen* müssen
**"Power BI Project (.pbip)"**, **"Store semantic model using TMDL format"** und
**"Store reports using enhanced metadata format (PBIR)"** aktiviert sein.

---

## Schritt 1 – Dataflows anlegen

Im Fabric-Arbeitsbereich **drei** Dataflows Gen2 erstellen. Jede Abfrage steht
einzeln unter `dataflows/<dataflow>/` und lässt sich per Copy-Paste in den
erweiterten Editor einer neuen Power-Query-Abfrage übertragen. Die Trennung
folgt der Quelle: CRM-Extrakte teilen eine Verbindung und einen Fehlerfall,
das Mapping hängt an SharePoint und die SAP-Abfragen am Warehouse – keine
davon soll mitreißen, wenn eine andere klemmt. Begründung ausführlich in
`dataflows/README.md`.

| Dataflow | Ordner | Abfragen (Ziel = Dateiname ohne Nummer) | Modus |
|---|---|---|---|
| `df_crm_ingest` | `dataflows/df_crm_ingest/` | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` | Ersetzen |
| `df_map_unit_assignment` | `dataflows/df_map_unit_assignment/` | `stg_map_unit_assignment` | Ersetzen |
| `df_sap_ingest` | `dataflows/df_sap_ingest/` | `bronze_sap_unit`, `bronze_sap_revenue` | Ersetzen |

**Warum die SAP-Abfragen direkt nach `bronze_*` schreiben und nicht nach
`stg_*`:** sie werden bewusst **nicht historisiert**. Betriebsstammdaten sind
ein Ist-Stand und keine Bewegung; `V_SAP_EXPORTS_cleansed` ist bereits der
gepflegte Ist-/Planstand je Periode. Ein Tagessnapshot darüber würde dieselben
Buchungen täglich vervielfachen, ohne eine Frage zu beantworten, die nicht
schon über `fy_year`/`fy_period` beantwortbar wäre. `nb_05_snapshot` fasst
diese beiden Tabellen deshalb nicht an – anders als die CRM-Extrakte, bei
denen die Bewegungsanalyse genau auf der Historie beruht.

In `df_sap_ingest` sind vor dem ersten Lauf zwei Stellen zu füllen:

* `01_bronze_sap_unit.m` – die Navigation zum bestehenden Gen1-Dataflow
  `sap_master_data_unit` enthält mandantenspezifische GUIDs. Über *Daten
  abrufen → Dataflows* erzeugen lassen und die beiden ersten Schritte der
  Datei damit ersetzen.
* `02_bronze_sap_revenue.m` – `SapServer` auf den Servernamen des
  SAP-Warehouse `Reporting` setzen und `AktuellesGJ` mit `CURRENT_FY`
  gleichhalten.

In jedem Ordner zuerst `00_fn_berlin_now.m` als **Funktionsquery** anlegen und
**"Laden aktivieren" ausschalten** – sie liefert keine Zieltabelle, sondern
wird von den übrigen Abfragen des Dataflows aufgerufen. Dataflow Gen2 teilt
Funktionen nicht über Dataflow-Grenzen hinweg, deshalb liegt die Datei in
beiden Ordnern.

Die Entitäten `systemuser` und `audit` werden bewusst **nicht** extrahiert –
beide sind im Mandanten nicht verfügbar (Begründung und Konsequenzen:
`docs/04_crm_feldkatalog.md`, Abschnitt „Bewusst nicht extrahiert").

`stg_map_unit_assignment` lädt die vom Controlling gepflegte Datei
`Mapping_Planwerke.xlsx` (SharePoint, `08_Budget`) – dieselbe Datei, die das
Altmodell live in `fct_opp` gejoint hat. Sie steuert die Werk-Zuordnung über
Sektor/Subsektor; Aufbau und Auflösungskette:
`docs/04_crm_feldkatalog.md`, Abschnitt „Werk-Zuordnung". Sie wird wie die
Fakten historisiert, weil sie ein manueller Input in offizielle Budgetzahlen
ist: ohne Snapshot lässt sich eine abgeschlossene Budgetrunde nach der
nächsten Pflegerunde nicht mehr reproduzieren.

Die **CRM- und Mapping-Abfragen** schreiben mit **Ersetzen** in ihre
`stg_*`-Tabelle. Die Historisierung nach `bronze_*` übernimmt `nb_05_snapshot`
– nicht mit Anfügen direkt nach `bronze_*` schreiben, der Grund steht in
Schritt 2. Die **SAP-Abfragen** schreiben dagegen direkt nach `bronze_*`,
ebenfalls mit Ersetzen; sie durchlaufen die Historisierung nicht (Begründung
oben).

### Erster Lauf prüfen

```sql
SELECT DISTINCT _fehlende_felder
FROM   bronze_crm_opportunity
WHERE  snapshot_date = (SELECT MAX(snapshot_date) FROM bronze_crm_opportunity);
```

Die Ausgabe listet alle Wunschfelder, die im Mandanten nicht existieren. Zu
jedem Eintrag eine Entscheidung treffen – siehe `docs/04_crm_feldkatalog.md`.

---

## Schritt 2 – Notebooks importieren

Die fünf Dateien aus `lakehouse/notebooks/` als Fabric-Notebooks importieren
und mit dem Lakehouse verbinden:

```
nb_00_config     Konstanten, Hilfsfunktionen, Zeitzone (schreibt nichts)
nb_05_snapshot   Staging -> Bronze, idempotent je Tagespartition
nb_10_silver     Bronze -> Silver, Historisierung
nb_20_gold       Silver -> Gold, Perioden-Fanout
nb_30_quality    Qualitätsregeln, bricht bei ERROR ab
```

`nb_05_snapshot` ist der Grund, warum die Dataflows mit **Ersetzen** in
`stg_*` schreiben und nicht mit Anfügen direkt nach `bronze_*`: es löscht die
Partition des Tages, bevor es schreibt, und macht den Lauf beliebig oft
wiederholbar. Ein Dataflow-Append würde bei jedem Retry einen zweiten Snapshot
desselben Tages anhängen und jede Summe verdoppeln.

### Import – unbedingt so, sonst schlägt `%run` fehl

`nb_05_snapshot`, `nb_10_silver`, `nb_20_gold` und `nb_30_quality` beginnen
mit einer eigenen Zelle, die nur `%run nb_00_config` enthält – so laden sie
die Konstanten und Hilfsfunktionen aus `nb_00_config` (u. a. `write_delta`,
`EXCLUDED_STATE_NAMES`, `add_fiscal_columns`, `name_oder_id`).

**Diese vier Dateien müssen als vollständige Notebook-Objekte importiert
werden** (Arbeitsbereich → Neu → Notebook importieren, `.py`-Datei
auswählen), **nicht** durch Kopieren des Textes in eine einzelne, bereits
bestehende Zelle. Der Grund liegt im Dateiformat: `%run` steht dort als
eigene Zelle, getrennt durch `# COMMAND ----------`-Marker. Landet der ganze
Dateiinhalt stattdessen in einer einzigen Zelle, ist die Zeile
`# MAGIC %run nb_00_config` nur noch ein Kommentar – sie wird nie ausgeführt,
und jeder Aufruf einer Funktion aus `nb_00_config` bricht mit
`NameError: name '…' is not defined` ab.

Nach dem Import in jedem der vier Notebooks prüfen: Die erste Codezelle
enthält ausschließlich `%run nb_00_config` (ohne `# MAGIC`-Präfix, das wird
beim Import automatisch aufgelöst) und läuft ohne Fehler grün durch, bevor
die zweite Zelle startet.

**Nach jeder Änderung an `nb_00_config` alle fünf Notebooks neu importieren.**
Fabric hält je Notebook eine eigene Kopie; wird nur `nb_10_silver` ersetzt,
läuft dessen `%run` weiter gegen die alte Konfiguration. Damit das nicht als
`NameError` mitten im Lauf auffällt, trägt `nb_00_config` die Konstante
`CONFIG_VERSION`, die die vier abhängigen Notebooks in ihrer ersten Codezelle
prüfen. Ist sie zu niedrig, brechen sie sofort mit einer Meldung ab, die zum
Neuimport auffordert. Beim Ändern von Hilfsfunktionen in `nb_00_config` die
Version hochzählen und `BENOETIGTE_CONFIG_VERSION` in den vier Notebooks
mitziehen.

**In `nb_00_config` anzupassen:**

```python
CURRENT_FY = 2025   # 2025 = FY2025/26. Einmal jährlich hochzählen.
```

Derselbe Wert steht im Semantikmodell als Parameter
`AktuellesGeschaeftsjahr`. Beide müssen übereinstimmen –
`docs/08_datenqualitaet.md` beschreibt, woran man eine Abweichung erkennt.

Manueller Erstlauf in dieser Reihenfolge: `nb_05_snapshot`, `nb_10_silver`,
`nb_20_gold`, `nb_30_quality`.

---

## Schritt 3 – Pipeline einrichten

Data-Pipeline `pl_net_new_ity_daily` mit acht Aktivitäten:

```
df_crm_ingest aktualisieren            ─┐
df_map_unit_assignment aktualisieren   ─┼─▶ nb_05_snapshot ─▶ nb_10_silver ─▶ nb_20_gold ─▶ nb_30_quality ─▶ Semantikmodell
df_sap_ingest aktualisieren            ─┘         │                 │              │              │                │
                                              (Succeeded)       (Succeeded)    (Succeeded)    (Succeeded)      (Succeeded)
```

| # | Aktivität | Typ | Abhängigkeit | Liest zusätzlich | Schreibt |
|---|---|---|---|---|---|
| 1 | `df_crm_ingest` aktualisieren | Dataflow-Aktualisierung | – | Dataverse | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` |
| 2 | `df_map_unit_assignment` aktualisieren | Dataflow-Aktualisierung | – | SharePoint | `stg_map_unit_assignment` |
| 3 | `df_sap_ingest` aktualisieren | Dataflow-Aktualisierung | – | SAP-Warehouse `Reporting`, Gen1-Dataflow `sap_master_data_unit` | `bronze_sap_unit`, `bronze_sap_revenue` |
| 4 | `nb_05_snapshot` | Notebook | 1 **und** 2, je Succeeded | alle `stg_*` | `bronze_crm_*`, `bronze_map_unit_assignment` |
| 5 | `nb_10_silver` | Notebook | 4 **und** 3, je Succeeded | `bronze_crm_*`, **`bronze_sap_unit`** | `silver_opportunity`, `silver_contract`, `silver_unit`, `silver_*_history`, `silver_dq_reject` |
| 6 | `nb_20_gold` | Notebook | 5, Succeeded | `silver_*`, `bronze_map_unit_assignment`, **`bronze_sap_revenue`** | `gold_dim_*`, `gold_fct_*` |
| 7 | `nb_30_quality` | Notebook | 6, Succeeded | `gold_fct_net_new_ity`, `silver_*` | `gold_dq_checks` |
| 8 | Semantikmodell aktualisieren | native Aktivität, sonst Web-Aktivität gegen die Enhanced-Refresh-REST-API | 7, Succeeded | – | Import-Tabellen des Modells |

`df_sap_ingest` läuft parallel zu 1 und 2, hängt aber **nicht** an
`nb_05_snapshot`: es schreibt direkt nach `bronze_*` und wird nicht
historisiert. Die Verkettung greift erst bei `nb_10_silver`, der ersten
Aktivität, die SAP-Daten tatsächlich liest.

**Die Abhängigkeitsbedingung muss überall „Succeeded" sein, nicht
„Completed".** `nb_05_snapshot` und `nb_30_quality` werfen absichtlich eine
Ausnahme, wenn etwas nicht stimmt (doppelter Snapshot, veralteter
Staging-Stand, ERROR-Datenqualitätsregel). Bei „Completed" liefe die Pipeline
trotzdem weiter und aktualisierte das Semantikmodell mit kaputten oder alten
Daten – genau der Fall, den die Verkettung verhindern soll. Ein Bericht mit
alten, aber korrekten Zahlen ist besser als einer mit frischen, aber falschen.

Vorschlag für Startzeiten: 05:00 (Dataflows) · 05:20 · 05:30 · 05:45 · 06:00 ·
06:15.

### SAP-Aktualität

`df_sap_ingest` ist Teil dieser Pipeline und zieht `bronze_sap_unit` und
`bronze_sap_revenue` bei jedem Lauf frisch. Die SAP-Aktualität hängt damit
nicht mehr an einem fremden Zeitplan – der frühere Fall „`nb_10_silver`
rechnet unbemerkt mit dem SAP-Stand von gestern" ist konstruktiv
ausgeschlossen, weil Aktivität 5 auf Aktivität 3 mit „Succeeded" wartet.

Eine Abhängigkeit bleibt: `df_sap_ingest` liest den Gen1-Dataflow
`sap_master_data_unit`, der seinen **eigenen** Refresh-Zeitplan hat. Läuft
dieser später als `pl_net_new_ity_daily`, sind die Betriebsstammdaten (nicht
die Umsätze) einen Tag alt. Das ist deutlich unkritischer als beim Umsatz –
Werke, Sektoren und Cause-of-Change ändern sich selten tagesaktuell –, sollte
aber beim Festlegen der Startzeit bekannt sein.

### Nach dem ersten vollständigen Lauf prüfen

```sql
-- Genau ein Snapshot je Bronze-Tabelle für heute?
SELECT 'bronze_crm_opportunity' AS tabelle, COUNT(DISTINCT snapshot_date) AS n
FROM   bronze_crm_opportunity WHERE snapshot_date = current_date()
UNION ALL
SELECT 'bronze_crm_contract', COUNT(DISTINCT snapshot_date)
FROM   bronze_crm_contract WHERE snapshot_date = current_date()
UNION ALL
SELECT 'bronze_map_unit_assignment', COUNT(DISTINCT snapshot_date)
FROM   bronze_map_unit_assignment WHERE snapshot_date = current_date();
-- jede Zeile muss n = 1 zeigen; 0 heißt der Dataflow/nb_05 ist nicht durchgelaufen

-- Ist der Gold-Fakt für denselben Tag geschrieben?
SELECT snapshot_date, COUNT(*) AS zeilen
FROM   gold_fct_net_new_ity
GROUP  BY snapshot_date
ORDER  BY snapshot_date DESC
LIMIT  3;

-- Blockiert eine ERROR-Regel den heutigen Stand?
SELECT regel_id, anzahl_verstoesse, beschreibung
FROM   gold_dq_checks
WHERE  pruef_datum = current_date() AND schweregrad = 'ERROR' AND anzahl_verstoesse > 0;

-- Genau EINE Zeile je Vorgang in Silver?
-- Muss 0 Zeilen liefern. Trifft es zu, liest nb_10_silver die Bronze-Historie
-- ungefiltert und jede Summe ist um den Faktor der bisherigen Ladelaeufe zu
-- hoch (Regel DQ-SIL-001, docs/01_architektur.md, Abschnitt Schichtgrenze).
SELECT opportunityid, COUNT(*) AS n
FROM   silver_opportunity GROUP BY opportunityid HAVING COUNT(*) > 1
UNION ALL
SELECT cgplc_cgcontractid, COUNT(*)
FROM   silver_contract GROUP BY cgplc_cgcontractid HAVING COUNT(*) > 1;
```

Erst wenn diese drei Abfragen den erwarteten Tagesstand zeigen und die letzte
leer bleibt, hat die Pipeline **alle** Daten korrekt geladen. Die vollständige
Regelliste inklusive Handlungsanweisungen: `docs/08_datenqualitaet.md`.

---

## Schritt 4 – Bericht öffnen

```bash
python3 tools/validate_pbip.py     # muss "Alle Prüfungen bestanden" melden
```

Dann `powerbi/Net New ITY Cockpit.pbip` in Power BI Desktop öffnen.

Beim ersten Öffnen fragt Desktop nach den Anmeldedaten für den SQL-Endpunkt des
Lakehouse. Die Parameter `LakehouseServer` und `LakehouseDatabase` sind in
`expressions.tmdl` vorbelegt und lassen sich beim Umzug in eine andere Umgebung
dort oder über die Arbeitsbereichseinstellungen überschreiben.

---

## Schritt 5 – Veröffentlichen

In den Arbeitsbereich veröffentlichen, danach:

1. **Anmeldedaten** für die Lakehouse-Verbindung im Semantikmodell hinterlegen.
2. **Geplante Aktualisierung ausschalten** – die Pipeline steuert den Refresh.
3. **Berechtigungen** setzen: Ersteller haben Schreibrechte auf den
   Arbeitsbereich, Fachbereich erhält Leserechte auf die App.

---

## Laufender Betrieb

### Änderungen am Bericht

**Der Bericht wird von Hand in Power BI Desktop gepflegt.** Layout, Visuals
und Formatierung werden dort geändert und die PBIP-Dateien anschließend
committet:

```bash
python3 tools/validate_pbip.py     # prüft Feldverweise, Geometrie, Farben
```

`tools/build_report.py` erzeugt **alle** Seiten neu und verwirft dabei jede
Handänderung – ohne Rückfrage und ohne dass es im Bericht auffällt. Er ist
deshalb kein Routinewerkzeug, sondern ein Sonderfall für einen bewussten
Neuaufbau, und läuft nur mit ausdrücklicher Bestätigung:

```bash
python3 tools/build_report.py --seiten-neu-erzeugen
```

Ohne dieses Argument bricht er ab und schreibt nichts. Vor einem Lauf prüfen,
ob im Bericht ungesicherte Handarbeit steht (`git status`, `git diff --stat`).

Der Generator verwendet stabile Bezeichner: derselbe Seitenname erzeugt
denselben Ordnernamen. Ein Lauf ohne inhaltliche Änderung an `build_report.py`
erzeugt daher keinen Git-Diff – überschreibt aber trotzdem alles, was in
Power BI Desktop dazugekommen ist.

Wer stattdessen direkt in Power BI Desktop arbeitet, überschreibt beim nächsten
Generatorlauf seine Änderungen. In dem Fall entweder die Änderung in den
Generator zurücktragen oder den Generator für diese Seite nicht mehr verwenden.

### Änderungen am Modell

TMDL-Dateien unter `powerbi/Net New ITY Cockpit.SemanticModel/definition/`
bearbeiten, danach:

```bash
python3 tools/generate_docs.py     # docs/02 und docs/03 neu erzeugen
python3 tools/validate_pbip.py
```

Jede neue Kennzahl braucht einen `///`-Kommentar. Ohne ihn schlägt
`validate_pbip.py` fehl – das ist Absicht: undokumentierte Kennzahlen sind
genau der Zustand, aus dem die Altmodelle bestanden.

### Jahreswechsel

Zum 1. Oktober:

1. `CURRENT_FY` in `lakehouse/notebooks/nb_00_config.py` hochzählen
2. `AktuellesGeschaeftsjahr` in `expressions.tmdl` hochzählen
3. `@CURRENT_FY` in `lakehouse/03_gold/gold_fct_net_new_ity.sql` hochzählen,
   falls die SQL-Variante verwendet wird
4. `nb_05_snapshot`, `nb_10_silver`, `nb_20_gold`, `nb_30_quality` manuell
   laufen lassen
5. Semantikmodell aktualisieren

---

## Fehlerbilder

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `NameError: name 'write_delta'/'add_fiscal_columns'/'EXCLUDED_STATE_NAMES' … is not defined` | `nb_00_config` wurde nicht ausgeführt – meist, weil der gesamte Dateiinhalt in einer einzigen Zelle statt als importiertes Notebook mit eigener `%run`-Zelle vorliegt | Notebook neu über „Notebook importieren" mit der `.py`-Datei anlegen (siehe Schritt 2, Abschnitt „Import"); zur Kontrolle die erste Zelle einzeln ausführen – sie muss nur `%run nb_00_config` enthalten und fehlerfrei laufen |
| `[PARSE_SYNTAX_ERROR] Syntax error at or near 'DECLARE'` in einer Notebookzelle | `lakehouse/03_gold/gold_fct_net_new_ity.sql` (T-SQL) wurde in eine Spark-SQL-Zelle eingefügt | Diese Datei nicht in Notebooks verwenden – sie gehört in den SQL-Editor eines Fabric Warehouse. Für den normalen Lakehouse-Aufbau ausschließlich `nb_20_gold.py` verwenden |
| `nb_05_snapshot` bricht mit "snapshot_date ist X, erwartet Y" ab | Der Dataflow hat nicht erfolgreich geschrieben, im Staging steht der Vortagsstand | Dataflow-Lauf prüfen und wiederholen. Für eine bewusste Nachladung `allow_stale_snapshot=True` setzen |
| `nb_05_snapshot` bricht mit "doppelte Werte in …" ab | Der Snapshot-Grain ist verletzt, die Quelle liefert einen Schlüssel mehrfach | Staging-Tabelle prüfen; meist ein geänderter Extraktfilter |
| Pipeline bricht bei `nb_30_quality` ab | ERROR-Regel verletzt | `SELECT * FROM gold_dq_checks WHERE schweregrad = 'ERROR' AND anzahl_verstoesse > 0 ORDER BY pruef_datum DESC` – jede Zeile nennt den Handlungshinweis |
| Bericht zeigt leere Werte | `CURRENT_FY` und `AktuellesGeschaeftsjahr` weichen ab | Beide Werte angleichen |
| Szenarienseite verändert nichts | Alle Regler auf Vorbelegung (0 Monate, kein Anlauf) | Das ist der Basisfall; Regler verstellen |
| Verträge fehlen im Lost Business | Kein Vorjahres-ARO im CRM | Regel DQ-CON-001 auf der Seite Datenqualität |
| Opportunities fehlen im New Business | Kein Mobilisierungsdatum im CRM | Regel DQ-OPP-001 |
| Ein Feld fehlt in Bronze | Im Mandanten nicht vorhanden | Spalte `_fehlende_felder` prüfen, `docs/04_crm_feldkatalog.md` |
| `validate_pbip.py` meldet fehlende Kennzahl | Bericht referenziert etwas, das im Modell nicht existiert | Entweder Kennzahl anlegen oder Referenz im Generator korrigieren |
