#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator für die PBIR-Definition des Berichts "Net New ITY Cockpit".

WARUM EIN GENERATOR
Die PBIR-Struktur besteht aus einer JSON-Datei je Visualisierung, verteilt über
Verzeichnisse mit zufälligen Namen. Von Hand gepflegt ist sie weder lesbar noch
überprüfbar: eine Farbe an fünf Stellen zu ändern heißt, fünf Dateien zu suchen.

Hier steht das Layout jeder Seite als kompakte Deklaration weiter unten in
PAGES. Der Generator erzeugt daraus die vollständige Ordnerstruktur. Damit ist
der Bericht diffbar, das Designsystem an genau einer Stelle definiert, und eine
neue Seite kostet zehn Zeilen statt zehn Dateien.

Aufruf:
    python3 tools/build_report.py

Ergebnis:
    powerbi/Net New ITY Cockpit.Report/definition/...
"""

import hashlib
import json
import os
import shutil

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "powerbi", "Net New ITY Cockpit.Report")
DEFINITION = os.path.join(REPORT, "definition")
PAGES_DIR = os.path.join(DEFINITION, "pages")

# ---------------------------------------------------------------------------
# Designsystem
# ---------------------------------------------------------------------------
# Leinwand 1280 x 720 (16:9). Ein 8-px-Raster hält alle Kanten in einer Flucht;
# unausgerichtete Kanten sind die häufigste Form von visuellem Rauschen.
CANVAS_W, CANVAS_H = 1280, 720
GRID = 8
MARGIN = 16
NAV_W = 168          # linke Navigationsspalte
HEADER_H = 76        # Kopfbereich mit Aussage-Kachel
FILTER_H = 56        # Filterzeile
FOOTER_H = 24        # Fußzeile mit Datenstand

CONTENT_X = NAV_W + MARGIN
CONTENT_W = CANVAS_W - CONTENT_X - MARGIN

# Farbrollen. Identisch zur Datei
# StaticResources/SharedResources/BaseThemes/NetNewITY.json.
C = {
    "nb_won": "#184F95",
    "nb_expected": "#3987E5",
    "nb_pipeline": "#86B6EF",
    "lb_lost": "#A02222",
    "lb_expected": "#E34948",
    "lb_atrisk": "#EB9998",
    "referenz": "#898781",
    "tinte": "#0B0B0B",
    "tinte_2": "#52514E",
    "linie": "#E1E0D9",
    "flaeche": "#FFFFFF",
    "seite": "#F9F9F7",
    "gut": "#0CA30C",
    "warn": "#FAB219",
    "schlecht": "#D03B3B",
}

MEASURE_TABLE = "_Kennzahlen"

SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
SCHEMA_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------
def _id(*teile) -> str:
    """Stabiler 20-stelliger Bezeichner. Stabil heißt: gleicher Input erzeugt
    denselben Ordnernamen, damit ein erneuter Lauf keine Scheinänderungen im
    Git-Diff produziert."""
    return hashlib.sha1("|".join(str(t) for t in teile).encode()).hexdigest()[:20]


def lit(value) -> dict:
    """Literal-Ausdruck im PBIR-Format."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, int):
        v = f"{value}L"
    elif isinstance(value, float):
        v = f"{value}D"
    else:
        v = f"'{value}'"
    return {"expr": {"Literal": {"Value": v}}}


def farbe(hexwert: str) -> dict:
    return {"solid": {"color": lit(hexwert)}}


def props(**kwargs) -> list:
    return [{"properties": dict(kwargs)}]


def measure(name: str, tabelle: str = MEASURE_TABLE) -> dict:
    """Projektion einer Kennzahl."""
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": tabelle}}, "Property": name}},
        "queryRef": f"{tabelle}.{name}",
        "nativeQueryRef": name,
    }


def spalte(tabelle: str, name: str, aktiv: bool = True) -> dict:
    """Projektion einer Spalte."""
    p = {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": tabelle}}, "Property": name}},
        "queryRef": f"{tabelle}.{name}",
        "nativeQueryRef": name,
    }
    if aktiv:
        p["active"] = True
    return p


def visual(
    typ,
    x,
    y,
    w,
    h,
    *,
    roles=None,
    titel=None,
    untertitel=None,
    objects=None,
    z=None,
    sort=None,
    filters=None,
    extra=None,
):
    """Erzeugt einen Visualisierungscontainer.

    roles: dict Rollenname -> Liste von Projektionen, z. B.
           {"Category": [spalte(...)], "Y": [measure(...)]}
    """
    z = z if z is not None else int(y) * 10 + int(x) // 10
    container_objects = {}
    if titel is not None:
        container_objects["title"] = props(
            show=lit(True), text=lit(titel), titleWrap=lit(True),
            fontColor=farbe(C["tinte"]), alignment=lit("left"),
        )
    else:
        container_objects["title"] = props(show=lit(False))
    if untertitel is not None:
        container_objects["subTitle"] = props(
            show=lit(True), text=lit(untertitel), titleWrap=lit(True),
            fontColor=farbe(C["tinte_2"]), alignment=lit("left"),
        )

    v = {"visualType": typ}
    if roles:
        v["query"] = {"queryState": {r: {"projections": p} for r, p in roles.items()}}
        if sort:
            v["query"]["sortDefinition"] = sort
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = container_objects
    v["drillFilterOtherVisuals"] = True
    if extra:
        v.update(extra)

    node = {
        "$schema": SCHEMA_VISUAL,
        "name": None,  # wird beim Schreiben gesetzt
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": v,
    }
    if filters:
        node["filterConfig"] = {"filters": filters}
    return node


