# Net New ITY – Umbau auf Sternschema & Szenario-Engine

Dieses Dokument beschreibt den restrukturierten Aufbau des Berichts, den
Freeze-/Forecast-Prozess und den Migrationspfad auf monatliche Lakehouse-Daten.

> **Wichtig:** Der Bericht wurde als Power BI **Project (PBIP/TMDL)** umgebaut.
> Öffne `Net New ITY.pbip` in Power BI Desktop (aktuelle Version, „Power BI
> Project"-Speicherformat aktiviert). Beim ersten Öffnen die Datenquellen-
> Anmeldung (SharePoint, Dataflow, Lakehouse) einmal bestätigen und
> aktualisieren.

---

## 1. Zielarchitektur auf einen Blick

Klassisches Sternschema: schlanke Faktentabelle in der Mitte, Dimensionen
außen. Szenarien (Actual/Budget/Forecast-Runden) sind **Daten** (Zeilen in der
Faktentabelle), nicht länger dupliziertes DAX/Power-Query.

```
                         ┌───────────────┐
                         │   DIM_DATE    │   Kalender inkl. verschobenem
                         │ (Datum, FY_*) │   Geschäftsjahr (FY_Offset)
                         └───────┬───────┘
                                 │ Datum
┌──────────────┐         ┌───────┴────────┐        ┌───────────────┐
│ DIM_Szenario │─Szenario│    Revenues    │─MetricId│  DIM_Struktur │
│ ACT/BUD/...  │         │ (Fakten,       │        │ (Net-New-     │
└──────────────┘         │  monatlich)    │        │  Hierarchie)  │
                         └───────┬────────┘        └───────────────┘
                                 │ Werk
                         ┌───────┴────────┐
                         │ SAP_Stammdaten │   Stammdaten (aktueller Stand)
                         └────────────────┘
```

Zusätzliche, bewusst **entkoppelte** Tabellen (Slicer/Steuerung):
`Snapshot_Timestamp_R/S` (Vergleichszeitpunkte CRM), `Zeitfilter` (MTD/YTD),
`Granularität`, `Zeitansicht`, `KPI`, `Abgeschlossene Periode`, `Comments`.

### Was war vorher das Problem?

| Vorher | Nachher |
|---|---|
| Feste Jahreszahlen (`=2024`, `=2025`, `N_Geschäftsjahr`-Tabellen) | Alles aus `Geschäftsjahresbeginn` abgeleitet → **beliebig viele Jahre** |
| YTD-Werte roh geladen, Monatswerte per DATEADD-Differenz in **jedem** Measure | YTD→Monat **einmal** in Power Query; Measures sind einfache SUMs |
| CoC-Stände 3× dupliziert geladen (`md_BUD`, `md_RGF`, `md_R03`) | **eine** Funktion `fnStammdaten_Snapshot(datum)` |
| 6-fache Entpivotierung (`Mapping Art`/`Mapping Wert`) → riesige Faktentabelle | 1 Zeile je Werk/Monat/Version/Szenario mit **einer** `MetricId` |
| 12 Auto-Date-`LocalDateTable`s + Time-Intelligence | entfernt, eine saubere `DIM_DATE` |
| Szenarien als hartverdrahtete Measure-Varianten | `DIM_Szenario` + `Szenario_Konfig` (Tabelle) |

---

## 2. Das verschobene Geschäftsjahr

An **genau einer Stelle** definiert: Parameter `Geschäftsjahresbeginn`
(Standard `01.10.2025`). Daraus abgeleitet:

- `FY_Startmonat` = Monat des GJ-Beginns (10 = Oktober)
- `Aktuelles_Geschäftsjahr` = Jahr des GJ-Beginns (2025)
- Funktionen `fnFiscal_DatumZuPeriode`, `fnFiscal_DatumZuGJ`,
  `fnFiscal_PeriodeZuDatum` – die einzige Stelle mit FY-Logik.

`DIM_DATE` trägt pro Tag: `FY_Start` (2025 = „FY2025/26"), `FY_Offset`
(0 = laufend, −1 = Vorjahr, −2 …), `FY_Periode` (P01…P12), `FY_MonatNr`,
`FY_Quartal`, `FY_Jahr`. **Beim Jahreswechsel nur `Geschäftsjahresbeginn`
umstellen** – Kalender, Periodenlogik und alle FY-Measures ziehen automatisch
nach. Der Kalender spannt rollierend GJ-6 … GJ+3 Jahre.

> Mehrjahresfähigkeit: `FY_Offset` ersetzt die alten fixen Jahresvergleiche.
> `−1` ist immer „das Vorjahr relativ zum eingestellten GJ", egal welches
> Kalenderjahr. Für Vergleiche über mehr als 2 Jahre siehe Abschnitt 6.

---

## 3. Szenario-Engine (Herzstück)

### 3.1 `Szenario_Konfig`

Eine Tabelle steuert **alle** Szenarien und Forecast-Runden. Je Zeile:

| Spalte | Bedeutung |
|---|---|
| `Szenario` | Kürzel (ACT, BUD, RGF, RF, P35, R03, FC02, ARO_RGF, R01) |
| `FY_Offset` | 0 = laufendes GJ, −1 = Vorjahr |
| `Werttyp_Version` | Quell-Version (z. B. `Plan_20`, `Actual_0`) |
| `CoC_Quelle` | `live` / `live_fy` / `snapshot` – woher der Cause of Change kommt |
| `CoC_Snapshot` | Stichtag für `snapshot` (verweist auf Parameter) |
| `CoC_Spalte_Adjustments` | CoC-Spalte für manuelle Werke |
| `Perioden_Freeze` | `true` = abgeschlossene Perioden nutzen den eingefrorenen Monatsstand |

**Eine neue Forecast-Runde = ein bis zwei neue Zeilen hier** (+ ggf. neuer
Snapshot-Parameter). Kein Eingriff ins Datenmodell nötig.

### 3.2 Cause of Change: live vs. eingefroren – die Kernlogik

Deine Anforderung wörtlich umgesetzt:

> „Nach jedem Monatsabschluss die Daten freezen zum damaligen Cause-of-Change-
> Stand. Bei Änderungen im nochmaligen Cause of Change müssen sich trotzdem
> wieder die YTD-Werte ziehen, da das Delta unterjährig mitgemeldet wird."

Für jede Faktenzeile gilt beim Cause of Change:

```
Buchungsperiode <= Abgeschlossene_Periode   → eingefrorener Stand
    (Stammdaten_Historie: CoC-Stand zum damaligen Monatsabschluss)
Buchungsperiode  > Abgeschlossene_Periode    → aktueller Live-Stand
    (Stammdaten_CoC, zieht den YTD-/CoC-Stand von jetzt)
```

- **`Stammdaten_Historie`**: liest aus `exports_md` je Betrieb und Periode den
  zum jeweiligen Monatsabschluss gültigen `cause_of_change` (letzter Export der
  Periode). Das ist der „gefrorene Stand".
- Ändert sich der Cause of Change eines Betriebs **im laufenden (offenen)
  Zeitraum**, greift für die noch offenen Perioden automatisch wieder der
  Live-Stand → das Delta wird unterjährig sichtbar, exakt wie gefordert.
- Das **Budget** (`Perioden_Freeze = false`) bleibt dagegen vollständig auf
  seinem Snapshot-Stand eingefroren.

Die Umschaltung steuerst du über den Parameter **`Abgeschlossene_Periode`**
(0–12, FY-Periode). Nach dem Abschluss von Periode *n* setzt du ihn auf *n*.

### 3.3 `MetricId` statt Mapping-Unpivot

Die Zuordnung (FY_Offset × Cause of Change) → Berichtsposition der Net-New-
Hierarchie liegt in `fnCoC_ZuMetricId`:

| FY_Offset | CoC | MetricId | Bedeutung |
|---|---|---|---|
| −1 | 1 | 1 | PY revenue from contracts won PY |
| 0 | 1 | 2 | CY revenue from contracts won PY |
| 0 | 2 | 4 | New Business ITY |
| beliebig | 3 | 6 | Lost Business Roll |
| −1 | 4 | 7 | PY revenue from contracts lost CY |
| 0 | 4 | 8 | CY revenue from contracts lost CY |
| sonst | – | 99 | Like for Like (in Measures ausgeblendet) |

Jede Faktenzeile bekommt je Szenario **eine** `MetricId` → Beziehung zu
`DIM_Struktur`. Die früheren 6 „Mapping CoCh X"-Spalten + Unpivot entfallen.

---

## 4. Snapshots der Stammdaten (Forecast/Budget einfrieren)

Du wolltest „auf einfache Art Snapshots der Stammdaten, um einen gefrorenen
Stand der Forecasts/des Budgets zu haben". Umsetzung:

- Der gefrorene Stand steckt in `exports_md` (Lakehouse), datiert per
  `update_ts`. `fnStammdaten_Snapshot(datum)` holt den Stand zu genau diesem
  Datum – **eine** Funktion für alle Runden (früher: `md_BUD`, `md_RGF`,
  `md_R03` als drei fast identische Abfragen).
- Pro Runde gibt es **einen Datums-Parameter** und **eine Blatt-Abfrage**, die
  die Funktion mit diesem Datum aufruft:
  - `Parameter_BUD_Stammdaten` → `Snapshot_BUD` – Budget
  - `Parameter_RGF_Stammdaten` → `Snapshot_RGF` – RGF/ARO
  - `Parameter_R03_Stammdaten` → `Snapshot_R03` – Forecast-Runde R03
- Die Blatt-Abfragen sind bewusst getrennt (nur Lakehouse-Zugriff, keine
  Referenz auf andere Abfragen), damit die **Formula-Firewall** nicht anschlägt.
- `Stammdaten_CoC` bindet die Snapshots über die Zuordnung **`SnapshotMap`**
  ein (Szenario-Kürzel → Blatt-Abfrage); `Szenario_Konfig` verknüpft jedes
  Szenario per `CoC_Quelle = "snapshot"` mit dieser Logik. Ein Snapshot =
  ein Datum. Fertig.

---

## 5. Runbooks

### 5.1 Monatsabschluss (jeden Monat)

1. Neuen Stammdaten-Export nach `exports_md` schreiben lassen (Lakehouse) –
   `update_ts` = Abschlussmonat. `Stammdaten_Historie` friert daraus den
   CoC-Stand der abgeschlossenen Periode automatisch ein.
2. Neue Revenues (SAP) in `Revenues_SAP.xlsx` bzw. später ins Lakehouse.
3. Parameter **`Abgeschlossene_Periode`** auf die neu abgeschlossene FY-Periode
   setzen (z. B. nach Dezember-Abschluss im Okt-GJ → Periode 3).
4. Aktualisieren. Ergebnis: abgeschlossene Perioden zeigen den gefrorenen CoC-
   Stand, offene Perioden ziehen weiter Live-YTD.

> Konvention `Stammdaten_Historie`: Ein Export im Monat *m* friert die
> **Vormonats**-Periode ein (Export November → Periode 1 = Oktober). Passt das
> bei dir nicht, ist es die **einzige** Stelle zum Anpassen
> (`Date.AddMonths([update_ts], -1)` in `expressions.tmdl`).

### 5.2 Neuen Snapshot / neue Forecast-Runde anlegen (z. B. R06)

Alle Schritte in Power BI Desktop → **Daten transformieren** (Power-Query-Editor).
Beispiel: neue Runde „R06" mit Version `Plan_R06`, eingefroren zum 15.06.2026.

**1. Snapshot-Datum als Parameter.** Neuen Parameter `Parameter_R06_Stammdaten`
   (Typ Datum) anlegen und auf den Freeze-Stichtag setzen (den `update_ts`, zu
   dem der Stammdaten-Export im Lakehouse eingefroren werden soll), z. B.
   `#date(2026, 6, 15)`. Am schnellsten: bestehenden `Parameter_R03_Stammdaten`
   duplizieren und umbenennen.

**2. Snapshot-Blatt-Abfrage.** Neue leere Abfrage anlegen (Gruppe
   „3. Stammdaten"), Name `Snapshot_R06`, im erweiterten Editor exakt:
   ```m
   fnStammdaten_Snapshot(Parameter_R06_Stammdaten)
   ```
   > Wichtig: genau diese eine Zeile – kein direkter Lakehouse-Zugriff hier,
   > sonst schlägt die Firewall an.

**3. In `SnapshotMap` eintragen.** In der Abfrage `Stammdaten_CoC` die Zeile
   `SnapshotMap = [ BUD = Snapshot_BUD, ARO_RGF = Snapshot_RGF, R03 = Snapshot_R03 ],`
   um das neue Szenario ergänzen:
   ```m
   SnapshotMap = [ BUD = Snapshot_BUD, ARO_RGF = Snapshot_RGF, R03 = Snapshot_R03, R06 = Snapshot_R06 ],
   ```

**4. Szenario-Zeilen in `Szenario_Konfig`.** Runde (laufendes GJ + Vorjahres-
   Basis) ergänzen:
   ```m
   {"R06", 10,  0, "Plan_R06", "snapshot", Parameter_R06_Stammdaten, "cause_of_change_R03", true},
   {"R06", 10, -1, "Actual_0", "snapshot", Parameter_R06_Stammdaten, "cause_of_change_R03", true},
   ```
   - Spalte `CoC_Spalte_Adjustments`: nur relevant für **manuelle** Werke aus
     `Manuelle_Adjustments.xlsx`. Reicht eine bestehende Spalte (z. B.
     `cause_of_change_R03`), einfach diese verwenden. Braucht die Runde eine
     **eigene** manuelle CoC-Spalte, siehe Hinweis unten.

**5. (Optional) Measures für Zahlen.** Soll die Runde eigene Werte im Bericht
   zeigen, in `0. Measuretabelle` zwei Measures nach Muster `RGF_Value` /
   `RGF_Periodic` anlegen – nur `Revenues[Szenario] = "R06"` als Filter tauschen.

**6. Aktualisieren.** Die Runde erscheint automatisch in `DIM_Szenario` (als
   Slicer) und in der Faktentabelle.

> **Nur neu einfrieren (kein neues Szenario)?** Dann genügt Schritt 1: das
> Datum des vorhandenen Parameters ändern und aktualisieren. Der Snapshot
> zieht dann den Stammdaten-Stand des neuen Stichtags.

> **Eigene manuelle CoC-Spalte je Runde:** Braucht die Runde in
> `Manuelle_Adjustments.xlsx` eine eigene Spalte `cause_of_change_R06`, dann
> (a) Spalte in der Excel ergänzen, (b) in den Abfragen `Man_Rev` und
> `Man_Stamm` in die Spaltenauswahl aufnehmen, (c) in `Revenues` im Schritt
> `ManCoC` mit `{"cause_of_change_R06", "Man_cause_of_change_R06"}` umbenennen.
> Für die meisten Runden ist das nicht nötig – eine bestehende Spalte genügt.

### 5.2a Forecast-Register: Runden dauerhaft nebeneinander (Budget vs 2+10 vs 5+7 vs 8+4 vs 10+2 vs Actual)

Ausgangslage im Quellsystem: Der **aktuelle** Forecast liegt immer auf `RGF`
(teils zusätzlich auf `RTD`, muss addiert werden). Beim Rollen auf die nächste
Runde wird der bisherige Forecast auf eine **andere** Planversion gesichert –
welche, ist variabel. Genau diese Variabilität bildet `Szenario_Konfig` als
**Register** ab: Beim Schließen einer Runde hältst du dort fest, auf welcher
Version + zu welchem Stammdaten-Stand die Runde eingefroren wurde.

**Modellprinzip – jede Runde ist eine eigene, unveränderliche Spur:**

- `RGF` bleibt „der aktuelle Forecast" (bewegt sich mit; Haupt-Report-Seiten
  nutzen weiter `RGF`). Ist der aktuelle FC = RGF **+** RTD, einfach beide
  Versionen als Zeilen unter `RGF` listen – sie summieren automatisch:
  ```m
  {"RGF", 3, 0, "Plan_RGF", "live_fy", null, "cause_of_change_fy", true},
  {"RGF", 3, 0, "Plan_RTD", "live_fy", null, "cause_of_change_fy", true},
  {"RGF", 3,-1, "Actual_0", "live_fy", null, "cause_of_change_fy", true},
  ```
- Jede **archivierte** Runde bekommt ein festes Szenario (`FC_02_10`,
  `FC_05_07`, `FC_08_04`, `FC_10_02` …) mit der Version, auf die sie gesichert
  wurde, und ihrem eigenen Stammdaten-Snapshot. Beispiel für eine auf `Plan_R03`
  gesicherte 8+4-Runde, Stammdaten-Stand 15.02.2026:
  ```m
  // Snapshot-Parameter + Blatt-Abfrage (einmalig je Runde):
  //   Parameter_FC0804_Stamm = #date(2026,2,15)
  //   Snapshot_FC0804        = fnStammdaten_Snapshot(Parameter_FC0804_Stamm)
  //   SnapshotMap: ... , FC_08_04 = Snapshot_FC0804
  {"FC_08_04", 5, 0, "Plan_R03", "snapshot", Parameter_FC0804_Stamm, "cause_of_change_fy", true},
  {"FC_08_04", 5,-1, "Actual_0", "snapshot", Parameter_FC0804_Stamm, "cause_of_change_fy", true},
  ```
  (Liegt die Runde auf mehreren Versionen, z. B. Basis + RTD, einfach mehrere
  `0`-Offset-Zeilen anlegen – sie addieren sich.)

**Ablauf beim Rollen auf eine neue Runde (Register-Eintrag):**

1. Notieren, auf welche Version das Quellsystem den bisherigen FC gesichert hat.
2. Snapshot-Parameter + `Snapshot_…`-Blatt-Abfrage + `SnapshotMap`-Eintrag für
   die Runde anlegen (Stammdaten-Stichtag der Runde).
3. In `Szenario_Konfig` die zwei (oder mehr) Zeilen der Runde ergänzen.
4. `RGF` auf den neuen aktuellen FC zeigen lassen (Version(en) tauschen).

**Vergleichsansicht bauen (ohne Measure je Runde):**

Matrix/Zebra-Tabelle: **Zeilen** = Net-New-Hierarchie (`DIM_Struktur`),
**Spalten** = `DIM_Szenario[Szenario]`, **Wert** = `[Wert_YTD]` (oder
`[Wert_Periodic]` für Monatswerte). Jede Runde erscheint automatisch als eigene
Spalte; neue Runde = neue Spalte, kein neues Measure. Reihenfolge der Spalten
steuert die Spalte `Sort` in `Szenario_Konfig` / `DIM_Szenario`.

### 5.3 Jahreswechsel (neues Geschäftsjahr)

1. Parameter `Geschäftsjahresbeginn` auf den neuen 1. des GJ setzen.
2. Budget-/Forecast-Snapshot-Parameter auf die neuen Stichtage.
3. `Abgeschlossene_Periode` zurück auf 0 (bzw. Stand des neuen GJ).
4. Aktualisieren. Kalender, FY_Offset und alle Measures ziehen automatisch nach.

---

## 6. Migration auf monatliche Lakehouse-Daten

Der Umstieg berührt **nur die Datenquelle**, nicht die Berichtslogik:

1. In `expressions.tmdl` die Abfrage **`SAP_Revenues`** auf die Lakehouse-
   Quelle umstellen. Zielspalten unverändert: `Werk`, `Werttyp`, `Version`,
   `Betrag`, `Geschäftsjahr`, `Buchungsperiode`.
2. In `tables/Revenues.tmdl` den Block **„2) YTD → Monatswerte" ersatzlos
   entfernen** und im weiteren Verlauf `MonatlicheWerte` durch `MitOffset`
   ersetzen. Der Block ist genau dafür klar markiert.
3. Alles Übrige (Szenario-Expansion, CoC-Freeze, MetricId, Measures) bleibt
   unverändert, weil YTD dort ausschließlich als Measure (`*_Value`) berechnet
   wird – nicht mehr in den geladenen Daten.

### Mehrjahresvergleiche (> 2 Jahre)

Aktuell decken die Szenarien `FY_Offset` 0/−1 ab (laufendes + Vorjahr). Für
weitere Jahre:

- `fnCoC_ZuMetricId` um die gewünschten Offsets erweitern (Zuordnung CoC →
  MetricId je Jahr).
- In `Szenario_Konfig` Zeilen mit den zusätzlichen `FY_Offset`-Werten ergänzen.
- `DIM_DATE` deckt den Zeitraum bereits ab (rollierend GJ-6 … GJ+3).

---

## 7. Measure-Konventionen

- `*_Periodic` = Monatswert (einfache SUM auf der monatlichen Faktentabelle).
- `*_Value` = YTD (kumuliert bis zur letzten Periode im Kontext; ohne
  Periodenfilter = Gesamtjahr) – berechnet über `DIM_DATE[FY_MonatNr]`.
- Szenario-Auswahl über `Revenues[Szenario]`; `MetricId <> 99` blendet
  „Like for Like" aus.
- Es wurden 15 im Bericht ungenutzte Measures entfernt; die verbleibenden 79
  werden alle in Visuals verwendet oder von diesen als Abhängigkeit benötigt.
  Namen, Formatstrings und Anzeigeordner blieben stabil, damit alle Visuals
  unverändert funktionieren.

---

## 8. Bekannte Prüfpunkte (nach dem ersten Refresh in Power BI Desktop)

Diese Punkte konnten ohne laufende Datenquellen nicht end-to-end verifiziert
werden – bitte beim ersten Refresh gegen den alten Bericht abgleichen:

1. **YTD→Monat-Differenzierung**: Kontrolle, dass Summe der Monatswerte je Werk
   dem letzten YTD-Wert der Quelle entspricht (Stichprobe 2–3 Werke).
2. **CoC-Freeze-Grenze**: `Abgeschlossene_Periode` testweise variieren und
   prüfen, dass die Umschaltung gefroren/live an der richtigen Periode greift.
3. **Szenario-Summen**: `ACT_Value`, `BUD_Value`, `RGF_Value` gegen die alten
   Werte je Ebene der Net-New-Hierarchie vergleichen.
4. **`Stammdaten_Historie`-Konvention** (Vormonat, Abschnitt 5.1) gegen deine
   tatsächliche Export-Kadenz prüfen.
