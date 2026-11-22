"""Verify native feature regeneration preserves bytes and modification times."""
from pathlib import Path
import hashlib,json,subprocess,sys
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from programs.settings import SETTINGS
paths=[p for p in (R/'native/ezdxf').glob('*') if p.is_file() and (p.suffix=='.dxf' or p.name.endswith('.dxf.provenance.json'))]
def state():return {p.relative_to(R).as_posix():(p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
before=state();subprocess.run([SETTINGS['python'],'-I',str(R/'generators/run_features.py')],check=True,cwd=R);assert state()==before,'Stable drawing or sidecar changed'
(R/'results/feature_stability.json').write_text(json.dumps(dict(files=len(paths),bytes_and_mtimes_preserved=True),indent=2)+'\n');print(len(paths),'drawing and sidecar bytes and mtimes preserved')
