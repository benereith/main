# 02 – Datenmodell

> **Diese Datei wird erzeugt.** Sie entsteht aus den TMDL-Dateien des
> Semantikmodells über `python3 tools/generate_docs.py`. Änderungen bitte
> an der Quelle vornehmen (`powerbi/Net New ITY Cockpit.SemanticModel/`),
> nicht hier.


## Überblick

| Tabelle | Rolle | Spalten | Kennzahlen | Quelle |
|---|---|---:|---:|---|
| `CRM Data` | Prüfung | 4 | 3 | – |
| `DIM Betrieb` | Dimension | 23 | 3 | `gold_dim_unit` |
| `DIM Datum` | Dimension | 18 | 0 | `gold_dim_date` |
| `DIM HFM-Struktur` | Dimension | 11 | 0 | `gold_dim_hfm_struktur` |
| `DIM Opportunity` | Dimension | 21 | 0 | `gold_dim_opportunity` |
| `DIM Status` | Dimension | 8 | 0 | `gold_dim_status` |
| `DIM Vertrag` | Dimension | 19 | 0 | `gold_dim_contract` |
| `DQ Prüfungen` | Prüfung | 6 | 0 | `gold_dq_checks` |
| `FCT CRM-Bewegung` | Fakt | 14 | 0 | `gold_fct_crm_movement` |
| `FCT Net New ITY` | Fakt | 35 | 0 | `gold_fct_net_new_ity` |
| `FCT Umsatz` | Fakt | 17 | 0 | `gold_fct_revenue` |
| `Szenario Anlauf` | Szenario-Parameter | 2 | 0 | berechnet (DATATABLE) |
| `Szenario Anlaufdauer` | Szenario-Parameter | 2 | 0 | berechnet (DATATABLE) |
| `Szenario Bewertung` | Szenario-Parameter | 3 | 0 | berechnet (DATATABLE) |
| `Szenario Schwelle` | Szenario-Parameter | 2 | 0 | berechnet (DATATABLE) |
| `Szenario Verschiebung` | Szenario-Parameter | 3 | 0 | berechnet (DATATABLE) |
| `_Kennzahlen` | Kennzahlen | 1 | 70 | – |

## Beziehungen

Grundregeln, die in den Altmodellen verletzt waren:

1. Nur EINE Richtung. Die Altmodelle hatten elf beidseitig filternde
   Beziehungen (dim_opp_* zu fct_opp), was Filterpfade unvorhersehbar
   und Measures nicht mehr lokal nachvollziehbar macht.
2. Keine Auto-Datumstabellen. Die Altmodelle trugen 12 bis 19
   LocalDateTable_*-Tabellen mit sich.
3. Ein Kalender für alle Fakten, verbunden über den Monatsbeginn.

| Von | Nach | Aktiv | Zweck |
|---|---|---|---|
| `'FCT Net New ITY'.Periode` | `'DIM Datum'.Datum` | ja | Wirkungsperiode des Net New ITY. Der Fakt liegt auf Monatsebene, deshalb Verbindung auf den Monatsbeginn. |
| `'FCT Net New ITY'.'Status Code'` | `'DIM Status'.'Status Code'` | ja | Statusdimension. Filtert die Zerlegung nach Sicherheitsgrad. |
| `'FCT Net New ITY'.'Entität ID'` | `'DIM Opportunity'.'Opportunity ID'` | ja | Opportunity-Stammdaten. Nur New-Business-Zeilen finden einen Treffer; Lost-Business-Zeilen laufen ins Leere, was fachlich korrekt ist. |
| `'FCT Net New ITY'.'Entität ID'` | `'DIM Vertrag'.'Vertrag ID'` | nein | Vertragsstammdaten. Spiegelbild der Opportunity-Beziehung: nur Lost-Business-Zeilen treffen. Deshalb INAKTIV – zwei aktive Beziehungen vom selben Schlüssel auf zwei Dimensionen wären ein mehrdeutiger Pfad. Aktiviert wird sie in den Vertragsvisualisierungen über USERELATIONSHIP. |
| `'FCT Net New ITY'.Werk` | `'DIM Betrieb'.Werk` | ja | Betriebszuordnung, soweit im CRM gepflegt (cgplc_sapid). |
| `'FCT Umsatz'.Periode` | `'DIM Datum'.Datum` | ja | SAP-Umsätze an denselben Kalender. |
| `'FCT Umsatz'.Werk` | `'DIM Betrieb'.Werk` | ja | SAP-Umsätze an die Betriebsdimension. |
| `'FCT Umsatz'.'Metric ID'` | `'DIM HFM-Struktur'.'Metric ID'` | ja | SAP-Umsätze an die Net-New-Hierarchie über das Cause-of-Change-Mapping. |
| `'FCT CRM-Bewegung'.'Entität ID'` | `'DIM Opportunity'.'Opportunity ID'` | ja | Bewegungsdaten an die Opportunity-Stammdaten, damit in der Bewegungsanalyse Kunde, Sektor und Verantwortlicher verfügbar sind. |
| `'FCT CRM-Bewegung'.'Entität ID'` | `'DIM Vertrag'.'Vertrag ID'` | nein | Bewegungsdaten an die Vertragsstammdaten. Inaktiv aus demselben Grund wie bei der Faktentabelle. |
| `'DIM Opportunity'.status_code` | `'DIM Status'.'Status Code'` | nein | Statusdimension an die Opportunity-Stammdaten. INAKTIV – der Fakt verbindet bereits auf DIM Status; eine zweite aktive Beziehung auf dieselbe Dimension wäre ein mehrdeutiger Filterpfad. |
| `'DIM Vertrag'.status_code` | `'DIM Status'.'Status Code'` | ja | Statusdimension an die Vertragsstammdaten. Erlaubt die Auswertung der Risikostufe direkt auf der Vertragsdimension. |
| `'FCT Net New ITY'.Entität` | `'CRM Data'.name` | ja | Faktentabelle an die manuell gepflegte Planungsdatei (2026_04_29_Planung_unknown_ITY_Effekt.xlsx), verbunden über den Namen des Vorgangs. Namensbasierte Verbindungen sind empfindlich gegen Umbenennungen im CRM – abweichende Schreibweisen fallen in die Blank-Zeile. |

