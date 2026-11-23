# Expected functions: checker.core.compare(doc, intent, reader), extract(doc, selector);
# map.build.main_view_rows(root), comparison_rows(writer, resaver, root),
# and _page_evidence(data) preserve attribution evidence without running main().
"""WP8 requirements 6/7 and sweep regressions; no CAD or regeneration.

Proposed schema where the spec is silent: a grading row's read_observation is
{reader, status, actual, detail}, using reader_error for a public-API failure.
It never replaces the grading status. Reads cells expose reader_error counts;
round-trip summaries add unreadable_by_reader, displayed as "unreadable by
<reader>". Native converter observations appear in comparison native_read cells
and the converter's main Reads cell as "lost by converter", with both the
direct and converted evidence. These are contract proposals, not existing APIs.
Expected values below come from authored intents, not saved actual values.
"""
import json

import ezdxf
import pytest
from ezdxf.acis import api as acis

from checker import core
from test_attribution import attribution_corpus, populate, cells
from test_map_views import ROOT, builder, features, item_rows, write_json


READER = 'ezdxf ' + ezdxf.__version__
ACIS_FILE = 'native/bricscad/k_regions_solids_2000_binary.dxf'


def read_json(path):
    return json.loads(path.read_text())


def acis_intent():
    return read_json(ROOT / 'intent/future_k_regions_solids.json')


def field_intent(selector, value=1):
    return dict(intent_id='synthetic', expected=[dict(
        id='probe', selector=selector, value=value, tolerance=0,
        versions=['AC1032'])])


def assert_reader_failure(observation, exception, message):
    assert observation['status'] == 'reader_error'
    assert observation['reader'] == READER
    assert observation['actual'] is None
    detail = json.dumps(observation)
    for text in ('ezdxf', ezdxf.__version__, exception, message):
        assert text in detail


@pytest.mark.parametrize('field', [
    'F152_region.acis_body_count', 'F154_solid3d.acis_body_count',
    'F154_solid3d.acis_bbox_size'])
def test_real_acis_grading_and_public_read_are_separate(field):
    intent = acis_intent()
    expected = next(f for f in intent['expected'] if f['id'] == field)
    doc = ezdxf.readfile(ROOT / ACIS_FILE)  # Never audit before observing.
    entity = core.feature_entity(doc, expected['selector'])
    with pytest.raises(IndexError):
        acis.load_dxf(entity)  # Establish the pinned reader's real failure.
    row = next(r for r in core.compare(doc, intent, READER) if r['field'] == field)
    assert row['status'] == 'same'
    assert row['actual'] == pytest.approx(expected['value'], abs=expected['tolerance'])
    assert_reader_failure(row['read_observation'], 'IndexError', 'list index out of range')
    cause = json.dumps(row['read_observation']).lower()
    assert 'sat' in cause and 'binary' in cause and 'teigha' in cause
    # No monkey patch of the library is permitted by requirement 1.
    with pytest.raises(IndexError):
        acis.load_dxf(entity)


def test_successful_public_acis_read_is_recorded_too():
    intent = acis_intent()
    doc = ezdxf.readfile(ROOT / 'native/bricscad/k_regions_solids_2000_ASCII.dxf')
    field = next(f for f in intent['expected'] if f['id'] == 'F154_solid3d.acis_body_count')
    assert len(acis.load_dxf(core.feature_entity(doc, field['selector']))) == field['value']
    row = next(r for r in core.compare(doc, intent, READER) if r['field'] == field['id'])
    assert row['status'] == 'same'
    observation = row['read_observation']
    assert observation['reader'] == READER
    assert observation['status'] == 'same' and observation['actual'] == field['value']


