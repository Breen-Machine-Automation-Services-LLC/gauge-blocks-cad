import hashlib,json,math,re
from pathlib import Path
import ezdxf.math
from ezdxf.lldxf.tagwriter import TagCollector
from ezdxf.lldxf.const import DXFError
class CheckerLimit(Exception):
 """The selector requires unsupported or ambiguous checker behavior."""

VOLATILE={'$TDCREATE','$TDUPDATE','$TDUCREATE','$TDUUPDATE','$TDINDWG','$TDUSRTIMER','$VERSIONGUID','$FINGERPRINTGUID','$HANDSEED'}
ACIS_TYPES={'REGION','3DSOLID','BODY'}
# ACIS data (SAT text or SAB binary) starts with a header that records the build time of the body, e.g. Sun Nov 22 13:24:09 2026.
ACIS_DATE=re.compile(rb'(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ 0-9][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}')
def acis_canonical(tags):
 # Join the data tags (codes 1, 3 and 310) and blank the build time; other tags of the entity stay as they are.
 data=b''.join(t.value if isinstance(t.value,bytes) else str(t.value).encode('utf-8','replace') for t in tags if t.code in (1,3,310))
 rest=[(t.code,str(t.value)) for t in tags if t.code not in (1,3,310) and not (t.code==2 and re.fullmatch(r'\{[0-9a-fA-F-]{36}\}',str(t.value)))]  # code 2 is a per-save unique id
 return rest+[('acis',hashlib.sha256(ACIS_DATE.sub(b'<time>',data)).hexdigest())]
def digest(d):
 # Preserve handles: references remain meaningful, without masking semantic changes.
 headers=[(k,str(v)) for k,v in ((k,d.header[k]) for k in d.header.varnames()) if k not in VOLATILE]
 metadata=d.rootdict.get('EZDXF_META')
 volatile_handles={e.dxf.handle for k,e in metadata.items() if k in {'CREATED_BY_EZDXF','WRITTEN_BY_EZDXF'}} if metadata else set()
 entities=[]
 for e in d.entitydb.values():
  if not e.is_alive:continue
  tags=TagCollector.dxftags(e,dxfversion='AC1032')
  dwgprops=e.dxftype()=='XRECORD' and any(t.code==1 and t.value=='DWGPROPS COOKIE' for t in tags)
  canonical=[];app=None;metadata_value=False
  for t in tags:
   if dwgprops and t.code in (41,42):continue
   if t.code==1001:app=t.value
   if t.code==1 and e.dxf.handle in volatile_handles:continue
   if t.code==1000 and app=='EZDXF':
    if metadata_value:
     metadata_value=False;continue
    if t.value in {'CREATED_BY_EZDXF','WRITTEN_BY_EZDXF'}:metadata_value=True
   canonical.append((t.code,str(t.value)))
  if e.dxftype() in ACIS_TYPES:canonical=acis_canonical(tags)
  entities.append(canonical)
 return hashlib.sha256(json.dumps([sorted(headers),entities],sort_keys=True).encode()).hexdigest()
# Names use ASCII case equivalence for the authored symbol alphabet. Other text stays literal.
def name_key(value):
 return value.translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')) if isinstance(value,str) else value
def same_name(a,b):return name_key(a)==name_key(b)
def symbol_item(table,name):
 return next(e for e in table if same_name(e.name if hasattr(e,'block') else e.dxf.name,name))
def dictionary_item(dictionary,name):
 keys=[key for key in dictionary.keys() if same_name(key,name)]
 if len(keys)>1:raise CheckerLimit('Ambiguous dictionary key: '+name)
 if not keys:raise KeyError(name)
 return dictionary[keys[0]]
def named_layout(d,name):
 entry=dictionary_item(dictionary_item(d.rootdict,'ACAD_LAYOUT'),name)
 return d.layouts.get(entry.dxf.name)
def app_data(e,name):
 keys=[key for key in e.xdata.data if same_name(key,name)] if e.xdata else []
 if len(keys)>1:raise CheckerLimit('Ambiguous application: '+name)
 if not keys:raise KeyError('Missing application: '+name)
 return e.get_xdata(keys[0])
SYMBOL_ATTRS={'layer','linetype','style','dimstyle','ucs','view','viewport','appid'}
SYMBOL_TABLES={'layers','linetypes','styles','dimstyles','views','ucs','viewports','appids','blocks'}
def symbol_attr(attr,table):
 return attr in SYMBOL_ATTRS or (attr=='name' and table in SYMBOL_TABLES|{'INSERT','DIMENSION'})
