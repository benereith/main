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
`Vergleichszeitpunkt` (Vergleichszeitpunkte Sales/Retention), `Zeitfilter`
(MTD/YTD), `Granularität`, `Zeitansicht`, `KPI`, `Abgeschlossene Periode`.

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

**Die einzige Stelle im Modell, an der Szenarien, Forecast-Runden und
Berichtsjahre entstehen.** Vollständig datengetrieben: eine neue Runde, ein
neues Geschäftsjahr, ein neuer Snapshot = **eine neue Zeile hier** – kein
neuer Parameter, keine neue Abfrage, keine neue Funktion, kein Eingriff sonst
irgendwo im Modell.

| Spalte | Bedeutung |
|---|---|
| `Szenario` | Kürzel, erscheint 1:1 in `Revenues[Szenario]` / `DIM_Szenario` |
| `Sort` | Anzeigereihenfolge in `DIM_Szenario` |
| `Berichtsjahr_Start` | Absolutes Geschäftsjahr, auf das sich die Zeile bezieht |
| `FY_Offset` | Offset relativ zu `Berichtsjahr_Start` (0 = dieses Jahr, −1 = dessen Vorjahr) |
| `Werttyp_Version` | Quell-Version (z. B. `Plan_20`, `Actual_0`) |
| `CoC_Quelle` | `live` / `live_fy` / `live_ny` / `snapshot` – woher der Cause of Change kommt |
| `CoC_Snapshot` | Nur bei `snapshot`: Stichtag – Parameter **oder** Literal `#date(jjjj,mm,tt)` |
| `CoC_Snapshot_Spalte` | Nur bei `snapshot`: `"cause_of_change_fy"` (laufendes Jahr der Runde) oder `"cause_of_change_ny"` (kommendes Jahr) |
| `CoC_Spalte_Adjustments` | CoC-Spalte für manuelle Werke (Manuelle_Adjustments.xlsx) |
| `Perioden_Freeze` | `true` = abgeschlossene Perioden nutzen den eingefrorenen Monatsstand |

**Neue Runde/neues Berichtsjahr anlegen** – eine bis mehrere Zeilen anhängen,
Beispiel (im Code auch als auskommentiertes Muster hinterlegt):

```m
{"BUD_FY28", 30, A + 2,  0, "Plan_20",  "snapshot", #date(2027,8,31), "cause_of_change_ny", "cause_of_change_BUD", false},
{"BUD_FY28", 30, A + 2, -1, "Plan_RGF", "snapshot", #date(2027,8,31), "cause_of_change_ny", "cause_of_change_BUD", false},
{"BUD_FY28", 30, A + 2, -1, "Plan_R12", "snapshot", #date(2027,8,31), "cause_of_change_ny", "cause_of_change_BUD", false}
```

Der Snapshot-Stichtag kann direkt als Literal in die Zeile geschrieben werden
(kein neuer Parameter nötig) – oder auf einen bestehenden/neuen Parameter
verweisen, falls du das Datum lieber über die Power-Query-Parameter-UI statt
im Advanced Editor pflegen willst. Beides funktioniert gleichwertig.

Der gesamte Mechanismus dahinter (**ein** gemeinsamer Lakehouse-Rohdaten-Zugriff
+ dynamisches Filtern pro Konfig-Zeile) steht in Abschnitt 4.

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

## 4. Snapshots der Stammdaten (Forecast/Budget einfrieren) – voll modular

Du wolltest „auf einfache Art Snapshots der Stammdaten, um einen gefrorenen
Stand der Forecasts/des Budgets zu haben" – und zwar so, dass **beliebig
viele** dazukommen können, einfach als zusätzliche Zeile, weil der Bericht ab
jetzt laufend gepflegt wird (jedes künftige Geschäftsjahr bringt neues Budget,
neue Actuals, neue Forecast-Runden). Dafür ist die Snapshot-Mechanik
komplett datengetrieben aufgebaut:

- **`Stammdaten_Snapshots_Rohdaten`** – die **einzige** Abfrage im ganzen
  Modell, die für Snapshots auf das Lakehouse zugreift (`exports_md`,
  ungefiltert, komplett geladen). Ersetzt sowohl die früheren `md_BUD`/
  `md_RGF`/`md_R03` als auch die späteren `Snapshot_BUD`/`Snapshot_RGF`/
  `Snapshot_R03`/`Snapshot_BUD_FY27` – **eine** Abfrage für alle Runden,
  aller Berichtsjahre, für immer.
