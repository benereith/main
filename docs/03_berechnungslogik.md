# 03 – Berechnungslogik aller Kennzahlen

> **Diese Datei wird erzeugt.** Sie entsteht aus den TMDL-Dateien des
> Semantikmodells über `python3 tools/generate_docs.py`. Änderungen bitte
> an der Quelle vornehmen (`powerbi/Net New ITY Cockpit.SemanticModel/`),
> nicht hier.


Das Modell enthält **76 Kennzahlen** in 11 Ordnern.

## Inhalt

- [(ohne Ordner)](#) – 7 Kennzahlen
- [01 Basis](#01-basis) – 12 Kennzahlen
- [02 Status](#02-status) – 10 Kennzahlen
- [03 Zeit](#03-zeit) – 4 Kennzahlen
- [04 Szenarien](#04-szenarien) – 4 Kennzahlen
- [05 Budget und Forecast](#05-budget-und-forecast) – 8 Kennzahlen
- [06 Quoten](#06-quoten) – 4 Kennzahlen
- [07 CRM-Bewegung](#07-crm-bewegung) – 5 Kennzahlen
- [08 Datenqualität](#08-datenqualität) – 3 Kennzahlen
- [09 Titel und Kontext](#09-titel-und-kontext) – 4 Kennzahlen
- [10 Roll-Budget](#10-roll-budget) – 15 Kennzahlen


## (ohne Ordner)

### `Budget ITY Effect`

Budgetierter unknown-ITY-Effekt aus der gepflegten Planungsdatei 2026_04_29_Planung_unknown_ITY_Effekt.xlsx (SharePoint, 08_Budget).

Bewusst NICHT aus dem Lakehouse, sondern direkt aus der Excel: die Datei ist ein manueller Planungsinput, der im Budgetprozess laufend fortgeschrieben wird. Wer die Zahl abstimmt, muss den Stand der Datei kennen – die Tabelle 'CRM Data' trägt ihn deshalb unverändert.

```dax
Budget ITY Effect =
SUM('CRM Data'[ity effect])
```

### `ITY Target Pipeline`

Pipeline-Ziel: das Dreifache des New-Business-Budgets.

Der Faktor 3 ist eine Erfahrungsregel – rund ein Drittel der Pipeline wird gewonnen, also braucht es das Dreifache des Ziels an Volumen. Er steht hier als Konstante und ist keine aus den Daten abgeleitete Größe; bei geänderter Abschlussquote muss er nachgezogen werden.

```dax
ITY Target Pipeline =
[New Business Budget]*3
```

### `ITY relativ sicher`

Gesicherter plus erwarteter ITY-Anteil, also alles außer der reinen Pipeline. Die Größe, mit der sich belastbar planen lässt: Won und Lost stehen fest, Expected Win und Expected Loss liegen über der Wahrscheinlichkeitsschwelle.

```dax
ITY relativ sicher =
[ITY gesichert]+[ITY erwartet]
```

### `Net New ITY YoY`

Veränderung gegenüber der GLEICHEN Periode des Vorjahres.

Rechnet bewusst auf der Bruttosumme und bringt den Vorjahresbezug selbst mit – nicht über [Net New ITY], das seinerseits bereits den Vorjahresanteil abzieht. Andernfalls wäre der Abzug doppelt drin.

Aufgehoben werden nur die Zeitfilter (GJ Jahr, GJ Periode Nr); Region, Sektor und übrige Filter bleiben erhalten, damit die Kennzahl auch in einer aufgerissenen Sicht stimmt.

**Format:** `0`

```dax
Net New ITY YoY =
-- 1. Szenario-Auswahl bestimmen
VAR _SzenarioBasis = SELECTEDVALUE ( 'Szenario Bewertung'[Bewertungsbasis], "CRM-gewichtet" )

-- 2. Hilfs-Funktion für die Szenario-Berechnung
VAR _BerechneSzenario = 
    SWITCH (
        _SzenarioBasis,
        "CRM-gewichtet", SUM ( 'FCT Net New ITY'[Betrag] ),
        "Vollwert",      SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
        "Nur gesichert",
            CALCULATE (
                SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
                KEEPFILTERS ( 'DIM Status'[Status Code] IN { "WON", "LOST" } )
            ),
        SUM ( 'FCT Net New ITY'[Betrag] )
    )

-- 3. Wert für das aktuelle Jahr
VAR _AktuellerWert = _BerechneSzenario

-- 4. Aktuelles Jahr und Periode ermitteln (mit Fallback, falls kein Jahr gefiltert ist)
VAR _AktuellesGJ = 
    COALESCE (
        SELECTEDVALUE ( 'DIM Datum'[GJ Jahr] ),
        MAX ( 'DIM Datum'[GJ Jahr] )
    )

VAR _AktuellePeriode = SELECTEDVALUE ( 'DIM Datum'[GJ Periode Nr] )

-- 5. Wert für das Vorjahr berechnen (unter Beibehaltung aller anderen Berichtsfilter)
VAR _VorjahresWert = 
    CALCULATE (
        _BerechneSzenario,
        -- Nur die Zeitfilter aufheben, damit Regionen, etc. erhalten bleiben!
        REMOVEFILTERS ( 'DIM Datum'[GJ Jahr], 'DIM Datum'[GJ Periode Nr] ),
        'DIM Datum'[GJ Jahr] = _AktuellesGJ - 1,
        'DIM Datum'[GJ Periode Nr] = _AktuellePeriode
    )

-- 6. Finale Rückgabe: Aktueller Wert plus Vorjahr * -1
RETURN
    IF (
        NOT ISBLANK ( _AktuellerWert ) || NOT ISBLANK ( _VorjahresWert ),
        _AktuellerWert + ( _VorjahresWert * -1 )
    )
```

### `New Business Budget`

Budgetierter New-Business-Effekt aus den SAP-Planwerten (Version 90), eingegrenzt auf Betriebe mit Cause of Change 2 in der Folgejahressicht.

ACHTUNG – manueller Zuschlag: die konstanten 4.900.000 € sind eine Korrektur außerhalb der Datenquelle. Sie sind hier nicht herleitbar und müssen bei jeder Budgetrunde geprüft werden; andernfalls schleppt die Kennzahl den Wert einer alten Runde unbemerkt mit.

```dax
New Business Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
    KEEPFILTERS('DIM Betrieb'[cause_of_change_ny] in {2}))+4900000
```

### `Unweighted`

Vollwert ohne Wahrscheinlichkeitsgewichtung, vorzeichenbehaftet. Obergrenze der Betrachtung: so viel entstünde, wenn jede Opportunity gewonnen und jeder Risikovertrag verloren würde.

```dax
Unweighted =
SUM('FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)])
```

### `Unweighted ITY Pipeline`

Ungewichtetes New-Business-Volumen – die Pipeline zum Vollwert, ohne Lost Business. Gegengröße zu [ITY Target Pipeline].

```dax
Unweighted ITY Pipeline =
CALCULATE(SUM('FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)]), 'FCT Net New ITY'[Geschäftsart]="NEW")
```


## 01 Basis

### `Anzahl Opportunities`

Anzahl der Opportunities mit Wirkung im Filterkontext. Zählt Entitäten, nicht Zeilen – eine Opportunity über zwölf Monate ist eine Opportunity.

**Format:** `#,0`

```dax
Anzahl Opportunities =
CALCULATE (
    DISTINCTCOUNT ( 'FCT Net New ITY'[Entität ID] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" )
)
```

### `Anzahl Risikoverträge`

Anzahl der Bestandsverträge mit Verlustrisiko im Filterkontext.

**Format:** `#,0`

```dax
Anzahl Risikoverträge =
CALCULATE (
    DISTINCTCOUNT ( 'FCT Net New ITY'[Entität ID] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" )
)
```

### `Lost Business ARO`

Lost Business ARO – annualisierte Umsatzrate der letzten zwölf Monate gekündigter Verträge. Negativ. HFM: MAP136.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Lost Business ARO =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" ),
    KEEPFILTERS ( 'FCT Net New ITY'[Wertebene] = "ARO" )
)
```

### `Lost Business ITY`

Lost Business ITY – In-the-year-Wirkung gekündigter Verträge. Ergebnis ist NEGATIV (Vorzeichenkonvention). HFM: MAP141c.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Lost Business ITY =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" ),
    KEEPFILTERS ( 'FCT Net New ITY'[Wertebene] = "ITY" )
)
```

### `Net New ARO`

Net New ARO = New Business ARO plus Lost Business ARO. Die Addition genügt, weil Lost bereits negativ ist.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ARO =
[New Business ARO] + [Lost Business ARO]
```

### `Net New ITY`

01 BASIS

Net New ITY = INKREMENTELLE Wirkung des gewählten Zeitraums. HFM: MAP141a minus MAP141c (ITY-Ebene).

WARUM EIN VORJAHRESABZUG Net New misst die VERÄNDERUNG gegenüber dem Vorjahr, nicht den Gesamtumsatz eines Vertrags. Eine Opportunity, die im April 2026 mobilisiert, trägt im FY2025/26 sechs Monate ITY. Im FY2026/27 läuft sie zwölf Monate – neu ist dort aber nur die Differenz, denn die sechs Monate wurden im Vorjahr bereits als New Business gezählt.

Beispiel (ARO 2.000.000 €, Mobilisierung 01.04.2026): FY2025/26   6 × 166.210 €  =    997.260 €   ITY   (MAP141a) FY2026/27  12 × 166.667 €  =  2.000.000 €   brutto davon Vorjahresanteil      =   −997.260 € Net New FY2026/27          =  1.002.740 €   der Roll-Effekt Ohne den Abzug erschienen 2.000.000 € – der Vertrag wäre doppelt gezählt worden, einmal im Jahr der Mobilisierung und noch einmal vollständig im Folgejahr.

SO WIRD ABGEZOGEN Verglichen werden die GLEICHEN Fiskalperioden des Vorjahres und nur die Vorgänge, die im aktuellen Kontext überhaupt vorkommen. Beides ist notwendig: · Gleiche Perioden statt ganzes Vorjahr – sonst stimmt die Summe bei einer Monatsauswahl nicht mehr mit der Jahressumme überein. · Nur vorhandene Vorgänge – sonst erzeugt ein Vertrag, der im Vorjahr Zeilen hatte und im gewählten Jahr keine mehr, einen Phantomwert aus dem Nichts. Das trifft vor allem Lost Business, das nach zwölf Perioden aus der Basis fällt.

Die Zerlegung ist sichtbar: [Net New ITY (brutto)] − [Vorjahresanteil] ergibt exakt diese Kennzahl.

Bewertungsbasis und Vorzeichenkonvention: siehe [Net New ITY (brutto)].

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY =
VAR _GJ         = MAX ( 'FCT Net New ITY'[GJ Jahr] )
VAR _Perioden   = VALUES ( 'FCT Net New ITY'[GJ Periode Nr] )
VAR _Entitaeten = VALUES ( 'FCT Net New ITY'[Entität ID] )
VAR _Aktuell    = [Net New ITY (brutto)]
VAR _Vorjahr =
    CALCULATE (
        [Net New ITY (brutto)],
        REMOVEFILTERS ( 'DIM Datum' ),
        'FCT Net New ITY'[GJ Jahr] = _GJ - 1,
        _Perioden,
        _Entitaeten
    )
RETURN
    _Aktuell - _Vorjahr
```

### `Net New ITY (brutto)`

Bruttosumme der Faktzeilen im Filterkontext, OHNE Vorjahresabzug.

Basis für [Net New ITY] und die Kennzahl für jede Abstimmung: die Differenz zwischen dieser und [Net New ITY] ist genau der Betrag, der im Vorjahr bereits gezählt wurde.

Die Bewertungsbasis steuert der Datenschnitt 'Szenario Bewertung': CRM-gewichtet  Umsatz × Eintrittswahrscheinlichkeit (Standard) Vollwert       Umsatz ohne Gewichtung – Obergrenze Nur gesichert  nur Won und Lost, ungewichtet – Untergrenze

Vorzeichen: New positiv, Lost negativ. Die Umkehr passiert einmalig im Lakehouse (amount_signed), nicht in dieser Kennzahl.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY (brutto) =
VAR _Basis = SELECTEDVALUE ( 'Szenario Bewertung'[Bewertungsbasis], "CRM-gewichtet" )
RETURN
SWITCH (
    _Basis,
    "CRM-gewichtet", SUM ( 'FCT Net New ITY'[Betrag] ),
    "Vollwert",      SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
    "Nur gesichert",
        CALCULATE (
            SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
            KEEPFILTERS ( 'DIM Status'[Status Code] IN { "WON", "LOST" } )
        ),
    SUM ( 'FCT Net New ITY'[Betrag] )
)
```

### `New Business ARO`

New Business ARO – annualisierte Umsatzrate der ersten zwölf Monate gewonnener Verträge, ab dem zweiten Geschäftsjahr. Vorlaufindikator: zeigt das Volumen, das im Folgejahr voll wirkt. HFM: MAP131.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
New Business ARO =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[Wertebene] = "ARO" )
)
```

### `New Business ITY`

New Business ITY – In-the-year-Wirkung neu gewonnener Verträge. Filtert die Faktentabelle auf Geschäftsart NEW und Wertebene ITY. HFM: MAP141a.

Wertebene ITY bedeutet: nur Monate innerhalb des ersten Geschäftsjahres der Opportunity. Danach greift MAP131 (ARO).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
New Business ITY =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[Wertebene] = "ITY" )
)
```

### `Vorjahresanteil`

Betrag, der im gewählten Zeitraum bereits im Vorjahr gezählt wurde – der Abzug, den [Net New ITY] vornimmt. Für die Abstimmung sichtbar gemacht: [Net New ITY (brutto)] − [Vorjahresanteil] = [Net New ITY].

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Vorjahresanteil =
VAR _GJ         = MAX ( 'FCT Net New ITY'[GJ Jahr] )
VAR _Perioden   = VALUES ( 'FCT Net New ITY'[GJ Periode Nr] )
VAR _Entitaeten = VALUES ( 'FCT Net New ITY'[Entität ID] )
RETURN
    CALCULATE (
        [Net New ITY (brutto)],
        REMOVEFILTERS ( 'DIM Datum' ),
        'FCT Net New ITY'[GJ Jahr] = _GJ - 1,
        _Perioden,
        _Entitaeten
    )
```

### `Ø Verlust-% (volumengewichtet)`

Durchschnittliche Verlustwahrscheinlichkeit der Risikoverträge, volumengewichtet. Analog zu Ø Win-%.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Ø Verlust-% (volumengewichtet) =
VAR _Volumen =
    CALCULATE (
        SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
        KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" )
    )
VAR _Gewichtet =
    CALCULATE (
        SUM ( 'FCT Net New ITY'[Betrag] ),
        KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" )
    )
RETURN
    DIVIDE ( _Gewichtet, _Volumen )
```

### `Ø Win-% (volumengewichtet)`

Durchschnittliche Gewinnwahrscheinlichkeit, gewichtet mit dem ARO-Volumen der Opportunity.

Bewusst volumengewichtet: der ungewichtete Mittelwert (so im Altmodell [Win%]) lässt eine 5-Mio-Opportunity mit 30 Prozent genauso schwer wiegen wie eine 50-Tsd-Opportunity mit 90 Prozent und ist als Steuerungsgröße irreführend.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Ø Win-% (volumengewichtet) =
VAR _Volumen =
    CALCULATE (
        SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
        KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" )
    )
VAR _Gewichtet =
    CALCULATE (
        SUM ( 'FCT Net New ITY'[Betrag] ),
        KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" )
    )
RETURN
    DIVIDE ( _Gewichtet, _Volumen )
```


## 02 Status

### `ITY At Risk`

ITY-Wirkung gefährdeter Verträge (Retention-% über 20 %, unter 100 %). Negativ.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY At Risk =
CALCULATE ( [Lost Business ITY], 'DIM Status'[Status Code] = "AT_RISK" )
```

### `ITY Expected Loss`

ITY-Wirkung erwarteter Verluste (Retention-% bis 20 %). Negativ.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY Expected Loss =
CALCULATE ( [Lost Business ITY], 'DIM Status'[Status Code] = "EXPECTED_LOSS" )
```

### `ITY Expected Win`

ITY-Wirkung erwarteter Gewinne (Win-% ab 80 %, unter 100 %).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY Expected Win =
CALCULATE ( [New Business ITY], 'DIM Status'[Status Code] = "EXPECTED_WIN" )
```

### `ITY Lost`

ITY-Wirkung bereits verlorener Verträge (Retention-% = 0). Negativ.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY Lost =
CALCULATE ( [Lost Business ITY], 'DIM Status'[Status Code] = "LOST" )
```

### `ITY Pipeline`

ITY-Wirkung offener Pipeline (Win-% unter 80 %).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY Pipeline =
CALCULATE ( [New Business ITY], 'DIM Status'[Status Code] = "PIPELINE" )
```

### `ITY Won`

02 STATUS – Zerlegung nach Sicherheitsgrad

ITY-Wirkung bereits gewonnener Opportunities (Win-% = 100 %). Der belastbarste Teil des New Business.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY Won =
CALCULATE ( [New Business ITY], 'DIM Status'[Status Code] = "WON" )
```

### `ITY erwartet`

Erwarteter Anteil: Expected Win plus Expected Loss.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY erwartet =
[ITY Expected Win] + [ITY Expected Loss]
```

### `ITY gesichert`

Gesicherter Anteil: Won plus Lost. Die Zahl, die man ohne weitere Annahmen berichten kann.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY gesichert =
[ITY Won] + [ITY Lost]
```

### `ITY unsicher`

Unsicherer Anteil: Pipeline plus At Risk.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY unsicher =
[ITY Pipeline] + [ITY At Risk]
```

### `Sicherungsgrad`

Anteil des gesicherten am gesamten Net New ITY. Kernkennzahl für die Belastbarkeit des Forecasts: je höher, desto weniger hängt die Zahl an Annahmen.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Sicherungsgrad =
DIVIDE ( ABS ( [ITY gesichert] ), ABS ( [ITY gesichert] ) + ABS ( [ITY erwartet] ) + ABS ( [ITY unsicher] ) )
```


## 03 Zeit

### `Net New ITY Gesamtjahr`

Net New ITY des gesamten Geschäftsjahres, unabhängig davon, welche Periode gerade gefiltert ist. Nenner für Fortschrittsanzeigen.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY Gesamtjahr =
VAR _GJ = MAX ( 'DIM Datum'[GJ Jahr] )
RETURN
    CALCULATE (
        [Net New ITY],
        REMOVEFILTERS ( 'DIM Datum' ),
        'DIM Datum'[GJ Jahr] = _GJ
    )
```

### `Net New ITY Vorjahr`

Net New ITY der gleichen Periode des Vorjahres. Verschiebt den Monatsindex um zwölf – funktioniert dadurch auch über die Geschäftsjahresgrenze hinweg korrekt.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY Vorjahr =
VAR _Verschoben =
    SUMX (
        VALUES ( 'DIM Datum'[Monatsindex] ),
        VAR _Ziel = 'DIM Datum'[Monatsindex] - 12
        RETURN
            CALCULATE (
                [Net New ITY],
                REMOVEFILTERS ( 'DIM Datum' ),
                'FCT Net New ITY'[Monatsindex] = _Ziel
            )
    )
RETURN
    _Verschoben
```

### `Net New ITY YTD`

03 ZEIT

Net New ITY kumuliert seit Beginn des Geschäftsjahres.

Umsetzung über den linearen Monatsindex statt über TOTALYTD: die Standard-Zeitintelligenz kennt nur Kalenderjahre und liefert für ein Oktober-September-Geschäftsjahr falsche Grenzen.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY YTD =
VAR _GJ = MAX ( 'DIM Datum'[GJ Jahr] )
VAR _BisPeriode = MAX ( 'DIM Datum'[GJ Periode Nr] )
RETURN
    CALCULATE (
        [Net New ITY],
        REMOVEFILTERS ( 'DIM Datum' ),
        'DIM Datum'[GJ Jahr] = _GJ,
        'DIM Datum'[GJ Periode Nr] <= _BisPeriode
    )
```

### `Net New ITY Δ Vorjahr`

Veränderung gegenüber der Vorjahresperiode in Euro.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Net New ITY Δ Vorjahr =
[Net New ITY] - [Net New ITY Vorjahr]
```


## 04 Szenarien

### `Net New ITY (Szenario)`

04 SZENARIEN – ersetzt das manuelle Shiften

Net New ITY unter den gewählten Szenarioannahmen.

BERECHNUNG IN ZWEI SCHRITTEN

1. Zeitliche Verschiebung. Für jeden Monat der Achse wird der Wert des Quellmonats geholt, der um die eingestellte Anzahl Monate davor liegt. Bei +2 zeigt Dezember also den ursprünglichen Oktoberwert. Iteriert wird über 'DIM Datum'[Monatsindex] – zwölf bis vierundzwanzig Werte im Filterkontext.

2. Anlaufkurve. Innerhalb des Quellmonats wird über 'FCT Net New ITY'[Periodenindex] iteriert (Monat 1, 2, 3 … seit Mobilisierung). Liegt der Periodenindex innerhalb der eingestellten Anlaufdauer, wird der Anlauffaktor angewandt.

Beide Schleifen laufen über niedrigkardinale Spalten. Der Aufwand liegt bei maximal 24 × 24 Zellen – deutlich günstiger, als für jede Parameterkombination eine eigene Faktenvariante zu materialisieren (das wären 10 × 6 × 7 = 420 Varianten).

Sind alle Parameter auf Standard (0 Monate, kein Anlauf), ist das Ergebnis identisch zu [Net New ITY].

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY (Szenario) =
VAR _Verschiebung = SELECTEDVALUE ( 'Szenario Verschiebung'[Monate], 0 )
VAR _Faktor       = SELECTEDVALUE ( 'Szenario Anlauf'[Faktor], 1 )
VAR _Dauer        = SELECTEDVALUE ( 'Szenario Anlaufdauer'[Monate], 0 )
RETURN
SUMX (
    VALUES ( 'DIM Datum'[Monatsindex] ),
    VAR _Zielmonat = 'DIM Datum'[Monatsindex] - _Verschiebung
    RETURN
        CALCULATE (
            IF (
                _Dauer = 0 || _Faktor = 1,
                -- Kein Anlaufeffekt: eine einfache Summe genügt.
                [Net New ITY],
                -- Mit Anlaufeffekt: je Periodenindex gewichten.
                SUMX (
                    VALUES ( 'FCT Net New ITY'[Periodenindex] ),
                    VAR _Index = 'FCT Net New ITY'[Periodenindex]
                    VAR _Gewicht =
                        IF ( _Index >= 1 && _Index <= _Dauer, _Faktor, 1 )
                    RETURN
                        CALCULATE ( [Net New ITY] ) * _Gewicht
                )
            ),
            REMOVEFILTERS ( 'DIM Datum' ),
            'FCT Net New ITY'[Monatsindex] = _Zielmonat
        )
)
```

### `Net New ITY (ab Schwelle)`

Net New ITY nur für Vorgänge ab der eingestellten Mindestwahrscheinlichkeit.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY (ab Schwelle) =
VAR _Schwelle = SELECTEDVALUE ( 'Szenario Schwelle'[Schwelle], 0 )
RETURN
    CALCULATE (
        [Net New ITY],
        KEEPFILTERS ( 'FCT Net New ITY'[Wahrscheinlichkeit] >= _Schwelle )
    )
```

### `Szenario Beschreibung`

Beschreibt die aktuell eingestellten Szenarioannahmen als Fließtext. Wird als Untertitel der Szenarioseite angezeigt, damit ein Screenshot immer seine eigenen Annahmen mitführt – niemand muss raten, welche Einstellungen zu einer Zahl geführt haben.

```dax
Szenario Beschreibung =
VAR _Verschiebung = SELECTEDVALUE ( 'Szenario Verschiebung'[Monate], 0 )
VAR _Faktor       = SELECTEDVALUE ( 'Szenario Anlauf'[Faktor], 1 )
VAR _Dauer        = SELECTEDVALUE ( 'Szenario Anlaufdauer'[Monate], 0 )
VAR _Basis        = SELECTEDVALUE ( 'Szenario Bewertung'[Bewertungsbasis], "CRM-gewichtet" )
VAR _Schwelle     = SELECTEDVALUE ( 'Szenario Schwelle'[Schwelle], 0 )
VAR _TextShift =
    SWITCH (
        TRUE (),
        _Verschiebung = 0, "keine Verschiebung",
        _Verschiebung > 0, FORMAT ( _Verschiebung, "0" ) & " Monat(e) später",
        FORMAT ( -_Verschiebung, "0" ) & " Monat(e) früher"
    )
VAR _TextAnlauf =
    IF (
        _Dauer = 0 || _Faktor = 1,
        "kein Anlaufeffekt",
        FORMAT ( _Faktor, "0 %" ) & " über " & FORMAT ( _Dauer, "0" ) & " Monate"
    )
VAR _TextSchwelle =
    IF ( _Schwelle = 0, "alle Wahrscheinlichkeiten", "ab " & FORMAT ( _Schwelle, "0 %" ) )
RETURN
    "Annahmen: " & _Basis & " · " & _TextShift & " · Anlauf: " & _TextAnlauf
        & " · " & _TextSchwelle
```

### `Δ Szenario zu Basis`

Wirkung der Szenarioannahmen gegenüber dem Basisfall. Positiv bedeutet: das Szenario ist günstiger als die reine CRM-Sicht.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Δ Szenario zu Basis =
[Net New ITY (Szenario)] - [Net New ITY]
```


## 05 Budget und Forecast

### `Budget Net New (SAP)`

Budgetwert aus den Umsatzdaten nach der Logik des Altmodells ([SAP_Value] auf der Tabelle Revenues). Zwei Summanden:

1. LAUFENDES Geschäftsjahr, Budget (Version 90). 2. VORJAHR, Forecast (Versionen RGF und R12) – dort steht für das Budgetjahr noch kein Plan, der Forecast ist die beste Schätzung.

Beide Teile grenzen über die Folgejahressicht des Cause of Change ab ("Mapping CoCh NY" im Altmodell, hier 'Metric ID NY') und lassen Metric 99 = Like for Like außen vor – das ist definitionsgemäß kein Net New.

Im Vorjahresteil zusätzlich ausgeschlossen: Plan-Betriebe vom Typ ITY mit Cause of Change 4. Diese Kombination ist im Vorjahresforecast bereits anderweitig erfasst und würde doppelt zählen.

WARUM SUMMARIZE + AVERAGE STATT EINER EINFACHEN SUMME Aus dem Altmodell übernommen: liefert die Quelle je Werk, Periode, Geschäftsjahr und Werttyp mehr als eine Zeile, summierte eine einfache SUM die Dubletten mit auf. Der Mittelwert je Gruppe kollabiert sie stattdessen auf ihren Wert. Seit der Entdopplung von unit_coch in nb_20_gold sollten keine Dubletten mehr entstehen – die Konstruktion bleibt als Absicherung erhalten, weil ein Rückfall sonst wieder nur als stillschweigend zu hohe Zahl sichtbar würde.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Budget Net New (SAP) =
VAR _GJ      = MAX ( 'FCT Umsatz'[GJ Jahr] )
VAR _Vorjahr = _GJ - 1

VAR _Entdoppelt =
    SUMMARIZE (
        'FCT Umsatz',
        'FCT Umsatz'[Werk],
        'FCT Umsatz'[GJ Periode Nr],
        'FCT Umsatz'[GJ Jahr],
        'FCT Umsatz'[Werttyp Version]
    )

VAR _BudgetLaufend =
    CALCULATE (
        SUMX ( _Entdoppelt, CALCULATE ( AVERAGE ( 'FCT Umsatz'[Monatswert] ) ) ),
        KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
        KEEPFILTERS ( 'FCT Umsatz'[Metric ID NY] <> 99 ),
        'FCT Umsatz'[GJ Jahr] = _GJ
    )

VAR _ForecastVorjahr =
    CALCULATE (
        SUMX ( _Entdoppelt, CALCULATE ( AVERAGE ( 'FCT Umsatz'[Monatswert] ) ) ),
        KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] IN { "Plan_RGF", "Plan_R12" } ),
        KEEPFILTERS ( 'FCT Umsatz'[Metric ID NY] <> 99 ),
        'FCT Umsatz'[GJ Jahr] = _Vorjahr,
        FILTER (
            ALL ( 'FCT Umsatz'[Betriebstyp], 'FCT Umsatz'[cause_of_change_ny] ),
            NOT (
                'FCT Umsatz'[Betriebstyp] = "Plan-Betriebe ITY"
                    && 'FCT Umsatz'[cause_of_change_ny] = 4
            )
        )
    )

RETURN
    _BudgetLaufend + _ForecastVorjahr
```

### `Net ITY Budget`

Budgetierter unknown-ITY-Effekt (SAP-Version 90, Planbetriebe). Der Wert, gegen den die CRM-Approximation gestellt wird.

```dax
Net ITY Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
    KEEPFILTERS('DIM Betrieb'[cause_of_change_ny] in {4,2}))+4900000-6842682.23
```

### `Organischer Umsatz Vorjahr`

Organischer Vorjahresumsatz – Bezugsgröße aller Prozentkennzahlen der Group Guidance (MAP111e, MAP112e). Definition laut Guidance: Vorjahresumsatz, bereinigt um Zu- und Verkäufe, zu aktuellen Wechselkursen.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Organischer Umsatz Vorjahr =
VAR _GJ = MAX ( 'DIM Datum'[GJ Jahr] )
RETURN
    CALCULATE (
        SUM ( 'FCT Umsatz'[Monatswert] ),
        REMOVEFILTERS ( 'DIM Datum' ),
        'FCT Umsatz'[GJ Jahr] = _GJ - 1,
        KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Actual_0" ),
        KEEPFILTERS ( 'FCT Umsatz'[Metric ID] <> 99 )
    )
```

### `Umsatz Budget`

Budgetierter Umsatz (SAP-Version 20).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Umsatz Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" )
)
```

### `Umsatz Forecast`

Aktueller Forecast (SAP-Versionen RGF und R12).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Umsatz Forecast =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] IN { "Plan_RGF", "Plan_R12" } )
)
```

### `Umsatz Ist`

05 BUDGET UND FORECAST (SAP)

Gebuchter Umsatz laut SAP (Version 0).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Umsatz Ist =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Actual_0" )
)
```

### `Zielerreichung`

Zielerreichung der CRM-Approximation gegenüber Budget.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Zielerreichung =
DIVIDE ( [Net New ITY (Szenario)], [Net ITY Budget] )
```

### `Δ CRM zu Budget`

Abweichung der CRM-Approximation vom Budget. Positiv = das CRM zeigt mehr Net New ITY, als budgetiert wurde.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Δ CRM zu Budget =
[Net New ITY (Szenario)] - [Net ITY Budget]
```


## 06 Quoten

### `Lost Business %`

Lost Business in Prozent des organischen Vorjahresumsatzes. Als positive Zahl dargestellt, obwohl der Zähler negativ ist – so liest sich "Lost Business 3,2 %" wie in der Group-Berichterstattung. HFM: MAP112e.

**Format:** `0.00\ %;-0.00\ %;0.00\ %`

```dax
Lost Business % =
DIVIDE ( ABS ( [Lost Business ITY] ), [Organischer Umsatz Vorjahr] )
```

### `Net New Business %`

Net New Business in Prozent des organischen Vorjahresumsatzes. New minus Lost. HFM: Net new business (Reported) %.

**Format:** `0.00\ %;-0.00\ %;0.00\ %`

```dax
Net New Business % =
DIVIDE ( [Net New ITY], [Organischer Umsatz Vorjahr] )
```

### `New Business %`

06 QUOTEN NACH GROUP GUIDANCE

New Business in Prozent des organischen Vorjahresumsatzes. HFM: MAP111e.

**Format:** `0.00\ %;-0.00\ %;0.00\ %`

```dax
New Business % =
DIVIDE ( [New Business ITY], [Organischer Umsatz Vorjahr] )
```

### `Retention %`

Retention-Quote = 100 Prozent minus Lost Business Quote. HFM: Retention (Reported) %.

**Format:** `0.00\ %;-0.00\ %;0.00\ %`

```dax
Retention % =
1 - [Lost Business %]
```


## 07 CRM-Bewegung

### `Bewegung Anzahl`

Anzahl der Vorgänge, an denen sich seit dem letzten Stichtag etwas geändert hat.

**Format:** `#,0`

```dax
Bewegung Anzahl =
DISTINCTCOUNT ( 'FCT CRM-Bewegung'[Entität ID] )
```

### `Bewegung Statuswechsel`

Anzahl der Statuswechsel. Die wichtigste Bewegungsart: ein Wechsel von Pipeline zu Expected Win verändert die Belastbarkeit des Forecasts stärker als jede Wertkorrektur.

**Format:** `#,0`

```dax
Bewegung Statuswechsel =
CALCULATE (
    DISTINCTCOUNT ( 'FCT CRM-Bewegung'[Entität ID] ),
    KEEPFILTERS ( 'FCT CRM-Bewegung'[Änderungsart] = "Statuswechsel" )
)
```

### `Bewegung Wert`

07 CRM-BEWEGUNG

Summe aller Wertänderungen im CRM im gewählten Zeitraum.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Bewegung Wert =
SUM ( 'FCT CRM-Bewegung'[Wertänderung] )
```

### `Bewegung negativ`

Wertänderung nur aus Vorgängen, die sich verschlechtert haben.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Bewegung negativ =
CALCULATE (
    SUM ( 'FCT CRM-Bewegung'[Wertänderung] ),
    KEEPFILTERS ( 'FCT CRM-Bewegung'[Wertänderung] < 0 )
)
```

### `Bewegung positiv`

Wertänderung nur aus Vorgängen, die sich verbessert haben.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Bewegung positiv =
CALCULATE (
    SUM ( 'FCT CRM-Bewegung'[Wertänderung] ),
    KEEPFILTERS ( 'FCT CRM-Bewegung'[Wertänderung] > 0 )
)
```


## 08 Datenqualität

### `DQ Fehler`

Anzahl der Verstöße gegen Regeln mit Schweregrad ERROR. Ist dieser Wert größer als 0, hat die Pipeline nicht durchlaufen und die Zahlen im Bericht sind älter als der letzte Ladelauf.

**Format:** `#,0`

```dax
DQ Fehler =
VAR _Letzte = CALCULATE ( MAX ( 'DQ Prüfungen'[Prüfdatum] ), ALL ( 'DQ Prüfungen' ) )
RETURN
    CALCULATE (
        SUM ( 'DQ Prüfungen'[Verstöße] ),
        'DQ Prüfungen'[Prüfdatum] = _Letzte,
        'DQ Prüfungen'[Schweregrad] = "ERROR"
    )
```

### `DQ Status`

Ampeltext zum Zustand der Datenbasis.

```dax
DQ Status =
VAR _Fehler = [DQ Fehler]
VAR _Alle = [DQ Verstöße]
RETURN
    SWITCH (
        TRUE (),
        _Fehler > 0, "Kritisch – " & FORMAT ( _Fehler, "#,0" ) & " blockierende Verstöße",
        _Alle > 0, "Eingeschränkt – " & FORMAT ( _Alle, "#,0" ) & " Hinweise zur Nachpflege",
        "Vollständig"
    )
```

### `DQ Verstöße`

08 DATENQUALITÄT

Anzahl der Regelverstöße im jüngsten Prüflauf.

**Format:** `#,0`

```dax
DQ Verstöße =
VAR _Letzte = CALCULATE ( MAX ( 'DQ Prüfungen'[Prüfdatum] ), ALL ( 'DQ Prüfungen' ) )
RETURN
    CALCULATE ( SUM ( 'DQ Prüfungen'[Verstöße] ), 'DQ Prüfungen'[Prüfdatum] = _Letzte )
```


## 09 Titel und Kontext

### `Aussage Net New`

09 DYNAMISCHE TITEL UND KONTEXT

Storytelling with Data, Kapitel 5: Der Titel trägt die Aussage, nicht die Beschriftung der Achse. Diese Kennzahlen erzeugen Titel, die sich mit dem Filterkontext ändern und die Botschaft der Grafik benennen.

Kernaussage zur Entwicklung des Net New ITY. Benennt Richtung und Größenordnung statt nur die Kennzahl zu wiederholen.

```dax
Aussage Net New =
VAR _Wert = [Net New ITY (Szenario)]
VAR _Budget = [Net ITY Budget]
VAR _Delta = _Wert - _Budget
VAR _Richtung = IF ( _Delta >= 0, "über", "unter" )
RETURN
    IF (
        ISBLANK ( _Budget ),
        "Net New ITY: " & FORMAT ( _Wert, "#,0 €" ),
        "Net New ITY liegt " & FORMAT( ABS ( _Delta ), "#,0 €" ) & " "
            & _Richtung & " Budget ("
            & FORMAT ( [Zielerreichung], "0 %" ) & " Zielerreichung)"
    )
```

### `Aussage Sicherheit`

Aussage zur Belastbarkeit des Forecasts.

```dax
Aussage Sicherheit =
VAR _Grad = [Sicherungsgrad]
RETURN
    FORMAT ( _Grad, "0 %" ) & " des ausgewiesenen Net New ITY sind bereits gesichert · "
        & FORMAT ( [Anzahl Opportunities], "#,0" ) & " Opportunities · "
        & FORMAT ( [Anzahl Risikoverträge], "#,0" ) & " Risikoverträge"
```

### `Erläuterung Bewertungsbasis`

Erläutert die aktuell gewählte Bewertungsbasis im Klartext.

```dax
Erläuterung Bewertungsbasis =
VAR _Basis = SELECTEDVALUE ( 'Szenario Bewertung'[Bewertungsbasis], "CRM-gewichtet" )
RETURN
    SWITCH (
        _Basis,
        "CRM-gewichtet", "Beträge sind mit der Eintrittswahrscheinlichkeit aus dem CRM gewichtet.",
        "Vollwert", "Beträge sind ungewichtet – Obergrenze bei vollständigem Eintritt aller Vorgänge.",
        "Nur gesichert", "Nur bereits gewonnene bzw. verlorene Vorgänge, ungewichtet – belastbare Untergrenze.",
        ""
    )
```

### `Stand der Daten`

Stand der Daten und Zustand der Prüfungen – gehört auf jede Seite, damit ein exportiertes Bild seinen eigenen Stichtag mitführt.

```dax
Stand der Daten =
VAR _Stand = CALCULATE ( MAX ( 'FCT Net New ITY'[Stichtag] ), ALL ( 'FCT Net New ITY' ) )
RETURN
    "Datenstand " & FORMAT ( _Stand, "DD.MM.YYYY" ) & " · Datenqualität: " & [DQ Status]
```


## 10 Roll-Budget

### `Aussage Roll-Lücke`

Ampeltext zur Roll-Lücke. Beantwortet in einem Satz, ob und wie viel noch gewonnen werden muss – Storytelling with Data, Kapitel 5: die Aussage gehört in den Titel, nicht in die Legende.

```dax
Aussage Roll-Lücke =
VAR _Luecke  = [Roll Lücke]
VAR _Pipe    = [Roll offen (gewichtet)]
VAR _Deckung = DIVIDE ( _Pipe, _Luecke )
VAR _GJ      = SELECTEDVALUE ( 'DIM Datum'[GJ Bezeichnung], "dem Budgetjahr" )
RETURN
SWITCH (
    TRUE (),
    ISBLANK ( [Roll Budget] ),
        "Kein Roll-Budget im Filterkontext – Betriebstyp und Geschäftsjahr prüfen",
    _Luecke <= 0,
        "Roll-Budget für " & _GJ & " ist gedeckt: "
            & FORMAT ( -_Luecke, "#,0 €" ) & " über Plan",
    _Deckung >= 1,
        "Noch " & FORMAT ( _Luecke, "#,0 €" ) & " bis zum Roll-Budget "
            & _GJ & " – die offene Pipeline deckt das im Erwartungswert ("
            & FORMAT ( _Deckung, "0 %" ) & ")",
    "Noch " & FORMAT ( _Luecke, "#,0 €" ) & " bis zum Roll-Budget "
        & _GJ & " – die offene Pipeline deckt davon nur "
        & FORMAT ( _Deckung, "0 %" ) & ", es fehlt Pipeline"
)
```

### `Beitrag Zeitraum (gewichtet)`

Beitrag einer einzelnen Opportunity zum gewählten Geschäftsjahr, gewichtet. Für die Rangliste "was muss noch gewonnen werden": in einer Tabelle über 'FCT Net New ITY'[Entität Name] liefert sie je Zeile den Beitrag genau dieses Vorgangs.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Beitrag Zeitraum (gewichtet) =
CALCULATE (
    SUM ( 'FCT Net New ITY'[Betrag] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" )
)
```

### `Beitrag kumuliert`

Kumulierter Beitrag der offenen Roll-Opportunities, absteigend nach Beitrag. Zusammen mit [Roll Lücke] beantwortet sie die eigentliche Frage: WIE VIELE der offenen Vorgänge reichen aus, um die Lücke zu schließen? In der Rangliste ist das die Zeile, ab der die kumulierte Summe die Lücke übersteigt.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Beitrag kumuliert =
VAR _Aktuell = [Beitrag Zeitraum (gewichtet)]
VAR _Tabelle =
    ADDCOLUMNS (
        ALLSELECTED ( 'FCT Net New ITY'[Entität] ),
        "@Beitrag", [Beitrag Zeitraum (gewichtet)]
    )
RETURN
    SUMX ( FILTER ( _Tabelle, [@Beitrag] >= _Aktuell ), [@Beitrag] )
```

### `ITY CRM (Budgetjahr)`

ITY-Anteil des Budgetjahres aus dem CRM – Entscheidungen, die im Budgetjahr selbst fallen. Gegengröße zu [ITY Budget].

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
ITY CRM (Budgetjahr) =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[ITY Cluster] = "unknown ITY" )
)
```

### `Lost Business (Zeitraum)`

Lost Business des gewählten Geschäftsjahres, als negative Zahl. Steht neben [Roll CRM] und [ITY CRM (Budgetjahr)], damit die Netto-Sicht des Budgetjahres vollständig ist.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Lost Business (Zeitraum) =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "LOST" )
)
```

### `Roll Budget`

10 ROLL-BUDGET

Alle Kennzahlen dieser Gruppe beantworten EINE Frage: "Was muss im laufenden Geschäftsjahr noch gewonnen werden, damit das Roll-Budget des Budgetjahres erreicht wird?"

Der Umsatz eines Budgetjahres aus Neugeschäft zerfällt in zwei Teile: Roll → Entscheidung fällt im VORHERGEHENDEN Jahr, Umsatz rollt hinein. Darauf lässt sich JETZT noch Einfluss nehmen. ITY  → Entscheidung fällt im Budgetjahr selbst. Die Trennung steht auf dem Fakt als 'ITY Cluster' und im SAP-Budget als Betriebstyp der Planbetriebe (Version 90).

Budgetseite: Roll-Anteil des unknown-ITY-Budgets (SAP-Version 90, Planbetriebe vom Typ Roll). Gegengröße zu [Roll gesichert].

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
    KEEPFILTERS ( 'FCT Umsatz'[Betriebstyp] = "Plan-Betriebe Roll" )
)
```

### `Roll CRM`

CRM-Seite: Neugeschäft im gewählten Zeitraum, dessen Entscheidung im Vorjahr fällt – der Roll-Anteil. Bewertung folgt dem Datenschnitt 'Szenario Bewertung'.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll CRM =
CALCULATE (
    [Net New ITY],
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[ITY Cluster] = "unknown Roll" )
)
```

### `Roll Deckungsgrad`

Deckt die gewichtete Pipeline die Lücke? Über 100 Prozent = die offenen Opportunities reichen im Erwartungswert aus. Unter 100 Prozent = es fehlt Pipeline, nicht nur Abschlussquote.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Roll Deckungsgrad =
DIVIDE ( [Roll offen (gewichtet)], [Roll Lücke] )
```

### `Roll Lücke`

DIE Kernzahl der Seite: Was fehlt noch bis zum Roll-Budget? Budget minus bereits Gewonnenes. Positiv = es fehlt noch etwas.

Bewusst gegen [Roll gesichert] gerechnet, nicht gegen die gewichtete Pipeline: die Frage lautet "was muss noch kommen", nicht "was erwarten wir im Mittel".

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll Lücke =
[Roll Budget] - [Roll gesichert]
```

### `Roll Zielerreichung`

Zielerreichung Roll gesamt: Gewonnenes plus gewichtete Pipeline gegen Budget.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Roll Zielerreichung =
DIVIDE ( [Roll gesichert] + [Roll offen (gewichtet)], [Roll Budget] )
```

### `Roll gesichert`

Bereits gewonnener Roll-Anteil. Ungewichtet, weil WON keine Wahrscheinlichkeit mehr trägt – der Auftrag liegt vor. Das ist der Sockel, auf dem die Lücke aufsetzt.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll gesichert =
CALCULATE (
    SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[ITY Cluster] = "unknown Roll" ),
    KEEPFILTERS ( 'DIM Status'[Status Code] = "WON" )
)
```

### `Roll offen (Vollwert)`

Voller Wert des noch offenen Roll-Anteils, ohne Gewichtung. Obergrenze: so viel wäre erreichbar, wenn ALLES gewonnen würde.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll offen (Vollwert) =
CALCULATE (
    SUM ( 'FCT Net New ITY'[Betrag ungewichtet (vorzeichenbehaftet)] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[ITY Cluster] = "unknown Roll" ),
    KEEPFILTERS ( 'DIM Status'[Status Code] IN { "EXPECTED_WIN", "PIPELINE", "NO_PROBABILITY" } )
)
```

### `Roll offen (gewichtet)`

Noch offener Roll-Anteil, gewichtet mit der Win-Wahrscheinlichkeit. Enthält Expected Win und Pipeline – also alles, was noch zu gewinnen ist. Das ist der erwartete Beitrag der laufenden Verhandlungen.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Roll offen (gewichtet) =
CALCULATE (
    SUM ( 'FCT Net New ITY'[Betrag] ),
    KEEPFILTERS ( 'FCT Net New ITY'[Geschäftsart] = "NEW" ),
    KEEPFILTERS ( 'FCT Net New ITY'[ITY Cluster] = "unknown Roll" ),
    KEEPFILTERS ( 'DIM Status'[Status Code] IN { "EXPECTED_WIN", "PIPELINE", "NO_PROBABILITY" } )
)
```

### `Schließt Lücke`

Reicht dieser Vorgang zusammen mit allen größeren aus, um die Lücke zu schließen? Färbt die Rangliste ein: alles bis zur ersten "Ja"-Zeile ist das Minimalpaket, das gewonnen werden muss.

```dax
Schließt Lücke =
IF ( [Beitrag kumuliert] >= [Roll Lücke], "Ja", "Nein" )
```

### `Unknown ITY Budget`

Budgetseite: ITY-Anteil des unknown-ITY-Budgets (Planbetriebe Typ ITY). Entscheidungen dazu fallen erst im Budgetjahr selbst.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Unknown ITY Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
    KEEPFILTERS ( 'FCT Umsatz'[Betriebstyp] = "Plan-Betriebe ITY" )
)
```
