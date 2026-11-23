import json
from pathlib import Path
p=Path(__file__).parent
string={'type':'string','minLength':1};sha={'type':'string','pattern':'^[a-f0-9]{64}$'}
def obj(props,required=None):return {'type':'object','properties':props,'required':required or list(props),'additionalProperties':False}
identity={'intent_id':string,'representation_id':string}
selector=obj({'kind':{'enum':['identity','query_count','insert_attributes','linetype_pattern','complex_pattern','table','block','layer_count','layout_count','viewport_freeze','viewport_color','object','xdata','xrecord','group','feature_attr']},'table':string,'name':string,'attr':string,'dictionary':string},['kind'])
required_by_kind={'feature_attr':['table','name','attr'],'table':['table','name','attr'],'block':['name','attr'],'layout_count':['name'],'viewport_color':['name'],'object':['dictionary','name','attr'],'group':['name'],'query_count':['name'],'linetype_pattern':['name'],'complex_pattern':['name','attr']}
selector['allOf']=[{'if':{'properties':{'kind':{'const':k}}},'then':{'required':v}} for k,v in required_by_kind.items()]
f=obj({'id':string,'value':{},'selector':selector,'reference':obj({'section':string,'source':string,'url':{'type':'string','format':'uri','pattern':r'^https://help\.autodesk\.com/cloudhelp/\d{4}/ENU/AutoCAD-DXF/files/GUID-[A-F0-9-]+\.htm(?:#.*)?$'},'basis':string,'basis_type':{'enum':['normative','application_semantics','compatibility_policy','synthetic']}}),'tolerance':{'type':'number','minimum':0},'versions':{'type':'array','items':{'enum':['AC1009','AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']},'minItems':1,'uniqueItems':True}})
f['properties']['recomputed_width_relative_tolerance']={'type':'number','minimum':0,'maximum':1}
intent=obj({**identity,'feature_fields':{'type':'object','additionalProperties':{'type':'array','items':string,'minItems':1,'uniqueItems':True}},'title':string,'description':string,'status':{'enum':['wanted','planned','blocked']},'features':{'type':'array','items':string,'minItems':1,'uniqueItems':True},'expected':{'type':'array','items':f,'minItems':1}})
intent['required']=['intent_id','title','description']
intent['allOf']=[{'if':{'not':{'required':['status']}},'then':{'required':['representation_id','features','expected']}}]
side=obj({**identity,'program':{'enum':['ezdxf','oda','bricscad','cadcraft']},'build':string,'format':{'enum':['DXF','DWG']},'version':{'enum':['R12','2000','2004','2007','2010','2013','2018']},'encoding':{'enum':['ASCII','binary']},'made_by':obj({'script':string,'input_digest':sha}),'content_digest':sha,'ezdxf_based':{'type':'boolean'},'digest_reader':string},['intent_id','representation_id','program','build','format','version','encoding','made_by','content_digest','ezdxf_based'])
for n,s in [('intent',intent),('provenance',side)]:s['$schema']='https://json-schema.org/draft/2020-12/schema';(p/(n+'.schema.json')).write_text(json.dumps(s,indent=2)+'\n')
