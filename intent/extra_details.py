"""Additional independent generator expectations."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];MOD=['AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']
def load(t):return json.loads((R/'intent'/('feature_'+t+'.json')).read_text())
def add(i,layer,typ,attr,value,versions=MOD):
 key=layer+'.'+attr
 if any(f['id']==key for f in i['expected']):return
 i['features']=sorted(set(i['features']+[layer]));i['expected'].append(dict(id=key,value=value,selector=dict(kind='feature_attr',name=layer,table=typ,attr=attr),reference=dict(section=typ+'; '+attr,source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2026/ENU/',basis='DXF Reference; independently authored generator constants'),tolerance=1e-8,versions=versions))
def save(i):(R/'intent'/(i['intent_id']+'.json')).write_text(json.dumps(i,indent=2)+'\n')
i=load('b_geometry')
for st in range(3):add(i,f'F20_hatch_solid_style{st}','HATCH','loop_flags',[3,2,2])
for l,t,a,v in [('F23_hatch_flags7_22','HATCH','loop_flags',[7,22]),('F24_hatch_pattern','HATCH','pattern_name','ANSI31'),('F24_hatch_pattern','HATCH','pattern_scale',.5),('F24_hatch_pattern','HATCH','pattern_angle',15),('F25_hatch_gradient','HATCH','gradient_rotation',30),('F34_spline','SPLINE','fit_points',[[160,40,0],[170,55,0],[180,38,0],[190,52,0]]),('F35_linetype_custom','LINE','linetype','F35CUSTOM')]:add(i,l,t,a,v,MOD[1:] if a=='gradient_rotation' else MOD)
save(i)
i=load('c_layouts')
for l,h in [('F41_LayoutA',60),('F42_LayoutB',60)]:add(i,l,'VIEWPORT','view_height',h)
save(i)
i=load('d_dimensions')
for l,typ in [('F50_dim_linear',32),('F51_dim_aligned',32),('F52_dim_angular',34),('F53_dim_radial',36),('F55_dim_dimstyle_xdata',32)]:add(i,l,'DIMENSION','dimtype',typ)
save(i)
i=load('i_dictionaries')
for n in 'abcd':add(i,'F130_sortents_'+n,'SOLID','color',256)
for n in 'abc':add(i,'F131_sortents_block_'+n,'SOLID','color',256)
add(i,'F132_xdict_line','LINE','extension_record',[[1,'entity xrecord string'],[40,3.25],[70,7]])
save(i)
i=load('j_raster')
for l in ['F140_image_plain','F141_image_rotated','F142_image_clip_rect','F143_image_clip_poly','F144_image_adjust']:add(i,l,'IMAGE','image_size',[64,48])
add(i,'F142_image_clip_rect','IMAGE','boundary_path',[[10,10],[50,40]])
add(i,'F143_image_clip_poly','IMAGE','boundary_path',[[10,5],[54,12],[60,40],[30,46],[4,30],[10,5]])
save(i)
i=load('l_proxy')
for l,t in [('F180_proxy_entity','SYNTH_WIDGET'),('F181_proxy_entity_b','SYNTH_GADGET')]:add(i,l,t,'opaque_values',[[90,7],[40,2.5]],MOD)
save(i)
for topic,entries in [('n_misc',[('ACAD_SCALELIST','N_1_TO_37','name','N_1_TO_37'),('ACAD_SCALELIST','N_1_TO_37','paper_units',1.),('ACAD_SCALELIST','N_1_TO_37','drawing_units',37.),('ACAD_SCALELIST','N_5_TO_2','name','N_5_TO_2'),('ACAD_SCALELIST','N_5_TO_2','paper_units',5.),('ACAD_SCALELIST','N_5_TO_2','drawing_units',2.)]),('e_objects',[('ACAD_VISUALSTYLE','F70_plain','description','F70_plain'),('ACAD_VISUALSTYLE','F71_marker','description','F71_marker')])]:
 i=load(topic)
 for dictionary,name,attr,value in entries:
  key=name+'.'+attr
  if any(f['id']==key for f in i['expected']):continue
  feature='F169_scale_list_marker' if topic=='n_misc' else name
  i['features']=sorted(set(i['features']+[feature]))
  i['expected'].append(dict(id=key,value=value,selector=dict(kind='object',dictionary=dictionary,name=name,attr=attr),reference=dict(section='SCALE codes 300,140,141' if topic=='n_misc' else 'VISUALSTYLE code 2',source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2026/ENU/',basis='DXF Reference; invented object values'),tolerance=1e-8,versions=MOD if topic=='n_misc' else MOD[2:]))
 save(i)

i=load('i_dictionaries')
add(i,'F130_sortents_a','SOLID','redraw_order',['F130_sortents_d','F130_sortents_c','F130_sortents_b','F130_sortents_a'])
add(i,'F131_sortents_block_a','SOLID','redraw_order',['F131_sortents_block_c','F131_sortents_block_b','F131_sortents_block_a'])
save(i)
i=load('e_objects')
key='F71_marker.acad_marker'
if not any(f['id']==key for f in i['expected']):
 f=dict(i['expected'][-1]);f.update(id=key,value=[[1000,'AcRTDxfName'],[1000,'VISUALSTYLE']],selector=dict(kind='object',dictionary='ACAD_VISUALSTYLE',name='F71_marker',attr='acad_marker'));f['reference']=dict(f['reference'],section='VISUALSTYLE; Extended Data codes 1001,1000');i['expected'].append(f)
save(i)

for topic,name,attr,value,feature in [('e_objects','F72_xrecord','tags',[[1,'ZEV_RECORD'],[40,12.5],[70,42]],'F72_xrecord'),('e_objects','F73_dictionaryvar','value','ZEV_VAR','F73_dictionaryvar'),('l_proxy','SYNTH_OBJ_REF','opaque_values',[[90,3],[40,1.25]],'F182_proxy_object_marker')]:
 i=load(topic);key=name+'.'+attr
 if not any(f['id']==key for f in i['expected']):
  i['features']=sorted(set(i['features']+[feature]));i['expected'].append(dict(id=key,value=value,selector=dict(kind='object',dictionary='ROOT',name=name,attr=attr),reference=dict(section='XRECORD; DICTIONARYVAR; CLASSES',source='Autodesk DXF Reference',url='https://help.autodesk.com/view/OARX/2026/ENU/',basis='DXF Reference; invented payload'),tolerance=1e-8,versions=MOD))
 save(i)
