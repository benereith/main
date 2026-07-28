# 03 – Berechnungslogik aller Kennzahlen

> **Diese Datei wird erzeugt.** Sie entsteht aus den TMDL-Dateien des
> Semantikmodells über `python3 tools/generate_docs.py`. Änderungen bitte
> an der Quelle vornehmen (`powerbi/Net New ITY Cockpit.SemanticModel/`),
> nicht hier.


Das Modell enthält **51 Kennzahlen** in 9 Ordnern.

## Inhalt

- [01 Basis](#01-basis) – 10 Kennzahlen
- [02 Status](#02-status) – 10 Kennzahlen
- [03 Zeit](#03-zeit) – 4 Kennzahlen
- [04 Szenarien](#04-szenarien) – 4 Kennzahlen
- [05 Budget und Forecast](#05-budget-und-forecast) – 7 Kennzahlen
- [06 Quoten](#06-quoten) – 4 Kennzahlen
- [07 CRM-Bewegung](#07-crm-bewegung) – 5 Kennzahlen
- [08 Datenqualität](#08-datenqualität) – 3 Kennzahlen
- [09 Titel und Kontext](#09-titel-und-kontext) – 4 Kennzahlen


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

Net New ITY = New Business ITY minus Lost Business ITY, im Filterkontext.

Die Bewertungsbasis wird über den Datenschnitt 'Szenario Bewertung' gesteuert: CRM-gewichtet  Umsatz × Eintrittswahrscheinlichkeit (Standard) Vollwert       Umsatz ohne Gewichtung – Obergrenze Nur gesichert  nur Won und Lost, ungewichtet – Untergrenze

Vorzeichen: New positiv, Lost negativ. Die Umkehr passiert einmalig im Lakehouse (amount_signed), nicht in dieser Kennzahl. HFM: MAP141a minus MAP141c (ITY-Ebene).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Net New ITY =
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
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_20" )
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

Gebuchter Umsatz laut SAP (Version 0).

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Umsatz Ist =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Actual_0" )
)
```

### `Unknown ITY Budget`

Budgetierter unknown-ITY-Effekt (SAP-Version 90, Planbetriebe). Der Wert, gegen den die CRM-Approximation gestellt wird.

**Format:** `#,0\ "€";-#,0\ "€";#,0\ "€"`

```dax
Unknown ITY Budget =
CALCULATE (
    SUM ( 'FCT Umsatz'[Monatswert] ),
    KEEPFILTERS ( 'FCT Umsatz'[Werttyp Version] = "Plan_90" ),
    KEEPFILTERS ( 'FCT Umsatz'[Betriebstyp] <> "Real-Betriebe" )
)
```

### `Zielerreichung`

Zielerreichung der CRM-Approximation gegenüber Budget.

**Format:** `0.0\ %;-0.0\ %;0.0\ %`

```dax
Zielerreichung =
DIVIDE ( [Net New ITY (Szenario)], [Unknown ITY Budget] )
```

### `Δ CRM zu Budget`

Abweichung der CRM-Approximation vom Budget. Positiv = das CRM zeigt mehr Net New ITY, als budgetiert wurde.

**Format:** `+#,0\ "€";-#,0\ "€";0\ "€"`

```dax
Δ CRM zu Budget =
[Net New ITY (Szenario)] - [Unknown ITY Budget]
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

Kernaussage zur Entwicklung des Net New ITY. Benennt Richtung und Größenordnung statt nur die Kennzahl zu wiederholen.

```dax
Aussage Net New =
VAR _Wert = [Net New ITY (Szenario)]
VAR _Budget = [Unknown ITY Budget]
VAR _Delta = _Wert - _Budget
VAR _Richtung = IF ( _Delta >= 0, "über", "unter" )
RETURN
    IF (
        ISBLANK ( _Budget ),
        "Net New ITY: " & FORMAT ( _Wert, "#,0 €" ),
        "Net New ITY liegt " & FORMAT ( ABS ( _Delta ), "#,0 €" ) & " "
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
