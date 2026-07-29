#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prüft das PBIP-Projekt auf Konsistenz, bevor es in Power BI geöffnet wird.

Geprüft wird:
  1. Jede im Bericht referenzierte Kennzahl existiert im Semantikmodell.
  2. Jede im Bericht referenzierte Spalte existiert im Semantikmodell.
  3. Jede Tabelle in relationships.tmdl existiert und die Spalten auch.
  4. Jede Tabelle ist in model.tmdl per "ref table" eingebunden.
  5. Kein Visual ragt über die Leinwand hinaus oder überlappt ein anderes
     in einer Weise, die Inhalte verdeckt.
  6. Jede Kennzahl trägt eine Beschreibung (/// Kommentar).
  7. Die im Bericht verwendeten Hexfarben stammen aus der Themendatei.
  8. TMDL-Kommentare sind gültig: kein //-Kommentar (TMDL kennt nur ///) und
     keine Leerzeile zwischen führendem ///-Block und erstem Objekt – beides
     lässt Power BI Desktop beim Öffnen mit "TDML-Formatfehler" abbrechen.

Aufruf:
    python3 tools/validate_pbip.py
Rückgabewert 0 = alles in Ordnung, 1 = mindestens ein Fehler.
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "powerbi", "Net New ITY Cockpit.SemanticModel", "definition")
REPORT = os.path.join(ROOT, "powerbi", "Net New ITY Cockpit.Report")
THEME = os.path.join(REPORT, "StaticResources", "SharedResources", "BaseThemes", "NetNewITY.json")

CANVAS_W, CANVAS_H = 1280, 720

fehler, warnungen = [], []


def melde_fehler(m):
    fehler.append(m)


def melde_warnung(m):
    warnungen.append(m)


# ---------------------------------------------------------------------------
# 1. Modell einlesen
# ---------------------------------------------------------------------------
def lies_modell():
    """Liest die TMDL-Dateien und liefert
       {tabelle: {"columns": set, "measures": set, "measures_ohne_doku": set}}
    """
    tabellen = {}
    for pfad in glob.glob(os.path.join(MODEL, "tables", "*.tmdl")):
        text = open(pfad, encoding="utf-8").read()
        m = re.search(r"^table\s+(.+)$", text, re.M)
        if not m:
            melde_fehler(f"{os.path.basename(pfad)}: keine table-Deklaration gefunden")
            continue
        name = m.group(1).strip().strip("'")

        spalten, kennzahlen, ohne_doku = set(), set(), set()
        zeilen = text.split("\n")
        for i, zeile in enumerate(zeilen):
            mc = re.match(r"^\tcolumn\s+(.+?)(\s*=.*)?$", zeile)
            if mc:
                spalten.add(mc.group(1).strip().strip("'"))
                continue
            mm = re.match(r"^\tmeasure\s+(.+?)\s*=", zeile)
            if mm:
                kn = mm.group(1).strip().strip("'")
                kennzahlen.add(kn)
                # Dokumentation = /// Zeile(n) unmittelbar davor
                j = i - 1
                hat_doku = False
                while j >= 0 and (zeilen[j].strip() == "" or zeilen[j].strip().startswith("///")):
                    if zeilen[j].strip().startswith("///"):
                        hat_doku = True
                        break
                    j -= 1
                if not hat_doku:
                    ohne_doku.add(kn)

        tabellen[name] = {"columns": spalten, "measures": kennzahlen, "ohne_doku": ohne_doku}
    return tabellen


# ---------------------------------------------------------------------------
# 2. Bericht prüfen
# ---------------------------------------------------------------------------
def sammle_referenzen(knoten, treffer):
    """Läuft rekursiv durch die Visual-JSON und sammelt alle
    Column-/Measure-Referenzen ein."""
    if isinstance(knoten, dict):
        for art in ("Column", "Measure"):
            if art in knoten and isinstance(knoten[art], dict):
                ausdruck = knoten[art].get("Expression", {})
                entity = ausdruck.get("SourceRef", {}).get("Entity")
                prop = knoten[art].get("Property")
                if entity and prop:
                    treffer.append((art, entity, prop))
        for wert in knoten.values():
            sammle_referenzen(wert, treffer)
    elif isinstance(knoten, list):
        for wert in knoten:
            sammle_referenzen(wert, treffer)


