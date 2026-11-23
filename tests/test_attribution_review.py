"""WP8 review rulings 8–12: authored observations, no CAD or regeneration.

For ruling 9, field_counts is a proposed cell contract: counts of attributed
field observations, separate from existing feature/slot totals.
"""
import json
from collections import defaultdict

import ezdxf
import pytest
from ezdxf.acis import api as acis

from checker import core
from checker.attribution import Attribution, outcome
from test_attribution import attribution_corpus, populate, cells
from test_attribution_gaps import READER, field_intent
from test_map_views import ROOT, builder, features, write_json


def load(root):
    provenance = {}
    for folder in ('native', 'cross'):
        for p in (root / folder).rglob('*.provenance.json'):
            provenance[p.relative_to(root).as_posix()[:-len('.provenance.json')]] = json.loads(p.read_text())
    rows, seen = [], set()
    for p in sorted((root / 'results').glob('*checks.json')):
        data = json.loads(p.read_text())
        if isinstance(data, list):
            for row in data:
                key = tuple(row.get(k) for k in ('file', 'field', 'reader', 'converter'))
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
    declarations = json.loads((root / 'programs/pairs.json').read_text())
    return provenance, rows, Attribution(provenance, rows, declarations)


@pytest.mark.parametrize('control', ['other_field', 'other_version', 'other_intent',
                                      'other_pair', 'mixed_encodings', 'all_same'])
def test_ruling8_dwg_excuse_requires_every_matching_direct_dxf(
        attribution_corpus, control):
    root = populate(attribution_corpus, [dict(source='same', cross='absent', format='DWG')])
    provenance, rows, _ = load(root)
    dwg = next(r for r in rows if r['file'].startswith('cross/ezdxf__cadcraft/') and r['file'].endswith('.dwg'))
    direct = next(r for r in rows if r['file'].startswith('cross/ezdxf__cadcraft/') and r['file'].endswith('.dxf'))
    if control == 'other_field':
        direct['field'] = 'unrelated'
    elif control == 'other_version':
        provenance[direct['file']]['version'] = '2018'
    elif control == 'other_intent':
        direct['intent_id'] = 'unrelated'
    elif control == 'other_pair':
        rows.remove(direct)  # The other pair's kept DXF cannot establish this pair.
        direct = dict(direct, file=direct['file'].replace('__cadcraft/', '__oda/'))
        rows.append(direct)
        provenance[direct['file']] = dict(provenance[dwg['file']], format='DXF')
    else:
        path = direct['file'].replace('.dxf', '_binary.dxf')
        provenance[path] = dict(provenance[direct['file']], encoding='binary')
        rows.append(dict(direct, file=path, status='same' if control == 'all_same' else 'absent'))
    attribution = Attribution(provenance, rows, json.loads((root / 'programs/pairs.json').read_text()))
    assert outcome([attribution.attribute(dwg)]) == (
        'lost in writer or converter' if control == 'all_same' else 'lost')


def test_ruling8_repository_dwg_excuses_have_field_version_evidence():
    provenance, rows, attribution = load(ROOT)
    direct_by_slot = defaultdict(list)
    for row in rows:
        meta = provenance.get(row['file'], {})
        if row['file'].startswith('cross/') and meta.get('format') == 'DXF' and not row.get('converter'):
            direct_by_slot[(row['file'].split('/')[1], row.get('intent_id'),
                            row.get('field'), meta.get('version'))].append(row)
    violations, checked = [], 0
    for row in rows:
        meta = provenance.get(row['file'], {})
        if meta.get('format') != 'DWG' or outcome([attribution.attribute(row)]) != 'lost in writer or converter':
            continue
        checked += 1
        pair = row['file'].split('/')[1]
        direct = direct_by_slot[(pair, row.get('intent_id'), row.get('field'), meta.get('version'))]
        if not direct or any(r['status'] != 'same' for r in direct):
            violations.append((row['file'], row['field'], [(r['file'], r['status']) for r in direct]))
    assert checked > 0
    assert not violations, f'{len(violations)} invalid DWG excuses: {violations[:10]}'


@pytest.mark.parametrize('real', ['lost', 'changed', 'unreadable by reader'])
@pytest.mark.parametrize('excuse', ['source not readable', 'lost in writer or converter'])
def test_ruling9_real_loss_outranks_excuses_in_either_order(tmp_path, real, excuse):
    # Serialize independent raw observations so the fixture is a temporary input.
    rows = [dict(status='absent', attribution=s) for s in (real, excuse)]
    write_json(tmp_path, 'observations.json', rows)
    rows = json.loads((tmp_path / 'observations.json').read_text())
    assert outcome(rows) == real
    assert outcome(list(reversed(rows))) == real


@pytest.mark.parametrize('status,expected,key', [
    ('absent', 'lost', 'lost'), ('differs', 'changed', 'changed'),
    ('reader_error', 'unreadable by reader', 'unreadable_by_reader')])
def test_ruling9_mixed_feature_and_cell_expose_both_field_counts(
        builder, attribution_corpus, status, expected, key):
    root = populate(attribution_corpus, [
        dict(source='same', cross=status), dict(source='absent', cross='absent')])
    intent = json.loads((root / 'intent/synthetic.json').read_text())
    intent.update(features=['mixed'], feature_fields={'mixed': ['field_0', 'field_1']})
    write_json(root, 'intent/synthetic.json', intent)
    # Put both fields into one output as well as one feature.
    path = root / 'results/fixture_checks.json'
    rows = json.loads(path.read_text())
    for row in rows:
        if row['file'].startswith('cross/'):
            row['file'] = 'cross/ezdxf__cadcraft/synthetic_0_2000.dxf'
        else:
            row['file'] = 'native/ezdxf/synthetic_0_2000_ASCII.dxf'
    write_json(root, path.relative_to(root), rows)
    comparison, main = cells(builder, root)
    feature = features(comparison)[('synthetic', 'mixed')]['round_trip']
    for cell in (feature, main):
        assert cell['status'] == expected
        assert cell['field_counts'][key] == 1
        assert cell['field_counts']['source_not_readable'] == 1
        assert cell['field_counts']['total'] == 2
    assert comparison['summary'][key] == 1
    assert comparison['summary']['total'] == 1


