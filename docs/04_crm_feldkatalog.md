# 04 – CRM-Feldkatalog

Welche Felder aus Dataverse geladen werden, wofür sie gebraucht werden und
welche davon im Mandanten noch zu prüfen sind.

## Ausgangslage

Das Altmodell "CRM Call" lud **21 Felder** aus `opportunity` und **13** aus
`cgplc_cgcontract`. Die Auswahl stand in der Abfrage selbst
(`Table.SelectColumns`), sodass jedes zusätzliche Feld eine Modelländerung
bedeutete – und alles, was nie ausgewählt wurde, im Bericht schlicht nicht
existierte.

Der neue Extrakt lädt breit in die Bronze-Schicht und filtert erst in Silver.
Die Feldlisten stehen in `dataflows/df_crm_ingest/01_stg_crm_opportunity.m`
und `dataflows/df_crm_ingest/02_stg_crm_contract.m`.

## Statuskennzeichnung

| Kennzeichen | Bedeutung |
|---|---|
| **B** | Bestätigt – im Altmodell nachweislich verwendet, existiert also im Mandanten |
| **S** | Dataverse-Standardfeld der jeweiligen Entität |
| **C** | Kundenspezifisches Feld (`cgplc_`-Präfix) – **Verfügbarkeit im Mandanten prüfen** |

Die Extraktion nutzt einen `SafeSelect`-Schritt: sie schneidet die Wunschliste
mit den tatsächlich vorhandenen Spalten und lädt nur die Schnittmenge. Ein
fehlendes Feld bricht den Ladelauf also nicht ab, sondern erscheint in der
Diagnosespalte `_fehlende_felder`. Der Katalog kann dadurch schrittweise
wachsen, ohne dass jemand vorher jede Spalte in Dataverse verifizieren muss.

## Lookup-Namenspaare: GUID und Anzeigename

Der TDS-Endpunkt (`CommonDataService.Database`) liefert für jedes
**Lookup-Feld** `foo` zwei Spalten: `foo` enthält die **GUID**, `fooname` den
**Anzeigenamen**. Analog bei Optionsets (`statecode` / `statecodename`).

Beide werden geladen und haben getrennte Aufgaben:

| Spalte | Aufgabe |
|---|---|
| `cgplc_sectorlookup` (GUID) | Join-Schlüssel, stabil bei Umbenennungen |
| `cgplc_sectorlookupname` | Anzeige, Filter, Schlüssel des Sektor-Mappings |

In Silver/Gold löst die Hilfsfunktion `name_oder_id()` (in `nb_00_config.py`)
jeden Lookup zum Anzeigenamen auf und fällt auf die GUID zurück, falls die
Namensspalte im Mandanten fehlt. Alle sprechenden Spalten des Berichts
(Sektor, Subsektor, Vertragsart, aktueller Anbieter, Kunde …) tragen dadurch
Namen, keine GUIDs – und das Sektor-Mapping in `Mapping_Planwerke.xlsx` wird
über Namen geschlüsselt, so wie das Controlling sie pflegt.

Das Altmodell „CRM Call" hat dasselbe Problem anders gelöst: elf
`dim_opp_*`-Tabellen, per „Duplikate entfernen" aus dem Fakt erzeugt, jeweils
GUID + Name. Der Umweg entfällt.

---

## opportunity – New Business

### Identität

| Feld | Status | Verwendung |
|---|---|---|
| `opportunityid` | B | Primärschlüssel, Fakt-Verknüpfung |
| `name` | B | Bezeichnung in allen Listen |
| `accountid` | B | Verknüpfung zum Kunden |
| `parentaccountid` | B | Konzernstruktur – Konzernkunden bündeln |
| `ownerid` / `owneridname` | B / S | Verantwortlicher, Filterdimension |
| `customerid` | S | Polymorpher Kundenbezug |
| `opportunityratingcode` | S | A/B/C-Einstufung – zusätzliche Priorisierungsachse |

### Termine