## Tabellen im Detail

### `CRM Data`

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `NB/LB` | string | `NB/LB` | – |
| `name` | string | `name` | – |
| `ity_cluster` | string | `ity_cluster` | – |
| `ity effect` | double | `ity effect` | – |

### `DIM Betrieb`

SAP-Betriebsstammdaten (Werke). Quelle: gold_dim_unit. Ersetzt SAP_Stammdaten bzw. dim_sap_master_data_unit der Altmodelle.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Werk` | int64 | `betrieb` | – |
| `Werk Bezeichnung` | string | `werk_bezeichnung` | "0123 – Bezeichnung". Führende Nullen, damit die Sortierung stimmt. |
| `Betriebsname` | string | `bezeichnung_betrieb` | – |
| `Buchungskreis` | int64 | `buchungskreis` | – |
| `Sektor` | string | `sektor` | – |
| `HFM Sektor` | string | `hfm_sektor` | Harmonisierter Sektor für die HFM-Meldung (HC / BU / …). |
| `Betriebstyp` | string | `betriebstyp` | Real-Betriebe / Plan-Betriebe Roll / Plan-Betriebe ITY. Plan-Betriebe sind Platzhalter-Kostenstellen für unknown Business und dürfen in Betriebszählungen nicht mitlaufen. |
| `Known / Unknown` | string | `known_unknown` | known = realer Betrieb, unknown = Planbetrieb. Die Kernunterscheidung des gesamten Berichts: known ITY ist gebucht, unknown ITY wird aus dem CRM approximiert. |
| `Unit-Status` | string | `unit_status` | "In Betrieb" = aus den SAP-Stammdaten. "Geplant"    = existiert nur im gepflegten Mapping, weil die Unit noch nicht gewonnen ist. Ohne diese Ergänzung fielen geplante Units in die Leerzeile jeder Organisationsauswertung – also genau der Teil, um den es im Net New Business geht. Für sie bleiben Region, Management und Sektor leer, solange die Mappingdatei diese Angaben nicht mitführt. |
| `Vertragsbeginn` | dateTime | `vertragsbeginn` | – |
| `Schließung` | dateTime | `schliessung` | – |
| `Vertragsart` | string | `bezeichnung_vertragsart` | – |
| `Region` | string | `bezeichnung_region` | – |
| `Management` | string | `bezeichnung_management` | – |
| `Verantwortungsbereich` | string | `bezeichnung_verantwortungsbereich` | – |
| `Branche` | string | `bezeichnung_branche` | – |
| `Kundengruppe` | string | `bezeichnung_kundengruppe` | – |
| `Bundesland` | string | `bundesland` | – |
| `Stadt` | string | `stadt` | – |
| `Cause of Change` | int64 | `cause_of_change` | Cause of Change laut SAP-Stammdaten. Alle Codes sind relativ zu einem BEZUGSJAHR zu lesen – "Vorjahr" heißt das Jahr vor dem Bezugsjahr: 1 = im Vorjahr gewonnen    → rollt ins Bezugsjahr (Metrik 1 bzw. 2) 2 = im Bezugsjahr gewonnen → New Business ITY (Metrik 4) 3 = im Vorjahr verloren    → Lost Business Roll (Metrik 6) 4 = im Bezugsjahr verloren → Lost Business ITY (Metrik 7 bzw. 8) 5 = M&A                    → keine Net-New-Größe (99) Welches Bezugsjahr gilt, hängt an der Variante: diese Spalte und cause_of_change_fy blicken aus dem laufenden Geschäftsjahr, cause_of_change_ny aus dem Folgejahr. Die Umsetzung steht in nb_20_gold, fn_map_coch. |
| `Cause of Change Bezeichnung` | string | `bezeichnung_cause_of_change` | – |
| `cause_of_change_fy` | int64 | `cause_of_change_fy` | – |
| `cause_of_change_ny` | int64 | `cause_of_change_ny` | – |

### `DIM Datum`

Fiskalkalender der Gruppe (1. Oktober – 30. September). Quelle: gold_dim_date. Ersetzt drei identische M-Kalender der Altmodelle und alle Auto-Datumstabellen (LocalDateTable_*).

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Datum` | dateTime | `datum` | Kalendertag. Schlüsselspalte der Datumstabelle. |
| `Kalenderjahr` | int64 | `jahr` | Kalenderjahr. |
| `Monatsbeginn` | dateTime | `monat_erster` | Erster Tag des Monats. Verbindungsschlüssel zu den Faktentabellen, die auf Monatsebene liegen. |
| `GJ Jahr` | int64 | `fy_year` | Geschäftsjahr als Zahl = Kalenderjahr des FY-Beginns. 2025 bedeutet FY2025/26. |
| `GJ Bezeichnung` | string | `fy_label` | Geschäftsjahr als Beschriftung, z. B. "FY2025/26". |
| `GJ Periode Nr` | int64 | `fy_period` | Geschäftsperiode 1–12. P01 = Oktober, P12 = September. |
| `GJ Periode` | string | `fy_periode` | Periodenkürzel "P01" … "P12". |
| `Periode Label` | string | `fy_periode_label` | Achsenbeschriftung "Okt 25". Kurz genug, um ohne Drehung zu lesen – gedrehte Achsenbeschriftungen kosten Lesezeit (Storytelling with Data, Kapitel 3: Clutter). |
| `GJ Quartal` | string | `fy_quartal` | Geschäftsquartal FQ1–FQ4. |
| `GJ Quartal Nr` _(technisch)_ | int64 | `fy_quartal_nr` | – |
| `Monatsindex` _(technisch)_ | int64 | `monat_index` | LINEARER Monatsindex = GJ-Jahr × 12 + GJ-Periode. Grundlage der Szenario-Verschiebung: "n Monate später" ist damit eine einfache Subtraktion. Ein Schlüssel aus Jahr × 100 + Periode wäre an der Jahresgrenze nicht linear (202512 → 202601) und würde die Verschiebung im Dezember zerreißen. |
| `GJ Sortierung` _(technisch)_ | int64 | `fy_sort` | Sortierschlüssel GJ-Jahr × 100 + Periode. Nur für Sortierung, nicht für Arithmetik verwenden (siehe Monatsindex). |
| `Ist Vergangenheit` | boolean | `ist_vergangenheit` | Wahr für alle Tage vor dem heutigen. Trennt im Bericht Ist von Plan, ohne dass jede Visualisierung eine eigene Datumsbedingung braucht. |
| `monat_nr` | int64 | `monat_nr` | – |
| `monat` | string | `monat` | – |
| `tag` | int64 | `tag` | – |
| `quartal` | string | `quartal` | – |
| `fy_jahr_monat` | string | `fy_jahr_monat` | – |

