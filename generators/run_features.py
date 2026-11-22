"""Generate and verify feature DXFs without launching proprietary programs."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from generators.features import TOPICS,build
from programs.adapters import Ezdxf,VERSIONS
from checker.core import compare
from regenerate import sidecar,publish,write_json
import tempfile

def main(intent_id=None):
 ez=Ezdxf();rows=[];audits=[]
 if intent_id:
  rows=[r for r in json.loads((R/'results/features_checks.json').read_text()) if r['intent_id']!=intent_id]
  audits=[r for r in json.loads((R/'results/features_audits.json').read_text()) if not Path(r['file']).name.startswith(intent_id.removeprefix('feature_')+'_')]
 for topic in sorted(TOPICS):
  if intent_id and intent_id != 'feature_'+topic: continue
  ip=R/'intent'/('feature_'+topic+'.json');intent=json.loads(ip.read_text());inp=hashlib.sha256(ip.read_bytes()+b''.join(p.read_bytes() for p in sorted((R/'generators').glob('*.py')))).hexdigest()
  for version in VERSIONS:
   for encoding in (['ASCII'] if version=='R12' else ['ASCII','binary']):
    d=build(topic,version)
    with tempfile.TemporaryDirectory(dir=R/'results') as td:
     tmp=Path(td)/'drawing.dxf';ez.save(d,tmp,'DXF',version,encoding);loaded=ez.open(tmp);audit=loaded.audit()
     assert not audit.errors and not audit.fixes,(topic,version,audit.errors,audit.fixes)
     dest=R/'native/ezdxf'/f'{topic}_{version}_{encoding}.dxf';meta=sidecar(dest,loaded,intent,ez,version,encoding,inp);meta['made_by']['script']='generators/run_features.py';publish(tmp,dest,meta)
     sc=dest.with_suffix('.dxf.provenance.json')
     if json.loads(sc.read_text())!=meta:write_json(sc,meta)
     checks=compare(loaded,intent,'ezdxf '+ez.build)
     for row in checks:row.update(file=dest.relative_to(R).as_posix(),converter=None,self_read=False)
     assert all(x['status']=='same' for x in checks),(topic,version,[x for x in checks if x["status"]!="same"])
     rows.extend(checks);audits.append(dict(file=dest.relative_to(R).as_posix(),errors=0,fixes=0))
  print('Verified '+topic,flush=True)
 write_json(R/'results/features_checks.json',rows);write_json(R/'results/features_audits.json',audits)
 print(f'{len(audits)} files; {len(rows)} fields same; zero audit errors or fixes')
if __name__=='__main__':main()
