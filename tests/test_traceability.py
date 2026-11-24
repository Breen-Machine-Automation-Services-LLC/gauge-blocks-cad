"""WP3 contracts. No drawing generation, network access, or desktop programs.

Inventory integration retains the supplied inventory's build(repo), read_intents(repo),
and validate(records, intents) API. Intent authoring runs only in a scratch tree.
"""
from collections import Counter
from copy import deepcopy
import importlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess

import pytest
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
BASIS_TYPES = {'normative', 'application_semantics', 'compatibility_policy', 'synthetic'}
LANDING = 'https://help.autodesk.com/view/OARX/2024/ENU/'
ITEM_URL = re.compile(r'https://help\.autodesk\.com/cloudhelp/\d{4}/ENU/AutoCAD-DXF/files/GUID-[A-F0-9-]+\.htm(?:#.*)?$')


def intents():
    return [json.loads(p.read_text()) for p in sorted((ROOT / 'intent').glob('*.json'))
            if not p.name.endswith('.schema.json')]


def fields():
    return [(i['intent_id'], f) for i in intents() for f in i.get('expected', [])]


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    # Override, rather than setdefault: never read settings.local.json.
    monkeypatch.setenv('CAD_DATASET_SETTINGS', str(ROOT / 'settings.example.json'))
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('External process forbidden'))


def test_every_expected_field_has_valid_basis_type():
    assert fields()
    bad = [(i, f['id'], f.get('reference', {}).get('basis_type')) for i, f in fields()
           if f.get('reference', {}).get('basis_type') not in BASIS_TYPES]
    assert not bad, bad


@pytest.mark.parametrize('mutation', ['missing', 'invalid', 'landing'])
def test_validator_rejects_bad_reference(tmp_path, monkeypatch, mutation):
    from intent import validate
    sample = deepcopy(next(i for i in intents() if i['intent_id'] == 'feature_b_geometry'))
    # Give every field a valid control reference; introduce exactly one defect.
    for f in sample['expected']:
        f['reference']['basis_type'] = 'synthetic'
    directory = tmp_path / 'intent'
    directory.mkdir()
    for name in ('intent.schema.json', 'provenance.schema.json'):
        shutil.copyfile(ROOT / 'intent' / name, directory / name)
    path = directory / 'feature_b_geometry.json'
    path.write_text(json.dumps(sample))
    monkeypatch.setattr(validate, 'R', tmp_path)
    validate.main()  # Control must be accepted before the isolated mutation.
    ref = sample['expected'][0]['reference']
    if mutation == 'missing':
        ref.pop('basis_type')
    elif mutation == 'invalid':
        ref['basis_type'] = 'invented_invalid_type'
    else:
        ref['url'] = LANDING
    path.write_text(json.dumps(sample))
    with pytest.raises((ValidationError, AssertionError, ValueError)):
        validate.main()


@pytest.mark.parametrize('intent_id,field_id,expected', [
    ('background_layers', 'vp.color', 'compatibility_policy'),
    ('feature_b_geometry', 'F32_circle.radius', 'synthetic'),
])
def test_known_basis_types(intent_id, field_id, expected):
    field = next(f for i, f in fields() if i == intent_id and f['id'] == field_id)
    assert field['reference'].get('basis_type') == expected


def test_ltype_pattern_basis_is_synthetic_and_names_group_72():
    matches = [f for _, f in fields() if
               (f['selector']['kind'] == 'linetype_pattern' and
                isinstance(f['value'], list) and [72, 65] in f['value'])]
    assert matches, 'Missing LTYPE group 72 alignment expectation'
    for field in matches:
        assert field['reference'].get('basis_type') == 'synthetic'
        assert re.search(r'\b72\b', field['reference']['basis'])


def test_validator_accepts_wholly_standard_fixed_normative_field(tmp_path, monkeypatch):
    from intent import validate
    sample = deepcopy(next(i for i in intents() if i['intent_id'] == 'feature_b_geometry'))
    for field in sample['expected']:
        field['reference']['basis_type'] = 'synthetic'
    field = sample['expected'][0]
    field['value'] = 65
    field['selector'] = {'kind': 'table', 'table': 'LTYPE', 'name': 'ZEV_DASH', 'attr': 'alignment'}
    field['reference'].update(url=next(r['reference_url'] for r in inventory() if r['kind'] == 'table' and r['name'] == 'LTYPE'), basis_type='normative', basis='Linetype alignment group 72 is fixed at 65 by the standard.')
    directory = tmp_path / 'intent'
    directory.mkdir()
    for name in ('intent.schema.json', 'provenance.schema.json'):
        shutil.copyfile(ROOT / 'intent' / name, directory / name)
    (directory / 'feature_b_geometry.json').write_text(json.dumps(sample))
    monkeypatch.setattr(validate, 'R', tmp_path)
    validate.main()



