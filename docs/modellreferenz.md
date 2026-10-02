# Modellreferenz Flash_Basis

Automatisch aus den `///`-Beschreibungen der TMDL-Dateien erzeugt (`Flash/Flash_Basis.SemanticModel/definition`). Bei Änderungen am Modell die Beschreibung im TMDL pflegen, nicht diese Datei. Ausgeblendete Objekte sind mit *(ausgeblendet)* markiert.

## Tabellen und Spalten

### Fakt_SAP

SAP-Werte je Werk, Periode, Konto und Version (Faktentabelle). Bewusst schmal: Werk und Periode stecken im Status_Key, die Zeit- und Unit-Filter laufen über Dim_UnitStatus. Faktenzeilen von Werken außerhalb der Managementbereiche werden beim Laden verworfen.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Status_Key` *(ausgeblendet)* | Int64 | Schlüssel Werk * 1.000.000 + Geschäftsjahr * 100 + Periode. Verknüpfung zu Dim_UnitStatus. |
| `Konto` *(ausgeblendet)* | String | Konto / Kostenart. Verknüpfung zu Dim_Konto. |
| `Version` *(ausgeblendet)* | String | SAP-Version: 0 = Actuals, 20 = Budget, RGF/R12 = aktueller Forecast, RF/35/RTD = weitere Forecast-Stände, V = Version V. |
| `Wert` *(ausgeblendet)* | Decimal | Betrag in Euro. Nicht direkt verwenden, sondern über die Measures (Act, Budget, Forecast, Flash). |

### Dim_UnitStatus

Abrechnungsstatus und Flash-Szenario je Werk UND Periode. Zentrale Tabelle der Mehrmonats-Logik: Dim_Unit und Dim_Datum filtern diese Tabelle, sie filtert Fakt_SAP und Kommentare. Dadurch gilt jeder Monat mit dem Status, den er hat, und Unit-Zählungen respektieren Unit- und Monatsfilter. Achtung Historie: IA_Stammdaten enthält je Werk nur das letzte Übergabedatum. Für Monate vor diesem Datum ergibt die Regel daher 'Kein Kennzeichen' (= Actuals) - was für abgeschlossene Monate fachlich passt, aber keine echte Statushistorie ist.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Status_Key` *(ausgeblendet)* | Int64 | Schlüssel Werk * 1.000.000 + Geschäftsjahr * 100 + Periode. Verknüpfung zu Fakt_SAP und Kommentare. |
| `Werk` *(ausgeblendet)* | Int64 | Werksnummer. Verknüpfung zu Dim_Unit. |
| `Periode` *(ausgeblendet)* | Int64 | SAP-Periode 1-12 (1 = Oktober). |
| `Datum` *(ausgeblendet)* | DateTime | Erster Kalendertag der Periode. Verknüpfung zu Dim_Datum. |
| `FIBU_Übergabe` | DateTime | Spätestes FIBU-Übergabedatum der Unit (nicht periodenbezogen). |
| `Flash_Übergabe` | DateTime | Spätestes Flash-Übergabedatum der Unit (nicht periodenbezogen). |
| `Kennzeichen` *(ausgeblendet)* | String | Rohes Kennzeichen aus den Übergabedaten, bewertet gegen genau diese Periode: Abgerechnet (FIBU-Übergabe im Monat), Flash (Flash-Übergabe im Monat), Offen (FIBU-Übergabe im Vormonat), sonst Kein Kennzeichen. |
| `Hat_Actuals` *(ausgeblendet)* | Boolean | Wahr, wenn die Unit in dieser Periode Actuals (SAP-Version 0) mit Wert <> 0 hat. |
| `Hat_Budget` *(ausgeblendet)* | Boolean | Wahr, wenn die Unit in dieser Periode Budgetwerte (SAP-Version 20) mit Wert <> 0 hat. |
| `Hat_Forecast` *(ausgeblendet)* | Boolean | Wahr, wenn die Unit in dieser Periode Forecastwerte (RF, RGF, 35, R12, RTD) mit Wert <> 0 hat. |
| `Innenauftragsart` *(ausgeblendet)* | String | Innenauftragsart der Unit (Kopie aus Dim_Unit, nur zur Szenario-Berechnung). |
| `Vertragsart` *(ausgeblendet)* | String | Vertragsart der Unit (Kopie aus Dim_Unit, nur zur Szenario-Berechnung). |
| `Status` | String | Auswertbarer Status der Unit in dieser Periode. Inaktiv          - weder Actuals (0) noch Budget (20) noch Forecast (RF/RGF/35/R12/RTD). Mit Abrechnung oder Flash ist nicht zu rechnen; die Unit fällt aus dem Flash. Kein Kennzeichen - Werte vorhanden, aber weder Abrechnung noch Flash gemeldet. Echte Kennzeichnung, wird als Actuals gerechnet. Abgerechnet      - FIBU-Übergabe in diesem Monat. Flash            - Flash-Übergabe in diesem Monat. Offen            - FIBU-Übergabe im Vormonat, in diesem Monat noch nichts. |
| `Status_Sortierung` *(ausgeblendet)* | Int64 | Fachliche Sortierreihenfolge für Status. |
| `Flash_Szenario` | String (berechnet) | Welche Wertart bildet für diese Unit in dieser Periode den Flash ab? Ohne Wertung - Status Inaktiv, kein Beitrag zum Flash. ACT          - Innenauftragsart I oder N, oder Status Abgerechnet / Kein Kennzeichen. FC           - Status Offen, oder Status Flash bei Vertragsart PR / M / XK / XP. V            - alles Übrige. Die Kanne-Sonderlogik ist bewusst NICHT hier, sondern in der Measure Flash: ein Slicer kann keine berechnete Spalte umsteuern. |

