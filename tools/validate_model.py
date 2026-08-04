#!/usr/bin/env python3
"""Konsistenzpruefung fuer das MAP4-Praemientool-Semantikmodell (TMDL).

Prueft ohne Power BI Desktop:
  1. Partitionsname == Tabellenname
  2. model.tmdl referenziert genau die vorhandenen Tabellen
  3. Alle Beziehungsspalten existieren
  4. Keine mehrdeutigen Filterpfade (mehr als ein aktiver Pfad zwischen zwei Tabellen)
  5. Alle Tabellen-/Spalten-/Measure-Referenzen in DAX existieren
  6. Keine case-insensitiven Namenskollisionen, sortByColumn zeigt auf vorhandene Spalten
  7. Alle Feldverweise im Report existieren im Modell

Aufruf:  python3 tools/validate_model.py
"""
import collections
import glob
import itertools
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MAP4-Praemientool")
MODEL = os.path.join(ROOT, "MAP4-Prämientool.SemanticModel", "definition")
REPORT = os.path.join(ROOT, "MAP4-Prämientool.Report", "definition")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().replace("\r", "")


def load_tables():
    tables = {}
    for path in sorted(glob.glob(os.path.join(MODEL, "tables", "*.tmdl"))):
        text = read(path)
        name = re.search(r"^table (.+)$", text, re.M).group(1).strip()
        partition = re.search(r"^\tpartition (.+?) = (\w+)$", text, re.M)
        # Der DAX-Teil ist alles vor der Partition; die M-Query enthaelt eckige
        # Klammern, die sonst faelschlich als Spaltenverweise gelesen wuerden.
        dax = "\n".join(
            line for line in text.split("\n\tpartition ")[0].split("\n")
            if not line.strip().startswith("///")
        )
        tables[name] = {
            "columns": [c.strip().strip("'") for c in re.findall(r"^\tcolumn (.+)$", text, re.M)],
            "measures": [m.strip().strip("'") for m in re.findall(r"^\tmeasure (.+?)\s*=", text, re.M)],
            "partition": partition.group(1).strip() if partition else None,
            "sort_by": [s.strip().strip("'") for s in re.findall(r"sortByColumn: (.+)", text)],
            "dax": dax,
            "file": os.path.basename(path),
        }
    return tables


def load_relationships():
    text = read(os.path.join(MODEL, "relationships.tmdl"))
    rels = []
    for block in re.split(r"^relationship ", text, flags=re.M)[1:]:
        rels.append({
            "name": block.split("\n")[0].strip(),
            "from": re.search(r"fromColumn: (\S+)", block).group(1),
            "to": re.search(r"toColumn: (\S+)", block).group(1),
            "active": "isActive: false" not in block,
            "bidirectional": "bothDirections" in block,
        })
    return rels


def main():
    tables = load_tables()
    rels = load_relationships()
    errors = []

    for name, tbl in tables.items():
        if tbl["partition"] != name:
            errors.append(f"Partitionsname '{tbl['partition']}' != Tabelle '{name}' ({tbl['file']})")

    refs = {r.strip() for r in re.findall(r"^ref table (.+)$", read(os.path.join(MODEL, "model.tmdl")), re.M)}
    if refs != set(tables):
        errors.append(f"model.tmdl: fehlt={sorted(set(tables) - refs)} zuviel={sorted(refs - set(tables))}")

    names = [r["name"] for r in rels]
    if len(names) != len(set(names)):
        errors.append("Doppelte Beziehungsnamen")

    for rel in rels:
        for ref in (rel["from"], rel["to"]):
            table, column = ref.split(".", 1)
            if table not in tables:
                errors.append(f"{rel['name']}: Tabelle '{table}' fehlt")
            elif column not in tables[table]["columns"]:
                errors.append(f"{rel['name']}: Spalte '{table}[{column}]' fehlt")

    adjacency = collections.defaultdict(list)
    for rel in rels:
        if not rel["active"]:
            continue
        a, b = rel["from"].split(".")[0], rel["to"].split(".")[0]
        adjacency[a].append((b, rel["name"]))
        adjacency[b].append((a, rel["name"]))

    def all_paths(src, dst):
        found = []

        def walk(node, seen, used):
            if node == dst:
                found.append(tuple(used))
                return
            for neighbour, rel_name in adjacency[node]:
                if neighbour not in seen:
                    walk(neighbour, seen | {neighbour}, used + [rel_name])

        walk(src, {src}, [])
        return found

    for a, b in itertools.combinations(sorted(tables), 2):
        found = all_paths(a, b)
        if len(found) > 1:
            errors.append(f"MEHRDEUTIG {a} <-> {b}: {found}")

    all_measures = {m for tbl in tables.values() for m in tbl["measures"]}
    for name, tbl in tables.items():
        for table, column in re.findall(r"\b([A-Za-z_]\w*)\[([^\]]+)\]", tbl["dax"]):
            if table in tables and column not in tables[table]["columns"] and column not in tables[table]["measures"]:
                errors.append(f"DAX {name}: {table}[{column}] existiert nicht")
        for measure in re.findall(r"(?<![\w\]'])\[([^\]\[]+)\]", tbl["dax"]):
            if measure not in all_measures:
                errors.append(f"DAX {name}: Measure [{measure}] existiert nicht")

        counts = collections.Counter(x.lower() for x in tbl["columns"] + tbl["measures"])
        for key, count in counts.items():
            if count > 1:
                errors.append(f"{name}: Namenskollision '{key}' ({count}x, Power BI ist case-insensitiv)")
        for sort_by in tbl["sort_by"]:
            if sort_by not in tbl["columns"]:
                errors.append(f"{name}: sortByColumn '{sort_by}' existiert nicht")

    for path in sorted(glob.glob(os.path.join(REPORT, "pages", "*", "visuals", "*", "visual.json"))):
        with open(path, encoding="utf-8") as fh:
            payload = json.dumps(json.load(fh), ensure_ascii=False)
        visual = os.path.basename(os.path.dirname(path))
        pattern = r'"Entity":\s*"([^"]+)"[^}]*}\s*},\s*"Property":\s*"([^"]+)"'
        for entity, prop in re.findall(pattern, payload):
            if entity not in tables:
                errors.append(f"Report {visual}: Tabelle '{entity}' fehlt")
            elif prop not in tables[entity]["columns"] and prop not in tables[entity]["measures"]:
                errors.append(f"Report {visual}: {entity}[{prop}] fehlt")

    active = sum(1 for r in rels if r["active"])
    bidi = sum(1 for r in rels if r["bidirectional"])
    print(f"Tabellen: {len(tables)} | Beziehungen: {len(rels)} (aktiv {active}) | Measures: {len(all_measures)}")
    print(f"Bidirektional: {bidi} | Deaktiviert: {len(rels) - active}")

    if errors:
        print("\nPROBLEME:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1
    print("\nAlles konsistent: keine fehlenden Referenzen, keine mehrdeutigen Filterpfade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
