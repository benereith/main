# Net New ITY Cockpit

Konsolidierung der drei bestehenden Net-New-ITY-Berichte zu einem Bericht, einem
Semantikmodell und einer Datenstrecke.

---

## Worum es geht

Aus dem CRM wird approximiert, wie sich das **unknown ITY** entwickelt – also
der Anteil des Net New Business, der noch nicht auf einem realen SAP-Betrieb
gebucht ist. Der Rechenweg:

```
New Business                       Lost Business
─────────────────────────────      ────────────────────────────────
ITY-Umsatz aus dem CRM             Vorjahres-ARO aus dem CRM
  × Gewinnwahrscheinlichkeit         × (1 − Haltewahrscheinlichkeit)
  ÷ Anzahl Monate bis zum             ÷ 12
    Ende des 1. Geschäftsjahres
  → Monatswert                      → Monatswert
  → auf die Perioden verteilt       → auf die Perioden verteilt
                    ╲               ╱
                     Net New ITY je Monat
                     (New positiv, Lost negativ)
```

Grundlage der Definitionen ist die Group Guidance *New & Lost Business – HFM
Revenue Definitions & Guidance* (Februar 2025). Die relevanten Konten:

| Konto | Bedeutung |
|---|---|
| MAP131 | New Business Revenue (ARO) – erste 12 Monate gewonnener Verträge |
| MAP141a | New Business Revenue (ITY) – Wirkung davon im laufenden Jahr |
| MAP136 | Lost Business Revenue (ARO) – letzte 12 Monate gekündigter Verträge |
| MAP141c | Lost Business Revenue (ITY) – Wirkung davon im laufenden Jahr |

Maßgeblich für die Zuordnung zu laufendem oder Vorjahr ist laut Guidance das
**Entscheidungsdatum** im CRM, nicht das Mobilisierungs- oder Schließungsdatum.

---

## Was sich ändert

| | Vorher | Nachher |
|---|---|---|
| Berichte | 3 | 1 |
| Seiten | 51 (davon 22 Duplikate) | 9 |
| Semantikmodelle | 3 | 1 |
| Tabellen | 87 | 16 |
| Kennzahlen | ~109, überwiegend undokumentiert | 51, jede mit Beschreibung |
| Auto-Datumstabellen | 32 | 0 |
| Perioden-Fanout | 3 verschiedene Umsetzungen | 1, im Lakehouse |
| Szenarien | fest verdrahtet in Power Query | 5 Regler im Bericht |
| Excel im Produktivpfad | 3 SharePoint-Dateien | 0 |
| CRM-Felder | 34 | 90 (Wunschliste, wächst schrittweise) |
| Datenqualitätsprüfung | keine | 12 Regeln, blockierend bei ERROR |
| Bewegungsanalyse | keine | eigene Seite mit Vorher/Nachher |

### Die drei wichtigsten Verbesserungen

**1. Kein manuelles Shiften mehr.** Anlauffaktor, Anlaufdauer, zeitliche
Verschiebung, Bewertungsbasis und Mindestwahrscheinlichkeit sind Regler im
Bericht. Vorher steckten sie als Konstanten in Power Query (0,8 über 3 Monate,
Verschiebung +1); jede Änderung war eine Modelländerung mit vollem Refresh.

**2. Entwicklungen im CRM sind zeigbar.** Eine Snapshot-Historie erfasst
täglich, was sich geändert hat – Wert, Wahrscheinlichkeit, Status – und stellt
Vorher und Nachher nebeneinander. Die Frage "was ist seit dem letzten Call
passiert?" hat jetzt eine Seite.

**3. Nichts verschwindet mehr still.** Wo die Altmodelle fehlerhafte Sätze per
`Table.SelectRows` aus dem Datenstrom entfernten, protokolliert der Neubau sie
mit Name, Grund und Handlungsanweisung.

---

## Aufbau des Repositories

```
docs/                    Dokumentation (Einstieg: 01_architektur.md)
lakehouse/
  notebooks/             PySpark: Bronze -> Silver -> Gold -> Qualität
  03_gold/               T-SQL-Variante des Perioden-Fanouts
dataflows/               M-Code der CRM-Extrakte
powerbi/
  Net New ITY Cockpit.pbip
  ...SemanticModel/      TMDL: 16 Tabellen, 51 Kennzahlen
  ...Report/             PBIR: 9 Seiten
tools/
  build_report.py        erzeugt die PBIR-Struktur aus einer Deklaration
  generate_docs.py       erzeugt docs/02 und docs/03 aus dem TMDL
  validate_pbip.py       prüft Referenzen, Layout, Dokumentation, Farben
```