def test_public_acis_observation_really_calls_library_without_poisoning_grade(monkeypatch):
    intent = acis_intent()
    doc = ezdxf.readfile(ROOT / 'native/bricscad/k_regions_solids_2000_ASCII.dxf')
    calls = []

    def broken_public_load(entity):
        calls.append(entity.dxftype())
        raise RuntimeError('synthetic public SAT loader defect')

    monkeypatch.setattr(acis, 'load_dxf', broken_public_load)
    rows = core.compare(doc, intent, READER)
    assert all(r['status'] == 'same' for r in rows)
    for row in rows:
        if '.acis_' in row['field']:
            assert_reader_failure(row['read_observation'], 'RuntimeError',
                                  'synthetic public SAT loader defect')
    assert {'REGION', '3DSOLID'} <= set(calls)


@pytest.mark.parametrize('exception', [IndexError, RuntimeError, AttributeError])
def test_library_query_failure_is_reader_error_and_other_fields_continue(monkeypatch, exception):
    doc = ezdxf.new('R2018')
    doc.modelspace().add_line((0, 0), (1, 0))
    original = type(doc.modelspace()).query

    def query(space, expression, *args, **kwargs):
        if expression == 'CIRCLE':
            raise exception('synthetic library query defect')
        return original(space, expression, *args, **kwargs)

    monkeypatch.setattr(type(doc.modelspace()), 'query', query)
    intent = field_intent(dict(kind='query_count', name='CIRCLE'))
    intent['expected'].append(dict(intent['expected'][0], id='survives',
                                   selector=dict(kind='query_count', name='LINE')))
    rows = core.compare(doc, intent, READER)
    assert [r['field'] for r in rows] == ['probe', 'survives']
    assert rows[1]['status'] == 'same' and rows[1]['actual'] == 1
    assert_reader_failure(rows[0], exception.__name__, 'synthetic library query defect')


@pytest.mark.parametrize('gradient', [False, True], ids=['missing', 'present'])
def test_missing_optional_gradient_is_clean_absence(gradient):
    doc = ezdxf.new('R2018')
    hatch = doc.modelspace().add_hatch(dxfattribs={'layer': 'gradient_probe'})
    if gradient:
        hatch.set_gradient(rotation=37)
    else:
        assert hatch.gradient is None  # Real missing-object shape from the sweep.
    intent = field_intent(dict(kind='feature_attr', table='HATCH',
                               name='gradient_probe', attr='gradient_rotation'), 37)
    row, = core.compare(doc, intent, READER)
    assert row['status'] == ('same' if gradient else 'absent')
    assert row['actual'] == (37 if gradient else None)
    rendered = json.dumps(row)
    assert 'NoneType' not in rendered and 'has no attribute' not in rendered
    assert 'reader_error' not in rendered


def test_genuine_missing_entity_remains_absent():
    intent = field_intent(dict(kind='feature_attr', table='CIRCLE',
                               name='missing', attr='radius'))
    row, = core.compare(ezdxf.new('R2018'), intent, READER)
    assert row['status'] == 'absent' and row['actual'] is None


@pytest.mark.parametrize('matching_reader', [True, False])
def test_resaved_reader_error_has_own_bucket_only_with_clean_same_reader(
        builder, attribution_corpus, matching_reader):
    root = populate(attribution_corpus, [dict(
        source='same', cross='reader_error',
        source_reader=READER if matching_reader else 'other synthetic-public')])
    path = root / 'results/fixture_checks.json'
    rows = read_json(path)
    for row in rows:
        if row['file'].startswith('cross/'):
            row.update(reader=READER, detail='ezdxf ' + ezdxf.__version__ +
                       ' IndexError: synthetic library query defect')
    write_json(root, path.relative_to(root), rows)
    comparison, main = cells(builder, root)
    rt = features(comparison)[('synthetic', 'field_0')]['round_trip']
    for cell in (rt, main):
        assert cell['kept'] == 0 and cell['total'] == 1
        assert cell['status'] == ('unreadable by reader' if matching_reader else 'source not readable')
        if matching_reader:
            assert 'unreadable by ' + READER in cell['label']
        assert any(r['status'] == 'reader_error' and r['reader'] == READER
                   for r in cell['evidence'])
    for summary in (comparison['summary'], main):
        assert summary['unreadable_by_reader'] == int(matching_reader)
        assert summary['source_not_readable'] == int(not matching_reader)
        assert summary['kept'] == summary['lost'] == summary['changed'] == 0
        assert summary['total'] == 1


