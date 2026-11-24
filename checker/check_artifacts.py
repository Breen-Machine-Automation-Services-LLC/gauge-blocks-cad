"""Check published evidence, score currency, uniqueness and derived files."""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checker.scoring import current, stamp
from checker.derived import DERIVED, rebuild

R = Path(__file__).resolve().parents[1]
failures = []


def fail(file, message, command):
    failures.append(f'{file}: {message}; run {command}')


def evidence(name, predicate, command):
    path = R / name
    try:
        data = json.loads(path.read_text())
        if not predicate(data):
            fail(name, 'invalid evidence', command)
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(name, str(exc), command)
        return []


a = evidence('results/audits.json', lambda x: len(x) == 77 and all(r['errors'] == 0 for r in x), 'python regenerate.py')
r = evidence('results/checks.json', lambda x: all(row['status'] == 'same' for row in x if row['file'].startswith('native/')), 'python regenerate.py')
e = evidence('results/digest_evidence.json', lambda x: len(x) == 13 and all(row['equal'] and row['one_field_changes_digest'] for row in x), 'python checker/test_digest.py')
for path in (R / 'native').rglob('*.dxf'):
    if bytes([47, 104, 111, 109, 101, 47]) in path.read_bytes() or b'/tmp/' in path.read_bytes():
        fail(path.relative_to(R), 'local path in drawing', 'python regenerate.py')
try:
    if '\u2014' in (R / 'README.md').read_text():
        fail('README.md', 'contains an em dash', 'edit README.md')
except OSError as exc:
    fail('README.md', str(exc), 'restore README.md')

# Resolve the same source digest and build that each planner uses for refusals.
refusal_inputs = None

def refusal_context():
    global refusal_inputs
    if refusal_inputs is None:
        from generators import run_cross, run_bricscad
        from checker.scoring import native_input
        refusal_inputs = {}
        for pair in run_cross.PAIRS:
            build = run_cross.ADAPTERS[pair.split('__')[1]].build
            for _, dest, _, _, _, side in run_cross.jobs_for(pair, root=R):
                refusal_inputs[dest.relative_to(R).as_posix()] = (side['content_digest'], build)
        for topic, iid in run_bricscad.TOPICS.items():
            if (R / 'intent' / (iid + '.json')).exists():
                inp = native_input(R, iid, 'bricscad', lsp=R / 'generators/bricscad/make_bricscad_masters.lsp')[0]
                for dest in run_bricscad._outputs(R, topic):
                    refusal_inputs[dest.relative_to(R).as_posix()] = (inp, run_bricscad.BricsCad.build)
    return refusal_inputs


owners = {}
duplicates = set()
stamps = {}
for path in sorted((R / 'results').glob('*checks.json')):
    try:
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        count = 0
        for row in rows:
            key = tuple(row.get(k) for k in ('file', 'field', 'reader', 'converter'))
            previous = owners.setdefault(key, path.name)
            if previous != path.name:
                duplicates.add((previous, path.name))
            try:
                iid = row['intent_id']
                if row.get('status') == 'refused':
                    inp, build = refusal_context().get(row['file'], (None, None))
                    valid = current([row], R, iid, inp, build)
                else:
                    if iid not in stamps:
                        stamps[iid] = stamp(R, iid)
                    valid = current([row], R, iid, score=stamps[iid])
            except (OSError, KeyError, ValueError, TypeError):
                valid = False
            count += not valid
        if count:
            fail(path.relative_to(R), f'{count} stale rows', 'python regenerate.py')
    except (OSError, ValueError, TypeError) as exc:
        fail(path.relative_to(R), str(exc), 'python regenerate.py')
for first, second in sorted(duplicates):
    fail(f'results/{first} and results/{second}', 'duplicate measurements', 'python regenerate.py')

with TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
    try:
        rebuild(Path(tmp))
        for names, command, _ in DERIVED:
            for name in names:
                if not (R / name).is_file() or (R / name).read_bytes() != (Path(tmp) / name).read_bytes():
                    fail(name, 'stale derived file', f'python {command}')
    except (OSError, ValueError, KeyError) as exc:
        fail('derived files', f'rebuild failed: {exc}', 'python checker/derived.py')

if failures:
    print('\n'.join(failures))
    raise SystemExit(1)
print(json.dumps({'drawings': len(a), 'native_fields_same': sum(x['status'] == 'same' for x in r if x['file'].startswith('native/')), 'cross_fields': sum(x['file'].startswith('cross/') for x in r), 'audit_errors': sum(x['errors'] for x in a), 'audit_fixes': sum(x['fixes'] for x in a), 'digest_cases': len(e), 'artifact_checks': 'pass'}))
