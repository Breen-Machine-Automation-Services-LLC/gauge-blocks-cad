"""Coverage derives from real native files, writable pairs, and measurements."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('coverage_builder',ROOT/'map/build.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
from map.check_links import page_data

with tempfile.TemporaryDirectory(prefix='cad-coverage-') as tmp:
    root=Path(tmp)
    for directory in ['intent','native/ezdxf','cross/ezdxf__cadcraft','results','programs','map']:
        (root/directory).mkdir(parents=True)
    (root/'map/template.html').write_text((ROOT/'map/template.html').read_text())
    caps={'ezdxf':dict(name='ezdxf',versions=['2000'],formats={'DXF':['ASCII','binary']}),
          'cadcraft':dict(name='CADCraft',versions=['2000'],formats={'DXF':['ASCII']})}
    for c in caps.values(): c['outputs']=[[fmt,v,enc] for fmt,encs in c['formats'].items() for v in c['versions'] for enc in encs]
    (root/'programs/capabilities.json').write_text(json.dumps(caps))
    (root/'programs/pairs.json').write_text(json.dumps([dict(writer='ezdxf',resaver='cadcraft',sources='native/ezdxf'),dict(writer='cadcraft',resaver='ezdxf',sources='cross/dwg_sources')]))
    for name,encoding,measured in [('complete','ASCII',True),('missing','ASCII',False),('gap','binary',False)]:
        intent=dict(intent_id=name,title=name,description='Invented coverage fixture',representation_id='reference_1',features=['geometry'],expected=[dict(id='value',value=1,versions=['AC1009','AC1015'])])
        (root/'intent'/f'{name}.json').write_text(json.dumps(intent))
        native=f'native/ezdxf/{name}.dxf';(root/native).write_text('fixture')
        meta=dict(intent_id=name,program='ezdxf',build='test',format='DXF',version='2000',encoding=encoding,content_digest=name)
        (root/(native+'.provenance.json')).write_text(json.dumps(meta))
        if measured:
            target=f'cross/ezdxf__cadcraft/{name}.dxf';(root/target).write_text('fixture')
            output=dict(meta,program='cadcraft',content_digest='output',made_by={'input_digest':name})
            (root/(target+'.provenance.json')).write_text(json.dumps(output))
            (root/'results/checks.json').write_text(json.dumps([dict(file=target,field='value',status='same')]))
    # An undeclared reverse pair from native/cadcraft must not be expected.
    (root/'native/cadcraft').mkdir()
    (root/'native/cadcraft/complete.dxf').write_text('fixture')
    (root/'native/cadcraft/complete.dxf.provenance.json').write_text(json.dumps(dict(meta,intent_id='complete',program='cadcraft',encoding='ASCII')))
    # A DWG source exists only in a declared cross folder, with no native DWG.
    caps['ezdxf']['outputs'].append(['DWG','2000','binary'])
    (root/'programs/capabilities.json').write_text(json.dumps(caps))
    dwg=dict(meta,intent_id='complete',program='cadcraft',format='DWG',encoding='binary')
    (root/'cross/dwg_sources').mkdir()
    target='cross/dwg_sources/complete.dwg'
    (root/target).write_text('fixture')
    (root/(target+'.provenance.json')).write_text(json.dumps(dwg))
    builder.ROOT=root
    with contextlib.redirect_stdout(io.StringIO()):builder.main()
    data=page_data((root/'map/index.html').read_text())
    def cell(name,encoding):
        topic=next(t for t in data['topics'] if t['id']==name)
        return topic['features'][0]['cells'][data['columns'].index(['DXF','2000',encoding])]
    assert cell('complete','ASCII')['coverage']=='covered'
    no_source=next(t for t in data['topics'] if t['id']=='complete')['features'][0]['cells'][data['columns'].index(['DXF','R12','binary'])]
    assert no_source['coverage']=='no source'
    missing=cell('missing','ASCII');assert missing['coverage']=='partial'
    assert missing['missing']==['not yet run: ezdxf to CADCraft']
    topic=next(t for t in data['topics'] if t['id']=='complete')
    dwg=topic['features'][0]['cells'][data['columns'].index(['DWG','2000','binary'])]
    assert dwg['coverage']=='partial' and dwg['missing']==['not yet run: CADCraft to ezdxf']
    gap=cell('gap','binary');assert gap['coverage']=='covered'
    assert gap['impossible']==[builder.gap_reason(root, 'cadcraft', 'DXF', '2000', 'binary')]
print('Synthetic complete, missing-pair, and capability-gap coverage pass')
