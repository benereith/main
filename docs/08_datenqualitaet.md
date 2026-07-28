# 08 – Datenqualität

Welche Regeln geprüft werden, was sie bedeuten und wer sie behebt.

Umsetzung: `lakehouse/notebooks/nb_30_quality.py`
Ergebnis: `gold_dq_checks` → Tabelle `DQ Prüfungen` → Seite *Abstimmung &
Datenqualität*

---

## Warum das nötig ist

Die Altmodelle entfernten fehlerhafte Datensätze aus dem Datenstrom. In
`fct_opp` etwa:

```m
#"Gefilterte Zeilen 3" = Table.SelectRows(
    #"Neu angeordnete Spalten",
    each [cgplc_openingdate] <> null and [cgplc_openingdate] <> ""
)
```

Eine Opportunity ohne Mobilisierungsdatum verschwand damit spurlos. Ihr
ITY-Beitrag fehlte im Ergebnis, ohne dass irgendwo stand, dass etwas fehlt. Bei
der Frage "warum sind es 1,2 Mio. weniger als letzte Woche?" war das nicht mehr
rekonstruierbar.

Der Neubau filtert dieselben Sätze – protokolliert sie aber mit Namen, Grund
und Handlungshinweis.

---

## Schweregrade

| Grad | Wirkung |
|---|---|
| **ERROR** | Die Pipeline bricht ab. Das Semantikmodell wird **nicht** aktualisiert und behält den letzten geprüften Stand |
| **WARNING** | Der Lauf geht durch, die Regel erscheint im Bericht |
| **INFO** | Reine Kennzahl, kein Handlungsdruck |

Ein Bericht mit älteren, aber korrekten Zahlen ist besser als einer mit
frischen, aber falschen. Deshalb blockiert ERROR.

---

## Die Regeln

### New Business

#### DQ-OPP-001 · Opportunity ohne Mobilisierungsdatum · WARNING

`cgplc_openingdate` ist leer. Ohne dieses Datum gibt es keinen Startpunkt für
die Periodenverteilung – der ITY-Effekt fällt vollständig aus dem Forecast.

**Zuständig:** Vertrieb (Opportunity-Verantwortlicher)
**Behebung:** Mobilisierungsdatum im CRM nachpflegen

#### DQ-OPP-002 · ARO ohne ITY · WARNING

`cgplc_revenuearo > 0`, aber `cgplc_revenueity` leer oder 0. Der ITY-Wert wird
mit 0 gerechnet – die Opportunity taucht im ARO auf, wirkt aber nicht auf das
laufende Geschäftsjahr.

**Zuständig:** Vertrieb
**Behebung:** `cgplc_revenueity` ergänzen. Faustregel: ARO ÷ 12 × Anzahl Monate
vom Mobilisierungsmonat bis zum 30. September.

#### DQ-OPP-003 · ITY größer als ARO · ERROR

`cgplc_revenueity > cgplc_revenuearo`. Fachlich unmöglich: der ITY-Wert ist
laut Group Guidance (S. 3) der Anteil des ARO, der im ersten Geschäftsjahr
anfällt – MAP141a kann MAP131 nicht übersteigen.

**Zuständig:** Vertrieb, Eskalation an Controlling
**Behebung:** Einen der beiden Werte korrigieren

#### DQ-OPP-004 · ITY-Rate weicht stark von ARO ÷ 12 ab · WARNING

Erwartung: ITY ÷ ITY-Monate ≈ ARO ÷ 12. Die Toleranz ist bewusst weit gesetzt
(Faktor 2), damit nur echte Ausreißer auffallen – etwa ein ITY-Wert, der
versehentlich als Jahreswert statt als anteiliger Wert erfasst wurde.

**Zuständig:** Vertrieb
**Behebung:** Plausibilität beider Werte prüfen

#### DQ-OPP-005 · Win-% außerhalb 0–100 · ERROR

**Zuständig:** CRM-Administration
**Behebung:** `cgplc_win` korrigieren, Feldvalidierung im CRM einrichten

#### DQ-OPP-006 · Mobilisierung vor Entscheidung · WARNING

`cgplc_openingdate < estimatedclosedate`. Ein Betrieb, der vor der
Vertragsentscheidung startet, deutet auf einen Pflegefehler bei einem der
beiden Termine hin.

**Zuständig:** Vertrieb
**Behebung:** Termine prüfen

### Lost Business

#### DQ-CON-001 · Risikovertrag ohne Vorjahres-ARO · WARNING

`cgplc_lastfyrevenuearo` fehlt bei einem Vertrag mit Retention unter 100 %. Der
Verlust wird mit **0 €** bewertet – der Vertrag steht in der Liste, wirkt aber
nicht auf die Zahl.

