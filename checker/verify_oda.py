"""Check cross-set coverage, versions, sidecars and result-table attribution."""
from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from programs.adapters import VERSIONS,Ezdxf
from intent.validate import main as validate
validate()
rows=json.loads((R/'results/checks.json').read_text()); files={r['file'] for r in rows}
cross=R/'cross/ezdxf__oda';native=sorted((R/'native/ezdxf').glob('*.dxf'))
expected={cross/(p.stem+'.'+ext) for p in native for ext in ('dxf','dwg')}
actual={p for p in cross.iterdir() if p.suffix.lower() in ('.dxf','.dwg')}
assert actual==expected,(len(expected-actual),len(actual-expected))
for p in sorted(expected):
 meta=json.loads(p.with_suffix(p.suffix+'.provenance.json').read_text());rel=str(p.relative_to(R));matched=[r for r in rows if r['file']==rel]
 assert rel in files and matched,p
 assert all(r['self_read']==(p.suffix=='.dwg') for r in matched),p
 assert all(bool(r['converter'])==(p.suffix=='.dwg') for r in matched),p
 version=VERSIONS[meta['version']]
 if p.suffix=='.dxf':
  drawing=Ezdxf().open(p)
  assert drawing.dxfversion==version,p
  assert p.read_bytes().startswith(b'AutoCAD Binary DXF') == (meta['encoding']=='binary'),p
  props=drawing.rootdict.get('DWGPROPS')
  if props is not None and props.dxftype()=='XRECORD':
   assert all(t.value in ('','ZEV_OPERATOR') for t in props.tags if t.code==8),p
 else: assert p.read_bytes()[:6].decode('ascii')==version,p
print(f'{len(native)} native inputs, {len(expected)} cross files: sidecars, output versions, result coverage, and self-read flags verified.')