def test_reader_errors_are_visible_and_counted_against_reader(builder, attribution_corpus):
    root = populate(attribution_corpus, [dict(source='reader_error', cross='same'),
                                       dict(source='same', cross='same')])
    path = root / 'results/fixture_checks.json'
    rows = read_json(path)
    for row in rows:
        row['reader'] = READER
        if row['status'] == 'reader_error':
            row['detail'] = READER + ' IndexError: synthetic library query defect'
    write_json(root, path.relative_to(root), rows)
    programs = item_rows(builder.main_view_rows(root))['PROXY']['programs']
    cell = programs['ezdxf']['reads']
    assert cell['status'] == 'reader_error'
    assert cell['reader_error'] == 1
    assert READER in cell['label']
    assert any(r['status'] == 'reader_error' for r in cell['evidence'])
    comparison, main = cells(builder, root)
    for summary in (comparison['summary'], main):
        assert summary['source_not_readable'] == 1
        assert summary['kept'] == 1 and summary['total'] == 2


def acis_corpus(root, rows):
    intent = acis_intent()
    iid = intent['intent_id']
    inventory = read_json(ROOT / 'standard/dxf-inventory.json')
    write_json(root, 'standard/dxf-inventory.json', [i for i in inventory
               if i['name'] in ('3DSOLID', 'REGION') and i['kind'] == 'entity'])
    write_json(root, 'intent/' + iid + '.json', intent)
    write_json(root, 'programs/capabilities.json', {
        p: dict(name=p, engine=p, outputs=[]) for p in ('ezdxf', 'bricscad', 'oda')})
    write_json(root, 'programs/pairs.json', [dict(
        writer='bricscad', resaver='oda', sources='native/bricscad')])
    cross = 'cross/bricscad__oda/k_regions_solids_2000_binary.dxf'
    for file in (ACIS_FILE, cross):
        write_json(root, file + '.provenance.json',
                   read_json(ROOT / (file + '.provenance.json')))
    write_json(root, 'results/fixture_checks.json', rows)
    return cross


@pytest.mark.parametrize('item', ['3DSOLID', 'REGION'])
def test_public_acis_gap_is_shown_in_reads_without_charging_round_trip(builder, tmp_path, item):
    # Isolate map consumption from the checker producer tested above.
    intent = acis_intent()
    rows = []
    cross = 'cross/bricscad__oda/k_regions_solids_2000_binary.dxf'
    for file in (ACIS_FILE, cross):
        for f in intent['expected']:
            row = dict(file=file, intent_id=intent['intent_id'], field=f['id'],
                       reader=READER, converter=None, status='same',
                       expected=f['value'], actual=f['value'])
            if f['selector'].get('attr', '').startswith('acis_'):
                row['read_observation'] = dict(reader=READER, status='reader_error', actual=None,
                    detail=READER + ' IndexError: list index out of range; cannot decode SAT '
                    'from binary DXF written by Teigha programs, R2000 to R2010')
            rows.append(row)
    acis_corpus(tmp_path, rows)
    programs = item_rows(builder.main_view_rows(tmp_path))[item]['programs']
    read = programs['ezdxf']['reads']
    assert read['status'] == 'reader_error'
    for text in (READER, 'SAT', 'binary', 'Teigha', 'R2000', 'R2010'):
        assert text in read['label']
    assert any(r['file'] == ACIS_FILE and r['read_observation']['status'] == 'reader_error'
               for r in read['evidence'] if 'read_observation' in r)
    assert programs['oda']['round_trip']['status'] == 'kept'
    comparison = builder.comparison_rows('bricscad', 'oda', tmp_path)
    assert comparison['summary']['kept'] == comparison['summary']['total'] == 2
    assert all(r['round_trip']['status'] == 'kept' for r in features(comparison).values())