### `DIM HFM-Struktur`

Net-New-Hierarchie und Zuordnung zum HFM-Kontenplan. Quelle: gold_dim_hfm_struktur.

Übernimmt DIM_Struktur der Altmodelle und ergänzt sie um die Forward-Indikatoren MAP131/MAP136/MAP141a/MAP141c aus der Group Guidance (Feb 2025, S. 3) – diese fehlten dort, obwohl der gesamte Bericht sie misst.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Metric ID` _(technisch)_ | int64 | `metric_id` | – |
| `Kennzahl` | string | `metric` | – |
| `Sortierung` _(technisch)_ | int64 | `sort` | – |
| `Ebene 1` | string | `level1_label` | – |
| `Ebene 2` | string | `level2_label` | – |
| `Ebene 3` | string | `level3_label` | – |
| `Ebene 4` | string | `level4_label` | – |
| `HFM Konto` | string | `hfm_account` | HFM-Konto, z. B. MAP131, MAP141a, MAP112c. |
| `HFM Definition` | string | `hfm_beschreibung` | Wortlaut der Kontodefinition aus dem HFM Chart of Accounts. Wird im Bericht als QuickInfo an den Kennzahlen angezeigt – damit steht die Definition dort, wo die Zahl steht. |
| `Ist Blattknoten` _(technisch)_ | boolean | `is_leaf` | – |
| `parent_id` | int64 | `parent_id` | – |

### `DIM Opportunity`

Opportunity-Stammdaten aus dem CRM. Quelle: gold_dim_opportunity.

Ersetzt die elf dim_opp_*-Tabellen des Altmodells "CRM Call". Diese waren über "Duplikate entfernen" aus dem Fakt erzeugt und über beidseitig filternde Beziehungen angebunden – eine Konstruktion, die Filterrichtungen unvorhersehbar macht. Hier: eine Dimension, eine Richtung.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Opportunity ID` _(technisch)_ | string | `opportunityid` | – |
| `Opportunity` | string | `opportunity_name` | – |
| `Kunde` | string | `account_name` | – |
| `Verantwortlicher` | string | `owner_name` | – |
| `Vertriebsgebiet` | string | `territory_name` | – |
| `Vertriebsphase` | string | `sales_stage` | Vertriebsphase laut CRM (cgplc_salesstagename). |
| `Vertragsart` | string | `contract_type` | – |
| `Sektor` | string | `sector` | – |
| `Subsektor` | string | `subsector` | – |
| `Aktueller Anbieter` | string | `current_supplier` | Bisheriger Anbieter – die Wettbewerbersicht, die im Altbericht fehlte. |
| `ITY Cluster` | string | `ity_cluster` | – |
| `Entscheidungsdatum` | dateTime | `est_close_date` | Erwartetes Entscheidungsdatum. |
| `Mobilisierung` | dateTime | `opening_date` | Mobilisierungs-/Eröffnungsdatum – Startpunkt der Periodenverteilung. |
| `Gewinndatum` | dateTime | `won_date` | – |
| `Win %` | double | `win_probability` | – |
| `ARO Umsatz` | double | `revenue_aro` | ARO-Umsatz laut CRM – Basis für HFM MAP131. |
| `ITY Umsatz` | double | `revenue_ity` | ITY-Umsatz laut CRM – Basis für HFM MAP141a. |
| `Bruttomarge %` | double | `bg_percent` | Bruttomarge in Prozent laut CRM. |
| `ITY Monate` | int64 | `calc_ity_months` | – |
| `contract_id` | string | `contract_id` | – |
| `status_code` | string | `status_code` | – |

