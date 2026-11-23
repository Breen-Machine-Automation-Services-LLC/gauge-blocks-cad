"""Run the BricsCAD-authored generators (tables, regions and solids), publish native/bricscad and check it.

Each topic is built in a fresh BricsCAD session (see generators/bricscad/make_bricscad_masters.lsp) and saved at every
format, version and encoding BricsCAD can write. DXF is read directly with ezdxf. DWG is read through ODA File
Converter, a shared-engine reader of BricsCAD-written DWG (BricsCAD itself uses ODA libraries; see CAPABILITIES.md).
A file is rewritten only when its content digest or the writer build changes. Run from the repository root:
python -I generators/run_bricscad.py. Foreground only; it does not commit or push.
"""
from pathlib import Path
import sys, json, hashlib, shutil, collections, re
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import digest, compare
from programs import privacy
from programs.adapters import BricsCad, Oda, VERSIONS, workdir
from programs.bricscad_batch import run_script
from regenerate import sidecar, publish, write_json

TOPICS = {'k_tables': 'future_k_tables', 'k_regions_solids': 'future_k_regions_solids'}
LSP = R / 'generators/bricscad/make_bricscad_masters.lsp'
NAME = re.compile(r'^(k_tables|k_regions_solids)_(R12|2000|2004|2007|2010|2013|2018)_(ASCII|binary)\.(dxf|dwg)$')


def observe(doc):
    seen = collections.Counter()
    for e in doc.modelspace():
        layer = next((t.value for t in TagCollector.dxftags(e) if t.code == 8), None)
        seen[f'{e.dxftype()} on {layer if layer is not None else e.dxf.get("layer", "?")}'] += 1
    return dict(seen)


