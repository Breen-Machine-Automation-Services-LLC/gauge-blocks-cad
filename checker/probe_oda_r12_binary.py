"""Exercise ODA's R12 binary-DXF output, which has no native binary input."""
from pathlib import Path
import json,sys,tempfile
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from programs.adapters import Oda,Ezdxf
from checker.core import compare,digest
with tempfile.TemporaryDirectory(dir=R/'results') as tmp:
 p=Path(tmp)/'out.dxf';oda=Oda();oda.save(R/'native/ezdxf/blocks_R12_ASCII.dxf',p,'DXF','R12','binary')
 d=Ezdxf().open(p);rows=compare(d,json.loads((R/'intent/background_blocks.json').read_text()),'ezdxf '+Ezdxf.build)
 assert p.read_bytes().startswith(b'AutoCAD Binary DXF') and d.dxfversion=='AC1009' and rows
 evidence={'build':oda.build,'format':'DXF','version':'R12','encoding':'binary','signature':'AutoCAD Binary DXF','fields_read':len(rows),'digest':digest(d),'audit_errors':len(d.audit().errors)}
 (R/'results/oda_r12_binary_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