### Dim_Unit

Units (Werke) mit Organisationszuordnung. Reine Stammdaten ohne Zeitbezug: alles, was sich je Monat ändert (Abrechnungsstatus, Flash-Szenario), liegt in Dim_UnitStatus.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Werk` *(ausgeblendet)* | Int64 | Werksnummer (Schlüssel). Verknüpfung zu Dim_UnitStatus. |
| `Werk - Bezeichnung` | String | Werksnummer (vierstellig) und Bezeichnung, z. B. '0127 - Musterbetrieb'. Standardfeld zur Anzeige einer Unit. |
| `Betriebsbezeichnung` *(ausgeblendet)* | String | Reine Bezeichnung des Betriebs ohne Werksnummer. |
| `Managementbereich` | String | Managementbereich der Unit (Eurest, Food Affairs, Kanne, Leonardi, Medirest). Der Wert 'Kanne' steuert die Sonderlogik der Measure Flash. |
| `Region` | String | Region der Unit. |
| `Bezirk` | String | Bezirk der Unit. |
| `Sektor` | String | Sektor der Unit. |
| `Betriebstyp` | String | Plan-Betriebe Roll, Plan-Betriebe ITY oder Real-Betriebe. Ableitung über die Listen Planbetriebe_Roll und Planbetriebe_ITY. |
| `Vertragsart` | String | Vertragsart der Unit (z. B. PR, M, XK, XP). Steuert in Dim_UnitStatus, ob eine Flash-Meldung als Forecast gilt. |
| `Innenauftragsart` | String | Innenauftragsart der Unit. I und N werden im Flash immer als Actuals gerechnet, P wird per Berichtsfilter ausgeschlossen. |
| `Buchungskreis` | Int64 | Buchungskreis der Unit. |
| `Service` | Int64 | Service-Kennzeichen der Unit. |
| `Verantwortungsbereich` | Int64 | Verantwortungsbereich der Unit. |

### Dim_Datum

Datumsdimension des geladenen Geschäftsjahres (Oktober bis September), taggenau. Die Fakten sind monatsgenau und hängen am ersten Tag des Monats. Die Tabelle enthält bewusst nur das aktuelle Geschäftsjahr: so ist MAX(FY_Jahr) im ungefilterten Kontext eindeutig und der Monats-Slicer zeigt genau zwölf Einträge.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Datum` *(ausgeblendet)* | DateTime | Kalendertag. Schlüsselspalte der Datumstabelle; Verknüpfung zu Dim_UnitStatus über den Monatsersten. |
| `Periode` | String | SAP-Periode mit Monat, z. B. 'P09 · Jun 26'. Das Feld für den Monats-Slicer; sortiert nach Geschäftsjahresmonat. |
| `Monat` | String | Monatsname (z. B. Juni), sortiert nach Geschäftsjahresmonat. |
| `FY_Jahr` | String | Geschäftsjahr als Text, z. B. 'FY2025/26'. |
| `FY_Quartal` | String | Geschäftsquartal, z. B. 'FQ3'. |
| `FY_QuartalNr` *(ausgeblendet)* | Int64 | Nummer des Geschäftsquartals 1-4. Sortierspalte für FY_Quartal. |
| `FY_MonatNr` *(ausgeblendet)* | Int64 | Geschäftsjahresmonat 1-12 (Oktober = 1) und damit identisch zur SAP-Periode. Grundlage der Kumulierung (YTD) in der Measure _Wert P&L. |
| `Ist_Berichtsmonat` *(ausgeblendet)* | Boolean | Wahr für den Monat, der dem Parameter Aktuelle_Periode entspricht. Dient als Standardmonat, solange im Bericht kein Monat gewählt ist. |

