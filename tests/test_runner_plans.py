"""WP7 acceptance tests: synthetic copies and fake CAD programs only."""
# Expected API: plan(intent_id=None, force=False, root=None) in regenerate,
# run_features and run_bricscad; run_cross.plan additionally
# takes pair and reader_name. Plans are dicts of root-relative file lists:
# resave, rescore, carried, gaps. A resave includes its scoring; rescore is
# scoring without a save. Reading-only plans have no resaves.
# Native background execution entry point: regenerate.run_native(intent_id=None,
# force=False, root=None); regenerate.main remains the CLI orchestrator.
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ['CAD_DATASET_SETTINGS'] = str(Path(__file__).resolve().parents[1] / 'settings.example.json')
from checker import scoring
from test_drawing_inputs import tree, harness, dump, invoke, saved_bytes

KINDS = ['background', 'feature', 'bricscad', 'cross']


@pytest.fixture
def corpus(harness, monkeypatch):
    h = harness
    import ezdxf
    real_current = scoring.current
    real_reading_current = scoring.reading_current
    modules = [h.regen, h.feature, h.bc, h.cross]
    for module in modules:
        monkeypatch.setattr(module, 'current', real_current)
        if hasattr(module, 'reading_current'):
            monkeypatch.setattr(module, 'reading_current', real_reading_current)
    h.scored = []
    h.published = []
    h.read = []
    def compare(doc, intent, *args, **kwargs):
        rows = [dict(intent_id=intent['intent_id'], field='count', status='same',
                     reader='ezdxf ' + ezdxf.__version__, expected=2, actual=2, tolerance=0)]
        h.scored.extend(rows)
        return rows
    original_publish = h.regen.publish
    def publish(temp, dest, *args, **kwargs):
        h.published.append(dest.relative_to(h.root).as_posix())
        return original_publish(temp, dest, *args, **kwargs)
    for module in modules:
        monkeypatch.setattr(module, 'compare', compare)
        if hasattr(module, 'publish'):
            monkeypatch.setattr(module, 'publish', publish)
    def read_many(self, paths):
        h.read.extend(Path(p).relative_to(h.root).as_posix() for p in paths
                      if Path(p).is_relative_to(h.root / 'cross'))
        return dict.fromkeys(paths, SimpleNamespace())
    monkeypatch.setattr(h.bc.BricsCad, 'read_dwg_many', read_many)
    # The real LISP writes ASCII DXF, binary DXF and one binary DWG at 2000.
    def script(text, *args):
        out = Path(re.search(r'\(setq \*out-dir\* "([^"]+)"\)', text).group(1))
        topic = re.search(r'\(setq \*topic\* "([^"]+)"\)', text).group(1)
        (out / 'make_bricscad_masters.log').write_text('Synthetic generation\n')
        for enc, ext in [('ASCII', 'dxf'), ('binary', 'dxf'), ('binary', 'dwg')]:
            (out / f'{topic}_2000_{enc}.{ext}').write_bytes(saved_bytes('bricscad', ext.upper(), '2000', enc))
        return 0
    monkeypatch.setattr(h.bc, 'run_script', script)
    # Add the third native BricsCAD output; its sidecar must not define counts.
    source = h.root / 'native/bricscad/k_tables_2000_binary.dxf'
    target = source.with_suffix('.dwg')
    target.write_text('synthetic DWG')
    meta = json.loads(source.with_suffix('.dxf.provenance.json').read_text())
    meta.update(format='DWG', encoding='binary')
    dump(target.with_suffix('.dwg.provenance.json'), meta)
    h.paths = {
        'background': sorted(p.relative_to(h.root).as_posix() for p in (h.root / 'native/ezdxf').glob('background_*.dxf')),
        'feature': sorted(p.relative_to(h.root).as_posix() for p in (h.root / 'native/ezdxf').glob('synthetic_*.dxf')),
        'bricscad': sorted(p.relative_to(h.root).as_posix() for p in (h.root / 'native/bricscad').glob('*.d[xw][fg]')),
        'cross': sorted(d.relative_to(h.root).as_posix() for _, d, *_ in h.cross.jobs_for('ezdxf__oda')),
    }
    h.iids = dict(background='background_background', feature='feature_synthetic',
                  bricscad='future_synthetic', cross='feature_synthetic')
    h.result = dict(background='checks', feature='features_checks', bricscad='native_bricscad_checks',
                    cross='cross_ezdxf__oda_checks')
    for kind, paths in h.paths.items():
        rows = []
        for rel in paths:
            side = json.loads((h.root / (rel + '.provenance.json')).read_text())
            iid = side['intent_id']
            converter = 'oda synthetic-build' if rel.endswith('.dwg') else None
            row = dict(file=rel, intent_id=iid, field='count', status='same',
                       reader='ezdxf ' + ezdxf.__version__, converter=converter,
                       scored_with=scoring.stamp(h.root, iid), **engines(kind, rel))
            rows.append(row)
        dump(result_path(h, kind), rows)
    return h


