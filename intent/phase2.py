"""Author phase 2 intentions and explicit source-level expectations."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def save(i):(R/'intent'/(i['intent_id']+'.json')).write_text(json.dumps(i,indent=2)+'\n')
for p in (R/'intent').glob('background_*.json'):
 i=json.loads(p.read_text());i.update(title=i['intent_id'].replace('_',' ').title(),description='Synthetic background content defined by the referenced DXF fields.');save(i)
MOD=['AC1015','AC1018','AC1021','AC1024','AC1027','AC1032'];ALL=['AC1009']+MOD
# Expected constants transcribed from the source generators, independent of saved drawings.
cases={
'a_text':[('F14_text_rotated','TEXT','rotation',33),('F07_style_widthobl','TEXT','text','Wide oblique')],
'b_geometry':[('F31_arc','ARC','radius',8),('F32_circle','CIRCLE','radius',7),('F33_ellipse','ELLIPSE','ratio',.5),('F36_linetype_dashed_ltscale','LINE','ltscale',2.5)],
'c_layouts':[('F40_model_marker','CIRCLE','radius',20)],
'd_dimensions':[('F54_dim_override_text','DIMENSION','text','OVR <> mm')],
'e_objects':[('F70_plain','LINE','end',[10,5,0])],
'f_extents':[('F80_extents_line','LINE','end',[17,11,0]),('F81_extents_mtext_block','INSERT','insert',[10,2,0])],
'g_blocks':[('F102_insert_rotated','INSERT','rotation',30),('F103_insert_mirrored','INSERT','xscale',-1),('F104_insert_nonuniform','INSERT','yscale',.5),('F105_insert_minsert','INSERT','row_count',2)],
'h_attributes':[('F118_insert_rotinsert','INSERT','rotation',40),('F119_insert_mirinsert','INSERT','xscale',-1)],
'i_dictionaries':[('F132_xdict_circle','CIRCLE','radius',4)],
'j_raster':[('F144_image_adjust','IMAGE','brightness',70),('F144_image_adjust','IMAGE','contrast',30),('F144_image_adjust','IMAGE','fade',20)],
'n_misc':[('F164_solid','SOLID','thickness',2),('F167_viewport_twisted','VIEWPORT','view_twist_angle',30)]}
for topic,fields in cases.items():
 i=dict(intent_id='feature_'+topic,title=topic[2:].replace('_',' ').title(),description='Ported synthetic master '+topic[0].upper()+'. Feature layers retain the source generator identifiers.',representation_id='reference_1',features=sorted({x[0] for x in fields}),expected=[])
 for layer,typ,attr,value in fields:
  i['expected'].append(dict(id=layer+'.'+attr,value=value,selector=dict(kind='feature_attr',name=layer,table=typ,attr=attr),reference=dict(section=typ+' group codes for '+attr,source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2026/ENU/',basis='DXF Reference; invented constants from the source generator'),tolerance=1e-8,versions=MOD if typ in ['IMAGE','VIEWPORT','DIMENSION','ELLIPSE'] or attr=='ltscale' else ALL))
 save(i)
stubs=[('m_ole','OLE','blocked','Needs an authoring program that can embed an OLE object.'),('surface','SURFACE','planned','An extruded surface from an open curve, written by an authoring program that creates surface entities.'),('dynamic_blocks','AutoCAD dynamic blocks','blocked','Blocked on AutoCAD; author evaluation graph and dynamic block metadata.'),('aec_proxy','AEC proxy objects','blocked','Blocked on AutoCAD with an AEC vertical product; preserve classes and opaque payload.'),('acceptance','AutoCAD opens but loads no drawing','blocked','Blocked on AutoCAD; verify open succeeds and drawing content actually loads.'),('representations','Multiple representations per intent','planned','Author alternative valid encodings with shared semantic expectations.'),('codepages','Pre-2007 code-page text','planned','Accented, Cyrillic and East Asian strings with explicit code pages.'),('unicode','UTF-8 versus escaped text','planned','Compare literal UTF-8 and escaped Unicode at 2007 and later.'),('proof_sheet','Visual proof sheet','planned','Realistic invented schematic with a known visible location for every loss.'),('own_drawings','Generator for user drawings','wanted','Accept a user drawing as input to produce native and cross sets.')]
for key,title,status,description in stubs:save(dict(intent_id='future_'+key,title=title,status=status,description=description))