def feature_entity(d,s):
 return next(e for e in d.entitydb.values() if e.is_alive and e.dxftype()==s['table'] and same_name(layer_of(e),s['name']))
def symbol_query(space,query):
 # Select entity types publicly and apply the shared symbol-name rule ourselves.
 if re.fullmatch(r'\s*(?:[A-Z0-9_]+\s*)+\s*',query):return list(space.query(query))
 match=re.fullmatch(r"\s*(\*|[A-Z0-9_]+)\s*\[\s*(layer|name)\s*==\s*(['\"])(.*?)\3\s*\]\s*",query)
 if not match:raise CheckerLimit('Unsupported query_count query: '+query)
 typ,attr,_,value=match.groups()
 if attr=='name' and typ!='INSERT':raise CheckerLimit('Unsupported query_count name operand: '+query)
 return [e for e in space.query(typ) if same_name(getattr(e.dxf,attr),value)]

def proxy_payload(e):
 tags=TagCollector.dxftags(e);subclass=None;envelope=None;values=[]
 for t in tags:
  if t.code==100:subclass=t.value
  if t.code in (90,40):
   if e.dxftype() in {'ACAD_PROXY_OBJECT','ACAD_PROXY_ENTITY'} and subclass in {'AcDbProxyObject','AcDbProxyEntity'} and envelope is None and t.code==90:
    if t.value!={'ACAD_PROXY_OBJECT':499,'ACAD_PROXY_ENTITY':498}[e.dxftype()]:raise KeyError('Invalid proxy class-ID envelope for '+e.dxftype())
    envelope=t.value;continue
   values.append([t.code,t.value])
 if e.dxftype() in {'ACAD_PROXY_OBJECT','ACAD_PROXY_ENTITY'} and envelope is None:raise KeyError('Missing proxy class-ID envelope')
 return values
def layer_of(e):
 # Exported tags first (as before); ezdxf exports no tags for ACIS entities before R2013, so fall back to the loaded attribute.
 value=next((t.value for t in TagCollector.dxftags(e) if t.code==8),None)
 if value is None and e.dxf.hasattr('layer'):value=e.dxf.layer
 return value
def table_tags(e):
 tags=[(t.code,t.value) for t in TagCollector.dxftags(e)]
 return tags[next(i for i,t in enumerate(tags) if t==(100,'AcDbTable')):]
def redraw_layout(d, name):
 e=next(e for e in d.entitydb.values() if e.is_alive and same_name(layer_of(e),name) and hasattr(e,'get_layout'))
 layout=e.get_layout()
 if layout is None:raise CheckerLimit('Unsupported draw-order layout: '+name)
 return layout

def effective_redraw_order(layout):
 # DXF Reference, OBJECTS / SORTENTSTABLE: 331 entity handles, 5 sort handles.
 # https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-462F4378-F850-4E89-90F2-3C1880F55779.htm
 # Unlisted entities retain their own handles as sort keys (see DRAW_ORDER.md).
 table=dict(layout.get_redraw_order())
 return [layer_of(e) for e in sorted(layout, key=lambda e:int(table.get(e.dxf.handle,e.dxf.handle),16))]

def literal_redraw_order(layout):
 return [dict(entity_handle=h,sort_handle=k) for h,k in layout.get_redraw_order()]

def applicable_fields(intent, version, encoding=None):
 return [f for f in intent['expected'] if version in f['versions']
         and (encoding is None or encoding in f.get('encodings', ['ASCII','binary']))]

def encoding_intent(intent, encoding):
 # Preserve version selection by compare and apply the shared rule to encoding restrictions.
 if not any('encodings' in f for f in intent['expected']):return intent
 fields=[f for f in intent['expected'] if applicable_fields({'expected':[f]}, f['versions'][0], encoding)]
 return dict(intent,expected=fields)

def decode_sat_records(tags):
 records=[]
 for tag in tags:
  if tag.code==1:records.append(tag.value)
  elif tag.code==3 and records:records[-1]+=tag.value
 for record in records:
  decoded=[];i=0
  while i<len(record):
   c=ord(record[i]);i+=1
   decoded.append({32:' ',64:'_',95:'@'}.get(c,chr(159-c) if 65<=c<=94 else chr(c^95)))
   if c==94 and i<len(record) and record[i]==' ':i+=1
  yield ''.join(decoded)

