# 05 – Berichtsdesign

Warum der Bericht aussieht, wie er aussieht. Grundlage sind die Prinzipien aus
*Storytelling with Data* (Cole Nussbaumer Knaflic) und ein Farbsystem, das gegen
Sehschwächen und Kontrastanforderungen geprüft wurde.

---

## 1. Die sechs Regeln, die das Layout bestimmen

### 1.1 Der Titel trägt die Aussage, nicht die Achsenbeschriftung

Ein Titel wie *"Net New ITY nach Periode"* wiederholt nur, was die Achsen schon
sagen. Der Kopfbereich jeder Seite zeigt stattdessen die Kennzahl
`[Aussage Net New]`:

> Net New ITY liegt 1.240.000 € über Budget (118 % Zielerreichung)

Der Text ändert sich mit dem Filterkontext. Wer einen Screenshot weitergibt,
gibt die Aussage mit weiter – nicht nur ein Diagramm, das erklärt werden muss.

Dasselbe Prinzip bei den Untertiteln jeder Visualisierung: statt
*"Legende: Status"* steht dort, was man sehen soll – *"Dunkel = gesichert,
hell = offen"*.

### 1.2 Grau ist die Standardfarbe, Farbe ist die Ausnahme

Referenzwerte (Budget, Vorjahr) sind grau (`#898781`). Nur die Größe, um die es
gerade geht, bekommt Farbe. Das ist der Unterschied zwischen "hier sind zwei
Linien" und "hier ist die Linie, und das ist ihr Vergleichsmaßstab".

Konkret auf der Cockpit-Seite: die CRM-Approximation ist blau, das Budget grau.
Ohne Legende ist erkennbar, welche der beiden die Botschaft trägt.

### 1.3 Weniger Tinte pro Aussage

Aus dem Layout entfernt:

* Gitterlinien der Kategorienachse (die Kategorien stehen bereits als Text da)
* Achsenlinien (die Beschriftung markiert die Achse ausreichend)
* Rahmen und Schatten um jede Visualisierung (eine feine Kante in `#E1E0D9`
  genügt zur Abgrenzung)
* Datenbeschriftungen an jedem Punkt einer Linie – dort, wo die Form die
  Aussage trägt, stört jede Zahl
* Die "Duplikat von …"-Seiten der Altberichte. Von 51 Seiten in drei Berichten
  bleiben **10 Seiten** in einem.

Behalten: horizontale Hilfslinien in `#E1E0D9`. Sie helfen beim Ablesen von
Größenordnungen und sind hell genug, um nicht mit Daten verwechselt zu werden.

### 1.4 Die Form folgt der Frage

| Frage | Gewählte Form | Warum nicht anders |
|---|---|---|
| Wie steht es um die Kernzahlen? | Kachelreihe | Fünf Kopfzahlen sind keine Verteilung – ein Balkendiagramm mit fünf Balken zwingt zum Lesen einer Achse, die nichts erklärt |
| Wie entwickelt sich das über die Perioden? | Linie | Die Zeitachse ist stetig; Balken suggerieren Einzelereignisse |
| Woraus setzt sich die Summe zusammen? | Wasserfall | Die Standardform für "von A nach B über diese Schritte" |
| Wie verteilt sich das auf viele Kategorien? | Horizontaler Balken | Lange Kategorienamen (Kunden, Betriebe) brauchen horizontalen Platz; gedrehte Beschriftungen kosten Lesezeit |
| Wie sieht das für 40 Organisationseinheiten aus? | Matrix | Mehr als etwa sieben Kategorien mit exakten Zahlen sind eine Tabelle, kein Diagramm |
| Was hat sich geändert? | Tabelle mit Vorher/Nachher nebeneinander | Der direkte Vergleich zweier Zahlen ist eine Lesefrage, keine Formfrage |

Bewusst **nicht** verwendet:

* **Kein Kreisdiagramm.** Winkelvergleiche sind ungenauer als Längenvergleiche.
* **Keine zweite Werteachse.** Zwei Größenordnungen in einem Bild führen
  zwangsläufig zu Fehlinterpretationen; getrennte Grafiken sind ehrlicher.
* **Keine Farbverläufe als Serienfarbe.** Farbverläufe verschieben die
  wahrgenommene Größe.

### 1.5 Eine Farbe bedeutet immer dasselbe

