# 09 – Abgleich mit der Vorarbeit

Dieses Repository entstand zunächst ohne Kenntnis zweier früherer Branches.
Sie wurden nachgereicht und hier eingearbeitet. Das Dokument hält fest, was
übernommen wurde, was bewusst abweicht und was noch offen ist.

## Die beiden Branches

| Branch | Inhalt | Verhältnis zum aktuellen Stand |
|---|---|---|
| `claude/crm-report-rebuild-1bwcfg` | Vollständige Lakehouse-Strecke für den CRM-Call: Dataflows, Snapshot-Historisierung, abgeleitete Tabellen, PBIP mit 48 Kennzahlen inkl. Leading KPIs | **Substanziell weiter** als der ursprüngliche Neubau in mehreren Punkten. Teilweise eingearbeitet, Rest siehe „Offen" |
| `claude/pbib-report-restructure-fq7uor` | Der bestehende Bericht „Net New ITY" mit neuem Theme `NetNewITY_Theme.json` und zehn überarbeiteten Visualisierungen | Themenarbeit auf dem **Altbericht**. Dieselbe validierte Farbmethodik, die auch hier verwendet wird – der Neubau ist die konsequente Fortführung, kein Widerspruch |

---

## Übernommen

### 1. Idempotenter Snapshot-Load über Staging

**Das war ein echter Defekt im ursprünglichen Neubau.** Die Dataflows
schrieben mit Aktualisierungsmethode *Anfügen* direkt nach `bronze_*`. Läuft
ein Dataflow an einem Tag zweimal – Retry nach Timeout, manueller Refresh –
stehen zwei Snapshots mit identischem `snapshot_date` in der Tabelle und
**jede Summe verdoppelt sich**, ohne Fehler und ohne Warnung.

Jetzt wie in der Vorarbeit:

```
Dataflow Gen2 (REPLACE)  →  stg_*
nb_05_snapshot.py        →  bronze_*   (Partition löschen, dann anfügen)
```

`nb_05_snapshot.py` prüft zusätzlich:

* genau ein `snapshot_date` je Staging-Tabelle (sonst lief der Extrakt über
  Mitternacht),
* der Geschäftsschlüssel ist je Snapshot eindeutig,
* das `snapshot_date` ist der heutige Berliner Tag – sonst ist der Dataflow
  fehlgeschlagen und der Vortagsstand steht noch im Staging. Ohne diesen
  Wächter meldet der Lauf Erfolg, es entsteht kein neuer Snapshot, und der
  Bericht zeigt alte Zahlen als aktuell.

Ergänzt um Regel **DQ-SNP-001**, die denselben Fehler auch dann fängt, wenn
jemand die Ladestrecke umbaut.

### 2. Zeitzone Europe/Berlin

**Ebenfalls ein Defekt.** Die Fabric-Kapazität der Gruppe läuft in UK-Zeit,
der Service in UTC. Ein Ladelauf zwischen 00:00 und 01:00 Berliner Zeit bekäme
das Datum des Vortags, fiele in die Vortagspartition, überschriebe dort den
echten Vortagsstand und **löschte einen Tag Historie** aus den
Bewegungstabellen. Bei einem Nachtplan oder einem Retry nach Mitternacht
passiert das unbemerkt.

Übernommen: `dataflows/fn_berlin_now.m` (EU-Sommerzeitregel explizit, in der
Vorarbeit stundenweise über 2024–2035 gegen die IANA-Daten geprüft) und
`spark.conf.set("spark.sql.session.timeZone", "Europe/Berlin")` in
`nb_00_config.py`. Der Zonenversatz wird vor dem Schreiben abgeschnitten, weil
das Lakehouse-Ziel eines Dataflow Gen2 `datetimezone` nicht unterstützt.

Zusätzlich werden `snapshot_date` und `loaded_at` jetzt **einmal je Lauf**
ausgewertet statt je Zeile.

### 3. Mapping an die reale Datei angeglichen

Der erste Entwurf erfand Spaltennamen (`entity_id`, `werk`). Die reale
`Mapping_Planwerke.xlsx` trägt `dim_opp_name[opportunityid]` und
`Mapping Unit`. Beide Bestandsspalten werden jetzt mit `MissingField.Error`
gelesen – ein Umbau der Datei muss auffallen, nicht stillschweigend zu einem
leeren Mapping führen. Die Sektorspalten sind optional ergänzt, damit die
Erweiterung schrittweise erfolgen kann.

