"""Recheck alignment fields from existing DXFs and saved DWG measurements."""
# Refresh affected fields directly from existing DXF files, retaining reader attribution.
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
d=json.loads((R/'intent/feature_a_text.json').read_text())
new=[f for f in d['expected'] if f['id'].endswith('.alignment_rotation_error') or '_fit.width' in f['id']]
import sys
sys.path.insert(0,str(R))
import ezdxf
from checker.core import compare,equal
changes=[]
for p in (R/'results').glob('*checks.json'):
 rows=json.loads(p.read_text());modified=False;by={}
 if not isinstance(rows,list):continue
 for r in rows:
  if r.get('intent_id')==d['intent_id']:by.setdefault(r['file'],[]).append(r)
 for path,rs in by.items():
  if not (R/path).is_file():continue
  if path.endswith('.dxf'):
   doc=ezdxf.readfile(R/path)
   for provenance in {(r.get('reader'),r.get('converter'),r.get('self_read')) for r in rs if not r.get('converter')}:
    measured=compare(doc,d,provenance[0]);target={r['field']:r for r in rs if (r.get('reader'),r.get('converter'),r.get('self_read'))==provenance}
    for r in measured:
     if r['field'] not in {x['id'] for x in new} and not '_aligned.height' in r['field']:continue
     old=target.get(r['field']);r.update(file=path,converter=provenance[1],self_read=provenance[2])
     if old:
      if old['status']!=r['status']:changes.append(dict(file=path,field=r['field'],before=old['status'],after=r['status']))
      old.update(r)
     else:rows.append(r)
     modified=True
  else:
   # Existing measured DWG rows preserve actual values and converter provenance.
   for r in rs:
    f=next((f for f in d['expected'] if f['id']==r.get('field') and '_aligned.height' in f['id']),None)
    if f and r['status']!='absent':
     old=r['status'];r['tolerance']=f['tolerance'];r['status']='same' if equal(r['actual'],f['value'],f['tolerance']) else 'differs'
     if old!=r['status']:changes.append(dict(file=path,field=r['field'],before=old,after=r['status']))
     modified=True
 if modified:p.write_text(json.dumps(rows,indent=2)+'\n')
(R/'results/alignment_recheck.json').write_text(json.dumps(changes,indent=2)+'\n');print('Changed field rows',len(changes))
