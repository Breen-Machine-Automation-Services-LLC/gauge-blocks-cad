"""WP1b contracts. Synthetic intents, copied sources, and fake CAD programs only.

These are acceptance tests for the implementation that follows this test-only change.
No migration behavior is specified here.
"""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('CAD_DATASET_SETTINGS', str(ROOT / 'settings.example.json'))
from checker import scoring


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def tree(tmp_path):
    for directory in ('generators', 'checker', 'programs'):
        shutil.copytree(ROOT / directory, tmp_path / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(ROOT / 'regenerate.py', tmp_path / 'regenerate.py')
    for iid in ('background_synthetic', 'feature_synthetic', 'future_synthetic'):
        dump(tmp_path / 'intent' / (iid + '.json'), {
            'intent_id': iid, 'representation_id': 'reference_1',
            'title': 'Synthetic drawing', 'description': 'Invented fixture',
            'expected': [{'id': 'count', 'value': 2, 'tolerance': 0,
                          'selector': {'kind': 'layer_count'},
                          'reference': {'basis': 'Invented citation'}}]})
    (tmp_path / 'results').mkdir()
    return tmp_path


def inputs(root):
    return {iid: scoring.native_input(root, iid, **kwargs)[0]
            for iid, kwargs in (
                ('background_synthetic', {}), ('feature_synthetic', {}),
                ('future_synthetic', dict(program='bricscad',
                    script=root / 'generators/run_bricscad.py',
                    lsp=root / 'generators/bricscad/make_bricscad_masters.lsp')))}


@pytest.mark.parametrize('source', [
    'generators/run_cross.py', 'generators/run_features.py',
    'generators/run_bricscad.py', 'generators/run_independent.py',
    'checker/core.py', 'programs/adapters.py', 'regenerate.py',
    'generators/summarize_cross.py', 'generators/write_coverage.py',
])
def test_orchestration_is_not_a_drawing_input(tree, source):
    before = inputs(tree)
    with (tree / source).open('a') as stream:
        stream.write('\n# Synthetic orchestration edit\n')
    assert inputs(tree) == before


@pytest.mark.parametrize('source,affected', [
    ('generators/background.py', {'background_synthetic', 'feature_synthetic'}),
    ('generators/features.py', {'background_synthetic', 'feature_synthetic'}),
    ('generators/master_l.py', {'background_synthetic', 'feature_synthetic'}),
    ('generators/masters_abcd.py', {'background_synthetic', 'feature_synthetic'}),
    ('generators/masters_ghijn.py', {'background_synthetic', 'feature_synthetic'}),
    ('generators/bricscad/make_bricscad_masters.lsp', {'future_synthetic'}),
])
def test_drawing_code_changes_its_native_inputs(tree, source, affected):
    # Requirement 1 specifies every drawing Python module for ezdxf natives.
    before = inputs(tree)
    with (tree / source).open('a') as stream:
        stream.write('\n; synthetic edit\n' if source.endswith('.lsp') else '\n# synthetic edit\n')
    after = inputs(tree)
    assert {iid for iid in before if after[iid] != before[iid]} == affected


def test_new_drawing_module_is_included(tree):
    before = inputs(tree)
    (tree / 'generators/synthetic_drawing.py').write_text('def draw(): return 2\n')
    after = inputs(tree)
    assert after['feature_synthetic'] != before['feature_synthetic']
    assert after['background_synthetic'] != before['background_synthetic']
    assert after['future_synthetic'] == before['future_synthetic']


@pytest.mark.parametrize('iid', ['background_synthetic', 'feature_synthetic', 'future_synthetic'])
@pytest.mark.parametrize('edit', ['reference', 'title', 'expected'])
def test_intent_uses_the_score_stamp_reduction(tree, iid, edit):
    before = inputs(tree)
    stamp_before = scoring.stamp(tree, iid)['intent']
    path = tree / 'intent' / (iid + '.json')
    intent = json.loads(path.read_text())
    if edit == 'reference':
        intent['expected'][0]['reference'] = {'basis': 'Revised invented citation'}
    elif edit == 'title':
        intent['title'] = 'Revised synthetic title'
    else:
        intent['expected'][0]['value'] = 3
    dump(path, intent)
    after = inputs(tree)
    changed = edit == 'expected'
    assert (scoring.stamp(tree, iid)['intent'] != stamp_before) == changed
    assert (after[iid] != before[iid]) == changed
    assert all(after[other] == before[other] for other in before if other != iid)


@pytest.fixture
def harness(tree, monkeypatch):
    """Run real orchestration with fake drawing builders/readers/savers.

    The process-launch guard also protects future implementations of these tests.
    Existing outputs have current input digests, builds and scores.
    """
    import regenerate as regen
    from generators import run_features as feature, run_bricscad as bc, run_cross as cross
    from programs import adapters
    modules = (regen, feature, bc, cross)
    def forbidden(*args, **kwargs):
        raise AssertionError('External process launch is forbidden in WP1b tests')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(os, 'system', forbidden)
    path = tree / 'intent/background_synthetic.json'
    background = json.loads(path.read_text())
    background['intent_id'] = 'background_background'
    path.unlink()
    dump(tree / 'intent/background_background.json', background)
    saved = []
    doc = SimpleNamespace(audit=lambda: SimpleNamespace(errors=[], fixes=[]))
    class Fake:
        name = 'ezdxf'
        build = 'synthetic-build'
        def open(self, path):
            return doc
        def save(self, source, path, fmt, version, encoding):
            saved.append((self.name, Path(path).suffix, version, encoding))
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(saved_bytes(self.name, fmt, version, encoding))
        def save_many(self, jobs):
            for job in jobs:
                self.save(*job)
            return {job[1]: None for job in jobs}
        def read_dwg_many(self, paths):
            return dict.fromkeys(paths, doc)
    class FakeOda(Fake):
        name = 'oda'
    class FakeBc(Fake):
        name = 'bricscad'
    monkeypatch.setattr(adapters, 'ADAPTERS', {'ezdxf': Fake, 'oda': FakeOda, 'bricscad': FakeBc})
    monkeypatch.setattr(adapters, 'BricsCad', FakeBc)
    monkeypatch.setattr(adapters, 'VERSIONS', {'2000': 'AC1015'})
    monkeypatch.setattr(regen, 'ROOT', tree)
    calls = []
    helper = scoring.native_input
    def traced(*args, **kwargs):
        result = helper(*args, **kwargs)
        calls.append((args[1], result[0]))
        return result
    monkeypatch.setattr(scoring, 'native_input', traced)
    for module in modules:
        if hasattr(module, 'R'):
            monkeypatch.setattr(module, 'R', tree)
        if hasattr(module, 'native_input'):
            monkeypatch.setattr(module, 'native_input', traced)
        monkeypatch.setattr(module, 'VERSIONS', {'2000': 'AC1015'})
        if hasattr(module, 'Ezdxf'):
            monkeypatch.setattr(module, 'Ezdxf', Fake)
        if hasattr(module, 'Oda'):
            monkeypatch.setattr(module, 'Oda', FakeOda)
        monkeypatch.setattr(module, 'compare', lambda *a, **kw: [])
        monkeypatch.setattr(module, 'current', lambda *a, **kw: True)
    monkeypatch.setattr(bc, 'BricsCad', FakeBc)
    monkeypatch.setattr(bc, 'LSP', tree / 'generators/bricscad/make_bricscad_masters.lsp')
    monkeypatch.setattr(bc, 'TOPICS', {'k_tables': 'future_synthetic'})
    monkeypatch.setattr(feature, 'TOPICS', ['synthetic'])
    monkeypatch.setattr(feature, 'build', lambda *a: doc)
    monkeypatch.setattr(regen, 'build', lambda *a: doc)
    monkeypatch.setattr(regen, 'digest', lambda *a: 'synthetic-content')
    monkeypatch.setattr(cross, 'reading_current', lambda *a: True)
    monkeypatch.setattr(cross, 'ADAPTERS', adapters.ADAPTERS)
    monkeypatch.setattr(cross, 'PAIRS', {'ezdxf__oda': ('native/ezdxf', 'oda'),
                                      'bricscad__oda': ('native/bricscad', 'oda')})
    monkeypatch.setattr(cross, 'LOG', tree / 'logs/cross.log')
    monkeypatch.setattr(cross, 'workdir', lambda *a: __import__('tempfile').mkdtemp(dir=tree / 'results'))
    monkeypatch.setattr(cross.privacy, 'assert_clean', lambda *a: None)
    monkeypatch.setattr(cross, 'digest', lambda *a: 'synthetic-content')
    monkeypatch.setattr(cross.ezdxf, 'readfile', lambda *a: doc)
    # Native BricsCAD saves are performed by its LISP batch entry point.
    def fake_script(script, *args):
        import re
        out = Path(re.search(r'\(setq \*out-dir\* "([^"]+)"\)', script).group(1))
        (out / 'make_bricscad_masters.log').write_text('Synthetic generation\n')
        for encoding in ('ASCII', 'binary'):
            (out / f'k_tables_2000_{encoding}.dxf').write_bytes(
                saved_bytes('bricscad', 'DXF', '2000', encoding))
            saved.append(('bricscad', '.dxf', '2000', encoding))
        return 0
    monkeypatch.setattr(bc, 'run_script', fake_script)
    monkeypatch.setattr(bc, 'observe', lambda *a: {})
    monkeypatch.setattr(bc, 'workdir', cross.workdir)
    monkeypatch.setattr(bc, 'sidecar', regen.sidecar)
    for filename in ('checks', 'audits', 'features_checks', 'features_audits', 'native_bricscad_checks'):
        dump(tree / 'results' / (filename + '.json'), [])
    def seed(iid, topic, program='ezdxf'):
        kwargs = {} if program == 'ezdxf' else dict(program=program, script=Path(bc.__file__), lsp=bc.LSP)
        inp = helper(tree, iid, **kwargs)[0]
        for encoding in ('ASCII', 'binary'):
            dest = tree / 'native' / program / f'{topic}_2000_{encoding}.dxf'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('synthetic existing drawing')
            meta = dict(intent_id=iid, program=program, build=Fake.build, format='DXF',
                        version='2000', encoding=encoding, ezdxf_based=program == 'ezdxf',
                        content_digest='synthetic-content', made_by={'input_digest': inp})
            dump(dest.with_suffix('.dxf.provenance.json'), meta)
    # Separate names avoid collisions between background and feature destinations.
    seed('feature_synthetic', 'synthetic')
    seed('background_background', 'background')
    seed('future_synthetic', 'k_tables', 'bricscad')
    for src, dest, fmt, version, enc, side in cross.jobs_for('ezdxf__oda'):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('synthetic existing cross drawing')
        dump(dest.with_suffix(dest.suffix + '.provenance.json'),
             dict(intent_id=side['intent_id'], build=Fake.build, made_by={'input_digest': side['content_digest']}))
    return SimpleNamespace(root=tree, regen=regen, feature=feature, bc=bc, cross=cross,
                           calls=calls, saved=saved, helper=helper)


def invoke(h, monkeypatch, *arguments):
    monkeypatch.setattr(sys, 'argv', ['regenerate.py', *arguments])
    h.regen.main()


@pytest.mark.parametrize('kind', ['feature', 'background', 'bricscad'])
def test_runners_and_dry_run_use_one_helper(harness, monkeypatch, capsys, kind):
    h = harness
    iid = {'feature': 'feature_synthetic', 'background': 'background_background',
           'bricscad': 'future_synthetic'}[kind]
    if kind == 'feature':
        h.feature.main(iid)
    elif kind == 'bricscad':
        h.bc.main()
    else:
        invoke(h, monkeypatch, '--intent', iid, '--pairs', 'ezdxf__oda')
    runner_calls = [digest for intent, digest in h.calls if intent == iid]
    assert runner_calls, 'Runner must call checker.scoring.native_input'
    h.calls.clear()
    pair = 'bricscad__oda' if kind == 'bricscad' else 'ezdxf__oda'
    invoke(h, monkeypatch, '--intent', iid, '--pairs', pair, '--dry-run', '--with-bricscad')
    dry_calls = [digest for intent, digest in h.calls if intent == iid]
    assert dry_calls, 'Dry run must call checker.scoring.native_input'
    assert set(runner_calls) == set(dry_calls)


@pytest.mark.parametrize('iid', ['feature_synthetic', 'background_background'])
def test_force_dry_run_counts_every_selected_output(harness, monkeypatch, capsys, iid):
    h = harness
    invoke(h, monkeypatch, '--intent', iid, '--pairs', 'ezdxf__oda', '--dry-run')
    baseline = capsys.readouterr().out
    assert 'native: 0 resave, 0 rescore' in baseline
    invoke(h, monkeypatch, '--intent', iid, '--pairs', 'ezdxf__oda', '--dry-run', '--force')
    output = capsys.readouterr().out
    assert 'native: 2 resave, 0 rescore' in output
    assert 'ezdxf__oda: 4 resave, 0 rescore' in output
    assert not h.saved, 'Dry run must never save'


@pytest.mark.parametrize('iid', ['feature_synthetic', 'background_background'])
def test_force_runner_resaves_every_selected_output(harness, monkeypatch, iid):
    h = harness
    invoke(h, monkeypatch, '--intent', iid, '--pairs', 'ezdxf__oda')
    assert not h.saved, 'Current selected outputs must be skipped without --force'
    invoke(h, monkeypatch, '--intent', iid, '--pairs', 'ezdxf__oda', '--force')
    assert sorted(h.saved) == sorted([
        ('ezdxf', '.dxf', '2000', 'ASCII'), ('ezdxf', '.dxf', '2000', 'binary'),
        ('oda', '.dxf', '2000', 'ASCII'), ('oda', '.dxf', '2000', 'binary'),
        ('oda', '.dwg', '2000', 'binary'), ('oda', '.dwg', '2000', 'binary')])


def test_force_bricscad_dry_run_counts_selected_natives(harness, monkeypatch, capsys):
    h = harness
    invoke(h, monkeypatch, '--intent', 'future_synthetic', '--pairs', 'bricscad__oda',
           '--with-bricscad', '--dry-run')
    assert 'native bricscad: 0 resave, 0 rescore' in capsys.readouterr().out
    invoke(h, monkeypatch, '--intent', 'future_synthetic', '--pairs', 'bricscad__oda',
           '--with-bricscad', '--dry-run', '--force')
    output = capsys.readouterr().out
    assert 'native bricscad: 2 resave, 0 rescore' in output
    assert 'native:' not in output
    assert 'bricscad__oda: 2 resave, 0 rescore' in output
    assert not h.saved


def test_force_bricscad_runner_resaves_selected_natives(harness, monkeypatch):
    h = harness
    h.bc.main()
    assert not h.saved
    invoke(h, monkeypatch, '--intent', 'future_synthetic', '--pairs', 'bricscad__oda',
           '--with-bricscad', '--force')
    assert sorted(save for save in h.saved if save[0] == 'bricscad') == [
        ('bricscad', '.dxf', '2000', 'ASCII'), ('bricscad', '.dxf', '2000', 'binary')]
    assert not any(save[0] == 'ezdxf' for save in h.saved)


# Pin both sides: a newly added module must receive an explicit classification.
DRAWING_MODULES = {
    'background.py', 'features.py', 'master_l.py', 'masters_abcd.py',
    'masters_ghijn.py',
}
EXCLUDED_MODULES = {
    'run_bricscad.py', 'run_cross.py', 'run_features.py', 'run_independent.py',
    'summarize_cross.py', 'write_coverage.py',
}


def assert_generator_classification(root):
    modules = {p.name for p in (root / 'generators').glob('*.py')}
    assert not DRAWING_MODULES & EXCLUDED_MODULES
    assert modules == DRAWING_MODULES | EXCLUDED_MODULES, 'Unclassified generator modules'


def test_excluded_generator_modules_are_pinned(tree):
    assert_generator_classification(tree)
    # Exercise the actual digest policy, including its run_ prefix exclusion.
    excluded = set()
    baseline = inputs(tree)['feature_synthetic']
    for name in sorted(DRAWING_MODULES | EXCLUDED_MODULES):
        path = tree / 'generators' / name
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n# synthetic classification probe\n')
            if inputs(tree)['feature_synthetic'] == baseline:
                excluded.add(name)
        finally:
            path.write_bytes(original)
    assert excluded == EXCLUDED_MODULES
    assert set(scoring.ORCHESTRATION_MODULES) == {
        'summarize_cross.py', 'write_coverage.py',
    }


@pytest.mark.parametrize('name', ['synthetic_new.py', 'run_synthetic_new.py'])
def test_unclassified_generator_module_fails_classification(tree, name):
    assert_generator_classification(tree)
    (tree / 'generators' / name).write_text('# Synthetic unclassified module\n')
    with pytest.raises(AssertionError, match='Unclassified generator modules'):
        assert_generator_classification(tree)


def saved_bytes(program, fmt, version, encoding):
    return f'new synthetic save: {program} {fmt} {version} {encoding}\n'.encode()


@pytest.mark.parametrize('runner', ['native', 'feature', 'cross', 'bricscad'])
def test_force_replaces_destination_bytes(harness, runner):
    h = harness
    if runner == 'native':
        iid = 'background_background'
        intent = json.loads((h.root / 'intent' / f'{iid}.json').read_text())
        targets = [(h.root / 'native/ezdxf' / f'background_2000_{enc}.dxf',
                    saved_bytes('ezdxf', 'DXF', '2000', enc))
                   for enc in ('ASCII', 'binary')]
        def run():
            for enc in ('ASCII', 'binary'):
                h.regen.run_case((intent, 'background', '2000', enc,
                                 h.helper(h.root, iid)[0]), cross=False, force=True)
    elif runner == 'feature':
        targets = [(h.root / 'native/ezdxf' / f'synthetic_2000_{enc}.dxf',
                    saved_bytes('ezdxf', 'DXF', '2000', enc))
                   for enc in ('ASCII', 'binary')]
        def run():
            h.feature.main('feature_synthetic', force=True)
    elif runner == 'cross':
        targets = [(dest, saved_bytes('oda', fmt, version, enc))
                   for _, dest, fmt, version, enc, _ in
                   h.cross.jobs_for('ezdxf__oda', intent='feature_synthetic')]
        def run():
            h.cross.run_pair('ezdxf__oda', intent='feature_synthetic',
                             reader_name='oda', force=True)
    else:
        targets = [(h.root / 'native/bricscad' / f'k_tables_2000_{enc}.dxf',
                    saved_bytes('bricscad', 'DXF', '2000', enc))
                   for enc in ('ASCII', 'binary')]
        def run():
            h.bc.main('future_synthetic', force=True)
    assert targets
    # Matching content digests/builds deliberately prevent ordinary publication
    # from replacing these bytes; force must override that optimization.
    for dest, expected in targets:
        assert dest.exists() and dest.read_bytes() != expected
    run()
    for dest, expected in targets:
        assert dest.read_bytes() == expected, str(dest.relative_to(h.root))


def test_selected_bricscad_run_preserves_other_intent_stale_stamp(harness, monkeypatch):
    h = harness
    other = 'future_other_synthetic'
    intent = json.loads((h.root / 'intent/future_synthetic.json').read_text())
    intent['intent_id'] = other
    dump(h.root / 'intent' / f'{other}.json', intent)
    monkeypatch.setattr(h.bc, 'TOPICS', {
        'k_tables': 'future_synthetic', 'k_regions_solids': other,
    })
    stale = dict(scoring.stamp(h.root, other), checker='synthetic obsolete checker')
    carried = dict(file='native/bricscad/k_regions_solids_2000_ASCII.dxf',
                   intent_id=other, field='count', status='same', converter=None,
                   scored_with=stale)
    path = h.root / 'results/native_bricscad_checks.json'
    dump(path, [carried])
    monkeypatch.setattr(h.bc, 'compare', lambda *a, **kw: [
        dict(intent_id='future_synthetic', field='count', status='same')])
    h.bc.main('future_synthetic', force=True)
    rows = json.loads(path.read_text())
    selected = [r for r in rows if r['intent_id'] == 'future_synthetic']
    assert selected, 'The selected intent must actually be scored'
    assert all(r['scored_with'] == scoring.stamp(h.root, 'future_synthetic')
               for r in selected)
    assert [r for r in rows if r['intent_id'] == other] == [carried]


@pytest.mark.parametrize('staleness', ['input', 'missing'])
def test_bricscad_dry_run_counts_whole_topic_rebuild(harness, monkeypatch, capsys, staleness):
    h = harness
    dest = h.root / 'native/bricscad/k_tables_2000_ASCII.dxf'
    if staleness == 'missing':
        dest.unlink()
    else:
        sc = dest.with_suffix('.dxf.provenance.json')
        meta = json.loads(sc.read_text())
        meta['made_by']['input_digest'] = 'synthetic stale input'
        dump(sc, meta)
    invoke(h, monkeypatch, '--intent', 'future_synthetic', '--pairs', 'bricscad__oda',
           '--with-bricscad', '--dry-run')
    output = capsys.readouterr().out
    count = int(re.search(r'native bricscad: (\d+) resave', output).group(1))
    assert not h.saved, 'Dry run must never save'
    h.bc.main('future_synthetic')
    rebuilt = [save for save in h.saved if save[0] == 'bricscad']
    assert len(rebuilt) == 2, 'One stale file must rebuild both files of the topic'
    assert count == len(rebuilt), output


@pytest.mark.parametrize('mechanic', [
    'programs/bricscad_batch.py', 'bcad_run.sh',
    'generators/run_bricscad.py', 'programs/adapters.py',
])
def test_volatile_docs_name_save_mechanics_and_force(tree, mechanic):
    text = (tree / 'checker/VOLATILE.md').read_text()
    # The file must be named in the save-mechanics guidance, not elsewhere in
    # historical digest evidence that happens to mention the same runner.
    guidance = text[text.index('Native drawings rebuild'):]
    assert mechanic in guidance
    assert '--force' in guidance
