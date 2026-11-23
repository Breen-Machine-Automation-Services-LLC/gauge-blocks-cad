# DXF standard inventory

`dxf-inventory.json` lists the Reference's entities, objects, symbol tables and
header variables. `reference_catalog.py` transcribes the item names and owning
URLs. The source inventory records a read date of 2026-11-23.

The source uses the 2027 ENTITIES and HEADER pages, the reachable 2026 OBJECTS
contents, and the 2017 full index and nested topics as fallbacks. This mixed
edition inventory does not establish exhaustive equivalence with the current
edition. Documentation grouping topics remain labeled as such. Header variables
share their owning HEADER table page because individual variable pages do not
exist.

Run from the repository root with the pinned Python dependencies:

```sh
python standard/build_inventory.py
python standard/check_inventory.py
python -I generators/write_coverage.py
```

The builder computes status from intent selectors and citations, and presence in
provenance-linked native ASCII drawings read as tags without auditing or saving.
Generator source supplies supplementary witnesses, not status decisions. It never
executes generators or CAD programs. The five statuses are:

- `included`: an intent field tests a property, through its selector or cited item.
- `partial`: tested, with the missing forms listed below.
- `present`: present in native drawings without a property assertion.
- `future`: named by a planned, wanted or blocked intent, without tested or native evidence.
- `omitted`: none of these evidence sources identifies it.

Tested evidence takes precedence over presence and future requests. These statuses
describe dataset coverage, not program support or full conformance. Future-item
matching recognizes SURFACE, extruded surface, OLE and proxy-object requests in
intent titles and descriptions.

The only hand-set status judgments are these incomplete forms:

- DIMENSION: Linear, aligned, angular and radial fields exist; ordinate and diameter forms are not authored.
- ELLIPSE: An elliptical arc is authored; no full-ellipse fixture.
- HATCH: Solid, island, pattern and gradient fields exist; edge-path and associative forms are not authored.
- POLYLINE: 2D width/bulge and 3D forms occur; polyface and polygon-mesh forms are not authored.
- REGION: Entity count and ACIS body count tested; the intended circle radius is not tested.
- SPLINE: Fit-point fixture only; no independent rational/control-point form.
- TABLE: Reference label TABLE maps to ACAD_TABLE in dataset selectors; rows, columns and cell strings tested, not merge geometry.

`build(repo)`, `read_intents(repo)` and `validate(records, intents)` provide the
analysis and validation interfaces. The checker also verifies full rebuild
equality and rejects deliberately invalid inventory mutations.

The cataloged OBJECTS contents and historical nested topics contain no SCALE item
page. Scale-list fields cite the recorded OBJECTS section URL and explicitly state
this limitation. SCALE is not added as a documented Reference item.
