"""Effective order contracts; all drawings and SORTENTS tables are built in memory."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import ezdxf
from checker.core import compare

class DrawOrderTests(unittest.TestCase):
 def test_tables(self):
  for block in (False,True):
   for mode in ('absent','full','partial','reversed'):
    with self.subTest(block=block,mode=mode):
     d=ezdxf.new('R2018');space=d.blocks.new('I_SORTBLK') if block else d.modelspace()
     prefix='F131_sortents_block_' if block else 'F130_sortents_'
     entities=[space.add_solid([(0,0),(1,0),(1,1)],dxfattribs={'layer':prefix+x}) for x in 'abc']
     handles=[e.dxf.handle for e in entities]
     if mode=='full':space.set_redraw_order(zip(handles,handles))
     if mode=='partial':space.set_redraw_order([(handles[0],handles[0]),(handles[2],handles[2])])
     if mode=='reversed':space.set_redraw_order([(handles[0],handles[1]),(handles[1],handles[0])])
     # An unrelated entity must not affect the comparison.
     space.add_line((0,0),(1,1))
     f=dict(id=prefix+'a.redraw_order',value=[prefix+x for x in 'abc'],tolerance=0,versions=['AC1032'],selector=dict(kind='feature_attr',table='SOLID',name=prefix+'a',attr='redraw_order'))
     row=compare(d,dict(intent_id='test',expected=[f]),'test')[0]
     self.assertEqual(row['status'],'differs' if mode=='reversed' else 'same')
     self.assertEqual(len(row['detail']['literal_table']),{'absent':0,'full':3,'partial':2,'reversed':2}[mode])
     self.assertEqual(len(row['detail']['effective_space_order']),4)

if __name__=='__main__':unittest.main()
