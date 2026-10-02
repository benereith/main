# Kommentierung im Flash-Bericht (Translytical Task Flow)

Der Bericht liest Kommentare per DirectQuery aus einer Fabric-SQL-Datenbank und schreibt sie
über eine User Data Function zurück. Dadurch ist ein neuer Kommentar sofort sichtbar, ohne dass
das semantische Modell aktualisiert werden muss.

## Was im Repository bereits fertig ist

| Baustein | Ort | Status |
| --- | --- | --- |
| Tabelle `Kommentare` (DirectQuery) | `Flash/Flash_Basis.SemanticModel/definition/tables/Kommentare.tmdl` | fertig |
| Beziehung `Kommentare[Status_Key]` → `Dim_UnitStatus[Status_Key]` | `definition/relationships.tmdl` | fertig |
| Steuertabellen `p_Kategorie`, `p_Eingabe` | `definition/tables/` | fertig |
| Seite **Kommentare** mit Eingabe-Slicern, Button und Kommentarliste | Bericht, Seite *Kommentare* | fertig, Button braucht zwei IDs |
| Kommentarliste auf *Flash* und *Unit-Detail* | Bericht | fertig |
| SQL-Tabelle | `01_tabelle.sql` | auszuführen |
| User Data Function | `02_user_data_function.py` | zu veröffentlichen |

Der Button **Kommentar speichern** ist bereits mit der Funktion `kommentar_speichern` und den vier
Eingabe-Slicern der Seite verdrahtet. Offen sind nur die beiden IDs der veröffentlichten Funktion
(Workspace und User-Data-Functions-Item). Bis dahin bleibt der Button deaktiviert.

## Einrichtung

1. **Fabric-SQL-Datenbank anlegen** (Workspace → Neu → SQL-Datenbank), z. B. `Flash_Writeback`.
2. **`01_tabelle.sql` ausführen.** Legt `dbo.Flash_Kommentare` samt berechnetem, persistiertem
   `Status_Key` an. Der Schlüssel (`Werk * 1.000.000 + Geschäftsjahr * 100 + Periode`) muss dem im
   Modell entsprechen.
3. **`02_user_data_function.py` veröffentlichen** (Workspace → Neu → User Data Functions) und unter
   *Verwalten von Verbindungen* die SQL-Datenbank mit dem Alias `Flash_Writeback` verbinden.
4. **Modellparameter setzen** (Power-Query-Editor, Gruppe *Parameter*):
   - `Kommentar_SQL_Endpoint` → SQL-Verbindungszeichenfolge der Fabric-Datenbank
   - `Kommentar_Datenbank` → `Flash_Writeback`
5. **Button verbinden.** In Power BI Desktop den Button *Kommentar speichern* markieren →
   *Format* → *Aktion* → Typ **Datenfunktion** → Workspace und Funktion `kommentar_speichern`
   neu auswählen. Desktop trägt dabei die IDs und die Funktionssignatur ein. Alternativ die beiden
   Platzhalter-GUIDs (`00000000-…`) in
   `Flash_Basis.Report/definition/pages/<Seite Kommentare>/visuals/<Button>/visual.json` ersetzen.
6. **Parameterzuordnung prüfen** (sollte bereits stehen):

   | Parameter der Funktion | Eingabe auf der Seite |
   | --- | --- |
   | `werk` | Slicer *1 Unit* (`Dim_Unit[Werk - Bezeichnung]`) |
   | `periode` | Slicer *2 Periode* (`Dim_Datum[Periode]`) |
   | `kategorie` | Slicer *3 Kategorie* (`p_Kategorie[Kategorie]`) |
   | `kommentar` | Texteingabe *4 Kommentar* (`p_Eingabe[Kommentartext]`) |

7. **Berechtigungen:** Die Benutzer brauchen Ausführungsrechte auf der User Data Function.
   Direkte Schreibrechte auf der SQL-Datenbank sind nicht nötig und auch nicht gewünscht –
   der Benutzername wird von der Funktion aus dem Aufrufkontext gesetzt, nicht vom Bericht.

Die Funktion leitet Werksnummer, Periode und Geschäftsjahr aus den Slicer-Texten ab
(`'0127 - Musterbetrieb'`, `'P09 · Jun 26'`). Sie hat deshalb nur Text-Parameter, und der Bericht
braucht keine technischen Zusatzfelder.

## Bewusste Entscheidungen

- **Soft Delete statt DELETE.** `Ist_Aktiv = 0` statt Löschen; die M-Abfrage der Tabelle
  `Kommentare` blendet inaktive Zeilen aus. Historie bleibt nachvollziehbar.
- **`Erfasst_von` kommt aus dem Kontext, nicht aus dem Bericht.** Ein Berichtsparameter ließe
  sich manipulieren.
- **Kommentare hängen an `Dim_UnitStatus`** (Werk × Periode), wie die Faktentabelle. Unit-, Monats-
  und Statusfilter wirken damit automatisch auf die Kommentarliste.
- **Eingabefeld über eine entkoppelte Tabelle** (`p_Eingabe`): Der Text-Slicer braucht ein Feld,
  soll aber keine anderen Visuals filtern.

## Voraussetzung und Grenzen

Translytical Task Flows brauchen eine Fabric-Kapazität und aktivierte User Data Functions.
Ohne Fabric-Kapazität funktioniert die Anzeige der Kommentare (DirectQuery) nicht, solange die
Parameter auf den Platzhalter zeigen; die übrigen Seiten sind davon nicht betroffen.

Nicht in Desktop getestet: Ob der Text-Slicer als Eingabefeld und die Slicer-Parameterbindung wie
beschrieben zusammenspielen, lässt sich nur mit der echten Funktion prüfen (Schritt 5).