### `DIM Status`

Statusdimension für New- und Lost-Business-Pipeline.

Warum als Dimension statt als String-Filter in Measures: In den Altmodellen wurden Buckets über CALCULATE(..., Sales_Status="Won YTD") gefiltert. Dadurch waren Sortierung und Farbe je Visualisierung neu zu pflegen, und ein neuer Bucket erforderte neue Measures. Hier hängen Reihenfolge, Sicherheitsgrad und Farbrolle an den Daten.

Quelle: gold_dim_status.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Status Code` _(technisch)_ | string | `status_code` | – |
| `Status` | string | `status_label` | Anzeigebezeichnung: Won, Expected Win, Pipeline, Lost, Expected Loss, At Risk, No Risk, Ohne Win-%. |
| `Geschäftsart` | string | `business_type` | NEW oder LOST. |
| `Sortierung` _(technisch)_ | int64 | `status_sort` | – |
| `Sicherheitsgrad` | string | `sicherheitsgrad` | gesichert / erwartet / unsicher / unbekannt. Diese Gruppierung trägt die Kernaussage jeder Pipeline-Grafik: Wie viel des Net New ITY ist bereits belastbar? |
| `Farbrolle` _(technisch)_ | string | `farbrolle` | Farbrolle für das Berichtsthema (nb-won, nb-expected, nb-pipeline, lb-lost, lb-expected, lb-atrisk, neutral). Aufgelöst in StaticResources/SharedResources/BaseThemes/NetNewITY.json. |
| `Farbe` | berechnet | – | Hex-Farbe zur direkten Bindung in Visualisierungen (Datenfarben → bedingte Formatierung → Feldwert). So ist die Farbsemantik an die Daten gebunden und kann in keiner Visualisierung versehentlich abweichen. Die Werte stammen aus zwei validierten Ein-Ton-Rampen: Blau  #86b6ef → #3987e5 → #184f95   (New Business, zunehmende Sicherheit) Rot   #eb9998 → #e34948 → #a02222   (Lost Business, zunehmende Sicherheit) Beide Rampen erfüllen Monotonie, Mindestabstand je Stufe und den 2:1-Kontrast der hellsten Stufe gegen weißen Hintergrund. |
| `status_key` | int64 | `status_key` | – |

### `DIM Vertrag`

Bestandsverträge aus dem CRM (Retention-Sicht). Quelle: gold_dim_contract.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Vertrag ID` _(technisch)_ | string | `contract_key` | – |
| `Vertrag` | string | `contract_name` | – |
| `SAP ID` | string | `sap_id` | SAP-Betriebsnummer – Verbindung zur Betriebsdimension und damit zu den tatsächlich gebuchten Umsätzen. |
| `Risikogrund` | string | `risk_reason` | Risikogrund laut CRM (cgplc_reasonforriskname). Trägt die Erklärung hinter jedem gefährdeten Vertrag – im Altbericht nur als Rohspalte vorhanden, nie visualisiert. |
| `Entscheidungsdatum` | dateTime | `decision_date` | Entscheidungsdatum. Laut Group Guidance (S. 2) maßgeblich für die Zuordnung eines Verlusts zu "current year" oder "prior year". |
| `Erwartetes Entscheidungsdatum` | dateTime | `forecast_decision_date` | – |
| `Betriebsbeginn` | dateTime | `operation_start_date` | – |
| `Vertragsende (bereinigt)` | dateTime | `adj_end_date` | Bereinigtes Vertragsende: Vertragsende laut CRM, ersatzweise Entscheidungsdatum plus drei Monate (übliche Kündigungsfrist bis zur Demobilisierung). Viele Evergreen-Verträge haben kein Enddatum. |
| `ITY Cluster` | string | `ity_cluster` | – |
| `Sektor` | string | `sector` | Sektor des Vertrags. Spiegelbild zu 'DIM Opportunity'[Sektor], damit die Lost-Seite nach denselben Merkmalen auswertbar ist wie die New-Seite. Für Datenschnitte, die BEIDE Geschäftsarten treffen sollen, stattdessen 'FCT Net New ITY'[Sektor] verwenden – diese Spalte hier filtert nur Verträge. |
| `Subsektor` | string | `subsector` | Subsektor des Vertrags. Siehe Hinweis bei Sektor. |
| `Vertragsart` | string | `contract_type` | – |
| `Verantwortlicher` | string | `owner_name` | – |
| `Retention %` | double | `retention_probability` | Haltewahrscheinlichkeit. Achtung Leserichtung: 100 % = kein Risiko. Die Verlustwahrscheinlichkeit ist 1 − Retention-%. |
| `ARO Umsatz` | double | `revenue_aro` | – |
| `Vorjahres-ARO` | double | `last_fy_revenue_aro` | Vorjahres-ARO – Bemessungsgrundlage für HFM MAP136 (Lost ARO). |
| `ARO-Status` | string | `ly_aro_status` | "ARO im CRM" / "Kein ARO im CRM". Ohne Vorjahres-ARO wird der Verlust mit 0 € bewertet – dieser Marker macht die Lücke sichtbar. |
| `ITY Monate` | int64 | `calc_ity_months` | – |
| `status_code` | string | `status_code` | – |