def pruefe_bericht(tabellen):
    visual_dateien = sorted(glob.glob(os.path.join(REPORT, "definition", "pages", "*", "visuals", "*", "visual.json")))
    if not visual_dateien:
        melde_fehler("Keine Visualisierungen gefunden – wurde tools/build_report.py ausgeführt?")
        return

    seiten = {}
    for pfad in visual_dateien:
        seite = pfad.split(os.sep)[-4]
        d = json.load(open(pfad, encoding="utf-8"))
        kurz = os.path.join(*pfad.split(os.sep)[-5:])

        # --- Referenzen ---
        treffer = []
        sammle_referenzen(d, treffer)
        for art, entity, prop in treffer:
            if entity not in tabellen:
                melde_fehler(f"{kurz}: Tabelle '{entity}' existiert nicht im Modell")
                continue
            schluessel = "measures" if art == "Measure" else "columns"
            if prop not in tabellen[entity][schluessel]:
                art_de = "Kennzahl" if art == "Measure" else "Spalte"
                melde_fehler(f"{kurz}: {art_de} '{entity}'[{prop}] existiert nicht im Modell")

        # --- Geometrie ---
        pos = d.get("position", {})
        x, y = pos.get("x", 0), pos.get("y", 0)
        w, h = pos.get("width", 0), pos.get("height", 0)
        if x < 0 or y < 0:
            melde_fehler(f"{kurz}: negative Position ({x}, {y})")
        if x + w > CANVAS_W + 0.5:
            melde_fehler(f"{kurz}: ragt rechts über die Leinwand ({x + w:.0f} > {CANVAS_W})")
        if y + h > CANVAS_H + 0.5:
            melde_fehler(f"{kurz}: ragt unten über die Leinwand ({y + h:.0f} > {CANVAS_H})")
        if w < 40 or h < 20:
            melde_warnung(f"{kurz}: sehr klein ({w:.0f} x {h:.0f})")
        seiten.setdefault(seite, []).append((kurz, x, y, w, h, d["visual"]["visualType"]))

    # --- Überlappungen innerhalb einer Seite ---
    # Navigation und Fußzeile liegen bewusst auf eigenen Bahnen; echte
    # Überlappungen zweier Datenvisuals sind dagegen immer ein Layoutfehler.
    for seite, liste in seiten.items():
        daten_visuals = [v for v in liste if v[5] not in ("pageNavigator", "actionButton")]
        for i in range(len(daten_visuals)):
            for j in range(i + 1, len(daten_visuals)):
                a, b = daten_visuals[i], daten_visuals[j]
                ueberlapp_x = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                ueberlapp_y = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
                if ueberlapp_x > 2 and ueberlapp_y > 2:
                    melde_fehler(
                        f"Seite {seite}: '{a[5]}' und '{b[5]}' überlappen sich um "
                        f"{ueberlapp_x:.0f} x {ueberlapp_y:.0f} px"
                    )


# ---------------------------------------------------------------------------
# 3. Beziehungen prüfen
# ---------------------------------------------------------------------------
def pruefe_beziehungen(tabellen):
    pfad = os.path.join(MODEL, "relationships.tmdl")
    if not os.path.exists(pfad):
        melde_warnung("relationships.tmdl fehlt")
        return
    text = open(pfad, encoding="utf-8").read()
    for richtung, tab, sp in re.findall(r"(fromColumn|toColumn):\s*'?([^'.\n]+)'?\.'?([^'\n]+?)'?\s*$", text, re.M):
        tab = tab.strip().strip("'")
        sp = sp.strip().strip("'")
        if tab not in tabellen:
            melde_fehler(f"relationships.tmdl: Tabelle '{tab}' existiert nicht")
        elif sp not in tabellen[tab]["columns"]:
            melde_fehler(f"relationships.tmdl: Spalte '{tab}'[{sp}] existiert nicht")


# ---------------------------------------------------------------------------
# 4. model.tmdl prüfen
# ---------------------------------------------------------------------------
def pruefe_modelldatei(tabellen):
    pfad = os.path.join(MODEL, "model.tmdl")
    text = open(pfad, encoding="utf-8").read()
    referenziert = {m.strip().strip("'") for m in re.findall(r"^ref table\s+(.+)$", text, re.M)}
    for name in tabellen:
        if name not in referenziert:
            melde_fehler(f"model.tmdl: Tabelle '{name}' ist nicht per 'ref table' eingebunden")
    for name in referenziert:
        if name not in tabellen:
            melde_fehler(f"model.tmdl: 'ref table {name}' zeigt auf eine nicht vorhandene Datei")


