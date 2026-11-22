import hashlib,json,math,re
import ezdxf.math
from ezdxf.lldxf.tagwriter import TagCollector
from ezdxf.lldxf.const import DXFError
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
def layer_of(e):
 # Exported tags first (as before); ezdxf exports no tags for ACIS entities before R2013, so fall back to the loaded attribute.
 value=next((t.value for t in TagCollector.dxftags(e) if t.code==8),None)
 if value is None and e.dxf.hasattr('layer'):value=e.dxf.layer
 return value
def table_tags(e):
 tags=[(t.code,t.value) for t in TagCollector.dxftags(e)]
 return tags[next(i for i,t in enumerate(tags) if t==(100,'AcDbTable')):]
def extract(d,s):
 kind=s['kind'];name=s.get('name');attr=s.get('attr')
 if kind=='feature_attr':
  e=next(e for e in d.entitydb.values() if e.is_alive and e.dxftype()==s['table'] and layer_of(e)==name)
  if attr=='alignment_rotation_error':
   delta=e.dxf.align_point-e.dxf.insert
   angle=math.degrees(math.atan2(delta.y,delta.x))
   return (e.dxf.rotation-angle+180)%360-180
  if attr=='table_rows':return next(v for c,v in table_tags(e) if c==91)
  if attr=='table_columns':return next(v for c,v in table_tags(e) if c==92)
  if attr=='table_cell_text':return [v for c,v in table_tags(e) if c==1 and v!='']
  if attr in ('acis_body_count','acis_bbox_size'):
   from ezdxf.acis import api as acis
   bodies=acis.load_dxf(e)
   if attr=='acis_body_count':return len(bodies)
   box=ezdxf.math.BoundingBox([v for m in acis.mesh_from_body(bodies[0]) for v in m.vertices])
   return list(box.size)
  if attr=='redraw_order':
   layout=d.blocks.get('I_SORTBLK') if name.startswith('F131') else d.modelspace()
   return [d.entitydb[h].dxf.layer for h,order in sorted(layout.get_redraw_order(),key=lambda pair:int(pair[1],16))]
  if attr=='image_size':return list(e.dxf.image_size)[:2]
  if attr=='loop_flags':return [p.path_type_flags for p in e.paths]
  if attr=='gradient_rotation':return e.gradient.rotation
  if attr=='fit_points':return [list(v) for v in e.fit_points]
  if attr=='extension_record':return [list(t) for t in e.get_extension_dict()['G_XR'].tags]
  if attr=='opaque_values':return [list(t) for t in TagCollector.dxftags(e) if t.code in [90,40]]
  if attr=='has_embedded_mtext':return e.has_embedded_mtext_entity
  if attr=='points':return [list(p) for p in e.get_points('xyseb')]
  if attr=='vertices':return [[v.dxf.location.x,v.dxf.location.y,v.dxf.start_width,v.dxf.end_width,v.dxf.bulge] for v in e.vertices]
  if attr in ['boundary_path','frozen_layers']:return list(getattr(e,attr))
  value=getattr(e.dxf,attr)
  return 0 if value is None and attr=='width' else value
 if kind=='table':
  value=getattr(getattr(d,s['table']).get(name).dxf,attr)
  # VIEW center is a 2D DCS point in the Reference.
  if s['table']=='views' and attr=='center':return list(value)[:2]
  return value
 if kind=='block':
  b=d.blocks.get(name)
  if attr=='inserts':return len(d.modelspace().query('INSERT[name=="'+name+'"]'))
  return [e.dxf.get(attr) for e in b if e.dxftype()=='ATTDEF']
 if kind=='identity':return [t.value for t in d.modelspace().block_record.block.get_xdata('ZEV_IDENTITY')]
 if kind=='query_count':return len(d.modelspace().query(s['name']))
 if kind=='insert_attributes':return [[a.dxf.tag,a.dxf.text] for e in d.modelspace().query('INSERT') for a in e.attribs]
 if kind=='linetype_pattern':return [list(t) for t in d.linetypes.get(name).pattern_tags.tags if t.code in [72,73,40,49]]
 if kind=='complex_pattern':
  tags=d.linetypes.get(name).pattern_tags.tags
  if attr=='style':return d.entitydb[next(t.value for t in tags if t.code==340)].dxf.name
  code={'text':9,'scale':46,'rotation':50,'xoffset':44,'yoffset':45,'element_type':74}[attr]
  return next(t.value for t in tags if t.code==code and (code!=74 or t.value!=0))
 if kind=='layer_count':return len([x for x in d.layers if x.dxf.name.startswith('ZEV_')])
 if kind=='layout_count':return len(d.layouts.get(name))
 if kind=='viewport_freeze':return list(next(v for v in d.layouts.get('ZEV_PAPER').viewports() if v.dxf.id!=1).frozen_layers)
 if kind=='viewport_color':
  v=next(v for v in d.layouts.get('ZEV_PAPER').viewports() if v.dxf.id!=1)
  return d.layers.get(name).get_vp_overrides().get_color(v.dxf.handle)
 if kind=='object':
  e=d.rootdict[name] if s['dictionary']=='ROOT' else d.rootdict[s['dictionary']][name]
  if attr=='tags':return [list(t) for t in e.tags]
  if attr=='opaque_values':return [list(t) for t in TagCollector.dxftags(e) if t.code in [90,40]]
  if attr=='acad_marker':return [list(t) for t in e.get_xdata('ACAD')]
  if s['dictionary']=='ACAD_SCALELIST':
   code={'name':300,'paper_units':140,'drawing_units':141}[attr]
   return next(t.value for t in TagCollector.dxftags(e) if t.code==code)
  return e.dxf.get(attr)
 if kind=='xdata':return [list(t) for t in next(e for e in d.modelspace() if e.has_xdata('ZEV_APP')).get_xdata('ZEV_APP')]
 if kind=='xrecord':return [list(t) for t in next(e for e in d.modelspace() if e.has_extension_dict).get_extension_dict()['ZEV_RECORD'].tags]
 if kind=='group':return len(d.groups.get(name))
 raise ValueError(kind)