### `DQ Prüfungen`

Ergebnisse der Datenqualitätsprüfungen je Ladelauf. Quelle: gold_dq_checks (siehe lakehouse/notebooks/nb_30_quality.py).

Diese Tabelle macht sichtbar, was in den Altmodellen unsichtbar war: Opportunities ohne Mobilisierungsdatum, Verträge ohne Vorjahres-ARO, ITY-Werte oberhalb des ARO. Solche Sätze wurden dort per "Gefilterte Zeilen" entfernt und tauchten nirgends wieder auf – der fehlende Betrag war im Ergebnis nicht mehr erklärbar.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Regel` | string | `regel_id` | – |
| `Schweregrad` | string | `schweregrad` | ERROR bricht die Pipeline ab, WARNING erscheint im Bericht, INFO ist eine reine Kennzahl. |
| `Beschreibung` | string | `beschreibung` | – |
| `Verstöße` | int64 | `anzahl_verstoesse` | – |
| `Handlungshinweis` | string | `hinweis` | Konkrete Handlungsanweisung – wer im CRM was nachpflegen muss. |
| `Prüfdatum` | dateTime | `pruef_datum` | – |

### `FCT CRM-Bewegung`

Veränderungen im CRM zwischen zwei Ladeläufen. Quelle: gold_fct_crm_movement.

Diese Tabelle ist die Antwort auf die Anforderung, Entwicklungen im CRM schnell zeigen zu können. Granularität: eine Zeile je Entität und Änderungszeitpunkt – mit Vorher- und Nachher-Wert.

Die Historie entsteht in nb_10_silver: pro Tag wird ein Snapshot geschrieben, aber nur dann eine neue Zeile erzeugt, wenn sich eine der überwachten Größen tatsächlich geändert hat. Jede Zeile bedeutet also eine echte Änderung.

Bewusst NICHT mit 'DIM Datum' verbunden: die Zeitachse dieser Tabelle ist der Erhebungsstichtag, nicht die Wirkungsperiode. Eine Verbindung würde beide Zeitbegriffe vermischen.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Entität ID` _(technisch)_ | string | `entity_id` | – |
| `Entitätstyp` | string | `entity_type` | – |
| `Geschäftsart` | string | `business_type` | – |
| `Stichtag` | dateTime | `snapshot_date` | Stichtag, an dem die Änderung festgestellt wurde. |
| `Vorheriger Stichtag` | dateTime | `prev_snapshot_date` | Stichtag des vorherigen Stands. |
| `Wert neu` | double | `value_new` | Wert nach der Änderung. New Business: ITY-Umsatz. Lost Business: Vorjahres-ARO. |
| `Wert alt` | double | `value_old` | – |
| `Wertänderung` | double | `value_delta` | Wertänderung. Positiv = Chance gewachsen bzw. Risiko gewachsen – die Leserichtung hängt an der Geschäftsart. |
| `Wahrscheinlichkeit neu` | double | `probability_new` | – |
| `Wahrscheinlichkeit alt` | double | `probability_old` | – |
| `Wahrscheinlichkeitsänderung` | double | `probability_delta` | – |
| `Status neu` | string | `status_new` | – |
| `Status alt` | string | `status_old` | – |
| `Änderungsart` | string | `aenderungsart` | Statuswechsel / Wahrscheinlichkeit / Wert / Sonstiges. Erlaubt es, im Bericht die relevanten Änderungen zuerst zu zeigen: ein Statuswechsel wiegt schwerer als eine Wertkorrektur. |

### `FCT Net New ITY`

Zentrale Faktentabelle: Perioden-Fanout aus CRM-Opportunities (New Business) und CRM-Bestandsverträgen (Lost Business).

Granularität: eine Zeile je Entität und Monat. Quelle: gold_fct_net_new_ity (siehe lakehouse/notebooks/nb_20_gold.py).

