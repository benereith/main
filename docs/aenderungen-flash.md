# Flash-Bericht – Optimierung Schritt 1

Betrifft `Flash/Flash_Basis.SemanticModel` und `Flash/Flash_Basis.Report`.

## 1. Schalter „Kanne abgerechnet"

Neue Steuertabelle `p_Kanne_Abrechnung` (ohne Beziehung) mit den Werten *Nein* / *Ja* und ein
Slicer auf der Seite *Flash*.

- **Nein** (Standard): Kanne folgt derselben ACT/FC/V-Logik wie alle anderen Managementbereiche.
- **Ja**: alle Kanne-Units zählen mit ihren Ist-Werten (SAP-Version 0), unabhängig vom Status.

Ausgewertet wird der Schalter in der Measure `[Flash]`. Der Bereich Kanne wird dort getrennt
gerechnet, alle übrigen Bereiche laufen über `[Flash Basis]`.

Wichtige Konsequenz: `Flash_Szenario` musste dafür aus `sap_master_data_unit` heraus. Ein Slicer
kann keine berechnete Spalte umsteuern – die Kanne-Ausnahme sitzt deshalb bewusst in der Measure,
die Grundzuordnung bleibt aus Performancegründen eine berechnete Spalte (jetzt in `Unit_Status`).

## 2. Vergangene Monate

Die Faktenabfrage zog bisher genau eine Periode (`Period = @Periode`). Jetzt:

```
AND Period BETWEEN @VonPeriode AND @BisPeriode
```

- Neuer Parameter `Startperiode` (Standard 1 = ab Oktober, also volles Geschäftsjahr bis
  einschließlich Berichtsmonat).
- `Aktuelle_Periode` ist weiterhin der Berichtsmonat; die Auswahlliste beginnt jetzt bei 1
  statt bei 0 (Periode 0 gibt es fachlich nicht).
- Der Parameter `pBerichtsmonat` **entfällt**. Der Berichtsmonat wird über die neue M-Funktion
  `fnPeriodeStart(Jahr, Periode)` aus `Geschäftsjahr` + `Aktuelle_Periode` abgeleitet. Vorher
  gab es zwei unabhängig zu pflegende Quellen für denselben Monat – die konnten auseinanderlaufen.
- Die Versionsliste steht jetzt zentral im Parameter `SAP_Versionen`. **`RF` und `35` wurden
  ergänzt**; sie fehlten bisher in der Abfrage, obwohl sie fachlich FC-Versionen sind.

### Neu: Tabelle `Unit_Status` (Grain Werk × Periode)

Das ist der Kern der Umstellung. Der Abrechnungsstatus wurde bisher **einmal** je Werk gegen
`pBerichtsmonat` bewertet und lag als Spalte in `sap_master_data_unit`. Bei mehreren geladenen
Monaten wäre das falsch: ein im Mai abgerechnetes Werk hätte auch den März als „Abgerechnet"
gezeigt.

`Unit_Status` bewertet dieselbe Regel jetzt je Periode und hängt über den Schlüssel
`Werk|Geschäftsjahr|Periode` an der Faktentabelle. Entfallen sind dafür:

- `Übergabedatum[Status]` (die Tabelle enthält nur noch die reinen Übergabedaten)
- `sap_master_data_unit[Status]` und `sap_master_data_unit[Flash_Szenario]`

Die Status-Slicer und der berichtsweite Statusfilter wurden auf `Unit_Status[Status]` umgehängt.

### Neu: Schalter „Zeitbezug"

Steuertabelle `p_Zeitbezug` mit *Einzelmonat* / *Kumuliert (YTD)*. Ausgewertet in den vier
Basis-Measures `ACT_/BUD_/FC_/V_Value_P&L`; alles Weitere (Flash, Ratios, Flex, Rang) baut darauf
auf und ist damit automatisch konsistent. Die YTD-Variante filtert über `FY_Jahr`/`FY_MonatNr`
aus `DIM_DATE` statt über `DATESYTD` – so ist kein sprachabhängiges Jahresende-Literal nötig.

Neuer Monats-Slicer auf `DIM_DATE[Monat_Label]` (z. B. „Jun 26"), sortiert über die neue
Hilfsspalte `Monat_Sortierung`.

## 3. „Kein Kennzeichen" vs. „Inaktiv"

`Unit_Status` prüft je Werk und Periode, ob überhaupt Werte vorliegen:

| Prüfung | SAP-Versionen |
| --- | --- |
| `Hat_Actuals` | `0` |
| `Hat_Budget` | `20` |
| `Hat_Forecast` | `RF`, `RGF`, `35`, `R12`, `RTD` |

Liegt nichts davon vor, ist der Status **`Inaktiv`** statt `Kein Kennzeichen`. Das Szenario wird
dann `Ohne Wertung` und die Unit fließt nicht in `[Flash]` ein – vorher landeten diese Units über
den Zweig `Status IN {"Kein Kennzeichen", "Abgerechnet"}` in ACT und haben die Flop-Listen
verwässert.

`Kein Kennzeichen` **mit** Daten bleibt eine echte Kennzeichnung und wird weiterhin als ACT
gerechnet.

Zur Kontrolle gibt es zwei Measures und eine Kachel *Datenlage* auf der Seite *Flash*:
`[Units ohne Daten]` und `[Units ohne Kennzeichen]`.

Beachte: der aktuelle FC bleibt ausschließlich **RGF + R12**. Die übrigen FC-Versionen zählen nur
für die Frage „wird hier überhaupt geplant", nicht in den Forecastwert.

## 4. Kommentierung

Siehe `docs/kommentare/README.md`. Umgesetzt als Translytical Task Flow: DirectQuery-Tabelle
`Kommentare` auf eine Fabric-SQL-Datenbank plus User Data Function zum Schreiben.

Im Modell und Bericht ist alles fertig; noch zu tun sind das Anlegen der Datenbank, das
Veröffentlichen der Funktion, das Setzen der beiden Verbindungsparameter und das Zuweisen der
Datenaktion an den Button.

## Was beim ersten Öffnen zu prüfen ist

1. **Parameter setzen:** `Geschäftsjahr`, `Aktuelle_Periode`, `Startperiode` und – falls die
   Kommentierung genutzt wird – `Kommentar_SQL_Endpoint` / `Kommentar_Datenbank`.
   Ohne gültigen SQL-Endpunkt schlägt die Tabelle `Kommentare` fehl; sie kann bis zur
   Einrichtung deaktiviert werden.
2. **Datenvolumen:** Statt einer Periode werden jetzt bis zu zwölf geladen. Bei Laufzeitproblemen
   `Startperiode` höher setzen.
3. **Kanne-Schalter steht auf „Nein"**, solange nichts ausgewählt ist – die Measure fällt bei
   fehlender Auswahl bewusst auf den bisherigen Rechenweg zurück.
4. `[SPLY]` liefert weiterhin nichts, weil nur ein Geschäftsjahr geladen wird. Das war vorher
   schon so; für echte Vorjahreswerte müsste die Faktenabfrage um das Vorjahr erweitert werden.
