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

Im Fabric-Arbeitsbereich drei Dataflows Gen2 erstellen und den M-Code aus
`dataflows/` einfügen:

| Dataflow | Datei | Ziel | Modus |
|---|---|---|---|
| `df_crm_opportunity` | `dataflows/df_crm_opportunity.m` | `bronze_crm_opportunity` | Anfügen |
| `df_crm_contract` | `dataflows/df_crm_contract.m` | `bronze_crm_contract` | Anfügen |
| `df_crm_lookups` | `dataflows/df_crm_lookups.m` | `bronze_crm_account`, `bronze_crm_territory` | Anfügen |
| `df_map_unit_assignment` | `dataflows/df_map_unit_assignment.m` | `bronze_map_unit_assignment` | **Ersetzen** |

In `df_crm_lookups` ist nur die erste Abfrage aktiv; `territory` steht
auskommentiert in derselben Datei und wird als eigene Abfrage angelegt. Die
gemeinsame Quellfunktion `fnDataverse` steht am Dateianfang. Die Entitäten
`systemuser` und `audit` werden bewusst **nicht** extrahiert – beide sind im
Mandanten nicht verfügbar (Begründung und Konsequenzen:
`docs/04_crm_feldkatalog.md`, Abschnitt „Bewusst nicht extrahiert").

`df_map_unit_assignment` lädt die vom Controlling gepflegte Datei
`Mapping_Planwerke.xlsx` (SharePoint, `08_Budget`). Sie steuert die
Werk-Zuordnung der CRM-Vorgänge über Sektor/Subsektor – Aufbau und
Auflösungskette: `docs/04_crm_feldkatalog.md`, Abschnitt „Werk-Zuordnung".
Als Stammdatum wird sie ersetzt, nicht angefügt.

Für die CRM-Extrakte gilt Aktualisierungsmethode **Anfügen** – die
Snapshot-Historie hängt daran.

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

Die vier Dateien aus `lakehouse/notebooks/` als Fabric-Notebooks importieren und
mit dem Lakehouse verbinden:

```
nb_00_config     Konstanten und Hilfsfunktionen (schreibt nichts)
nb_10_silver     Bronze -> Silver, Historisierung
nb_20_gold       Silver -> Gold, Perioden-Fanout
nb_30_quality    Qualitätsregeln, bricht bei ERROR ab
```

**In `nb_00_config` anzupassen:**

```python
CURRENT_FY = 2025   # 2025 = FY2025/26. Einmal jährlich hochzählen.
```

Derselbe Wert steht im Semantikmodell als Parameter
`AktuellesGeschaeftsjahr`. Beide müssen übereinstimmen –
`docs/08_datenqualitaet.md` beschreibt, woran man eine Abweichung erkennt.

Manueller Erstlauf in dieser Reihenfolge: `nb_10_silver`, `nb_20_gold`,
`nb_30_quality`.

---

## Schritt 3 – Pipeline einrichten

Data-Pipeline `pl_net_new_ity_daily` mit vier aufeinanderfolgenden Aktivitäten:

```
Dataflows (parallel)        05:00
   -> nb_10_silver          05:30   bei Erfolg
   -> nb_20_gold            05:45   bei Erfolg
   -> nb_30_quality         06:00   bei Erfolg
   -> Semantikmodell        06:15   bei Erfolg
```

Die Verkettung über "bei Erfolg" ist die eigentliche Absicherung:
`nb_30_quality` wirft bei Verstößen gegen ERROR-Regeln eine Ausnahme, die
Pipeline bricht ab, und das Semantikmodell behält den letzten geprüften Stand.
Ein Bericht mit alten, aber korrekten Zahlen ist besser als einer mit frischen,
aber falschen.

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
4. `nb_10_silver`, `nb_20_gold`, `nb_30_quality` manuell laufen lassen
5. Semantikmodell aktualisieren

---

## Fehlerbilder

| Symptom | Ursache | Abhilfe |
|---|---|---|
| Pipeline bricht bei `nb_30_quality` ab | ERROR-Regel verletzt | `SELECT * FROM gold_dq_checks WHERE schweregrad = 'ERROR' AND anzahl_verstoesse > 0 ORDER BY pruef_datum DESC` – jede Zeile nennt den Handlungshinweis |
| Bericht zeigt leere Werte | `CURRENT_FY` und `AktuellesGeschaeftsjahr` weichen ab | Beide Werte angleichen |
| Szenarienseite verändert nichts | Alle Regler auf Vorbelegung (0 Monate, kein Anlauf) | Das ist der Basisfall; Regler verstellen |
| Verträge fehlen im Lost Business | Kein Vorjahres-ARO im CRM | Regel DQ-CON-001 auf der Seite Datenqualität |
| Opportunities fehlen im New Business | Kein Mobilisierungsdatum im CRM | Regel DQ-OPP-001 |
| Ein Feld fehlt in Bronze | Im Mandanten nicht vorhanden | Spalte `_fehlende_felder` prüfen, `docs/04_crm_feldkatalog.md` |
| `validate_pbip.py` meldet fehlende Kennzahl | Bericht referenziert etwas, das im Modell nicht existiert | Entweder Kennzahl anlegen oder Referenz im Generator korrigieren |
