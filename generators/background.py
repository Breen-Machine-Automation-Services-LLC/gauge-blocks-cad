"""Invented background content. No external drawing inputs."""
import ezdxf

def build(topic, version):
 d=ezdxf.new(version if version=='R12' else 'R'+version); m=d.modelspace(); modern=version!='R12'
 d.appids.new('ZEV_IDENTITY')
 m.block_record.block.set_xdata('ZEV_IDENTITY',[(1000,'background_'+topic),(1000,'reference_1')])
 if topic=='blocks':
  for name in ['ZEV_UNUSED','ZEV_USED']:
   b=d.blocks.new(name); b.add_attdef('ZEV_TAG',(0,0),text='ZEV_VALUE',height=2)
  m.add_blockref('ZEV_USED',(0,0)).add_auto_attribs({'ZEV_TAG':'ZEV_VALUE'})
 elif topic=='layers':
  d.linetypes.new('ZEV_DASH',dxfattribs={'pattern':[1,.5,-.5]})
  for i in range(100):
   a={'color':i%7+1,'linetype':'ZEV_DASH' if i%2 else 'Continuous','flags':(1 if i%5==0 else 0)|(4 if i%7==0 else 0)}
   if modern:a.update(plot=int(i%3!=0),lineweight=25 if i%2 else 50)
   l=d.layers.new(f'ZEV_{i:03}',dxfattribs=a)
   if i%4==0:l.off()
   if i<3:m.add_point((i,0),dxfattribs={'layer':l.dxf.name})
  if modern:
   p=d.layouts.new('ZEV_PAPER');v=p.add_viewport((5,5),(10,10),(0,0),10);v.freeze('ZEV_001')
   o=d.layers.get('ZEV_002').get_vp_overrides();o.set_color(v.dxf.handle,6);o.commit()
 elif topic=='styles':
  d.linetypes.new('ZEV_DASH',dxfattribs={'pattern':[1,.5,-.5],'description':'ZEV pattern'})
  d.styles.new('ZEV_TEXT',dxfattribs={'font':'txt','height':2.5,'width':.8})
  if modern:
   lt=d.linetypes.new('ZEV_TEXT_PATTERN')
   lt.setup_pattern('A,.5,-.2,["ZEV",ZEV_TEXT,S=.1,R=0,X=0,Y=0],-.2',length=.9)
  d.dimstyles.new('ZEV_DIM',dxfattribs={'dimscale':2.,'dimasz':3.})
 elif topic=='plots':
  d.layouts.new('ZEV_EMPTY')
  dic=d.rootdict.get_required_dict('ACAD_PLOTSETTINGS'); p=d.objects.new_entity('PLOTSETTINGS',{'owner':dic.dxf.handle,'page_setup_name':'ZEV_SETUP','current_style_sheet':'ZEV_STYLE.ctb','paper_width':210.,'paper_height':297.});dic['ZEV_SETUP']=p
 elif topic=='metadata':
  d.appids.new('ZEV_APP');e=m.add_point((1,2));e.set_xdata('ZEV_APP',[(1000,'ZEV_DATA'),(1040,12.5)])
  if modern:
   x=e.new_extension_dict();r=x.add_xrecord('ZEV_RECORD');r.reset([(1,'ZEV_RECORD_VALUE'),(90,42)])
   dic=d.rootdict.get_required_dict('ZEV_DICT');dic['ZEV_VAR']=d.objects.add_dictionary_var(owner=dic.dxf.handle,value='ZEV_VAR_VALUE')
 elif topic=='named':
  d.views.new('ZEV_VIEW',dxfattribs={'height':20.,'width':30.,'center':(1,2)})
  d.ucs.new('ZEV_UCS',dxfattribs={'origin':(3,4,0),'xaxis':(1,0,0),'yaxis':(0,1,0)})
  if modern:
   e=m.add_point((2,3));g=d.groups.new('ZEV_GROUP',description='ZEV collection');g.set_data([e])
   dic=d.rootdict.get_required_dict('ACAD_SCALELIST')
   from ezdxf.entities import factory
   from ezdxf.lldxf.extendedtags import ExtendedTags
   s=factory.load(ExtendedTags.from_text('0\nSCALE\n330\n'+dic.dxf.handle+'\n100\nAcDbScale\n70\n0\n300\nZEV_SCALE\n140\n1.0\n141\n5.0\n290\n0\n'),d)
   d.entitydb.add(s);d.objects.add_object(s);dic['ZEV_SCALE']=s
 return d