### Dim_Konto

Kontenplan mit GuV-Hierarchie aus dem Warehouse (dbo.tab_accounts_hierarchy).

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Konto` *(ausgeblendet)* | String | Kostenart / Konto (Schlüssel). Verknüpfung zu Fakt_SAP. |
| `Konto Bezeichnung` | String | Beschreibung der Kostenart. |
| `GuV Ebene 2` | String | Ebene 2 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 3` | String | Ebene 3 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 4` | String | Ebene 4 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 5` | String | Ebene 5 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 6` *(ausgeblendet)* | String | Ebene 6 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 7` *(ausgeblendet)* | String | Ebene 7 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 8` *(ausgeblendet)* | String | Ebene 8 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `GuV Ebene 9` *(ausgeblendet)* | String | Ebene 9 der GuV-Hierarchie (Schlüssel mit Bezeichnung). |
| `Typ` | String | Kontotyp, z. B. 'P&L'. Der Bericht rechnet ausschließlich mit P&L-Konten. |
| `Kennzahl` | String | Ordnet die drei Steuerkennzahlen der Quoten-Logik zu: Umsatz, CoS, Overhead (sonst leer). Wird anhand des Schlüsselpräfixes der Ebene 2 gebildet (IS10000_T, IS20000_T, IS40000_T), nicht über den ganzen Text. |

### Kommentare

Berichtskommentare je Werk und Periode, gelesen aus der Fabric-SQL-Datenbank. DirectQuery, damit ein über den Translytical Task Flow gespeicherter Kommentar ohne Modell-Refresh sichtbar ist. Einrichtung von Datenbank, Tabelle und User Data Function: docs/kommentare/README.md.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Kommentar_ID` *(ausgeblendet)* | Int64 | Technischer Primärschlüssel aus der SQL-Tabelle. |
| `Status_Key` *(ausgeblendet)* | Int64 | Schlüssel Werk * 1.000.000 + Geschäftsjahr * 100 + Periode (in SQL berechnet). Verknüpfung zu Dim_UnitStatus. |
| `Werk` *(ausgeblendet)* | Int64 | Werksnummer, auf die sich der Kommentar bezieht. |
| `Periode` *(ausgeblendet)* | Int64 | SAP-Periode des Kommentars (1 = Oktober). |
| `Kommentar` | String | Freitext des Kommentars. |
| `Kategorie` | String | Einordnung des Kommentars (Abrechnung, CoS, Overhead, Umsatz, Sonstiges). |
| `Erfasst_von` | String | Benutzer, der den Kommentar erfasst hat. Wird von der User Data Function aus dem Aufrufkontext gesetzt. |
| `Erfasst_am` | DateTime | Zeitpunkt der Erfassung (UTC). |

### p_Zeitbezug

Steuertabelle ohne Beziehung: Einzelmonat oder kumuliert (YTD). Ausgewertet an genau einer Stelle, in der Measure _Wert P&L. Alles darauf Aufbauende (Act, Budget, Forecast, Flash, Quoten, Flex, Rang) folgt automatisch. Ohne Auswahl gilt Einzelmonat.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Zeitbezug` | String | Auswahlwert: 'Einzelmonat' oder 'Kumuliert (YTD)'. |
| `Sortierung` *(ausgeblendet)* | Int64 | Sortierung, damit 'Einzelmonat' vorne steht. |

### p_Kanne_Abrechnung

Steuertabelle ohne Beziehung: Schalter für den Managementbereich Kanne. Kanne wird abweichend abgerechnet. Bei 'Ja' zählen alle Kanne-Units mit ihren Ist-Werten (SAP-Version 0), unabhängig vom Übergabestatus; bei 'Nein' gilt dieselbe Logik wie für alle anderen Bereiche. Wirkt ausschließlich über die Measure Flash und braucht keinen Refresh.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Kanne abgerechnet` | String | Auswahlwert: 'Nein' (Standard, Statuslogik) oder 'Ja' (Kanne komplett als Actuals). |
| `Sortierung` *(ausgeblendet)* | Int64 | Sortierung, damit 'Nein' vor 'Ja' steht. |

