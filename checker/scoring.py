"""Score identity and observation metadata shared by result producers."""
from pathlib import Path
import hashlib
import json
import ezdxf

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

def current(rows, root, intent_id):
    score = stamp(root, intent_id)
    return bool(rows) and all(row.get('scored_with') == score for row in rows)

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
