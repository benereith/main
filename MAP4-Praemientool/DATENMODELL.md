# MAP4 Prämientool – Datenmodell

Dokumentation des umgebauten Semantikmodells. Ziel des Umbaus: eindeutige Filterwege,
keine M:N-Beziehungen, sauberer Split Pacht/Mandat und ein Schalter für die Prämienarten.

## Namenskonvention

| Präfix  | Bedeutung                                                              |
|---------|------------------------------------------------------------------------|
| `F_`    | Faktentabelle                                                          |
| `dim_`  | Dimension, filtert immer nur in eine Richtung nach unten                |
| `brg_`  | Brückentabelle für echtes M:N                                          |
| `tab_`  | Parameter-/Konfigurationstabelle (keine Dimension)                     |
| `sw_`   | beziehungsloser Schalter (What-if), wird nur per Measure ausgelesen     |
| `_`     | Measure-Tabelle                                                        |

## Struktur

```
                     dim_Person
                          │
              brg_Person_Betrieb  ◄── einzige bidirektionale Beziehung
                          │
  Retention ── dim_Region ┤
                          │
     dim_PachtMandat ─────┼──── dim_Betrieb ────┬── dim_Innenauftrag
            │             │          │          ├── Personaldaten
            │             │          │          └── Compliance
            │             │          ▼
            │             │        F_SAP ◄── dim_Konto
            │             │          ▲
            │             │          ├── dim_Szenario
            │             │          └── dim_Periode
            │
   tab_Prämienpunkte ── dim_Praemienart

   sw_Ergebnisziel     sw_HSE_TRIFR      (ohne Beziehung, nur per Measure gelesen)
```

## Beziehungen im Detail

`relationships.tmdl` enthält bewusst keine Kommentare: `///` ist in TMDL eine
Objektbeschreibung, und `relationship` hat in TOM keine Description-Eigenschaft.
Ein `///` dort bricht den Parser. Deshalb steht die Erklärung hier.

| Von | Nach | Richtung | Zweck |
|---|---|---|---|
| `F_SAP[Object_group]` | `dim_Betrieb[betrieb]` | → | Betriebsnummer in den SAP-Exporten |
| `F_SAP[Account]` | `dim_Konto[Kostenart_Key]` | → | numerischer Schlüssel; vorher lief die Beziehung von `Account` (Ganzzahl) auf `Kostenart` (Text) |
| `F_SAP[Szenario_Key]` | `dim_Szenario[Szenario_Key]` | → | Budget/FC über `SAP_Version\|YTD-YTG` |
| `F_SAP[Perioden_Key]` | `dim_Periode[Perioden_Key]` | → | Geschäftsjahr × Periode |
| `dim_Betrieb[Pacht/Mandat]` | `dim_PachtMandat[Pacht/Mandat]` | → | Split wirkt auf alle Fakten |
| `tab_Prämienpunkte[Vertragsart]` | `dim_PachtMandat[Pacht/Mandat]` | → | zweiter Ast derselben Dimension – **ersetzt die M:N** |
| `tab_Prämienpunkte[Prämienziel]` | `dim_Praemienart[Prämienziel]` | → | Prämienart als Dimension |
| `dim_Betrieb[region]` | `dim_Region[region_key]` | → | eine einzige Region-Achse |
| `Retention[Region]` | `dim_Region[region_key]` | → | vorher gleichzeitig an Innenauftrag und Unit |
| `dim_Innenauftrag[betrieb]` | `dim_Betrieb[betrieb]` | → | nachgelagerte Dimension, nur Zusatzattribute |
| `Personaldaten[Betrieb]` | `dim_Betrieb[betrieb]` | → | |
| `Compliance[Betrieb]` | `dim_Betrieb[betrieb]` | → | |
| `brg_Person_Betrieb[Vollname]` | `dim_Person[Vollname]` | → | Person filtert ihre Zuordnungen |
| `dim_Betrieb[Abrechnungsbetrieb]` | `dim_Abrechnungseinheit[Abrechnungsbetrieb]` | → | Betriebeset: mehrere Betriebe, eine Abrechnung |
| `brg_Person_Betrieb[Betrieb]` | `dim_Betrieb[betrieb]` | **↔** | einzige bidirektionale Beziehung, Brückenmuster |
| `Personaldaten[Vollname]` | `dim_Person[Vollname]` | *inaktiv* | aktiv entstünde ein Filterkreis |

Die bidirektionale Brückenbeziehung ist nötig, damit eine ausgewählte Person bis auf die
Fakten durchfiltert (`dim_Person → brg → dim_Betrieb → F_SAP`). Die Gegenrichtung erlaubt es,
zu einem ausgewählten Betrieb die Verantwortlichen über `brg_Person_Betrieb[Vollname]`
anzuzeigen. Sie bleibt eindeutig, weil `brg_Person_Betrieb` mit keiner weiteren Tabelle
verbunden ist.

