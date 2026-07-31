# Dataflows

Drei Dataflows Gen2, kein Monolith. Jede Abfrage steht einzeln in einer
eigenen Datei, damit sie sich per Copy-Paste in den Power-Query-Editor
übertragen lässt, ohne dass Kommentarblöcke oder ein `let…in` erst entpackt
werden müssen.

## Warum drei Dataflows und nicht einer

Die Faustregel: Abfragen, die dieselbe **Quelle** und denselben **Fehlerfall**
teilen, gehören in einen Dataflow. Abfragen mit anderer Quelle gehören in
einen eigenen.

| Dataflow | Abfragen | Quelle | Warum zusammen bzw. getrennt |
|---|---|---|---|
| `df_crm_ingest` | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` | Dataverse (`cpgplc.crm.dynamics.com`) | Gleiche Verbindung, gleicher Gateway, gleicher Zeitplan. Ein CRM-Verbindungsproblem betrifft ohnehin alle vier gleichzeitig – ein gemeinsamer Fehlschlag ist ehrlicher als vier separate, die zufällig gleichzeitig rot werden |
| `df_map_unit_assignment` | `stg_map_unit_assignment`, `stg_budget_ity` | SharePoint / Excel, Ordner `08_Budget` | Andere Quelle, andere Fehlerdomäne. Ein SharePoint-Hänger soll den CRM-Ingest nicht blockieren, und ein CRM-Verbindungsabbruch soll nicht verhindern, dass die gepflegten Excel-Dateien geladen werden. Beide Abfragen lesen aus demselben Ordner derselben Bibliothek – nach der Faustregel oben gehören sie damit zusammen, und ein vierter Dataflow brächte nur eine weitere Pipeline-Aktivität, ohne einen Fehlerfall zu entkoppeln |
| `df_sap_ingest` | `bronze_sap_unit`, `bronze_sap_revenue` | SAP-Warehouse `Reporting`, Gen1-Dataflow `sap_master_data_unit` | Dritte Quelle mit eigenem Gateway. Schreibt als einziger Dataflow direkt nach `bronze_*` statt nach `stg_*`, weil SAP-Daten **nicht historisiert** werden – Begründung unten |

Eine einzige Abfrage **alles in einem Dataflow abzubilden** (auch die Mapping-
Tabelle mit hineinzunehmen) würde funktionieren, koppelt aber zwei Systeme
ohne fachlichen Grund: Ein Timeout bei SharePoint würde dann auch den
CRM-Ingest als fehlgeschlagen melden, obwohl Dataverse einwandfrei geliefert
hat. In der Pipeline (`docs/06_deployment.md`) laufen beide Dataflows
ohnehin parallel und werden erst danach von `nb_05_snapshot.py` gemeinsam
verarbeitet – die Trennung kostet also nichts an Orchestrierung.

## Aufbau je Ordner

```
df_crm_ingest/
  00_fn_berlin_now.m            Funktionsquery, "Laden aktivieren" AUS
  01_stg_crm_opportunity.m
  02_stg_crm_contract.m
  03_stg_crm_account.m
  04_stg_crm_territory.m

df_map_unit_assignment/
  00_fn_berlin_now.m            eigene Kopie - Dataflow Gen2 teilt Funktionen
                                 nicht ueber Dataflow-Grenzen hinweg
  01_stg_map_unit_assignment.m
  02_stg_budget_ity.m           Budgetannahmen unknown ITY

df_sap_ingest/
  00_fn_berlin_now.m            eigene Kopie, siehe oben
  01_bronze_sap_unit.m          Quellnavigation beim Einrichten erzeugen
  02_bronze_sap_revenue.m       SapServer und AktuellesGJ eintragen
```

Jede Datei außer `00_fn_berlin_now.m` beginnt mit `let` und endet mit `in
<letzter Schritt>` – copy-paste-fertig für eine neue Abfrage im
Power-Query-Editor (Erweiterter Editor). Der Dateiname ohne Nummer und
Endung ist der empfohlene Abfragename im Dataflow.

`00_fn_berlin_now.m` ist eine **Funktionsquery**: `() as datetimezone => let …`.
Beim Anlegen "Laden aktivieren" für diese Abfrage ausschalten – sie liefert
keine Zieltabelle, sondern wird von den anderen Abfragen im selben Dataflow
aufgerufen.

## Reihenfolge beim Anlegen

1. `00_fn_berlin_now.m` zuerst anlegen (Laden deaktivieren).
2. Die übrigen Abfragen des Ordners in beliebiger Reihenfolge – sie
   referenzieren `fn_berlin_now` nur namentlich, eine Ladereihenfolge ist
   nicht erforderlich.

## Ziele und Historisierung

Alle Abfragen verwenden die Aktualisierungsmethode **Ersetzen**. Wohin sie
schreiben, unterscheidet sich aber je nach Fachlichkeit:

| Dataflow | Ziel | Historisierung |
|---|---|---|
| `df_crm_ingest`, `df_map_unit_assignment` | `stg_*` | ja – `nb_05_snapshot.py` schreibt daraus die Tagespartition nach `bronze_*` |
| `df_sap_ingest` | `bronze_*` direkt | nein – `nb_05_snapshot.py` fasst diese Tabellen nicht an |

Der Unterschied ist bewusst. Bei CRM ist die **Bewegung** die eigentliche
Information: „Was hat sich seit dem letzten CRM-Call geändert?" lässt sich nur
beantworten, wenn jeder Tagesstand erhalten bleibt. SAP dagegen liefert einen
**Ist-Stand** – Betriebsstammdaten und die bereits gepflegten Perioden-Umsätze
aus `V_SAP_EXPORTS_cleansed`. Ein Tagessnapshot darüber würde dieselben
Buchungen täglich vervielfachen, ohne eine Frage zu beantworten, die nicht
schon über `fy_year`/`fy_period` beantwortbar wäre.

Die beiden Excel-Abfragen werden aus einem dritten Grund historisiert: sie
sind **manuelle Inputs in offizielle Budgetzahlen**. Ohne Snapshot lässt sich
nach der nächsten Pflegerunde nicht mehr feststellen, welcher Stand von
`Mapping_Planwerke.xlsx` bzw. `2026_04_29_Planung_unknown_ITY_Effekt.xlsx` in
einer bereits kommunizierten Zahl steckte – die Budgetrunde wäre nicht mehr
reproduzierbar.

Details und Begründung: `docs/06_deployment.md`, Schritt 1–2.
