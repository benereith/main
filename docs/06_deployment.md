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

Im Fabric-Arbeitsbereich **zwei** Dataflows Gen2 erstellen. Jede Abfrage steht
einzeln unter `dataflows/<dataflow>/` und lässt sich per Copy-Paste in den
erweiterten Editor einer neuen Power-Query-Abfrage übertragen. Die Trennung
in zwei Dataflows folgt der Quelle: CRM-Extrakte teilen eine Verbindung und
einen Fehlerfall, das Mapping hängt an SharePoint und soll nicht mitreißen,
wenn Dataverse klemmt – Begründung ausführlich in `dataflows/README.md`.

| Dataflow | Ordner | Abfragen (Ziel = Dateiname ohne Nummer) | Modus |
|---|---|---|---|
| `df_crm_ingest` | `dataflows/df_crm_ingest/` | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` | Ersetzen |
| `df_map_unit_assignment` | `dataflows/df_map_unit_assignment/` | `stg_map_unit_assignment` | Ersetzen |

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

Alle Abfragen schreiben mit **Ersetzen** in ihre `stg_*`-Tabelle. Die
Historisierung nach `bronze_*` übernimmt `nb_05_snapshot` – nicht mit Anfügen
direkt nach `bronze_*` schreiben, der Grund steht in Schritt 2.

SAP-Seite: `bronze_sap_revenue` aus `V_SAP_EXPORTS_cleansed` und
`bronze_sap_unit` aus dem bestehenden Dataflow `sap_master_data_unit`. Das
SQL-Muster steht in `lakehouse/03_gold/gold_fct_net_new_ity.sql`; im Regelfall
genügt eine Verknüpfung (Shortcut) auf die bestehenden Tabellen.

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

Data-Pipeline `pl_net_new_ity_daily` mit sieben Aktivitäten:

```
df_crm_ingest aktualisieren            ─┐
                                         ├─▶ nb_05_snapshot ─▶ nb_10_silver ─▶ nb_20_gold ─▶ nb_30_quality ─▶ Semantikmodell
df_map_unit_assignment aktualisieren   ─┘         │                 │              │              │                │
                                              (Succeeded)       (Succeeded)    (Succeeded)    (Succeeded)      (Succeeded)
```

| # | Aktivität | Typ | Abhängigkeit | Liest zusätzlich | Schreibt |
|---|---|---|---|---|---|
| 1 | `df_crm_ingest` aktualisieren | Dataflow-Aktualisierung | – | Dataverse | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` |
| 2 | `df_map_unit_assignment` aktualisieren | Dataflow-Aktualisierung | – | SharePoint | `stg_map_unit_assignment` |
| 3 | `nb_05_snapshot` | Notebook | 1 **und** 2, je Succeeded | alle `stg_*` | `bronze_crm_*`, `bronze_map_unit_assignment` |
| 4 | `nb_10_silver` | Notebook | 3, Succeeded | `bronze_crm_*`, **`bronze_sap_unit`** | `silver_opportunity`, `silver_contract`, `silver_unit`, `silver_*_history`, `silver_dq_reject` |
| 5 | `nb_20_gold` | Notebook | 4, Succeeded | `silver_*`, `bronze_map_unit_assignment`, **`bronze_sap_revenue`** | `gold_dim_*`, `gold_fct_*` |
| 6 | `nb_30_quality` | Notebook | 5, Succeeded | `gold_fct_net_new_ity`, `silver_*` | `gold_dq_checks` |
| 7 | Semantikmodell aktualisieren | native Aktivität, sonst Web-Aktivität gegen die Enhanced-Refresh-REST-API | 6, Succeeded | – | Import-Tabellen des Modells |

**Die Abhängigkeitsbedingung muss überall „Succeeded" sein, nicht
„Completed".** `nb_05_snapshot` und `nb_30_quality` werfen absichtlich eine
Ausnahme, wenn etwas nicht stimmt (doppelter Snapshot, veralteter
Staging-Stand, ERROR-Datenqualitätsregel). Bei „Completed" liefe die Pipeline
trotzdem weiter und aktualisierte das Semantikmodell mit kaputten oder alten
Daten – genau der Fall, den die Verkettung verhindern soll. Ein Bericht mit
alten, aber korrekten Zahlen ist besser als einer mit frischen, aber falschen.