VORZEICHENKONVENTION – der wichtigste Unterschied zu den Altmodellen: New Business  -> Betrag positiv Lost Business -> Betrag negativ Damit ist Net New ITY = SUM('Betrag gewichtet (vorzeichenbehaftet)'). In den Altmodellen wurde das Vorzeichen an mindestens fünf Stellen unterschiedlich gedreht (M: *-1 in fct_opp/fct_retention; DAX: *-1 in Retention_ITY, LY_REV, ARO_LY). Hier passiert es genau einmal, im Lakehouse.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Entität ID` _(technisch)_ | string | `entity_id` | Schlüssel der Opportunity (opportunityid) bzw. des Vertrags (cgplc_cgcontractid). |
| `Entität` | string | `entity_name` | Bezeichnung der Opportunity bzw. des Vertrags. |
| `Entitätstyp` | string | `entity_type` | OPPORTUNITY oder CONTRACT. |
| `Geschäftsart` | string | `business_type` | NEW oder LOST. Steuert Vorzeichen und HFM-Kontenzuordnung. |
| `Status Code` | string | `status_code` | Verknüpfung zu DIM Status (Won / Expected Win / Pipeline / …). |
| `ITY Cluster` | string | `ity_cluster` | "unknown ITY" oder "unknown Roll" – wann die Entscheidung fällt und wohin sie dadurch wirkt. Bezeichner aus den Altmodellen beibehalten, damit Abstimmungen gegen die Altreports möglich bleiben. unknown Roll → Abschluss im laufenden Geschäftsjahr, Umsatz überwiegend im Folgejahr. Das ist die Größe, die auf der Seite "Roll-Budget" gegen das Budget läuft: was jetzt noch gewonnen werden muss. unknown ITY → Abschluss im Folgejahr, Wirkung innerhalb desselben Jahres. |
| `Wahrscheinlichkeit` | double | `probability` | Gewinn- bzw. Verlustwahrscheinlichkeit als Dezimalzahl (0–1). New Business  : Win-% aus dem CRM. Lost Business : 1 − Retention-%. |
| `Periode` _(technisch)_ | dateTime | `period_date` | Erster Tag des Wirkungsmonats. Verbindung zu DIM Datum. |
| `GJ Jahr` _(technisch)_ | int64 | `fy_year` | – |
| `GJ Periode Nr` _(technisch)_ | int64 | `fy_period` | – |
| `Monatsindex` _(technisch)_ | int64 | `monat_index` | Linearer Monatsindex, deckungsgleich mit 'DIM Datum'[Monatsindex]. Zielspalte der Szenario-Verschiebung. |
| `Periodenindex` | int64 | `period_index` | Laufende Nummer des Monats seit dem auslösenden Ereignis (Mobilisierung bzw. Vertragsende), beginnend bei 1. Niedrigkardinal (1–24) – deshalb kann die Anlaufkurve in DAX ohne Performance-Verlust über diese Spalte iterieren. |
| `Wertebene` | string | `value_layer` | ITY  = Wirkung im ersten Geschäftsjahr (HFM MAP141a / MAP141c) ARO  = Dauerzustand ab dem zweiten Geschäftsjahr (MAP131 / MAP136) |
| `HFM Konto` | string | `hfm_account` | HFM-Konto laut Group Guidance (Feb 2025, S. 3). |
| `Betrag gewichtet` _(technisch)_ | double | `amount_weighted` | Monatswert × Wahrscheinlichkeit, immer positiv. |
| `Betrag ungewichtet` | double | `amount_unweighted` | Monatswert ohne Wahrscheinlichkeitsgewichtung (Vollwert). Antwortet auf "Was wäre, wenn alles eintritt?". |
| `Betrag` _(technisch)_ | double | `amount_signed` | Gewichteter Monatswert mit Vorzeichen: NEW positiv, LOST negativ. Basis fast aller Measures. |
| `Betrag ungewichtet (vorzeichenbehaftet)` _(technisch)_ | double | `amount_unweighted_signed` | Ungewichteter Monatswert mit Vorzeichen. Basis der Bewertungsbasis "Vollwert" – als eigene Spalte materialisiert, damit auch diese Sicht eine einfache Summe bleibt. |
| `Auslösendes Datum` | dateTime | `driver_date` | Auslösendes Datum: Mobilisierung (New) bzw. bereinigtes Vertragsende (Lost). Bereinigt heißt: Vertragsende, ersatzweise Entscheidungsdatum plus drei Monate. |
| `Entscheidungsdatum` | dateTime | `decision_date` | Entscheidungsdatum laut CRM. Laut Group Guidance (S. 2) maßgeblich für die Zuordnung zu "current year" bzw. "prior year" – NICHT das Mobilisierungs- oder Schließungsdatum. |
| `Ende 1. GJ` _(technisch)_ | dateTime | `calc_first_fy_end` | Ende des ersten Geschäftsjahres der Entität. Grenze zwischen ITY- und ARO-Phase. |
| `ITY Monate` | int64 | `calc_ity_months` | Anzahl Monate der ITY-Phase. Teiler bei der Verteilung des ITY-Werts. |
| `Sektor` | string | `sector` | KONFORME ATTRIBUTE (Sektor bis Verantwortlicher) Diese fünf Merkmale liegen bewusst auf dem Fakt und nicht nur in den Dimensionen, weil sie für BEIDE Geschäftsarten gefüllt sind. Grund: 'DIM Opportunity' und 'DIM Vertrag' sind getrennte Dimensionen. Ein Datenschnitt auf 'DIM Opportunity'[Sektor] filtert nur die New-Zeilen – die Lost-Zeilen hängen an dieser Dimension gar nicht und laufen unverändert durch. Das Ergebnis wäre ein "Net New ITY im Sektor Healthcare", das das gesamte Lost Business aller Sektoren enthält: falsch, ohne Fehlermeldung. Für seitenübergreifende Datenschnitte deshalb IMMER diese Spalten verwenden, nicht die gleichnamigen der Dimensionen. Die Dimensionsspalten bleiben für Detailsichten innerhalb einer Geschäftsart. |
| `Subsektor` | string | `subsector` | Subsektor. Konform über beide Geschäftsarten – siehe Sektor. |
| `Vertragsart` | string | `contract_type` | Vertragsart. Konform über beide Geschäftsarten – siehe Sektor. |
| `Kunde` | string | `account_name` | Kunde. Konform über beide Geschäftsarten – siehe Sektor. Auf der Lost-Seite über cgplc_accountid aus dem Konto nachgeschlagen. |
| `Verantwortlicher` | string | `owner_name` | Verantwortlicher. Konform über beide Geschäftsarten – siehe Sektor. |
| `Werk` _(technisch)_ | int64 | `sap_id` | SAP-Betriebsnummer. Verbindung zu DIM Betrieb und damit zu Region, Management und Verantwortungsbereich. Aufgelöst über eine vierstufige Kette (nb_20_gold, Abschnitt 5d): 1. Einzelfall-Ausnahme aus der Mapping-Tabelle 2. cgplc_sapid am Vorgang selbst 3. Mapping über Sektor UND Subsektor 4. Mapping über Sektor allein Die Mapping-Tabelle (Mapping_Planwerke.xlsx) pflegt das Controlling – dort steht, welcher Sektor/Subsektor auf welchem Planbetrieb geplant wird. Die SAP-Nummer des Kontos wird bewusst nicht verwendet: sie ist ein Debitor, kein Betrieb. Welche Stufe gegriffen hat, zeigt 'Werk Zuordnung'. Lücken zählt Regel DQ-MAP-001, fehlende Mapping-Zeilen listet DQ-MAP-002. |
| `Werk Zuordnung` | string | `werk_zuordnung` | Herkunft der Werk-Zuordnung: Ausnahme (Mapping) / CRM direkt / Mapping Sektor/Subsektor / Mapping Sektor / Nicht zugeordnet. Macht je Vorgang sichtbar, ob eine Zahl auf gepflegten CRM-Daten oder auf der Mapping-Tabelle beruht – und priorisiert damit die Nachpflege: "Nicht zugeordnet" ist die Arbeitsliste. |
| `Stichtag` _(technisch)_ | dateTime | `snapshot_date` | Stichtag des Ladelaufs. Ermöglicht Snapshot-Vergleiche. |
| `event_month` | dateTime | `event_month` | – |
| `fy_label` | string | `fy_label` | – |
| `fy_sort` | int64 | `fy_sort` | – |
| `amount_abs` | double | `amount_abs` | – |
| `loaded_at` | dateTime | `loaded_at` | – |

### `FCT Umsatz`

Gebuchte und geplante Umsätze aus SAP. Quelle: gold_fct_revenue. Granularität: Werk × Geschäftsjahr × Periode × Werttyp/Version.

Ersetzt die Tabelle Revenues der Altmodelle. Zwei Dinge sind bereinigt: 1. Das Vorzeichen wird einmal im Lakehouse gedreht (SAP liefert Erträge negativ), nicht mehr in jedem zweiten Measure. 2. Das Cause-of-Change-Mapping auf die Net-New-Hierarchie ist eine Funktion im Lakehouse statt dreier identischer M-Kaskaden.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Werk` _(technisch)_ | int64 | `werk` | – |
| `GJ Jahr` _(technisch)_ | int64 | `fy_year` | – |
| `GJ Periode Nr` _(technisch)_ | int64 | `fy_period` | – |
| `Monatsindex` _(technisch)_ | int64 | `monat_index` | – |
| `Periode` _(technisch)_ | dateTime | `period_date` | – |
| `Werttyp` | string | `werttyp` | Actual oder Plan. |
| `Version` | string | `version` | SAP-Version. 0 = Ist, 20 = Budget, RGF/R12 = Forecast, 90 = Planung unknown ITY, 35/RFC = Vorjahresforecast. |
| `Werttyp Version` | string | `werttyp_version` | Kombination Werttyp_Version, z. B. "Actual_0", "Plan_20", "Plan_RGF". Der Schlüssel, über den in den Measures die Szenarien der Planung auseinandergehalten werden. |
| `Monatswert` _(technisch)_ | double | `betrag_monat` | Monatswert (nicht kumuliert), Vorzeichen bereits gedreht: Ertrag positiv. |
| `Wert kumuliert` _(technisch)_ | double | `betrag_ytd` | Kumulierter Wert seit Periode 1 des Geschäftsjahres. Im Lakehouse per Fensterfunktion berechnet, nicht in DAX – das spart bei jedem YTD-Visual eine Kontexttransition. |
| `Metric ID` _(technisch)_ | int64 | `metric_id` | MetricId der Net-New-Hierarchie – aus Cause of Change abgeleitet. Verbindung zu DIM HFM-Struktur. |
| `Metric ID FY` _(technisch)_ | int64 | `metric_id_fy` | Variante des Mappings auf Basis cause_of_change_fy (Forecast-Sicht). |
| `Metric ID NY` _(technisch)_ | int64 | `metric_id_ny` | Variante des Mappings auf Basis cause_of_change_ny (Planjahressicht). |
| `Betriebstyp` | string | `betriebstyp` | – |
| `cause_of_change` | int64 | `cause_of_change` | Cause of Change des Betriebs, wie in den SAP-Stammdaten gepflegt. Rohwert, aus dem 'Metric ID' abgeleitet wird. |
| `cause_of_change_fy` | int64 | `cause_of_change_fy` | Cause of Change mit Blick auf das laufende Geschäftsjahr. |
| `cause_of_change_ny` | int64 | `cause_of_change_ny` | Cause of Change mit Blick auf das FOLGEJAHR – die Sicht, auf der die Budgetlogik aufsetzt (im Altmodell "Mapping CoCh NY"). Liegt bewusst auf dem Fakt und nicht nur auf 'DIM Betrieb': die Budgetkennzahl grenzt über die Kombination aus Betriebstyp und diesem Wert ab. Über zwei Tabellen hinweg ließe sich das weder mit einem einzelnen ALL() ausdrücken noch performant auswerten. |