# --- wiederkehrende Bausteine ----------------------------------------------
def nav(seiten_reihenfolge=True):
    """Linke Navigationsspalte. Eine feste Position auf jeder Seite - der Leser
    muss die Navigation nicht suchen."""
    return visual(
        "pageNavigator",
        MARGIN,
        MARGIN,
        NAV_W - MARGIN,
        CANVAS_H - 2 * MARGIN,
        z=9000,
        objects={
            "shapeCustomRectangle": props(
                fillColor=farbe(C["flaeche"]),
                fillTransparency=lit(0),
            ),
            "text": props(
                fontColor=farbe(C["tinte_2"]),
                fontSize=lit(10.0),
                horizontalAlignment=lit("left"),
            ),
            "selectedState": props(
                fillColor=farbe(C["nb_won"]),
                fontColor=farbe("#FFFFFF"),
            ),
            "grid": props(
                layout=lit("Vertical"),
                padding=lit(4),
            ),
        },
    )


def kopf(aussage_measure="Aussage Net New", zusatz_measure="Aussage Sicherheit"):
    """Kopfbereich: die Kernaussage als Text, nicht als Zahl.

    Storytelling with Data, Kapitel 5: Der Titel ist der wichtigste Text auf
    einer Seite. Er benennt die Botschaft. Ein Titel wie 'Net New ITY nach
    Periode' beschreibt nur die Achsen; hier steht stattdessen eine Kennzahl,
    die Richtung und Abstand zum Ziel in Worte fasst und sich mit dem Filter
    mitändert.
    """
    return [
        visual(
            "cardVisual",
            CONTENT_X,
            MARGIN,
            CONTENT_W,
            HEADER_H,
            roles={"Data": [measure(aussage_measure)]},
            z=8000,
            objects={
                "callout": props(
                    show=lit(True), fontSize=lit(19.0),
                    fontFamily=lit("Segoe UI Semibold"),
                    color=farbe(C["tinte"]), horizontalAlignment=lit("left"),
                ),
                "label": props(show=lit(False)),
                "background": props(show=lit(True), color=farbe(C["flaeche"])),
                "border": props(show=lit(False)),
            },
        )
    ]


def fusszeile():
    """Datenstand und Datenqualität - gehört auf jede Seite, damit ein
    exportiertes Bild seinen eigenen Stichtag mitführt."""
    return visual(
        "cardVisual",
        CONTENT_X,
        CANVAS_H - MARGIN - FOOTER_H,
        CONTENT_W,
        FOOTER_H,
        roles={"Data": [measure("Stand der Daten")]},
        z=8100,
        objects={
            "callout": props(
                show=lit(True), fontSize=lit(9.0), color=farbe(C["referenz"]),
                horizontalAlignment=lit("left"),
            ),
            "label": props(show=lit(False)),
            "background": props(show=lit(False)),
            "border": props(show=lit(False)),
        },
    )


def kpi(x, y, w, h, measures, titel=None, untertitel=None):
    """Kennzahlenzeile. Mehrere Kennzahlen in einer Kachelreihe statt in einem
    Balkendiagramm - eine Handvoll Kopfzahlen ist keine Verteilung und braucht
    keine Achse."""
    return visual(
        "cardVisual", x, y, w, h,
        roles={"Data": [measure(m) for m in measures]},
        titel=titel, untertitel=untertitel,
        objects={
            "callout": props(show=lit(True), fontSize=lit(22.0), color=farbe(C["tinte"])),
            "label": props(show=lit(True), fontSize=lit(9.0), color=farbe(C["tinte_2"])),
        },
    )


def slicer(x, y, w, h, tabelle, feld, titel, modus="Dropdown", syncgruppe=None):
    v = visual(
        "slicer", x, y, w, h,
        roles={"Values": [spalte(tabelle, feld)]},
        titel=titel,
        objects={
            "data": props(mode=lit(modus)),
            "header": props(show=lit(False)),
            "selection": props(selectAllCheckboxEnabled=lit(True), singleSelect=lit(False)),
        },
    )
    if syncgruppe:
        v["visual"]["syncGroup"] = {
            "groupName": syncgruppe, "fieldChanges": False, "filterChanges": True
        }
    return v


def filter_measure_gleich(tabelle, feld, werte):
    """Kategorialer Filter auf eine Spalte."""
    return {
        "name": _id(tabelle, feld, *werte),
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": tabelle}}, "Property": feld}},
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": tabelle, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": feld}}
                            ],
                            "Values": [[{"Literal": {"Value": f"'{w}'"}}] for w in werte],
                        }
                    }
                }
            ],
        },
    }