**Reihenfolge korrigiert.** Der erste Entwurf setzte `cgplc_sapid` vor das
Mapping. Das ist falsch: die CRM-Brücke greift nur für Opportunities, die
einen *bestehenden* Vertrag betreffen, und läuft für echte Net-New-Units
definitionsgemäß leer. Das gepflegte Mapping trägt die vorausschauende
Annahme und ist die fachlich maßgebliche Quelle. Stünde die Brücke davor,
überstimmte ein veralteter `cgplc_sapid`-Eintrag eine bewusst gepflegte
Zuordnung. Jetzt:

1. Mapping-Ausnahme über `opportunityid`
2. Mapping über (Sektor, Subsektor)
3. Mapping über (Sektor)
4. CRM-Brücke `cgplc_sapid` – Rückfallebene
5. NULL → DQ-MAP-001

**Mapping wird historisiert.** Es ist ein manueller Input in offizielle
Budgetzahlen; ohne Snapshot lässt sich eine abgeschlossene Budgetrunde nach
der nächsten Pflegerunde nicht mehr reproduzieren. Es läuft deshalb durch
dieselbe Staging-Historisierung wie die Fakten; die Auflösung nutzt den
jüngsten Stand.

### 4. Geplante Units in der Betriebsdimension

`DIM Betrieb` speiste sich ausschließlich aus den SAP-Stammdaten. Damit fielen
genau die Units in die Leerzeile, um die es im Net New Business geht:
Betriebe, die noch nicht gewonnen sind und deshalb in SAP nicht existieren.
Sie stehen ausschließlich im gepflegten Mapping.

Jetzt vereinigt `gold_dim_unit` beide Herkünfte, unterschieden über
`Unit-Status` (*In Betrieb* / *Geplant*).

---

## Bewusst abweichend

Zwei Entscheidungen widersprechen der Vorarbeit. Beide sind vertretbar; die
Abweichung ist dokumentiert, damit sie nicht als Versehen gelesen wird.

### Vorzeichen im Lakehouse statt im Measure

Die Vorarbeit führt in den Tabellen ausschließlich positive Beträge und dreht
das Vorzeichen im Measure `Netto Budgeteffekt` – Begründung: die Rohtabelle
ist ohne Vorzeichenwissen lesbar.

Hier wird das Vorzeichen einmalig im Lakehouse gesetzt (`amount_signed`: New
positiv, Lost negativ). Begründung: die drei Altmodelle drehten dasselbe
Vorzeichen an mindestens fünf Stellen unterschiedlich – teils in M, teils in
DAX –, sodass dieselbe Größe je Kennzahl ein anderes Vorzeichen hatte. Eine
einzige Festlegung an der Quelle macht `Net New ITY` zur simplen Summe und
`DQ-FCT-002` zum Wächter darüber.

**Wenn beide Stände zusammengeführt werden, muss hier eine Entscheidung
fallen** – die Kennzahlen sind sonst nicht mischbar.

### Harmonisierung: eine Faktentabelle statt zweier

Die Vorarbeit hält Opportunities und Contracts bis zur Effektebene getrennt
(`fct_opp_phasing`, `fct_retention_phasing`, vereinigt in
`fct_budget_effect`) – Begründung: fast disjunkte Attribute, typspezifische
Änderungsverfolgung.

Hier gibt es eine gemeinsame `gold_fct_net_new_ity` mit `business_type` als
Diskriminator und einem konformen Attributsatz, der für beide Seiten gefüllt
ist. Die Stammdaten bleiben in getrennten Dimensionen (`DIM Opportunity`,
`DIM Vertrag`). Das ist näher an der Vorarbeit, als es zunächst aussieht: auch
dort konvergiert die Semantik auf der Achse Periode × Betrieb. Der Unterschied
ist, wo die Vereinigung passiert.

---

## Offen

Diese Punkte aus der Vorarbeit sind **noch nicht** eingearbeitet. Sie sind
keine Kleinigkeiten.

### Vollextrakt statt gefiltertem Abzug