@pytest.mark.parametrize('baseline', [None, 'absent', 'differs', 'reader_error'])
def test_ruling10_same_is_kept_regardless_of_baseline(attribution_corpus, baseline):
    root = populate(attribution_corpus, [dict(source=baseline, cross='same')])
    _, rows, attribution = load(root)
    row = next(r for r in rows if r['file'].startswith('cross/'))
    assert outcome([attribution.attribute(row)]) == 'kept'


@pytest.mark.parametrize('raw,expected', [('absent', 'lost'), ('differs', 'changed'),
                                         ('reader_error', 'unreadable by reader')])
def test_ruling10_unmeasured_baseline_charges_resaver(attribution_corpus, raw, expected):
    root = populate(attribution_corpus, [dict(source=None, cross=raw)])
    _, rows, attribution = load(root)
    row = attribution.attribute(next(r for r in rows if r['file'].startswith('cross/')))
    assert row['source_status'] == 'not measured'
    assert outcome([row]) == expected


def test_ruling10_repository_same_rows_are_kept():
    _, rows, attribution = load(ROOT)
    same = [r for r in rows if r['status'] == 'same']
    assert same
    violations = [(r['file'], r['field'], attribution.attribute(r).get('attribution'))
                  for r in same if outcome([attribution.attribute(r)]) != 'kept']
    assert not violations, f'{len(violations)} same rows not kept: {violations[:10]}'


@pytest.mark.parametrize('binary,padded', [(False, False), (False, True),
                                          (True, False), (True, True)])
def test_ruling11_sat_note_requires_binary_and_unpadded_raw_record(
        tmp_path, monkeypatch, binary, padded):
    doc = ezdxf.new('R2000')
    solid = doc.modelspace().add_3dsolid(dxfattribs={'layer': 'probe'})
    # "ACIS Builder"; deliberately too short to be valid SAT. Force an
    # unrelated public failure while leaving the raw record available.
    solid.sat = ('ACIS Builder',)
    path = tmp_path / 'probe.dxf'
    doc.saveas(path, fmt='bin' if binary else 'asc')
    # ezdxf writes "^ " for A; removing only that pad creates Teigha's shape.
    assert b'^ ' in path.read_bytes(), 'Fixture must contain the encrypted A padding'
    if not padded:
        path.write_bytes(path.read_bytes().replace(b'^ ', b'^'))
    assert (b'^ ' in path.read_bytes()) == padded
    doc = ezdxf.readfile(path)
    def fail(entity):
        raise IndexError('synthetic public failure')
    monkeypatch.setattr(acis, 'load_dxf', fail)
    intent = field_intent(dict(kind='feature_attr', table='3DSOLID',
                              name='probe', attr='acis_body_count'))
    intent['expected'][0]['versions'] = ['AC1015']
    row, = core.compare(doc, intent, READER)
    observation = row['read_observation']
    assert observation['status'] == 'reader_error'
    assert 'synthetic public failure' in observation['detail']
    assert ('Teigha' in observation['detail']) == (binary and not padded)


@pytest.mark.parametrize('attr', ['gradient_rotation', 'extension_record',
                                  'block_circle_radius'])
def test_ruling12_missing_intermediate_objects_are_absent(tmp_path, attr):
    doc = ezdxf.new('R2018')
    if attr == 'gradient_rotation':
        doc.modelspace().add_hatch(dxfattribs={'layer': 'probe'})
        table = 'HATCH'
    elif attr == 'extension_record':
        doc.modelspace().add_line((0, 0), (1, 0), dxfattribs={'layer': 'probe'})
        table = 'LINE'
    else:
        doc.blocks.new('empty')
        doc.modelspace().add_blockref('empty', (0, 0), dxfattribs={'layer': 'probe'})
        table = 'INSERT'
    path = tmp_path / 'missing.dxf'
    doc.saveas(path)
    intent = field_intent(dict(kind='feature_attr', table=table, name='probe', attr=attr))
    row, = core.compare(ezdxf.readfile(path), intent, READER)
    assert row['status'] == 'absent'
    assert row['actual'] is None
    assert 'NoneType' not in json.dumps(row)


def test_ruling12_gradient_absence_uses_shared_resolution():
    # Structural part of ruling 12: a one-off None guard fixes the symptom but
    # leaves every other dereference exposed. Do not prescribe a helper name.
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(core.extract))
    branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and any(isinstance(part, ast.Constant) and part.value == 'gradient_rotation'
                        for part in ast.walk(node.test))]
    # A generic resolver may remove the special-case branch altogether.
    for branch in branches:
        body = ast.Module(body=branch.body, type_ignores=[])
        guards = [node for node in ast.walk(body)
                  if isinstance(node, (ast.If, ast.IfExp, ast.Compare))]
        assert not guards, 'Missing-object checks belong in shared resolution, not the gradient field'
        assert any(isinstance(node, ast.Call) for node in ast.walk(body)), (
            'Gradient dereference must go through shared resolution')