def equal(a,b,tol):
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):return math.isclose(a,b,abs_tol=tol,rel_tol=0)
 if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(equal(x,y,tol) for x,y in zip(a,b))
 return a==b
def recomputed_fit_width(d, selector):
 from ezdxf.tools.text_size import text_size
 e=next(e for e in d.entitydb.values() if e.is_alive and e.dxftype()==selector['table'] and layer_of(e)==selector['name'])
 span=(e.dxf.align_point-e.dxf.insert).magnitude
 unscaled=text_size(e).width/e.dxf.width
 return span/unscaled

def compare(d,intent,reader,source_version=None):
 rows=[]
 for f in intent['expected']:
  if (source_version or d.dxfversion) not in f['versions']:continue
  row={'intent_id':intent['intent_id'],'field':f['id'],'reader':reader,'expected':f['value'],'tolerance':f['tolerance']}
  try:
   actual=extract(d,f['selector']);actual=json.loads(json.dumps(actual,default=list));row['actual']=actual
   same=equal(actual,f['value'],f['tolerance'])
   if not same and 'recomputed_width_relative_tolerance' in f:
    recomputed=recomputed_fit_width(d,f['selector'])
    same=abs(actual-recomputed)<=abs(recomputed)*f['recomputed_width_relative_tolerance']
    row['detail']='Font-measured Fit width factor '+str(recomputed)+'; relative tolerance '+str(f['recomputed_width_relative_tolerance'])
   row['status']='same' if same else 'differs'
  except (KeyError,StopIteration,AttributeError,TypeError,IndexError,ValueError,DXFError) as ex:row.update(status='absent',actual=None,detail=str(ex))
  rows.append(row)
 return rows
