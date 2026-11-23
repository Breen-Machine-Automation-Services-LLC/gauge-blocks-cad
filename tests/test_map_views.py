# Expected builder functions: main_view_rows(root), comparison_rows(writer, resaver, root).
"""WP6 acceptance tests; synthetic inputs, no CAD, browser, or regeneration.

Builder contract expected (root is a Path; functions must not write files):
  main_view_rows(root) -> {programs: [...], groups: [{kind, rows: [...]}]}
  comparison_rows(writer, resaver, root) -> {declared, label, groups, summary}
Main rows retain inventory name/reference_url; dataset is a labeled cell with
intents, and programs maps program IDs to reads/writes/round_trip labeled cells.
Every cell has status, label, icon, evidence (raw result rows or provenance),
and detail_link. Links use #detailed?item=...&program=... (comparison also pair).
Round-trip cells add kept/total (distinct measured features); comparison rows add
intent_id, feature, native (bool), and round_trip with kept/total slot counts.
Program headers have id/name/engine/shared_engine/label. Summary has total,
kept, changed, lost, refused, not_measured, and a label naming the denominator.

Spec assumptions, pending owner clarification: exclude wholly not_scored features
from main measured denominator; mixed scored/not_scored is not fully kept;
refused gets its own summary bucket so all features reconcile. A comparison's
slot denominator includes not_scored slots. Reads means measured, not conformant.
UI contract: view options main/comparison/detailed; main defaults; detailed links
are supplied in data and consumed by template. Existing topics/columns stay.
"""
import contextlib
import importlib.util
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ('ezdxf', 'oda', 'bricscad', 'cadcraft')


def write_json(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value))


