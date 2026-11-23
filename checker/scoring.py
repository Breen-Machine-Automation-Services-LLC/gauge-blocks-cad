"""Score identity and observation metadata shared by result producers."""
from pathlib import Path
import hashlib
import json
import ezdxf

ENGINES = {'ezdxf': 'ezdxf', 'oda': 'oda-teigha', 'bricscad': 'oda-teigha', 'cadcraft': 'cadcraft'}

def stamp(root, intent_id):
    from programs.adapters import VERSIONS
    intent = json.loads((root / 'intent' / (intent_id + '.json')).read_text())
    fields = [{key: value for key, value in field.items() if key != 'reference'}
              for field in intent.get('expected', [])]
    scoring_intent = json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return {'checker': hashlib.sha256(Path(__file__).with_name('core.py').read_bytes()).hexdigest(),
            'ezdxf': ezdxf.__version__, 'versions': dict(VERSIONS),
            'intent': hashlib.sha256(scoring_intent).hexdigest()}

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

def native_input(root, intent_id, program='ezdxf', script=None, lsp=None, versions=None):
    """Return the input digest and supported version/encoding cases."""
    from programs.adapters import VERSIONS
    ip = root / 'intent' / (intent_id + '.json')
    if program == 'bricscad':
        sources = lsp.read_bytes() + script.read_bytes()
    elif intent_id.startswith('feature_'):
        sources = b''.join(p.read_bytes() for p in sorted((root / 'generators').glob('*.py')))
    else:
        sources = (root / 'generators/background.py').read_bytes()
    cases = [(v, e) for v in (VERSIONS if versions is None else versions)
             if not (v == 'R12' and intent_id == 'background_plots')
             for e in (['ASCII'] if v == 'R12' else ['ASCII', 'binary'])]
    return hashlib.sha256(ip.read_bytes() + sources).hexdigest(), cases

def reading_current(rows, reader, converter):
    return bool(rows) and all(r.get('reader') == reader and r.get('converter') == converter for r in rows)
