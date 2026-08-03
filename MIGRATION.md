# Flash Dataflow – Umbau auf Lakehouse

Der überarbeitete Dataflow liegt in [`flash_dataflow.pq`](flash_dataflow.pq).

## Vor dem ersten Refresh anpassen

| Parameter | Bedeutung |
|---|---|
| `P_LakehouseId` | GUID des Lakehouse (Platzhalter im Code) |
| `P_WorkspaceId` | Workspace des Lakehouse (aktuell derselbe wie beim SAP-Dataflow) |
| `P_Tabelle_RGF` / `P_Tabelle_RTD` | Namen der Delta-Tabellen |
| `Upload_Jahr` | neu, für die Dateiauswahl im D6-Ordner |
| `P_ZeitversatzStunden` | ersetzt das feste `+2h` |

Außerdem in `BEx_Abruf_RGF` / `BEx_Abruf_RTD` die Quellspaltennamen
(`werk`, `kostenart`, `budget`, `fc_version`, `act`) auf das echte
Lakehouse-Schema setzen. Liegen RGF und RTD in **einer** Tabelle mit
Versionsspalte, ist die Alternativvariante im Code kommentiert.

## Zu löschende Altabfragen

`Beispieldatei`, `Beispieldatei (2)`, `Beispieldatei (3)`,
`Beispieldatei … transformieren` (alle drei), `Parameter`, `Parameter (2)`,
`Datei transformieren`, `Datei transformieren (2)`, `Datei transformieren (3)`.

Ersetzt durch: `fn_ExcelSheet1`, `fn_LakehouseTabelle`, `fn_D6Ordner`, `fn_D6Datei`.

## Gefundene Fehler (mitkorrigiert)

1. **FC-Kombination verlor Werte.** In `BEx_Abruf` war
   `FC Version RGF = [FC Version RGF] + [FC Version RTD]` nach einem
   LeftOuter-Join. Werke ohne RTD-Zeile bekamen `Zahl + null = null`, was der
   spätere `ReplaceValue(null, 0)` auf **0** setzte – der RGF-Wert war weg.
   Jetzt: `Table.Combine` + `Table.Group`, fehlende Gegenstücke zählen als 0.
2. **Hart codierter Dateiname.** `D6_LM` griff auf
   `20260605_Input_D6_2.XLSX` zu; ab dem Folgemonat wären das Vormonatsdaten
   vom falschen Monat bzw. ein Fehler. Jetzt über `fn_D6Datei` aus
   `Upload_Monat`/`Upload_Jahr` abgeleitet (inkl. Jahreswechsel).
3. **`Replacer.ReplaceText` auf `Kostenart`** ersetzte Teilstrings statt
   ganzer Werte. Jetzt exaktes Mapping über einen Record-Lookup.
4. **Leerprüfung `= ""`** in `D6_LM` griff nicht, wenn Excel `null` liefert.
   Jetzt `([Abg.] ?? "") = ""`.
5. **`Table.SelectRows(..., each [Attributes]?[Hidden]? <> true)`** stand in
   `Beispieldatei` *nach* dem Entfernen der Spalte `Attributes` und in
   `Beispieldatei (2)` doppelt.

## Performance

- Unpivot → Pivot in `BEx_Abruf` durch zweimal `Table.Group` ersetzt.
- `FillDown`/`FillUp` des Timestamps über die ganze Tabelle durch den Skalar
  `D6_Timestamp` ersetzt.
- Spaltenauswahl und Filter jeweils so früh wie möglich, damit sie im
  Lakehouse gefaltet werden.
- `Adj Rev` und `Adj UPC` in einem Durchlauf statt zweier identischer
  Bedingungsketten.
- `Input_D6` lädt die Zieldatei direkt statt über
  `AddColumn` + `ExpandTableColumn`.
- SharePoint-Navigationspfad einmal statt sechsmal.

## Staging-Einstellungen

Nur `Flash_Export` als Ausgabe aktivieren. Staging an bei `BEx_Abruf_RGF`,
`BEx_Abruf_RTD`, `SAP_Stammdaten`; aus bei allen Funktions- und
Parameterabfragen.
