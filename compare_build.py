"""Compare an isolated program build with published cross-pair measurements."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import argparse
import collections
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from programs import adapters
from programs.cadcraft_mcp import HarnessError, launch_options
from generators import run_cross as cross

# map/template.html compatibility rank, mapped to checker statuses.
RANK = {'same': 0, 'not run': 1, 'differs': 2, 'absent': 3, 'refused': 4}


def snapshot():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
    return {n.decode(): hashlib.sha256((ROOT/n.decode()).read_bytes()).hexdigest()
            for n in names if n and (ROOT/n.decode()).is_file()}


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program', required=True, choices=['cadcraft'])
    p.add_argument('--binary', required=True, type=Path)
    p.add_argument('--label', required=True)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--pairs', nargs='+', help='Pair IDs, separated by spaces or commas')
    p.add_argument('--intent')
    p.add_argument('--overwrite', action='store_true', help='Replace the existing run directory')
    a = p.parse_args()
    if Path(a.label).name != a.label or a.label in ('.', '..'): p.error('label must be a filename component')
    out = a.out.resolve()
    if out == ROOT or ROOT in out.parents: p.error('--out must be outside the published repository')
    binary = a.binary.resolve()
    if not binary.is_file(): p.error('binary does not exist')
    pairs = [k for k, v in cross.PAIRS.items() if v[1] == a.program]
    if a.pairs:
        chosen = [k for group in a.pairs for k in group.split(',')]
        if any(k not in pairs for k in chosen): p.error('pairs must name declared pairs re-saved by the selected program')
        pairs = chosen
    if a.intent and not (ROOT/'intent'/f'{a.intent}.json').is_file(): p.error('unknown intent')
    before = snapshot()
    run = out/a.label
    if run.exists():
        if not a.overwrite: p.error(f'run destination already exists: {run}')
        shutil.rmtree(run)
    run.mkdir(parents=True)
    (run/'results').mkdir()
    shutil.copytree(ROOT/'intent', run/'intent')
    commit = subprocess.run(['git', '-C', str(binary.parent), 'log', '-1', '--format=%h'], capture_output=True, text=True)
    commit = commit.stdout.strip() if commit.returncode == 0 else None
    baseline = adapters.CadCraft.build
    provenance = {'binary': str(binary), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                  'commit': commit, 'published_build': baseline,
                  'different_baseline_commit': bool(commit and not baseline.startswith(commit))}
    try:
        provenance['mcp_launch_options'] = launch_options(binary, '<workdir>')
        probe_error = None
    except HarnessError as ex:
        provenance['mcp_launch_options'] = None
        probe_error = str(ex)
    adapters.CadCraft.binary = str(binary)
    adapters.CadCraft.build = commit or baseline
    adapters.SCRATCH_ROOT = run/'results'
    original_jobs = cross.jobs_for
    jobs = {pair: original_jobs(pair, intent=a.intent) for pair in pairs}
    def isolated_jobs(pair, limit=None, intent=None):
        return [(s, run/d.relative_to(ROOT), *rest) for s, d, *rest in jobs[pair]][:limit]
    cross.jobs_for = isolated_jobs
    cross.R = run
    cross.LOG = run/'progress.log'
    failures = {}
    for pair in pairs:
        if probe_error:
            failures[pair] = probe_error
            continue
        try:
            cross.run_pair(pair, intent=a.intent, reader_name='oda', retain_unreadable=True)
        except HarnessError as ex:
            failures[pair] = str(ex)
            print(f'{pair}: could not run this build: {ex}', flush=True)
    rows = []
    cells = collections.defaultdict(collections.Counter)
    for pair in pairs:
        if pair in failures: continue
        published = read(ROOT/'results'/f'cross_{pair}_checks.json', [])
        built = read(run/'results'/f'cross_{pair}_checks.json', [])
        old = {(r['file'], r['field']): r for r in published}
        new = {(r['file'], r['field']): r for r in built}
        allowed = {str(d.relative_to(ROOT)): side for _, d, *_, side in jobs[pair]}
        for file in sorted(allowed):
            side = allowed[file]
            intent = read(ROOT/'intent'/f"{side['intent_id']}.json")
            fields = {f for path, f in old.keys() | new.keys() if path == file and f != 'open'}
            if not fields: fields = {'open'}
            for field in sorted(fields):
                b = old.get((file, field), old.get((file, 'open'), {'status': 'not run', 'actual': None}))
                n = new.get((file, field), new.get((file, 'open'), {'status': 'not run', 'actual': None}))
                delta = RANK[n['status']] - RANK[b['status']]
                change = 'improved' if delta < 0 else 'worsened' if delta > 0 else 'unchanged'
                features = [f for f, ids in intent.get('feature_fields', {}).items() if field in ids] or [intent['title']]
                row = dict(pair=pair, file=file, intent_id=side['intent_id'], field=field, features=features,
                           published=b, build=n, change=change)
                rows.append(row)
                for feature in features:
                    cell = (pair, side['intent_id'], feature, Path(file).suffix[1:].upper(), side['version'], 'binary' if file.endswith('.dwg') else side['encoding'])
                    cells[cell][change] += 1
    rows.sort(key=lambda r: (-RANK[r['published']['status']], -RANK[r['build']['status']], r['file'], r['field']))
    counts = {k: sum(r['change'] == k for r in rows) for k in ('improved', 'worsened', 'unchanged')}
    after = snapshot()
    result = dict(label=a.label, provenance=provenance, failures=failures, counts=counts, rows=rows,
                  cells=[dict(cell=list(k), counts=dict(v)) for k, v in sorted(cells.items())],
                  repository_unchanged=before == after,
                  changed_repository_paths=sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k)))
    cross.write_json(out/f'{a.label}-compare.json', result)
    cross.write_json(out/f'{a.label}-repository-before.json', before)
    cross.write_json(out/f'{a.label}-repository-after.json', after)
    lines = [f'# {a.label}', '', json.dumps(provenance), '',
             'The baseline is a different commit.' if provenance['different_baseline_commit'] else '',
             f'Field counts: {counts}', '',
             f'Repository unchanged: {before == after}. Changed paths: {result["changed_repository_paths"]}', '',
             'Counts describe field status transitions; unchanged can include differing actual values with the same status.', '',
             '| Pair / feature / format / version / encoding | Improved | Worsened | Unchanged |', '| --- | ---: | ---: | ---: |']
    lines[4:4] = [f'{pair}: could not run this build: {reason}' for pair, reason in failures.items()]
    lines += ['| '+' / '.join(k)+' | '+' | '.join(str(v[x]) for x in counts)+' |' for k, v in sorted(cells.items())]
    lines += ['', '| File | Field | Published status / value | Build status / value | Change |', '| --- | --- | --- | --- | --- |']
    def value(r): return (r['status']+' / '+json.dumps(r.get('actual'), ensure_ascii=False)).replace('|', '\\|').replace('\n', ' ')
    lines += [f"| {r['file']} | {r['field']} | {value(r['published'])} | {value(r['build'])} | {r['change']} |" for r in rows]
    (out/f'{a.label}-compare.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(label=a.label, counts=counts, repository_unchanged=before == after)), flush=True)
    if before != after: raise RuntimeError('Published repository changed during comparison')


if __name__ == '__main__': main()
