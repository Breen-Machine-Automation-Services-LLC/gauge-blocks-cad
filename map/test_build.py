"""Regression: a refused conversion without an output sidecar is still a run."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('map_builder',ROOT/'map/build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
from map.check_links import page_data

with tempfile.TemporaryDirectory(prefix='cad-map-refusal-') as folder:
    root = Path(folder)
    for name in ('intent','native/ezdxf','cross','results','map','programs'):
        (root/name).mkdir(parents=True)
    for name in ('intent/background_blocks.json','native/ezdxf/blocks_2000_ASCII.dxf.provenance.json','native/ezdxf/blocks_2000_ASCII.dxf','map/template.html','programs/capabilities.json','programs/pairs.json'):
        (root/name).write_bytes((ROOT/name).read_bytes())
    refused = 'cross/ezdxf__oda/blocks_2000_ASCII.dwg'
    (root/'results/checks.json').write_text(json.dumps([dict(file=refused,intent_id='background_blocks',status='refused',reader='test reader',actual='File would not open')]))
    builder.ROOT = root
    with contextlib.redirect_stdout(io.StringIO()):
        builder.main()
    page = (root/'map/index.html').read_text()
    data = page_data(page)
    column = data['columns'].index(['DWG','2000','binary'])
    cell = data['topics'][0]['features'][0]['cells'][column]
    assert cell['coverage']=='planned', cell
    assert cell['runs'][0]['status']=='refused', cell
    assert cell['runs'][0]['unavailable'] is True
    assert cell['runs'][0]['inputs']==['native/ezdxf/blocks_2000_ASCII.dxf']
    assert cell['files']==[]
(ROOT/'map/build-checks.json').write_text(json.dumps(dict(refusal_without_output_sidecar='pass',coverage_does_not_claim_unavailable_output='pass',input_provenance='pass'),indent=2)+'\n')
print('Refusal without output: status, provenance, and coverage pass')
