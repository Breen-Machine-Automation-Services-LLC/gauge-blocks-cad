"""Score identity and observation metadata shared by result producers."""
from pathlib import Path
import hashlib
import json
import ezdxf
from checker.core import applicable_fields

ENGINES = {'ezdxf': 'ezdxf', 'oda': 'oda-teigha', 'bricscad': 'oda-teigha', 'cadcraft': 'cadcraft'}

def scoring_intent(intent):
    """Serialize the expected fields that affect scoring and drawing inputs."""
    fields = [{key: value for key, value in field.items() if key != 'reference'}
              for field in intent.get('expected', [])]
    return json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def stamp(root, intent_id):
    from programs.adapters import VERSIONS
    intent = json.loads((root / 'intent' / (intent_id + '.json')).read_text())
    return {'checker': hashlib.sha256(Path(__file__).with_name('core.py').read_bytes()).hexdigest(),
            'ezdxf': ezdxf.__version__, 'versions': dict(VERSIONS),
            'intent': hashlib.sha256(scoring_intent(intent)).hexdigest()}

def annotate(rows, root, intent_id, writer, reader):
    score = stamp(root, intent_id)
    for row in rows:
        row.update(scored_with=score, writer_engine=ENGINES[writer], reader_engine=ENGINES[reader],
                   shared_engine=ENGINES[writer] == ENGINES[reader])
    return rows

def current(rows, root, intent_id, input_digest=None, build=None, score=None):
    """Apply the same currency rule to completed refusals and scored rows."""
    if not rows:
        return False
    if any(row.get('status') == 'refused' for row in rows):
        return refusal_current(rows, input_digest, build) and input_digest is not None and build is not None
    score = stamp(root, intent_id) if score is None else score
    return all(row.get('scored_with') == score and
               row.get('writer_engine') in ENGINES.values() and
               row.get('reader_engine') in ENGINES.values() and
               row.get('shared_engine') is (row['writer_engine'] == row['reader_engine'])
               for row in rows)

def load_rows(path):
    return json.loads(path.read_text()) if path.exists() else []

# Modules that report on drawings rather than draw them; run_*.py are runners.
ORCHESTRATION_MODULES = {
    'summarize_cross.py': 'Summarizes measured cross-program results.',
    'write_coverage.py': 'Builds coverage reports from intents and measurements.',
}

def native_input(root, intent_id, program='ezdxf', script=None, lsp=None, versions=None):
    """Return the input digest and supported version/encoding cases."""
    from programs.adapters import VERSIONS
    ip = root / 'intent' / (intent_id + '.json')
    intent = scoring_intent(json.loads(ip.read_text()))
    if program == 'bricscad':
        sources = lsp.read_bytes()
    else:
        sources = b''.join(p.read_bytes() for p in sorted((root / 'generators').glob('*.py'))
                           if not p.name.startswith('run_') and p.name not in ORCHESTRATION_MODULES)
    cases = [(v, e) for v in (VERSIONS if versions is None else versions)
             if not (v == 'R12' and intent_id == 'background_plots')
             for e in (['ASCII'] if v == 'R12' else ['ASCII', 'binary'])]
    return hashlib.sha256(intent + sources).hexdigest(), cases

def reading_current(rows, reader, converter):
    return bool(rows) and all(r.get('reader') == reader and r.get('converter') == converter for r in rows)


def empty_plan():
    return {key: [] for key in ('resave', 'rescore', 'carried', 'gaps')}


def score_records(path):
    return path.with_suffix('.scores.json')


def file_current(rows, root, intent_id, path, rel, current_fn=current,
                 reader=None, converter=None, identity=None, reading_fn=reading_current):
    """Empty comparisons retain score identity separately from field results."""
    if current_fn(rows, root, intent_id):
        return ((reader is None or reading_fn(rows, reader, converter))
                and (identity is None or all(r.get('read_input_digest') == identity for r in rows)))
    if rows:
        return False
    records = score_records(path)
    saved = json.loads(records.read_text()).get(rel, {}) if records.exists() else {}
    return (saved.get('scored_with') == stamp(root, intent_id)
            and (reader is None or (saved.get('reader') == reader and saved.get('converter') == converter))
            and (identity is None or saved.get('read_input_digest') == identity))


def record_score(rows, root, intent_id, path, rel, reader=None, converter=None, identity=None):
    """Persist completion of a comparison that has no applicable fields."""
    records = score_records(path)
    saved = json.loads(records.read_text()) if records.exists() else {}
    if rows:
        if rel not in saved:
            return
        del saved[rel]
    else:
        saved[rel] = dict(scored_with=stamp(root, intent_id), reader=reader,
                          converter=converter, read_input_digest=identity)
    records.parent.mkdir(parents=True, exist_ok=True)
    records.write_text(json.dumps(saved, indent=2) + '\n')


def native_plan(jobs, root, force, build, result, current_fn):
    result_plan = empty_plan()
    previous = load_rows(result)
    for iid, topic, version, enc, inp, dest in jobs:
        sc = dest.with_suffix('.dxf.provenance.json')
        old = json.loads(sc.read_text()) if sc.exists() else {}
        rel = dest.relative_to(root).as_posix()
        rows = [r for r in previous if r['file'] == rel]
        if force or not dest.exists() or old.get('build') != build or old.get('made_by', {}).get('input_digest') != inp:
            kind = 'resave'
        elif not file_current(rows, root, iid, result, rel, current_fn):
            kind = 'rescore'
        else:
            kind = 'carried'
        result_plan[kind].append(rel)
    return result_plan


def refusal_current(rows, input_digest, build):
    """A completed refusal remains valid for the same drawing input and writer."""
    return bool(rows) and all(r.get('status') == 'refused'
                             and r.get('attempt_input_digest') == input_digest
                             and r.get('attempt_build') == build for r in rows)


def stamp_refusal(rows, input_digest, build):
    for row in rows:
        if row.get('status') == 'refused':
            row.update(attempt_input_digest=input_digest, attempt_build=build)


def writable(root, program, fmt, version, encoding):
    """The declared output tuples define the re-saver's capability gaps."""
    path = root / 'programs/capabilities.json'
    if not path.exists():
        # Alternate output roots share the runner's declarations unless they supply their own.
        path = Path(__file__).resolve().parents[1] / 'programs/capabilities.json'
    caps = json.loads(path.read_text())[program]
    return [fmt, version, encoding] in caps['outputs']
