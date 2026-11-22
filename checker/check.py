from pathlib import Path
import sys,json,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from programs.adapters import Ezdxf,Oda,BricsCad,VERSIONS
from checker.core import compare,digest
p=argparse.ArgumentParser();p.add_argument('drawing',type=Path);p.add_argument('--intent',type=Path);p.add_argument('--converter',choices=['oda','bricscad']);a=p.parse_args()
side=a.drawing.with_suffix(a.drawing.suffix+'.provenance.json')
intent=json.loads((a.intent if a.intent else ROOT/'intent'/(json.loads(side.read_text())['intent_id']+'.json')).read_text())
if a.drawing.suffix.lower()=='.dwg':
 if not a.converter:p.error('DWG requires --converter oda or bricscad')
 conv=Oda() if a.converter=='oda' else BricsCad();d=conv.read_dwg_many([a.drawing])[a.drawing]
 if isinstance(d,str):print(json.dumps({'status':'refused','detail':d}));sys.exit(2)
else:d=Ezdxf().open(a.drawing)
metadata=json.loads(side.read_text()) if side.exists() else {}
rows=compare(d,intent,'ezdxf '+Ezdxf.build,VERSIONS.get(metadata.get('version')) if a.drawing.suffix.lower()=='.dwg' else None)
writer=json.loads(side.read_text()).get('program') if side.exists() else None
for r in rows:
 r['converter']=((Oda.name+' '+Oda.build) if a.converter=='oda' else (BricsCad.name+' '+BricsCad.build)) if a.converter else None
 r['self_read']=bool(a.drawing.suffix.lower()=='.dwg' and a.converter=='oda' and writer==a.converter)
print(json.dumps({'content_digest':digest(d),'fields':rows},indent=2));sys.exit(int(any(r['status']!='same' for r in rows)))