| Feld | Status | Verwendung |
|---|---|---|
| `estimatedclosedate` | B | Erwartetes Entscheidungsdatum. **Maßgeblich für CY/PY-Zuordnung** laut Guidance S. 2 |
| `actualclosedate` | S | Tatsächlicher Abschluss – Basis für Terminstabilitätsanalysen |
| `cgplc_openingdate` | B | Mobilisierung. Startpunkt des Perioden-Fanouts |
| `cgplc_wondate` | B | Gewinndatum |
| `createdon` | S | Anlage im CRM – erlaubt Alterung der Pipeline ("wie lange liegt das schon?") |
| `modifiedon` | S | Letzte Änderung – Frischeindikator |
| `cgplc_bidduedate` | C | Angebotsfrist |
| `cgplc_contractstartdate` / `cgplc_contractenddate` | C | Vertragslaufzeit |
| `cgplc_mobilisationdate` | C | Mobilisierungsstart, falls abweichend von `cgplc_openingdate` |

### Werte

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_revenuearo` | B | ARO – Bemessungsgrundlage **MAP131** |
| `cgplc_revenueity` | B | ITY – Bemessungsgrundlage **MAP141a** |
| `cgplc_revenuearo_base` / `cgplc_revenueity_base` | B | Dieselben Werte in Konzernwährung |
| `estimatedvalue` / `estimatedvalue_base` | S | Geschätzter Auftragswert – Plausibilisierung gegen ARO |
| `budgetamount` | S | Kundenbudget |
| `cgplc_bgpercent` | B | Bruttomarge – erlaubt Margensicht statt reiner Umsatzsicht |
| `cgplc_ebitpercent` | C | EBIT-Marge |
| `cgplc_capexvalue` | C | Investitionsbedarf – relevant für Mobilisierungsplanung |
| `cgplc_contractterm` | C | Laufzeit in Monaten |
| `transactioncurrencyid` / `exchangerate` | S | Währungsumrechnung nachvollziehbar machen |

### Wahrscheinlichkeit und Status

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_win` | B | Gewinnwahrscheinlichkeit 0–100. Kern der Gewichtung |
| `closeprobability` | S | Standardfeld – Abweichungen zu `cgplc_win` sind ein Datenqualitätssignal |
| `cgplc_salesstagename` | B | Vertriebsphase im Klartext |
| `salesstage` / `salesstagecode` / `stepname` | S | Phase als Code und Prozessschritt |
| `statecode` / `statecodename` | S / B | Status |
| `statuscode` / `statuscodename` | S | Statusgrund |
| `cgplc_reasonforlossname` | C | **Verlustgrund** – im Altbericht nicht vorhanden, beantwortet aber die häufigste Rückfrage im Call |
| `cgplc_confidencelevel` | C | Selbsteinschätzung des Vertriebs |

### Klassifizierung

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_contracttypelookup` | B | Vertragsart |
| `cgplc_sectorlookup` / `cgplc_subsector` | B | Sektor / Subsektor |
| `cgplc_currentsupplier` | B | **Bisheriger Anbieter** – Wettbewerbersicht |
| `cgplc_territoryid` | B | Vertriebsgebiet |
| `cgplc_contractid` | B | Verknüpfter Bestandsvertrag |
| `cgplc_sapid` | C | **SAP-Betriebsnummer.** Ersetzt bei Verfügbarkeit die SharePoint-Datei `Mapping_Planwerke.xlsx` |
| `cgplc_businesstype` | C | New / Retention / Extension – die Unterscheidung, die die Guidance auf S. 4 verlangt |
| `cgplc_isretender` | C | Ausschreibung eines Bestandsvertrags |
| `cgplc_numberofsites` / `cgplc_headcount` | C | Größenmerkmale für Mobilisierungsaufwand |

---

## cgplc_cgcontract – Lost Business

### Identität und Status

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_cgcontractid` | B | Primärschlüssel |
| `cgplc_name` | B | Vertragsbezeichnung |
| `cgplc_sapid` | B | **Verknüpfung zum SAP-Betrieb** – Brücke zu den gebuchten Umsätzen |
| `statuscodename` | B | Filter auf "Aktiv" |
| `statecode` / `statecodename` / `statuscode` | S | Vollständiger Statusbaum – nötig, um Statuswechsel zwischen Läufen zu erkennen |
| `cgplc_accountid` / `cgplc_parentaccountid` | C | Kunde und Konzernmutter |
| `ownerid` / `owneridname` | S | Verantwortlicher |
| `createdon` / `modifiedon` | S | Anlage und letzte Änderung |

