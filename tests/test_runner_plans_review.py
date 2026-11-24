"""WP7 review contracts; independent synthetic expectations and fake CAD only."""
import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from checker import scoring
from test_drawing_inputs import tree, harness, dump, invoke
from test_runner_plans import corpus, plan, run, result_path


def rows(h, kind):
    return json.loads(result_path(h, kind).read_text())


def forget_outputs(h, kind):
    for rel in h.paths[kind]:
        (h.root / rel).unlink(missing_ok=True)
        (h.root / (rel + '.provenance.json')).unlink(missing_ok=True)


@pytest.mark.parametrize('failure', ['no_output', 'program_refusal'])
@pytest.mark.parametrize('retry', ['unchanged', 'build', 'input', 'force'])
def test_cross_refusal_converges_and_retries(corpus, monkeypatch, failure, retry):
    h = corpus
    forget_outputs(h, 'cross')
    calls = []
    def refuse(self, jobs):
        calls.extend(jobs)
        return {job[1]: None if failure == 'no_output' else 'Synthetic program rejected input'
                for job in jobs}
    adapter = h.cross.ADAPTERS['oda']
    monkeypatch.setattr(adapter, 'save_many', refuse)
    run(h, 'cross')
    assert len(calls) == len(h.paths['cross'])
    refused = rows(h, 'cross')
    assert {r['file'] for r in refused if r['status'] == 'refused'} == set(h.paths['cross'])
    assert all(r.get('scored_with') == scoring.stamp(h.root, r['intent_id']) for r in refused)
    if retry == 'build':
        monkeypatch.setattr(adapter, 'build', 'synthetic-new-build')
    elif retry == 'input':
        for source in (h.root / 'native/ezdxf').glob('*.provenance.json'):
            meta = json.loads(source.read_text())
            meta['content_digest'] = 'synthetic-new-input'
            dump(source, meta)
    work = plan(h, 'cross', force=retry == 'force')
    expected = 'carried' if retry == 'unchanged' else 'resave'
    assert sorted(work[expected]) == h.paths['cross']
    assert not work['gaps'] and not work['rescore']
    assert not work['resave' if expected == 'carried' else 'carried']
    if retry == 'unchanged':
        calls.clear()
        run(h, 'cross')
        assert not calls, 'A current refusal must not invoke the resaver again'


@pytest.mark.parametrize('retry', ['unchanged', 'build', 'input', 'force'])
def test_native_bricscad_missing_refusal_converges(corpus, monkeypatch, retry):
    h = corpus
    # Keep valid siblings: a refused missing file must not rebuild the topic.
    missing = h.paths['bricscad'][0]
    (h.root / missing).unlink()
    calls = []
    def no_output(script, *args):
        calls.append(script)
        out = Path(re.search(r'\(setq \*out-dir\* "([^"]+)"\)', script).group(1))
        (out / 'make_bricscad_masters.log').write_text('Synthetic refusal\n')
        return 0
    monkeypatch.setattr(h.bc, 'run_script', no_output)
    run(h, 'bricscad')
    assert calls
    refused = [r for r in rows(h, 'bricscad') if r['file'] == missing]
    assert refused and all(r['status'] == 'refused' for r in refused)
    assert all(r.get('scored_with') == scoring.stamp(h.root, r['intent_id']) for r in refused)
    if retry == 'build':
        monkeypatch.setattr(h.bc.BricsCad, 'build', 'synthetic-new-build')
    elif retry == 'input':
        with h.bc.LSP.open('a') as stream:
            stream.write('\n; synthetic drawing input changed\n')
    work = plan(h, 'bricscad', force=retry == 'force')
    expected = 'carried' if retry == 'unchanged' else 'resave'
    assert sorted(work[expected]) == h.paths['bricscad']
    assert not work['rescore'] and not work['gaps']
    if retry == 'unchanged':
        assert not work['resave']
        calls.clear()
        run(h, 'bricscad')
        assert not calls


def orchestration_spies(h, monkeypatch):
    spies = {}
    for name, module, entry in [('background', h.regen, 'run_native'),
                                ('feature', h.feature, 'main'),
                                ('bricscad', h.bc, 'main'),
                                ('cross', h.cross, 'run_pair')]:
        spies[name] = Mock()
        monkeypatch.setattr(module, entry, spies[name])
    return spies