## Was die M:N-Beziehung ersetzt hat

Vorher:

```
sap_master_data_innenauftrag[Pacht/Mandat] <--> Prämienvereinbarungen[Vertragsart]
   many-to-many, crossFilteringBehavior: bothDirections
```

Jede Auswahl eines Prämienziels filterte über diese Beziehung auf die Innenaufträge
zurück und von dort über `betrieb` in die gesamte Faktenwelt.

Nachher: `dim_PachtMandat` ist eine gemeinsame Dimension, die **beide** Seiten von oben
mit 1:n und Einwegfilter filtert.

```
dim_PachtMandat ──► dim_Betrieb        ──► F_SAP
dim_PachtMandat ──► tab_Prämienpunkte
```

Ein Slicer auf `dim_PachtMandat[Pacht/Mandat]` splittet damit Umsatz, UP und Prämienpunkte
gleichzeitig – ohne Rückfilterung und ohne Mehrdeutigkeit.

## Szenarien: Budget und FC

`dim_Szenario` bildet die Versionslogik über den zusammengesetzten Schlüssel
`SAP_Version|YTD-YTG` ab. `F_SAP[Szenario_Key]` wird in Power Query erzeugt.

| Szenario | SAP_Version | YTD/YTG | Szenario_Key |
|----------|-------------|---------|--------------|
| Budget   | 20          | YTD     | `20\|YTD`    |
| Budget   | 20          | YTG     | `20\|YTG`    |
| FC       | 0           | YTD     | `0\|YTD`     |
| FC       | RGF         | YTG     | `RGF\|YTG`   |
| FC       | R12         | YTG     | `R12\|YTG`   |

- **Budget** = SAP-Version 20 über alle Perioden.
- **FC** = YTD aus Version 0 (Actuals) + YTG aus RGF und R12.

Die Grenze zwischen YTD und YTG steuert weiterhin der Parameter `YTD/YTG` (aktuell `9`).
Kommt eine Version dazu, wird sie hier ergänzt – keine Measure muss angefasst werden.

## Kennzahlen

| Measure          | Definition                                                      |
|------------------|-----------------------------------------------------------------|
| `UP`             | Summe über **alle** Konten mit `dim_Konto[Type] = "P&L"`         |
| `Revenue`        | `UP`, zusätzlich auf `Level_2_Key = "IS10000_T - Total Revenue inkl. IFRS/ NEUTRA/MGMT"` |
| `Revenue Budget` / `Revenue FC` | `Revenue` je Szenario                            |
| `UP Budget` / `UP FC`           | `UP` je Szenario                                 |

Der Split Pacht/Mandat läuft im Regelfall über `dim_PachtMandat[Pacht/Mandat]` als Feld.
Für feste Gegenüberstellungen in einem Visual gibt es zusätzlich `... Pacht` / `... Mandat`
im Ordner `03 Pacht-Mandat`.

## Schalter für die Prämienarten

Zwei beziehungslose Tabellen, je ein Slicer, unabhängig voneinander:

- `sw_Ergebnisziel[Ergebnisziel Compass Group Deutschland]` → erreicht / nicht erreicht
- `sw_HSE_TRIFR[HSE-TRIFR]` → erreicht / nicht erreicht

`[Prämienpunkte erreicht]` multipliziert die Punkte je Prämienziel mit dem Faktor des
zugehörigen Schalters. Weil die Schaltertabellen keine Beziehung haben, filtern sie keine
einzige Faktenzeile weg – die Auswahl wirkt konzernweit auf alle Prämienberechtigten.

Ohne Auswahl (oder bei Mehrfachauswahl) gilt bewusst „nicht erreicht" (Faktor 0).

**Neues Prämienziel:** taucht automatisch in `dim_Praemienart` auf, zählt aber mit 0 Punkten,
bis es in `[Prämienpunkte erreicht]` und ggf. mit einer eigenen `sw_`-Tabelle ergänzt wird.

## Zielerreichung und Prämienpunkte

Jedes Prämienziel bekommt in `dim_Praemienart[Zielart]` einen fachlichen Code. Der Code
steuert, welche Logik ausgewertet wird:

| Zielart | Logik | Erreicht wenn |
|---|---|---|
| `ERGEBNIS_CGD` | Schalter `sw_Ergebnisziel` | manuell auf „erreicht" gesetzt |
| `HSE_TRIFR` | Schalter `sw_HSE_TRIFR` | manuell auf „erreicht" gesetzt |
| `UMSATZ` | `[Revenue FC] - [Revenue Budget]` | Delta ≥ 0 |
| `UP` | `[UP FC] - [UP Budget]` | Delta ≥ 0 |
| `COMPLIANCE` | `Compliance[Status Zielerfüllung]` | **alle** Betriebe im Kontext tragen „ja" |
| `UNBEKANNT` | – | nicht gemappt, zählt mit 0 Punkten |