Die Farbzuordnung hängt in `DIM Status[Farbe]` an den Daten, nicht an der
einzelnen Visualisierung. Damit ist "Expected Win" auf jeder Seite dasselbe
Blau – auch dann, wenn ein Filter dazu führt, dass in einer Grafik nur drei
statt sechs Status vorkommen. Bei der üblichen Zuweisung nach Reihenfolge
würde in diesem Fall umgefärbt, und dieselbe Farbe stünde plötzlich für etwas
anderes.

### 1.6 Konstante Anordnung

Auf allen Seiten an derselben Stelle:

```
┌────────┬──────────────────────────────────────────────────────┐
│        │  Kernaussage als Text (Kennzahl, ändert sich mit     │
│        │  dem Filter)                                    76px │
│  Navi- ├──────────────────────────────────────────────────────┤
│  ga-   │  Filter- bzw. Kennzahlenzeile                   56px │
│  tion  ├──────────────────────────────────────────────────────┤
│        │                                                      │
│ 168px  │  Inhalt                                              │
│        │                                                      │
│        ├──────────────────────────────────────────────────────┤
│        │  Datenstand · Datenqualität                     24px │
└────────┴──────────────────────────────────────────────────────┘
```

Alle Kanten liegen auf einem 8-px-Raster. Unausgerichtete Kanten sind die
häufigste Form von visuellem Rauschen und die am leichtesten zu vermeidende.
`tools/validate_pbip.py` prüft Überstände und Überlappungen automatisch.

---

## 2. Farbsystem

### 2.1 Zwei Ein-Ton-Rampen statt einer kategorialen Palette

Die Statusstufen sind **keine** beliebigen Kategorien – sie sind zwei geordnete
Skalen: New Business von unsicher nach sicher, Lost Business ebenso. Eine
kategoriale Palette würde diese Ordnung verschenken. Stattdessen:

| Status | Farbe | Bedeutung der Farbe |
|---|---|---|
| Pipeline | `#86B6EF` | Blau, hell = New Business, wenig gesichert |
| Expected Win | `#3987E5` | Blau, mittel |
| Won | `#184F95` | Blau, dunkel = gesichert |
| At Risk | `#EB9998` | Rot, hell = Lost Business, wenig gesichert |
| Expected Loss | `#E34948` | Rot, mittel |
| Lost | `#A02222` | Rot, dunkel = gesichert |
| Referenz (Budget, Vorjahr) | `#898781` | Neutralgrau – Kontext, keine Botschaft |
| Summen und Gesamtlinien | `#0B0B0B` | Tinte |

Der Farbton trägt die Richtung (Gewinn/Verlust), die Helligkeit die Sicherheit.
Zwei Informationen in einem Kanal, ohne dass eine Legende sie erklären muss.

### 2.2 Prüfung

Beide Rampen wurden mit dem Validierungsskript der Data-Viz-Methode gegen
weißen Hintergrund geprüft:

```
Blau  #86B6EF → #3987E5 → #184F95
  Helligkeit monoton                     bestanden
  Abstand je Stufe ≥ 0,06                bestanden
  Kontrast der hellsten Stufe  2,11:1    bestanden (Grenze 2:1)
  Farbtonspanne  3°                      bestanden (eine Rampe = ein Ton)

Rot   #EB9998 → #E34948 → #A02222
  Helligkeit monoton                     bestanden
  Abstand je Stufe ≥ 0,06                bestanden
  Kontrast der hellsten Stufe  2,20:1    bestanden
  Farbtonspanne  6°                      bestanden
```

Der erste Kandidat für die helle Rotstufe (`#F0A6A5`) fiel mit 1,96:1 durch und
wurde ersetzt – bei diesem Kontrast verschwimmt die hellste Stufe mit dem
weißen Hintergrund.

Blau und Rot als Gegenpole sind auch bei Rot-Grün-Sehschwäche unterscheidbar,
weil sie sich in der Helligkeit unterscheiden und nicht nur im Farbton. Eine
Grün-Rot-Kodierung – naheliegend für "gut/schlecht" – wäre genau hier
gescheitert.

### 2.3 Statusfarben sind reserviert

`good #0CA30C`, `warning #FAB219`, `bad #D03B3B` stehen ausschließlich für
Zustände (Datenqualität, Zielerreichung) und werden nie als Serienfarbe
wiederverwendet. Sie erscheinen immer zusammen mit einer Beschriftung, nie als
Farbe allein – wer die Farbe nicht unterscheiden kann, liest den Text.

### 2.4 Wo die Farben stehen

