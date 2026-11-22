from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
a=json.loads((R/'results/audits.json').read_text());r=json.loads((R/'results/checks.json').read_text());e=json.loads((R/'results/digest_evidence.json').read_text())
assert len(a)==77 and all(x['errors']==0 for x in a)
assert all(x['status']=='same' for x in r if x['file'].startswith('native/'))
assert len(e)==13 and all(x['equal'] and x['one_field_changes_digest'] for x in e)
for p in (R/'native').rglob('*.dxf'):
 assert bytes([47,104,111,109,101,47]) not in p.read_bytes() and b'/tmp/' not in p.read_bytes(),p
assert '\u2014' not in (R/'README.md').read_text()
print(json.dumps({'drawings':len(a),'native_fields_same':sum(x['status']=='same' for x in r if x['file'].startswith('native/')),'cross_fields':sum(x['file'].startswith('cross/') for x in r),'audit_errors':sum(x['errors'] for x in a),'audit_fixes':sum(x['fixes'] for x in a),'digest_cases':len(e),'artifact_checks':'pass'}))
