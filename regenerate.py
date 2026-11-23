"""Regenerate the native and ODA cross sets in the foreground."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys,json,hashlib,csv,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from programs.settings import SETTINGS
from generators.background import build
from checker.core import digest,compare
from programs.adapters import Ezdxf,Oda,VERSIONS

def write_json(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def sidecar(p,doc,intent,adapter,version,encoding,input_digest):
 return {'intent_id':intent['intent_id'],'representation_id':intent['representation_id'],'program':adapter.name,'build':adapter.build,'format':p.suffix[1:].upper(),'version':version,'encoding':encoding,'made_by':{'script':'regenerate.py','input_digest':input_digest},'content_digest':digest(doc),'ezdxf_based':True}
def publish(temp,dest,meta):
 sc=dest.with_suffix(dest.suffix+'.provenance.json');old=json.loads(sc.read_text()) if sc.exists() else {}
 if not dest.exists() or any(old.get(k)!=meta[k] for k in ['content_digest','build','encoding']):
  dest.parent.mkdir(parents=True,exist_ok=True);temp.replace(dest);write_json(sc,meta)
def run_case(case, cross=True):
 intent,topic,version,encoding,input_digest=case;ez=Ezdxf();oda=Oda();rows=[]
 d=build(topic,version)
 with tempfile.TemporaryDirectory(dir=ROOT/'results') as tmp:
  p=Path(tmp)/'drawing.dxf';ez.save(d,p,'DXF',version,encoding);loaded=ez.open(p)
  dest=ROOT/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf';meta=sidecar(dest,loaded,intent,ez,version,encoding,input_digest)
  checks=compare(loaded,intent,'ezdxf '+ez.build)
  a=loaded.audit()
  audit={'intent_id':intent['intent_id'],'version':version,'encoding':encoding,'errors':len(a.errors),'fixes':len(a.fixes)}
  if a.errors:raise RuntimeError(str(a.errors))
  publish(p,dest,meta)
  for row in checks:
   row.update(file=str(dest.relative_to(ROOT)),converter=None,self_read=False);rows.append(row)
  for fmt in (['DXF','DWG'] if cross else []):
   out=Path(tmp)/('cross.'+fmt.lower());oda.save(dest,out,fmt,version,encoding if fmt=='DXF' else 'binary')
   dd=ez.open(out) if fmt=='DXF' else oda.read_dwg(out)
   target=ROOT/'cross/ezdxf__oda'/f'{topic}_{version}_{encoding}.{fmt.lower()}'
   publish(out,target,sidecar(target,dd,intent,oda,version,encoding if fmt=='DXF' else 'binary',meta['content_digest']))
   for row in compare(dd,intent,'ezdxf '+ez.build, VERSIONS[version]):
    row.update(file=str(target.relative_to(ROOT)),converter='oda '+oda.build if fmt=='DWG' else None,self_read=(fmt=='DWG'));rows.append(row)
 return rows,audit

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--intent')
 parser.add_argument('--pairs',help='Comma-separated declared pair IDs')
 parser.add_argument('--dry-run',action='store_true')
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
   for pair in pairs:
    build=ADAPTERS[pair.split('__')[1]].build
    for src,dest,fmt,version,enc,side in jobs_for(pair,intent=args.intent):
     sc=dest.with_suffix(dest.suffix+'.provenance.json')
     old=json.loads(sc.read_text()) if sc.exists() else {}
     if not dest.exists() or old.get('made_by',{}).get('input_digest')!=side['content_digest'] or old.get('build')!=build:
      print('Would rewrite '+dest.relative_to(ROOT).as_posix()+' from '+src.relative_to(ROOT).as_posix())
     else:print('Up to date '+dest.relative_to(ROOT).as_posix())
   return
  if args.intent:
   if args.intent.startswith('feature_'):
    from generators.run_features import main as feature_main
    feature_main(args.intent)
   elif args.intent.startswith('background_'):
    ip=ROOT/'intent'/f'{args.intent}.json';intent=json.loads(ip.read_text())
    topic=args.intent.removeprefix('background_')
    inp=hashlib.sha256(ip.read_bytes()+(ROOT/'generators/background.py').read_bytes()).hexdigest()
    rows=[r for r in json.loads((ROOT/'results/checks.json').read_text()) if not (r['intent_id']==args.intent and r['file'].startswith('native/ezdxf/'))]
    audits=[r for r in json.loads((ROOT/'results/audits.json').read_text()) if r['intent_id']!=args.intent]
    for version in VERSIONS:
     if version=='R12' and topic=='plots':continue
     for enc in (['ASCII'] if version=='R12' else ['ASCII','binary']):
      rs,a=run_case((intent,topic,version,enc,inp),cross=False);rows.extend(rs);audits.append(a)
    write_json(ROOT/'results/checks.json',rows);write_json(ROOT/'results/audits.json',audits)
   else:parser.error('Intent has no ezdxf native generator')
  for pair in pairs:run_pair(pair,intent=args.intent,reader_name=None if args.with_bricscad else 'oda')
  return
 cases=[]
 for ip in sorted((ROOT/'intent').glob('background_*.json')):
  intent=json.loads(ip.read_text());topic=intent['intent_id'].removeprefix('background_');input_digest=hashlib.sha256(ip.read_bytes()+(ROOT/'generators/background.py').read_bytes()).hexdigest()
  for version in VERSIONS:
   if version=='R12' and topic=='plots':continue
   for encoding in (['ASCII'] if version=='R12' else ['ASCII','binary']):cases.append((intent,topic,version,encoding,input_digest))
 rows=[];audits=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  for rs,a in pool.map(run_case,cases):
   rows.extend(rs);audits.append(a);print(f"Completed {len(audits)}/{len(cases)} native inputs",flush=True)
 barriers=[{'program':'oda','status':'resolved','cause':'Original launcher referenced a missing executable; direct AppRun under xvfb works.','blocked':'cross generation, DWG reading, exact executable build and save-digest evidence'}]
 write_json(ROOT/'results/checks.json',rows);write_json(ROOT/'results/audits.json',audits);write_json(ROOT/'results/barriers.json',barriers)
 with (ROOT/'results/checks.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['file','intent_id','field','reader','converter','self_read','status','expected','actual','tolerance','detail']);w.writeheader();w.writerows(rows)
 from generators.run_features import main as feature_main
 feature_main()
 from generators.run_cross import PAIRS,jobs_for,run_pair
 for pair in PAIRS:
  if pair.split('__')[1]=='bricscad' and not args.with_bricscad:
   for _,dest,*_ in jobs_for(pair):print('Skipped BricsCAD '+dest.relative_to(ROOT).as_posix())
  elif pair.split('__')[1]=='oda' and not args.with_bricscad:
   run_pair(pair,reader_name='oda')
  else:run_pair(pair)
 from map.build import main as map_main
 map_main()
 from intent.validate import main as validate
 validate();subprocess.run([SETTINGS['python'],'-I',str(ROOT/'measure_size.py')],check=True,cwd=ROOT)
 if any(row['status']!='same' for row in rows if row['file'].startswith('native/')):raise RuntimeError('Native expected-field failures; see results/checks.json')
 print(json.dumps({'files':len(audits),'fields':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in ['same','differs','absent']},'barriers':barriers}))
if __name__=='__main__':main()