- **`fnStammdaten_Snapshot(rohdaten, datum, spalte)`** – rein funktional
  (kein Datenquellenzugriff mehr), filtert die geladenen Rohdaten auf
  Stichtag + CoC-Spalte. Wird pro Szenario aus `Stammdaten_CoC` aufgerufen.
- **`Stammdaten_CoC`** liest Datum und Spalte für jedes `snapshot`-Szenario
  **direkt aus `Szenario_Konfig`** (`CoC_Snapshot` / `CoC_Snapshot_Spalte`) –
  keine Zuordnungstabelle, kein Umweg mehr über benannte Einzelabfragen.

**Damit gilt: ein neuer Snapshot = eine neue Zeile in `Szenario_Konfig`,
sonst nichts.** Kein neuer Parameter, keine neue Abfrage, keine Änderung an
`Stammdaten_CoC`, `fnStammdaten_Snapshot` oder sonst irgendwo im Modell.
Genaues Vorgehen inkl. Beispiel in Abschnitt 3.1 und 5.2.

Formula-Firewall-Hinweis: `Stammdaten_Snapshots_Rohdaten` ist bewusst die
einzige Stelle mit direktem Lakehouse-Zugriff (keine Referenz auf andere
Abfragen); `Stammdaten_CoC` referenziert nur bereits geladene Ergebnisse
anderer Abfragen (keinen direkten Datenquellen-Zugriff mehr) – exakt das
Leaf/Combination-Muster, das schon bei `Stammdaten_Basis` funktioniert.

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

Alle Schritte in Power BI Desktop → **Daten transformieren** (Power-Query-Editor)
→ Abfrage `Szenario_Konfig` → Erweiterter Editor.
Beispiel: neue Runde „R06" mit Version `Plan_R06`, eingefroren zum 15.06.2026,
CoC-Stand zum GJ-Ende des laufenden Jahres.

**Einziger Schritt: Zeile(n) in `Szenario_Konfig` anhängen** (laufendes GJ +
Vorjahres-Basis):

```m
{"R06", 10, A,  0, "Plan_R06", "snapshot", #date(2026, 6, 15), "cause_of_change_fy", "cause_of_change_R03", true},
{"R06", 10, A, -1, "Actual_0", "snapshot", #date(2026, 6, 15), "cause_of_change_fy", "cause_of_change_R03", true},
```

Das Datum steht hier direkt als Literal in der Zeile – kein neuer Parameter,
keine neue Abfrage, keine Änderung an `SnapshotMap` (die gibt es nicht mehr)
nötig. Spaltenerklärung siehe Abschnitt 3.1. Danach **Aktualisieren** – die
Runde erscheint automatisch in `DIM_Szenario` (als Slicer) und in der
Faktentabelle.

- Spalte `CoC_Spalte_Adjustments`: nur relevant für **manuelle** Werke aus
  `Manuelle_Adjustments.xlsx`. Reicht eine bestehende Spalte (z. B.
  `cause_of_change_R03`), einfach diese verwenden. Braucht die Runde eine
  **eigene** manuelle CoC-Spalte, siehe Hinweis unten.
- **(Optional) Measures für eigene Zahlen.** Soll die Runde eigene Werte im
  Bericht zeigen, in `0. Measuretabelle` zwei Measures nach Muster `RGF_Value`
  / `RGF_Periodic` anlegen – nur `Revenues[Szenario] = "R06"` als Filter
  tauschen. Ohne eigenes Measure ist die Runde trotzdem sofort über die
  generischen `Wert_YTD`/`Wert_Periodic` + `DIM_Szenario[Szenario]` sichtbar
  (siehe Abschnitt 5.2a).

> **Nur neu einfrieren (bestehende Runde, kein neues Szenario)?** Dann in der
> betroffenen Zeile nur das Datum in `CoC_Snapshot` ändern und aktualisieren.

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
**Konkrete Zuordnung in diesem Modell** (Version-Mapping des Controllings):

| Runde | Version(en) | Szenario | CoC-Stand |
|---|---|---|---|
| Budget | Plan_20 / Plan_35 | `BUD` | Snapshot (Budget) |
| 2+10 | Plan_R03 | `R03` | Snapshot (R03) |
| 5+7 | Plan_RGF (ohne R12) | `FC57` | live (umstellbar) |
| 8+4 (aktuell) | Plan_RGF + Plan_R12 | `RGF` | live |
| 10+2 | Plan_35 + Plan_RTD | `P35` | live |
| Actual | Actual_0 | `ACT` | live |