* Theme: `powerbi/Net New ITY Cockpit.Report/StaticResources/SharedResources/BaseThemes/NetNewITY.json`
* Datenbindung: `DIM Status[Farbe]` (berechnete Spalte im Semantikmodell)
* Generator: `tools/build_report.py`, Konstante `C` – erzeugt alle Seiten
  neu und verwirft Handarbeit, läuft nur mit `--seiten-neu-erzeugen`

`tools/validate_pbip.py` prüft, dass im Bericht keine Farbe vorkommt, die nicht
im Theme definiert ist.

---

## 3. Die Seiten

### 3.1 Cockpit

**Frage:** Wie ist die Lage?

Kernaussage als Text, darunter fünf Kachelwerte, darunter der Monatsverlauf
gegen Budget und rechts daneben die Zusammensetzung nach Sicherheit. Ganz unten
die Organisationssicht als Matrix.

Die Anordnung folgt der Leserichtung: erst die Aussage, dann die Zahlen, dann
der Verlauf, dann das Detail. Wer nach fünf Sekunden abbricht, hat trotzdem das
Wichtigste gelesen.

### 3.2 Net-New-Brücke

**Frage:** Woraus setzt sich die Zahl zusammen?

Wasserfall über die Statusstufen: von der gesicherten Basis über die erwarteten
Effekte zur ausgewiesenen Summe. Darunter die Zuordnung zum HFM-Kontenplan und
die Sektorsicht – New und Lost getrennt, damit sich gegenläufige Effekte nicht
gegenseitig verdecken.

### 3.3 Szenarien

**Frage:** Was wäre, wenn?

Die Seite, die das manuelle Shiften ersetzt. Fünf Regler in einer Reihe:
Bewertungsbasis, zeitliche Verschiebung, Anlauffaktor, Anlaufdauer,
Mindestwahrscheinlichkeit. Darüber ein Satz, der die aktuelle Einstellung in
Worten wiedergibt (`[Szenario Beschreibung]`), damit ein Screenshot seine
eigenen Annahmen mitführt.

Links der Verlauf mit drei Linien – unverändert, mit Annahmen, Budget. Rechts,
wohin die Annahmen den Effekt verschieben.

Im Altmodell erforderte jede dieser Einstellungen eine Änderung in Power Query
und einen vollständigen Refresh. Details zur Umsetzung:
`docs/03_berechnungslogik.md`, Ordner *04 Szenarien*.

### 3.4 Roll-Budget

**Frage:** Was muss im laufenden Jahr noch gewonnen werden, damit das
Roll-Budget des Budgetjahres steht?

Die operative Konsequenz aus dem Cockpit, deshalb direkt dahinter. Der Umsatz
eines Budgetjahres aus Neugeschäft zerfällt in zwei Teile:

| Teil | Entscheidung fällt | Beeinflussbar? |
|---|---|---|
| **Roll** | im vorhergehenden Jahr | ja – jetzt |
| **ITY** | im Budgetjahr selbst | erst später |

Die Trennung liegt auf dem Fakt als `ITY Cluster` und auf der Budgetseite als
Betriebstyp der Planbetriebe (SAP-Version 90, `Plan-Betriebe Roll` bzw.
`Plan-Betriebe ITY`) – sie musste also nicht erfunden werden, sie war in
beiden Quellen schon da, wurde aber in keinem Altmodell gegeneinander gestellt.

Aufbau:

1. Die Antwort als Satz (`[Aussage Roll-Lücke]`) – nennt Betrag und ob die
   offene Pipeline ihn im Erwartungswert deckt.
2. Fünf Kopfzahlen, die sich als Rechnung lesen: Budget → Gesichertes → Lücke
   → offene Pipeline → Deckungsgrad.
3. Links Budget, Gesichertes und Pipeline auf gemeinsamer Achse. Der *Abstand*
   ist die Botschaft, deshalb Balken und keine Kacheln.
4. Rechts die Rangliste der offenen Roll-Vorgänge, absteigend nach Beitrag,
   mit kumulierter Summe und der Spalte `Schließt Lücke`. Ab der ersten
   „Ja"-Zeile ist das Minimalpaket beisammen – das ist die eigentliche
   Handlungsinformation und der Grund für die Seite.
5. Unten die Netto-Sicht des gewählten Jahres: Roll, ITY und Lost Business
   nebeneinander über die Perioden.

`[Roll Lücke]` rechnet bewusst gegen `[Roll gesichert]`, nicht gegen die
gewichtete Pipeline: die Frage lautet „was muss noch kommen", nicht „was
erwarten wir im Mittel".

