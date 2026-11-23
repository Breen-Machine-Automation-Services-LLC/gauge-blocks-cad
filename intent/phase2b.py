"""Author the tables, regions and solids intents (phase 2b). Expected values come from the invented generator in the
intent description and the Autodesk DXF Reference group codes; none comes from a program's output.
Run from the repository root: python -I intent/phase2b.py (after intent/phase2.py, which writes the planned stubs)."""
import json
from pathlib import Path
from references import author_references
R = Path(__file__).resolve().parents[1]
URL = 'https://help.autodesk.com/view/OARX/2026/ENU/'
# ACAD_TABLE was introduced with AutoCAD 2005 (AC1018); REGION and 3DSOLID exist from AutoCAD R13, so AC1015 and later here.
TABLE_VERSIONS = ['AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032']
ACIS_VERSIONS = ['AC1015', 'AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032']


def field(fid, value, kind, name, table, attr, section, basis, versions, tolerance=0,*,basis_type):
    selector = {'kind': kind, 'name': name} if kind == 'query_count' else {'kind': kind, 'name': name, 'table': table, 'attr': attr}
    return dict(id=fid, value=value, selector=selector,
                reference=dict(basis_type=basis_type,section=section, source='Autodesk DXF Reference', url=URL, basis=basis),
                tolerance=tolerance, versions=versions)


def write(i):
    (R / 'intent' / (i['intent_id'] + '.json')).write_text(json.dumps(author_references(i), indent=2) + '\n')


tables = [('F150_table_merged_title', 4, 3, ['Merged Title Row', 'Item', 'Qty', 'Note', 'Widget', '12', 'red', 'Gadget', '7', 'blue']),
          ('F151_table_plain', 3, 2, ['A1', 'B1', 'A2', 'B2', 'A3', 'B3'])]
expected = []; ff = {}
for layer, rows, cols, texts in tables:
    ids = []
    for attr, value, code, what in [('table_rows', rows, 91, 'number of rows'), ('table_columns', cols, 92, 'number of columns'),
                                    ('table_cell_text', texts, 1, 'cell text values in row order, merged and empty cells omitted')]:
        fid = layer + '.' + attr
        expected.append(field(fid, value, 'feature_attr', layer, 'ACAD_TABLE', attr, 'ACAD_TABLE group code ' + str(code) + ': ' + what,
                              'DXF Reference; invented values from the generator in the intent description', TABLE_VERSIONS,basis_type='synthetic'))
        ids.append(fid)
    ff[layer] = ids
write(dict(intent_id='future_k_tables', title='Tables', representation_id='reference_1',
           description='Merged title and plain table cells; generator: generators/bricscad/make_bricscad_masters.lsp. Tables: 4 rows by 3 columns, merged title "Merged Title Row", header Item/Qty/Note, Widget/12/red, Gadget/7/blue; plain 3 by 2 cells A1/B1, A2/B2, A3/B3. Authored by BricsCAD only; ezdxf has no table writer, so other programs appear as cross-set resavers. The expectation reads the table cell data. The plain table drawn block omits B1 although its cell data holds it.',
           features=[t[0] for t in tables], expected=expected, feature_fields=ff))

expected = []; ff = {'F152_region': [], 'F154_solid3d': []}
for layer, etype in [('F152_region', 'REGION'), ('F154_solid3d', '3DSOLID')]:
    fid = layer + '.count'
    expected.append(field(fid, 1, 'query_count', etype + '[layer=="' + layer + '"]', None, None, etype + ' entity (ACIS)',
                          'DXF Reference; one entity per layer in the generator in the intent description', ACIS_VERSIONS,basis_type='synthetic'))
    ff[layer].append(fid)
    fid = layer + '.acis_body_count'
    expected.append(field(fid, 1, 'feature_attr', layer, etype, 'acis_body_count', etype + ' ACIS data (SAT text or SAB binary): one body',
                          'DXF Reference; one ACIS body per entity', ACIS_VERSIONS,basis_type='synthetic'))
    ff[layer].append(fid)
fid = 'F154_solid3d.acis_bbox_size'
expected.append(field(fid, [12, 8, 6], 'feature_attr', 'F154_solid3d', '3DSOLID', 'acis_bbox_size', '3DSOLID ACIS data: box 12 by 8 by 6',
                      'DXF Reference; box dimensions from the generator in the intent description, read as a tessellation bounding box', ACIS_VERSIONS, 1e-6,basis_type='synthetic'))
ff['F154_solid3d'].append(fid)
write(dict(intent_id='future_k_regions_solids', title='Regions and solids', representation_id='reference_1',
           description='Circular region radius 10 and box 12 by 8 by 6; generator: generators/bricscad/make_bricscad_masters.lsp. Expected REGION from circle radius 10 and 3DSOLID box dimensions 12 by 8 by 6. Authored by BricsCAD only. The region expectation is the entity count and one ACIS body; its radius cannot be read from ACIS data with the pinned ezdxf.',
           features=['F152_region', 'F154_solid3d'], expected=expected, feature_fields=ff))