def sortierung(name, tabelle=MEASURE_TABLE, richtung="Descending", ist_measure=True):
    feld = (
        {"Measure": {"Expression": {"SourceRef": {"Entity": tabelle}}, "Property": name}}
        if ist_measure
        else {"Column": {"Expression": {"SourceRef": {"Entity": tabelle}}, "Property": name}}
    )
    return {"sort": [{"field": feld, "direction": richtung}], "isDefaultSort": True}


# ===========================================================================
# SEITENDEFINITIONEN
# ===========================================================================
# Reihenfolge folgt der Lesereihenfolge eines CRM-Calls:
#   Was ist die Lage?  ->  Woraus setzt sie sich zusammen?  ->  Wie entwickelt
#   sie sich?  ->  Was wäre wenn?  ->  Welche Vorgänge konkret?  ->  Was hat
#   sich seit dem letzten Mal geändert?  ->  Stimmen die Daten?
# ---------------------------------------------------------------------------

INHALT_Y = MARGIN + HEADER_H + 8


def seite_cockpit():
    y = INHALT_Y
    vis = kopf()

    # Kennzahlenzeile
    vis.append(
        kpi(
            CONTENT_X, y, CONTENT_W, 96,
            ["Net New ITY (Szenario)", "New Business ITY", "Lost Business ITY",
             "Sicherungsgrad", "Δ CRM zu Budget"],
        )
    )
    y += 96 + 8

    # Hauptgrafik: Verlauf. Eine Linie trägt die Aussage, die zweite ist
    # Referenz. Betonungsform statt kategorialer Palette.
    h_haupt = 264
    vis.append(
        visual(
            "lineChart",
            CONTENT_X, y, int(CONTENT_W * 0.62), h_haupt,
            roles={
                "Category": [spalte("DIM Datum", "Periode Label")],
                "Y": [measure("Net New ITY (Szenario)"), measure("Unknown ITY Budget")],
            },
            titel="Monatsverlauf gegen Budget",
            untertitel="Blau: CRM-Approximation · Grau: budgetierter unknown-ITY-Effekt",
            objects={
                "labels": props(show=lit(False)),
                "legend": props(show=lit(True), position=lit("TopLeft"), showTitle=lit(False)),
                "categoryAxis": props(
                    show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(False),
                    labelColor=farbe(C["tinte_2"]), fontSize=lit(9.0),
                ),
                "valueAxis": props(
                    show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(True),
                    gridlineColor=farbe(C["linie"]), labelColor=farbe(C["referenz"]),
                    fontSize=lit(9.0), labelDisplayUnits=lit(1000000.0),
                ),
                "dataPoint": [
                    {"properties": {"fill": farbe(C["nb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Net New ITY (Szenario)"}},
                    {"properties": {"fill": farbe(C["referenz"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Unknown ITY Budget"}},
                ],
            },
        )
    )

    # Zerlegung nach Sicherheitsgrad, gestapelt. Beantwortet die Frage
    # "wie belastbar ist die Linie links?" direkt daneben.
    vis.append(
        visual(
            "stackedColumnChart",
            CONTENT_X + int(CONTENT_W * 0.62) + 8, y,
            CONTENT_W - int(CONTENT_W * 0.62) - 8, h_haupt,
            roles={
                "Category": [spalte("DIM Status", "Geschäftsart")],
                "Series": [spalte("DIM Status", "Status")],
                "Y": [measure("Net New ITY")],
            },
            titel="Zusammensetzung nach Sicherheit",
            untertitel="Dunkel = gesichert, hell = offen",
            objects={
                "legend": props(show=lit(True), position=lit("Bottom"), showTitle=lit(False), fontSize=lit(9.0)),
                "labels": props(show=lit(False)),
                "categoryAxis": props(show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(False)),
                "valueAxis": props(show=lit(False)),
            },
        )
    )
    y += h_haupt + 8

    # Organisationssicht als Matrix - viele Zeilen mit Zahlen sind eine
    # Tabelle, kein Diagramm.
    vis.append(
        visual(
            "pivotTable",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Rows": [spalte("DIM Betrieb", "Region"), spalte("DIM Betrieb", "Management")],
                "Values": [
                    measure("New Business ITY"), measure("Lost Business ITY"),
                    measure("Net New ITY"), measure("Net New Business %"),
                ],
            },
            titel="Net New ITY nach Organisation",
            sort=sortierung("Net New ITY"),
            objects={"subTotals": props(rowSubtotals=lit(True), columnSubtotals=lit(False))},
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "Cockpit", vis


def seite_bridge():
    y = INHALT_Y
    vis = kopf(aussage_measure="Aussage Sicherheit")

    # Wasserfall: die Standardform für "wie kommt die Summe zustande".
    vis.append(
        visual(
            "waterfallChart",
            CONTENT_X, y, CONTENT_W, 340,
            roles={
                "Category": [spalte("DIM Status", "Status")],
                "Y": [measure("Net New ITY")],
            },
            titel="Von der gesicherten Basis zum ausgewiesenen Net New ITY",
            untertitel="Jede Säule ist ein Sicherheitsgrad. Blau erhöht, rot mindert, grau ist die Summe.",
            sort=sortierung("Sortierung", "DIM Status", "Ascending", ist_measure=False),
            objects={
                "sentimentColors": props(
                    increaseFill=farbe(C["nb_expected"]),
                    decreaseFill=farbe(C["lb_expected"]),
                    totalFill=farbe(C["tinte_2"]),
                ),
                "labels": props(show=lit(True), color=farbe(C["tinte_2"]), fontSize=lit(9.0),
                                labelDisplayUnits=lit(1000000.0)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"])),
                "categoryAxis": props(show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(False)),
            },
        )
    )
    y += 340 + 8

    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X, y, int(CONTENT_W * 0.5) - 4, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Category": [spalte("DIM HFM-Struktur", "Kennzahl")],
                "Y": [measure("Net New ITY")],
            },
            titel="Zuordnung zum HFM-Kontenplan",
            untertitel="Group Guidance Februar 2025, Seite 3",
            sort=sortierung("Sortierung", "DIM HFM-Struktur", "Ascending", ist_measure=False),
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0), labelDisplayUnits=lit(1000000.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["nb_expected"])),
            },
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.5) + 4, y,
            int(CONTENT_W * 0.5) - 4, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Category": [spalte("DIM Betrieb", "HFM Sektor")],
                "Y": [measure("New Business ITY"), measure("Lost Business ITY")],
            },
            titel="Sektorsicht",
            untertitel="New und Lost getrennt, damit sich Effekte nicht gegenseitig verdecken",
            sort=sortierung("New Business ITY"),
            objects={
                "labels": props(show=lit(False)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"])),
                "dataPoint": [
                    {"properties": {"fill": farbe(C["nb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.New Business ITY"}},
                    {"properties": {"fill": farbe(C["lb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Lost Business ITY"}},
                ],
            },
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "Net-New-Brücke", vis


def seite_szenario():
    """Die Seite, die das manuelle Shiften ersetzt."""
    y = MARGIN
    vis = []

    # Erklärtext oben: was diese Seite tut. Eine Seite mit fünf Reglern braucht
    # einen Satz, der sagt, was die Regler bewirken.
    vis.append(
        visual(
            "cardVisual",
            CONTENT_X, y, CONTENT_W, 44,
            roles={"Data": [measure("Szenario Beschreibung")]},
            z=8000,
            objects={
                "callout": props(show=lit(True), fontSize=lit(12.0), color=farbe(C["tinte_2"]),
                                 horizontalAlignment=lit("left")),
                "label": props(show=lit(False)),
                "background": props(show=lit(True), color=farbe(C["flaeche"])),
                "border": props(show=lit(False)),
            },
        )
    )
    y += 44 + 8

    # Reglerzeile. Alle Parameter in einer Reihe, damit sie als
    # zusammengehörige Steuerung gelesen werden.
    breite = (CONTENT_W - 4 * 8) // 5
    for i, (tab, feld, titel) in enumerate([
        ("Szenario Bewertung", "Bewertungsbasis", "Bewertungsbasis"),
        ("Szenario Verschiebung", "Bezeichnung", "Zeitliche Verschiebung"),
        ("Szenario Anlauf", "Bezeichnung", "Anlauffaktor"),
        ("Szenario Anlaufdauer", "Bezeichnung", "Anlaufdauer"),
        ("Szenario Schwelle", "Bezeichnung", "Mindestwahrscheinlichkeit"),
    ]):
        vis.append(
            slicer(CONTENT_X + i * (breite + 8), y, breite, FILTER_H, tab, feld, titel,
                   syncgruppe=f"szenario_{feld}")
        )
    y += FILTER_H + 8

    vis.append(
        kpi(CONTENT_X, y, CONTENT_W, 88,
            ["Net New ITY", "Net New ITY (Szenario)", "Δ Szenario zu Basis",
             "Unknown ITY Budget", "Zielerreichung"])
    )
    y += 88 + 8

    h = CANVAS_H - y - MARGIN - FOOTER_H - 8
    vis.append(
        visual(
            "lineChart",
            CONTENT_X, y, int(CONTENT_W * 0.66), h,
            roles={
                "Category": [spalte("DIM Datum", "Periode Label")],
                "Y": [measure("Net New ITY"), measure("Net New ITY (Szenario)"),
                      measure("Unknown ITY Budget")],
            },
            titel="Wirkung der Annahmen auf den Monatsverlauf",
            untertitel="Hellblau: unverändert aus dem CRM · Dunkelblau: mit Annahmen · Grau: Budget",
            objects={
                "labels": props(show=lit(False)),
                "legend": props(show=lit(True), position=lit("TopLeft"), showTitle=lit(False)),
                "categoryAxis": props(show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(False)),
                "valueAxis": props(show=lit(True), showAxisTitle=lit(False), gridlineShow=lit(True),
                                   gridlineColor=farbe(C["linie"]), labelDisplayUnits=lit(1000000.0)),
                "dataPoint": [
                    {"properties": {"fill": farbe(C["nb_pipeline"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Net New ITY"}},
                    {"properties": {"fill": farbe(C["nb_won"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Net New ITY (Szenario)"}},
                    {"properties": {"fill": farbe(C["referenz"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Unknown ITY Budget"}},
                ],
            },
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.66) + 8, y,
            CONTENT_W - int(CONTENT_W * 0.66) - 8, h,
            roles={
                "Category": [spalte("DIM Datum", "GJ Periode")],
                "Y": [measure("Δ Szenario zu Basis")],
            },
            titel="Verschiebung je Periode",
            untertitel="Wohin die Annahmen den Effekt bewegen",
            objects={
                "labels": props(show=lit(False)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"])),
                "categoryAxis": props(show=lit(True), showAxisTitle=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["nb_expected"])),
            },
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "Szenarien", vis


def seite_new_business():
    y = INHALT_Y
    vis = kopf()

    filterzeile = [
        ("DIM Opportunity", "Vertriebsphase", "Vertriebsphase"),
        ("DIM Status", "Status", "Status"),
        ("DIM Opportunity", "Sektor", "Sektor"),
        ("DIM Opportunity", "Verantwortlicher", "Verantwortlicher"),
    ]
    breite = (CONTENT_W - 3 * 8) // 4
    for i, (tab, feld, titel) in enumerate(filterzeile):
        vis.append(slicer(CONTENT_X + i * (breite + 8), y, breite, FILTER_H, tab, feld, titel))
    y += FILTER_H + 8

    h_oben = 200
    vis.append(
        visual(
            "clusteredColumnChart",
            CONTENT_X, y, int(CONTENT_W * 0.5) - 4, h_oben,
            roles={
                "Category": [spalte("DIM Datum", "Periode Label")],
                "Series": [spalte("DIM Status", "Status")],
                "Y": [measure("New Business ITY")],
            },
            titel="Wann die Neugeschäfte wirken",
            untertitel="Gestapelt nach Sicherheitsgrad",
            filters=[filter_measure_gleich("FCT Net New ITY", "Geschäftsart", ["NEW"])],
            objects={
                "legend": props(show=lit(True), position=lit("TopLeft"), showTitle=lit(False)),
                "labels": props(show=lit(False)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"]),
                                   labelDisplayUnits=lit(1000.0)),
            },
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.5) + 4, y,
            int(CONTENT_W * 0.5) - 4, h_oben,
            roles={
                "Category": [spalte("DIM Opportunity", "Aktueller Anbieter")],
                "Y": [measure("New Business ITY")],
            },
            titel="Gegen wen wir antreten",
            untertitel="ITY-Volumen nach bisherigem Anbieter – im Altbericht nicht sichtbar",
            sort=sortierung("New Business ITY"),
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0), labelDisplayUnits=lit(1000.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["nb_expected"])),
            },
        )
    )
    y += h_oben + 8

    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Values": [
                    spalte("DIM Opportunity", "Opportunity", aktiv=False),
                    spalte("DIM Opportunity", "Kunde", aktiv=False),
                    spalte("DIM Status", "Status", aktiv=False),
                    spalte("DIM Opportunity", "Win %", aktiv=False),
                    spalte("DIM Opportunity", "ARO Umsatz", aktiv=False),
                    spalte("DIM Opportunity", "ITY Umsatz", aktiv=False),
                    spalte("DIM Opportunity", "Entscheidungsdatum", aktiv=False),
                    spalte("DIM Opportunity", "Mobilisierung", aktiv=False),
                    measure("New Business ITY"),
                ]
            },
            titel="Opportunities im Detail",
            untertitel="Sortiert nach ITY-Wirkung. Rechtsklick auf eine Zeile öffnet die Detailseite.",
            sort=sortierung("New Business ITY"),
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "New Business", vis


def seite_lost_business():
    y = INHALT_Y
    vis = kopf()

    filterzeile = [
        ("DIM Status", "Status", "Risikostufe"),
        ("DIM Vertrag", "Risikogrund", "Risikogrund"),
        ("DIM Vertrag", "ARO-Status", "Datenlage Vorjahres-ARO"),
        ("DIM Betrieb", "Region", "Region"),
    ]
    breite = (CONTENT_W - 3 * 8) // 4
    for i, (tab, feld, titel) in enumerate(filterzeile):
        vis.append(slicer(CONTENT_X + i * (breite + 8), y, breite, FILTER_H, tab, feld, titel))
    y += FILTER_H + 8

    h_oben = 200
    vis.append(
        visual(
            "clusteredColumnChart",
            CONTENT_X, y, int(CONTENT_W * 0.5) - 4, h_oben,
            roles={
                "Category": [spalte("DIM Datum", "Periode Label")],
                "Series": [spalte("DIM Status", "Status")],
                "Y": [measure("Lost Business ITY")],
            },
            titel="Wann die Verluste wirken",
            untertitel="Gestapelt nach Risikostufe",
            filters=[filter_measure_gleich("FCT Net New ITY", "Geschäftsart", ["LOST"])],
            objects={
                "legend": props(show=lit(True), position=lit("TopLeft"), showTitle=lit(False)),
                "labels": props(show=lit(False)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"]),
                                   labelDisplayUnits=lit(1000.0)),
            },
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.5) + 4, y,
            int(CONTENT_W * 0.5) - 4, h_oben,
            roles={
                "Category": [spalte("DIM Vertrag", "Risikogrund")],
                "Y": [measure("Lost Business ITY")],
            },
            titel="Warum wir verlieren",
            untertitel="ITY-Wirkung nach Risikogrund laut CRM",
            sort=sortierung("Lost Business ITY", richtung="Ascending"),
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0), labelDisplayUnits=lit(1000.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["lb_expected"])),
            },
        )
    )
    y += h_oben + 8

    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Values": [
                    spalte("DIM Vertrag", "Vertrag", aktiv=False),
                    spalte("DIM Vertrag", "SAP ID", aktiv=False),
                    spalte("DIM Status", "Status", aktiv=False),
                    spalte("DIM Vertrag", "Retention %", aktiv=False),
                    spalte("DIM Vertrag", "Vorjahres-ARO", aktiv=False),
                    spalte("DIM Vertrag", "Vertragsende (bereinigt)", aktiv=False),
                    spalte("DIM Vertrag", "Entscheidungsdatum", aktiv=False),
                    spalte("DIM Vertrag", "Risikogrund", aktiv=False),
                    measure("Lost Business ITY"),
                ]
            },
            titel="Risikoverträge im Detail",
            untertitel="Sortiert nach ITY-Wirkung. Verträge ohne Vorjahres-ARO werden mit 0 € bewertet – siehe Spalte Datenlage.",
            sort=sortierung("Lost Business ITY", richtung="Ascending"),
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "Lost Business", vis


def seite_bewegung():
    """Die Seite für den CRM-Call: was hat sich seit dem letzten Mal geändert?"""
    y = INHALT_Y
    vis = kopf(aussage_measure="Aussage Net New")

    breite = (CONTENT_W - 2 * 8) // 3
    vis.append(slicer(CONTENT_X, y, breite, FILTER_H, "FCT CRM-Bewegung", "Stichtag", "Stichtag", modus="Dropdown"))
    vis.append(slicer(CONTENT_X + breite + 8, y, breite, FILTER_H, "FCT CRM-Bewegung", "Änderungsart", "Art der Änderung"))
    vis.append(slicer(CONTENT_X + 2 * (breite + 8), y, breite, FILTER_H, "FCT CRM-Bewegung", "Geschäftsart", "New / Lost"))
    y += FILTER_H + 8

    vis.append(
        kpi(CONTENT_X, y, CONTENT_W, 88,
            ["Bewegung Anzahl", "Bewegung Statuswechsel", "Bewegung positiv",
             "Bewegung negativ", "Bewegung Wert"])
    )
    y += 88 + 8

    h_oben = 190
    vis.append(
        visual(
            "clusteredColumnChart",
            CONTENT_X, y, int(CONTENT_W * 0.45) - 4, h_oben,
            roles={
                "Category": [spalte("FCT CRM-Bewegung", "Stichtag")],
                "Y": [measure("Bewegung positiv"), measure("Bewegung negativ")],
            },
            titel="Bewegung im Zeitverlauf",
            untertitel="Aufwärtskorrekturen gegen Abwärtskorrekturen je Stichtag",
            objects={
                "legend": props(show=lit(True), position=lit("TopLeft"), showTitle=lit(False)),
                "labels": props(show=lit(False)),
                "valueAxis": props(show=lit(True), gridlineShow=lit(True), gridlineColor=farbe(C["linie"]),
                                   labelDisplayUnits=lit(1000.0)),
                "dataPoint": [
                    {"properties": {"fill": farbe(C["nb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Bewegung positiv"}},
                    {"properties": {"fill": farbe(C["lb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Bewegung negativ"}},
                ],
            },
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.45) + 4, y,
            CONTENT_W - int(CONTENT_W * 0.45) - 4, h_oben,
            roles={
                "Category": [spalte("FCT CRM-Bewegung", "Änderungsart")],
                "Y": [measure("Bewegung Anzahl")],
            },
            titel="Wovon die Änderungen handeln",
            untertitel="Ein Statuswechsel verändert die Belastbarkeit stärker als eine Wertkorrektur",
            sort=sortierung("Bewegung Anzahl"),
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["referenz"])),
            },
        )
    )
    y += h_oben + 8

    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Values": [
                    spalte("FCT CRM-Bewegung", "Stichtag", aktiv=False),
                    spalte("DIM Opportunity", "Opportunity", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Änderungsart", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Status alt", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Status neu", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wahrscheinlichkeit alt", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wahrscheinlichkeit neu", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wert alt", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wert neu", aktiv=False),
                    measure("Bewegung Wert"),
                ]
            },
            titel="Jede Änderung im Klartext",
            untertitel="Vorher und nachher nebeneinander – die Grundlage für die Nachfrage im Call",
            sort=sortierung("Bewegung Wert"),
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "CRM-Bewegung", vis


def seite_abstimmung():
    y = INHALT_Y
    vis = kopf(aussage_measure="Stand der Daten")

    h_oben = 240
    vis.append(
        visual(
            "pivotTable",
            CONTENT_X, y, int(CONTENT_W * 0.55) - 4, h_oben,
            roles={
                "Rows": [spalte("DIM Datum", "GJ Periode")],
                "Values": [
                    measure("Net New ITY"), measure("Net New ITY (Szenario)"),
                    measure("Unknown ITY Budget"), measure("Δ CRM zu Budget"),
                ],
            },
            titel="CRM gegen Budget, Periode für Periode",
            untertitel="Die Abstimmspalte, die im Altbericht auf drei Seiten verteilt war",
            sort=sortierung("GJ Periode", "DIM Datum", "Ascending", ist_measure=False),
        )
    )
    vis.append(
        visual(
            "clusteredBarChart",
            CONTENT_X + int(CONTENT_W * 0.55) + 4, y,
            CONTENT_W - int(CONTENT_W * 0.55) - 4, h_oben,
            roles={
                "Category": [spalte("DIM Betrieb", "Known / Unknown")],
                "Y": [measure("Net New ITY"), measure("Unknown ITY Budget")],
            },
            titel="Known gegen unknown",
            untertitel="Gebuchtes Geschäft gegen die CRM-Approximation",
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0), labelDisplayUnits=lit(1000000.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": [
                    {"properties": {"fill": farbe(C["nb_expected"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Net New ITY"}},
                    {"properties": {"fill": farbe(C["referenz"])},
                     "selector": {"metadata": f"{MEASURE_TABLE}.Unknown ITY Budget"}},
                ],
            },
        )
    )
    y += h_oben + 8

    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN - FOOTER_H - 8,
            roles={
                "Values": [
                    spalte("DQ Prüfungen", "Regel", aktiv=False),
                    spalte("DQ Prüfungen", "Schweregrad", aktiv=False),
                    spalte("DQ Prüfungen", "Beschreibung", aktiv=False),
                    measure("DQ Verstöße"),
                    spalte("DQ Prüfungen", "Handlungshinweis", aktiv=False),
                ]
            },
            titel="Datenqualität – was im CRM nachgepflegt werden muss",
            untertitel="Jede Zeile nennt die betroffene Regel und die konkrete Handlung. Regeln mit Schweregrad ERROR blockieren die Aktualisierung.",
            sort=sortierung("DQ Verstöße"),
        )
    )
    vis.append(fusszeile())
    vis.append(nav())
    return "Abstimmung & Datenqualität", vis


def seite_detail():
    """Drillthrough-Seite für einen einzelnen Vorgang."""
    y = MARGIN
    vis = []
    # Zurück-Knopf. Die Rücksprungfunktion hängt an der Container-Eigenschaft
    # visualLink, nicht an den Visual-Objekten - deshalb hier gesondert gesetzt.
    zurueck = visual(
        "actionButton", MARGIN, MARGIN, 120, 32,
        z=9000,
        objects={"icon": [{"properties": {"shapeType": lit("back")}, "selector": {"id": "default"}}]},
    )
    zurueck["visual"]["visualContainerObjects"]["visualLink"] = props(
        show=lit(True), type=lit("Back")
    )
    vis.append(zurueck)

    y = MARGIN + 40
    vis.append(
        kpi(MARGIN, y, CANVAS_W - 2 * MARGIN, 88,
            ["New Business ITY", "New Business ARO", "Ø Win-% (volumengewichtet)",
             "Anzahl Opportunities"])
    )
    y += 88 + 8

    vis.append(
        visual(
            "columnChart",
            MARGIN, y, CANVAS_W - 2 * MARGIN, 220,
            roles={
                "Category": [spalte("DIM Datum", "Periode Label")],
                "Y": [measure("Net New ITY")],
            },
            titel="Periodenverteilung dieses Vorgangs",
            untertitel="So verteilt sich der ITY-Wert auf die Monate des Geschäftsjahres",
            objects={
                "labels": props(show=lit(True), fontSize=lit(9.0), labelDisplayUnits=lit(1000.0)),
                "valueAxis": props(show=lit(False)),
                "dataPoint": props(defaultColor=farbe(C["nb_expected"])),
            },
        )
    )
    y += 220 + 8

    vis.append(
        visual(
            "tableEx",
            MARGIN, y, CANVAS_W - 2 * MARGIN, CANVAS_H - y - MARGIN,
            roles={
                "Values": [
                    spalte("FCT CRM-Bewegung", "Stichtag", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Änderungsart", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wahrscheinlichkeit alt", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wahrscheinlichkeit neu", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wert alt", aktiv=False),
                    spalte("FCT CRM-Bewegung", "Wert neu", aktiv=False),
                ]
            },
            titel="Historie dieses Vorgangs im CRM",
            sort=sortierung("Stichtag", "FCT CRM-Bewegung", "Descending", ist_measure=False),
        )
    )
    return "Detail (Drillthrough)", vis, {
        "drillthrough": [spalte("DIM Opportunity", "Opportunity", aktiv=False)],
        "visibility": "HiddenInViewMode",
    }


def seite_dokumentation():
    y = MARGIN
    vis = []
    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, 300,
            roles={
                "Values": [
                    spalte("DIM HFM-Struktur", "HFM Konto", aktiv=False),
                    spalte("DIM HFM-Struktur", "Kennzahl", aktiv=False),
                    spalte("DIM HFM-Struktur", "HFM Definition", aktiv=False),
                ]
            },
            titel="HFM-Kontendefinitionen",
            untertitel="Wortlaut aus dem HFM Chart of Accounts, Group Guidance Februar 2025",
            sort=sortierung("Sortierung", "DIM HFM-Struktur", "Ascending", ist_measure=False),
        )
    )
    y += 300 + 8
    vis.append(
        visual(
            "tableEx",
            CONTENT_X, y, CONTENT_W, CANVAS_H - y - MARGIN,
            roles={
                "Values": [
                    spalte("DIM Status", "Status", aktiv=False),
                    spalte("DIM Status", "Geschäftsart", aktiv=False),
                    spalte("DIM Status", "Sicherheitsgrad", aktiv=False),
                    spalte("DIM Status", "Farbe", aktiv=False),
                ]
            },
            titel="Statusdefinitionen und Farbzuordnung",
            untertitel="Die Farbe jeder Statusstufe ist an die Daten gebunden und in allen Visualisierungen identisch",
            sort=sortierung("Sortierung", "DIM Status", "Ascending", ist_measure=False),
        )
    )
    vis.append(nav())
    return "Definitionen", vis


PAGES = [
    seite_cockpit,
    seite_bridge,
    seite_szenario,
    seite_new_business,
    seite_lost_business,
    seite_bewegung,
    seite_abstimmung,
    seite_detail,
    seite_dokumentation,
]


# ===========================================================================
# Schreiben
# ===========================================================================
def schreibe():
    if os.path.exists(PAGES_DIR):
        shutil.rmtree(PAGES_DIR)
    os.makedirs(PAGES_DIR, exist_ok=True)

    reihenfolge = []
    for fn in PAGES:
        ergebnis = fn()
        if len(ergebnis) == 3:
            anzeigename, visuals, zusatz = ergebnis
        else:
            anzeigename, visuals = ergebnis
            zusatz = {}

        seiten_id = _id("page", anzeigename)
        reihenfolge.append(seiten_id)
        seiten_pfad = os.path.join(PAGES_DIR, seiten_id)
        os.makedirs(os.path.join(seiten_pfad, "visuals"), exist_ok=True)

        page = {
            "$schema": SCHEMA_PAGE,
            "name": seiten_id,
            "displayName": anzeigename,
            "displayOption": "FitToPage",
            "height": CANVAS_H,
            "width": CANVAS_W,
            "objects": {
                "background": props(color=farbe(C["seite"]), transparency=lit(0)),
                "outspace": props(color=farbe(C["seite"]), transparency=lit(0)),
            },
        }
        if zusatz.get("visibility"):
            page["visibility"] = zusatz["visibility"]
        if zusatz.get("drillthrough"):
            page["filterConfig"] = {
                "filters": [
                    {
                        "name": _id("dt", anzeigename, i),
                        "field": f["field"],
                        "type": "Categorical",
                        "howCreated": "Drillthrough",
                    }
                    for i, f in enumerate(zusatz["drillthrough"])
                ]
            }

        with open(os.path.join(seiten_pfad, "page.json"), "w", encoding="utf-8") as fh:
            json.dump(page, fh, indent=2, ensure_ascii=False)

        for i, v in enumerate(visuals):
            vid = _id("visual", anzeigename, i, v["visual"]["visualType"])
            v["name"] = vid
            vpfad = os.path.join(seiten_pfad, "visuals", vid)
            os.makedirs(vpfad, exist_ok=True)
            with open(os.path.join(vpfad, "visual.json"), "w", encoding="utf-8") as fh:
                json.dump(v, fh, indent=2, ensure_ascii=False)

        print(f"  {anzeigename:32s} {len(visuals):2d} Visualisierungen")

    with open(os.path.join(PAGES_DIR, "pages.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {"$schema": SCHEMA_PAGES, "pageOrder": reihenfolge, "activePageName": reihenfolge[0]},
            fh, indent=2, ensure_ascii=False,
        )

    with open(os.path.join(DEFINITION, "version.json"), "w", encoding="utf-8") as fh:
        json.dump({"$schema": SCHEMA_VERSION, "version": "2.0.0"}, fh, indent=2)

    with open(os.path.join(DEFINITION, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "$schema": SCHEMA_REPORT,
                "themeCollection": {
                    "baseTheme": {
                        "name": "NetNewITY",
                        "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.3.0"},
                        "type": "SharedResources",
                    }
                },
                "resourcePackages": [
                    {
                        "name": "SharedResources",
                        "type": "SharedResources",
                        "items": [
                            {"name": "NetNewITY", "path": "BaseThemes/NetNewITY.json", "type": "BaseTheme"}
                        ],
                    }
                ],
                "objects": {
                    "section": props(verticalAlignment=lit("Top")),
                    "outspacePane": props(expanded=lit(False)),
                },
                "settings": {
                    "useStylableVisualContainerHeader": True,
                    "exportDataMode": "AllowSummarized",
                    "defaultDrillFilterOtherVisuals": True,
                    "allowChangeFilterTypes": True,
                    "useEnhancedTooltips": True,
                    "useDefaultAggregateDisplayName": True,
                },
            },
            fh, indent=2, ensure_ascii=False,
        )

    with open(os.path.join(REPORT, "definition.pbir"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                "version": "4.0",
                "datasetReference": {"byPath": {"path": "../Net New ITY Cockpit.SemanticModel"}},
            },
            fh, indent=2, ensure_ascii=False,
        )

    print(f"\n{len(reihenfolge)} Seiten geschrieben nach {PAGES_DIR}")


if __name__ == "__main__":
    schreibe()
