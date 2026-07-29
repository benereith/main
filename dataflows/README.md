# Dataflows

Zwei Dataflows Gen2, kein Monolith. Jede Abfrage steht einzeln in einer
eigenen Datei, damit sie sich per Copy-Paste in den Power-Query-Editor
übertragen lässt, ohne dass Kommentarblöcke oder ein `let…in` erst entpackt
werden müssen.

## Warum zwei Dataflows und nicht einer

Die Faustregel: Abfragen, die dieselbe **Quelle** und denselben **Fehlerfall**
teilen, gehören in einen Dataflow. Abfragen mit anderer Quelle gehören in
einen eigenen.

| Dataflow | Abfragen | Quelle | Warum zusammen bzw. getrennt |
|---|---|---|---|
| `df_crm_ingest` | `stg_crm_opportunity`, `stg_crm_contract`, `stg_crm_account`, `stg_crm_territory` | Dataverse (`cpgplc.crm.dynamics.com`) | Gleiche Verbindung, gleicher Gateway, gleicher Zeitplan. Ein CRM-Verbindungsproblem betrifft ohnehin alle vier gleichzeitig – ein gemeinsamer Fehlschlag ist ehrlicher als vier separate, die zufällig gleichzeitig rot werden |
| `df_map_unit_assignment` | `stg_map_unit_assignment` | SharePoint / Excel | Andere Quelle, andere Fehlerdomäne. Ein SharePoint-Hänger soll den CRM-Ingest nicht blockieren, und ein CRM-Verbindungsabbruch soll nicht verhindern, dass die gepflegte Mapping-Tabelle geladen wird |

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

Alle Ziele sind Staging-Tabellen (`stg_*`) mit Aktualisierungsmethode
**Ersetzen**. Die Historisierung nach `bronze_*` übernimmt
`lakehouse/notebooks/nb_05_snapshot.py` – Details und Begründung:
`docs/06_deployment.md`, Schritt 1–2.
