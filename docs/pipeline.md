# Aktualisierungspipeline

Orchestrierung des täglichen Laufs. Definition:
`fabric/pipeline/pipeline-content.json` — die drei `PLATZHALTER_*`-GUIDs sind
vor dem ersten Lauf zu ersetzen.

## Ablauf

```
01 CRM Extrakt (Dataflow Gen2)
      │  Succeeded
      ▼
02 Snapshot laden und ableiten (Notebook)
      │  Succeeded
      ▼
03 Semantic Model aktualisieren (Web → Power BI REST)
```

| # | Aktivität | Inhalt | Timeout | Retry |
|---|---|---|---|---|
| 01 | Dataflow Gen2 | Vollextrakt → `stg_*` (Replace) | 2 h | 2 × / 5 min |
| 02 | Notebook | `02_load_snapshot.py` + `03_derived_tables.sql` | 1 h | 1 × / 2 min |
| 03 | Web-Aktivität | Refresh des Import-Modells | 1 h | 1 × / 2 min |

## Warum diese Struktur

**Alle Abhängigkeiten auf `Succeeded`, nicht auf `Completed`.** Das ist die
wichtigste Einstellung der ganzen Pipeline. Der Dataflow schreibt mit
*Replace*; schlägt er fehl, bleibt der Stand des Vortags in der
Staging-Tabelle stehen. Das Notebook würde ihn anstandslos verarbeiten — der
Load ist idempotent und schriebe einfach die Vortagspartition neu. Der Lauf
meldete Erfolg, es entstünde aber kein neuer Snapshot, und der Bericht zeigte
alte Zahlen als aktuell. Genau diese stille Variante ist gefährlicher als ein
harter Abbruch.

**Zusätzlich prüft das Notebook selbst.** `02_load_snapshot.py` vergleicht das
`snapshot_date` aus dem Staging gegen das heutige Datum in Berliner Zeit und
bricht bei Abweichung ab. Die Pipeline-Abhängigkeit allein würde reichen,
solange niemand das Notebook von Hand startet — die Prüfung deckt auch diesen
Fall ab. Für bewusste Nachladungen setzt man `allow_stale_snapshot = True`.

**02 und 03 in einem Notebook.** Die abgeleiteten Tabellen (`fct_*_current`,
`fct_*_changes`) sind ohne den Load bedeutungslos, und ein Zwischenzustand —
neuer Snapshot, aber alte Ableitungen — wäre schlechter als eine gröbere
Fehlermeldung. Da der gesamte Lauf idempotent ist, kostet ein Neustart nach
Fehler nichts. Wer feinere Fehlerisolierung im Monitoring will, kann die
beiden Zellen auf zwei Notebook-Aktivitäten aufteilen.

**Retries beim Dataflow höher.** Dataverse drosselt gelegentlich; zwei
Wiederholungen im Abstand von fünf Minuten fangen das ab, ohne dass jemand
eingreift. Beim Notebook ist ein Retry sinnvoll (transiente Spark-Startfehler),
mehr nicht — ein fachlicher Fehler wiederholt sich ohnehin.

## Zeitplan

Täglich, **05:00 Uhr, Zeitzone `(UTC+01:00) Amsterdam, Berlin, …`**.

Die Zeitzone im Trigger ausdrücklich auf Berlin stellen, nicht auf UTC oder
UK. Sonst verschiebt sich die Startzeit zweimal im Jahr mit der Umstellung —
und ein Lauf, der dadurch vor Mitternacht rutscht, träfe genau die
Datumsgrenze, die in `fn_berlin_now` mühsam abgesichert wurde.

Der Lauf ist unkritisch gegenüber Doppelstarts: Ein manueller Refresh neben
dem Zeitplan schreibt dieselbe Tagespartition neu, statt sie zu verdoppeln.

## Semantic-Model-Refresh

Die Web-Aktivität ruft die Power-BI-REST-API:

```
POST https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets/{datasetId}/refreshes
Body: { "type": "Full", "commitMode": "transactional", "notifyOption": "MailOnFailure" }
Auth: MSI, resource https://analysis.windows.net/powerbi/api
```

Voraussetzung: Die Workspace-Identität braucht auf dem Semantic Model
mindestens Beitragsrechte. Ist sie nicht eingerichtet, geht auch ein
Dienstprinzipal — dann muss im Mandanten *Dienstprinzipale dürfen
Power-BI-APIs verwenden* aktiv sein.

Falls im Workspace die native Aktivität **Semantikmodellaktualisierung**
verfügbar ist, ist sie der bequemere Weg: gleiche Wirkung, aber ohne
API-URL und ohne eigene Berechtigungsvergabe. Die Web-Aktivität steht hier,
weil sie unabhängig von der Verfügbarkeit dieser Aktivität funktioniert.

Der Refresh ist nötig, weil das Modell im **Import**-Modus läuft (siehe
`docs/architecture.md`, Abschnitt *Import statt Direct Lake*). Bei einem
späteren Wechsel auf Direct Lake entfällt Aktivität 03 ersatzlos.

## Fehlerbenachrichtigung

Der Pipeline eine Aktivität auf dem Fehlerpfad (`Failed`) von 01 und 02
anhängen — Outlook oder Teams. Ohne die fällt ein Ausfall erst auf, wenn
jemand den Bericht anschaut und sich über den Wert von `Datenstand` wundert.

Das Measure `Datenstand` im Bericht zeigt `MAX(fct_opportunity[snapshot_date])`
und ist die zweite Sicherung: Steht dort nicht das heutige Datum, ist die
Strecke stehen geblieben.

## Einmalig vor dem ersten Lauf

1. `01_create_tables.sql` im Notebook ausführen (nur `fct_*`/`map_*`;
   die `stg_*` legt der Dataflow selbst an).
2. Dataflow Gen2 mit den vier Queries anlegen, `fn_berlin_now` auf
   *Laden deaktivieren*.
3. Pipeline anlegen, GUIDs eintragen, Zeitplan setzen.
4. Pipeline einmal von Hand starten und Aktivität 02 im Monitoring prüfen —
   dort meldet sich der Grain-Check, falls der Dataflow ein abweichendes
   Schema geschrieben hat.
5. Im PBIP `WarehouseName` setzen und einmal refreshen.
