# Flash-Bericht – Neuaufbau

Betrifft `Flash/Flash_Basis.SemanticModel` (Modell) und `Flash/Flash_Basis.Report` (Bericht).
Vollständige Objektliste mit Beschreibungen: [`modellreferenz.md`](modellreferenz.md).
Einrichtung der Kommentarfunktion: [`kommentare/README.md`](kommentare/README.md).

## 1. Was neu ist

| Wunsch | Umsetzung |
| --- | --- |
| Schalter „Kanne abgerechnet" | Steuertabelle `p_Kanne_Abrechnung`, Slicer auf *Flash* und *Unit-Detail*. Bei **Ja** zählen alle Kanne-Units als Actuals, bei **Nein** gilt die normale Statuslogik. Wirkt in der Measure `Flash`, ohne Refresh. |
| Vergangene Monate ziehen | Die Faktenabfrage lädt `Startperiode` bis `Aktuelle_Periode` (Standard: Oktober bis Berichtsmonat). Monats-Slicer und Schalter *Einzelmonat / Kumuliert (YTD)* im Bericht. |
| „Kein Kennzeichen" | Hat eine Unit in einem Monat weder Actuals (0), Budget (20) noch Forecast (RF, RGF, 35, R12, RTD), ist sie **Inaktiv** und fällt aus dem Flash. „Kein Kennzeichen" **mit** Werten bleibt eine echte Kennzeichnung und wird als Actuals gerechnet. |
| Aktueller FC | `Forecast` = RGF + R12. Die übrigen Forecast-Stände zählen nur für die Prüfung „hat Forecastwerte". |
| Kommentierung | Translytical Task Flow, siehe `kommentare/README.md`. |
| „State of the art" | Sternschema, schmale Faktentabelle, Logik in Power Query statt berechneter Spalten, eine zentrale Zeitlogik, `///`-Beschreibungen für jedes Objekt, neues Berichtslayout und Theme. |

## 2. Modell

```
                 Dim_Unit                    Dim_Datum
                 (Stammdaten)                (Monate)
                     │ 1                        │ 1
                     │ n                        │ n
                     └────────►  Dim_UnitStatus ◄┘      Werk × Periode
                                 │ 1        │ 1
                                 │ n        │ n
                              Fakt_SAP   Kommentare     (DirectQuery)
                                 │ n
                                 │ 1
                              Dim_Konto
```

`Dim_UnitStatus` sitzt bewusst zwischen den Dimensionen und den Fakten. Der Abrechnungsstatus gilt je
Werk **und** Periode; nur so rechnet jeder Monat mit „seinem" Status, und Unit-Zählungen (Datenlage)
respektieren Unit- und Monatsfilter. Alle Beziehungen sind Viele-zu-Eins in eine Richtung, es gibt
keine mehrdeutigen Pfade.

| Tabelle | Zweck |
| --- | --- |
| `Fakt_SAP` | Werk × Periode × Konto × Version, im Warehouse aggregiert, vier Spalten |
| `Dim_UnitStatus` | Status, Datenlage und Flash-Szenario je Werk × Periode |
| `Dim_Unit` | Stammdaten und Organisationshierarchie |
| `Dim_Datum` | Geschäftsjahr Oktober bis September, taggenau |
| `Dim_Konto` | GuV-Hierarchie, Kennzahl-Zuordnung Umsatz / CoS / Overhead |
| `Kommentare` | Berichtskommentare aus Fabric SQL (DirectQuery) |
| `_Kennzahlen` | alle Measures, in Anzeigeordnern |
| `p_Zeitbezug`, `p_Kanne_Abrechnung`, `p_TopN`, `p_Kategorie`, `p_Eingabe` | Steuertabellen ohne Beziehung |

Nicht geladene Quellabfragen (Power-Query-Gruppe *Staging*): `Quelle_Unit`, `Quelle_Übergabe`,
`Quelle_Datenlage`, `Quelle_SAP`. Parameter und Listen stehen in der Gruppe *Parameter*.

## 3. Fachlogik

### Status je Werk und Periode (`Dim_UnitStatus[Status]`)

| Status | Bedingung |
| --- | --- |
| Inaktiv | weder Actuals (0) noch Budget (20) noch Forecast (RF/RGF/35/R12/RTD) mit Wert ≠ 0 |
| Abgerechnet | FIBU-Übergabe im Monat |
| Flash | Flash-Übergabe im Monat |
| Offen | FIBU-Übergabe im Vormonat |
| Kein Kennzeichen | sonst |

### Szenario (`Dim_UnitStatus[Flash_Szenario]`)