Diese Runden tragen in `DIM_Szenario` die Spalte **`Runde`** (Budget/2+10/5+7/
8+4/10+2/Actual, korrekt sortiert). 5+7 und 8+4 teilen sich die `Plan_RGF`-Basis
– 8+4 ist 5+7 **plus** den `Plan_R12`-Aufsatz.

- Jede weitere **archivierte** Runde bekommt ein festes Szenario mit der
  Version, auf die sie gesichert wurde, und ihrem eigenen Stammdaten-Snapshot
  – als **eine Zeile** in `Szenario_Konfig` (kein Parameter, keine Abfrage
  nötig, siehe Abschnitt 4/5.2). Beispiel für eine auf `Plan_R03` gesicherte
  Runde, Stammdaten-Stand 15.02.2026, Berichtsjahr = laufendes GJ (`A`):
  ```m
  {"FC_08_04", 5, A, 0, "Plan_R03", "snapshot", #date(2026,2,15), "cause_of_change_fy", "cause_of_change_R03", true},
  {"FC_08_04", 5, A,-1, "Actual_0", "snapshot", #date(2026,2,15), "cause_of_change_fy", "cause_of_change_R03", true},
  ```
  (Liegt die Runde auf mehreren Versionen, z. B. Basis + RTD, einfach mehrere
  `0`-Offset-Zeilen anlegen – sie addieren sich.)

**Ablauf beim Rollen auf eine neue Runde (Register-Eintrag):**

1. Notieren, auf welche Version das Quellsystem den bisherigen FC gesichert hat.
2. In `Szenario_Konfig` die zwei (oder mehr) Zeilen der Runde ergänzen – Datum
   direkt als Literal, keine weiteren Schritte.
3. `RGF` auf den neuen aktuellen FC zeigen lassen (Version(en) tauschen).

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

## 6. Lakehouse-Anbindung (umgesetzt)

Die Revenue-Quelle läuft jetzt über das **Reporting-Warehouse** statt der Excel:

1. **`SAP_Revenues`** liest per nativer SQL (`Sql.Database(Reporting_Server,
   Reporting_Datenbank, [Query=…])`) direkt **monatliche** Werte (`Betrag_Monat`).
   Server/DB stehen als Parameter in „1. Konfiguration". Die alte Excel-Variante
   (`Revenues_SAP.xlsx`, YTD) liegt in der Git-Historie.
2. **`Revenues`** differenziert nur noch die **manuellen** Zeilen (Man_Rev, YTD)
   auf Monatswerte; SAP wird als bereits monatlich durchgereicht (`if IstMan
   then <diff> else <wert>`).
3. Alles Übrige (Szenario-Expansion, CoC-Freeze, MetricId, Measures) bleibt
   unverändert, weil YTD ausschließlich als Measure (`*_Value`) berechnet wird.

> **Zu prüfen — Granularität der manuellen Adjustments:** Aktuell als **YTD**
> behandelt (unverändert wie vor dem Umstieg). Sind eure manuellen Werte
> **monatlich** erfasst, im markierten Block in `Revenues.tmdl` die Bedingung
> auf „nie differenzieren" setzen (Kommentar dort). 
>
> **Zu prüfen — `Werk` = `Object_group`:** wird nach `Int64` gecastet. Falls
> `Object_group` nicht-numerische Werke enthält, dort den Typ anpassen.
>
> **Mehrjahr:** die `IN (…)`-Liste in `SAP_Revenues` um weitere Jahre erweitern
> bzw. auf `>= Aktuelles_Geschäftsjahr - 1` umstellen.

### Net New in % des Vorjahresumsatzes

Kennzahl `Net New % (Forecast/Actual)` bzw. `(Budget)` = Net New / `Vorjahresumsatz`.
Die **Basis** (`Vorjahresumsatz`) ist berichtsjahr-abhängig:
- **FY26** → Planversion **35** des Vorjahres (`FY_Offset = -1`) — so umgesetzt.
- **FY27** → **RGF + R12** des FY26. Setzt die Berichtsjahr-Erweiterung voraus
  (dann wird die Basis-Version je Berichtsjahr umgeschaltet).

### Mehrjahr / Berichtsjahr (umgesetzt für FY26 + FY27)

