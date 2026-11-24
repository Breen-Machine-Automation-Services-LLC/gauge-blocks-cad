"""Run the BricsCAD-authored generators (tables, regions and solids), publish native/bricscad and check it.

Each topic is built in a fresh BricsCAD session (see generators/bricscad/make_bricscad_masters.lsp) and saved at every
format, version and encoding BricsCAD can write. DXF is read directly with ezdxf. DWG is read through ODA File
Converter, a shared-engine reader of BricsCAD-written DWG (BricsCAD itself uses ODA libraries; see CAPABILITIES.md).
A stale drawing input or missing output rebuilds its topic; current files are only re-scored when needed. Run from the repository root:
python -I generators/run_bricscad.py. Foreground only; it does not commit or push.
"""
from pathlib import Path
import sys, json, hashlib, shutil, collections, re
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from checker.scoring import annotate, current, load_rows, native_input
from checker.core import encoding_intent, digest, compare
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


def _outputs(root, topic):
    # Existing manifests retain the measured output formats; first runs use the save matrix.
    sides=list((root/'native/bricscad').glob(topic+'_*.provenance.json'))
    formats={(json.loads(p.read_text()).get('format'),json.loads(p.read_text()).get('encoding')) for p in sides}
    if hasattr(BricsCad,'TYPES') or not formats:
        formats={('DXF','ASCII'),('DXF','binary'),('DWG','binary')}
    formats.add(('DXF','ASCII'))
    return sorted(root/'native/bricscad'/f'{topic}_{v}_{enc}.{fmt.lower()}'
                  for v in VERSIONS for fmt,enc in formats if fmt!='DWG' or v!='R12')


def plan(intent_id=None, force=False, root=None):
    from checker.scoring import empty_plan, file_current
    root=R if root is None else Path(root)
    work=empty_plan();path=root/'results/native_bricscad_checks.json';previous=load_rows(path)
    for topic,iid in TOPICS.items():
        if intent_id and iid!=intent_id:continue
        if not (root/'intent'/f'{iid}.json').exists():continue
        inp=native_input(root,iid,'bricscad',Path(__file__),LSP)[0]
        paths=_outputs(root,topic)
        def stale(dest):
            sc=dest.with_suffix(dest.suffix+'.provenance.json')
            old=json.loads(sc.read_text()) if sc.exists() else {}
            rows=[r for r in previous if r['file']==dest.relative_to(root).as_posix()]
            if (bool(rows) and all(r.get('status') == 'refused' for r in rows) and current(rows,root,iid,inp,BricsCad.build)):return False
            return not dest.exists() or old.get('build')!=BricsCad.build or old.get('made_by',{}).get('input_digest')!=inp
        rebuild=force or any(stale(p) for p in paths)
        for dest in paths:
            rel=dest.relative_to(root).as_posix();rows=[r for r in previous if r['file']==rel]
            kind='resave' if rebuild else 'carried' if ((bool(rows) and all(r.get('status') == 'refused' for r in rows) and current(rows,root,iid,inp,BricsCad.build)) or file_current(rows,root,iid,path,rel,current)) else 'rescore'
            work[kind].append(rel)
    return work


