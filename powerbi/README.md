# CRM Net New Budget — PBIP-Projekt

Power-BI-Projekt für den neu gebauten Bericht. Öffnen mit
`CRM Net New Budget.pbip` in Power BI Desktop (PBIP-Vorschaufeature muss
aktiv sein: *Datei → Optionen → Vorschaufeatures → Power BI Project (.pbip)
save option*).

## Vor dem ersten Öffnen: zwei Parameter setzen

Beim ersten Refresh fragt Power BI nach den Verbindungsparametern. Der
SQL-Endpoint ist bereits eingetragen, der Name der Datenbank fehlt:

| Parameter | Wert |
|---|---|
| `SqlEndpoint` | `3w3wftkijo6ujehh4fb2eleovu-sdjibi3hrggujev7dt4yjznhu4.datawarehouse.fabric.microsoft.com` |
| `WarehouseName` | **`BITTE_EINTRAGEN`** → Name des Lakehouse bzw. Warehouse |
| `FY_Start` | `01.10.2025` — Beginn des Betrachtungszeitraums |
| `FY_Ende` | `30.09.2027` — Ende des Betrachtungszeitraums |

`WarehouseName` ist der Anzeigename des Artefakts im Fabric-Workspace, unter
dem die Tabellen im Schema `dbo` liegen. Zu ändern über *Transformieren →
Parameter verwalten*.

`FY_Start` und `FY_Ende` steuern `dim_date` und damit den kompletten
Auswertungshorizont — sie ersetzen die vier `Est_*`-Parameter und die fest
verdrahteten `#date(2027, 9, 30)` des Altmodells.

## Voraussetzung im Lakehouse

Das Modell liest fünf Tabellen aus `dbo`, die von der Ladestrecke erzeugt
werden (`fabric/lakehouse/`):

```
fct_opportunity_current        fct_opportunity_changes
fct_retention_current          fct_retention_changes
map_opportunity_unit_current
```

Existieren sie noch nicht, zuerst `01_create_tables.sql`,
`02_load_snapshot.py` und `03_derived_tables.sql` im Notebook ausführen.

Zusätzlich hängt `dim_sap_master_data_unit` am bestehenden
Gruppen-Dataflow (`sap_master_data_unit`). Ist der nicht erreichbar, kann die
Tabelle entfernt werden — dann entfallen `dim_unit[sektor]`, `dim_unit[bezirk]`,
`fct_retention[sektor]` und die Unterscheidung `In Betrieb` / `Geplant`.

## Speichermodus: Import, nicht Direct Lake

Das ursprüngliche Zielbild sah Direct Lake vor. Dieses Projekt ist **Import**,
und der Grund ist eine harte Einschränkung: Direct Lake unterstützt keine
berechneten Spalten und keine berechneten Tabellen auf Direct-Lake-Tabellen.
Das Modell lebt aber genau davon — die ITY-Phasierung, `fct_budget_effect`,
`dim_unit` und sämtliche abgeleiteten Dimensionen sind DAX-Tabellen, dazu
kommen Spalten wie `win_status`, `Ret_Status` und `days_to_decision`.

Import ist hier auch fachlich unkritisch: die Quelle wechselt genau einmal
täglich, ein Refresh nach dem Notebook-Lauf genügt. Der Preis ist ein
Refresh-Schritt mehr und Speicher im Modell statt im Lakehouse.

**Wenn Direct Lake gewünscht ist**, muss die Ableitungslogik nach Spark
wandern: Phasierung und `fct_budget_effect` als Delta-Tabellen in
`03_derived_tables.sql`, Dimensionen ebenso. Das Modell enthielte dann nur
noch physische Tabellen und Measures. Das ist der sauberere Endzustand, aber
eine eigene Ausbaustufe — die Phasierungslogik müsste von DAX nach Spark SQL
übersetzt und gegengerechnet werden.

## Seiten

| Seite | Inhalt |
|---|---|
| Leading KPIs | Nettoeffekt, gewichtete Pipeline, Win Rate, At Risk Share, Mappingstand |
| Net New Budget | Budgetwirkung je Periode und Effektart, Nettoeffekt je Betrieb |
| Pipeline-Bewegung | Zugang, Wertbewegung, Stage-Wechsel, Terminverschiebungen |
| Retention | Exposure, Risikogründe, Bewegung der Einschätzung, Entscheidungen |
| Mapping & Datenqualität | Effekt ohne Betriebszuordnung, Unit-Status, Datenstand |

## Was bewusst fehlt

Die Measures `90_Value`, `90_Periodic` und `Pipeline Coverage` sind **nicht**
enthalten. Sie hängen an der SAP-Tabelle `Revenues` aus dem Altmodell, die
nicht Teil dieser Strecke ist. Sobald `Revenues` angebunden ist, lassen sie
sich unverändert aus `fabric/semantic-model/03_measures.dax` übernehmen —
`Pipeline Coverage` ist als Deckungsgrad gegen `[90_Value]` definiert und
wird erst damit sinnvoll.

Ebenfalls nicht übernommen: die Export-Seiten des Altberichts und das
Zebra-BI-Custom-Visual. Beides lässt sich ergänzen, hing aber an Tabellen
und Lizenzen außerhalb dieser Strecke.