def main(intent_id=None, force=False):
    bc, oda = BricsCad(), Oda(); rows = []; written = []
    observation_path=R/'results/native_bricscad_observations.json'
    saved=json.loads(observation_path.read_text()) if observation_path.exists() else {}
    observations=saved.get('modelspace_entities_by_file',{});steps=saved.get('generator_steps',{})
    selected_intent = intent_id
    previous_rows = load_rows(R/'results/native_bricscad_checks.json')
    if selected_intent:
        rows = [r for r in previous_rows if r['intent_id'] != selected_intent]
    carried_count = len(rows)
    for topic, intent_id in TOPICS.items():
        if selected_intent and intent_id != selected_intent:
            continue
        intent = json.loads((R / 'intent' / (intent_id + '.json')).read_text())
        input_digest = native_input(R,intent_id,'bricscad',Path(__file__),LSP)[0]
        existing=sorted((R/'native/bricscad').glob(topic+'_*.provenance.json'))
        previous=load_rows(R/'results/native_bricscad_checks.json')
        if existing:
            complete=all(json.loads(p.read_text()).get('build')==bc.build and json.loads(p.read_text()).get('made_by',{}).get('input_digest')==input_digest and Path(str(p).removesuffix('.provenance.json')).exists() for p in existing)
            if complete and not force:
                paths=[Path(str(p).removesuffix('.provenance.json')) for p in existing]
                for dest in paths:
                    rel=dest.relative_to(R).as_posix();old=[row for row in previous if row['file']==rel]
                    if current(old,R,intent_id):rows.extend(old);continue
                    dwg=dest.suffix=='.dwg'
                    doc=oda.read_dwg_many([dest])[dest] if dwg else ezdxf.readfile(dest)
                    if isinstance(doc,str):
                        checks=[dict(intent_id=intent_id,field='open',reader='ezdxf '+ezdxf.__version__,status='refused',expected=None,actual=None,tolerance=0,detail=doc)]
                    else:
                        version=NAME.match(dest.name).group(2)
                        checks=compare(doc,intent,'ezdxf '+ezdxf.__version__,VERSIONS[version] if dwg else None)
                    for row in checks:row.update(file=rel,converter='oda '+oda.build if dwg else None,self_read=False)
                    rows.extend(checks)
                    if not dwg and dest.name.endswith('_binary.dxf'):
                        conversion=Path(workdir('bricscad-bin-'))
                        try:
                            target=conversion/dest.name
                            version=NAME.match(dest.name).group(2)
                            status=oda.save_many([(dest,target,'DXF',version,'ASCII')])[target]
                            if status is None:
                                secondary=compare(ezdxf.readfile(target),intent,'ezdxf '+ezdxf.__version__)
                            else:
                                secondary=[dict(intent_id=intent_id,field='open',reader='ezdxf '+ezdxf.__version__,status='refused',expected=None,actual=None,tolerance=0,detail=status)]
                            for row in secondary:row.update(file=rel,converter='oda '+oda.build+' (binary DXF to ASCII DXF)',self_read=False)
                            rows.extend(secondary)
                        finally:
                            shutil.rmtree(conversion,ignore_errors=True)
                continue
        work = Path(workdir('bricscad-gen-')); out = work / 'out'; out.mkdir()
        try:
            script = ('(setvar "FILEDIA" 0)\n(setvar "CMDECHO" 0)\n'
                      f'(setq *out-dir* "{out}/")\n(setq *topic* "{topic}")\n(load "{LSP}")\n(mk-run)\n_.QUIT _Y\n')
            rc = run_script(script, work / 'run', 'gen', 600)
            if rc != 0:
                raise RuntimeError(f'BricsCAD generator for {topic} exited {rc}')
            log = (out / 'make_bricscad_masters.log').read_text().replace(str(out), '<out>')
            steps[topic] = [ln for ln in log.splitlines() if ln.strip() and not ln.startswith('((-1')]
            files = sorted(p for p in out.iterdir() if NAME.match(p.name))
            dwgs = [p for p in files if p.suffix == '.dwg']
            read_dwg = oda.read_dwg_many(dwgs)
            # Second reader for binary DXF: ODA rewrites it as ASCII DXF at the same version, then ezdxf reads that.
            bins = [p for p in files if p.suffix == '.dxf' and p.name.endswith('_binary.dxf')]
            conv = Path(workdir('bricscad-bin-')); jobs = [(p, conv / p.name, 'DXF', NAME.match(p.name).group(2), 'ASCII') for p in bins]
            try:
                status = oda.save_many(jobs); second = {}
                for p, dest, *_ in jobs:
                    second[p.name] = ezdxf.readfile(dest) if status[dest] is None else status[dest]
            finally:
                shutil.rmtree(conv, ignore_errors=True)
            for p in files:
                m = NAME.match(p.name); version, encoding, fmt = m.group(2), m.group(3), m.group(4).upper()
                privacy.assert_clean(p)
                if fmt == 'DXF':
                    doc = ezdxf.readfile(p); converter = None
                else:
                    doc = read_dwg[p]
                    if isinstance(doc, str):
                        rows.append(dict(file=f'native/bricscad/{p.name}', intent_id=intent['intent_id'], field='open', reader='oda ' + oda.build, converter=None,
                                         self_read=False, status='refused', expected=None, actual=None, tolerance=0, detail=doc)); continue
                    converter = 'oda ' + oda.build
                dest = R / 'native/bricscad' / p.name
                meta = sidecar(dest, doc, intent, bc, version, 'binary' if fmt == 'DWG' else encoding, input_digest)
                meta['ezdxf_based'] = False; meta['made_by']['script'] = 'generators/run_bricscad.py'
                if fmt == 'DWG':
                    meta['digest_reader'] = converter
                before = dest.exists(); publish(p, dest, meta, force=force); written.append(dest.name)
                if dest.exists() and json.loads(dest.with_suffix(dest.suffix + '.provenance.json').read_text()).get('content_digest') != meta['content_digest']:
                    raise RuntimeError('sidecar digest mismatch ' + p.name)
                observations[p.name] = observe(doc)
                if p.name in second:
                    d2 = second[p.name]
                    if isinstance(d2, str):
                        rows.append(dict(file=f'native/bricscad/{p.name}', intent_id=intent['intent_id'], field='open', reader='ezdxf ' + ezdxf.__version__, converter='oda ' + oda.build + ' (binary DXF to ASCII DXF)',
                                         self_read=False, status='refused', expected=None, actual=None, tolerance=0, detail=d2))
                    else:
                        for row in compare(d2, intent, 'ezdxf ' + ezdxf.__version__):
                            row.update(file=f'native/bricscad/{p.name}', converter='oda ' + oda.build + ' (binary DXF to ASCII DXF)', self_read=False); rows.append(row)
                reader = 'ezdxf ' + ezdxf.__version__
                for row in compare(doc, intent, reader, VERSIONS[version] if fmt == 'DWG' else None):
                    row.update(file=f'native/bricscad/{p.name}', converter=converter, self_read=False); rows.append(row)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    for row in rows[carried_count:]:
        annotate([row],R,row['intent_id'],'bricscad','oda' if row.get('converter') or row['file'].endswith('.dwg') else 'ezdxf')
    write_json(R / 'results/native_bricscad_checks.json', rows)
    if not written and observation_path.exists():
        return
    write_json(R / 'results/native_bricscad_observations.json', {'generator_steps': steps, 'modelspace_entities_by_file': observations})
    counts = collections.Counter(r['status'] for r in rows)
    print(f'{len(written)} native BricsCAD files; rows {dict(counts)}')


if __name__ == '__main__':
    main()
