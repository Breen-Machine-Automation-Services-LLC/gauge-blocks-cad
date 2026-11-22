"""Check that every new cross sidecar points at a source whose content digest it records, and that every output has result rows.
Run from the repository root. Exits nonzero on a mismatch.
"""
from pathlib import Path
import json, sys
R = Path(__file__).resolve().parents[1]
SRC = {p['writer']+'__'+p['resaver']: p['sources'] for p in json.loads((R/'programs/pairs.json').read_text())}
rows = {}
for p in (R / 'results').glob('cross_*checks.json'):
    for r in json.loads(p.read_text()):
        rows.setdefault(r['file'], []).append(r)
bad = []; n = 0
for pair, folder in SRC.items():
    digests = {json.loads(p.read_text())['content_digest'] for p in (R / folder).glob('*.json')}
    for sc in sorted((R / 'cross' / pair).glob('*.json')):
        m = json.loads(sc.read_text()); n += 1; rel = Path(str(sc).removesuffix('.provenance.json')).relative_to(R).as_posix()
        if m['made_by']['input_digest'] not in digests:
            bad.append(('stale source digest', rel))
        intent = json.loads((R / 'intent' / (m['intent_id'] + '.json')).read_text())
        version = {'R12': 'AC1009', '2000': 'AC1015', '2004': 'AC1018', '2007': 'AC1021', '2010': 'AC1024', '2013': 'AC1027', '2018': 'AC1032'}[m['version']]
        applicable = any(version in f['versions'] for f in intent.get('expected', []))
        if rel not in rows and applicable:
            bad.append(('no result rows', rel))
        if m['format'] == 'DWG' and 'digest_reader' not in m:
            bad.append(('DWG without digest_reader', rel))
print(f'{n} cross sidecars checked; {len(bad)} problems')
for b in bad[:20]:
    print(b)
sys.exit(1 if bad else 0)