Die Engine ist jetzt **berichtsjahr-fähig**:
- `Szenario_Konfig` trägt je Zeile ein **`Berichtsjahr_Start`** (absolutes GJ);
  `FY_Offset` ist der Offset **relativ dazu**. Absolutes Quelljahr =
  `Berichtsjahr_Start + FY_Offset`. Dadurch kann dasselbe FY26-Jahr sowohl als
  „laufend" (FY26) als auch als „Vorjahr" (FY27) auftreten.
- **`MetricId`** wird aus dem **relativen** Offset zum Berichtsjahr gebildet –
  die Net-New-Zerlegung stimmt damit je Berichtsjahr.
- **CoC-Kennzeichen je Jahr:** FY26 nutzt `cause_of_change_fy` (`live_fy`),
  FY27 als kommendes Jahr `cause_of_change_ny` (Option `live_ny` bzw. für
  eingefrorene Snapshots die Spalte an `fnStammdaten_Snapshot` übergeben,
  siehe unten).
- **`DIM_Berichtsjahr`** (FY26/FY27) als Slicer; **`SAP_Revenues`** zieht alle
  Jahre ab Vorjahr (`Fiscal_Year >= Aktuelles_Geschäftsjahr - 1`).
- **FY26-Measures bleiben unverändert**, weil ihre Szenarien (BUD/ACT/RGF …)
  nur FY26-Zeilen enthalten. **FY27 = Szenario `BUD_FY27`** (Runde „Budget FY27"),
  sichtbar über die generischen `Wert_YTD`/`Wert_Periodic` + `DIM_Szenario[Runde]`.

#### CoC-Snapshot für Budget FY27 (eingefroren)

Der Snapshot-Mechanismus ist seit Abschnitt 4 vollständig datengetrieben:
`fnStammdaten_Snapshot(rohdaten, snapshotDatum, cocSpalte)` liest die einmal
geladenen Rohdaten (`Stammdaten_Snapshots_Rohdaten`) und filtert dynamisch.
`cocSpalte = "cause_of_change_fy"` = Stand zum GJ-Ende des laufenden Jahres,
`"cause_of_change_ny"` = Stand im kommenden Geschäftsjahr.

Für Budget FY27 stehen in `Szenario_Konfig` beide `BUD_FY27`-Zeilen auf
`CoC_Quelle = "snapshot"`, `CoC_Snapshot = Parameter_BUD_FY27_Stammdaten`,
`CoC_Snapshot_Spalte = "cause_of_change_ny"`. **Kein `SnapshotMap`, keine
eigene Blatt-Abfrage mehr nötig** – das ist bereits der generelle Mechanismus
aus Abschnitt 4/5.2, hier nur mit `_ny` statt `_fy` als Spalte.

`Parameter_BUD_FY27_Stammdaten` ist aktuell ein **Platzhalter** (`31.08.2026`,
analog ~1 Monat vor GJ-Beginn wie beim FY26-Budget) – auf den tatsächlichen
Freeze-Stichtag setzen.

**Weitere FY27-Sichten hinzufügen** (Actuals FY27, FC FY27 …) oder ein
komplett neues Berichtsjahr (FY28 …): genau wie in Abschnitt 5.2 beschrieben
– eine Szenario-Zeilengruppe mit dem passenden `Berichtsjahr_Start` anhängen
(laufend = neues Jahr, Vorjahr = Basis-Jahr), `CoC_Snapshot_Spalte` je nach
Distanz zum heutigen Jahr `"cause_of_change_fy"` (dieses Jahr) oder
`"cause_of_change_ny"` (nächstes Jahr) – für weiter entfernte Jahre ggf. eine
neue Spalte in `exports_md`, falls das Quellsystem so weit vorausklassifiziert.

**Offen / zu prüfen:**
- **Freeze-Stichtag `Parameter_BUD_FY27_Stammdaten`** ist ein Platzhalter –
  auf den echten Termin setzen (siehe oben).
- **FY27-Budget-Version** als `Plan_20` angenommen – bitte bestätigen.
- **Net New % für FY27**: `Vorjahresumsatz` ist aktuell FY26-fix (Plan_35). Für
  FY27 ist die Basis RGF+R12 (steckt bereits in `BUD_FY27`s Vorjahres-Zeilen);
  ein berichtsjahr-abhängiger Nenner kann ergänzt werden.
- `DIM_DATE` deckt den Zeitraum ab (rollierend GJ-6 … GJ+3).

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
