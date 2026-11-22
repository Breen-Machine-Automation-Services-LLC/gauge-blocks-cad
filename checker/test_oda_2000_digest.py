from pathlib import Path
import sys,json,tempfile,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from programs.adapters import Oda,Ezdxf
from checker.core import digest
from ezdxf.lldxf.tagwriter import TagCollector
o=Oda(); ez=Ezdxf(); source=R/'native/ezdxf/metadata_2000_ASCII.dxf'
with tempfile.TemporaryDirectory(dir=R/'results') as tmp:
 a=Path(tmp)/'a.dxf'; b=Path(tmp)/'b.dxf'
 o.save(source,a,'DXF','2000','ASCII');time.sleep(2);o.save(source,b,'DXF','2000','ASCII')
 x=ez.open(a);y=ez.open(b)
 headers={k:[str(x.header.get(k)),str(y.header.get(k))] for k in x.header.varnames() if x.header.get(k)!=y.header.get(k)}
 def tags(d):return {e.dxf.handle:[list(t) for t in TagCollector.dxftags(e,dxfversion='AC1032')] for e in d.entitydb.values() if e.is_alive}
 aa=tags(x);bb=tags(y); changes={h:[aa.get(h),bb.get(h)] for h in aa.keys()|bb.keys() if aa.get(h)!=bb.get(h)}
 equal=digest(x)==digest(y);next(iter(y.modelspace())).dxf.location=(9,2,0);sensitive=digest(x)!=digest(y)
 evidence={'build':o.build,'input':str(source.relative_to(R)),'header_changes':headers,'entity_changes':changes,'equal':equal,'one_field_changes_digest':sensitive}
 (R/'results/oda_2000_digest_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2));assert equal and sensitive
