"""Synthetic feature topics ported from masters A through N."""
from pathlib import Path
import sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import ezdxf
from generators import masters_abcd as a, masters_ghijn as b
TOPICS={'a_text':a.master_a,'b_geometry':a.master_b,'c_layouts':a.master_c,'d_dimensions':a.master_d,'g_blocks':b.master_g,'h_attributes':b.master_h,'i_dictionaries':b.master_i,'j_raster':b.master_j,'n_misc':b.master_n}
def master_e():
 from ezdxf.entities import factory
 from ezdxf.lldxf.extendedtags import ExtendedTags
 d=ezdxf.new('R2018');dic=d.rootdict.get_required_dict('ACAD_VISUALSTYLE')
 for n,marker in [('F70_plain',False),('F71_marker',True)]:
  text='0\nVISUALSTYLE\n330\n'+dic.dxf.handle+'\n100\nAcDbVisualStyle\n2\n'+n+'\n70\n0\n71\n0\n72\n0\n73\n0\n90\n0\n40\n0.0\n291\n0\n'
  e=factory.load(ExtendedTags.from_text(text),d);d.entitydb.add(e);d.objects.add_object(e);dic[n]=e
  if marker:e.set_xdata('ACAD',[(1000,'AcRTDxfName'),(1000,'VISUALSTYLE')])
  d.layers.new(n);d.modelspace().add_line((0,0),(10,5),dxfattribs={'layer':n})
 xr=d.rootdict.add_xrecord('F72_xrecord');xr.reset([(1,'ZEV_RECORD'),(40,12.5),(70,42)])
 dv=d.objects.add_dictionary_var(d.rootdict.dxf.handle,'ZEV_VAR');d.rootdict['F73_dictionaryvar']=dv
 for name in ['F72_xrecord','F73_dictionaryvar']:
  d.layers.new(name);d.modelspace().add_point((20,0),dxfattribs={'layer':name})
 return d
def master_f():
 d=ezdxf.new('R2018');d.layers.new('F80_extents_line');d.layers.new('F81_extents_mtext_block')
 block=d.blocks.new('F81_MTBLK');block.add_mtext(r'{\pxqc;\H0.36588x;ZEV text\H1.2147x;\P\H0.68751x;ZEV label}',dxfattribs={'char_height':.2186,'width':0,'attachment_point':1,'layer':'F81_extents_mtext_block'})
 d.modelspace().add_line((0,0),(17,11),dxfattribs={'layer':'F80_extents_line'});d.modelspace().add_blockref('F81_MTBLK',(10,2),dxfattribs={'layer':'F81_extents_mtext_block'});return d
from generators.master_l import master_l
TOPICS.update(e_objects=master_e,f_extents=master_f,l_proxy=master_l)
def build(topic,version):
 d=TOPICS[topic]()
 if topic=='n_misc':
  from ezdxf.entities import factory
  from ezdxf.lldxf.extendedtags import ExtendedTags
  dic=d.rootdict['ACAD_SCALELIST']
  for name,pu,du in [('N_1_TO_37',1.,37.),('N_5_TO_2',5.,2.)]:
   raw='0\nSCALE\n330\n'+dic.dxf.handle+'\n100\nAcDbScale\n70\n0\n300\n'+name+'\n140\n'+str(pu)+'\n141\n'+str(du)+'\n290\n0\n'
   e=factory.load(ExtendedTags.from_text(raw),d);d.entitydb.add(e);d.objects.add_object(e);dic[name]=e
 # Preserve only representable R12 entities, including block geometry.
 if version=='R12':
  out=ezdxf.new('R12');supported={'LINE','POINT','CIRCLE','ARC','SOLID','TEXT','POLYLINE','INSERT','ATTDEF'}
  for layer in d.layers:
   if layer.dxf.name not in out.layers:out.layers.new(layer.dxf.name)
  def transfer(e,target):
   if e.dxftype()=='INSERT':
    attrs={k:v for k,v in e.dxf.all_existing_dxf_attribs().items() if k in ['layer','rotation','xscale','yscale','zscale','row_count','column_count','row_spacing','column_spacing']}
    ins=target.add_blockref(e.dxf.name,e.dxf.insert,dxfattribs=attrs)
    for att in e.attribs:
     attrs={'layer':att.dxf.layer,'height':att.dxf.height}
     if att.dxf.halign in (3,5):
      attrs.update({k:att.dxf.get(k) for k in ('rotation','width','halign','valign','align_point')})
     ins.add_attrib(att.dxf.tag,att.dxf.text,att.dxf.insert,dxfattribs=attrs)
   else:target.add_foreign_entity(e)
  for block in d.blocks:
   if block.name.lower().startswith(('*model','*paper')):continue
   nb=out.blocks.new(block.name,base_point=block.block.dxf.base_point)
   for e in block:
    if e.dxftype() in supported:transfer(e,nb)
  for e in d.modelspace():
   if e.dxftype() in supported:transfer(e,out.modelspace())
  d=out
 else:d.dxfversion='R'+version
 if 'ZEV_IDENTITY' not in d.appids:d.appids.new('ZEV_IDENTITY')
 d.modelspace().block_record.block.set_xdata('ZEV_IDENTITY',[(1000,'feature_'+topic),(1000,'reference_1')])
 return d
