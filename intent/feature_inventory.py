"""Inventory feature layer declarations from source generators, never saved drawings."""
from pathlib import Path
from references import author_references
import ast,json,re
R=Path(__file__).resolve().parents[1]
for filename,topics in [('masters_abcd.py',{'master_a':'a_text','master_b':'b_geometry','master_c':'c_layouts','master_d':'d_dimensions'}),('masters_ghijn.py',{'master_g':'g_blocks','master_h':'h_attributes','master_i':'i_dictionaries','master_j':'j_raster','master_n':'n_misc'})]:
 tree=ast.parse((R/'generators'/filename).read_text())
 for fn in tree.body:
  if not isinstance(fn,ast.FunctionDef) or fn.name not in topics:continue
  topic=topics[fn.name];p=R/'intent'/('feature_'+topic+'.json');i=json.loads(p.read_text())
  interpolated={id(x) for f in ast.walk(fn) if isinstance(f,ast.JoinedStr) for x in ast.walk(f)}
  names={n.value for n in ast.walk(fn) if id(n) not in interpolated and isinstance(n,ast.Constant) and isinstance(n.value,str) and re.fullmatch(r'F\d+_[a-z][A-Za-z0-9_]*[A-Za-z0-9]' ,n.value)}
  names|=set(i['features'])
  for name in sorted(names):
   key=name+'.layer'
   if not any(f['id']==key for f in i['expected']):i['expected'].append(dict(id=key,value=name,selector=dict(kind='table',table='layers',name=name,attr='name'),reference=dict(basis_type='synthetic',section='LAYER code 2; common entity code 8',source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2024/ENU/',basis='DXF Reference; feature layer declared in source generator'),tolerance=0,versions=['AC1009','AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']))
  i['features']=sorted(names);p.write_text(json.dumps(author_references(i),indent=2)+'\n')
p=R/'intent/feature_l_proxy.json'
if p.exists():
 i=json.loads(p.read_text());i['features']=['F180_proxy_entity','F181_proxy_entity_b','F182_proxy_object_marker'];i['expected']=[]
 for name in i['features']:
  i['expected'].append(dict(id=name+'.layer',value=name,selector=dict(kind='table',table='layers',name=name,attr='name'),reference=dict(basis_type='synthetic',section='LAYER code 2; CLASSES',source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2024/ENU/',basis='DXF Reference; invented custom classes'),tolerance=0,versions=['AC1009','AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']))
 p.write_text(json.dumps(author_references(i),indent=2)+'\n')
