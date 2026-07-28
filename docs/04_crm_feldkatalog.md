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
Die Feldlisten stehen in `dataflows/df_crm_opportunity.m` und
`dataflows/df_crm_contract.m`.

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
| `account` | Kundenname, Konzernstruktur, SAP-Debitor, Branche, Region | `dim_opp_account`, `dim_opp_parent` |
| `systemuser` | Klarname des Verantwortlichen | `dim_opp_owner` |
| `territory` | Vertriebsgebiete inkl. Hierarchie | `dim_opp_territory` |
| `audit` | Änderungshistorie der Opportunities | – (neu) |

Die vier `dim_opp_*`-Tabellen des Altmodells entstanden per "Duplikate
entfernen" aus dem Fakt. Das hatte zwei Folgen: Stammdaten ohne offene
Opportunity fehlten in der Dimension, und Attribute stammten aus dem Fakt statt
aus der Quelle. Beides ist mit echten Entitätsextrakten behoben.

### Zur Audit-Entität

`audit` liefert die tatsächliche Änderungshistorie mitsamt Zeitstempel und
Bearbeiter – deutlich feiner als unsere Tagessnapshots. Die Entität muss im
Mandanten für `opportunity` aktiviert sein. Ist sie es nicht, liefert die
Abfrage eine leere Tabelle, und die Bewegungsanalyse arbeitet mit den
Tagessnapshots aus `silver_opportunity_history` weiter. Beide Wege füttern
dieselbe Gold-Tabelle `gold_fct_crm_movement`.

---

## Neue Auswertungsmöglichkeiten

Was mit dem erweiterten Feldkatalog beantwortbar wird und vorher nicht war:

| Frage | Benötigte Felder |
|---|---|
| Gegen welche Wettbewerber verlieren wir am meisten Volumen? | `cgplc_currentsupplier`, `cgplc_competitorid` |
| Aus welchen Gründen verlieren wir? | `cgplc_reasonforlossname`, `cgplc_reasonforriskname` |
| Wie lange liegt eine Opportunity schon in derselben Phase? | `createdon`, `modifiedon`, `salesstage`, `audit` |
| Wie oft verschiebt sich ein Entscheidungsdatum, bevor es hält? | `estimatedclosedate` über `audit` bzw. Snapshot-Historie |
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
