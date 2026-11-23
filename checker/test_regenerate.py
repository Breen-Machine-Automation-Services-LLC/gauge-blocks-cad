"""Limited dry runs list skipped BricsCAD outputs without launching programs or writing files."""
from pathlib import Path
import contextlib,io,json,sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import regenerate
from generators.run_cross import jobs_for
from programs.adapters import ADAPTERS

def forbidden(*args,**kwargs):
 raise AssertionError('Dry run attempted a program operation')
with contextlib.ExitStack() as stack:
 for adapter in ADAPTERS.values():
  stack.enter_context(patch.object(adapter,'__init__',forbidden))
 stack.enter_context(patch('subprocess.run',forbidden))
 stack.enter_context(patch.object(Path,'write_text',forbidden))
 stack.enter_context(patch.object(Path,'write_bytes',forbidden))
 stack.enter_context(patch.object(Path,'mkdir',forbidden))
 stack.enter_context(patch.object(Path,'replace',forbidden))
 stack.enter_context(patch.object(sys,'argv',['regenerate.py','--pairs','ezdxf__bricscad,oda__bricscad','--intent','feature_a_text','--dry-run']))
 out=io.StringIO()
 with contextlib.redirect_stdout(out):regenerate.main()
lines=out.getvalue().splitlines()
skipped=[line for line in lines if line.startswith('Skipped BricsCAD ')]
assert len(skipped)==52,len(skipped)
assert any(line.startswith('native: ') and 'resave' in line and 'rescore' in line for line in lines)
for pair in ['ezdxf__bricscad','oda__bricscad']:
 jobs=jobs_for(pair,intent='feature_a_text')
 assert len(jobs)==26
 for src,dest,*_,side in jobs:
  assert side['intent_id']=='feature_a_text'
  assert any(line == 'Skipped BricsCAD '+dest.relative_to(ROOT).as_posix() for line in lines)
assert 'native Aligned text' not in (ROOT/'OPEN-ITEMS.md').read_text()
print('52 BricsCAD targets skipped and listed with no adapter construction, subprocess, or filesystem writes')
