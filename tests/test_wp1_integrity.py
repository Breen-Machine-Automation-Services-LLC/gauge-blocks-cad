"""WP1 behavioral contracts; all drawings and result files here are synthetic."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
from unittest.mock import Mock

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('CAD_DATASET_SETTINGS', str(ROOT / 'settings.example.json'))
from checker import core
from generators import run_cross


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def intent(doc):
    return {'intent_id': 'synthetic', 'expected': [dict(id='value', value=1, tolerance=0,
            versions=[doc.dxfversion], selector={'kind': 'layer_count'})]}


def scored(doc, selector):
    i = intent(doc)
    i['expected'][0]['selector'] = selector
    return core.compare(doc, i, 'test')[0]


def test_ambiguous_dictionary_is_not_scored():
    doc = ezdxf.new()
    dictionary = doc.rootdict.add_new_dict('SYNTHETIC')
    dictionary.add_dict_var('Key', 'one')
    dictionary.add_dict_var('KEY', 'two')
    row = scored(doc, dict(kind='object', dictionary='SYNTHETIC', name='key', attr='value'))
    assert row['status'] == 'not_scored'
    assert 'ambigu' in row['detail'].lower()


@pytest.mark.parametrize('selector,reason', [
    ({'kind': 'query_count', 'name': '*[color>1]'}, 'query'),
    ({'kind': 'unknown_selector'}, 'unknown'),
])
def test_unsupported_forms_are_not_scored(selector, reason):
    row = scored(ezdxf.new(), selector)
    assert row['status'] == 'not_scored'
    assert reason in row['detail'].lower()


def test_arbitrary_extraction_exception_is_reader_error(monkeypatch):
    def broken(*args):
        raise RuntimeError('synthetic checker failure')
    monkeypatch.setattr(core, 'extract', broken)
    row = scored(ezdxf.new(), {'kind': 'layer_count'})
    assert row['status'] == 'reader_error'
    assert 'RuntimeError' in row['detail']
    assert 'synthetic checker failure' in row['detail']


@pytest.mark.parametrize('selector', [
    {'kind': 'feature_attr', 'table': 'LINE', 'name': 'MISSING', 'attr': 'color'},
    {'kind': 'table', 'table': 'layers', 'name': 'MISSING', 'attr': 'color'},
    {'kind': 'object', 'dictionary': 'ROOT', 'name': 'MISSING', 'attr': 'value'},
    {'kind': 'table', 'table': 'layers', 'name': '0', 'attr': 'missing_attribute'},
])
def test_missing_values_are_absent(selector):
    assert scored(ezdxf.new(), selector)['status'] == 'absent'


@pytest.fixture
def cross_case(tmp_path, monkeypatch):
    doc = ezdxf.new('R2000')
    doc.layers.new('ZEV_ONE')
    i = intent(doc)
    dump(tmp_path / 'intent/synthetic.json', i)
    src = tmp_path / 'native/ezdxf/sample.dxf'
    src.parent.mkdir(parents=True)
    src.write_text('source')
    dest = tmp_path / 'cross/ezdxf__oda/sample.dxf'
    dest.parent.mkdir(parents=True)
    dest.write_text('existing output')
    side = dict(intent_id='synthetic', content_digest='source-digest', ezdxf_based=True)
    dump(dest.with_suffix('.dxf.provenance.json'), {'made_by': {'input_digest': 'source-digest'}, 'build': 'fake-build'})
    old = dict(file='cross/ezdxf__oda/sample.dxf', intent_id='synthetic', field='value',
               reader='ezdxf test', converter=None, status='same', scored_with={'checker': 'old', 'intent': 'old'})
    dump(tmp_path / 'results/cross_ezdxf__oda_checks.json', [old])
    save = Mock(side_effect=AssertionError('up-to-date drawing was resaved'))
    reader = Mock(return_value=doc)
    class Fake:
        name = 'oda'
        build = 'fake-build'
        save_many = save
    monkeypatch.setattr(run_cross, 'R', tmp_path)
    monkeypatch.setattr(run_cross, 'ADAPTERS', {'oda': Fake, 'bricscad': Fake})
    monkeypatch.setattr(run_cross, 'jobs_for', lambda *a, **k: [(src, dest, 'DXF', '2000', 'ASCII', side)])
    monkeypatch.setattr(run_cross.ezdxf, 'readfile', reader)
    monkeypatch.setattr(run_cross, 'log', lambda *a: None)
    return tmp_path, save, reader


@pytest.mark.parametrize('changed', ['checker', 'intent'])
def test_cross_rescores_existing_output_without_resaving(cross_case, changed):
    root, save, reader = cross_case
    path = root / 'results/cross_ezdxf__oda_checks.json'
    rows = json.loads(path.read_text())
    rows[0]['scored_with'][changed] = 'changed-' + changed
    dump(path, rows)
    run_cross.run_pair('ezdxf__oda')
    save.assert_not_called()
    reader.assert_called_once_with(root / 'cross/ezdxf__oda/sample.dxf')
    assert json.loads(path.read_text())[0]['scored_with'] != rows[0]['scored_with']


def test_old_independent_result_name_is_gone():
    old = 'cross_ezdxf__oda_' + 'independent_checks.json'
    assert not (ROOT / 'results' / old).exists()
    for folder in ('checker', 'generators', 'map', 'programs'):
        for p in (ROOT / folder).rglob('*.py'):
            assert old not in p.read_text(), p
    retired = 'cross_ezdxf__oda_' + 'read_by_bricscad_checks.json'
    assert not (ROOT / 'results' / retired).exists()


def test_viewport_color_basis_and_value():
    # create.py authors the expectation; run in a temporary directory, never repository data.
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'create.py'
        shutil.copyfile(ROOT / 'intent/create.py', source)
        runpy.run_path(str(source), run_name='__main__')
        data = json.loads((Path(td) / 'background_layers.json').read_text())
    field = next(f for f in data['expected'] if f['id'] == 'vp.color')
    assert field['value'] == 6
    basis = field['reference']['basis'].lower()
    assert 'compatibility' in basis and 'policy' in basis and 'provisional' in basis
    assert 'standard' in basis


@pytest.fixture
def builder_case(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('wp1_map', ROOT / 'map/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    for folder in ('intent', 'native/ezdxf', 'cross/ezdxf__oda', 'results', 'programs', 'map'):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / 'map/template.html').write_text((ROOT / 'map/template.html').read_text())
    dump(tmp_path / 'programs/pairs.json', [dict(writer='ezdxf', resaver='oda', sources='native/ezdxf')])
    dump(tmp_path / 'programs/capabilities.json', {
        'ezdxf': {'name': 'ezdxf', 'outputs': [['DXF', '2000', 'ASCII']]},
        'oda': {'name': 'ODA', 'outputs': [['DXF', '2000', 'ASCII']]}})
    dump(tmp_path / 'intent/synthetic.json', {'intent_id': 'synthetic', 'title': 'Synthetic',
        'expected': [{'id': 'value', 'value': 1, 'versions': ['AC1015']}]})
    for path, program, digest, source in [('native/ezdxf/test.dxf', 'ezdxf', 'input', None),
                                          ('cross/ezdxf__oda/test.dxf', 'oda', 'output', 'input')]:
        (tmp_path / path).write_text('fixture')
        dump(tmp_path / (path + '.provenance.json'), dict(intent_id='synthetic', program=program,
             build='test', format='DXF', version='2000', encoding='ASCII', content_digest=digest,
             made_by={'input_digest': source}))
    row = dict(file='cross/ezdxf__oda/test.dxf', field='value', reader='test', converter=None,
               status='not_scored', detail='unsupported query')
    dump(tmp_path / 'results/checks.json', [row])
    dump(tmp_path / 'results/cross_ezdxf__oda_checks.json', [row])
    return tmp_path, builder, row


def map_cell(root):
    data = json.loads((root / 'map/index.html').read_text().split('const DATA=')[1].split(';\nconst icons=')[0])
    return data['topics'][0]['features'][0]['cells'][data['columns'].index(['DXF', '2000', 'ASCII'])]


def test_map_counts_duplicate_observation_once(builder_case, capsys):
    root, builder, row = builder_case
    builder.main()
    assert '1 measured fields' in capsys.readouterr().out
    assert len(map_cell(root)['runs'][0]['diffs']) == 1


def test_map_shows_not_scored_separately(builder_case):
    root, builder, row = builder_case
    builder.main()
    assert map_cell(root)['runs'][0]['status'] == 'not_scored'


def coverage_cells(builder_case, monkeypatch, status):
    from generators import write_coverage
    root, builder, row = builder_case
    row['status'] = status
    dump(root / 'results/checks.json', [row])
    dump(root / 'results/cross_ezdxf__oda_checks.json', [row])
    monkeypatch.setattr(write_coverage, 'R', root)
    monkeypatch.setattr(write_coverage, 'build_map', builder.main)
    write_coverage.main()
    lines = (root / 'COVERAGE.md').read_text().splitlines()
    header = next(line for line in lines if line.startswith('| Set |'))
    values = next(line for line in lines if line.startswith('| cross/ezdxf__oda |'))
    return dict(zip([x.strip() for x in header.split('|')[1:-1]],
                    [x.strip() for x in values.split('|')[1:-1]]))


def test_coverage_counts_duplicate_observation_once(builder_case, monkeypatch):
    cells = coverage_cells(builder_case, monkeypatch, 'same')
    assert cells['Rows same'] == '1'


def test_coverage_shows_not_scored_separately(builder_case, monkeypatch):
    cells = coverage_cells(builder_case, monkeypatch, 'not_scored')
    assert cells['Rows absent'] == '0'
    assert cells['Rows not scored'] == '1'


@pytest.fixture(autouse=True)
def no_external_programs(monkeypatch):
    # Every runner test must install an in-process fake at the adapter boundary.
    import subprocess
    monkeypatch.setattr(subprocess, 'Popen', Mock(side_effect=AssertionError('external program launched')))


def expected_stamp(root, intent_id):
    from checker.scoring import stamp
    return stamp(root, intent_id)


def assert_stamp(rows, root, intent_id):
    assert rows
    assert all(row.get('scored_with') == expected_stamp(root, intent_id) for row in rows)


def assert_engines(rows, writer, reader):
    assert rows
    for row in rows:
        assert row.get('writer_engine') == writer
        assert row.get('reader_engine') == reader
        assert row.get('shared_engine') is (writer == reader)


@pytest.fixture
def runner_case(tmp_path, monkeypatch):
    import tempfile
    import regenerate
    from generators import run_features, run_bricscad
    doc = ezdxf.new('R2000')
    i = intent(doc)
    i.update(representation_id='synthetic', title='Synthetic')
    i['expected'][0]['value'] = 0  # no ZEV_ layers in this independently authored drawing
    for name in ('synthetic', 'feature_synthetic'):
        dump(tmp_path / 'intent' / (name + '.json'), dict(i, intent_id=name))
    for folder in ('results', 'generators', 'native/ezdxf'):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    (tmp_path / 'generators/background.py').write_text('# synthetic generator')
    (tmp_path / 'generators/features.py').write_text('# synthetic features')
    saves = Mock()
    opens = Mock(return_value=doc)

    class FakeEzdxf:
        name = 'ezdxf'
        engine = 'ezdxf'
        build = 'synthetic-build'
        def save(self, drawing, path, *args):
            saves(path)
            Path(path).write_text('synthetic drawing')
        def open(self, path):
            return opens(path)

    class FakeOda:
        name = 'oda'
        engine = 'oda-teigha'
        build = 'synthetic-build'
        def read_dwg_many(self, paths):
            return {p: doc for p in paths}
        def save_many(self, jobs):
            assert not jobs, 'unexpected binary conversion'
            return {}

    for module, attr in ((regenerate, 'ROOT'), (run_features, 'R'), (run_bricscad, 'R')):
        monkeypatch.setattr(module, attr, tmp_path)
    monkeypatch.setattr(regenerate, 'Ezdxf', FakeEzdxf)
    monkeypatch.setattr(regenerate, 'Oda', FakeOda)
    monkeypatch.setattr(regenerate, 'build', lambda *args: doc)
    monkeypatch.setattr(run_features, 'Ezdxf', FakeEzdxf)
    monkeypatch.setattr(run_features, 'TOPICS', ['synthetic'])
    monkeypatch.setattr(run_features, 'VERSIONS', {'2000': 'AC1015'})
    monkeypatch.setattr(run_features, 'build', lambda *args: doc)
    monkeypatch.setattr(run_bricscad, 'Oda', FakeOda)
    class FakeBrics(FakeOda):
        name = 'bricscad'
    monkeypatch.setattr(run_bricscad, 'BricsCad', FakeBrics)
    monkeypatch.setattr(run_bricscad, 'TOPICS', {'k_tables': 'synthetic'})
    monkeypatch.setattr(run_bricscad, 'VERSIONS', {'2000': 'AC1015'})
    lsp = tmp_path / 'generators/synthetic.lsp'
    lsp.write_text('; synthetic')
    monkeypatch.setattr(run_bricscad, 'LSP', lsp)
    monkeypatch.setattr(run_bricscad, 'workdir', lambda prefix: tempfile.mkdtemp(dir=tmp_path, prefix=prefix))
    def fake_script(script, run, *args):
        out = run.parent / 'out'
        (out / 'make_bricscad_masters.log').write_text('synthetic')
        for suffix in ('2000_ASCII.dxf', '2000_binary.dwg'):
            (out / ('k_tables_' + suffix)).write_text('synthetic drawing')
        return 0
    monkeypatch.setattr(run_bricscad, 'run_script', fake_script)
    monkeypatch.setattr(run_bricscad.ezdxf, 'readfile', opens)
    monkeypatch.setattr(run_bricscad.privacy, 'assert_clean', lambda p: None)
    return tmp_path, doc, i, saves, opens


def run_native(case):
    import regenerate
    root, doc, i, saves, opens = case
    return regenerate.run_case((i, 'synthetic', '2000', 'ASCII', 'synthetic-input'), cross=False)[0]


@pytest.mark.parametrize('runner', ['native', 'feature', 'bricscad'])
def test_runner_writes_correct_stamp(runner_case, runner):
    root = runner_case[0]
    if runner == 'native':
        rows = run_native(runner_case)
        iid = 'synthetic'
    elif runner == 'feature':
        from generators import run_features
        run_features.main()
        rows = json.loads((root / 'results/features_checks.json').read_text())
        iid = 'feature_synthetic'
    else:
        from generators import run_bricscad
        run_bricscad.main()
        rows = json.loads((root / 'results/native_bricscad_checks.json').read_text())
        iid = 'synthetic'
    assert_stamp(rows, root, iid)


@pytest.mark.parametrize('runner', ['native', 'feature', 'bricscad'])
def test_runner_engine_fields(runner_case, runner):
    root = runner_case[0]
    if runner == 'native':
        assert_engines(run_native(runner_case), 'ezdxf', 'ezdxf')
    elif runner == 'feature':
        from generators import run_features
        run_features.main()
        assert_engines(json.loads((root / 'results/features_checks.json').read_text()), 'ezdxf', 'ezdxf')
    else:
        from generators import run_bricscad
        run_bricscad.main()
        rows = json.loads((root / 'results/native_bricscad_checks.json').read_text())
        for suffix, reader in (('.dxf', 'ezdxf'), ('.dwg', 'oda-teigha')):
            assert_engines([r for r in rows if r['file'].endswith(suffix)], 'oda-teigha', reader)


@pytest.mark.parametrize('runner', ['native', 'feature'])
@pytest.mark.parametrize('changed', ['checker', 'intent', 'missing'])
def test_native_and_feature_rescore_without_save(runner_case, runner, changed):
    root, doc, i, saves, opens = runner_case
    if runner == 'native':
        first = run_native(runner_case)
        path = root / 'results/checks.json'
        call = lambda: run_native(runner_case)
    else:
        from generators import run_features
        run_features.main()
        path = root / 'results/features_checks.json'
        first = json.loads(path.read_text())
        call = run_features.main
    for row in first:
        row['scored_with'] = expected_stamp(root, row['intent_id'])
        if changed == 'missing':
            row.pop('scored_with')
        else:
            row['scored_with'][changed] = '0' * 64
        row['actual'] = 'obsolete observation'
    dump(path, first)
    before = {p: p.read_bytes() for p in (root / 'native').rglob('*') if p.is_file()}
    saves.reset_mock()
    saves.side_effect = AssertionError('score-only refresh attempted a save')
    opens.reset_mock()
    result = call()
    saves.assert_not_called()
    assert opens.called
    rows = result if runner == 'native' else json.loads(path.read_text())
    assert_stamp(rows, root, first[0]['intent_id'])
    assert all(r['actual'] != 'obsolete observation' for r in rows)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize('program,engine', [('ezdxf', 'ezdxf'), ('oda', 'oda-teigha'),
                                             ('bricscad', 'oda-teigha'), ('cadcraft', 'cadcraft')])
def test_program_declarations_carry_engine(program, engine):
    declarations = json.loads((ROOT / 'programs/capabilities.json').read_text())
    assert declarations[program].get('engine') == engine


@pytest.fixture
def fresh_cross(tmp_path, monkeypatch):
    import tempfile
    doc = ezdxf.new('R2000')
    i = intent(doc)
    i.update(representation_id='synthetic')
    i['expected'][0]['value'] = 0
    dump(tmp_path / 'intent/synthetic.json', i)
    monkeypatch.setattr(run_cross, 'R', tmp_path)
    monkeypatch.setattr(run_cross, 'log', lambda *args: None)
    monkeypatch.setattr(run_cross, 'workdir', lambda prefix, root=None: tempfile.mkdtemp(dir=tmp_path, prefix=prefix))
    monkeypatch.setattr(run_cross.ezdxf, 'readfile', Mock(return_value=doc))
    monkeypatch.setattr(run_cross.privacy, 'assert_clean', lambda *args: None)
    saved = Mock()
    converted = Mock()
    def fake_adapter(name, engine):
        class Fake:
            build = 'synthetic-build'
            def save_many(self, jobs):
                saved(jobs)
                for src, dest, *_ in jobs:
                    dest.write_text('synthetic drawing')
                return {dest: None for _, dest, *_ in jobs}
            def read_dwg_many(self, paths):
                converted(paths)
                return {p: doc for p in paths}
        Fake.name = name
        Fake.engine = engine
        return Fake
    monkeypatch.setattr(run_cross, 'ADAPTERS', {name: fake_adapter(name, engine) for name, engine in
                        [('ezdxf', 'ezdxf'), ('oda', 'oda-teigha'), ('bricscad', 'oda-teigha'), ('cadcraft', 'cadcraft')]})
    def setup(pair, fmt):
        src = tmp_path / 'native/ezdxf/sample.dxf'
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text('synthetic source')
        dest = tmp_path / 'cross' / pair / ('sample.' + fmt.lower())
        side = dict(intent_id='synthetic', content_digest='source-digest', ezdxf_based=True)
        monkeypatch.setattr(run_cross, 'jobs_for', lambda *a, **k: [(src, dest, fmt, '2000', 'ASCII' if fmt == 'DXF' else 'binary', side)])
        return dest, tmp_path / 'results' / ('cross_' + pair + '_checks.json')
    return tmp_path, setup, saved, converted


@pytest.mark.parametrize('pair,fmt,writer,reader', [
    ('ezdxf__oda', 'DXF', 'oda-teigha', 'ezdxf'),
    ('ezdxf__oda', 'DWG', 'oda-teigha', 'oda-teigha'),
    ('ezdxf__bricscad', 'DXF', 'oda-teigha', 'ezdxf'),
    ('ezdxf__bricscad', 'DWG', 'oda-teigha', 'oda-teigha'),
    ('ezdxf__cadcraft', 'DXF', 'cadcraft', 'ezdxf'),
    ('ezdxf__cadcraft', 'DWG', 'cadcraft', 'oda-teigha'),
])
@pytest.mark.parametrize('contract', ['stamp', 'engines'])
def test_cross_writes_stamp_and_engines(fresh_cross, pair, fmt, writer, reader, contract):
    root, setup, saved, converted = fresh_cross
    dest, path = setup(pair, fmt)
    run_cross.run_pair(pair)
    rows = json.loads(path.read_text())
    assert saved.called
    if contract == 'stamp':
        assert_stamp(rows, root, 'synthetic')
    else:
        assert_engines(rows, writer, reader)


@pytest.mark.parametrize('fmt', ['DXF', 'DWG'])
@pytest.mark.parametrize('changed', ['checker', 'intent', 'missing'])
def test_cross_rescore_replaces_rows_and_preserves_drawing(fresh_cross, fmt, changed):
    root, setup, saved, converted = fresh_cross
    dest, path = setup('ezdxf__oda', fmt)
    run_cross.run_pair('ezdxf__oda')
    rows = json.loads(path.read_text())
    for row in rows:
        row['scored_with'] = expected_stamp(root, 'synthetic')
        if changed == 'missing':
            del row['scored_with']
        else:
            row['scored_with'][changed] = '0' * 64
        row['actual'] = 'obsolete observation'
    dump(path, rows)
    before = dest.read_bytes(), dest.stat().st_mtime_ns, dest.with_suffix(dest.suffix + '.provenance.json').read_bytes()
    saved.reset_mock()
    saved.side_effect = AssertionError('score-only refresh resaved drawing')
    converted.reset_mock()
    run_cross.ezdxf.readfile.reset_mock()
    run_cross.run_pair('ezdxf__oda')
    saved.assert_not_called()
    if fmt == 'DXF':
        run_cross.ezdxf.readfile.assert_called_once_with(dest)
        converted.assert_not_called()
    else:
        converted.assert_called_once_with([dest])
    current = json.loads(path.read_text())
    assert_stamp(current, root, 'synthetic')
    assert len(current) == len(rows)
    assert all(r['actual'] != 'obsolete observation' for r in current)
    assert before == (dest.read_bytes(), dest.stat().st_mtime_ns, dest.with_suffix(dest.suffix + '.provenance.json').read_bytes())


def seed_derived(tmp_path):
    """Give a minimal check_artifacts fixture its derived files.

    The freshness check rebuilds every derived file with the repository's own generators
    (checker/derived.py) and compares; those generators read the repository, not the
    fixture. A fixture therefore holds the committed derived files, which are exactly what
    that rebuild must reproduce, and the test keeps isolating its own subject."""
    import shutil
    from checker.derived import DERIVED
    for names, _, _ in DERIVED:
        for name in names:
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, tmp_path / name)


@pytest.mark.parametrize('stamp_state', ['current', 'checker', 'intent', 'missing'])
def test_artifact_stale_check_on_temporary_results(tmp_path, stamp_state):
    # Copy the entry point so its __file__-based root resolves to our fixture.
    # All legacy artifact checks are satisfied independently of the stale test.
    script = tmp_path / 'checker/check_artifacts.py'
    script.parent.mkdir()
    script.write_text((ROOT / 'checker/check_artifacts.py').read_text())
    dump(tmp_path / 'results/audits.json', [dict(errors=0, fixes=0)] * 77)
    dump(tmp_path / 'results/digest_evidence.json', [dict(equal=True, one_field_changes_digest=True)] * 13)
    (tmp_path / 'README.md').write_text('Synthetic')
    seed_derived(tmp_path)
    i = intent(ezdxf.new('R2000'))
    dump(tmp_path / 'intent/synthetic.json', i)
    stamp = expected_stamp(tmp_path, 'synthetic')
    good = dict(file='native/ezdxf/test.dxf', intent_id='synthetic', field='value', status='same', scored_with=stamp,
                writer_engine='ezdxf', reader_engine='ezdxf', shared_engine=True)
    bad = dict(good, field='second', scored_with=dict(stamp))
    if stamp_state == 'missing':
        bad.pop('scored_with')
    elif stamp_state != 'current':
        bad['scored_with'][stamp_state] = '0' * 64
    dump(tmp_path / 'results/checks.json', [good, bad, dict(bad, field='third')])
    dump(tmp_path / 'results/cross_ezdxf__oda_checks.json', [dict(bad, file='cross/ezdxf__oda/test.dxf')])
    output = io.StringIO()
    failure = None
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            runpy.run_path(str(script), run_name='__main__')
        except (AssertionError, SystemExit, RuntimeError) as exc:
            failure = exc
    if stamp_state == 'current':
        assert failure is None, output.getvalue() + str(failure)
    else:
        assert failure is not None, 'stale results incorrectly passed artifact checks'
        diagnostic = output.getvalue() + str(failure)
        import re
        assert re.search(r'checks\.json[^\n]*\b2\b|\b2\b[^\n]*checks\.json', diagnostic), diagnostic
        assert re.search(r'cross_ezdxf__oda_checks\.json[^\n]*\b1\b|\b1\b[^\n]*cross_ezdxf__oda_checks\.json', diagnostic), diagnostic


def test_dry_run_reports_native_and_pair_resave_and_rescore_counts(runner_case, monkeypatch, capsys):
    import re
    import sys
    import regenerate
    from programs import adapters
    root, doc, i, saves, opens = runner_case
    iid = 'background_synthetic'
    i = dict(i, intent_id=iid)
    ip = root / 'intent' / (iid + '.json')
    dump(ip, i)
    from checker.scoring import native_input
    inp = native_input(root, iid)[0]
    rows, _ = regenerate.run_case((i, 'synthetic', '2000', 'ASCII', inp), cross=False)
    for row in rows:
        row['scored_with'] = dict(expected_stamp(root, iid), checker='0' * 64)
    dump(root / 'results/checks.json', rows)
    dump(root / 'results/audits.json', [])
    monkeypatch.setattr(regenerate, 'VERSIONS', {'2000': 'AC1015'})
    monkeypatch.setattr(run_cross, 'R', root)
    monkeypatch.setattr(run_cross, 'PAIRS', {'ezdxf__oda': ('native/ezdxf', 'oda')})
    jobs = []
    pair_rows = []
    for name, state in [('missing', 'resave'), ('stale_checker', 'checker'),
                        ('stale_intent', 'intent'), ('current', 'current')]:
        src = root / 'native/ezdxf/synthetic_2000_ASCII.dxf'
        dest = root / 'cross/ezdxf__oda' / (name + '.dxf')
        side = dict(intent_id=iid, content_digest='source-digest', program='ezdxf')
        jobs.append((src, dest, 'DXF', '2000', 'ASCII', side))
        if state == 'resave':
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('synthetic drawing')
        dump(dest.with_suffix('.dxf.provenance.json'), dict(build='synthetic-build', made_by={'input_digest': 'source-digest'}))
        stamp = expected_stamp(root, iid)
        if state != 'current':
            stamp[state] = '0' * 64
        pair_rows.append(dict(file=dest.relative_to(root).as_posix(), intent_id=iid, field='value',
                              reader='ezdxf ' + ezdxf.__version__, converter=None,
                              status='same', scored_with=stamp,
                              writer_engine='ezdxf', reader_engine='ezdxf', shared_engine=True))
    dump(root / 'results/cross_ezdxf__oda_checks.json', pair_rows)
    monkeypatch.setattr(run_cross, 'jobs_for', lambda *a, **k: jobs)
    class FakeOda:
        name = 'oda'
        engine = 'oda-teigha'
        build = 'synthetic-build'
    monkeypatch.setattr(adapters, 'ADAPTERS', {'oda': FakeOda})
    monkeypatch.setattr(sys, 'argv', ['regenerate.py', '--intent', iid, '--pairs', 'ezdxf__oda', '--dry-run'])
    saves.reset_mock()
    saves.side_effect = AssertionError('dry run attempted save')
    opens.reset_mock()
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    capsys.readouterr()
    regenerate.main()
    output = capsys.readouterr().out.lower()
    # The wording is free; counts must be associated with the operation and set.
    for label, resaves, rescores in [('native', 1, 1), ('ezdxf__oda', 1, 2)]:
        lines = '\n'.join(line for line in output.splitlines() if label in line)
        for operation, count in [('resav', resaves), ('rescor', rescores)]:
            pattern = rf'(?:\b{count}\s+(?:outputs?\s+)?(?:to\s+)?{operation}\w*|{operation}\w*\s*[:=]?\s*{count}\b)'
            assert re.search(pattern, lines), (label, operation, count, output)
    saves.assert_not_called()
    opens.assert_not_called()
    assert before == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('builder_name', ['map', 'coverage'])
def test_builders_keep_distinct_reader_and_converter_observations(builder_case, monkeypatch, capsys, builder_name):
    from generators import write_coverage
    root, builder, row = builder_case
    # Four physical rows, three observations: only the exact duplicate collapses.
    rows = [row, dict(row, reader='other-reader'), dict(row, converter='other-converter')]
    dump(root / 'results/checks.json', [row])
    dump(root / 'results/cross_ezdxf__oda_checks.json', rows)
    if builder_name == 'map':
        builder.main()
        assert '3 measured fields' in capsys.readouterr().out
        assert len(map_cell(root)['runs'][0]['diffs']) == 3
    else:
        monkeypatch.setattr(write_coverage, 'R', root)
        monkeypatch.setattr(write_coverage, 'build_map', builder.main)
        write_coverage.main()
        lines = (root / 'COVERAGE.md').read_text().splitlines()
        header = next(line for line in lines if line.startswith('| Set |'))
        values = next(line for line in lines if line.startswith('| cross/ezdxf__oda |'))
        cells = dict(zip([x.strip() for x in header.split('|')[1:-1]],
                         [x.strip() for x in values.split('|')[1:-1]]))
        assert cells['Rows not scored'] == '3'


@pytest.mark.parametrize('fmt', ['DXF', 'DWG'])
def test_current_cross_stamp_does_not_read_or_save(fresh_cross, fmt):
    root, setup, saved, converted = fresh_cross
    dest, path = setup('ezdxf__oda', fmt)
    run_cross.run_pair('ezdxf__oda')
    rows = json.loads(path.read_text())
    for row in rows:
        row['scored_with'] = expected_stamp(root, 'synthetic')
    dump(path, rows)
    before = path.read_bytes()
    saved.reset_mock()
    converted.reset_mock()
    run_cross.ezdxf.readfile.reset_mock()
    run_cross.run_pair('ezdxf__oda')
    saved.assert_not_called()
    converted.assert_not_called()
    run_cross.ezdxf.readfile.assert_not_called()
    assert path.read_bytes() == before


def test_ambiguous_application_is_not_scored():
    doc = ezdxf.new()
    entity = doc.modelspace().add_point((0, 0))
    entity.set_xdata('ZEV_APP', [(1000, 'one')])
    entity.set_xdata('zev_app', [(1000, 'two')])
    row = scored(doc, {'kind': 'xdata'})
    assert row['status'] == 'not_scored'
    assert 'ambigu' in row['detail'].lower()


def test_unsupported_query_operand_is_not_scored():
    row = scored(ezdxf.new(), {'kind': 'query_count', 'name': "LINE[name=='SYNTHETIC']"})
    assert row['status'] == 'not_scored'
    assert 'operand' in row['detail'].lower()


@pytest.mark.parametrize('reversed_order,status', [(False, 'same'), (True, 'differs')])
def test_block_definition_draw_order_is_scored(reversed_order, status):
    doc = ezdxf.new('R2018')
    block = doc.blocks.new('SYNTHETIC')
    entities = [block.add_line((0, 0), (1, 0), dxfattribs={'layer': name})
                for name in ('SYNTHETIC_A', 'SYNTHETIC_B')]
    if reversed_order:
        a, b = (entity.dxf.handle for entity in entities)
        block.set_redraw_order([(a, b), (b, a)])
    i = intent(doc)
    i['expected'][0].update(value=['SYNTHETIC_A', 'SYNTHETIC_B'], selector=dict(
        kind='feature_attr', table='LINE', name='SYNTHETIC_A', attr='redraw_order'))
    row = core.compare(doc, i, 'test')[0]
    assert row['status'] == status


def test_ownerless_draw_order_entity_is_not_scored():
    doc = ezdxf.new()
    entity = doc.modelspace().add_line((0, 0), (1, 0), dxfattribs={'layer': 'SYNTHETIC'})
    doc.modelspace().unlink_entity(entity)
    assert entity.get_layout() is None
    row = scored(doc, dict(kind='feature_attr', table='LINE', name='SYNTHETIC', attr='redraw_order'))
    assert row['status'] == 'not_scored'
    assert row['detail']


@pytest.mark.parametrize('attribute,entity_type', [
    ('gradient_rotation', 'HATCH'), ('extension_record', 'LINE'),
    ('alignment_rotation_error', 'TEXT'), ('acis_body_count', '3DSOLID'),
])
def test_real_drawing_missing_structures_are_absent(attribute, entity_type):
    doc = ezdxf.new('R2018')
    space = doc.modelspace()
    if entity_type == 'HATCH':
        entity = space.add_hatch()
        assert entity.gradient is None
    elif entity_type == 'LINE':
        entity = space.add_line((0, 0), (1, 0))
        assert not entity.has_extension_dict
    elif entity_type == 'TEXT':
        entity = space.add_text('Synthetic')
        assert not entity.dxf.hasattr('align_point')
    else:
        entity = space.add_3dsolid()
        assert not entity.sat and not entity.sab
    entity.dxf.layer = 'SYNTHETIC'
    row = scored(doc, dict(kind='feature_attr', table=entity_type, name='SYNTHETIC', attr=attribute))
    assert row['status'] == 'absent', row
    assert row['detail']


@pytest.mark.parametrize('dependency', ['ezdxf', 'versions'])
def test_stamp_changes_with_status_dependencies(tmp_path, monkeypatch, dependency):
    from checker.scoring import stamp
    from programs.adapters import VERSIONS
    dump(tmp_path / 'intent/synthetic.json', intent(ezdxf.new()))
    before = stamp(tmp_path, 'synthetic')
    if dependency == 'ezdxf':
        monkeypatch.setattr(ezdxf, '__version__', ezdxf.__version__ + '-synthetic')
    else:
        monkeypatch.setitem(VERSIONS, '2000', 'AC9999')
    assert stamp(tmp_path, 'synthetic') != before


@pytest.mark.parametrize('dependency', ['reader', 'converter'])
def test_cross_rescores_when_reading_build_changes(fresh_cross, monkeypatch, dependency):
    root, setup, saved, converted = fresh_cross
    fmt = 'DXF' if dependency == 'reader' else 'DWG'
    dest, path = setup('ezdxf__oda', fmt)
    run_cross.run_pair('ezdxf__oda')
    original = dest.read_bytes(), dest.with_suffix(dest.suffix + '.provenance.json').read_bytes()
    saved.reset_mock()
    converted.reset_mock()
    run_cross.ezdxf.readfile.reset_mock()
    if dependency == 'reader':
        monkeypatch.setattr(ezdxf, '__version__', ezdxf.__version__ + '-synthetic')
    else:
        monkeypatch.setattr(run_cross.ADAPTERS['bricscad'], 'build', 'changed-reader-build')
    run_cross.run_pair('ezdxf__oda')
    saved.assert_not_called()
    if dependency == 'reader':
        run_cross.ezdxf.readfile.assert_called_once_with(dest)
        assert all(ezdxf.__version__ in row['reader'] for row in json.loads(path.read_text()))
    else:
        converted.assert_called_once_with([dest])
        assert all('changed-reader-build' in row['converter'] for row in json.loads(path.read_text()))
    assert original == (dest.read_bytes(), dest.with_suffix(dest.suffix + '.provenance.json').read_bytes())


def test_bricscad_native_stale_scores_refresh_without_generation(runner_case, monkeypatch):
    from generators import run_bricscad
    root, doc, _, _, opens = runner_case
    run_bricscad.main()
    path = root / 'results/native_bricscad_checks.json'
    rows = json.loads(path.read_text())
    for row in rows:
        row['scored_with']['checker'] = 'stale'
        row['actual'] = 'obsolete'
    dump(path, rows)
    before = {p: p.read_bytes() for p in (root / 'native/bricscad').rglob('*') if p.is_file()}
    monkeypatch.setattr(run_bricscad, 'run_script', Mock(side_effect=AssertionError('native regenerated')))
    opens.reset_mock()
    run_bricscad.main()
    assert opens.called
    assert all(row['actual'] != 'obsolete' for row in json.loads(path.read_text()))
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('fresh', [True, False])
def test_feature_failure_rule_applies_to_fresh_and_rescored(runner_case, fresh):
    from generators import run_features
    root, doc, _, saves, _ = runner_case
    if not fresh:
        run_features.main()
        path = root / 'results/features_checks.json'
        rows = json.loads(path.read_text())
        for row in rows:
            row['scored_with']['checker'] = 'stale'
        dump(path, rows)
        saves.reset_mock()
        saves.side_effect = AssertionError('rescore saved')
    doc.layers.new('ZEV_UNEXPECTED')
    with pytest.raises((AssertionError, RuntimeError, SystemExit)):
        run_features.main()
    if not fresh:
        saves.assert_not_called()


def test_shared_engine_readers_are_not_called_independent():
    import re
    violations = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or set(path.relative_to(ROOT).parts) & {'tests', '.git', '__pycache__', '.pytest_cache'}:
            continue
        if path.suffix not in {'.py', '.md', '.html', '.txt', '.json', '.sh'}:
            continue
        text = path.read_text(errors='replace')
        for match in re.finditer(r'(?<![\w-])independent\s+(?:DWG\s+)?(?:reader|converter)', text, re.I):
            context = text[max(0, match.start()-180):match.end()+300]
            # Negative engine statements and requests for future evidence are valid.
            prefix = text[max(0, match.start()-12):match.start()]
            if re.search(r'\b(?:not|no)\s+(?:an?\s+)?$', prefix, re.I):
                continue
            if 'ODA' in context and 'BricsCAD' in context:
                violations.append(f'{path.relative_to(ROOT)}:{text.count(chr(10), 0, match.start())+1}')
    assert not violations, violations


@pytest.mark.parametrize('missing', ['writer_engine', 'reader_engine', 'shared_engine'])
def test_artifact_check_rejects_missing_engine_fields(tmp_path, missing):
    script = tmp_path / 'checker/check_artifacts.py'
    script.parent.mkdir()
    script.write_text((ROOT / 'checker/check_artifacts.py').read_text())
    dump(tmp_path / 'results/audits.json', [dict(errors=0, fixes=0)] * 77)
    dump(tmp_path / 'results/digest_evidence.json', [dict(equal=True, one_field_changes_digest=True)] * 13)
    (tmp_path / 'README.md').write_text('Synthetic')
    seed_derived(tmp_path)
    dump(tmp_path / 'intent/synthetic.json', intent(ezdxf.new()))
    row = dict(file='native/ezdxf/test.dxf', intent_id='synthetic', field='value', status='same',
               scored_with=expected_stamp(tmp_path, 'synthetic'), writer_engine='ezdxf', reader_engine='ezdxf', shared_engine=True)
    dump(tmp_path / 'results/checks.json', [row])
    # A valid control must pass before removing exactly one engine field.
    runpy.run_path(str(script), run_name='__main__')
    del row[missing]
    dump(tmp_path / 'results/checks.json', [row])
    with pytest.raises((AssertionError, SystemExit, RuntimeError)):
        runpy.run_path(str(script), run_name='__main__')


def test_native_digest_and_skip_helper_is_shared():
    import ast
    import inspect
    import sys
    import regenerate
    from generators import run_features, run_bricscad
    # Require an actual shared callable, without prescribing its public name.
    modules = (regenerate, run_features, run_bricscad)
    called = []
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        called.append({getattr(module, name) for name in names
                       if callable(getattr(module, name, None)) and
                       any(word in name.lower() for word in ('input', 'digest', 'native', 'case'))})
    shared = set.intersection(*called)
    assert shared, 'native runners and dry run must call one shared input/skip helper'


def test_dry_run_and_feature_runner_agree_on_native_input_digest(runner_case, monkeypatch, capsys):
    import sys
    import regenerate
    from generators import run_features
    root, _, _, saves, opens = runner_case
    # Behavioral agreement: accept the runner's digest and then reject changed inputs.
    run_features.main()
    monkeypatch.setattr(regenerate, 'VERSIONS', {'2000': 'AC1015'})
    monkeypatch.setattr(run_cross, 'PAIRS', {})
    monkeypatch.setattr(sys, 'argv', ['regenerate.py', '--intent', 'feature_synthetic', '--dry-run'])
    saves.reset_mock()
    opens.reset_mock()
    capsys.readouterr()
    regenerate.main()
    output = capsys.readouterr().out
    assert 'native: 0 resave, 0 rescore' in output, output
    (root / 'generators/features.py').write_text('# changed synthetic input')
    regenerate.main()
    assert 'native: 2 resave, 0 rescore' in capsys.readouterr().out
    saves.assert_not_called()
    opens.assert_not_called()


@pytest.mark.parametrize('cohort', ['native'])
def test_dry_run_counts_bricscad_stale_cohorts(runner_case, monkeypatch, capsys, cohort):
    import sys
    import re
    import regenerate
    from generators import run_bricscad
    from programs import adapters
    root, _, _, _, opens = runner_case
    run_bricscad.main()
    path = root / 'results/native_bricscad_checks.json'
    rows = json.loads(path.read_text())
    label = r'(?:native.*bricscad|bricscad.*native)'
    count = 2
    for row in rows:
        row['scored_with']['checker'] = 'stale'
    dump(path, rows)
    monkeypatch.setattr(regenerate, 'VERSIONS', {'2000': 'AC1015'})
    monkeypatch.setattr(run_cross, 'R', root)
    monkeypatch.setattr(run_cross, 'PAIRS', {})
    monkeypatch.setattr(adapters, 'BricsCad', run_bricscad.BricsCad)
    monkeypatch.setattr(adapters, 'Oda', run_bricscad.Oda)
    monkeypatch.setattr(run_bricscad, 'run_script', Mock(side_effect=AssertionError('dry run generated')))
    monkeypatch.setattr(sys, 'argv', ['regenerate.py', '--dry-run', '--with-bricscad'])
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    opens.reset_mock()
    capsys.readouterr()
    regenerate.main()
    output = capsys.readouterr().out.lower()
    lines = '\n'.join(line for line in output.splitlines() if re.search(label, line))
    assert re.search(rf'\b{count}\s+(?:outputs?\s+)?(?:to\s+)?rescor', lines), output
    assert re.search(r'\b0\s+(?:outputs?\s+)?(?:to\s+)?resav', lines), output
    opens.assert_not_called()
    assert before == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
