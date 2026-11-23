"""Regenerate the native and ODA cross sets in the foreground."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys,json,hashlib,csv,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from programs.settings import SETTINGS
from generators.background import build
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import digest,compare
from programs.adapters import Ezdxf,Oda,VERSIONS

def write_json(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def sidecar(p,doc,intent,adapter,version,encoding,input_digest):
 return {'intent_id':intent['intent_id'],'representation_id':intent['representation_id'],'program':adapter.name,'build':adapter.build,'format':p.suffix[1:].upper(),'version':version,'encoding':encoding,'made_by':{'script':'regenerate.py','input_digest':input_digest},'content_digest':digest(doc),'ezdxf_based':True}
def publish(temp,dest,meta,force=False):
 sc=dest.with_suffix(dest.suffix+'.provenance.json');old=json.loads(sc.read_text()) if sc.exists() else {}
 if force or not dest.exists() or any(old.get(k)!=meta[k] for k in ['content_digest','build','encoding']):
  dest.parent.mkdir(parents=True,exist_ok=True);temp.replace(dest)
 if old!=meta:write_json(sc,meta)
def run_case(case, cross=True, force=False):
 intent,topic,version,encoding,input_digest=case;ez=Ezdxf();oda=Oda();rows=[]
 dest=ROOT/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf'
 sc=dest.with_suffix('.dxf.provenance.json')
 old=json.loads(sc.read_text()) if sc.exists() else {}
 if not force and not cross and dest.exists() and old.get('build')==ez.build and old.get('made_by',{}).get('input_digest')==input_digest:
  previous=[r for r in load_rows(ROOT/'results/checks.json') if r['file']==dest.relative_to(ROOT).as_posix()]
  if current(previous,ROOT,intent['intent_id']):
   return previous,dict(intent_id=intent['intent_id'],version=version,encoding=encoding,errors=0,fixes=0)
  loaded=ez.open(dest)
  checks=compare(loaded,intent,'ezdxf '+ez.build)
  for row in checks:row.update(file=dest.relative_to(ROOT).as_posix(),converter=None,self_read=False)
  annotate(checks,ROOT,intent['intent_id'],'ezdxf','ezdxf')
  return checks,dict(intent_id=intent['intent_id'],version=version,encoding=encoding,errors=0,fixes=0)
 d=build(topic,version)
 with tempfile.TemporaryDirectory(dir=ROOT/'results') as tmp:
  p=Path(tmp)/'drawing.dxf';ez.save(d,p,'DXF',version,encoding);loaded=ez.open(p)
  dest=ROOT/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf';meta=sidecar(dest,loaded,intent,ez,version,encoding,input_digest)
  checks=compare(loaded,intent,'ezdxf '+ez.build)
  a=loaded.audit()
  audit={'intent_id':intent['intent_id'],'version':version,'encoding':encoding,'errors':len(a.errors),'fixes':len(a.fixes)}
  if a.errors:raise RuntimeError(str(a.errors))
  publish(p,dest,meta,force=force)
  for row in checks:
   row.update(file=str(dest.relative_to(ROOT)),converter=None,self_read=False);rows.append(row)
  for fmt in (['DXF','DWG'] if cross else []):
   out=Path(tmp)/('cross.'+fmt.lower());oda.save(dest,out,fmt,version,encoding if fmt=='DXF' else 'binary')
   dd=ez.open(out) if fmt=='DXF' else oda.read_dwg(out)
   target=ROOT/'cross/ezdxf__oda'/f'{topic}_{version}_{encoding}.{fmt.lower()}'
   publish(out,target,sidecar(target,dd,intent,oda,version,encoding if fmt=='DXF' else 'binary',meta['content_digest']),force=force)
   for row in compare(dd,intent,'ezdxf '+ez.build, VERSIONS[version]):
    row.update(file=str(target.relative_to(ROOT)),converter='oda '+oda.build if fmt=='DWG' else None,self_read=(fmt=='DWG'));rows.append(row)
 annotate(rows,ROOT,intent['intent_id'],'ezdxf','ezdxf')
 for row in rows:
  if row['file'].startswith('cross/'):
   annotate([row],ROOT,intent['intent_id'],'oda','oda' if row['converter'] else 'ezdxf')
 return rows,audit

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--intent')
 parser.add_argument('--pairs',help='Comma-separated declared pair IDs')
 parser.add_argument('--dry-run',action='store_true')
 parser.add_argument('--force',action='store_true',help='Resave selected outputs regardless of input digests')
 parser.add_argument('--with-bricscad',action='store_true',help='Include pairs that launch BricsCAD')
 args=parser.parse_args()
 if args.intent or args.pairs or args.dry_run:
  from generators.run_cross import PAIRS,jobs_for,run_pair
  pairs=args.pairs.split(',') if args.pairs else list(PAIRS)
  if any(p not in PAIRS for p in pairs):parser.error('Unknown declared pair')
  if args.intent and not (ROOT/'intent'/f'{args.intent}.json').is_file():parser.error('Unknown intent')
  skipped=[p for p in pairs if not args.with_bricscad and (p.split('__')[1]=='bricscad')]
  for pair in skipped:
   for _,dest,*_ in jobs_for(pair,intent=args.intent):print('Skipped BricsCAD '+dest.relative_to(ROOT).as_posix())
  pairs=[p for p in pairs if p not in skipped]
  if args.dry_run:
   from programs.adapters import ADAPTERS
   native_save=native_score=0
   for ip in sorted((ROOT/'intent').glob('*.json')):
    if args.intent and ip.stem!=args.intent:continue
    if not ip.stem.startswith(('background_','feature_')):continue
    feature=ip.stem.startswith('feature_');topic=ip.stem.split('_',1)[1]
    inp,cases=native_input(ROOT,ip.stem,versions=VERSIONS)
    previous=load_rows(ROOT/('results/features_checks.json' if feature else 'results/checks.json'))
    for version in VERSIONS:
     for enc in [e for v,e in cases if v==version]:
      dest=ROOT/'native/ezdxf'/f'{topic}_{version}_{enc}.dxf';sc=dest.with_suffix('.dxf.provenance.json')
      old=json.loads(sc.read_text()) if sc.exists() else {}
      rel=dest.relative_to(ROOT).as_posix()
      if args.force or not dest.exists() or old.get('build')!=Ezdxf.build or old.get('made_by',{}).get('input_digest')!=inp:native_save+=1
      elif not current([r for r in previous if r['file']==rel],ROOT,ip.stem):native_score+=1
   print(f'native: {native_save} resave, {native_score} rescore')
   from generators import run_bricscad as bc_runner
   from programs.adapters import BricsCad
   from checker.scoring import reading_current
   import ezdxf
   bc_save=bc_score=0
   previous=load_rows(ROOT/'results/native_bricscad_checks.json')
   for topic,iid in bc_runner.TOPICS.items():
    if args.intent and args.intent!=iid:continue
    if not (ROOT/'intent'/f'{iid}.json').exists():continue
    inp,_=native_input(ROOT,iid,'bricscad',Path(bc_runner.__file__),bc_runner.LSP)
    sidecars=sorted((ROOT/'native/bricscad').glob(topic+'_*.provenance.json'))
    stale=args.force or any(not Path(str(sc).removesuffix('.provenance.json')).exists() or json.loads(sc.read_text()).get('build')!=BricsCad.build or json.loads(sc.read_text()).get('made_by',{}).get('input_digest')!=inp for sc in sidecars)
    if stale:
     bc_save+=len(sidecars)
     continue
    for sc in sidecars:
     dest=Path(str(sc).removesuffix('.provenance.json'));old=json.loads(sc.read_text())
     rel=dest.relative_to(ROOT).as_posix()
     if not current([r for r in previous if r['file']==rel],ROOT,iid):bc_score+=1
   print(f'native bricscad: {bc_save} resave, {bc_score} rescore')
   previous=load_rows(ROOT/'results/cross_ezdxf__oda_read_by_bricscad_checks.json');bc_score=0
   for dest in sorted((ROOT/'cross/ezdxf__oda').glob('*.dwg')):
    side=json.loads(dest.with_suffix('.dwg.provenance.json').read_text());iid=side['intent_id']
    if args.intent and args.intent!=iid:continue
    rel=dest.relative_to(ROOT).as_posix()
    old=[r for r in previous if r['file']==rel]
    identity=hashlib.sha256(dest.read_bytes()).hexdigest()
    if args.force or not current(old,ROOT,iid) or not reading_current(old,'ezdxf '+ezdxf.__version__,'bricscad '+BricsCad.build) or any(r.get('read_input_digest')!=identity for r in old):bc_score+=1
   print(f'read by bricscad: 0 resave, {bc_score} rescore')

   for pair in pairs:
    resaves=rescores=0
    previous=load_rows(ROOT/'results'/f'cross_{pair}_checks.json')
    build=ADAPTERS[pair.split('__')[1]].build
    for src,dest,fmt,version,enc,side in jobs_for(pair,intent=args.intent):
     sc=dest.with_suffix(dest.suffix+'.provenance.json')
     old=json.loads(sc.read_text()) if sc.exists() else {}
     rel=dest.relative_to(ROOT).as_posix()
     if args.force or not dest.exists() or old.get('made_by',{}).get('input_digest')!=side['content_digest'] or old.get('build')!=build:
      resaves+=1
      print('Would rewrite '+dest.relative_to(ROOT).as_posix()+' from '+src.relative_to(ROOT).as_posix())
     else:
      if not current([r for r in previous if r['file']==rel],ROOT,side['intent_id']):rescores+=1
    print(f'{pair}: {resaves} resave, {rescores} rescore')
   return
  if args.intent:
   if args.intent.startswith('feature_'):
    from generators.run_features import main as feature_main
    feature_main(args.intent, force=args.force)
   elif args.intent.startswith('background_'):
    ip=ROOT/'intent'/f'{args.intent}.json';intent=json.loads(ip.read_text())
    topic=args.intent.removeprefix('background_')
    inp=native_input(ROOT,ip.stem)[0]
    rows=[r for r in json.loads((ROOT/'results/checks.json').read_text()) if not (r['intent_id']==args.intent and r['file'].startswith('native/ezdxf/'))]
    audits=[r for r in json.loads((ROOT/'results/audits.json').read_text()) if r['intent_id']!=args.intent]
    for version in VERSIONS:
     if (version,'ASCII') not in native_input(ROOT,ip.stem)[1]:continue
     for enc in (['ASCII'] if version=='R12' else ['ASCII','binary']):
      rs,a=run_case((intent,topic,version,enc,inp),cross=False,force=args.force);rows.extend(rs);audits.append(a)
    write_json(ROOT/'results/checks.json',rows);write_json(ROOT/'results/audits.json',audits)
   elif args.with_bricscad:
    from generators.run_bricscad import main as bricscad_main, TOPICS
    if args.intent not in TOPICS.values():parser.error('Intent has no native generator')
    bricscad_main(args.intent, force=args.force)
   else:parser.error('Intent has no ezdxf native generator')
  for pair in pairs:run_pair(pair,intent=args.intent,reader_name=None if args.with_bricscad else 'oda',force=args.force)
  if args.with_bricscad:
   from generators.run_independent import main as independent_main
   independent_main(args.intent, force=args.force, root=ROOT)
  return
 cases=[]
 for ip in sorted((ROOT/'intent').glob('background_*.json')):
  intent=json.loads(ip.read_text());topic=intent['intent_id'].removeprefix('background_');input_digest=native_input(ROOT,ip.stem)[0]
  for version in VERSIONS:
   if (version,'ASCII') not in native_input(ROOT,ip.stem)[1]:continue
   for encoding in (['ASCII'] if version=='R12' else ['ASCII','binary']):cases.append((intent,topic,version,encoding,input_digest))
 rows=[];audits=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  for rs,a in pool.map(lambda case:run_case(case,cross=False,force=args.force),cases):
   rows.extend(rs);audits.append(a);print(f"Completed {len(audits)}/{len(cases)} native inputs",flush=True)
 barriers=[{'program':'oda','status':'resolved','cause':'Original launcher referenced a missing executable; direct AppRun under xvfb works.','blocked':'cross generation, DWG reading, exact executable build and save-digest evidence'}]
 write_json(ROOT/'results/checks.json',rows);write_json(ROOT/'results/audits.json',audits);write_json(ROOT/'results/barriers.json',barriers)
 with (ROOT/'results/checks.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['file','intent_id','field','reader','converter','self_read','scored_with','writer_engine','reader_engine','shared_engine','status','expected','actual','tolerance','detail']);w.writeheader();w.writerows(rows)
 from generators.run_features import main as feature_main
 feature_main(force=args.force)
 if args.with_bricscad:
  from generators.run_bricscad import main as bricscad_main
  bricscad_main(force=args.force)
 from generators.run_cross import PAIRS,jobs_for,run_pair
 for pair in PAIRS:
  if pair.split('__')[1]=='bricscad' and not args.with_bricscad:
   for _,dest,*_ in jobs_for(pair):print('Skipped BricsCAD '+dest.relative_to(ROOT).as_posix())
  elif pair.split('__')[1]=='oda' and not args.with_bricscad:
   run_pair(pair,reader_name='oda',force=args.force)
  else:run_pair(pair,force=args.force)
 if args.with_bricscad:
  from generators.run_independent import main as independent_main
  independent_main(args.intent, force=args.force, root=ROOT)
 from map.build import main as map_main
 map_main()
 from intent.validate import main as validate
 validate();subprocess.run([SETTINGS['python'],'-I',str(ROOT/'measure_size.py')],check=True,cwd=ROOT)
 if any(row['status']!='same' for row in rows if row['file'].startswith('native/')):raise RuntimeError('Native expected-field failures; see results/checks.json')
 print(json.dumps({'files':len(audits),'fields':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in ['same','differs','absent']},'barriers':barriers}))
if __name__=='__main__':main()
