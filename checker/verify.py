"""Validate every checked-in drawing, digest sensitivity, and regeneration stability."""
import sys,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import ezdxf
from checker.core import compare,digest
from intent.validate import main as validate
def check_natives():
 counts={};baselines={}
 for p in sorted((R/'native').rglob('*.dxf')):
  writer=p.relative_to(R/'native').parts[0]
  side=json.loads(p.with_suffix('.dxf.provenance.json').read_text());d=ezdxf.readfile(p)
  # Audit can repair the in-memory drawing, so check the loaded digest first.
  assert digest(d)==side['content_digest'],p
  assert not d.audit().errors,p
  i=json.loads((R/'intent'/(side['intent_id']+'.json')).read_text())
  rows=compare(d,i,'ezdxf 1.4.4')
  if writer=='ezdxf':
   for row in rows:assert row['status']=='same',f"{p}: {row['field']}"
  else:
   result=R/'results'/f'native_{writer}_checks.json'
   assert result.is_file(),f'{p}: field <results file> missing: {result}'
   if writer not in baselines:baselines[writer]=json.loads(result.read_text())
   recorded=[x for x in baselines[writer] if x['file']==p.relative_to(R).as_posix() and x['converter'] is None]
   def fields(items):
    out={}
    for x in items:
     field=x['field'];assert field not in out,f'{p}: {field} duplicated'
     out[field]={k:x[k] for k in ('field','status','expected','actual')}
    return out
   actual,expected=fields(rows),fields(recorded)
   for field in sorted(actual.keys() | expected.keys()):
    assert actual.get(field)==expected.get(field),f'{p}: {field} differs from recorded result'
  counts[writer]=counts.get(writer,0)+1
 return counts

if __name__ == '__main__':
 from programs.settings import SETTINGS
 validate();counts=check_natives();count=sum(counts.values())
 # Exercise all three result states and absolute tolerance independently.
 i=json.loads((R/'intent/background_layers.json').read_text())
 d=ezdxf.readfile(R/'native/ezdxf/layers_2018_ASCII.dxf')
 d.layers.get('ZEV_001').dxf.color=7
 d.layers.remove('ZEV_099')
 rs={x['field']:x for x in compare(d,i,'ezdxf 1.4.4')}
 assert rs['ZEV_001.color']['status']=='differs'
 assert rs['ZEV_001.color']['expected']==2 and rs['ZEV_001.color']['actual']==7
 assert rs['ZEV_099.color']['status']=='absent'
 assert rs['ZEV_002.color']['status']=='same'
 from checker.core import equal
 assert equal([1.0,2.0],[1.0+1e-10,2.0],1e-9)
 assert not equal(1.0,1.1,1e-9)
 paths=[p for root in ['native','cross'] for p in (R/root).rglob('*') if p.is_file()]
 before={str(p):[p.stat().st_mtime_ns,p.read_bytes()] for p in paths}
 subprocess.run([SETTINGS['python'],'-I',str(R/'regenerate.py')],check=True,cwd=R)
 assert all([Path(p).stat().st_mtime_ns,Path(p).read_bytes()]==v for p,v in before.items()),'Regeneration rewrote stable files'
 (R/'results/verification.json').write_text(json.dumps({'drawings':count,'drawings_by_writer':counts,'audits':'pass','expected_fields':'ezdxf: same; other writers: recorded results','sidecar_digests':'pass','unchanged_regeneration':'bytes and mtimes preserved'},indent=2)+'\n')
 print(f'{count} drawings verified; regeneration preserved every drawing and sidecar byte and mtime.')