def engines(kind, rel):
    """Engine fields a real row carries: the writer by runner kind, the reader ODA for DWG and ezdxf otherwise."""
    writer = scoring.ENGINES['bricscad' if kind == 'bricscad' else 'ezdxf']
    reader = scoring.ENGINES['oda' if rel.endswith('.dwg') else 'ezdxf']
    return dict(writer_engine=writer, reader_engine=reader, shared_engine=writer == reader)


def result_path(h, kind):
    return h.root / 'results' / (h.result[kind] + '.json')


def module_for(h, kind):
    return dict(background=h.regen, feature=h.feature, bricscad=h.bc,
                cross=h.cross)[kind]


def plan(h, kind, iid=None, force=False):
    module = module_for(h, kind)
    assert callable(getattr(module, 'plan', None)), f'{module.__name__} must expose plan()'
    kwargs = dict(intent_id=iid, force=force, root=h.root)
    if kind == 'cross':
        return module.plan('ezdxf__oda', reader_name='oda', **kwargs)
    return module.plan(**kwargs)


def run(h, kind, iid=None, force=False):
    if kind == 'cross':
        h.cross.run_pair('ezdxf__oda', intent=iid, force=force, reader_name='oda', root=h.root)
    elif kind == 'background':
        h.regen.run_native(iid, force=force, root=h.root)
    else:
        module_for(h, kind).main(iid, force=force, root=h.root)


def normalized(value):
    assert set(value) >= {'resave', 'rescore', 'carried', 'gaps'}
    return {key: sorted(value[key]) for key in ('resave', 'rescore', 'carried', 'gaps')}


