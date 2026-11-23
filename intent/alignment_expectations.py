"""Independent Aligned and Fit expectations, based on DXF group meanings."""
from pathlib import Path
from references import author_references
import json,math,copy
R=Path(__file__).resolve().parents[1];p=R/'intent/feature_a_text.json';d=json.loads(p.read_text());new=[]
url='https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-62E5383D-8A14-47B4-BFC4-35824CAE8363.htm'
for f in d['expected']:
 if '_aligned.height' in f['id']:
  f['tolerance']=1.0
  f['reference']['basis_type']='compatibility_policy';f['reference']['basis']='Groups 10 and 11 define the two-point span, 72=3 selects Aligned, 40 stores height, 41 width scale, and 50 rotation. Font measurement may recompute height. Dataset policy accepts height 2.5 +/- 1.0 drawing units (40 percent); this tolerance is a dataset choice, not a Reference limit. Rotation must agree with the alignment-point vector within 0.000001 degrees.'
  f['reference']['url']=url
 if '_aligned.height' in f['id'] or '_fit.height' in f['id']:
  name=f['selector']['name'];mode='aligned' if '_aligned' in name else 'fit'
  g=copy.deepcopy(f);g['id']=name+'.alignment_rotation_error';g['selector']['attr']='alignment_rotation_error';g['value']=0;g['tolerance']=1e-6;g['reference']['basis_type']='compatibility_policy';g['reference']['basis']='Groups 10 and 11 define the baseline direction for group 72 Aligned (3) or Fit (5). Group 50 must agree within 0.000001 degrees, modulo 360.';g['reference']['url']=url
  new.append(g);d['feature_fields'][name]=list(dict.fromkeys(d['feature_fields'][name]+[g['id']]))
  if mode=='fit':
   g=copy.deepcopy(g);g['id']=name+'.width';g['selector']['attr']='width';g['value']=1.0;g['tolerance']=0.4;g['reference']['basis_type']='compatibility_policy';g['reference']['basis']='Group 41 is adjusted for Fit (72=5) to span groups 10 and 11 at group-40 height. Different font metrics may recompute width. Dataset policy accepts 1.0 +/- 0.4 (40 percent), not a Reference-prescribed limit; points, height, and rotation remain separately checked.';new.append(g);d['feature_fields'][name]=list(dict.fromkeys(d['feature_fields'][name]+[g['id']]))
new=[f for f in new if f['id'] not in {x['id'] for x in d['expected']}];d['expected']+=new;p.write_text(json.dumps(author_references(d),indent=2)+'\n')

for f in d['expected']:
 if '_fit.width' in f['id']:
  f['tolerance']=1e-8;f['recomputed_width_relative_tolerance']=0.4
  f['reference']['basis_type']='compatibility_policy';f['reference']['basis']='Group 41 may be recomputed for Fit (72=5) to span groups 10 and 11 at group-40 height. Accept the authored width factor or the span divided by the unscaled text width measured with the reader font, within 40 percent for font-metric differences. Rotation must still agree with the alignment points within 0.000001 degrees. The 40 percent tolerance is dataset policy, not a Reference limit.'
p=R/'intent/feature_a_text.json';p.write_text(json.dumps(author_references(d),indent=2)+'\n')
