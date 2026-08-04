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
