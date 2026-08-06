"""Fabric User Data Function für die Kommentarerfassung im Flash-Bericht.

Wird vom Translytical Task Flow des Buttons "Kommentar erfassen" aufgerufen.
Die Parameter werk / fiscal_year / periode werden vom Button aus dem Berichtskontext
gefüllt, kategorie und kommentar aus den Eingabefeldern des Task Flows.

Anlegen: Fabric-Workspace > Neu > User Data Functions > diese Datei als function_app.py,
danach unter "Verwalten von Verbindungen" die Fabric-SQL-Datenbank mit dem Alias
"Flash_Writeback" verbinden und veröffentlichen.
"""

import fabric.functions as fn

udf = fn.UserDataFunctions()

# Erlaubte Kategorien - identisch zum Dropdown des Task Flows im Bericht.
KATEGORIEN = ("Abrechnung", "CoS", "Overhead", "Umsatz", "Sonstiges")

MAX_LAENGE = 2000


@udf.connection(argName="sql_db", alias="Flash_Writeback")
@udf.context(argName="kontext")
@udf.function()
def kommentar_speichern(
    sql_db: fn.FabricSqlConnection,
    kontext: fn.UserDataFunctionContext,
    werk: int,
    fiscal_year: int,
    periode: int,
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
    if not 1 <= periode <= 12:
        raise fn.UserThrownError("Die Periode muss zwischen 1 und 12 liegen.", {})
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
            (werk, fiscal_year, periode, text, kategorie, benutzer),
        )
        verbindung.commit()
        cursor.close()
    finally:
        verbindung.close()

    return "Kommentar gespeichert."


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