### 3.5 New Business

**Frage:** Welche Opportunities konkret?

Filterzeile, darunter zwei Diagramme (Wirkung nach Periode, Volumen nach
bisherigem Anbieter), darunter die Detailtabelle. Die Wettbewerbersicht war im
Altbericht nicht darstellbar, weil das Feld `cgplc_currentsupplier` zwar
geladen, aber nie visualisiert wurde.

### 3.6 Lost Business

**Frage:** Welche Verträge sind gefährdet und warum?

Spiegelbildlich aufgebaut zu New Business – gleiche Anordnung, gleiche
Positionen, andere Farbe. Wer die eine Seite kennt, findet sich auf der anderen
sofort zurecht. Zusätzlich eine Auswertung nach Risikogrund und ein Filter auf
die Datenlage des Vorjahres-ARO, weil Verträge ohne diesen Wert mit 0 € bewertet
werden und sonst unsichtbar unterschlagen würden.

### 3.7 CRM-Bewegung

**Frage:** Was hat sich seit dem letzten Call geändert?

Die Seite für die wiederkehrende Besprechung. Kacheln mit Anzahl Änderungen,
Statuswechseln und der Summe aus Auf- und Abwärtskorrekturen. Darunter der
Zeitverlauf der Bewegungen und ihre Zusammensetzung nach Art. Ganz unten jede
einzelne Änderung mit Vorher- und Nachher-Wert nebeneinander.

Grundlage ist die Snapshot-Historie aus `silver_*_history`: pro Tag ein
Snapshot, aber nur dann eine neue Zeile, wenn sich tatsächlich etwas geändert
hat. Jede Zeile in der Tabelle bedeutet also eine echte Änderung.

### 3.8 Abstimmung und Datenqualität

**Frage:** Kann ich den Zahlen trauen?

Oben CRM gegen Budget Periode für Periode und die Gegenüberstellung von known
und unknown Business. Unten die Datenqualitätsregeln mit Anzahl der Verstöße
und – das ist der Punkt – einem konkreten Handlungshinweis je Regel.

Die Altmodelle filterten fehlerhafte Sätze per "Gefilterte Zeilen" heraus. Der
fehlende Betrag war im Ergebnis nicht mehr erklärbar. Hier steht er in einer
Tabelle mit Namen und Grund.

### 3.9 Detail (Drillthrough)

Aus jeder Tabelle per Rechtsklick erreichbar. Zeigt die Periodenverteilung eines
einzelnen Vorgangs und dessen vollständige CRM-Historie.

### 3.10 Definitionen

HFM-Kontendefinitionen im Wortlaut der Group Guidance und die
Statusdefinitionen mit Farbzuordnung. Damit steht die Definition im Bericht und
nicht in einer separaten Datei, die niemand öffnet.

---

## 4. Interaktion

| Element | Verhalten |
|---|---|
| Navigation | Feste Spalte links auf jeder Seite, aktive Seite hervorgehoben |
| Filter | Immer in einer Zeile oben, nie am Rand verstreut |
| Szenarioregler | Über Synchronisierungsgruppen seitenübergreifend gleichgeschaltet – eine Einstellung wirkt überall |
| Drillthrough | Von jeder Detailtabelle auf die Detailseite |
| QuickInfo | HFM-Kontendefinition an den Kennzahlen der Brücke |
| Export | Zusammengefasste Daten erlaubt, Rohdatenexport gesperrt |

---

## 5. Was aus den Altberichten bewusst nicht übernommen wurde

| Element | Grund |
|---|---|
| Vier fremdbezogene Visualisierungen (Zebra BI Tables/Cards, Text Filter, Waterfall) | Lizenz- und Freigabeabhängigkeit. Alle Funktionen sind mit Bordmitteln abgebildet. Wo Zebra BI vorhanden ist, lassen sich Matrix und Wasserfall eins zu eins ersetzen – das Datenmodell ändert sich dadurch nicht |
| Goldfarbene Titelbalken `#B3985A` auf jedem Element | Eine Titelfarbe, die an jedem Element wiederholt wird, verliert ihre Signalwirkung und konkurriert mit den Daten |
| Grauer Seitenhintergrund `#E5E5E5` | Senkt den Kontrast aller Inhalte. Der neue Seitenhintergrund `#F9F9F7` trennt die Fläche von den weißen Visualisierungen, ohne sie abzudunkeln |
| 22 doppelte und verwaiste Seiten | Wurden zusammengeführt oder entfernt |
