"""Generate and verify feature DXFs without launching proprietary programs."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from generators.features import TOPICS,build
from programs.adapters import Ezdxf,VERSIONS
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import compare
from regenerate import sidecar,publish,write_json
import tempfile

def main(intent_id=None, force=False):
 ez=Ezdxf();rows=[];audits=[]
 if intent_id:
  rows=[r for r in json.loads((R/'results/features_checks.json').read_text()) if r['intent_id']!=intent_id]
  audits=[r for r in json.loads((R/'results/features_audits.json').read_text()) if not Path(r['file']).name.startswith(intent_id.removeprefix('feature_')+'_')]
 for topic in sorted(TOPICS):
  if intent_id and intent_id != 'feature_'+topic: continue
  ip=R/'intent'/('feature_'+topic+'.json');intent=json.loads(ip.read_text());inp,cases= native_input(R,intent['intent_id'],versions=VERSIONS)
  for version in VERSIONS:
   for encoding in [e for v,e in cases if v==version]:
    dest=R/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf'
    sc=dest.with_suffix('.dxf.provenance.json')
    old=json.loads(sc.read_text()) if sc.exists() else {}
    if not force and dest.exists() and old.get('build')==ez.build and old.get('made_by',{}).get('input_digest')==inp:
     previous=[r for r in load_rows(R/'results/features_checks.json') if r['file']==dest.relative_to(R).as_posix()]
     if current(previous,R,intent['intent_id']):checks=previous
     else:
      checks=compare(ez.open(dest),intent,'ezdxf '+ez.build)
      for row in checks:row.update(file=dest.relative_to(R).as_posix(),converter=None,self_read=False)
     annotate(checks,R,intent['intent_id'],'ezdxf','ezdxf')
     assert all(x['status']=='same' for x in checks),(topic,version,checks)
     rows.extend(checks);audits.append(dict(file=dest.relative_to(R).as_posix(),errors=0,fixes=0));continue
    d=build(topic,version)
    with tempfile.TemporaryDirectory(dir=R/'results') as td:
     tmp=Path(td)/'drawing.dxf';ez.save(d,tmp,'DXF',version,encoding);loaded=ez.open(tmp)
     dest=R/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf';meta=sidecar(dest,loaded,intent,ez,version,encoding,inp)
     checks=compare(loaded,intent,'ezdxf '+ez.build)
     audit=loaded.audit()
     assert not audit.errors and not audit.fixes,(topic,version,audit.errors,audit.fixes)
     meta['made_by']['script']='generators/run_features.py';publish(tmp,dest,meta,force=force)
     sc=dest.with_suffix('.dxf.provenance.json')
     if json.loads(sc.read_text())!=meta:write_json(sc,meta)
     for row in checks:row.update(file=dest.relative_to(R).as_posix(),converter=None,self_read=False)
     assert all(x['status']=='same' for x in checks),(topic,version,[x for x in checks if x["status"]!="same"])
     annotate(checks,R,intent['intent_id'],'ezdxf','ezdxf')
     rows.extend(checks);audits.append(dict(file=dest.relative_to(R).as_posix(),errors=0,fixes=0))
  print('Verified '+topic,flush=True)
 write_json(R/'results/features_checks.json',rows);write_json(R/'results/features_audits.json',audits)
 print(f'{len(audits)} files; {len(rows)} fields same; zero audit errors or fixes')
if __name__=='__main__':main()
