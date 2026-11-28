"""Contract checks for statuses, map provenance, and the complete feature matrix."""
from pathlib import Path
from collections import Counter
import json,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
sys.dont_write_bytecode = True
from map.check_links import page_data
from jsonschema import Draft202012Validator
schema=json.loads((R/'intent/intent.schema.json').read_text());v=Draft202012Validator(schema)
intents=[json.loads(p.read_text()) for p in (R/'intent').glob('*.json') if not p.name.endswith('.schema.json')]
counts=Counter(i.get('status','derived') for i in intents);assert set(counts)=={'wanted','planned','derived','blocked'}
for status in ['wanted','planned','blocked']:
 v.validate(dict(intent_id='test_request',title='Test request',description='Invented request',status=status))
assert not v.is_valid(dict(intent_id='bad',title='Bad',description='Bad',status='unknown'))
checks=json.loads((R/'results/features_checks.json').read_text());audits=json.loads((R/'results/features_audits.json').read_text())
assert len(audits)==12*13,len(audits)
assert all(r['status']=='same' for r in checks if not r['field'].endswith('.alignment_rotation_error'))
rotation_changes=[r for r in checks if r['status']=='differs']
assert not rotation_changes
assert len([r for r in checks if r['field'].endswith('.alignment_rotation_error')])==76
assert all(r['errors']==r['fixes']==0 for r in audits)
page=(R/'map/index.html').read_text()
data=page_data(page)
assert {t['id'] for t in data['topics']}=={i['intent_id'] for i in intents}
blocks=next(t for t in data['topics'] if t['id']=='background_blocks')
assert len(blocks['features'])==2
assert all(f['name']!='file identity' for t in data['topics'] for f in t['features'])
assert any(c['runs'] for f in blocks['features'] for c in f['cells'])
for status in ['partial','covered']:
 assert not v.is_valid(dict(intent_id='bad',title='Bad',description='Bad',status=status))
for name in ['README.md','CONTRIBUTING.md','OPEN-ITEMS.md','COVERAGE.md','intent/SCHEMA.md']:
 assert '\u2014' not in (R/name).read_text(),name
required=['future_dynamic_blocks','future_aec_proxy','future_acceptance','future_surface','future_m_ole','future_representations','future_codepages','future_unicode','future_proof_sheet','future_own_drawings']
assert set(required)<=set(i['intent_id'] for i in intents)
assert all(key in (R/'OPEN-ITEMS.md').read_text() for key in ['2007','Aligned','100 differing','53 missing','AutoCAD'])
assert 'map/index.html' in (R/'README.md').read_text()
evidence=dict(status_counts=dict(counts),native_feature_files=len(audits),fields_same=sum(r['status']=='same' for r in checks),documented_rotation_changes=len(rotation_changes),audit_errors=0,audit_fixes=0,all_intents_in_map=True)
print(json.dumps(evidence))