### p_TopN

Steuertabelle ohne Beziehung: Anzahl der Units in den Flop-Listen (Standard 20).

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Top N` | Int64 | Auswahlwert 5 bis 50 in Fünferschritten. |

### p_Kategorie

Steuertabelle ohne Beziehung: Auswahlliste der Kommentarkategorien für die Erfassung (Translytical Task Flow). Die Liste muss zu KATEGORIEN in der User Data Function passen.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Kategorie` | String | Kommentarkategorie zur Auswahl in der Erfassungsmaske. |
| `Sortierung` *(ausgeblendet)* | Int64 | Sortierung der Kategorien. |

### p_Eingabe

Steuertabelle ohne Beziehung: Platzhalterfeld für das Texteingabefeld der Kommentarerfassung. Der Text-Slicer braucht ein Feld; über diese entkoppelte Tabelle beeinflusst die Eingabe keine anderen Visuals.

| Spalte | Typ | Beschreibung |
| --- | --- | --- |
| `Kommentartext` | String | Platzhalter für den eingegebenen Kommentartext. Enthält keine Daten. |

## Measures

Zentrale Measure-Tabelle des Flash-Berichts. Aufbau in Schichten, damit Änderungen nur an einer Stelle nötig sind: 1 Werte      - Act, Budget, Forecast, Version V (alle über die Zeitlogik in _Wert P&L) 2 Flash      - Szenario-Mix je Unit inklusive Kanne-Schalter 3-5          - Abweichungen, Quoten/Flex und Rangfolge bauen ausschließlich auf Schicht 1 und 2 auf 6-8          - Datenlage, Kommentare, Kopfzeile 9 Hilfsmaße - ausgeblendete Bausteine und Farbmeasures

### 1 Werte

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Act` | `#,0\ "€";-#,0\ "€";0\ "€"` | Ist-Werte (SAP-Version 0) der P&L-Konten im betrachteten Zeitraum. |
| `Budget` | `#,0\ "€";-#,0\ "€";0\ "€"` | Budgetwerte (SAP-Version 20) der P&L-Konten im betrachteten Zeitraum. |
| `Forecast` | `#,0\ "€";-#,0\ "€";0\ "€"` | Aktueller Forecast der P&L-Konten: Summe aus RGF und R12. Die übrigen Forecast-Stände (RF, 35, RTD) zählen nur für die Datenprüfung in Dim_UnitStatus, nicht hier. |
| `Version V` | `#,0\ "€";-#,0\ "€";0\ "€"` | Werte der SAP-Version V. Wird im Flash für Units verwendet, die weder als Actuals noch als Forecast gelten. |

### 2 Flash

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Flash` | `#,0\ "€";-#,0\ "€";0\ "€"` | Flash-Wert des Berichts. Alle Managementbereiche außer Kanne folgen der Statuslogik aus Dim_UnitStatus[Flash_Szenario]. Kanne hängt am Schalter p_Kanne_Abrechnung: 'Ja'   - Kanne ist abgerechnet, alle Kanne-Units zählen mit ihren Ist-Werten (ACT) 'Nein' - Kanne folgt derselben ACT/FC/V-Logik wie alle anderen Bereiche (Standard) KEEPFILTERS erhält eine im Bericht gesetzte Auswahl des Managementbereichs: ist Kanne herausgefiltert, bleibt der Kanne-Teil leer. |