| Szenario | Bedingung | zählt im Flash |
| --- | --- | --- |
| Ohne Wertung | Status Inaktiv | nichts |
| ACT | Innenauftragsart I oder N, oder Status Abgerechnet / Kein Kennzeichen | `Act` |
| FC | Status Offen, oder Status Flash bei Vertragsart PR / M / XK / XP | `Forecast` |
| V | alles Übrige | `Version V` |

### Zeit

- Ohne Monatsauswahl zeigt der Bericht den **Berichtsmonat** (Parameter `Aktuelle_Periode`).
- Mehrere gewählte Monate werden im Einzelmonat-Modus summiert.
- *Kumuliert (YTD)* summiert vom Geschäftsjahresbeginn bis zum spätesten gewählten Monat.
- Die gesamte Zeitlogik steckt in einer Measure (`_Wert P&L`). Act, Budget, Forecast, Flash, Quoten,
  Flex und Rang folgen automatisch.

### Flop-Listen

Rang nach `Flex CoS`, `Flex OvH` bzw. `Act`, gewertet über alle im Bericht gewählten Units. Die Anzahl
(5 bis 50, Standard 20) stellt der Slicer *Anzahl Flop-Units* ein. CoS und Overhead berücksichtigen nur
Units mit Ist-Umsatz > 0, wie bisher.

## 4. Bericht

Alle Seiten 1920 × 1080, Raster 8 px, Filterleiste rechts, Navigation oben. Slicer sind seitenübergreifend
synchronisiert (Monat, Zeitbezug, Kanne, Organisation, Status, Anzahl).

| Seite | Frage, die sie beantwortet |
| --- | --- |
| **Flash** | Wo stehen Flash, Act, Forecast und Budget, und wo entsteht die Abweichung? KPI-Leiste, GuV-Matrix, Wasserfall, Kommentare |
| **Flop 20 CoS** | Welche Units haben die größte ungeplante CoS-Quote? |
| **Flop 20 Overhead** | Dasselbe für die Overhead-Quote |
| **Flop UPC** | Welche Units haben das niedrigste Act-Ergebnis? |
| **Datenlage** | Welche Units sind inaktiv oder ohne Kennzeichen? (immer Berichtsmonat) |
| **Kommentare** | Kommentare erfassen und nachlesen |
| **Unit-Detail** | Ausgeblendete Drillthrough-Seite: Rechtsklick auf eine Unit → *Drillthrough* |

Berichtsfilter wie bisher: Innenauftragsart ≠ P, Typ = P&L, GuV Ebene 2 ≠ „PI - Purchasing Income".
Auf den Flop-CoS- und -Overhead-Seiten zusätzlich Vertragsart ∉ M, PR, XK, XP.

## 5. Umbenennungen (alt → neu)

| Alt | Neu |
| --- | --- |
| `V_SAP_EXPORTS_cleansed` | `Fakt_SAP` (Spalten `Konto`, `Version`, `Wert`, `Status_Key`) |
| `sap_master_data_unit` | `Dim_Unit` (`betrieb` → `Werk`, `bezeichnung_management` → `Managementbereich`, `bezeichnung_region` → `Region`, `bezirk` → `Bezirk`, …) |
| `DIM_DATE` | `Dim_Datum` |
| `tab_accounts_hierarchy` | `Dim_Konto` (`Level_n_Key` → `GuV Ebene n`, `Type` → `Typ`, `Kostenart` → `Konto`) |
| `Übergabedatum` | `Quelle_Übergabe` (nicht mehr geladen) |
| `0_Measuretabelle` | `_Kennzahlen` |
| `ACT_Value_P&L` / `BUD_Value_P&L` / `FC_Value_P&L` / `V_Value_P&L` | `Act` / `Budget` / `Forecast` / `Version V` |
| `Act_Rev` | `Act Umsatz` |
| `Act_Ratio_CoS` / `FC_Ratio_CoS` / `Delta_Cos` | `Act CoS-Quote` / `FC CoS-Quote` / `Delta CoS-Quote` |
| `Act_Ratio_OvH` / `FC_Ratio_OvH` / `Delta_OvH` | `Act OvH-Quote` / `FC OvH-Quote` / `Delta OvH-Quote` |
| `Rang_Filter` | `Rang Flex CoS`, `Rang Flex OvH`, `Rang Act` |
| `pBerichtsmonat` | entfällt, der Monat ergibt sich aus `Geschäftsjahr` + `Aktuelle_Periode` |

