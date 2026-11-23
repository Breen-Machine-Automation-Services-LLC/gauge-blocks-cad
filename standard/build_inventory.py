"""Read-only dataset analysis; writes deliverables only beside this script."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from reference_catalog import READ_DATE, catalog

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent
TABLE_ATTRIBUTES = {
    "appids": "APPID", "block_records": "BLOCK_RECORD", "dimstyles": "DIMSTYLE",
    "layers": "LAYER", "linetypes": "LTYPE", "styles": "STYLE", "ucs": "UCS",
    "views": "VIEW", "viewports": "VPORT",
}
TYPE_ALIASES = {
    "ACAD_TABLE": "TABLE", "MULTILEADER": "MLEADER", "EXTRUDEDSURFACE": "Extruded Surface",
    "LOFTEDSURFACE": "Lofted Surface", "REVOLVEDSURFACE": "Revolved Surface",
    "SWEPTSURFACE": "Swept Surface", "PDFUNDERLAY": "UNDERLAY", "DWFUNDERLAY": "UNDERLAY",
    "DGNUNDERLAY": "UNDERLAY", "PDFDEFINITION": "UNDERLAYDEFINITION",
    "DWFDEFINITION": "UNDERLAYDEFINITION", "DGNDEFINITION": "UNDERLAYDEFINITION",
    "SECTION_MANAGER": "Section Manager", "SECTION_SETTINGS": "Section Settings",
}
SPECIAL_NOTES = {
    ("entity", "DIMENSION"): "Linear, aligned, angular and radial fields exist; ordinate and diameter forms are not authored.",
    ("entity", "POLYLINE"): "2D width/bulge and 3D forms occur; polyface and polygon-mesh forms are not authored.",
    ("entity", "ELLIPSE"): "An elliptical arc is authored; no full-ellipse fixture.",
    ("entity", "HATCH"): "Solid, island, pattern and gradient fields exist; edge-path and associative forms are not authored.",
    ("entity", "SPLINE"): "Fit-point fixture only; no independent rational/control-point form.",
    ("entity", "REGION"): "Entity count and ACIS body count tested; the intended circle radius is not tested.",
    ("entity", "MLEADERSTYLE"): "Kept under entity to match Autodesk's ENTITIES contents, despite storage as a nongraphical object.",
    ("entity", "COORDINATION MODEL"): "Present in the full historical contents but absent from the reachable 2027 ENTITIES summary; no retirement inferred.",
    ("entity", "TABLE"): "Reference label TABLE maps to ACAD_TABLE in dataset selectors; rows, columns and cell strings tested, not merge geometry.",
    ("object", "SECTION"): "Documentation parent for section-manager/settings data, not the graphical SECTION entity.",
    ("object", "RENDER"): "Documentation parent for render-related objects; retained as a contents row, not asserted to be a group-0 type.",
    ("object", "Section Type Settings"): "Nested settings data documented separately; not asserted to be an independently serialized object.",
    ("object", "Section Geometry Settings"): "Nested settings data documented separately; not asserted to be an independently serialized object.",
    ("object", "FIELD"): "Page title FIELD, while its group-0 table says ACAD_FIELD; inventory preserves the title.",
    ("object", "ACDBNAVISWORKSMODELDEF"): "Page prose calls these symbol table entries, but Autodesk lists the page under OBJECTS; classification follows the contents.",
    ("object", "UNDERLAYDEFINITION"): "Page prose calls these symbol table entries, but Autodesk lists the page under OBJECTS; classification follows the contents.",
    ("object", "IMAGEDEF"): "IMAGE.image_size selector reads the entity, not IMAGEDEF; no definition property is tested.",
    ("table", "BLOCK_RECORD"): "Block identity is on BLOCK, not BLOCK_RECORD; no direct block-record property selector.",
    ("header", "$PDMODE"): "Explicitly assigned in generators/masters_ghijn.py master_n, but no header selector tests it.",
    ("header", "$PDSIZE"): "Explicitly assigned in generators/masters_ghijn.py master_n, but no header selector tests it.",
}
PARTIAL_FORMS = {
    ("entity", name) for name in ("DIMENSION", "POLYLINE", "ELLIPSE", "HATCH", "SPLINE", "REGION", "TABLE")
}
def read_intents(repo):
    intents = {}
    for path in sorted((repo / "intent").glob("*.json")):
        data = json.loads(path.read_text())
        if "intent_id" in data:
            assert data["intent_id"] not in intents, path
            intents[data["intent_id"]] = data
    return intents


def read_tags(path):
    lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
    assert len(lines) % 2 == 0, f"Unpaired ASCII tags: {path}"
    return [(int(lines[index].strip()), lines[index + 1].strip()) for index in range(0, len(lines), 2)]


def collect_native(repo, intents):
    evidence = defaultdict(list)
    object_types = defaultdict(set)
    files = []
    hashes = {}
    known = {(record["kind"], record["name"]) for record in catalog()}
    for sidecar in sorted((repo / "native").rglob("*.dxf.provenance.json")):
        provenance = json.loads(sidecar.read_text())
        if provenance.get("encoding") != "ASCII":
            continue
        intent_id = provenance["intent_id"]
        assert intent_id in intents, sidecar
        path = Path(str(sidecar).removesuffix(".provenance.json"))
        tags = read_tags(path)
        files.append(str(path.relative_to(repo)))
        for source in (path, sidecar):
            hashes[str(source.relative_to(repo))] = hashlib.sha256(source.read_bytes()).hexdigest()
        section = ""
        items = set()
        current_type = None
        handle_types = {}
        dictionary_links = []
        for index, (code, value) in enumerate(tags):
            if code == 0 and value == "SECTION":
                section = tags[index + 1][1]
            elif code == 0 and value == "ENDSEC":
                section = ""
            elif section == "HEADER" and code == 9:
                items.add(("header", value))
            elif section == "TABLES" and code == 0 and value == "TABLE":
                items.add(("table", tags[index + 1][1]))
            elif section in ("BLOCKS", "ENTITIES", "OBJECTS") and code == 0:
                current_type = value
                kind = "object" if section == "OBJECTS" else "entity"
                if value == "MLEADERSTYLE":
                    kind = "entity"
                items.add((kind, TYPE_ALIASES.get(value, value)))
            elif section == "OBJECTS" and code == 5:
                handle_types[value] = current_type
            elif section == "OBJECTS" and current_type in ("DICTIONARY", "ACDBDICTIONARYWDFLT") and code == 3:
                link_code, link_handle = tags[index + 1]
                if link_code in (350, 360):
                    dictionary_links.append((value, link_handle))
        for entry_name, handle in dictionary_links:
            if handle in handle_types:
                object_types[(intent_id, entry_name)].add(handle_types[handle])
        for key in sorted(items & known):
            if not any(entry["intent"] == intent_id for entry in evidence[key]):
                evidence[key].append(dict(intent=intent_id, file=str(path.relative_to(repo)), basis="Existing native ASCII DXF and its provenance; presence only, not a tested property."))
    return evidence, object_types, files, hashes


def selector_items(selector, object_types, intent_id):
    kind = selector["kind"]
    attribute = selector.get("attr")
    result = []
    if kind == "feature_attr":
        entity = TYPE_ALIASES.get(selector["table"], selector["table"])
        result.append(("entity", entity))
        if attribute == "extension_record":
            result.extend([("object", "DICTIONARY"), ("object", "XRECORD")])
        if attribute == "redraw_order":
            result.append(("object", "SORTENTSTABLE"))
        if attribute == "block_circle_radius":
            result.append(("entity", "CIRCLE"))
        if attribute == "vertices":
            result.append(("entity", "VERTEX"))
    elif kind == "table":
        result.append(("table", TABLE_ATTRIBUTES[selector["table"]]))
    elif kind == "query_count":
        for name in selector["name"].split("[")[0].split():
            if name != "*":
                result.append(("entity", TYPE_ALIASES.get(name, name)))
    elif kind == "identity":
        result.append(("entity", "BLOCK"))
    elif kind == "block":
        result.append(("entity", "INSERT" if attribute == "inserts" else "ATTDEF"))
    elif kind == "insert_attributes":
        result.extend([("entity", "INSERT"), ("entity", "ATTRIB")])
    elif kind in ("linetype_pattern", "complex_pattern"):
        result.append(("table", "LTYPE"))
        if attribute == "style":
            result.append(("table", "STYLE"))
    elif kind == "layer_count":
        result.append(("table", "LAYER"))
    elif kind == "group":
        result.append(("object", "GROUP"))
    elif kind == "layout_count":
        result.append(("object", "LAYOUT"))
    elif kind in ("viewport_freeze", "viewport_color"):
        result.append(("entity", "VIEWPORT"))
        if kind == "viewport_color":
            result.append(("table", "LAYER"))
    elif kind == "xdata":
        result.append(("table", "APPID"))
    elif kind == "xrecord":
        result.extend([("object", "XRECORD"), ("object", "DICTIONARY")])
    elif kind == "object":
        result.append(("object", "DICTIONARY"))
        dictionary = selector["dictionary"]
        if dictionary == "ACAD_VISUALSTYLE":
            result.append(("object", "VISUALSTYLE"))
        elif dictionary == "ACAD_PLOTSETTINGS":
            result.append(("object", "PLOTSETTINGS"))
        elif dictionary == "ACAD_SCALELIST":
            result.append(("object", "SCALE"))
        elif attribute == "opaque_values":
            types = object_types[(intent_id, selector["name"])]
            if not types:
                raise ValueError(f"No native object-type witness: {intent_id}: {selector}")
            result.extend(("object", name) for name in sorted(types))
        elif attribute == "value":
            result.append(("object", "DICTIONARYVAR"))
        elif attribute == "tags":
            result.append(("object", "XRECORD"))
        else:
            raise ValueError(f"Unmapped object selector: {intent_id}: {selector}")
    else:
        raise ValueError(f"Unmapped selector: {intent_id}: {selector}")
    return result


def generator_witnesses(repo):
    witnesses = []
    for path in sorted((repo / "generators").rglob("*")):
        if path.suffix not in (".py", ".lsp"):
            continue
        if path.suffix == ".py":
            ast.parse(path.read_text())
        for line_number, text in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"add_|\.new\(|header\[|vla-Add|mk-identity|TOPICS", text):
                witnesses.append(dict(file=str(path.relative_to(repo)), line=line_number, text=text.strip()))
    return witnesses


def future_items(intent):
    text = " ".join(str(intent.get(key, "")) for key in ("title", "description"))
    result = []
    if re.search(r"\bSURFACE\b", text, re.I):
        result.append(("entity", "SURFACE"))
        if re.search(r"extruded surface", text, re.I):
            result.append(("entity", "Extruded Surface"))
    if re.search(r"\bOLE\b", text):
        result.extend([("entity", "OLEFRAME"), ("entity", "OLE2FRAME")])
    if re.search(r"proxy objects", text, re.I):
        result.append(("object", "ACAD_PROXY_OBJECT"))
    return result


def build(repo):
    intents = read_intents(repo)
    native, object_types, files, native_hashes = collect_native(repo, intents)
    tests = defaultdict(list)
    future = defaultdict(list)
    known = {(record["kind"], record["name"]) for record in catalog()}
    unmapped = []
    for intent_id, intent in intents.items():
        if intent.get("status") in ("planned", "wanted", "blocked"):
            for key in future_items(intent):
                future[key].append(dict(intent=intent_id, status=intent["status"], text=intent["description"]))
            continue
        for field in intent.get("expected", []):
            cited = field['reference']['url'].split('#')[0]
            for record in catalog():
                if record['reference_url'] == cited:
                    key = record['kind'], record['name']
                    tests[key].append(dict(intent=intent_id, field=field['id'], citation=cited))
            for key in selector_items(field["selector"], object_types, intent_id):
                if key not in known:
                    unmapped.append(dict(intent=intent_id, field=field["id"], type=key[1]))
                    continue
                tests[key].append(dict(intent=intent_id, field=field["id"], selector=field["selector"]))
    records = catalog()
    evidence = []
    for record in records:
        key = record["kind"], record["name"]
        tested, generated, planned = tests[key], native[key], future[key]
        if tested:
            status = "partial" if key in PARTIAL_FORMS else "included"
            note = f"{len(tested)} intent field(s) test this item; see the linked intents for selectors."
        elif generated:
            status = "present"
            note = "Present in provenance-linked native generator output (including defaults); no intent field tests a property."
        elif planned:
            status = "future"
            note = "Named by a planned, wanted or blocked intent; no tested or native instance found."
        else:
            status = "omitted"
            note = "No intent assertion, native generator-output instance, or item-naming future intent found."
        if key in SPECIAL_NOTES:
            note += " " + SPECIAL_NOTES[key]
        if record["kind"] == "header" and re.fullmatch(r"\$USER[IR][1-5]", record["name"]):
            note += " Expanded from the Reference's grouped $USERI1 - 5 / $USERR1 - 5 rows."
        record["dataset"] = dict(status=status, intents=sorted({entry["intent"] for entry in tested + generated + planned}), note=note)
        evidence.append(dict(kind=key[0], name=key[1], assertions=tested, native_presence=generated, future=planned))
    inputs = list((repo / "intent").glob("*.json")) + list((repo / "generators").rglob("*.py")) + list((repo / "generators").rglob("*.lsp"))
    inputs += [repo / name for name in ("DESIGN.md", "COVERAGE.md", "intent/SCHEMA.md", "checker/core.py")]
    evidence_document = dict(read_date=READ_DATE, repository=str(repo), native_ascii_files=files, items=evidence,
                             native_input_sha256=native_hashes,
                             noncatalog_assertions=unmapped, generator_witnesses=generator_witnesses(repo),
                             input_sha256={str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(inputs)})
    return records, evidence_document


def write_json(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    args = parser.parse_args()
    records, _ = build(args.repo)
    write_json("dxf-inventory.json", records)
    print(dict(records=len(records), statuses=Counter(r["dataset"]["status"] for r in records)))


if __name__ == "__main__":
    main()
