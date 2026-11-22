"""Independent feature expectations transcribed from the synthetic generators."""
from pathlib import Path
import json,math
R=Path(__file__).resolve().parents[1]
MOD=['AC1015','AC1018','AC1021','AC1024','AC1027','AC1032'];ALL=['AC1009']+MOD
JUST=['LEFT','CENTER','RIGHT','ALIGNED','MIDDLE','FIT','BOTTOM_LEFT','BOTTOM_CENTER','BOTTOM_RIGHT','MIDDLE_LEFT','MIDDLE_CENTER','MIDDLE_RIGHT','TOP_LEFT','TOP_CENTER','TOP_RIGHT']
def load(topic):return json.loads((R/'intent'/('feature_'+topic+'.json')).read_text())
def field(i,layer,typ,attr,value,versions=MOD):
 key=layer+'.'+attr
 if any(f['id']==key for f in i['expected']):return
 i['features']=sorted(set(i['features']+[layer]))
 i['expected'].append(dict(id=key,value=value,selector=dict(kind='feature_attr',name=layer,table=typ,attr=attr),reference=dict(section=typ+'; '+attr,source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2026/ENU/',basis='DXF Reference; independently authored generator constants'),tolerance=1e-8,versions=versions))
def save(i):(R/'intent'/(i['intent_id']+'.json')).write_text(json.dumps(i,indent=2)+'\n')
i=load('a_text')
for n,j in enumerate(JUST):
 h,v=({'LEFT':(0,0),'CENTER':(1,0),'RIGHT':(2,0),'ALIGNED':(3,0),'MIDDLE':(4,0),'FIT':(5,0)}.get(j) or ({'LEFT':0,'CENTER':1,'RIGHT':2}[j.split('_')[1]],{'BOTTOM':1,'MIDDLE':2,'TOP':3}[j.split('_')[0]]))
 for prefix,typ in [('F01_text_','TEXT'),('F03_attdef_','ATTDEF'),('F05_attrib_','ATTRIB')]:
  layer=prefix+j.lower()
  for attr,value in [('halign',h),('valign',v),('height',2.5)]:field(i,layer,typ,attr,value,ALL if typ!='ATTRIB' else MOD)
for layer,ap,width in [('F10_mtext_tl_width',1,40),('F11_mtext_mc_nowidth',5,0),('F12_mtext_tl_nowidth',1,0),('F13_mtext_mc_width',5,35)]:
 for attr,value in [('attachment_point',ap),('width',width),('char_height',2.5)]:field(i,layer,'MTEXT',attr,value)
for layer,typ in [('F04_attdef_multiline','ATTDEF'),('F04_attrib_multiline','ATTRIB')]:field(i,layer,typ,'has_embedded_mtext',True,['AC1032'])
save(i)
i=load('b_geometry')
for n,style in [(20,0),(21,1),(22,2)]:
 field(i,f'F20_hatch_style{style}','HATCH','hatch_style',style)
field(i,'F30_lwpoly_bulge_width','LWPOLYLINE','points',[[0,40,.5,1,.8],[20,40,1.5,.2,-.6],[40,55,0,0,0],[60,40,.3,.3,0]])
# Layer spelling is defined by the source generator.
for f in i['expected']:
 if '_hatch_style' in f['selector']['name']:f['selector']['name']=f['selector']['name'].replace('_hatch_style','_hatch_solid_style');f['id']=f['id'].replace('_hatch_style','_hatch_solid_style')
i['features']=sorted({f['selector']['name'] for f in i['expected']})
save(i)
i=load('g_blocks')
for layer,typ,attr,value in [('F100_block_basepoint','INSERT','name','G_BASEOFF'),('F101_nested_outer','INSERT','name','G_OUTER'),('F105_insert_minsert','INSERT','column_count',3),('F106_unused_block','CIRCLE','radius',2),('F107_wipeout_in_block','WIPEOUT','boundary_path',[[-.5,.5],[.5,.5],[.5,-.5],[-.5,-.5],[-.5,.5]]),('F108_wipeout_block_text','TEXT','text','OVER WIPE'),('F111_anonymous_block','INSERT','name','*U77')]:field(i,layer,typ,attr,value)
save(i)
i=load('h_attributes')
for n,name,flags in [(113,'constant',2),(114,'invisible',1),(115,'verify',4),(116,'preset',8),(117,'lockpos',0),(118,'rotinsert',0),(119,'mirinsert',0),(120,'textmirror',0),(121,'valuediff',0),(122,'nodef',0)]:
 field(i,f'F{n}_attdef_{name}','ATTDEF','flags',flags)
 if n not in [113,122]:field(i,f'F{n}_attrib_{name}','ATTRIB','flags',flags)
for layer,typ,attr,val in [('F117_attdef_lockpos','ATTDEF','lock_position',1),('F117_attrib_lockpos','ATTRIB','lock_position',1),('F120_attrib_textmirror','ATTRIB','text_generation_flag',2),('F121_attrib_valuediff','ATTRIB','text','CHANGED VALUE 9'),('F123_attrib_style_a','ATTRIB','style','H_STYLE_A'),('F124_attrib_style_b','ATTRIB','style','H_STYLE_B')]:field(i,layer,typ,attr,val,MOD[2:] if attr=='lock_position' else MOD)
save(i)
i=load('n_misc')
for layer,typ,attr,val in [('F160_polyline2d_width_bulge','POLYLINE','vertices',[[0,0,.5,1.5,0],[10,0,1,.2,.5],[20,5,0,0,-.4],[30,0,.8,.8,0]]),('F161_polyline2d_closed','POLYLINE','flags',1),('F162_polyline3d','POLYLINE','flags',8),('F166_viewport_scaled','VIEWPORT','view_height',40),('F168_viewport_frozen','VIEWPORT','frozen_layers',['F163_point'])]:field(i,layer,typ,attr,val,ALL if typ=='POLYLINE' else MOD)
save(i)
