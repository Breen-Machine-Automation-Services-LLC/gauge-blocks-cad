"""Validate every checked-in drawing, digest sensitivity, and regeneration stability."""
import sys,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from programs.settings import SETTINGS
import ezdxf
from checker.core import compare,digest
from intent.validate import main as validate
validate();count=0
for p in sorted((R/'native').rglob('*.dxf')):
 side=json.loads(p.with_suffix('.dxf.provenance.json').read_text());d=ezdxf.readfile(p)
 assert not d.audit().errors,p
 assert digest(d)==side['content_digest'],p
 i=json.loads((R/'intent'/(side['intent_id']+'.json')).read_text())
 assert all(x['status']=='same' for x in compare(d,i,'ezdxf 1.4.4')),p
 count+=1
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
(R/'results/verification.json').write_text(json.dumps({'drawings':count,'audits':'pass','all_expected_fields':'same','sidecar_digests':'pass','unchanged_regeneration':'bytes and mtimes preserved'},indent=2)+'\n')
print(f'{count} drawings verified; regeneration preserved every drawing and sidecar byte and mtime.')
