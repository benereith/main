#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erzeugt docs/03_berechnungslogik.md und docs/02_datenmodell.md aus den
TMDL-Dateien des Semantikmodells.

WARUM GENERIERT UND NICHT HANDGESCHRIEBEN
Handgepflegte Measure-Dokumentation ist nach der dritten Änderung falsch.
Hier ist die TMDL-Datei die einzige Quelle: die Beschreibung steht als
///-Kommentar direkt über der Kennzahl, der DAX-Ausdruck daneben. Dieses
Skript zieht beides heraus. Weicht die Dokumentation vom Code ab, ist das
Skript nicht gelaufen – nicht die Dokumentation veraltet.

Aufruf:
    python3 tools/generate_docs.py
"""

import glob
import os
import re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "powerbi", "Net New ITY Cockpit.SemanticModel", "definition")
DOCS = os.path.join(ROOT, "docs")

HINWEIS = (
    "> **Diese Datei wird erzeugt.** Sie entsteht aus den TMDL-Dateien des\n"
    "> Semantikmodells über `python3 tools/generate_docs.py`. Änderungen bitte\n"
    "> an der Quelle vornehmen (`powerbi/Net New ITY Cockpit.SemanticModel/`),\n"
    "> nicht hier.\n"
)


def lies_tabelle(pfad):
    """Zerlegt eine TMDL-Tabellendatei in Beschreibung, Spalten und Kennzahlen."""
    zeilen = open(pfad, encoding="utf-8").read().split("\n")

    tabellen_doku, tabellenname = [], None
    spalten, kennzahlen = [], []

    i = 0
    # Kopfkommentar der Tabelle
    while i < len(zeilen) and zeilen[i].startswith("///"):
        tabellen_doku.append(zeilen[i][3:].strip())
        i += 1
    m = re.match(r"^table\s+(.+)$", zeilen[i]) if i < len(zeilen) else None
    if m:
        tabellenname = m.group(1).strip().strip("'")

    doku = []
    while i < len(zeilen):
        zeile = zeilen[i]

        if re.match(r"^\t///", zeile):
            doku.append(zeile.strip()[3:].strip())
            i += 1
            continue

        mm = re.match(r"^\tmeasure\s+(.+?)\s*=\s*(.*)$", zeile)
        if mm:
            name = mm.group(1).strip().strip("'")
            rest = mm.group(2)
            ausdruck, i = lies_ausdruck(zeilen, i, rest)
            eigenschaften, i = lies_eigenschaften(zeilen, i)
            kennzahlen.append(
                {
                    "name": name,
                    "doku": doku[:],
                    "dax": ausdruck,
                    "ordner": eigenschaften.get("displayFolder", ""),
                    "format": eigenschaften.get("formatString", ""),
                }
            )
            doku = []
            continue

        mc = re.match(r"^\tcolumn\s+(.+?)(\s*=\s*(.*))?$", zeile)
        if mc:
            name = mc.group(1).strip().strip("'")
            berechnet = mc.group(2) is not None
            if berechnet:
                _, i = lies_ausdruck(zeilen, i, mc.group(3) or "")
            else:
                i += 1
            eigenschaften, i = lies_eigenschaften(zeilen, i)
            spalten.append(
                {
                    "name": name,
                    "doku": doku[:],
                    "typ": eigenschaften.get("dataType", "berechnet" if berechnet else ""),
                    "quelle": eigenschaften.get("sourceColumn", ""),
                    "versteckt": "isHidden" in eigenschaften,
                }
            )
            doku = []
            continue

        if zeile.strip() and not zeile.startswith("\t\t"):
            doku = []
        i += 1

    return tabellenname, tabellen_doku, spalten, kennzahlen


def lies_ausdruck(zeilen, i, rest):
    """Liest einen DAX-Ausdruck, auch mehrzeilig (``` oder Einrückung)."""
    if rest.strip().startswith("```"):
        i += 1
        block = []
        while i < len(zeilen) and not zeilen[i].strip().startswith("```"):
            block.append(zeilen[i].replace("\t\t\t", "", 1))
            i += 1
        i += 1
        return "\n".join(block).strip("\n"), i
    if rest.strip():
        return rest.strip(), i + 1
    # Mehrzeilig ohne Backticks: alle Folgezeilen mit tieferer Einrückung
    i += 1
    block = []
    while i < len(zeilen) and (zeilen[i].startswith("\t\t\t") or zeilen[i].strip() == ""):
        if zeilen[i].strip() == "" and block and not zeilen[i + 1 : i + 2]:
            break
        block.append(zeilen[i].replace("\t\t\t", "", 1))
        i += 1
    return "\n".join(block).strip("\n"), i


def lies_eigenschaften(zeilen, i):
    """Liest die eingerückten Eigenschaften eines Objekts."""
    eigenschaften = {}
    while i < len(zeilen):
        zeile = zeilen[i]
        if zeile.strip() == "":
            i += 1
            continue
        if not zeile.startswith("\t\t"):
            break
        inhalt = zeile.strip()
        if ":" in inhalt:
            k, v = inhalt.split(":", 1)
            eigenschaften[k.strip()] = v.strip()
        else:
            eigenschaften[inhalt] = True
        i += 1
    return eigenschaften, i


def lies_modell():
    tabellen = OrderedDict()
    for pfad in sorted(glob.glob(os.path.join(MODEL, "tables", "*.tmdl"))):
        name, doku, spalten, kennzahlen = lies_tabelle(pfad)
        if name:
            tabellen[name] = {
                "doku": doku,
                "spalten": spalten,
                "kennzahlen": kennzahlen,
                "datei": os.path.basename(pfad),
            }
    return tabellen


# ---------------------------------------------------------------------------
def schreibe_berechnungslogik(tabellen):
    alle = []
    for tname, t in tabellen.items():
        for k in t["kennzahlen"]:
            k["tabelle"] = tname
            alle.append(k)
    alle.sort(key=lambda k: (k["ordner"], k["name"]))

    zeilen = [
        "# 03 – Berechnungslogik aller Kennzahlen",
        "",
        HINWEIS,
        "",
        f"Das Modell enthält **{len(alle)} Kennzahlen** in "
        f"{len({k['ordner'] for k in alle})} Ordnern.",
        "",
        "## Inhalt",
        "",
    ]
    ordner = sorted({k["ordner"] for k in alle})
    for o in ordner:
        anker = re.sub(r"[^a-z0-9äöüß]+", "-", o.lower()).strip("-")
        anzahl = len([k for k in alle if k["ordner"] == o])
        zeilen.append(f"- [{o or '(ohne Ordner)'}](#{anker}) – {anzahl} Kennzahlen")
    zeilen.append("")

    for o in ordner:
        zeilen += ["", f"## {o or '(ohne Ordner)'}", ""]
        for k in [x for x in alle if x["ordner"] == o]:
            zeilen.append(f"### `{k['name']}`")
            zeilen.append("")
            if k["doku"]:
                absatz = []
                for d in k["doku"]:
                    if d == "":
                        if absatz:
                            zeilen.append(" ".join(absatz))
                            zeilen.append("")
                            absatz = []
                    else:
                        absatz.append(d)
                if absatz:
                    zeilen.append(" ".join(absatz))
                    zeilen.append("")
            else:
                zeilen.append("_Keine Beschreibung hinterlegt._")
                zeilen.append("")
            if k["format"]:
                zeilen.append(f"**Format:** `{k['format']}`")
                zeilen.append("")
            zeilen.append("```dax")
            zeilen.append(f"{k['name']} =")
            zeilen.append(k["dax"])
            zeilen.append("```")
            zeilen.append("")

    with open(os.path.join(DOCS, "03_berechnungslogik.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen))
    print(f"  docs/03_berechnungslogik.md  ({len(alle)} Kennzahlen)")


def schreibe_datenmodell(tabellen):
    zeilen = [
        "# 02 – Datenmodell",
        "",
        HINWEIS,
        "",
        "## Überblick",
        "",
        "| Tabelle | Rolle | Spalten | Kennzahlen | Quelle |",
        "|---|---|---:|---:|---|",
    ]
    for tname, t in tabellen.items():
        rolle = (
            "Fakt" if tname.startswith("FCT")
            else "Dimension" if tname.startswith("DIM")
            else "Szenario-Parameter" if tname.startswith("Szenario")
            else "Kennzahlen" if tname.startswith("_")
            else "Prüfung"
        )
        quelle = "–"
        pfad = os.path.join(MODEL, "tables", t["datei"])
        text = open(pfad, encoding="utf-8").read()
        m = re.search(r'fnLakehouse\("([^"]+)"\)', text)
        if m:
            quelle = f"`{m.group(1)}`"
        elif "= calculated" in text:
            quelle = "berechnet (DATATABLE)"
        zeilen.append(
            f"| `{tname}` | {rolle} | {len(t['spalten'])} | {len(t['kennzahlen'])} | {quelle} |"
        )

    zeilen += ["", "## Beziehungen", ""]
    zeilen += [
        "Grundregeln, die in den Altmodellen verletzt waren:",
        "",
        "1. Nur EINE Richtung. Die Altmodelle hatten elf beidseitig filternde",
        "   Beziehungen (dim_opp_* zu fct_opp), was Filterpfade unvorhersehbar",
        "   und Measures nicht mehr lokal nachvollziehbar macht.",
        "2. Keine Auto-Datumstabellen. Die Altmodelle trugen 12 bis 19",
        "   LocalDateTable_*-Tabellen mit sich.",
        "3. Ein Kalender für alle Fakten, verbunden über den Monatsbeginn.",
        "",
    ]
    rel_zeilen = open(os.path.join(MODEL, "relationships.tmdl"), encoding="utf-8").read().split("\n")
    zeilen += ["| Von | Nach | Aktiv | Zweck |", "|---|---|---|---|"]

    # Beziehungen sind der einzige Objekttyp im Modell OHNE description-
    # Eigenschaft: Power BI Desktop bricht beim Laden mit "Die Eigenschaft
    # 'description' ist unbekannt" ab, sobald ein ///-Block vor einer
    # relationship steht. Die Zwecktexte stehen deshalb hier statt in der
    # TMDL-Datei, gekoppelt über den Beziehungsnamen.
    ZWECK = {
        "FCT_NetNewITY__DIM_Datum":
            "Wirkungsperiode des Net New ITY. Der Fakt liegt auf Monatsebene, "
            "deshalb Verbindung auf den Monatsbeginn.",
        "FCT_NetNewITY__DIM_Status":
            "Statusdimension. Filtert die Zerlegung nach Sicherheitsgrad.",
        "FCT_NetNewITY__DIM_Opportunity":
            "Opportunity-Stammdaten. Nur New-Business-Zeilen finden einen "
            "Treffer; Lost-Business-Zeilen laufen ins Leere, was fachlich "
            "korrekt ist.",
        "FCT_NetNewITY__DIM_Vertrag":
            "Vertragsstammdaten. Spiegelbild der Opportunity-Beziehung: nur "
            "Lost-Business-Zeilen treffen. Deshalb INAKTIV – zwei aktive "
            "Beziehungen vom selben Schlüssel auf zwei Dimensionen wären ein "
            "mehrdeutiger Pfad. Aktiviert wird sie in den "
            "Vertragsvisualisierungen über USERELATIONSHIP.",
        "FCT_NetNewITY__DIM_Betrieb":
            "Betriebszuordnung, soweit im CRM gepflegt (cgplc_sapid).",
        "FCT_Umsatz__DIM_Datum":
            "SAP-Umsätze an denselben Kalender.",
        "FCT_Umsatz__DIM_Betrieb":
            "SAP-Umsätze an die Betriebsdimension.",
        "FCT_Umsatz__DIM_HFM":
            "SAP-Umsätze an die Net-New-Hierarchie über das "
            "Cause-of-Change-Mapping.",
        "FCT_Bewegung__DIM_Opportunity":
            "Bewegungsdaten an die Opportunity-Stammdaten, damit in der "
            "Bewegungsanalyse Kunde, Sektor und Verantwortlicher verfügbar "
            "sind.",
        "FCT_Bewegung__DIM_Vertrag":
            "Bewegungsdaten an die Vertragsstammdaten. Inaktiv aus demselben "
            "Grund wie bei der Faktentabelle.",
    }

    datensaetze, aktuell = [], None
    for z in rel_zeilen:
        if z.startswith("relationship "):
            if aktuell is not None:
                datensaetze.append(aktuell)
            aktuell = {"name": z.split(None, 1)[1].strip(), "body": []}
        elif z.strip() and aktuell is not None:
            aktuell["body"].append(z.strip())
    if aktuell is not None:
        datensaetze.append(aktuell)

    fehlend = [d["name"] for d in datensaetze if d["name"] not in ZWECK]
    if fehlend:
        print("  WARNUNG: Zwecktext fehlt für " + ", ".join(fehlend))

    for d in datensaetze:
        text = "\n".join(d["body"])
        mfrom = re.search(r"fromColumn:\s*(.+)", text)
        mto = re.search(r"toColumn:\s*(.+)", text)
        if mfrom and mto:
            aktiv = "nein" if "isActive: false" in text else "ja"
            zeilen.append(
                f"| `{mfrom.group(1).strip()}` | `{mto.group(1).strip()}` | "
                f"{aktiv} | {ZWECK.get(d['name'], '')} |"
            )

    zeilen += ["", "## Tabellen im Detail", ""]
    for tname, t in tabellen.items():
        zeilen += [f"### `{tname}`", ""]
        if t["doku"]:
            absatz = []
            for d in t["doku"]:
                if d == "":
                    if absatz:
                        zeilen += [" ".join(absatz), ""]
                        absatz = []
                else:
                    absatz.append(d)
            if absatz:
                zeilen += [" ".join(absatz), ""]
        if t["spalten"]:
            zeilen += ["| Spalte | Typ | Quellspalte | Bedeutung |", "|---|---|---|---|"]
            for s in t["spalten"]:
                bed = " ".join(x for x in s["doku"] if x) or "–"
                sichtbar = "" if not s["versteckt"] else " _(technisch)_"
                zeilen.append(
                    f"| `{s['name']}`{sichtbar} | {s['typ'] or '–'} | "
                    f"{('`' + s['quelle'] + '`') if s['quelle'] else '–'} | {bed} |"
                )
            zeilen.append("")

    with open(os.path.join(DOCS, "02_datenmodell.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen))
    print(f"  docs/02_datenmodell.md       ({len(tabellen)} Tabellen)")


if __name__ == "__main__":
    os.makedirs(DOCS, exist_ok=True)
    tab = lies_modell()
    print("Erzeuge Dokumentation …")
    schreibe_berechnungslogik(tab)
    schreibe_datenmodell(tab)