def inventory():
    path = ROOT / 'standard/dxf-inventory.json'
    assert path.is_file(), 'WP3 requires standard/dxf-inventory.json'
    return json.loads(path.read_text())


def test_every_field_url_is_an_inventory_item_page():
    bad = [(i, f['id'], f['reference']['url']) for i, f in fields()
           if not ITEM_URL.fullmatch(f['reference']['url'])]
    assert not bad, bad
    urls = {r['reference_url'].split('#')[0] for r in inventory()}
    # Exceptions must explicitly explain why an owning item page does not exist.
    for i, f in fields():
        ref = f['reference']
        assert ref['url'].split('#')[0] in urls or re.search(
            r'no (?:individual |item |specific )?page|no .*page exists', ref['basis'], re.I), (i, f['id'])


@pytest.mark.parametrize('script', ['create.py', 'phase2.py'])
def test_intent_authors_emit_typed_item_references(tmp_path, monkeypatch, script):
    # These author expectations only; no generator modules or drawings are run.
    shutil.copytree(ROOT / 'intent', tmp_path / 'intent')
    monkeypatch.syspath_prepend(str(tmp_path / 'intent'))
    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(tmp_path / 'intent' / script), run_name='__main__')
    names = ['background_layers.json', 'background_styles.json'] if script == 'create.py' else ['feature_b_geometry.json']
    for name in names:
        data = json.loads((tmp_path / 'intent' / name).read_text())
        assert data['expected']
        for f in data['expected']:
            assert f['reference'].get('basis_type') in BASIS_TYPES, (name, f['id'])
            assert ITEM_URL.fullmatch(f['reference']['url']), (name, f['id'])


def standard_modules(monkeypatch):
    for name in ('build_inventory.py', 'check_inventory.py', 'README.md'):
        assert (ROOT / 'standard' / name).is_file(), name
    monkeypatch.syspath_prepend(str(ROOT / 'standard'))
    return importlib.import_module('build_inventory'), importlib.import_module('check_inventory')


def test_standard_inventory_passes_checker(monkeypatch):
    records = inventory()
    builder, checker = standard_modules(monkeypatch)
    checker.validate(records, builder.read_intents(ROOT))


def test_inventory_statuses_equal_builder_computation(monkeypatch):
    records = inventory()
    builder, _ = standard_modules(monkeypatch)
    rebuilt, _ = builder.build(ROOT)  # Read-only analysis, never builder.main().
    statuses = lambda rows: {(r['kind'], r['name']): r['dataset']['status'] for r in rows}
    assert statuses(records) == statuses(rebuilt)


def test_coverage_standard_section_counts_match_inventory():
    text = (ROOT / 'COVERAGE.md').read_text()
    sections = re.split(r'(?m)^#{1,6} ', text)
    section = next((s for s in sections if 'standard' in s.split('\n')[0].lower()), None)
    assert section is not None, 'Missing standard coverage section'
    assert 'standard/dxf-inventory.json' in section
    counts = Counter(r['dataset']['status'] for r in inventory())
    for status in ('included', 'partial', 'present', 'future', 'omitted'):
        # Accept status/count rows or prose such as "included: 42".
        assert re.search(r'\b' + status + r'\b\s*[:|=–—-]?\s*' + str(counts[status]) + r'\b', section, re.I), (status, counts[status])


@pytest.mark.parametrize('changed', ['reference_changed', 'reference_removed', 'title', 'description',
                                     'all_field_keys', 'recomputed_width_relative_tolerance', 'invented_key'])
def test_stamp_tracks_scoring_inputs_only(tmp_path, changed):
    from checker.scoring import stamp
    sample = deepcopy(next(i for i in intents() if i['intent_id'] == 'feature_b_geometry'))
    path = tmp_path / 'intent' / (sample['intent_id'] + '.json')
    path.parent.mkdir()
    path.write_text(json.dumps(sample))
    before = stamp(tmp_path, sample['intent_id'])
    field = sample['expected'][0]
    if changed == 'all_field_keys':
        for key in field.keys() - {'reference'}:
            altered = deepcopy(sample)
            altered['expected'][0][key] = {'changed': True}
            path.write_text(json.dumps(altered))
            assert stamp(tmp_path, sample['intent_id']) != before, key
        return
    if changed == 'reference_changed':
        field['reference']['basis'] = 'Revised citation explanation'
    elif changed == 'reference_removed':
        field.pop('reference')
    elif changed in ('title', 'description'):
        sample[changed] = 'Changed intent metadata'
    else:
        field[changed] = 0.123
    path.write_text(json.dumps(sample))
    after = stamp(tmp_path, sample['intent_id'])
    assert (after == before) == (changed in ('reference_changed', 'reference_removed', 'title', 'description'))