def mutate(h, kind, state):
    paths = h.paths[kind]
    if state == 'score':
        rows = json.loads(result_path(h, kind).read_text())
        for row in rows:
            if row['file'] == paths[0]:
                row['scored_with']['checker'] = 'synthetic obsolete checker'
        dump(result_path(h, kind), rows)
    elif state == 'input':
        sc = h.root / (paths[0] + '.provenance.json')
        meta = json.loads(sc.read_text()); meta['made_by']['input_digest'] = 'obsolete'
        dump(sc, meta)
    elif state in ('missing', 'deleted_output'):
        (h.root / paths[0]).unlink()
        if state == 'deleted_output':
            (h.root / (paths[0] + '.provenance.json')).unlink()
    elif state in ('empty', 'orphan_sidecars'):
        for rel in paths:
            (h.root / rel).unlink()
            if state == 'empty':
                (h.root / (rel + '.provenance.json')).unlink()


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('state', ['current', 'input', 'score', 'missing', 'deleted_output', 'empty', 'orphan_sidecars', 'force', 'intent'])
def test_plan_lists_and_execution(corpus, monkeypatch, capsys, kind, state):
    h = corpus
    mutate(h, kind, state)
    paths = h.paths[kind]
    iid = h.iids[kind] if state == 'intent' else None
    if iid:
        paths = [p for p in paths if json.loads((h.root / (p + '.provenance.json')).read_text())['intent_id'] == iid]
    resave, rescore = [], []
    if state in ('empty', 'orphan_sidecars', 'force') or kind == 'bricscad' and state in ('input', 'missing', 'deleted_output'):
        resave = paths
    elif state in ('input', 'missing', 'deleted_output'):
        resave = paths[:1]
    elif state == 'score':
        rescore = paths[:1]
    expected = dict(resave=sorted(resave), rescore=sorted(rescore),
                    carried=sorted(set(paths) - set(resave) - set(rescore)), gaps=[])
    before = {p.relative_to(h.root).as_posix(): p.read_bytes() for p in h.root.rglob('*') if p.is_file()}
    actual = normalized(plan(h, kind, iid, state == 'force'))
    assert actual == expected
    assert before == {p.relative_to(h.root).as_posix(): p.read_bytes() for p in h.root.rglob('*') if p.is_file()}, 'Planning must be read-only'
    pair = 'bricscad__oda' if kind == 'bricscad' else 'ezdxf__oda'
    monkeypatch.setattr(h.cross, 'PAIRS', dict(h.cross.PAIRS, bricscad__oda=('native/bricscad', 'oda')))
    arguments = ['--pairs', pair, '--with-bricscad', '--dry-run']
    if iid:
        arguments += ['--intent', iid]
    if state == 'force':
        arguments += ['--force']
    # Force affects every selected runner. With no intent filter, both ezdxf
    # native cohorts contribute to the native summary.
    dry_save, dry_score = len(resave), len(rescore)
    if kind in ('background', 'feature') and state == 'force':
        other_kind = 'feature' if kind == 'background' else 'background'
        dry_save += len(h.paths[other_kind])
    invoke(h, monkeypatch, *arguments)
    output = capsys.readouterr().out
    label = {'background': 'native', 'feature': 'native', 'bricscad': 'native bricscad',
             'cross': 'ezdxf__oda'}[kind]
    assert f'{label}: {dry_save} resave, {dry_score} rescore' in output
    assert not h.published and not h.scored and not h.read
    runner_plan = Mock(wraps=module_for(h, kind).plan)
    monkeypatch.setattr(module_for(h, kind), 'plan', runner_plan)
    run(h, kind, iid, state == 'force')
    assert runner_plan.called, 'Real execution must consume its runner plan'
    assert sorted(h.published) == expected['resave']
    assert sorted({r['file'] for r in h.scored}) == sorted(resave + rescore)
    after = normalized(plan(h, kind, iid))
    assert after == dict(resave=[], rescore=[], carried=sorted(paths), gaps=[])


@pytest.mark.parametrize('kind', KINDS)
def test_selected_run_keeps_other_intent_stale(corpus, monkeypatch, kind):
    h = corpus
    iid = h.iids[kind]
    other = 'future_other_synthetic' if kind == 'bricscad' else 'feature_other_synthetic' if kind == 'feature' else 'background_other_synthetic'
    original = json.loads((h.root / 'intent' / f'{iid}.json').read_text())
    original['intent_id'] = other
    dump(h.root / 'intent' / f'{other}.json', original)
    if kind == 'bricscad':
        monkeypatch.setattr(h.bc, 'TOPICS', dict(h.bc.TOPICS, k_regions_solids=other))
    elif kind == 'feature':
        monkeypatch.setattr(h.feature, 'TOPICS', ['synthetic', 'other_synthetic'])
    # Clone a real fixture output and sidecar for the unselected intent.
    source = h.root / h.paths[kind][0]
    dest = source.with_name('k_regions_solids_2000_ASCII.dxf' if kind == 'bricscad'
                            else 'other_synthetic_2000_ASCII' + source.suffix)
    dest.write_bytes(source.read_bytes())
    meta = json.loads(source.with_suffix(source.suffix + '.provenance.json').read_text())
    meta['intent_id'] = other
    dump(dest.with_suffix(dest.suffix + '.provenance.json'), meta)
    stale = dict(file=dest.relative_to(h.root).as_posix(), intent_id=other,
                 field='count', status='same', scored_with=dict(scoring.stamp(h.root, other), checker='obsolete'))
    path = result_path(h, kind)
    rows = json.loads(path.read_text())
    # All pre-existing unselected rows are stale too; none may be re-annotated.
    for row in rows:
        if row['intent_id'] != iid:
            row['scored_with']['checker'] = 'obsolete'
    rows.append(stale)
    dump(path, rows)
    before = [r for r in rows if r['intent_id'] != iid]
    assert not scoring.current([stale], h.root, other)
    selected = normalized(plan(h, kind, iid, True))
    assert all(json.loads((h.root / (p + '.provenance.json')).read_text())['intent_id'] == iid
               for key in ('resave', 'rescore', 'carried') for p in selected[key])
    run(h, kind, iid, True)
    after = json.loads(path.read_text())
    assert [r for r in after if r['intent_id'] != iid] == before
    assert any(r['intent_id'] == iid for r in after), 'Selected intent must actually be scored'
    assert not scoring.current([r for r in after if r['intent_id'] == other], h.root, other)