Das ist die gefährlichste der Warnungen, weil sie das Ergebnis systematisch zu
günstig aussehen lässt. Auf der Seite *Lost Business* ist deshalb ein Filter auf
`DIM Vertrag[ARO-Status]` vorgesehen, mit dem sich diese Verträge isolieren
lassen.

**Zuständig:** Controlling
**Behebung:** Vorjahres-ARO aus SAP übernehmen

#### DQ-CON-002 · Vertrag ohne Enddatum und ohne Entscheidungsdatum · WARNING

Ohne beide Daten ist keine Periodenzuordnung möglich. Die Ersatzregel
(Entscheidungsdatum + 3 Monate) greift nicht.

**Zuständig:** Vertrieb
**Behebung:** Mindestens eines der beiden Daten pflegen. Die Group Guidance
(S. 2) stellt ausdrücklich auf das **Entscheidungsdatum** ab.

#### DQ-CON-003 · Retention-% außerhalb 0–100 · ERROR

**Zuständig:** CRM-Administration

### Faktentabelle

#### DQ-FCT-001 · Lücken in der Monatskette · ERROR

Jede Entität muss eine lückenlose Monatskette haben. Eine Lücke bedeutet einen
Fehler im Fanout, nicht in den Quelldaten.

**Zuständig:** BI-Entwicklung
**Behebung:** `nb_20_gold.py`, Abschnitt 5 prüfen

#### DQ-FCT-002 · Vorzeichenkonvention verletzt · ERROR

New Business muss ≥ 0 sein, Lost Business ≤ 0. Ein Verstoß bedeutet, dass die
Vorzeichenlogik in `nb_20_gold` nicht gegriffen hat – und dass jede
Net-New-Summe im Bericht falsch ist.

**Zuständig:** BI-Entwicklung

#### DQ-FCT-003 · Rekonstruktion des ITY-Gesamtwerts · ERROR

Die Summe der monatlichen ITY-Werte einer Opportunity im ersten Geschäftsjahr
muss dem gewichteten ITY-Gesamtwert entsprechen (Toleranz 1 Cent).

Das ist die schärfste Regel: Sie prüft, ob der Perioden-Fanout insgesamt
korrekt gerechnet hat. Schlägt sie an, stimmt entweder `calc_ity_months` nicht
oder die Abgrenzung zwischen ITY- und ARO-Phase.

**Zuständig:** BI-Entwicklung

### Zuordnung

#### DQ-MAP-001 · Opportunity ohne Betriebszuordnung · INFO

Ohne Zuordnung zu einem SAP-Betrieb lässt sich die Opportunity nicht gegen
gebuchte Umsätze stellen. Die Auswertung nach Sektor und Vertriebsgebiet
funktioniert trotzdem.

Diese Regel ersetzt die SharePoint-Datei `Mapping_Planwerke.xlsx` der
Altmodelle: Statt einer manuell gepflegten Zuordnungsliste außerhalb des
Systems zeigt der Bericht, wo die Zuordnung fehlt.

**Zuständig:** Controlling
**Behebung:** `cgplc_sapid` im CRM pflegen

---

## Auswertung

Aktueller Stand:

```sql
SELECT   regel_id, schweregrad, anzahl_verstoesse, beschreibung, hinweis
FROM     gold_dq_checks
WHERE    pruef_datum = (SELECT MAX(pruef_datum) FROM gold_dq_checks)
     AND anzahl_verstoesse > 0
ORDER BY CASE schweregrad WHEN 'ERROR' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END,
         anzahl_verstoesse DESC;
```

Entwicklung über die Zeit – zeigt, ob die Nachpflege vorankommt:

```sql
SELECT   pruef_datum, regel_id, anzahl_verstoesse
FROM     gold_dq_checks
WHERE    regel_id IN ('DQ-OPP-001', 'DQ-CON-001')
ORDER BY pruef_datum DESC, regel_id;
```

Konkrete Datensätze zu DQ-OPP-001:

```sql
SELECT * FROM silver_dq_reject WHERE dq_rule = 'DQ-OPP-001';
```

---

## Eine neue Regel ergänzen

In `nb_30_quality.py`:

```python
check(
    "DQ-XXX-999",              # eindeutige Kennung
    "WARNING",                 # ERROR | WARNING | INFO
    "Kurze Beschreibung des Fehlerbilds",
    df.filter(...),            # DataFrame mit den Verstößen
    "Wer muss was tun, damit es weg ist",
)
```

Der Hinweistext ist kein Beiwerk. Eine Regel ohne konkrete Handlungsanweisung
erzeugt nur Betriebsamkeit: Wer die Meldung sieht, muss ohne Rückfrage wissen,
was zu tun ist.