Vorschlag für Startzeiten: 05:00 (Dataflows) · 05:20 · 05:30 · 05:45 · 06:00 ·
06:15 – siehe aber die Einschränkung zu SAP direkt im Anschluss, bevor die
Zeiten festgelegt werden.

### Die Lücke, die diese Pipeline nicht schließt: SAP-Aktualität

`bronze_sap_unit` und `bronze_sap_revenue` werden von **keiner** der sieben
Aktivitäten geschrieben. Es sind Lakehouse-Shortcuts auf bereits bestehende
Objekte – den vorhandenen Dataflow `sap_master_data_unit` und die SQL-View
`V_SAP_EXPORTS_cleansed` (siehe Schritt 1). Ein Shortcut ist ein Live-Zeiger
und braucht keinen eigenen Refresh-Schritt in dieser Pipeline.

Damit hängt ihre Aktualität an einem Zeitplan, den `pl_net_new_ity_daily`
nicht kennt. Läuft der bestehende SAP-Dataflow später als 05:00, rechnet
`nb_10_silver` mit dem SAP-Stand von gestern – ohne dass ein Fehler auftaucht,
weil die Tabelle ja existiert und Daten enthält, nur veraltete.

Vor dem produktiven Einsatz eine der beiden Optionen wählen:

* **Zugriff auf den SAP-Dataflow vorhanden:** eine achte Aktivität
  „SAP-Dataflow aktualisieren" parallel zu 1 und 2 einfügen und
  `nb_10_silver` zusätzlich davon abhängig machen.
* **Kein Zugriff:** die Startzeit von `pl_net_new_ity_daily` mit Puffer hinter
  den bekannten SAP-Refresh legen.

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

Layout- und Seitenänderungen gehören in `tools/build_report.py`, nicht in die
generierten JSON-Dateien:

```bash
python3 tools/build_report.py      # Seiten neu erzeugen
python3 tools/validate_pbip.py     # prüfen
```

Der Generator verwendet stabile Bezeichner: derselbe Seitenname erzeugt
denselben Ordnernamen. Ein erneuter Lauf ohne inhaltliche Änderung erzeugt
daher keinen Git-Diff.

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
| `nb_05_snapshot` bricht mit "snapshot_date ist X, erwartet Y" ab | Der Dataflow hat nicht erfolgreich geschrieben, im Staging steht der Vortagsstand | Dataflow-Lauf prüfen und wiederholen. Für eine bewusste Nachladung `allow_stale_snapshot=True` setzen |
| `nb_05_snapshot` bricht mit "doppelte Werte in …" ab | Der Snapshot-Grain ist verletzt, die Quelle liefert einen Schlüssel mehrfach | Staging-Tabelle prüfen; meist ein geänderter Extraktfilter |
| Pipeline bricht bei `nb_30_quality` ab | ERROR-Regel verletzt | `SELECT * FROM gold_dq_checks WHERE schweregrad = 'ERROR' AND anzahl_verstoesse > 0 ORDER BY pruef_datum DESC` – jede Zeile nennt den Handlungshinweis |
| Bericht zeigt leere Werte | `CURRENT_FY` und `AktuellesGeschaeftsjahr` weichen ab | Beide Werte angleichen |
| Szenarienseite verändert nichts | Alle Regler auf Vorbelegung (0 Monate, kein Anlauf) | Das ist der Basisfall; Regler verstellen |
| Verträge fehlen im Lost Business | Kein Vorjahres-ARO im CRM | Regel DQ-CON-001 auf der Seite Datenqualität |
| Opportunities fehlen im New Business | Kein Mobilisierungsdatum im CRM | Regel DQ-OPP-001 |
| Ein Feld fehlt in Bronze | Im Mandanten nicht vorhanden | Spalte `_fehlende_felder` prüfen, `docs/04_crm_feldkatalog.md` |
| `validate_pbip.py` meldet fehlende Kennzahl | Bericht referenziert etwas, das im Modell nicht existiert | Entweder Kennzahl anlegen oder Referenz im Generator korrigieren |