### 3 Abweichungen

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Abw. Flash zu Budget` | `#,0\ "€";-#,0\ "€";0\ "€"` | Flash minus Budget in Euro. Positiv = besser als Budget, sofern Kosten in den SAP-Daten negativ geführt werden. |
| `Abw. Flash zu Budget %` | `+0.0\ %;-0.0\ %;0.0\ %` | Abweichung Flash zu Budget relativ zum Betrag des Budgets. |
| `Abw. Flash zu Forecast` | `#,0\ "€";-#,0\ "€";0\ "€"` | Flash minus Forecast (RGF + R12) in Euro. Positiv = besser als Forecast, sofern Kosten negativ geführt werden. |
| `Abw. Flash zu Forecast %` | `+0.0\ %;-0.0\ %;0.0\ %` | Abweichung Flash zu Forecast relativ zum Betrag des Forecasts. |

### 4 Quoten und Flex

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Act CoS` | `#,0\ "€";-#,0\ "€";0\ "€"` | Ist-Wert der Kennzahl CoS (Konten mit Kennzahl = CoS). |
| `Act CoS-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | CoS im Verhältnis zum Umsatz, auf Basis der Ist-Werte. |
| `Act OvH-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | Overhead im Verhältnis zum Umsatz, auf Basis der Ist-Werte. |
| `Act Overhead` | `#,0\ "€";-#,0\ "€";0\ "€"` | Ist-Wert der Kennzahl Overhead (Konten mit Kennzahl = Overhead). |
| `Act Umsatz` | `#,0\ "€";-#,0\ "€";0\ "€"` | Ist-Wert der Kennzahl Umsatz (Konten mit Kennzahl = Umsatz). |
| `Delta CoS-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | Abweichung der CoS-Quote im Ist gegen den Forecast in Prozentpunkten. Negativ = ungeplant höhere Kostenquote (Kosten sind negativ geführt). |
| `Delta OvH-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | Abweichung der OvH-Quote im Ist gegen den Forecast in Prozentpunkten. Negativ = ungeplant höhere Kostenquote (Kosten sind negativ geführt). |
| `FC CoS` | `#,0\ "€";-#,0\ "€";0\ "€"` | Forecast-Wert der Kennzahl CoS (Konten mit Kennzahl = CoS). |
| `FC CoS-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | CoS im Verhältnis zum Umsatz, auf Basis des Forecasts. |
| `FC OvH-Quote` | `0.00\ %;-0.00\ %;0.00\ %` | Overhead im Verhältnis zum Umsatz, auf Basis des Forecasts. |
| `FC Overhead` | `#,0\ "€";-#,0\ "€";0\ "€"` | Forecast-Wert der Kennzahl Overhead (Konten mit Kennzahl = Overhead). |
| `FC Umsatz` | `#,0\ "€";-#,0\ "€";0\ "€"` | Forecast-Wert der Kennzahl Umsatz (Konten mit Kennzahl = Umsatz). |
| `Flex CoS` | `#,0\ "€";-#,0\ "€";0\ "€"` | Geflexter CoS-Effekt in Euro: Ist-Umsatz mal Quotenabweichung. Beantwortet, was die Quotenabweichung bei dem tatsächlichen Umsatz kostet. |
| `Flex OvH` | `#,0\ "€";-#,0\ "€";0\ "€"` | Geflexter OvH-Effekt in Euro: Ist-Umsatz mal Quotenabweichung. Beantwortet, was die Quotenabweichung bei dem tatsächlichen Umsatz kostet. |

### 5 Rangfolge

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Im Top N Act` | `0` | 1, wenn die Unit zu den N niedrigsten nach Act gehört, sonst leer. Visual-Filter 'ist nicht leer'. |
| `Im Top N CoS` | `0` | 1, wenn die Unit zu den N schlechtesten nach Flex CoS gehört, sonst leer. Visual-Filter 'ist nicht leer'. |
| `Im Top N OvH` | `0` | 1, wenn die Unit zu den N schlechtesten nach Flex OvH gehört, sonst leer. Visual-Filter 'ist nicht leer'. |
| `Rang Act` | `0` | Rang der Unit nach Act (1 = niedrigster Wert). Grundlage der Flop-UPC-Seite. |
| `Rang Flex CoS` | `0` | Rang der Unit nach Flex CoS (1 = größter Nachteil). Berücksichtigt nur Units mit Ist-Umsatz > 0; die Wertung erfolgt über alle im Bericht gewählten Units (ALLSELECTED). |
| `Rang Flex OvH` | `0` | Rang der Unit nach Flex OvH (1 = größter Nachteil). Berücksichtigt nur Units mit Ist-Umsatz > 0. |

### 6 Datenlage

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Units` | `0` | Anzahl Units im Filterkontext. Ohne Monatsauswahl der Berichtsmonat. Unabhängig vom Zeitbezug-Schalter. |
| `Units inaktiv` | `0` | Units ohne Actuals, Budget und Forecast im betrachteten Monat. Mit Abrechnung oder Flash ist nicht zu rechnen. |
| `Units ohne Kennzeichen` | `0` | Units mit Werten, aber ohne Abrechnungs- oder Flash-Kennzeichen im betrachteten Monat. Werden als Actuals gerechnet. |