@pytest.mark.parametrize('kind', KINDS)
def test_zero_applicable_fields_current_after_one_run(corpus, monkeypatch, kind):
    h = corpus
    from checker.core import compare as real_compare
    iid = h.iids[kind]
    ip = h.root / 'intent' / f'{iid}.json'
    intent = json.loads(ip.read_text())
    # A nonempty intent with fields only in a later version reproduces WP7.
    intent['expected'][0]['versions'] = ['AC1032']
    dump(ip, intent)
    doc = SimpleNamespace(dxfversion='AC1015')
    zero_calls = []
    def zero_compare(_doc, intent, reader, source_version=None):
        zero_calls.append(intent['intent_id'])
        return real_compare(doc, intent, reader, source_version)
    monkeypatch.setattr(module_for(h, kind), 'compare', zero_compare)
    assert real_compare(doc, intent, 'synthetic reader') == []
    run(h, kind, iid, True)
    assert zero_calls, 'The drawing must actually be scored once'
    zero_calls.clear()
    after = normalized(plan(h, kind, iid))
    assert after['resave'] == []
    assert after['rescore'] == []
    selected = [p for p in h.paths[kind]
                if json.loads((h.root / (p + '.provenance.json')).read_text())['intent_id'] == iid]
    assert after['carried'] == sorted(selected)
    # This must survive loading persisted scores, not just an in-memory cache.
    h.scored.clear(); h.published.clear(); h.read.clear()
    run(h, kind, iid)
    assert not h.published and not h.read and not h.scored and not zero_calls


def test_capability_gaps_are_separate_from_resaves(corpus, monkeypatch, capsys):
    h = corpus
    paths = h.paths['cross']
    gap = next(p for p in paths if p.endswith('_binary.dxf'))
    (h.root / gap).unlink()
    key = 'ezdxf__oda|' + gap
    caps_path = h.root / 'programs/capabilities.json'
    caps = json.loads(caps_path.read_text())
    caps['oda']['outputs'] = [o for o in caps['oda']['outputs'] if o != ['DXF', '2000', 'binary']]
    dump(caps_path, caps)
    dump(h.root / 'results/cross_not_run.json', {key: 'Synthetic declared limitation'})
    dump(h.root / 'results/cross_gap_builds.json', {key: h.cross.ADAPTERS['oda'].build})
    expected = dict(resave=[], rescore=[], carried=sorted(set(paths) - {gap}), gaps=[gap])
    assert normalized(plan(h, 'cross')) == expected
    run(h, 'cross')
    assert not h.published and not h.scored
    invoke(h, monkeypatch, '--pairs', 'ezdxf__oda', '--dry-run')
    output = capsys.readouterr().out
    assert re.search(r'ezdxf__oda: 0 resave, 0 rescore.*1 (?:capability )?gap', output), output