@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location('wp6_map_builder', ROOT / 'map/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path
    for folder in ('intent', 'native', 'cross', 'results', 'programs', 'standard', 'map'):
        (root / folder).mkdir()
    (root / 'map/template.html').write_text((ROOT / 'map/template.html').read_text())
    items = [
        ('header', '$MEASUREMENT', 'future', []),
        ('table', 'LAYER', 'partial', ['layers']),
        ('entity', 'TEXT', 'included', ['text']),
        ('object', 'DICTIONARY', 'present', []),
        ('entity', 'HELIX', 'omitted', []),
    ]
    inventory = [dict(kind=k, name=n, reference_url='https://example.invalid/reference/' + n,
                      dataset=dict(status=s, intents=ids, note='Synthetic inventory'))
                 for k, n, s, ids in items]
    write_json(root, 'standard/dxf-inventory.json', inventory)
    caps = {p: dict(name={'oda': 'ODA File Converter', 'bricscad': 'BricsCAD',
                         'cadcraft': 'CADCraft', 'ezdxf': 'ezdxf'}[p],
                    engine='oda-teigha' if p in ('oda', 'bricscad') else p,
                    outputs=[['DXF', '2000', 'ASCII'], ['DXF', '2018', 'binary'],
                             ['DWG', '2018', 'binary']]) for p in PROGRAMS}
    write_json(root, 'programs/capabilities.json', caps)
    pairs = [dict(writer='ezdxf', resaver=p, sources='native/ezdxf')
             for p in ('cadcraft', 'oda', 'bricscad')]
    pairs.append(dict(writer='bricscad', resaver='oda', sources='native/bricscad'))
    write_json(root, 'programs/pairs.json', pairs)
    fields = {'Aligned': ['align', 'width'], 'Fit': ['fit'], 'Missing': ['missing'],
              'Refused': ['refused'], 'Unsupported': ['unsupported']}
    for intent_id, mapping, item in [('text', fields, 'TEXT'),
                                     ('layers', {'Color': ['color']}, 'LAYER')]:
        intent = dict(intent_id=intent_id, title=intent_id, representation_id='reference_1',
                      features=list(mapping), feature_fields=mapping,
                      expected=[dict(id=f, value=7, versions=['AC1015', 'AC1032'],
                                     selector=dict(kind='query_count', query=item),
                                     reference=dict(url='https://example.invalid/reference/' + item,
                                                    basis_type='synthetic'))
                                for ids in mapping.values() for f in ids])
        write_json(root, f'intent/{intent_id}.json', intent)
    rows = []

    def drawing(intent, program, pair='', version='2000', fmt='DXF'):
        encoding = 'ASCII' if version == '2000' else 'binary'
        path = f'{"cross/" + pair if pair else "native/" + program}/{intent}_{version}.{fmt.lower()}'
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('Synthetic placeholder; never parsed as a drawing')
        digest = f'{intent}-{program}-{version}-{fmt}'
        meta = dict(intent_id=intent, representation_id='reference_1', program=program,
                    build='synthetic-public', format=fmt, version=version, encoding=encoding,
                    content_digest=digest, ezdxf_based=program == 'ezdxf')
        if pair:
            meta['made_by'] = dict(input_digest=f'{intent}-{pair.split("__")[0]}-{version}-DXF')
        write_json(root, path + '.provenance.json', meta)
        return path

    def check(path, field, status, shared=False):
        rows.append(dict(file=path, intent_id='layers' if 'layers_' in path else 'text',
                         field=field, status=status, expected=7,
                         actual=7 if status == 'same' else None, reader='ezdxf synthetic-public',
                         converter='oda synthetic-public' if path.endswith('.dwg') else None,
                         shared_engine=shared))

    for version in ('2000', '2018'):
        native = drawing('text', 'ezdxf', version=version)
        for ids in fields.values():
            for field in ids:
                check(native, field, 'same')
        for program in ('cadcraft', 'oda', 'bricscad'):
            path = drawing('text', program, 'ezdxf__' + program, version)
            for field in ('align', 'width', 'fit', 'missing', 'refused', 'unsupported'):
                status = ('not_scored' if field == 'unsupported' else
                          'differs' if program == 'cadcraft' and field == 'fit' and version == '2018' else
                          'absent' if program == 'cadcraft' and field == 'missing' else
                          'refused' if program == 'cadcraft' and field == 'refused' else 'same')
                check(path, field, status)
    for program in ('ezdxf', 'bricscad'):
        check(drawing('layers', program), 'color', 'same')
    check(drawing('layers', 'bricscad', version='2018'), 'color', 'same')
    check(drawing('layers', 'cadcraft', 'ezdxf__cadcraft'), 'color', 'same')
    check(drawing('layers', 'oda', 'bricscad__oda', '2018', 'DWG'), 'color', 'same', True)
    write_json(root, 'results/fixture_checks.json', rows)
    # Duplicate observations must not inflate any denominator.
    write_json(root, 'results/duplicate_checks.json', rows[:2])
    return root


def main_rows(builder, root):
    assert callable(getattr(builder, 'main_view_rows', None)), 'WP6 requires main_view_rows(root)'
    return builder.main_view_rows(root)


def comparison(builder, root, writer='ezdxf', resaver='cadcraft'):
    assert callable(getattr(builder, 'comparison_rows', None)), 'WP6 requires comparison_rows(writer, resaver, root)'
    return builder.comparison_rows(writer, resaver, root)


def item_rows(data):
    return {row['name']: row for group in data['groups'] for row in group['rows']}


def features(data):
    return {(r['intent_id'], r['feature']): r for g in data['groups'] for r in g['rows']}


@pytest.mark.parametrize('item,status,intents', [
    ('TEXT', 'included', ['text']), ('LAYER', 'partial', ['layers']),
    ('DICTIONARY', 'present', []), ('$MEASUREMENT', 'future', []), ('HELIX', 'omitted', []),
])
def test_dataset_cells(builder, corpus, item, status, intents):
    cell = item_rows(main_rows(builder, corpus))[item]['dataset']
    assert cell['status'] == status
    assert cell['label'] == status
    assert cell['intents'] == intents


@pytest.mark.parametrize('program', PROGRAMS)
@pytest.mark.parametrize('item', ['TEXT', 'LAYER', 'DICTIONARY', '$MEASUREMENT', 'HELIX'])
def test_every_program_cell(builder, corpus, item, program):
    cells = item_rows(main_rows(builder, corpus))[item]['programs'][program]
    read = 'measured' if program == 'ezdxf' and item in ('TEXT', 'LAYER') else 'not measured'
    written = 'native drawing' if (program == 'ezdxf' and item in ('TEXT', 'LAYER') or
                                   program == 'bricscad' and item == 'LAYER') else 'no native drawing'
    expected_round_trip = {
        ('TEXT', 'cadcraft'): ('refused', 'kept 1 of 4', 1, 4),
        ('TEXT', 'oda'): ('kept', 'kept 4 of 4', 4, 4),
        ('TEXT', 'bricscad'): ('kept', 'kept 4 of 4', 4, 4),
        ('LAYER', 'cadcraft'): ('kept', 'kept 1 of 1', 1, 1),
        ('LAYER', 'oda'): ('kept', 'kept 1 of 1', 1, 1),
    }.get((item, program), ('not measured', 'not measured', 0, 0))
    assert cells['reads']['status'] == cells['reads']['label'] == read
    assert cells['writes']['status'] == cells['writes']['label'] == written
    rt = cells['round_trip']
    assert (rt['status'], rt['label'], rt['kept'], rt['total']) == expected_round_trip


@pytest.mark.parametrize('status,expected', [('same', 'kept'), ('absent', 'lost'), ('differs', 'changed')])
def test_round_trip_without_source_baseline_is_not_readable(builder, corpus, status, expected):
    rows = json.loads((corpus / 'results/fixture_checks.json').read_text())
    rows = [r for r in rows if r['file'] != 'native/bricscad/layers_2018.dxf']
    for row in rows:
        if row['file'].startswith('cross/bricscad__oda/'):
            row['status'] = status
    write_json(corpus, 'results/fixture_checks.json', rows)
    cell = item_rows(main_rows(builder, corpus))['LAYER']['programs']['oda']['round_trip']
    assert cell['status'] == expected
    if status != 'same':
        assert all(r['source_status'] == 'not measured' for r in cell['evidence'])


def test_groups_and_reference_links(builder, corpus):
    data = main_rows(builder, corpus)
    assert [g['kind'] for g in data['groups']] == ['entity', 'object', 'table', 'header']
    inventory = json.loads((corpus / 'standard/dxf-inventory.json').read_text())
    assert set(item_rows(data)) == {i['name'] for i in inventory}
    for group in data['groups']:
        for row in group['rows']:
            source = next(i for i in inventory if i['name'] == row['name'])
            assert source['kind'] == group['kind']
            assert row['reference_url'] == source['reference_url']


def test_headers_visibly_identify_shared_engine(builder, corpus):
    headers = {p['id']: p for p in main_rows(builder, corpus)['programs']}
    assert set(headers) == set(PROGRAMS)
    assert headers['oda']['name'] == 'ODA File Converter'
    for p in PROGRAMS:
        assert headers[p]['shared_engine'] is (p in ('oda', 'bricscad'))
        assert headers[p]['engine'] in headers[p]['label']
    assert headers['oda']['engine'] == headers['bricscad']['engine'] == 'oda-teigha'
    assert all('shared engine' in headers[p]['label'].lower() for p in ('oda', 'bricscad'))


@pytest.mark.parametrize('feature,status,kept,total', [
    ('Aligned', 'kept', 2, 2), ('Fit', 'changed', 1, 2),
    ('Missing', 'lost', 0, 2), ('Refused', 'refused', 0, 2),
    ('Unsupported', 'not scored', 0, 2), ('Color', 'kept', 1, 1),
])
def test_comparison_rows_worst_status_and_slot_counts(builder, corpus, feature, status, kept, total):
    data = comparison(builder, corpus)
    assert data['declared'] is True
    rows = features(data)
    assert set(rows) == {('text', f) for f in ('Aligned', 'Fit', 'Missing', 'Refused', 'Unsupported')} | {('layers', 'Color')}
    row = rows[('layers' if feature == 'Color' else 'text', feature)]
    assert row['native'] is True
    rt = row['round_trip']
    assert (rt['status'], rt['kept'], rt['total']) == (status, kept, total)
    assert status in rt['label'] and str(total) in rt['label']
    assert {r['reader'] for r in rt['evidence']} == {'ezdxf synthetic-public'}
    assert {r['converter'] for r in rt['evidence']} == {None}
    assert {r['field'] for r in rt['evidence']} == {
        'Aligned': {'align', 'width'}, 'Fit': {'fit'}, 'Missing': {'missing'},
        'Refused': {'refused'}, 'Unsupported': {'unsupported'}, 'Color': {'color'},
    }[feature]
    group = next(g for g in data['groups'] if row in g['rows'])
    assert group['name'] == ('LAYER' if feature == 'Color' else 'TEXT')


def test_comparison_summary_counts_features_not_fields_or_slots(builder, corpus):
    summary = comparison(builder, corpus)['summary']
    assert {k: summary[k] for k in ('total', 'kept', 'changed', 'lost', 'refused', 'not_measured')} == {
        'total': 6, 'kept': 2, 'changed': 1, 'lost': 1, 'refused': 1, 'not_measured': 1}
    assert '6' in summary['label'] and 'features' in summary['label']


def test_undeclared_pair_is_unknown_even_with_stray_results(builder, corpus):
    rows = json.loads((corpus / 'results/fixture_checks.json').read_text())
    stray = [dict(r, file=r['file'].replace('ezdxf__cadcraft', 'cadcraft__ezdxf'), status='same')
             for r in rows if 'ezdxf__cadcraft' in r['file']]
    write_json(corpus, 'results/stray_checks.json', stray)
    data = comparison(builder, corpus, 'cadcraft', 'ezdxf')
    assert data['declared'] is False
    assert data['label'] == 'not measured'
    assert data['summary']['kept'] == 0
    assert all(r['round_trip']['status'] == 'not measured' for r in features(data).values())


def test_declared_pair_without_measurements_is_unknown(builder, corpus):
    for path in (corpus / 'results').glob('*.json'):
        write_json(corpus, path.relative_to(corpus), [])
    data = comparison(builder, corpus)
    assert data['declared'] is True
    assert data['summary']['not_measured'] == data['summary']['total'] == 6
    assert all(r['round_trip']['status'] == 'not measured' for r in features(data).values())


def test_converter_evidence_shared_engine_and_non_native_writer(builder, corpus):
    data = comparison(builder, corpus, 'bricscad', 'oda')
    row = features(data)[('layers', 'Color')]
    assert row['native'] is True
    evidence = row['round_trip']['evidence']
    assert len(evidence) == 1
    assert evidence[0]['reader'] == 'ezdxf synthetic-public'
    assert evidence[0]['converter'] == 'oda synthetic-public'
    assert row['round_trip']['shared_engine'] is True
    assert 'shared engine' in row['round_trip']['label'].lower()
    assert features(data)[('text', 'Aligned')]['native'] is False


def test_not_scored_never_becomes_kept_or_lost(builder, corpus):
    for path in (corpus / 'results').glob('*.json'):
        rows = json.loads(path.read_text())
        write_json(corpus, path.relative_to(corpus), [dict(r, status='not_scored') for r in rows])
    for row in item_rows(main_rows(builder, corpus)).values():
        for cells in row['programs'].values():
            assert cells['reads']['status'] == 'not measured'
            assert cells['round_trip']['status'] == 'not measured'
            assert cells['round_trip']['kept'] == cells['round_trip']['total'] == 0
    summary = comparison(builder, corpus)['summary']
    assert summary['not_measured'] == summary['total'] == 6
    assert summary['kept'] == summary['lost'] == 0


def test_mixed_not_scored_feature_is_not_fully_kept(builder, corpus):
    path = corpus / 'results/fixture_checks.json'
    rows = json.loads(path.read_text())
    for r in rows:
        if 'ezdxf__oda/text_2018' in r['file'] and r['field'] == 'width':
            r['status'] = 'not_scored'
    write_json(corpus, 'results/fixture_checks.json', rows)
    rt = item_rows(main_rows(builder, corpus))['TEXT']['programs']['oda']['round_trip']
    assert (rt['kept'], rt['total']) == (3, 4)
    assert rt['status'] != 'kept'


def test_capabilities_alone_cannot_supply_cells(builder, corpus):
    before = main_rows(builder, corpus)
    caps = json.loads((corpus / 'programs/capabilities.json').read_text())
    for c in caps.values():
        c['outputs'] = []
    write_json(corpus, 'programs/capabilities.json', caps)
    assert main_rows(builder, corpus) == before


def test_every_cell_has_label_icon_and_filtered_detailed_link(builder, corpus):
    data = main_rows(builder, corpus)
    for item, row in item_rows(data).items():
        for program, cells in row['programs'].items():
            for cell in cells.values():
                assert cell['status'] and cell['label'].strip() and cell['icon'].strip()
                fragment = urlsplit(cell['detail_link']).fragment
                target, _, query = fragment.partition('?')
                assert target == 'detailed'
                assert parse_qs(query) == {'item': [item], 'program': [program]}
                assert isinstance(cell['evidence'], list)
        assert row['dataset']['label'] and row['dataset']['icon']
    for row in features(comparison(builder, corpus)).values():
        cell = row['round_trip']
        assert cell['status'] and cell['label'] and cell['icon']
        fragment = urlsplit(cell['detail_link']).fragment
        assert fragment.startswith('detailed?')
        assert parse_qs(fragment.partition('?')[2])['pair'] == ['ezdxf__cadcraft']


def test_main_evidence_retains_fields_files_and_statuses(builder, corpus):
    cell = item_rows(main_rows(builder, corpus))['TEXT']['programs']['cadcraft']['round_trip']
    assert {r['status'] for r in cell['evidence']} == {'same', 'differs', 'absent', 'refused', 'not_scored'}
    assert {r['field'] for r in cell['evidence']} == {'align', 'width', 'fit', 'missing', 'refused', 'unsupported'}
    assert all(r['file'].startswith('cross/ezdxf__cadcraft/') for r in cell['evidence'])
    native = item_rows(main_rows(builder, corpus))['LAYER']['programs']['bricscad']['writes']
    assert any(r.get('program') == 'bricscad' for r in native['evidence'])


def test_table_functions_are_read_only(builder, corpus):
    before = {p.relative_to(corpus): p.read_bytes() for p in corpus.rglob('*') if p.is_file()}
    main_rows(builder, corpus)
    comparison(builder, corpus)
    after = {p.relative_to(corpus): p.read_bytes() for p in corpus.rglob('*') if p.is_file()}
    assert after == before


class ViewOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_view = False
        self.options = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'select':
            self.in_view = attrs.get('id') == 'view'
        if tag == 'option' and self.in_view:
            self.current = dict(value=attrs.get('value'), selected='selected' in attrs, text='')
            self.options.append(self.current)

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'option':
            self.current = None
        if tag == 'select':
            self.in_view = False


def test_template_defaults_to_main_and_retains_linked_detailed_view(builder, corpus, monkeypatch):
    # Only run main against this temporary corpus, never the repository ROOT.
    monkeypatch.setattr(builder, 'ROOT', corpus)
    with contextlib.redirect_stdout(io.StringIO()):
        builder.main()
    page = (corpus / 'map/index.html').read_text()
    parser = ViewOptions()
    parser.feed(page)
    options = {o['value']: o for o in parser.options}
    assert {'main', 'comparison', 'detailed'} <= options.keys()
    assert options['main']['text'].strip() == 'Standard and programs'
    assert options['comparison']['text'].strip() == 'Program A to program B'
    assert options['detailed']['text'].strip() == 'Detailed coverage and compatibility'
    selected = [o['value'] for o in parser.options if o['selected']]
    assert (selected or [parser.options[0]['value']]) == ['main']
    # Preserve the old drill-down payload and publish both computed views.
    payload = json.loads(re.search(r'const DATA=(.*?);\s*\n', page).group(1))
    assert payload['topics'] and payload['columns']
    assert payload['main_view'] == main_rows(builder, corpus)
    assert payload['comparisons']['ezdxf__cadcraft'] == comparison(builder, corpus)
    assert 'detail_link' in page[page.index('</style>'):]
