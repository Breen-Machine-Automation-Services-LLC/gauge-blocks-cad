"""Regenerate the native and ODA cross sets in the foreground."""
from pathlib import Path
import sys,json,csv,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from programs.settings import SETTINGS
from generators.background import build
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import encoding_intent, digest,compare
from programs.adapters import Ezdxf,Oda,VERSIONS

def write_json(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def sidecar(p,doc,intent,adapter,version,encoding,input_digest):
 return {'intent_id':intent['intent_id'],'representation_id':intent['representation_id'],'program':adapter.name,'build':adapter.build,'format':p.suffix[1:].upper(),'version':version,'encoding':encoding,'made_by':{'script':'regenerate.py','input_digest':input_digest},'content_digest':digest(doc),'ezdxf_based':True}
def publish(temp,dest,meta,force=False,doc=None):
 sc=dest.with_suffix(dest.suffix+'.provenance.json');old=json.loads(sc.read_text()) if sc.exists() else {}
 if force or not dest.exists() or any(old.get(k)!=meta[k] for k in ['content_digest','build','encoding']):
  dest.parent.mkdir(parents=True,exist_ok=True);temp.replace(dest)
 if getattr(doc, 'filename', None) and Path(doc.filename) == temp: doc.filename=str(dest)
 if old!=meta:write_json(sc,meta)
def run_case(case, cross=True, force=False, root=None, action=None):
 root=ROOT if root is None else Path(root)
 intent,topic,version,encoding,input_digest=case;ez=Ezdxf();oda=Oda();rows=[]
 dest=root/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf'
 sc=dest.with_suffix('.dxf.provenance.json')
 old=json.loads(sc.read_text()) if sc.exists() else {}
 if action=='rescore' or (action is None and not force and not cross and dest.exists() and old.get('build')==ez.build and old.get('made_by',{}).get('input_digest')==input_digest):
  previous=[r for r in load_rows(root/'results/checks.json') if r['file']==dest.relative_to(root).as_posix()]
  if action is None and current(previous,root,intent['intent_id']):
   return previous,dict(intent_id=intent['intent_id'],version=version,encoding=encoding,errors=0,fixes=0)
  loaded=ez.open(dest)
  checks=compare(loaded, encoding_intent(intent, encoding), 'ezdxf '+ez.build, None)
  for row in checks:row.update(file=dest.relative_to(root).as_posix(),converter=None,self_read=False)
  annotate(checks,root,intent['intent_id'],'ezdxf','ezdxf')
  return checks,dict(intent_id=intent['intent_id'],version=version,encoding=encoding,errors=0,fixes=0)
 d=build(topic,version)
 with tempfile.TemporaryDirectory(dir=root/'results') as tmp:
  p=Path(tmp)/'drawing.dxf';ez.save(d,p,'DXF',version,encoding);loaded=ez.open(p)
  dest=root/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf';meta=sidecar(dest,loaded,intent,ez,version,encoding,input_digest)
  checks=compare(loaded, encoding_intent(intent, encoding), 'ezdxf '+ez.build, None)
  a=loaded.audit()
  audit={'intent_id':intent['intent_id'],'version':version,'encoding':encoding,'errors':len(a.errors),'fixes':len(a.fixes)}
  if a.errors:raise RuntimeError(str(a.errors))
  publish(p,dest,meta,force=force)
  for row in checks:
   row.update(file=str(dest.relative_to(root)),converter=None,self_read=False);rows.append(row)
  for fmt in (['DXF','DWG'] if cross else []):
   out=Path(tmp)/('cross.'+fmt.lower());oda.save(dest,out,fmt,version,encoding if fmt=='DXF' else 'binary')
   dd=ez.open(out) if fmt=='DXF' else oda.read_dwg(out)
   target=root/'cross/ezdxf__oda'/f'{topic}_{version}_{encoding}.{fmt.lower()}'
   publish(out,target,sidecar(target,dd,intent,oda,version,encoding if fmt=='DXF' else 'binary',meta['content_digest']),force=force,doc=dd)
   for row in compare(dd, encoding_intent(intent, encoding if fmt=='DXF' else 'binary'), 'ezdxf '+ez.build, VERSIONS[version]):
    row.update(file=str(target.relative_to(root)),converter='oda '+oda.build if fmt=='DWG' else None,self_read=(fmt=='DWG'));rows.append(row)
 annotate(rows,root,intent['intent_id'],'ezdxf','ezdxf')
 for row in rows:
  if row['file'].startswith('cross/'):
   annotate([row],root,intent['intent_id'],'oda','oda' if row['converter'] else 'ezdxf')
 return rows,audit

def _jobs(intent_id, root):
 jobs=[]
 for topic in sorted([p.stem.removeprefix('background_') for p in (root/'intent').glob('background_*.json')]):
  iid='background_'+topic
  if intent_id and iid!=intent_id:continue
  inp,cases=native_input(root,iid,versions=VERSIONS)
  for version,enc in cases:
   jobs.append((iid,topic,version,enc,inp,root/'native/ezdxf'/f'{topic}_{version}_{enc}.dxf'))
 return jobs

def plan(intent_id=None, force=False, root=None):
 from checker.scoring import native_plan
 root=ROOT if root is None else Path(root)
 return native_plan(_jobs(intent_id,root),root,force,Ezdxf.build,root/'results/checks.json',current)

def run_native(intent_id=None, force=False, root=None):
 from checker.scoring import record_score
 root=ROOT if root is None else Path(root)
 work=plan(intent_id,force,root)
 path=root/'results/checks.json';previous=load_rows(path)
 selected=set(sum(work.values(),[]))
 rows=[r for r in previous if r['file'] not in selected]
 audits=load_rows(root/'results/audits.json')
 for iid,topic,version,enc,inp,dest in _jobs(intent_id,root):
  rel=dest.relative_to(root).as_posix()
  if rel in work['carried']:
   rows.extend(r for r in previous if r['file']==rel);continue
  intent=json.loads((root/'intent'/f'{iid}.json').read_text())
  rs,a=run_case((intent,topic,version,enc,inp),cross=False,force=force,root=root,action='resave' if rel in work['resave'] else 'rescore')
  rows.extend(rs);record_score(rs,root,iid,path,rel)
  audits=[x for x in audits if not (x.get('intent_id')==iid and x.get('version')==version and x.get('encoding')==enc)]
  audits.append(a)
 write_json(path,rows);write_json(root/'results/audits.json',audits)
 with (root/'results/checks.csv').open('w') as stream:
  writer=csv.DictWriter(stream,fieldnames=['file','intent_id','field','reader','converter','self_read','scored_with','writer_engine','reader_engine','shared_engine','status','expected','actual','tolerance','detail','read_observation'])
  writer.writeheader();writer.writerows(rows)
 if any(r['status']!='same' for r in rows if r['file'].startswith('native/')):
  raise RuntimeError('Native expected-field failures; see results/checks.json')

def main():
 import argparse
 from generators import run_features,run_bricscad,run_cross
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--intent')
 parser.add_argument('--pairs')
 parser.add_argument('--dry-run',action='store_true')
 parser.add_argument('--force',action='store_true')
 parser.add_argument('--with-bricscad',action='store_true')
 parser.add_argument('--with-autocad',action='store_true')
 args=parser.parse_args()
 pairs=args.pairs.split(',') if args.pairs else list(run_cross.PAIRS)
 if any(p not in run_cross.PAIRS for p in pairs):parser.error('Unknown declared pair')
 if args.intent and not (ROOT/'intent'/f'{args.intent}.json').is_file():parser.error('Unknown intent')
 if args.intent and not (args.intent in run_bricscad.TOPICS.values() or args.intent in {'feature_'+t for t in run_features.TOPICS} or any(j[0]==args.intent for j in _jobs(args.intent,ROOT))):
  parser.error('Intent has no native generator')
 native_ezdxf=not args.pairs or any(p.startswith('ezdxf__') for p in pairs)
 native_bricscad=(args.with_bricscad and not args.pairs) or (bool(args.pairs) and any(p.startswith('bricscad__') for p in pairs))
 pairs=[p for p in pairs if (args.with_bricscad or p.split('__')[1]!='bricscad') and (args.with_autocad or p.split('__')[1]!='autocad')]
 reader=None
 if args.dry_run:
  def report(label,plans):
   combined={k:sum((p[k] for p in plans),[]) for k in ('resave','rescore','carried','gaps')}
   print(f"{label}: {len(combined['resave'])} resave, {len(combined['rescore'])} rescore, {len(combined['carried'])} carried, {len(combined['gaps'])} capability gaps")
   for kind in ('resave','rescore','carried','gaps'):
    for rel in combined[kind]:print(f'  {kind}: {rel}')
  if native_ezdxf:report('native',[plan(args.intent,force=args.force,root=ROOT),run_features.plan(args.intent,force=args.force,root=ROOT)])
  if native_bricscad:report('native bricscad',[run_bricscad.plan(args.intent,force=args.force,root=ROOT)])
  for pair in pairs:report(pair,[run_cross.plan(pair,intent_id=args.intent,force=args.force,root=ROOT,reader_name=reader)])
  return
 if native_ezdxf and (not args.intent or args.intent.startswith('background_')):run_native(args.intent,force=args.force,root=ROOT)
 if native_ezdxf and (not args.intent or args.intent.startswith('feature_')):run_features.main(args.intent,force=args.force,root=ROOT)
 if native_bricscad and (not args.intent or args.intent in run_bricscad.TOPICS.values()):run_bricscad.main(args.intent,force=args.force,root=ROOT)
 for pair in pairs:run_cross.run_pair(pair,intent=args.intent,reader_name=reader,force=args.force,root=ROOT)
 if not args.intent and not args.pairs:
  barriers=load_rows(ROOT/'results/barriers.json')
  write_json(ROOT/'results/barriers.json',barriers)
  rows=load_rows(ROOT/'results/checks.json');audits=load_rows(ROOT/'results/audits.json')
  from checker.derived import rebuild
  rebuild()
  from intent.validate import main as validate
  validate()
  print(json.dumps(dict(files=len(audits),fields=len(rows),statuses={s:sum(r['status']==s for r in rows) for s in ('same','differs','absent')},barriers=barriers)))
if __name__=='__main__':main()