---

## Dokumentation

| Datei | Inhalt |
|---|---|
| [01_architektur.md](docs/01_architektur.md) | Ausgangslage, Zielbild, was wohin ausgelagert wurde und warum |
| [02_datenmodell.md](docs/02_datenmodell.md) | Tabellen, Spalten, Beziehungen · *erzeugt* |
| [03_berechnungslogik.md](docs/03_berechnungslogik.md) | Jede Kennzahl mit Beschreibung und DAX · *erzeugt* |
| [04_crm_feldkatalog.md](docs/04_crm_feldkatalog.md) | Alle CRM-Felder, ihre Verwendung, was neu auswertbar wird |
| [05_report_design.md](docs/05_report_design.md) | Gestaltungsentscheidungen, Farbsystem, Seitenaufbau |
| [06_deployment.md](docs/06_deployment.md) | Einrichtung Schritt für Schritt, Betrieb, Fehlerbilder |
| [07_migration_mapping.md](docs/07_migration_mapping.md) | Jede alte Kennzahl und Seite → neu, inkl. bewusster Abweichungen |
| [08_datenqualitaet.md](docs/08_datenqualitaet.md) | Die 12 Regeln, ihre Bedeutung, Zuständigkeiten |

---

## Schnellstart

```bash
python3 tools/validate_pbip.py         # Konsistenz prüfen
```

Dann `powerbi/Net New ITY Cockpit.pbip` in Power BI Desktop öffnen.

Vollständige Einrichtung inklusive Dataflows, Notebooks und Pipeline:
[docs/06_deployment.md](docs/06_deployment.md).

### Nach Änderungen

```bash
python3 tools/build_report.py          # Seitenlayout neu erzeugen
python3 tools/generate_docs.py         # Doku aus dem Modell neu erzeugen
python3 tools/validate_pbip.py         # muss fehlerfrei durchlaufen
```

`validate_pbip.py` schlägt unter anderem fehl, wenn eine Kennzahl keine
Beschreibung hat. Das ist beabsichtigt.

---

## Erste Schritte im Bericht

1. **Cockpit** – Lage auf einen Blick. Der Text oben nennt die Aussage, nicht
   nur die Zahl.
2. **Szenarien** – die fünf Regler. Um die Zahlen des alten Budgetmodells zu
   reproduzieren: Anlauf auf 80 %, Anlaufdauer auf 3 Monate, Verschiebung auf
   +1 Monat.
3. **CRM-Bewegung** – was sich seit dem letzten Stichtag geändert hat.
4. **Abstimmung & Datenqualität** – ob den Zahlen zu trauen ist und was im CRM
   fehlt.

---

## Offene Punkte

* **CRM-Feldverfügbarkeit.** Die mit `[C]` gekennzeichneten Felder in
  `docs/04_crm_feldkatalog.md` sind Wunschfelder und im Mandanten noch nicht
  verifiziert. Der Extrakt lädt fehlende Felder nicht, bricht aber auch nicht
  ab, und protokolliert sie in `_fehlende_felder`.
* **Abnahme gegen die Altberichte.** Der Parallelbetrieb steht noch aus; das
  Vorgehen beschreibt `docs/07_migration_mapping.md`, Abschnitt 5.
* **Mapping-Tabelle befüllen.** Die Werk-Zuordnung der CRM-Vorgänge läuft über
  `Mapping_Planwerke.xlsx` (Sektor/Subsektor → Planbetrieb). Fehlende
  Kombinationen listet Regel DQ-MAP-002 als Arbeitsliste; bis dahin fallen
  nicht zuordenbare Vorgänge in Organisationssichten in die Leerzeile –
  erkennbar an `Werk Zuordnung = "Nicht zugeordnet"`.

## Bekannte Einschränkungen des Mandanten

* **`audit` ist nicht aktiviert.** Die Bewegungsanalyse arbeitet mit
  Tagessnapshots: Änderungen sind auf Tagesgranularität sichtbar, der
  Bearbeiter einer Änderung wird nicht erfasst.
* **`systemuser` ist nicht abrufbar.** Der Name des Verantwortlichen kommt aus
  `owneridname` am Vorgang; Verantwortliche ohne offenen Vorgang sind nicht
  listbar. Verschmerzbar.