def test_real_acis_cross_grading_still_matches_independent_intent():
    doc = ezdxf.readfile(ROOT / 'cross/bricscad__oda/k_regions_solids_2000_binary.dxf')
    rows = core.compare(doc, acis_intent(), READER)
    assert len(rows) == 5
    assert all(r['status'] == 'same' for r in rows)


@pytest.fixture
def table_converter_corpus(tmp_path):
    file = 'native/bricscad/k_tables_2013_binary.dxf'
    field = 'F151_table_plain.table_cell_text'
    rows = [r for r in read_json(ROOT / 'results/native_bricscad_checks.json')
            if r['file'] == file and r['field'] == field]
    direct, = [r for r in rows if r['converter'] is None]
    converted, = [r for r in rows if r['converter'] is not None]
    intent = read_json(ROOT / 'intent/future_k_tables.json')
    expected = next(f for f in intent['expected'] if f['id'] == field)
    assert expected['value'] == ['A1', 'B1', 'A2', 'B2', 'A3', 'B3']
    assert direct['status'] == 'same' and direct['actual'] == expected['value']
    assert converted['status'] == 'differs' and 'B1' not in converted['actual']
    intent.update(features=['F151_table_plain'], feature_fields={'F151_table_plain': [field]},
                  expected=[expected])
    write_json(tmp_path, 'intent/future_k_tables.json', intent)
    write_json(tmp_path, file + '.provenance.json', read_json(ROOT / (file + '.provenance.json')))
    write_json(tmp_path, 'results/fixture_checks.json', rows)
    write_json(tmp_path, 'standard/dxf-inventory.json', [dict(
        kind='entity', name='ACAD_TABLE', reference_url=expected['reference']['url'],
        dataset=dict(status='included', intents=[intent['intent_id']]))])
    write_json(tmp_path, 'programs/capabilities.json', {
        p: dict(name=p, engine=p, outputs=[]) for p in ('ezdxf', 'bricscad', 'oda')})
    write_json(tmp_path, 'programs/pairs.json', [dict(
        writer='bricscad', resaver='oda', sources='native/bricscad')])
    return tmp_path, direct, converted


@pytest.mark.parametrize('view', ['main', 'comparison'])
def test_native_secondary_table_loss_is_charged_to_converter(builder, table_converter_corpus, view):
    root, direct, converted = table_converter_corpus
    if view == 'main':
        programs = item_rows(builder.main_view_rows(root))['ACAD_TABLE']['programs']
        cell = programs['oda']['reads']
        assert programs['bricscad']['writes']['status'] == 'native drawing'
        assert programs['bricscad']['round_trip']['status'] == 'not measured'
    else:
        data = builder.comparison_rows('bricscad', 'oda', root)
        feature = features(data)[('future_k_tables', 'F151_table_plain')]
        cell = feature['native_read']
        assert feature['round_trip']['status'] == 'not measured'
        assert data['summary']['changed'] == data['summary']['lost'] == 0
    assert cell['status'] == 'lost by converter'
    assert converted['converter'] in cell['label']
    assert direct in cell['evidence'] and converted in cell['evidence']


def test_large_map_evidence_keeps_read_gap_cause_and_attribution(builder):
    # Exercise the packing path used by the real large map, not just tiny fixtures.
    row = dict(file=ACIS_FILE, intent_id='future_k_regions_solids',
               field='F154_solid3d.acis_body_count', reader=READER, converter=None,
               status='same', read_observation=dict(reader=READER, status='reader_error',
               actual=None, detail='IndexError: SAT binary Teigha R2000 to R2010'),
               source_status='same')
    data = dict(main_view=dict(padding='x' * 1_000_001, evidence=[row]), comparisons={})
    builder._page_evidence(data)
    packed = json.dumps(data)
    for text in ('read_observation', 'reader_error', READER, 'IndexError', 'SAT binary Teigha',
                 'source_status'):
        assert text in packed