def raw_sat_tags(entity):
 # Loaded SAT has already passed through the library decoder; read original tags by handle.
 from ezdxf.lldxf.tagger import binary_tags_loader, ascii_tags_loader
 from io import StringIO
 path=entity.doc.filename
 if not path:return []
 data=Path(path).read_bytes()
 tags=binary_tags_loader(data) if data.startswith(b'AutoCAD Binary DXF') else ascii_tags_loader(StringIO(data.decode(entity.doc.encoding,errors='surrogateescape')))
 selected=[];handle=None
 for tag in tags:
  if tag.code==0:
   if handle==entity.dxf.handle:return selected
   selected=[];handle=None
  if tag.code==5:handle=tag.value
  selected.append(tag)
 if handle==entity.dxf.handle:return selected
 return []

def raw_sat(entity):
 tags=raw_sat_tags(entity)
 return list(decode_sat_records(tags)) if tags else entity.sat

def unpadded_binary_sat(entity):
 path=entity.doc.filename
 if not path:return False
 with Path(path).open('rb') as stream:
  if not stream.read(22).startswith(b'AutoCAD Binary DXF'):return False
 # Join continuation tags before checking the encrypted A's following byte.
 records=[]
 for tag in raw_sat_tags(entity):
  if tag.code==1:records.append(tag.value)
  elif tag.code==3 and records:records[-1]+=tag.value
 return any(re.search(r'\^(?! )', record) for record in records)

def acis_value(entity, attr, public=False):
 from ezdxf.acis import api as acis
 if public:bodies=acis.load_dxf(entity)
 else:
  data=entity.sab if entity.has_binary_data else raw_sat(entity)
  if not data:raise KeyError('Missing ACIS data')
  bodies=acis.load(data)
 if not bodies:raise KeyError('ACIS entity has no decodable body')
 if attr=='acis_body_count':return len(bodies)
 box=ezdxf.math.BoundingBox([v for m in acis.mesh_from_body(bodies[0]) for v in m.vertices])
 return list(box.size)

def resolve_object(obj, *steps):
 """Resolve required query objects; missing intermediates are absent, not reader faults."""
 from ezdxf.entities.dxfns import DXFNamespace
 for step in steps:
  if obj is None:raise KeyError('Missing selected object')
  if callable(step):obj=step(obj)
  else:
   if isinstance(obj,DXFNamespace) and not obj.hasattr(step):raise KeyError('Missing selected attribute: '+step)
   obj=getattr(obj,step,None)
 if obj is None:raise KeyError('Missing selected object')
 return obj