@pytest.mark.parametrize('with_bricscad', [False, True])
@pytest.mark.parametrize('pair', ['ezdxf__oda', 'bricscad__oda'])
@pytest.mark.parametrize('dry', [False, True])
def test_pairs_scope_matches_dry_run(corpus, monkeypatch, capsys, with_bricscad, pair, dry):
    h = corpus
    monkeypatch.setattr(h.cross, 'PAIRS', dict(h.cross.PAIRS, bricscad__oda=('native/bricscad', 'oda')))
    spies = orchestration_spies(h, monkeypatch)
    planners = {}
    for name, module in [('background', h.regen), ('feature', h.feature),
                         ('bricscad', h.bc), ('cross', h.cross)]:
        planners[name] = Mock(return_value=dict(resave=[], rescore=[], carried=[], gaps=[]))
        monkeypatch.setattr(module, 'plan', planners[name])
    args = ['--pairs', pair]
    if with_bricscad:
        args.append('--with-bricscad')
    if dry:
        args.append('--dry-run')
    invoke(h, monkeypatch, *args)
    selected = {'cross'} | ({'background', 'feature'} if pair == 'ezdxf__oda' else {'bricscad'})
    for name in spies:
        assert spies[name].call_count == int(not dry and name in selected), name
        assert planners[name].call_count == int(dry and name in selected), name
    output = capsys.readouterr().out
    if dry:
        assert ('native:' in output) == (pair == 'ezdxf__oda')
        assert ('native bricscad:' in output) == (pair == 'bricscad__oda')
        assert f'{pair}:' in output
        assert 'read by bricscad' not in output


def fake_full_run(h, monkeypatch):
    # Full-run bookkeeping is exercised; all unrelated publication and process
    # entry points are replaced, including measure_size's subprocess.
    spies = orchestration_spies(h, monkeypatch)
    import map.build
    import intent.validate
    monkeypatch.setattr(map.build, 'main', Mock())
    monkeypatch.setattr(intent.validate, 'main', Mock())
    monkeypatch.setattr(h.regen.subprocess, 'run', Mock())
    return spies


def test_full_run_preserves_native_failure_guard(corpus, monkeypatch):
    h = corpus
    native = h.regen.run_native
    fake_full_run(h, monkeypatch)
    # Keep the real native runner so a guard in either the runner or the
    # orchestrator can satisfy the contract.
    monkeypatch.setattr(h.regen, 'run_native', native)
    monkeypatch.setattr(h.regen, 'compare', lambda *a, **kw: [dict(
        intent_id='background_background', field='count', status='differs',
        reader='synthetic reader', expected=2, actual=3, tolerance=0)])
    with pytest.raises(RuntimeError, match='Native expected-field failures'):
        invoke(h, monkeypatch, '--force')
    assert any(r['status'] == 'differs' for r in rows(h, 'background'))


def test_full_run_writes_barriers(corpus, monkeypatch):
    h = corpus
    fake_full_run(h, monkeypatch)
    invoke(h, monkeypatch)
    path = h.root / 'results/barriers.json'
    assert path.is_file(), 'A full run must persist the barriers report'
    assert isinstance(json.loads(path.read_text()), list)


def test_full_run_prints_final_status_summary(corpus, monkeypatch, capsys):
    h = corpus
    fake_full_run(h, monkeypatch)
    invoke(h, monkeypatch)
    summaries = []
    for line in capsys.readouterr().out.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and 'statuses' in value:
            summaries.append(value)
    assert summaries, 'The full run must print its final JSON status summary'
    summary = summaries[-1]
    native = rows(h, 'background')
    assert summary['fields'] == len(native)
    assert summary['statuses'] == {s: sum(r['status'] == s for r in native)
                                   for s in ('same', 'differs', 'absent')}
    assert summary['files'] == len(json.loads((h.root / 'results/audits.json').read_text()))
    assert summary['barriers'] == json.loads((h.root / 'results/barriers.json').read_text())


@pytest.mark.parametrize('dry', [False, True])
@pytest.mark.parametrize('with_bricscad', [False, True])
def test_intent_without_generator_is_usage_error(corpus, monkeypatch, capsys, dry, with_bricscad):
    h = corpus
    spies = orchestration_spies(h, monkeypatch)
    dump(h.root / 'intent/wanted_synthetic.json', dict(intent_id='wanted_synthetic', status='wanted'))
    args = ['--intent', 'wanted_synthetic']
    if dry:
        args.append('--dry-run')
    if with_bricscad:
        args.append('--with-bricscad')
    with pytest.raises(SystemExit) as ex:
        invoke(h, monkeypatch, *args)
    assert ex.value.code == 2
    assert 'generator' in capsys.readouterr().err.lower()
    assert not any(spy.called for spy in spies.values())


def test_cannot_write_text_is_not_a_declared_gap(corpus, monkeypatch):
    h = corpus
    forget_outputs(h, 'cross')
    # ODA declares every fixture output writable. The words alone cannot
    # override that declaration (e.g. a transient file-system failure).
    monkeypatch.setattr(h.cross.ADAPTERS['oda'], 'save_many',
                        lambda self, jobs: {j[1]: 'cannot write temporary file: synthetic storage failure'
                                           for j in jobs})
    run(h, 'cross')
    refused = rows(h, 'cross')
    assert {r['file'] for r in refused if r['status'] == 'refused'} == set(h.paths['cross'])
    assert not plan(h, 'cross')['gaps']
    gaps = h.root / 'results/cross_not_run.json'
    assert not gaps.exists() or not json.loads(gaps.read_text())


