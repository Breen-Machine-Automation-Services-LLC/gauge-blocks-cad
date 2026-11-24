"""Author explicit independent expectations, never read generated drawings."""
import json
from pathlib import Path
try:
 from intent.references import author_references
except ModuleNotFoundError as exc:
 if exc.name != 'intent':
  raise
 from references import author_references
ROOT=Path(__file__).resolve().parent
ALL=['AC1009','AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']; MOD=ALL[1:]
def make(topic):return {'intent_id':'background_'+topic,'title':topic.title(),'description':'Synthetic background '+topic,'representation_id':'reference_1','features':[],'expected':[]}
def add(i,key,value,selector,ref,modern=False,*,basis_type):
 i['expected'].append({'id':key,'value':value,'selector':selector,'reference':{'basis_type':basis_type,'section':ref,'source':'Autodesk DXF Reference','url':'https://help.autodesk.com/view/OARX/2024/ENU/?guid=GUID-235B22E0-A567-4CF6-92D3-38A2306D73F3','basis':'DXF Reference'},'tolerance':1e-9 if isinstance(value,float) else 0,'versions':MOD if modern else ALL})
def tab(i,table,name,attr,value,ref,modern=False,*,basis_type):add(i,f'{name}.{attr}',value,{'kind':'table','table':table,'name':name,'attr':attr},ref,modern,basis_type=basis_type)
for topic in ['blocks','layers','styles','plots','metadata','named']:
 i=make(topic)
 add(i,'identity',['background_'+topic,'reference_1'],{'kind':'identity'},'BLOCK extended data; APPID; codes 1001,1000',basis_type='synthetic')
 if topic=='blocks':
  i['features']=['unused block with attribute definition','used block with attribute']
  for name,n in [('ZEV_UNUSED',0),('ZEV_USED',1)]:
   for attr,value in [('tag',['ZEV_TAG']),('text',['ZEV_VALUE']),('inserts',n)]:add(i,name+'.'+attr,value,{'kind':'block','name':name,'attr':attr},'BLOCK; ATTDEF codes 2,1; INSERT code 2',basis_type='synthetic')
 if topic=='blocks':add(i,'used_attributes',[['ZEV_TAG','ZEV_VALUE']],{'kind':'insert_attributes'},'ATTRIB codes 2,1',basis_type='synthetic')
 if topic=='layers':
  i['features']=['100 mixed-state layers','unused layers','three populated layers','paper viewport freeze','paper viewport color override']
  add(i,'layer_count',100,{'kind':'layer_count'},'LAYER table',basis_type='synthetic')
  for n in range(100):
   name=f'ZEV_{n:03}'
   for attr,value in [('color',-(n%7+1) if n%4==0 else n%7+1),('flags',(1 if n%5==0 else 0)|(4 if n%7==0 else 0)),('linetype','ZEV_DASH' if n%2 else 'Continuous'),('plot',int(n%3!=0)),('lineweight',25 if n%2 else 50)]:tab(i,'layers',name,attr,value,'LAYER codes 62,70,6,290,370',attr in ['plot','lineweight'],basis_type='synthetic')
  for n in range(100):add(i,f'layer_usage_{n:03}',int(n<3),{'kind':'query_count','name':f'*[layer=="ZEV_{n:03}"]'},'Common entity code 8',basis_type='synthetic')
  add(i,'vp.freeze',['ZEV_001'],{'kind':'viewport_freeze'},'VIEWPORT code 331',True,basis_type='synthetic')
  add(i,'vp.color',6,{'kind':'viewport_color','name':'ZEV_002'},'LAYER extension dictionary; XRECORD viewport override (Reference silent on mapping)',True,basis_type='compatibility_policy')
  i['expected'][-1]['reference']['basis']='Compatibility policy, provisional: no published standard settles the override mapping'
 if topic=='styles':
  i['features']=['unused linetype','unused text style','unused dimension style']
  for table,name,attrs,ref in [('linetypes','ZEV_DASH',{'description':'ZEV pattern'},'LTYPE code 3; pattern codes 40,49'),('styles','ZEV_TEXT',{'font':'txt','height':2.5,'width':.8},'STYLE codes 3,40,41'),('dimstyles','ZEV_DIM',{'dimscale':2.,'dimasz':3.},'DIMSTYLE codes 40,41')]:
   for k,v in attrs.items():tab(i,table,name,k,v,ref,basis_type='synthetic')
 if topic=='styles':
  add(i,'style_usage',0,{'kind':'query_count','name':'TEXT MTEXT DIMENSION'},'TEXT; MTEXT; DIMENSION table references',basis_type='synthetic')
  add(i,'dash_pattern',[[72,65],[73,2],[40,1.0],[49,.5],[49,-.5]],{'kind':'linetype_pattern','name':'ZEV_DASH'},'LTYPE codes 72,73,40,49,74',basis_type='synthetic')
 if topic=='styles':
  i['features'].append('unused text-bearing linetype')
  for attr,value in {'text':'ZEV','style':'ZEV_TEXT','scale':.1,'rotation':0.,'xoffset':0.,'yoffset':0.,'element_type':2}.items():add(i,'complex.'+attr,value,{'kind':'complex_pattern','name':'ZEV_TEXT_PATTERN','attr':attr},'LTYPE codes 9,340,46,50,44,45,74',True,basis_type='synthetic')
 if topic=='plots':
  i['features']=['named page setup','plot-style table reference','empty layout']
  add(i,'empty',0,{'kind':'layout_count','name':'ZEV_EMPTY'},'LAYOUT; BLOCK_RECORD',True,basis_type='synthetic')
  for k,v in {'page_setup_name':'ZEV_SETUP','current_style_sheet':'ZEV_STYLE.ctb','paper_width':210.,'paper_height':297.}.items():add(i,k,v,{'kind':'object','dictionary':'ACAD_PLOTSETTINGS','name':'ZEV_SETUP','attr':k},'PLOTSETTINGS codes 1,7,44,45',True,basis_type='synthetic')
 if topic=='metadata':
  i['features']=['registered application','extended data','extension dictionary with XRECORD','DICTIONARYVAR']
  tab(i,'appids','ZEV_APP','name','ZEV_APP','APPID code 2',basis_type='synthetic')
  add(i,'xdata',[[1000,'ZEV_DATA'],[1040,12.5]],{'kind':'xdata'},'Extended Data codes 1000,1040',basis_type='synthetic')
  add(i,'xrecord',[[1,'ZEV_RECORD_VALUE'],[90,42]],{'kind':'xrecord'},'XRECORD codes 1,90; extension dictionary code 360',True,basis_type='synthetic')
  add(i,'dictionaryvar','ZEV_VAR_VALUE',{'kind':'object','dictionary':'ZEV_DICT','name':'ZEV_VAR','attr':'value'},'DICTIONARYVAR code 1',True,basis_type='synthetic')
 if topic=='named':
  i['features']=['scale list','named view','named UCS','group']
  for k,v in {'height':20.,'width':30.,'center':[1.,2.]}.items():tab(i,'views','ZEV_VIEW',k,v,'VIEW codes 40,41,10',basis_type='synthetic')
  for k,v in {'origin':[3.,4.,0.],'xaxis':[1.,0.,0.],'yaxis':[0.,1.,0.]}.items():tab(i,'ucs','ZEV_UCS',k,v,'UCS codes 10,11,12',basis_type='synthetic')
  add(i,'group',1,{'kind':'group','name':'ZEV_GROUP'},'GROUP code 340',True,basis_type='synthetic')
  for k,v in {'name':'ZEV_SCALE','paper_units':1.,'drawing_units':5.}.items():add(i,'scale.'+k,v,{'kind':'object','dictionary':'ACAD_SCALELIST','name':'ZEV_SCALE','attr':k},'SCALE codes 300,140,141',True,basis_type='synthetic')
 path=ROOT/(i['intent_id']+'.json')
 if path.exists():
  existing=json.loads(path.read_text())
  for key in ('title','description','feature_fields'):
   if key in existing:i[key]=existing[key]
  existing.update(i);i=existing
 path.write_text(json.dumps(author_references(i),indent=2)+'\n')