def extract(d,s):
 kind=s['kind'];name=s.get('name');attr=s.get('attr')
 if kind=='feature_attr':
  e=feature_entity(d,s)
  if attr=='alignment_rotation_error':
   delta=resolve_object(e,'dxf','align_point')-e.dxf.insert
   angle=math.degrees(math.atan2(delta.y,delta.x))
   return (e.dxf.rotation-angle+180)%360-180
  if attr=='table_rows':return next(v for c,v in table_tags(e) if c==91)
  if attr=='table_columns':return next(v for c,v in table_tags(e) if c==92)
  if attr=='table_cell_text':return [v for c,v in table_tags(e) if c==1 and v!='']
  if attr in ('acis_body_count','acis_bbox_size'):
   return acis_value(e,attr)
  if attr=='redraw_order':
   return effective_redraw_order(redraw_layout(d,name))
  if attr=='image_size':return list(e.dxf.image_size)[:2]
  if attr=='loop_flags':return [p.path_type_flags for p in e.paths]
  if attr=='gradient_rotation':return resolve_object(e,'gradient','rotation')
  if attr=='fit_points':return [list(v) for v in e.fit_points]
  if attr=='extension_record':
   return [list(t) for t in resolve_object(e,'extension_dict',lambda x:dictionary_item(x,'G_XR'),'tags')]
  if attr=='block_circle_radius':
   radii=[x.dxf.radius for x in symbol_item(d.blocks,e.dxf.name) if x.dxftype()=='CIRCLE']
   if not radii:raise KeyError('Referenced block contains no CIRCLE')
   return radii
  if attr=='opaque_values':return [list(t) for t in TagCollector.dxftags(e) if t.code in [90,40]]
  if attr=='has_embedded_mtext':return e.has_embedded_mtext_entity
  if attr=='points':return [list(p) for p in e.get_points('xyseb')]
  if attr=='vertices':return [[v.dxf.location.x,v.dxf.location.y,v.dxf.start_width,v.dxf.end_width,v.dxf.bulge] for v in e.vertices]
  if attr in ['boundary_path','frozen_layers']:return list(getattr(e,attr))
  value=getattr(e.dxf,attr)
  return 0 if value is None and attr=='width' else value
 if kind=='table':
  value=getattr(symbol_item(getattr(d,s['table']),name).dxf,attr)
  # VIEW center is a 2D DCS point in the Reference.
  if s['table']=='views' and attr=='center':return list(value)[:2]
  return value
 if kind=='block':
  b=symbol_item(d.blocks,name)
  if attr=='inserts':return sum(same_name(e.dxf.name,name) for e in d.modelspace().query('INSERT'))
  return [e.dxf.get(attr) for e in b if e.dxftype()=='ATTDEF']
 if kind=='identity':return [t.value for t in app_data(d.modelspace().block_record.block,'ZEV_IDENTITY')]
 if kind=='query_count':return len(symbol_query(d.modelspace(),s['name']))
 if kind=='insert_attributes':return [[a.dxf.tag,a.dxf.text] for e in d.modelspace().query('INSERT') for a in e.attribs]
 if kind=='linetype_pattern':return [list(t) for t in symbol_item(d.linetypes,name).pattern_tags.tags if t.code in [72,73,40,49]]
 if kind=='complex_pattern':
  tags=symbol_item(d.linetypes,name).pattern_tags.tags
  if attr=='style':return d.entitydb[next(t.value for t in tags if t.code==340)].dxf.name
  code={'text':9,'scale':46,'rotation':50,'xoffset':44,'yoffset':45,'element_type':74}[attr]
  return next(t.value for t in tags if t.code==code and (code!=74 or t.value!=0))
 if kind=='layer_count':return len([x for x in d.layers if name_key(x.dxf.name).startswith(name_key('ZEV_'))])
 if kind=='layout_count':return len(named_layout(d,name))
 if kind=='viewport_freeze':return list(next(v for v in named_layout(d,'ZEV_PAPER').viewports() if v.dxf.id!=1).frozen_layers)
 if kind=='viewport_color':
  v=next(v for v in named_layout(d,'ZEV_PAPER').viewports() if v.dxf.id!=1)
  return symbol_item(d.layers,name).get_vp_overrides().get_color(v.dxf.handle)
 if kind=='object':
  e=dictionary_item(d.rootdict,name) if s['dictionary']=='ROOT' else dictionary_item(dictionary_item(d.rootdict,s['dictionary']),name)
  if attr=='tags':return [list(t) for t in e.tags]
  if attr=='opaque_values':return [list(t) for t in TagCollector.dxftags(e) if t.code in [90,40]]
  if attr=='acad_marker':return [list(t) for t in app_data(e,'ACAD')]
  if same_name(s['dictionary'],'ACAD_SCALELIST'):
   code={'name':300,'paper_units':140,'drawing_units':141}[attr]
   return next(t.value for t in TagCollector.dxftags(e) if t.code==code)
  return e.dxf.get(attr)
 if kind=='xdata':
  for e in d.modelspace():
   if e.xdata and any(same_name(key,'ZEV_APP') for key in e.xdata.data):return [list(t) for t in app_data(e,'ZEV_APP')]
  raise KeyError('ZEV_APP')
 if kind=='xrecord':return [list(t) for t in dictionary_item(next(e for e in d.modelspace() if e.has_extension_dict).get_extension_dict(),'ZEV_RECORD').tags]
 if kind=='group':return len(dictionary_item(dictionary_item(d.rootdict,'ACAD_GROUP'),name))
 raise CheckerLimit('Unsupported selector kind: '+kind)
def equal(a,b,tol):
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):return math.isclose(a,b,abs_tol=tol,rel_tol=0)
 if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(equal(x,y,tol) for x,y in zip(a,b))
 return a==b