### Termine

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_contractenddate` | B | Vertragsende |
| `cgplc_decisiondate` | B | **Entscheidungsdatum – maßgeblich** für die CY/PY-Zuordnung (Guidance S. 2) |
| `cgplc_forecastdecisiondate` | B | Erwartetes Entscheidungsdatum |
| `cgplc_operationstartdate` | B | Betriebsbeginn |
| `cgplc_operationenddate` | C | Demobilisierung |
| `cgplc_noticeperiod` | C | Kündigungsfrist – ersetzt bei Verfügbarkeit die pauschale 3-Monats-Annahme |
| `cgplc_retenderdate` | C | Nächste Ausschreibung – Frühwarnung |
| `cgplc_contractstartdate` | C | Vertragsbeginn |

### Werte und Risiko

| Feld | Status | Verwendung |
|---|---|---|
| `cgplc_lastfyrevenuearo` | B | **Vorjahres-ARO – Bemessungsgrundlage MAP136** |
| `cgplc_revenuearo` | B | Aktueller ARO |
| `cgplc_currentrevenuearo` | S | Laufender Umsatz |
| `cgplc_budgetrevenuearo` | C | Budget-ARO |
| `cgplc_retentionprobability` | B | Haltewahrscheinlichkeit 0–100 |
| `cgplc_reasonforriskname` | B | **Risikogrund** |
| `cgplc_reasonforrisk` | C | Risikogrund als Optionset – stabiler als der Klartext |
| `cgplc_riskcategory` | C | Risikokategorie |
| `cgplc_competitorid` | C | Konkurrierender Anbieter |
| `cgplc_retentionactionplan` | C | Maßnahmenplan – Grundlage für die Nachverfolgung im Call |
| `cgplc_bgpercent` | C | Bruttomarge |

---

## Nachschlagetabellen

| Entität | Zweck | Ersetzt |
|---|---|---|
| `account` | Kundenname, Konzernstruktur, Branche, Region | `dim_opp_account`, `dim_opp_parent` |
| `territory` | Vertriebsgebiete inkl. Hierarchie | `dim_opp_territory` |

Die `dim_opp_*`-Tabellen des Altmodells entstanden per "Duplikate entfernen"
aus dem Fakt. Das hatte zwei Folgen: Stammdaten ohne offene Opportunity
fehlten in der Dimension, und Attribute stammten aus dem Fakt statt aus der
Quelle. Beides ist mit echten Entitätsextrakten behoben.

### Bewusst nicht extrahiert

**`systemuser`** ist im Mandanten nicht abrufbar. Das ist verschmerzbar: der
Klarname des Verantwortlichen kommt als `owneridname` direkt an der
Opportunity bzw. am Vertrag mit – genau daraus speist sich `owner_name` in
Silver. Es entfällt lediglich die Möglichkeit, Verantwortliche ohne einen
einzigen offenen Vorgang zu listen.

**`audit`** ist im Mandanten für `opportunity` **nicht aktiviert**. Die
Bewegungsanalyse (`gold_fct_crm_movement`) arbeitet deshalb ausschließlich mit
den Tagessnapshots aus `silver_opportunity_history` /
`silver_contract_history` – das ist der tragende Mechanismus, kein Notbehelf.
Konsequenz: Änderungen sind auf Tagesgranularität sichtbar (mehrere Änderungen
am selben Tag erscheinen als eine), und der Bearbeiter der Änderung ist nicht
erfasst. Sollte Audit später aktiviert werden, lässt sich die feinere Historie
ergänzen, ohne dass sich am Datenmodell etwas ändert.

---

## Konforme Attribute

Sechs Merkmale gelten für **beide** Geschäftsarten und liegen deshalb nicht nur
in den Dimensionen, sondern auch auf der Faktentabelle:

Alle Quellspalten sind die `…name`-Anzeigenamen der jeweiligen Lookups (mit
GUID-Rückfall über `name_oder_id()`, siehe oben):

| Attribut | Quelle New Business | Quelle Lost Business |
|---|---|---|
| Sektor | `opportunity.cgplc_sectorlookupname` | `cgplc_cgcontract.cgplc_sectorlookupname` |
| Subsektor | `opportunity.cgplc_subsectorname` | `cgplc_cgcontract.cgplc_subsectorname` |
| Vertragsart | `opportunity.cgplc_contracttypelookupname` | `cgplc_cgcontract.cgplc_contracttypelookupname` |
| Kunde | `account.name` über `accountid` | `account.name` über `cgplc_accountid`, ersatzweise `cgplc_accountidname` |
| Verantwortlicher | `opportunity.owneridname` | `cgplc_cgcontract.owneridname` |
| Werk | Auflösungskette, siehe unten | Auflösungskette, siehe unten |

### Werk-Zuordnung über die Mapping-Tabelle

`cgplc_sapid` ist am Vorgang nur lückenhaft gepflegt, und die SAP-Nummer am
Konto ist ein **Debitor, kein Betrieb** – sie taugt nicht als Ersatz. Die
fachliche Information, wohin ein Vorgang gehört, hängt am **Sektor und
Subsektor** und wird vom Controlling in `Mapping_Planwerke.xlsx` gepflegt
(geladen über `dataflows/df_map_unit_assignment/01_stg_map_unit_assignment.m` nach
`bronze_map_unit_assignment`).

Auflösungskette, erster Treffer gewinnt:

| Stufe | Quelle | `Werk Zuordnung` im Fakt |
|---|---|---|
| 1 | `entity_id`-Ausnahme in der Mapping-Tabelle | `Ausnahme (Mapping)` |
| 2 | `cgplc_sapid` am Vorgang selbst | `CRM direkt` |
| 3 | Mapping-Zeile mit Sektor **und** Subsektor | `Mapping Sektor/Subsektor` |
| 4 | Mapping-Zeile mit Sektor allein (Subsektor leer) | `Mapping Sektor` |
| 5 | – | `Nicht zugeordnet` → DQ-MAP-001 |

Die Spalte `Werk Zuordnung` steht auf der Faktentabelle: je Vorgang ist
sichtbar, welche Stufe gegriffen hat. Fehlende Mapping-Zeilen listet Regel
**DQ-MAP-002** als Arbeitsliste für die Pflege der Excel-Datei.

**Warum auf dem Fakt und nicht nur in den Dimensionen:** `DIM Opportunity` und
`DIM Vertrag` sind getrennte Dimensionen. Ein Datenschnitt auf
`DIM Opportunity[Sektor]` filtert nur die New-Zeilen; die Lost-Zeilen hängen an
dieser Dimension gar nicht und laufen unverändert durch. Das Ergebnis wäre ein
„Net New ITY im Sektor Healthcare", das das gesamte Lost Business aller
Sektoren enthält – falsch, ohne Fehlermeldung.

**Regel für den Berichtsbau:** Datenschnitte, die beide Geschäftsarten treffen
sollen, verwenden die Spalten der Faktentabelle. Die gleichnamigen
Dimensionsspalten bleiben für Detailsichten innerhalb einer Geschäftsart.

Regel **DQ-FCT-004** überwacht, dass keines dieser Attribute einseitig leer
läuft, und blockiert die Aktualisierung, wenn doch.

---

## Neue Auswertungsmöglichkeiten

Was mit dem erweiterten Feldkatalog beantwortbar wird und vorher nicht war:

| Frage | Benötigte Felder |
|---|---|
| Gegen welche Wettbewerber verlieren wir am meisten Volumen? | `cgplc_currentsupplier`, `cgplc_competitorid` |
| Aus welchen Gründen verlieren wir? | `cgplc_reasonforlossname`, `cgplc_reasonforriskname` |
| Wie lange liegt eine Opportunity schon in derselben Phase? | `createdon`, `modifiedon`, `salesstage` + Snapshot-Historie |
| Wie oft verschiebt sich ein Entscheidungsdatum, bevor es hält? | `estimatedclosedate` über die Snapshot-Historie (Tagesgranularität) |
| Wie sieht Net New nach Marge statt nach Umsatz aus? | `cgplc_bgpercent`, `cgplc_ebitpercent` |
| Welche Verluste sind mit Maßnahmen hinterlegt? | `cgplc_retentionactionplan` |
| Welche Bestandsverträge laufen aus, ohne dass eine Ausschreibung terminiert ist? | `cgplc_contractenddate`, `cgplc_retenderdate` |
| Wie groß ist der Mobilisierungsaufwand des Gewonnenen? | `cgplc_numberofsites`, `cgplc_headcount`, `cgplc_capexvalue` |

## Vorgehen zur Verifikation

Nach dem ersten Lauf des Dataflows:

```sql
SELECT DISTINCT _fehlende_felder
FROM   bronze_crm_opportunity
WHERE  snapshot_date = (SELECT MAX(snapshot_date) FROM bronze_crm_opportunity);
```

Die Ausgabe listet alle Wunschfelder, die im Mandanten nicht existieren. Für
jedes davon ist zu entscheiden: im CRM anlegen, durch ein vorhandenes Feld
ersetzen, oder aus der Wunschliste streichen.