@pytest.mark.parametrize('dimension', ['format', 'version', 'encoding'])
def test_declared_gap_records_build(corpus, monkeypatch, dimension):
    h = corpus
    # Declare a missing format, version, or encoding through the existing
    # capability schema, and return wording that contains no magic substring.
    path = h.root / 'programs/capabilities.json'
    caps = json.loads(path.read_text())
    def writable(fmt, version, encoding):
        return dict(format=fmt != 'DWG', version=version != '2000',
                    encoding=(fmt, encoding) != ('DXF', 'binary'))[dimension]
    caps['oda']['outputs'] = [o for o in caps['oda']['outputs'] if writable(*o)]
    if dimension == 'format':
        caps['oda']['formats'].pop('DWG')
    elif dimension == 'version':
        caps['oda']['versions'].remove('2000')
    else:
        caps['oda']['formats']['DXF'] = ['ASCII']
    dump(path, caps)
    adapter = h.cross.ADAPTERS['oda']
    original = adapter.save_many
    def save(self, jobs):
        supported = [j for j in jobs if writable(j[2], j[3], j[4])]
        result = original(self, supported)
        result.update({j[1]: 'Synthetic unsupported output tuple' for j in jobs if j not in supported})
        return result
    monkeypatch.setattr(adapter, 'save_many', save)
    forget_outputs(h, 'cross')
    run(h, 'cross')
    gaps = sorted(dest.relative_to(h.root).as_posix()
                  for _, dest, fmt, version, enc, _ in h.cross.jobs_for('ezdxf__oda', root=h.root)
                  if not writable(fmt, version, enc))
    assert gaps
    keys = ['ezdxf__oda|' + p for p in gaps]
    recorded = json.loads((h.root / 'results/cross_not_run.json').read_text())
    assert sorted(recorded) == sorted(keys)
    builds_path = h.root / 'results/cross_gap_builds.json'
    builds = json.loads(builds_path.read_text())
    assert all(builds[k] == adapter.build for k in keys)
    work = plan(h, 'cross')
    assert sorted(work['gaps']) == gaps
    assert not work['resave'] and not work['rescore']


@pytest.mark.parametrize('retry', ['unchanged', 'missing_build', 'build', 'force'])
def test_recorded_gap_retry_policy(corpus, monkeypatch, retry):
    h = corpus
    # Seed established on-disk gap records independently: broken gap creation
    # must not hide a second defect in the planner's retry policy.
    gap = next(p for p in h.paths['cross'] if p.endswith('_binary.dxf'))
    (h.root / gap).unlink()
    key = 'ezdxf__oda|' + gap
    caps_path = h.root / 'programs/capabilities.json'
    caps = json.loads(caps_path.read_text())
    caps['oda']['outputs'] = [o for o in caps['oda']['outputs'] if o != ['DXF', '2000', 'binary']]
    caps['oda']['formats']['DXF'] = ['ASCII']
    dump(caps_path, caps)
    adapter = h.cross.ADAPTERS['oda']
    dump(h.root / 'results/cross_not_run.json', {key: 'Synthetic declared limitation'})
    dump(h.root / 'results/cross_gap_builds.json',
         {} if retry == 'missing_build' else {key: adapter.build})
    if retry == 'build':
        monkeypatch.setattr(adapter, 'build', 'synthetic-new-build')
    work = plan(h, 'cross', force=retry == 'force')
    if retry == 'unchanged':
        assert work['gaps'] == [gap]
        assert not work['resave'] and not work['rescore']
    else:
        assert not work['gaps']
        assert gap in work['resave']


@pytest.mark.parametrize('dry', [False, True])
def test_without_pairs_native_steps_remain_selected(corpus, monkeypatch, dry):
    h = corpus
    spies = fake_full_run(h, monkeypatch)
    planners = {}
    for name, module in [('background', h.regen), ('feature', h.feature),
                         ('bricscad', h.bc), ('cross', h.cross)]:
        planners[name] = Mock(return_value=dict(resave=[], rescore=[], carried=[], gaps=[]))
        monkeypatch.setattr(module, 'plan', planners[name])
    args = ['--with-bricscad'] + (['--dry-run'] if dry else [])
    invoke(h, monkeypatch, *args)
    for name in spies:
        count = len(h.cross.PAIRS) if name == 'cross' else 1
        assert spies[name].call_count == count * int(not dry), name
        assert planners[name].call_count == count * int(dry), name
    calls = planners['cross'].call_args_list if dry else spies['cross'].call_args_list
    assert sorted(call.args[0] for call in calls) == sorted(h.cross.PAIRS)