# ---------------------------------------------------------------------------
# 5. Dokumentationspflicht
# ---------------------------------------------------------------------------
def pruefe_dokumentation(tabellen):
    for name, inhalt in tabellen.items():
        for kn in sorted(inhalt["ohne_doku"]):
            melde_fehler(f"Kennzahl '{name}'[{kn}] hat keine Beschreibung (/// Kommentar)")


# ---------------------------------------------------------------------------
# 6. Farben gegen das Thema prüfen
# ---------------------------------------------------------------------------
def pruefe_farben():
    if not os.path.exists(THEME):
        melde_warnung("Themendatei nicht gefunden")
        return
    thema = open(THEME, encoding="utf-8").read()
    erlaubt = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", thema)}
    erlaubt.add("#FFFFFF")

    verwendet = set()
    for pfad in glob.glob(os.path.join(REPORT, "definition", "pages", "*", "visuals", "*", "visual.json")):
        verwendet |= {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", open(pfad, encoding="utf-8").read())}

    fremd = verwendet - erlaubt
    if fremd:
        melde_fehler(
            "Farben im Bericht, die nicht im Thema definiert sind: " + ", ".join(sorted(fremd))
        )


# ---------------------------------------------------------------------------
# 7. TMDL-Kopfkommentare: müssen lückenlos zum ersten Objekt gehören
# ---------------------------------------------------------------------------
def pruefe_tmdl_kommentare():
    # TMDL kennt KEINEN //-Kommentar - weder auf oberster Ebene noch eingerückt
    # innerhalb eines Objekts. Zulässig ist ausschliesslich ///-Dokumentation,
    # und die muss lückenlos unmittelbar vor dem Objekt stehen, das sie
    # beschreibt. Alle drei Verstöße sind mit realem Fehlerbild aus Power BI
    # Desktop belegt:
    #   //-Zeile, Spalte 0    -> "Unerwarteter Zeilentyp: Other"
    #   //-Zeile, eingerückt  -> "Es wurde ein ungültiger Einzug erkannt"
    #   ///-Block + Leerzeile -> "Unerwarteter Zeilentyp: Empty"
    # Abschnittsüberschriften gehören deshalb in den ///-Block der folgenden
    # Kennzahl, nicht in einen eigenen Kommentarblock.
    for pfad in sorted(glob.glob(os.path.join(MODEL, "**", "*.tmdl"), recursive=True)):
        rel = os.path.relpath(pfad, ROOT)
        zeilen = open(pfad, encoding="utf-8").read().split("\n")

        for nr, zeile in enumerate(zeilen, start=1):
            gestrippt = zeile.strip()
            if gestrippt.startswith("//") and not gestrippt.startswith("///"):
                melde_fehler(
                    f"{rel}: Zeile {nr} ist ein //-Kommentar – TMDL kennt nur ///; "
                    "Text in den ///-Block des folgenden Objekts übernehmen"
                )

        i = 0
        sah_kommentar = False
        while i < len(zeilen) and zeilen[i].startswith("///"):
            sah_kommentar = True
            i += 1
        if sah_kommentar and i < len(zeilen) and zeilen[i].strip() == "":
            melde_fehler(
                f"{rel}: Zeile {i + 1} ist eine Leerzeile direkt nach einem "
                "führenden ///-Kommentarblock – TMDL bricht dort mit "
                "'Unerwarteter Zeilentyp: Empty' ab; Leerzeile entfernen, damit "
                "der Block zum ersten Objekt gehört"
            )


# ---------------------------------------------------------------------------
def main():
    print("Prüfe PBIP-Projekt …\n")
    tabellen = lies_modell()
    print(f"  Modell: {len(tabellen)} Tabellen, "
          f"{sum(len(t['measures']) for t in tabellen.values())} Kennzahlen, "
          f"{sum(len(t['columns']) for t in tabellen.values())} Spalten")

    pruefe_modelldatei(tabellen)
    pruefe_beziehungen(tabellen)
    pruefe_dokumentation(tabellen)
    pruefe_bericht(tabellen)
    pruefe_farben()
    pruefe_tmdl_kommentare()

    print()
    if warnungen:
        print(f"{len(warnungen)} Hinweis(e):")
        for w in warnungen:
            print(f"  · {w}")
        print()
    if fehler:
        print(f"{len(fehler)} Fehler:")
        for f in fehler:
            print(f"  ✗ {f}")
        return 1
    print("Alle Prüfungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