def semantic_equal(d,f,actual):
 s=f['selector'];kind=s['kind'];attr=s.get('attr');expected=f['value'];tol=f['tolerance']
 if kind=='feature_attr' and s.get('table')=='INSERT' and attr=='name' and re.fullmatch(r'\*U[0-9]+',expected,re.I):
  b=symbol_item(d.blocks,actual)
  return bool(re.fullmatch(r'\*U[0-9]+',actual,re.I) and b.block.dxf.flags & 1)
 if attr=='block_circle_radius':return any(equal(radius,expected,tol) for radius in actual)
 if attr=='frozen_layers' or kind=='viewport_freeze':return {name_key(x) for x in actual}=={name_key(x) for x in expected}
 if attr=='redraw_order':return equal([name_key(x) for x in actual if any(same_name(x,y) for y in expected)],[name_key(x) for x in expected],tol)
 if symbol_attr(attr,s.get('table')) or (kind=='complex_pattern' and attr=='style'):return same_name(actual,expected)
 if kind=='table' and s['table']=='layers' and attr=='flags':return equal(actual & ~64,expected & ~64,tol)
 if attr=='opaque_values':
  e=feature_entity(d,s) if kind=='feature_attr' else (dictionary_item(d.rootdict,s['name']) if s['dictionary']=='ROOT' else dictionary_item(dictionary_item(d.rootdict,s['dictionary']),s['name']))
  return equal(proxy_payload(e),expected,tol)
 if kind=='linetype_pattern':
  def pattern(tags):return sorted([t for t in tags if t[0]!=49],key=lambda t:t[0])+[t for t in tags if t[0]==49]
  return equal(pattern(actual),pattern(expected),tol)
 return equal(actual,expected,tol)
def recomputed_fit_width(d, selector):
 from ezdxf.tools.text_size import text_size
 e=feature_entity(d,selector)
 span=(e.dxf.align_point-e.dxf.insert).magnitude
 # Resolve the font's symbol reference without changing the loaded entity.
 measured=e.copy()
 try:measured.dxf.style=symbol_item(d.styles,e.dxf.style).dxf.name
 except StopIteration:pass
 unscaled=text_size(measured).width/e.dxf.width
 return span/unscaled

def compare(d,intent,reader,source_version=None,source_encoding=None):
 rows=[]
 for f in applicable_fields(intent,source_version or d.dxfversion,source_encoding):
  row={'intent_id':intent['intent_id'],'field':f['id'],'reader':reader,'expected':f['value'],'tolerance':f['tolerance']}
  try:
   actual=extract(d,f['selector'])
   if actual is None:raise KeyError('Missing selected attribute')
   if f['selector'].get('attr')=='redraw_order':
    row['detail']={'literal_table':literal_redraw_order(redraw_layout(d,f['selector']['name'])),'effective_space_order':actual}
   actual=json.loads(json.dumps(actual,default=list));row['actual']=actual
   same=semantic_equal(d,f,actual)
   if not same and 'recomputed_width_relative_tolerance' in f:
    recomputed=recomputed_fit_width(d,f['selector'])
    same=abs(actual-recomputed)<=abs(recomputed)*f['recomputed_width_relative_tolerance']
    row['detail']='Font-measured Fit width factor '+str(recomputed)+'; relative tolerance '+str(f['recomputed_width_relative_tolerance'])
   row['status']='same' if same else 'differs'
  except CheckerLimit as ex:
   row.update(status='not_scored',detail=str(ex));row.setdefault('actual',None)
  except (KeyError,StopIteration,DXFError) as ex:
   row.update(status='absent',detail=str(ex));row.setdefault('actual',None)
  except Exception as ex:
   row.update(status='reader_error',detail=f'ezdxf {ezdxf.__version__} {type(ex).__name__}: {ex}');row.setdefault('actual',None)
  if f['selector'].get('attr','').startswith('acis_'):
   observation=dict(reader=reader,actual=None)
   try:
    actual=acis_value(feature_entity(d,f['selector']),f['selector']['attr'],public=True)
    observation.update(actual=actual,status='same' if equal(actual,f['value'],f['tolerance']) else 'differs')
   except (KeyError,StopIteration):observation.update(status='absent')
   except Exception as ex:
    detail=f'ezdxf {ezdxf.__version__} {type(ex).__name__}: {ex}'
    if isinstance(ex,IndexError) and d.dxfversion<'AC1027' and unpadded_binary_sat(feature_entity(d,f['selector'])):
     detail+='; cannot decode SAT from binary DXF written by Teigha programs, R2000 to R2010'
    observation.update(status='reader_error',detail=detail)
   row['read_observation']=observation
  rows.append(row)
 return rows