@pytest.mark.parametrize('with_bricscad', [False, True])
@pytest.mark.parametrize('pair', ['ezdxf__oda', 'bricscad__oda'])
@pytest.mark.parametrize('dry', [False, True])
def test_no_bricscad_reading_step_is_selected(corpus, monkeypatch, capsys, with_bricscad, pair, dry):
    h = corpus
    monkeypatch.setattr(h.cross, 'PAIRS', dict(h.cross.PAIRS, bricscad__oda=('native/bricscad', 'oda')))
    # This test isolates orchestration; runner execution is covered above.
    monkeypatch.setattr(h.feature, 'main', Mock())
    monkeypatch.setattr(h.bc, 'main', Mock())
    monkeypatch.setattr(h.cross, 'run_pair', Mock())
    monkeypatch.setattr(h.regen, 'run_native', Mock(), raising=False)
    arguments = ['--intent', 'feature_synthetic', '--pairs', pair]
    if with_bricscad:
        arguments.append('--with-bricscad')
    if dry:
        arguments.append('--dry-run')
    invoke(h, monkeypatch, *arguments)
    # ODA-written DWG is read through BricsCAD by run_cross; no separate step repeats it.
    output = capsys.readouterr().out
    assert 'read by bricscad' not in output


@pytest.mark.parametrize('kind', ['background', 'feature', 'bricscad'])
@pytest.mark.parametrize('force', [False, True])
def test_regenerate_passes_intent_force_root(corpus, monkeypatch, kind, force):
    h = corpus
    native = Mock()
    if kind == 'background':
        monkeypatch.setattr(h.regen, 'run_native', native, raising=False)
    else:
        monkeypatch.setattr(module_for(h, kind), 'main', native)
    cross = Mock()
    monkeypatch.setattr(h.cross, 'run_pair', cross)
    pair = 'bricscad__oda' if kind == 'bricscad' else 'ezdxf__oda'
    monkeypatch.setattr(h.cross, 'PAIRS', dict(h.cross.PAIRS, bricscad__oda=('native/bricscad', 'oda')))
    arguments = ['--intent', h.iids[kind], '--pairs', pair, '--with-bricscad']
    if force:
        arguments.append('--force')
    invoke(h, monkeypatch, *arguments)
    native.assert_called_once_with(h.iids[kind], force=force, root=h.root)
    cross.assert_called_once_with(pair, intent=h.iids[kind], reader_name=None, force=force, root=h.root)


@pytest.mark.parametrize('force', [False, True])
def test_dry_run_prints_runner_plans_without_deciding(corpus, monkeypatch, capsys, force):
    h = corpus
    spies = {}
    # Deliberately disagree with disk: dry-run must trust each runner's plan.
    plans = {
        'background': dict(resave=h.paths['background'][:1], rescore=[], carried=h.paths['background'][1:], gaps=[]),
        'feature': dict(resave=[], rescore=h.paths['feature'], carried=[], gaps=[]),
        'bricscad': dict(resave=h.paths['bricscad'], rescore=[], carried=[], gaps=[]),
        'cross': dict(resave=h.paths['cross'][:2], rescore=h.paths['cross'][2:3], carried=h.paths['cross'][3:], gaps=[]),
    }
    for kind in KINDS:
        spies[kind] = Mock(return_value=plans[kind])
        monkeypatch.setattr(module_for(h, kind), 'plan', spies[kind], raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail('Dry-run duplicated a runner decision rule')
    for module in [h.regen, h.feature, h.bc, h.cross]:
        monkeypatch.setattr(module, 'current', forbidden)
    arguments = ['--pairs', 'ezdxf__oda', '--with-bricscad', '--dry-run']
    if force:
        arguments.append('--force')
    invoke(h, monkeypatch, *arguments)
    output = capsys.readouterr().out
    for kind, spy in spies.items():
        assert spy.call_count == int(kind != 'bricscad'), kind
        if kind == 'bricscad':
            continue
        assert spy.call_args.kwargs.get('root') == h.root
        assert spy.call_args.kwargs.get('force') is force
    for line in ['native: 1 resave, 2 rescore',
                 'ezdxf__oda: 2 resave, 1 rescore']:
        assert line in output
    assert 'read by bricscad' not in output
    assert 'native bricscad:' not in output
    assert not h.saved and not h.published and not h.scored and not h.read