def main(intent_id=None, force=False, root=None):
    from checker.scoring import record_score, stamp_refusal
    root=R if root is None else Path(root)
    work_plan=plan(intent_id,force,root)
    bc, oda = BricsCad(), Oda(); rows = []; written = []
    observation_path=root/'results/native_bricscad_observations.json'
    saved=json.loads(observation_path.read_text()) if observation_path.exists() else {}
    observations=saved.get('modelspace_entities_by_file',{});steps=saved.get('generator_steps',{})
    selected_intent = intent_id
    previous_rows = load_rows(root/'results/native_bricscad_checks.json')
    if selected_intent:
        rows = [r for r in previous_rows if r['intent_id'] != selected_intent]
    carried_count = len(rows)
    for topic, intent_id in TOPICS.items():
        if selected_intent and intent_id != selected_intent:
            continue
        intent = json.loads((root / 'intent' / (intent_id + '.json')).read_text())
        input_digest = native_input(root,intent_id,'bricscad',Path(__file__),LSP)[0]
        paths=_outputs(root,topic)
        if not any(p.relative_to(root).as_posix() in work_plan['resave'] for p in paths):
            for dest in paths:
                rel=dest.relative_to(root).as_posix();old=[row for row in previous_rows if row['file']==rel]
                if rel in work_plan['carried']:rows.extend(old);continue
                dwg=dest.suffix=='.dwg'
                doc=oda.read_dwg_many([dest])[dest] if dwg else ezdxf.readfile(dest)
                if isinstance(doc,str):
                    checks=[dict(intent_id=intent_id,field='open',reader='ezdxf '+ezdxf.__version__,status='refused',expected=None,actual=None,tolerance=0,detail=doc)]
                else:
                    version=NAME.match(dest.name).group(2)
                    checks=compare(doc, encoding_intent(intent, 'binary' if dwg else NAME.match(dest.name).group(3)), 'ezdxf '+ezdxf.__version__, VERSIONS[version] if dwg else None)
                for row in checks:row.update(file=rel,converter='oda '+oda.build if dwg else None,self_read=False)
                rows.extend(checks)
                record_score(checks,root,intent_id,root/'results/native_bricscad_checks.json',rel)
                if not dwg and dest.name.endswith('_binary.dxf'):
                    conversion=Path(workdir('bricscad-bin-'))
                    try:
                        target=conversion/dest.name
                        version=NAME.match(dest.name).group(2)
                        status=oda.save_many([(dest,target,'DXF',version,'ASCII')])[target]
                        if status is None:
                            secondary=compare(ezdxf.readfile(target), encoding_intent(intent, 'binary'), 'ezdxf '+ezdxf.__version__, None)
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
            files = [p for p in files if (root/'native/bricscad'/p.name).relative_to(root).as_posix() in work_plan['resave']]
            expected={Path(rel).name for rel in work_plan['resave'] if Path(rel).name.startswith(topic+'_')}
            for name in sorted(expected-{p.name for p in files}):
                rel = f'native/bricscad/{name}'
                checks = [dict(file=rel, intent_id=intent_id, field='open',
                               reader=f'{bc.name} {bc.build}', converter=None, self_read=False,
                               status='refused', expected=None, actual=None, tolerance=0,
                               detail='BricsCAD produced no output')]
                record_score(checks,root,intent_id,root/'results/native_bricscad_checks.json',rel)
                rows.extend(checks)
                observations.pop(name, None)
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
                dest = root / 'native/bricscad' / p.name
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
                        for row in compare(d2, encoding_intent(intent, encoding), 'ezdxf ' + ezdxf.__version__, None):
                            row.update(file=f'native/bricscad/{p.name}', converter='oda ' + oda.build + ' (binary DXF to ASCII DXF)', self_read=False); rows.append(row)
                reader = 'ezdxf ' + ezdxf.__version__
                checks=compare(doc, encoding_intent(intent, 'binary' if fmt == 'DWG' else encoding), reader, VERSIONS[version] if fmt == 'DWG' else None)
                record_score(checks,root,intent_id,root/'results/native_bricscad_checks.json',dest.relative_to(root).as_posix())
                for row in checks:
                    row.update(file=f'native/bricscad/{p.name}', converter=converter, self_read=False); rows.append(row)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    refusal_inputs={iid:native_input(root,iid,'bricscad',Path(__file__),LSP)[0]
                    for iid in {r['intent_id'] for r in rows[carried_count:] if r['status']=='refused'}}
    for row in rows[carried_count:]:
        if row['status']=='refused':
            stamp_refusal([row],refusal_inputs[row['intent_id']],bc.build)
        annotate([row],root,row['intent_id'],'bricscad','oda' if row.get('converter') or row['file'].endswith('.dwg') else 'ezdxf')
    write_json(root / 'results/native_bricscad_checks.json', rows)
    if not written and observation_path.exists():
        return
    write_json(root / 'results/native_bricscad_observations.json', {'generator_steps': steps, 'modelspace_entities_by_file': observations})
    counts = collections.Counter(r['status'] for r in rows)
    print(f'{len(written)} native BricsCAD files; rows {dict(counts)}')


if __name__ == '__main__':
    main()
