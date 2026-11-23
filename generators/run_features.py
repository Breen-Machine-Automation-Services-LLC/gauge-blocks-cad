"""Generate and verify feature DXFs without launching proprietary programs."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from generators.features import TOPICS,build
from programs.adapters import Ezdxf,VERSIONS
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import encoding_intent, compare
from regenerate import sidecar,publish,write_json
import tempfile

def _jobs(intent_id, root):
 jobs=[]
 for topic in sorted(TOPICS):
  iid='feature_'+topic
  if intent_id and iid!=intent_id:continue
  inp,cases=native_input(root,iid,versions=VERSIONS)
  for version,enc in cases:
   jobs.append((iid,topic,version,enc,inp,root/'native/ezdxf'/f'{topic}_{version}_{enc}.dxf'))
 return jobs

def plan(intent_id=None, force=False, root=None):
 from checker.scoring import native_plan
 root=R if root is None else Path(root)
 return native_plan(_jobs(intent_id,root),root,force,Ezdxf.build,root/'results/features_checks.json',current)

def main(intent_id=None, force=False, root=None):
 from checker.scoring import record_score
 root=R if root is None else Path(root)
 work=plan(intent_id,force,root);ez=Ezdxf()
 path=root/'results/features_checks.json';previous=load_rows(path)
 selected=set(sum(work.values(),[]))
 rows=[r for r in previous if r['file'] not in selected]
 audits=load_rows(root/'results/features_audits.json')
 for iid,topic,version,encoding,inp,dest in _jobs(intent_id,root):
  rel=dest.relative_to(root).as_posix()
  if rel in work['carried']:
   rows.extend(r for r in previous if r['file']==rel);continue
  intent=json.loads((root/'intent'/f'{iid}.json').read_text())
  errors=fixes=0
  if rel in work['rescore']:
   checks=compare(ez.open(dest), encoding_intent(intent, encoding), 'ezdxf '+ez.build, None)
  else:
   d=build(topic,version)
   with tempfile.TemporaryDirectory(dir=root/'results') as td:
    tmp=Path(td)/'drawing.dxf';ez.save(d,tmp,'DXF',version,encoding);loaded=ez.open(tmp)
    meta=sidecar(dest,loaded,intent,ez,version,encoding,inp)
    checks=compare(loaded, encoding_intent(intent, encoding), 'ezdxf '+ez.build, None)
    audit=loaded.audit();errors=len(audit.errors);fixes=len(audit.fixes)
    assert not errors and not fixes,(topic,version,audit.errors,audit.fixes)
    meta['made_by']['script']='generators/run_features.py';publish(tmp,dest,meta,force=force)
  for row in checks:row.update(file=rel,converter=None,self_read=False)
  assert all(x['status']=='same' for x in checks),(topic,version,checks)
  annotate(checks,root,iid,'ezdxf','ezdxf');rows.extend(checks)
  record_score(checks,root,iid,path,rel)
  audits=[a for a in audits if a.get('file')!=rel];audits.append(dict(file=rel,errors=errors,fixes=fixes))
 write_json(path,rows);write_json(root/'results/features_audits.json',audits)
if __name__=='__main__':main()
