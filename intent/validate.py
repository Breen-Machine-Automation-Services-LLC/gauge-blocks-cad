from pathlib import Path
import json
from jsonschema import Draft202012Validator,FormatChecker
R=Path(__file__).resolve().parents[1]
def main():
 intents={};count=0
 for kind,paths in [('intent',sorted(p for p in (R/'intent').glob('*.json') if not p.name.endswith('.schema.json'))),('provenance',sorted(p for folder in ['native','cross'] for p in (R/folder).rglob('*.json')))]:
  validator=Draft202012Validator(json.loads((R/'intent'/f'{kind}.schema.json').read_text()),format_checker=FormatChecker())
  for p in paths:
   data=json.loads(p.read_text());validator.validate(data);count+=1
   if kind=='intent':
    assert len({x['id'] for x in data.get('expected',[])})==len(data.get('expected',[]));intents[data['intent_id']]=data
    if 'feature_fields' in data:
     assert set(data['feature_fields'])==set(data['features'])
     assert {key for ids in data['feature_fields'].values() for key in ids}=={f['id'] for f in data['expected'] if f['selector']['kind']!='identity'}
   else:
    assert 'status' not in intents[data['intent_id']], 'An intent with drawings must omit status';assert data['intent_id'] in intents;assert data['representation_id']==intents[data['intent_id']]['representation_id'];assert Path(str(p).removesuffix('.provenance.json')).is_file()
 for folder in ['native','cross']:
  for p in (R/folder).rglob('*'):
   if p.suffix.lower() in ['.dxf','.dwg']:assert p.with_suffix(p.suffix+'.provenance.json').is_file(),p
 print(f'Validated {count} intents and sidecars; all drawings have sidecars.')
if __name__=='__main__':main()
