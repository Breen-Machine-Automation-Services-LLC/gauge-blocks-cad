from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from checker.scoring import stamp
R=Path(__file__).resolve().parents[1]
a=json.loads((R/'results/audits.json').read_text());r=json.loads((R/'results/checks.json').read_text());e=json.loads((R/'results/digest_evidence.json').read_text())
assert len(a)==77 and all(x['errors']==0 for x in a)
assert all(x['status']=='same' for x in r if x['file'].startswith('native/'))
assert len(e)==13 and all(x['equal'] and x['one_field_changes_digest'] for x in e)
for p in (R/'native').rglob('*.dxf'):
 assert bytes([47,104,111,109,101,47]) not in p.read_bytes() and b'/tmp/' not in p.read_bytes(),p
assert '\u2014' not in (R/'README.md').read_text()
stale=[];stamps={}
for path in sorted((R/'results').glob('*checks.json')):
 rows=json.loads(path.read_text())
 if not isinstance(rows,list):continue
 count=0
 for row in rows:
  try:
   iid=row['intent_id']
   if iid not in stamps:stamps[iid]=stamp(R,iid)
   valid=row.get('scored_with')==stamps[iid] and all(k in row for k in ('writer_engine','reader_engine','shared_engine'))
  except (OSError,KeyError): valid=False
  count+=not valid
 if count:stale.append(f'{path.name}: {count} stale rows')
if stale:
 print('\n'.join(stale))
 raise SystemExit('Stale score stamps; re-score existing drawings')
print(json.dumps({'drawings':len(a),'native_fields_same':sum(x['status']=='same' for x in r if x['file'].startswith('native/')),'cross_fields':sum(x['file'].startswith('cross/') for x in r),'audit_errors':sum(x['errors'] for x in a),'audit_fixes':sum(x['fixes'] for x in a),'digest_cases':len(e),'artifact_checks':'pass'}))