`[Prämienpunkte erreicht]` läuft über die Punktetabelle und multipliziert je Zeile die Punkte
mit der Zielerreichung der zugehörigen Zielart. Die Punkte folgen dabei automatisch der
Vertragsart (Pacht/Mandat) der Betriebe im Filterkontext.

Zwei Details, die in der Praxis leicht schiefgehen:

- **`TREATAS` auf die Vertragsart.** `dim_Betrieb → dim_PachtMandat` filtert bewusst nur in
  eine Richtung. Ohne `TREATAS` würden bei einem Pacht-Betrieb auch die Mandats-Punkte
  mitgezählt. Das betrifft `[Prämienpunkte max]` und `[Prämienpunkte erreicht]`.
- **Zielmeasures vor dem `SUMX` in Variablen.** Sonst würde die Kontextübertragung sie je
  Punktezeile neu und falsch berechnen.

### Zielart pflegen

In `dim_Praemienart` (Power Query → Erweiterter Editor), Block `HIER PFLEGEN`. Der Text links
muss **exakt** dem Prämienziel in `Prämienvereinbarung Pacht.xlsx` entsprechen. Nicht gemappte
Ziele bekommen `UNBEKANNT`; `[Kontrolle Prämienziele ohne Zielart]` zeigt, wie viele das sind.

## Betriebeset: mehrere Betriebe, eine Abrechnung

Manche Personen verantworten mehrere Betriebe, werden aber nur über einen davon abgerechnet.
Das lässt sich nicht aus den Stammdaten ableiten und wird in `tab_Betriebeset` **manuell**
gepflegt (Power Query → Erweiterter Editor, Block `HIER PFLEGEN`):

```
{Betrieb, Abrechnungsbetrieb, "Kommentar"}
{1234,    1200,               "1234 wird über 1200 abgerechnet"}
```

Nur Ausnahmen eintragen – jeder Betrieb ohne Eintrag rechnet sich selbst ab.

Daraus entsteht `dim_Betrieb[Abrechnungsbetrieb]` und darüber die Dimension
`dim_Abrechnungseinheit`. **Das ist der Trick:** Sobald
`dim_Abrechnungseinheit[Abrechnungseinheit]` in einem Visual auf den Zeilen liegt,
aggregieren Umsatz, UP, Compliance und alle Zielmeasures automatisch über das gesamte Set.
Es braucht dafür keine Sonder-Measure.

`[Betriebe der Abrechnungseinheit]` listet zur Kontrolle alle Betriebe der Einheit als Text.

## Person ↔ Betrieb: bekannte Doppelzählung

Die Zuordnung ist echtes M:N – eine Person verantwortet mehrere Betriebe, und ein Betrieb
kann durch unterjährige Verantwortungswechsel mehrere Personen haben. In der Quelle
(SharePoint-Betriebeliste) stehen **keine Gültigkeitszeiträume**.

Folge: Ein Betrieb mit mehreren Verantwortlichen wird jeder dieser Personen in voller Höhe
zugerechnet. Die Summe über alle Personen ist dann größer als der Gesamtwert.

Die Measure `[Betriebe mit mehreren Verantwortlichen]` macht die betroffenen Fälle sichtbar.
Sobald in der Quelldatei Gültig-von/bis gepflegt wird, lässt sich das periodengenau auflösen.

## Kontrollmeasures

Im Ordner `05 Kontrolle`. Die drei `Kontrolle Wert ohne ...`-Measures sollten **0** sein:

- `Kontrolle Wert ohne Szenariozuordnung` – SAP-Versionen, die in `dim_Szenario` fehlen.
  Diese Werte tauchen weder im Budget noch im FC auf.
- `Kontrolle Wert ohne Kontozuordnung` – Accounts, die in `dim_Konto` fehlen.
- `Kontrolle Wert ohne Betriebszuordnung` – Betriebe, die in `dim_Betrieb` fehlen.

## Prüfskript

```
python3 tools/validate_model.py
```

Prüft ohne Power BI Desktop: Beziehungsspalten, mehrdeutige Filterpfade, DAX-Referenzen,
Namenskollisionen und Feldverweise im Report.

## Offene Punkte

- `Personaldaten[Vollname] → dim_Person[Vollname]` ist angelegt, aber **deaktiviert** –
  aktiv entstünde ein Filterkreis. Voraussetzung für eine spätere Aktivierung ist, dass die
  Namensschreibweise in Betriebeliste und Personaldaten übereinstimmt.
  Die Kontrollspalte `dim_Person[Quelle]` zeigt, wer nur in einer der beiden Quellen steht.
- `Fiscal_Year = 2025` ist weiterhin im Power-Query-Filter von `F_SAP` gesetzt.
  `dim_Periode` ist vorbereitet, falls später mehrere Geschäftsjahre geladen werden sollen.