def test_reference_helper_requires_explicit_basis_type(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'intent'))
    from references import author_references
    sample = deepcopy(next(i for i in intents() if i['intent_id'] == 'feature_b_geometry'))
    sample['expected'] = sample['expected'][:1]
    path = tmp_path / 'temporary_intent.json'
    path.write_text(json.dumps(sample))
    author_references(json.loads(path.read_text()))  # Explicit type is accepted.
    sample['expected'][0]['reference'].pop('basis_type')
    path.write_text(json.dumps(sample))
    with pytest.raises((ValueError, AssertionError, KeyError)):
        author_references(json.loads(path.read_text()))


def test_fit_width_tolerances_are_compatibility_policy():
    expected_ids = {'F01_text_fit.width', 'F03_attdef_fit.width', 'F05_attrib_fit.width'}
    matches = [f for i, f in fields() if i == 'feature_a_text' and f['id'] in expected_ids]
    assert {f['id'] for f in matches} == expected_ids
    assert not [(f['id'], f['reference']['basis_type']) for f in matches
                if f['reference']['basis_type'] != 'compatibility_policy']


def test_application_semantics_names_published_source():
    # A bare mention of Autodesk or an application object is not a document title.
    source = re.compile(r'https?://\S+|Autodesk.{0,100}(?:Reference|Guide|Help|Manual|Documentation)', re.I)
    bad = [(i, f['id'], f['reference']['basis']) for i, f in fields()
           if f['reference']['basis_type'] == 'application_semantics'
           and not source.search(f['reference']['basis'])]
    assert not bad, bad


def test_scale_list_fields_do_not_cite_proxy_pages():
    proxies = {r['reference_url'].split('#')[0] for r in inventory()
               if r['name'] in ('ACAD_PROXY_ENTITY', 'ACAD_PROXY_OBJECT')}
    matches = [(i, f) for i, f in fields() if f['selector'].get('dictionary') == 'ACAD_SCALELIST']
    assert matches, 'Missing scale-list expectations'
    assert not [(i, f['id']) for i, f in matches
                if f['reference']['url'].split('#')[0] in proxies]


def test_validator_rejects_item_not_matching_selector(tmp_path, monkeypatch):
    from intent import validate
    sample = deepcopy(next(i for i in intents() if i['intent_id'] == 'feature_b_geometry'))
    field = deepcopy(next(f for f in sample['expected']
                          if f['selector'].get('table') == 'CIRCLE'
                          and f['selector'].get('attr') == 'radius'))
    sample['expected'] = [field]
    sample.pop('feature_fields', None)
    directory = tmp_path / 'intent'
    directory.mkdir()
    for name in ('intent.schema.json', 'provenance.schema.json'):
        shutil.copyfile(ROOT / 'intent' / name, directory / name)
    shutil.copytree(ROOT / 'standard', tmp_path / 'standard')
    path = directory / 'feature_b_geometry.json'
    path.write_text(json.dumps(sample))
    monkeypatch.setattr(validate, 'R', tmp_path)
    validate.main()
    field['reference']['url'] = next(r['reference_url'] for r in inventory()
                                     if r['kind'] == 'entity' and r['name'] == 'LINE')
    path.write_text(json.dumps(sample))
    with pytest.raises((ValidationError, AssertionError, ValueError)):
        validate.main()


def test_inventory_uses_five_status_values():
    assert {r['dataset']['status'] for r in inventory()} == {
        'included', 'partial', 'present', 'future', 'omitted'}


def test_cited_inventory_items_are_never_future_or_omitted():
    cited = {f['reference']['url'].split('#')[0] for _, f in fields()}
    bad = [(r['kind'], r['name'], r['dataset']['status']) for r in inventory()
           if r['reference_url'].split('#')[0] in cited
           and r['dataset']['status'] in ('future', 'omitted')]
    assert not bad, bad


def test_cited_proxy_object_is_not_future():
    record = next(r for r in inventory() if r['name'] == 'ACAD_PROXY_OBJECT')
    matches = [(i, f['id']) for i, f in fields()
               if f['reference']['url'].split('#')[0] == record['reference_url'].split('#')[0]]
    assert matches, 'Expected proxy-object citations to exercise this regression'
    assert record['dataset']['status'] not in ('future', 'omitted'), matches


def test_most_header_variables_are_present():
    headers = [r for r in inventory() if r['kind'] == 'header']
    assert headers
    counts = Counter(r['dataset']['status'] for r in headers)
    assert counts['present'] > len(headers) / 2, counts


def test_hand_set_status_judgments_have_documented_reasons(monkeypatch):
    builder, _ = standard_modules(monkeypatch)
    readme = (ROOT / 'standard/README.md').read_text()
    # PARTIAL_FORMS is the builder's explicit status override; SPECIAL_NOTES
    # supplies its reasons. Presence-derived statuses are not hand-set judgments.
    judgments = builder.PARTIAL_FORMS
    assert judgments, 'Expected documented judgments about incomplete forms'
    for key in sorted(judgments):
        reason = builder.SPECIAL_NOTES.get(key)
        assert reason, key
        assert key[1] in readme and reason in readme, (key, reason)