### `Szenario Anlauf`

SZENARIO-PARAMETER 2 von 4 · Anlauffaktor

Beantwortet: "Was passiert, wenn neue Betriebe in den ersten Monaten nur einen Teil des geplanten Umsatzes erreichen?"

Im Altmodell steckte der Faktor als Konstante 0,8 in einer Power-Query-Spalte (Betrag_Szenario_Anlauf), zusammen mit einer fest verdrahteten Anlaufdauer von drei Monaten. Beides ist jetzt einstellbar.

Der Faktor wirkt auf die ersten n Monate ab Mobilisierung, wobei n aus 'Szenario Anlaufdauer'[Monate] kommt. Angewandt wird er über 'FCT Net New ITY'[Periodenindex] – einer Spalte mit 24 verschiedenen Werten, weshalb die Iteration in DAX praktisch nichts kostet.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Faktor` | – | `[Faktor]` | – |
| `Bezeichnung` | – | `[Bezeichnung]` | – |

### `Szenario Anlaufdauer`

SZENARIO-PARAMETER 3 von 4 · Dauer der Anlaufphase

Legt fest, über wie viele Monate ab Mobilisierung der Anlauffaktor aus 'Szenario Anlauf'[Faktor] wirkt. 0 = kein Anlaufeffekt (Basisfall).

Zusammen mit dem Faktor bildet dieser Parameter die Anlaufkurve. Beide waren im Altmodell hart codiert (0,8 über drei Monate).

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Monate` | – | `[Monate]` | – |
| `Bezeichnung` | – | `[Bezeichnung]` | – |

