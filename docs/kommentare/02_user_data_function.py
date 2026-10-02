"""Fabric User Data Function für die Kommentarerfassung im Flash-Bericht.

Wird vom Button "Kommentar speichern" (Seite Kommentare) aufgerufen. Die vier Parameter kommen
direkt aus den Eingabe-Slicern der Seite:

    werk       Slicer "Unit"       -> Text wie "0127 - Musterbetrieb"
    periode    Slicer "Periode"    -> Text wie "P09 · Jun 26"
    kategorie  Slicer "Kategorie"  -> Text, siehe KATEGORIEN
    kommentar  Texteingabe         -> Freitext

Werksnummer, SAP-Periode und Geschäftsjahr werden aus den Slicer-Texten abgeleitet, damit der Bericht
keine zusätzlichen technischen Felder braucht.

Anlegen: Fabric-Workspace > Neu > User Data Functions > diese Datei als function_app.py,
danach unter "Verwalten von Verbindungen" die Fabric-SQL-Datenbank mit dem Alias
"Flash_Writeback" verbinden und veröffentlichen.
"""

import re

import fabric.functions as fn

udf = fn.UserDataFunctions()

# Erlaubte Kategorien - identisch zur Tabelle p_Kategorie im semantischen Modell.
KATEGORIEN = ("Abrechnung", "CoS", "Overhead", "Umsatz", "Sonstiges")

MAX_LAENGE = 2000


def _werk_aus_text(text: str) -> int:
    """'0127 - Musterbetrieb' oder '127' -> 127."""
    treffer = re.match(r"\s*(\d+)", text or "")
    if not treffer:
        raise fn.UserThrownError("Bitte zuerst eine Unit auswählen.", {})
    return int(treffer.group(1))


def _periode_aus_text(text: str) -> tuple[int, int]:
    """'P09 · Jun 26' -> (Geschäftsjahr 2025, Periode 9).

    Periode 1-3 = Oktober bis Dezember des Geschäftsjahres, Periode 4-12 = Januar bis September des
    Folgejahres. Das Kalenderjahr steht als zweistellige Zahl am Ende des Labels.
    """
    treffer = re.match(r"\s*P(\d{1,2}).*?(\d{2})\s*$", text or "")
    if not treffer:
        raise fn.UserThrownError("Bitte zuerst eine Periode auswählen.", {})
    periode, jahr2 = int(treffer.group(1)), int(treffer.group(2))
    if not 1 <= periode <= 12:
        raise fn.UserThrownError("Die Periode muss zwischen 1 und 12 liegen.", {})
    kalenderjahr = 2000 + jahr2
    geschaeftsjahr = kalenderjahr if periode <= 3 else kalenderjahr - 1
    return geschaeftsjahr, periode


@udf.connection(argName="sql_db", alias="Flash_Writeback")
@udf.context(argName="kontext")
@udf.function()
def kommentar_speichern(
    sql_db: fn.FabricSqlConnection,
    kontext: fn.UserDataFunctionContext,
    werk: str,
    periode: str,
    kategorie: str,
    kommentar: str,
) -> str:
    """Legt einen Kommentar zu genau einer Unit und Periode an."""

    text = (kommentar or "").strip()
    if not text:
        raise fn.UserThrownError("Bitte einen Kommentartext eingeben.", {})
    if len(text) > MAX_LAENGE:
        raise fn.UserThrownError(
            f"Der Kommentar ist zu lang ({len(text)} Zeichen, erlaubt sind {MAX_LAENGE}).", {}
        )

    werk_nr = _werk_aus_text(werk)
    geschaeftsjahr, periode_nr = _periode_aus_text(periode)
    if kategorie not in KATEGORIEN:
        kategorie = "Sonstiges"

    # Der schreibende Benutzer kommt aus dem Aufrufkontext und wird bewusst NICHT
    # als Parameter übergeben - sonst könnte er im Bericht überschrieben werden.
    benutzer = kontext.executing_user.get("PreferredUsername") or "unbekannt"

    verbindung = sql_db.connect()
    try:
        cursor = verbindung.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.Flash_Kommentare (Werk, Fiscal_Year, Periode, Kommentar, Kategorie, Erfasst_von)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (werk_nr, geschaeftsjahr, periode_nr, text, kategorie, benutzer),
        )
        verbindung.commit()
        cursor.close()
    finally:
        verbindung.close()

    return f"Kommentar zu Werk {werk_nr}, FY{geschaeftsjahr} P{periode_nr:02d} gespeichert."


@udf.connection(argName="sql_db", alias="Flash_Writeback")
@udf.context(argName="kontext")
@udf.function()
def kommentar_loeschen(
    sql_db: fn.FabricSqlConnection,
    kontext: fn.UserDataFunctionContext,
    kommentar_id: int,
) -> str:
    """Blendet einen Kommentar aus (Soft Delete) - die Zeile bleibt für die Nachvollziehbarkeit stehen.

    Nur der Verfasser darf seinen eigenen Kommentar zurücknehmen; die Prüfung passiert
    in der WHERE-Klausel, damit sie nicht am Bericht vorbei umgangen werden kann.
    """

    benutzer = kontext.executing_user.get("PreferredUsername") or "unbekannt"

    verbindung = sql_db.connect()
    try:
        cursor = verbindung.cursor()
        cursor.execute(
            "UPDATE dbo.Flash_Kommentare SET Ist_Aktiv = 0 WHERE Kommentar_ID = ? AND Erfasst_von = ?",
            (kommentar_id, benutzer),
        )
        betroffen = cursor.rowcount
        verbindung.commit()
        cursor.close()
    finally:
        verbindung.close()

    if betroffen == 0:
        raise fn.UserThrownError("Kommentar nicht gefunden oder von einem anderen Benutzer erfasst.", {})
    return "Kommentar entfernt."