Die Vorarbeit zieht **alle** Opportunities und Contracts, unabhängig von
Status, Sales Stage und Datum, und verlagert die fachlichen Einschränkungen in
die Phasierung – dort begrenzen sie die Budgetwirkung, nicht den Datenbestand.

Der aktuelle Stand filtert bereits in Silver (`statecodename <> "Verloren"`,
Stage-Ausschlüsse, Datumsfenster). Damit sind strukturell ausgeschlossen:

* **Win Rate** – braucht die verlorenen Opportunities
* **Avg Sales Cycle** – braucht die abgeschlossenen
* **Stage Movements** über das Ausscheiden hinaus

Umstellung heißt: Filter aus `nb_10_silver` entfernen und in `nb_20_gold` vor
den Fanout setzen. Wichtig dabei – und in der Vorarbeit ausdrücklich vermerkt:
Weil der Extrakt ohne Datumsfilter zieht, muss die Phasierung die Untergrenze
selbst setzen, sonst erzeugt jede Opportunity aus abgeschlossenen Jahren volle
Budgetwirkung über den ganzen Horizont. Ein weggelassener Filter fällt nicht
als Fehler auf, sondern als stille Überzeichnung.

### Leading KPIs

Die Vorarbeit definiert 48 Kennzahlen, darunter elf, die erst durch
Historisierung und Vollextrakt möglich werden:

| KPI | Aussage | Voraussetzung |
|---|---|---|
| Net New Pipeline (30d) | Wächst die Pipeline nach? | Historisierung ✓ |
| Pipeline Value Movement | Organisches Wachstum oder nachträgliche Abwertung? | Historisierung ✓ |
| Stage Movements | Bewegt sich die Pipeline überhaupt? | Historisierung ✓ |
| Close Date Slippage | Werden Abschlüsse systematisch verschoben? | Historisierung ✓ |
| Stale Pipeline ARO | Volumen ohne Fortschritt seit 90 Tagen | Historisierung ✓ |
| Retention Probability Movement | Verschlechtert sich die Einschätzung? | Historisierung ✓ |
| Newly At Risk ARO | Neu gefährdetes Volumen | Historisierung ✓ |
| Decisions Due 90d | Operativer Handlungsbedarf | – ✓ |
| At Risk Share | Anteil gefährdeter Bestandsumsätze | – ✓ |
| **Win Rate (Wert/Anzahl)** | Qualität der Pipeline | **Vollextrakt ✗** |
| **Avg Sales Cycle** | Wie lange dauert ein Abschluss? | **Vollextrakt ✗** |

Neun davon sind mit der bestehenden Snapshot-Historie sofort umsetzbar; zwei
hängen am Vollextrakt.

Dazu die Pflegestandskennzahlen `Unmapped Effekt`, `Unmapped Opportunities`,
`Unmapped Anteil` – sie zeigen, welches Volumen noch keinem Betrieb zugeordnet
ist, solange eine Budgetrunde offen ist. Der aktuelle Stand hat dafür nur die
DQ-Regeln, keine Kennzahl im Bericht.

### `04_pruefung.sql`

Neun Abfragen zum Gegenrechnen einzelner Opportunities gegen den Altbericht.
Der aktuelle Stand hat DQ-Regeln (die auf Verstöße prüfen), aber kein
Werkzeug, um eine einzelne Opportunity Monat für Monat nachzurechnen.

### `cfg_horizont`

Die Vorarbeit legt den Betrachtungszeitraum in eine einzeilige Tabelle statt
in Konstanten. Der aktuelle Stand pflegt ihn an zwei Stellen
(`nb_00_config.py` und `expressions.tmdl`), die übereinstimmen müssen –
`docs/06_deployment.md` weist darauf hin, aber eine Tabelle wäre die bessere
Lösung.

### Report-Theme aus `pbib-report-restructure`

`NetNewITY_Theme.json` verwendet dieselbe validierte Farbmethodik wie das
Theme dieses Repositories, mit der vollen achtstelligen kategorialen Palette.
Der Neubau nutzt stattdessen zwei semantische Ein-Ton-Rampen (Blau für New,
Rot für Lost, Helligkeit = Sicherheitsgrad). Kein Konflikt, aber ein bewusster
Unterschied: die kategoriale Palette ist richtig, wenn die Serien beliebige
Kategorien sind; hier sind sie zwei geordnete Skalen.