**Entfernt:** `SPLY` (lieferte ohne geladenes Vorjahr nie Werte), die ungenutzte Tabelle
`Abgeschlossene Periode`, die automatischen Datums-Hilfstabellen (Auto-Datum/Zeit ist aus), der
Custom Visual *Zebra BI Tables* (ersetzt durch die native Matrix) und der Berichtsfilter „Status ist
nicht leer" (konnte nie greifen).

Wer weitere Berichte auf `Flash_Basis` aufgesetzt hat, muss deren Feldverweise entsprechend anpassen.

## 6. Annahmen und Grenzen

- **Keine Statushistorie.** `IA_Stammdaten.XLSX` enthält je Werk nur das letzte Übergabedatum. Für
  Monate vor diesem Datum ergibt die Regel „Kein Kennzeichen" und damit Actuals. Für abgeschlossene
  Monate ist das fachlich passend, aber keine echte Historie. Wer den damaligen Status braucht,
  muss ihn monatlich als Schnappschuss ablegen.
- **Vorzeichen.** Abweichung = Flash minus Vergleichswert. „Positiv = besser" gilt nur, wenn Kosten in
  den SAP-Daten negativ geführt werden. Die Farben (grün/rot) und die Flop-Sortierung gehen davon aus.
- **„Hat Werte" heißt Wert ≠ 0.** Reine Nullzeilen in SAP machen eine Unit nicht aktiv.
- **Fremde Werke.** Faktenzeilen von Werken ohne Stammdatensatz (andere Managementbereiche) werden beim
  Laden verworfen. Vorher erschienen sie als leere Unit.
- **Version V** ist nur als Bezeichnung der SAP-Version übernommen; die fachliche Bedeutung ist im Modell
  nicht beschrieben.
- **Rangfunktion.** Die Flop-Filter rechnen je Unit über alle Units. Bei sehr vielen Units kann das
  Rendern der Flop-Seiten dauern; im Zweifel den Filter *Im Top N …* am Visual deaktivieren.
- **Datenschutzebenen.** `Dim_UnitStatus` und `Fakt_SAP` kombinieren Dataflow, SharePoint und
  Warehouse. Unterschiedliche Datenschutzebenen führen zu `Formula.Firewall`.

## 7. Beim ersten Öffnen

1. Parameter prüfen: `Geschäftsjahr`, `Startperiode`, `Aktuelle_Periode`. Die beiden `Kommentar_…`-
   Parameter zeigen auf einen Platzhalter, bis die Kommentarfunktion eingerichtet ist.
2. Beim ersten Aktualisieren die **nativen Abfragen freigeben** (zwei neue SQL-Texte: `Quelle_SAP`, `Quelle_Datenlage`).
3. Nach dem Refresh stichprobenartig prüfen:
   - `Dim_UnitStatus` hat Werke × Perioden Zeilen.
   - Die Summe `Act` im Berichtsmonat stimmt mit dem bisherigen Bericht überein (Abweichungen nur durch
     die verworfenen Fremd-Werke, siehe Abschnitt 6).
   - Schalter *Kanne abgerechnet* verändert nur den Kanne-Anteil von `Flash`.
4. Datenschutzebenen prüfen, falls `Formula.Firewall` auftritt.

## 8. Qualitätssicherung

Geprüft, bevor die Dateien committet wurden:

- Modell mit dem TMDL-Parser aus `Microsoft.AnalysisServices.Tabular` geladen (derselbe, der in Desktop
  den Formatfehler gemeldet hatte).
- Alle DAX-Referenzen auf Existenz geprüft, Ringabhängigkeiten gesucht, Beziehungen auf Datentypen und
  mehrdeutige Pfade, `///`-Beschreibung an jedem Objekt.
- Alle 22 M-Abfragen mit dem Power-Query-Parser von Microsoft syntaktisch geprüft, Schrittnamen und
  Parameter aufgelöst; `sourceColumn`-Namen gegen die Ausgabespalten der Abfragen abgeglichen.
- Bericht mit `powerbi-report-author validate` samt veröffentlichter JSON-Schemas geprüft (0 Fehler,
  0 Warnungen), jede Feldreferenz gegen das Modell, 8-px-Raster, Überlappungen, Alt-Texte.

**Nicht möglich:** Power BI Desktop und eine Datenverbindung standen nicht zur Verfügung. Daher sind weder
DAX noch M **ausgeführt**, und das Berichtslayout wurde nicht gerendert. Formatierungs-Details (Slicer-Höhen,
Kartenabstände, Spaltenbreiten) bitte beim ersten Öffnen kurz ansehen.