### 7 Kommentare

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Kommentar Anzahl` | `0` | Anzahl der Kommentare im aktuellen Filterkontext. |
| `Letzter Kommentar am` | `dd.mm.yyyy hh:nn` | Zeitpunkt des jüngsten Kommentars im Filterkontext. |

### 8 Kopfzeile

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Berichtskopf` |  | Textzeile für den Berichtskopf: betrachteter Monat, Zeitbezug und Kanne-Einstellung. |
| `Unit-Titel` |  | Name der ausgewählten Unit, für die Überschrift der Drillthrough-Seite Unit-Detail. |

### 9 Hilfsmaße

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `_Berichtsmonat Nr` *(ausgeblendet)* | `0` | Geschäftsjahresmonat (1-12) des Berichtsmonats laut Parameter Aktuelle_Periode, unabhängig von allen Filtern. |
| `_Bis Monat Nr` *(ausgeblendet)* | `0` | Letzter betrachteter Geschäftsjahresmonat: der späteste gewählte Monat, ohne Auswahl der Berichtsmonat. |
| `_Flash nach Status` *(ausgeblendet)* | `#,0\ "€";-#,0\ "€";0\ "€"` | Flash nach reiner Statuslogik, ohne Kanne-Ausnahme. Je Unit und Periode entscheidet Dim_UnitStatus[Flash_Szenario], welche Wertart zählt. Units mit Szenario 'Ohne Wertung' (Status Inaktiv) tauchen in keinem Zweig auf. |
| `_Kanne abgerechnet` *(ausgeblendet)* |  | Wahr, wenn der Kanne-Schalter auf 'Ja' steht. Ohne eindeutige Auswahl gilt 'Nein'. |
| `_Kumuliert` *(ausgeblendet)* |  | Wahr, wenn der Zeitbezug-Schalter auf 'Kumuliert (YTD)' steht. Ohne eindeutige Auswahl gilt Einzelmonat. |
| `_Monat gefiltert` *(ausgeblendet)* |  | Wahr, wenn im aktuellen Kontext irgendein Monatsfilter auf Dim_Datum liegt (Slicer, Zeile, Spalte). Falsch = es ist nichts gewählt, dann gilt der Berichtsmonat. |
| `_Top N` *(ausgeblendet)* | `0` | Gewählte Anzahl der Flop-Units, ohne Auswahl 20. |
| `_Wert P&L` *(ausgeblendet)* | `#,0\ "€";-#,0\ "€";0\ "€"` | Summe aller P&L-Werte im betrachteten Zeitraum, noch ohne Versionsfilter. Einzige Stelle mit Zeitlogik: alle Werte-Measures, Flash, Quoten, Flex und Rang bauen darauf auf und folgen dem Zeitbezug-Schalter automatisch. |

### 9 Hilfsmaße / Farben

| Measure | Format | Beschreibung |
| --- | --- | --- |
| `Farbe Abw. Budget` *(ausgeblendet)* |  | Schriftfarbe für Abweichungen zu Budget: rot negativ, grün positiv, sonst grau. |
| `Farbe Abw. Forecast` *(ausgeblendet)* |  | Schriftfarbe für Abweichungen zu Forecast: rot negativ, grün positiv, sonst grau. |
| `Farbe Act` *(ausgeblendet)* |  | Schriftfarbe für Act: rot negativ, grün positiv, sonst grau. |
| `Farbe Flex CoS` *(ausgeblendet)* |  | Schriftfarbe für Flex CoS und Delta CoS-Quote: rot negativ, grün positiv, sonst grau. |
| `Farbe Flex OvH` *(ausgeblendet)* |  | Schriftfarbe für Flex OvH und Delta OvH-Quote: rot negativ, grün positiv, sonst grau. |