### `Szenario Bewertung`

SZENARIO-PARAMETER 4 von 4 · Bewertungsbasis und Wahrscheinlichkeitsschwelle

Zwei Stellschrauben in einer Tabelle:

1. BEWERTUNGSBASIS – wie wird der CRM-Wert in Geld übersetzt? · "CRM-gewichtet"     Umsatz × Wahrscheinlichkeit (Standard, entspricht weighted_ity / weighted_ly_aro der Altmodelle) · "Vollwert"          Umsatz ohne Gewichtung – die Obergrenze · "Nur gesichert"     ausschließlich Won bzw. Lost, ungewichtet – die belastbare Untergrenze

Die drei Werte spannen den Korridor auf, in dem sich das tatsächliche Net New ITY bewegen wird. Im Altbericht existierte nur die mittlere Variante, weshalb die Bandbreite nie sichtbar war.

2. SCHWELLE – ab welcher Wahrscheinlichkeit zählt eine Opportunity? Filtert 'FCT Net New ITY'[Wahrscheinlichkeit]. Vorbelegung 0 % = alles.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Bewertungsbasis` | – | `[Bewertungsbasis]` | – |
| `Beschreibung` | – | `[Beschreibung]` | – |
| `Sortierung` | – | `[Sortierung]` | – |

### `Szenario Schwelle`

SZENARIO-PARAMETER · Mindest-Eintrittswahrscheinlichkeit

Filtert Opportunities und Risikoverträge unterhalb einer wählbaren Wahrscheinlichkeit aus der Betrachtung. Beantwortet die Frage, die in jedem CRM-Call gestellt wird: "Wie sieht es aus, wenn wir nur das zählen, was mindestens zu X Prozent sicher ist?"

Wirkt über [Net New ITY (ab Schwelle)] auf 'FCT Net New ITY'[Wahrscheinlichkeit].

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Schwelle` | – | `[Schwelle]` | – |
| `Bezeichnung` | – | `[Bezeichnung]` | – |

### `Szenario Verschiebung`

SZENARIO-PARAMETER 1 von 4 · Zeitliche Verschiebung

Beantwortet: "Was passiert mit dem Net New ITY, wenn sich alle Mobilisierungen bzw. Vertragsenden um n Monate verschieben?"

WARUM DAS HIER STEHT UND NICHT IM LAKEHOUSE Im Altmodell war die Verschiebung eine Power-Query-Spalte (Revenues[Verschiebung +1]) mit fest verdrahtetem +1. Jede Änderung des Verschiebungsbetrags erforderte eine Modelländerung und einen vollen Refresh. Materialisieren wäre auch keine Lösung: Die zehn Stufen mal fünf Anlauffaktoren mal sieben Anlaufdauern ergäben 350 Faktenvarianten.

Die DAX-Variante iteriert über 'DIM Datum'[Monatsindex] – zwölf bis vierundzwanzig Werte im Filterkontext. Der Aufwand ist vernachlässigbar.

Diese Tabelle ist bewusst NICHT mit dem Modell verbunden (disconnected): sie filtert nichts, sie liefert nur einen Skalar an die Measures.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Monate` | – | `[Monate]` | – |
| `Bezeichnung` | – | `[Bezeichnung]` | – |
| `Sortierung` | – | `[Sortierung]` | – |

### `_Kennzahlen`

Zentrale Measure-Tabelle. Enthält keine Daten, nur Kennzahlen. Jede Kennzahl trägt eine Beschreibung, die in Power BI als QuickInfo erscheint, und – wo einschlägig – den Verweis auf das HFM-Konto. Die ausführliche Herleitung steht in docs/03_berechnungslogik.md.

| Spalte | Typ | Quellspalte | Bedeutung |
|---|---|---|---|
| `Platzhalter` _(technisch)_ | string | `Platzhalter` | – |
