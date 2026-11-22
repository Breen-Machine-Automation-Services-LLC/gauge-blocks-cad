from pathlib import Path
import sys,json,tempfile,time,difflib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import ezdxf
from generators.background import build
from checker.core import digest
out=[]
with tempfile.TemporaryDirectory(dir=R/'results') as tmp:
 for v in ['2000','2004','2007','2010','2013','2018','R12']:
  for fmt in ['asc','bin'] if v!='R12' else ['asc']:
   d=build('metadata',v);p=Path(tmp)/'a.dxf';q=Path(tmp)/'b.dxf';d.saveas(p,fmt=fmt);time.sleep(1.05);d.saveas(q,fmt=fmt)
   a=ezdxf.readfile(p);b=ezdxf.readfile(q)
   changes={k:[str(a.header.get(k)),str(b.header.get(k))] for k in a.header.varnames() if a.header.get(k)!=b.header.get(k)}
   eq=digest(a)==digest(b);e=next(iter(b.modelspace()));e.dxf.location=(9,2,0);changed=digest(a)!=digest(b)
   from ezdxf.lldxf.tagwriter import TagCollector
   fresh=ezdxf.readfile(q)
   aa={e.dxf.handle:[list(t) for t in TagCollector.dxftags(e,dxfversion='AC1032')] for e in a.entitydb.values() if e.is_alive}
   bb={e.dxf.handle:[list(t) for t in TagCollector.dxftags(e,dxfversion='AC1032')] for e in fresh.entitydb.values() if e.is_alive}
   entity_changes=[{'handle':h,'before':t,'after':bb.get(h)} for h,t in aa.items() if t!=bb.get(h)]
   out.append({'entity_changes':entity_changes,'version':v,'encoding':fmt,'equal':eq,'one_field_changes_digest':changed,'header_changes':changes})
(R/'results/digest_evidence.json').write_text(json.dumps(out,indent=2)+'\n');print(f'{len(out)} two-save equality and one-field sensitivity cases completed.');assert all(x['equal'] and x['one_field_changes_digest'] for x in out)
