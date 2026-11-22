"""Recomputed dimensions have explicit limits; point/rotation disagreement remains visible."""
from pathlib import Path
import json,math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ezdxf
from checker.core import compare,recomputed_fit_width
intent=json.loads((ROOT/'intent/feature_a_text.json').read_text())
fields=[f for f in intent['expected'] if f['id'] in ['F01_text_aligned.height','F01_text_aligned.alignment_rotation_error']]
doc=ezdxf.new('R2000');doc.layers.add('F01_text_aligned')
text=doc.modelspace().add_text('Invented text',dxfattribs=dict(layer='F01_text_aligned',height=3.0,halign=3,insert=(0,0),align_point=(30,4),rotation=math.degrees(math.atan2(4,30))))
assert all(r['status']=='same' for r in compare(doc,dict(intent,expected=fields),'test'))
text.dxf.height=3.5001
assert compare(doc,dict(intent,expected=fields),'test')[0]['status']=='differs'
text.dxf.height=3.0;text.dxf.rotation=0
rows=compare(doc,dict(intent,expected=fields),'test');assert rows[0]['status']=='same' and rows[1]['status']=='differs'
fit=next(f for f in intent['expected'] if f['id']=='F01_text_fit.width')
text.dxf.layer='F01_text_fit';doc.layers.add('F01_text_fit');text.dxf.halign=5;text.dxf.width=1.0
assert compare(doc,dict(intent,expected=[fit]),'test')[0]['status']=='same'
target=recomputed_fit_width(doc,fit['selector'])
text.dxf.width=target*1.2
assert compare(doc,dict(intent,expected=[fit]),'test')[0]['status']=='same'
text.dxf.width=target*1.4001
assert compare(doc,dict(intent,expected=[fit]),'test')[0]['status']=='differs'
print('Aligned height, recomputed Fit width, tolerance boundaries, and rotation disagreement pass')

# Verify every regenerated encoding and version, including R12 ATTRIB copies.
verified=0
for path in sorted((ROOT/'native/ezdxf').glob('a_text_*.dxf')):
 doc=ezdxf.readfile(path)
 entities=[e for e in doc.entitydb.values() if e.is_alive and e.dxftype() in ('TEXT','ATTDEF','ATTRIB') and e.dxf.layer.endswith(('_aligned','_fit'))]
 assert len(entities)==6,(path,len(entities))
 for e in entities:
  first,second=e.dxf.insert,e.dxf.align_point
  angle=math.degrees(math.atan2(second.y-first.y,second.x-first.x))
  assert abs((e.dxf.rotation-angle+180)%360-180)<1e-8,(path,e.dxf.layer)
  assert e.dxf.height==2.5 and e.dxf.width==1,(path,e.dxf.layer)
  assert e.dxf.halign==(3 if e.dxf.layer.endswith('_aligned') else 5)
  verified+=1
assert verified==78
print('78 native Aligned/Fit TEXT, ATTDEF, and ATTRIB entities retain authored dimensions and consistent rotation')
