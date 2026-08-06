# Kommentierung im Flash-Bericht (Translytical Task Flow)

Der Bericht liest Kommentare per DirectQuery aus einer Fabric-SQL-Datenbank und schreibt sie
über eine User Data Function zurück. Dadurch ist ein neuer Kommentar sofort sichtbar, ohne dass
das semantische Modell aktualisiert werden muss.

## Was in diesem Repository bereits fertig ist

| Baustein | Ort | Status |
| --- | --- | --- |
| Tabelle `Kommentare` (DirectQuery) | `Flash/Flash_Basis.SemanticModel/definition/tables/Kommentare.tmdl` | fertig |
| Beziehungen zu `sap_master_data_unit` und `DIM_DATE` | `definition/relationships.tmdl` | fertig |
| Measures `Kommentar Anzahl`, `Kommentartext`, `Letzter Kommentar am` | `tables/0_Measuretabelle.tmdl` | fertig |
| Kommentar-Panel auf der Seite *Flash* | Visual `5e1fa8c4302db76915ca` | fertig |
| Button „Kommentar erfassen" | Visual `6f2c09b7541ae83d206f` | Button vorhanden, **Datenaktion muss zugewiesen werden** |
| SQL-Tabelle | `01_tabelle.sql` | auszuführen |
| User Data Function | `02_user_data_function.py` | zu veröffentlichen |

Die Zuweisung der Datenaktion an den Button ist der einzige Schritt, der sich nicht sinnvoll im
PBIP-Format vorab schreiben lässt – sie referenziert die konkrete Workspace- und Funktions-ID der
veröffentlichten User Data Function und wird in Power BI Desktop in drei Klicks gesetzt.

## Einrichtung

1. **Fabric-SQL-Datenbank anlegen** (Workspace → Neu → SQL-Datenbank), z. B. `Flash_Writeback`.
2. **`01_tabelle.sql` ausführen.** Legt `dbo.Flash_Kommentare` inkl. der berechneten Spalten
   `Status_Key` und `Datum` an. Beide sind persistiert, damit DirectQuery sauber faltet.
3. **`02_user_data_function.py` veröffentlichen** (Workspace → Neu → User Data Functions).
   Danach unter *Verwalten von Verbindungen* die SQL-Datenbank mit dem Alias `Flash_Writeback`
   verbinden. Die Funktionsnamen sind `kommentar_speichern` und `kommentar_loeschen`.
4. **Modellparameter setzen** – in `Flash/Flash_Basis.SemanticModel/definition/expressions.tmdl`
   oder komfortabler im Power-Query-Editor:
   - `Kommentar_SQL_Endpoint` → SQL-Verbindungszeichenfolge der Fabric-Datenbank
   - `Kommentar_Datenbank` → `Flash_Writeback`
5. **Button verdrahten:** Button *Kommentar erfassen* markieren → *Format* → *Aktion* →
   Typ **Datenfunktion** → Workspace und `kommentar_speichern` wählen. Parameter zuordnen:

   | Parameter der Funktion | Bindung im Bericht |
   | --- | --- |
   | `werk` | Feld `sap_master_data_unit[betrieb]` (Wert des ausgewählten Werks) |
   | `fiscal_year` | Feld `Unit_Status[Fiscal_Year]` |
   | `periode` | Feld `Unit_Status[Periode]` |
   | `kategorie` | Textfeld-/Dropdown-Slicer im Bericht |
   | `kommentar` | Texteingabe-Slicer im Bericht |

   Für `kategorie` und `kommentar` je einen **Texteingabe-Slicer** auf die Seite legen; die
   erlaubten Kategorien stehen in `02_user_data_function.py` in `KATEGORIEN`.
6. **Berechtigungen:** Die Benutzer brauchen Ausführungsrechte auf der User Data Function.
   Direkte Schreibrechte auf der SQL-Datenbank sind nicht nötig und auch nicht gewünscht –
   der Benutzername wird von der Funktion aus dem Aufrufkontext gesetzt, nicht vom Bericht.

## Bewusste Entscheidungen

- **Soft Delete statt DELETE.** `Ist_Aktiv = 0` statt Löschen; die M-Abfrage der Tabelle
  `Kommentare` blendet inaktive Zeilen aus. Historie bleibt nachvollziehbar.
- **`Erfasst_von` kommt aus dem Kontext, nicht aus dem Bericht.** Ein Berichtsparameter ließe
  sich manipulieren.
- **Kommentare hängen an `sap_master_data_unit` und `DIM_DATE`, nicht an `Unit_Status`.**
  Sie verhalten sich damit wie eine zweite Faktentabelle: Unit-Slicer und Monats-Slicer filtern
  sie automatisch mit. Über `Unit_Status` würde nur der Statusfilter greifen.

## Voraussetzung

Translytical Task Flows brauchen eine Fabric-Kapazität und aktivierte User Data Functions.
Ohne Fabric-Kapazität funktioniert die Anzeige der Kommentare (DirectQuery) zwar weiterhin,
das Schreiben aus dem Bericht heraus jedoch nicht.
