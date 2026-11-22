"""Associate semantic features with their independently authored expected fields."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
for p in (R/'intent').glob('*.json'):
 if p.name.endswith('.schema.json'):continue
 i=json.loads(p.read_text())
 if 'expected' not in i:continue
 groups={feature:[] for feature in i['features'] if feature!='file identity'}
 topic=i['intent_id'].removeprefix('background_')
 for f in i['expected']:
  key=f['id'];features=[]
  if i['intent_id'].startswith('feature_'):features=['F169_scale_list_marker' if f['selector'].get('dictionary')=='ACAD_SCALELIST' else 'F182_proxy_object_marker' if f['selector']['name']=='SYNTH_OBJ_REF' else f['selector']['name']]
  elif key=='identity':
   continue
  elif topic=='blocks':features=[i['features'][0] if key.startswith('ZEV_UNUSED.') else i['features'][1]]
  elif topic=='layers':
   if key=='vp.freeze':features=['paper viewport freeze']
   elif key=='vp.color':features=['paper viewport color override']
   elif key.startswith('layer_usage_'):features=['unused layers' if int(key[-3:])>=3 else 'three populated layers']
   else:features=['100 mixed-state layers']
  elif topic=='styles':
   if key.startswith('complex.'):features=['unused text-bearing linetype']
   elif key.startswith('ZEV_DIM.'):features=['unused dimension style']
   elif key.startswith('ZEV_TEXT.') or key=='style_usage':features=['unused text style']
   else:features=['unused linetype']
  elif topic=='plots':features=['empty layout' if key=='empty' else 'plot-style table reference' if key=='current_style_sheet' else 'named page setup']
  elif topic=='metadata':features=['registered application' if key.startswith('ZEV_APP.') else 'extended data' if key=='xdata' else 'extension dictionary with XRECORD' if key=='xrecord' else 'DICTIONARYVAR']
  elif topic=='named':features=['scale list' if key.startswith('scale.') else 'named view' if key.startswith('ZEV_VIEW.') else 'named UCS' if key.startswith('ZEV_UCS.') else 'group']
  for feature in features:groups.setdefault(feature,[]).append(key)
 assert all(groups.values()),(p,groups)
 i['features']=list(groups);i['feature_fields']=groups;p.write_text(json.dumps(i,indent=2)+'\n')
