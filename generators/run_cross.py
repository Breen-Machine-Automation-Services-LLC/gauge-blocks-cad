"""Cross sets for the BricsCAD and CADCraft phase: every native file of a writer, saved again by another program at
the same format and version, with a sidecar and checker rows per output.

Pairs and source folders are declared in programs/pairs.json. ezdxf sources also produce DWG.
Binary DXF is written by BricsCAD and ODA only. A request the re-saver cannot write is recorded in
results/cross_not_run.json (a capability gap), never as a failed row. DWG outputs are read through a configured
converter: ODA reads BricsCAD- and CADCraft-written DWG, BricsCAD reads ODA-written DWG. Rows go to
results/cross_<writer>__<resaver>_checks.json after every chunk, and a finished output is skipped on rerun.
Usage: python -I generators/run_cross.py [pair ...] [--limit N]. Foreground only; it does not commit or push.
"""
from pathlib import Path
import sys, json, shutil, collections, time, hashlib
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from checker.scoring import annotate, current, reading_current
from checker.core import digest, compare
from programs import privacy
from programs import adapters
from programs.adapters import VERSIONS, workdir
from collections.abc import Mapping
from regenerate import sidecar, publish, write_json


class AdapterRegistry(Mapping):
    """Resolve adapters from the shared registry at call time."""

    def __getitem__(self, name):
        return adapters.ADAPTERS[name]

    def __iter__(self):
        return iter(adapters.ADAPTERS)

    def __len__(self):
        return len(adapters.ADAPTERS)


ADAPTERS = AdapterRegistry()

CHUNK = {'bricscad': 40, 'cadcraft': 16, 'oda': 60}
PAIRS = {p['writer']+'__'+p['resaver']: (p['sources'], p['resaver']) for p in json.loads((R/'programs/pairs.json').read_text())}
READER = {'bricscad': 'oda', 'cadcraft': 'oda', 'oda': 'bricscad'}   # DWG reader program; engine families record shared implementations
CAPABILITY_GAP = ('cannot write', 'requires binary')
LOG = R / 'logs/run_cross.log'


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S') + ' ' + msg + '\n')
    print(msg, flush=True)


def load_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def jobs_for(pair, limit=None, intent=None, root=None):
    root=R if root is None else Path(root)
    folder, resaver = PAIRS[pair]; writer = pair.split('__')[0]; out = []
    for src in sorted((root / folder).glob('*.d[xw][fg]')):
        side = json.loads(src.with_suffix(src.suffix + '.provenance.json').read_text())
        if intent and side['intent_id'] != intent: continue
        if writer == 'ezdxf' and side['program'] != 'ezdxf':
            continue
        formats = ['DXF', 'DWG'] if (writer == 'ezdxf') else [side['format']]
        for fmt in formats:
            stem = src.stem
            dest = root / 'cross' / pair / (stem + '.' + fmt.lower())
            out.append((src, dest, fmt, side['version'], 'binary' if fmt == 'DWG' else side['encoding'], side))
    return out[:limit] if limit else out


def reader_for(pair, root, reader_name):
    """Keep the measured reader cohort unless a caller selects a reader explicitly."""
    if reader_name:return reader_name
    rows=load_json(root/'results'/f'cross_{pair}_checks.json',[])
    names={r['converter'].split(' ',1)[0] for r in rows if r.get('converter') and r['file'].endswith('.dwg')}
    return next(iter(names)) if len(names)==1 and names<=ADAPTERS.keys() else READER[pair.split('__')[1]]


def plan(pair, intent_id=None, force=False, root=None, reader_name=None):
    from checker.scoring import empty_plan, file_current
    root=R if root is None else Path(root)
    work=empty_plan();resaver=ADAPTERS[pair.split('__')[1]]()
    reader=ADAPTERS[reader_for(pair,root,reader_name)]
    path=root/'results'/f'cross_{pair}_checks.json'
    previous=load_json(path,[])
    gaps=load_json(root/'results/cross_not_run.json',{})
    builds=load_json(root/'results/cross_gap_builds.json',{})
    published_builds={load_json(p,{}).get('build') for p in (root/'cross'/pair).glob('*.provenance.json')}
    published_builds.discard(None)
    gap_build=next(iter(published_builds)) if len(published_builds)==1 else resaver.build
    for src,dest,fmt,version,enc,side in jobs_for(pair,intent=intent_id,root=root):
        rel=dest.relative_to(root).as_posix();key=pair+'|'+rel
        sc=dest.with_suffix(dest.suffix+'.provenance.json');old=load_json(sc,{})
        rows=[r for r in previous if r['file']==rel]
        if not force and key in gaps and builds.get(key,gap_build)==resaver.build:
            kind='gaps'
        elif force or not dest.exists() or old.get('build')!=resaver.build or old.get('made_by',{}).get('input_digest')!=side['content_digest']:
            kind='resave'
        elif not file_current(rows,root,side['intent_id'],path,rel,current, f'ezdxf {ezdxf.__version__}',None if fmt=='DXF' else f'{reader.name} {reader.build}',reading_fn=reading_current):
            kind='rescore'
        else:kind='carried'
        work[kind].append(rel)
    return work


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pairs', nargs='*', choices=list(PAIRS))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--budget', type=float)
    args = parser.parse_args()
    limit, budget = args.limit, args.budget
    pairs = args.pairs or list(PAIRS)
    t0 = time.time()
    for pair in pairs:
        if run_pair(pair, limit, t0, budget):
            return


def run_pair(pair, limit=None, t0=0, budget=None, intent=None, reader_name=None, retain_unreadable=False, force=False, root=None):
    from checker.scoring import record_score
    root=R if root is None else Path(root)
    work_plan=plan(pair,intent_id=intent,force=force,root=root,reader_name=reader_name)
    def emit(message):
        if root==R:
            log(message)
        else:
            path=root/'logs/run_cross.log';path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a') as stream:stream.write(time.strftime('%Y-%m-%dT%H:%M:%S')+' '+message+'\n')
            print(message,flush=True)

    reader_name=reader_for(pair,root,reader_name)
    writer_name, resaver_name = pair.split('__'); resaver = ADAPTERS[resaver_name](); reader = ADAPTERS[reader_name or READER[resaver_name]]()
    folder = root / 'cross' / pair; folder.mkdir(parents=True, exist_ok=True)
    checks_path = root / 'results' / f'cross_{pair}_checks.json'
    refused_path = root / 'results' / (f'cross_{pair}_refused.json' if writer_name == 'oda' else f'cross_{pair}_refused_checks.json')
    rows_by_file = collections.defaultdict(list)
    for r in load_json(checks_path, []):
        rows_by_file[r['file']].append(r)
    not_run = load_json(root/'results/cross_not_run.json',{})
    gap_builds = load_json(root/'results/cross_gap_builds.json',{})
    intents = {p.stem: json.loads(p.read_text()) for p in (root/'intent').glob('*.json') if not p.name.endswith('.schema.json')}
    jobs=jobs_for(pair,limit,intent,root=root)
    todo=[job for job in jobs if job[1].relative_to(root).as_posix() in work_plan['resave']]
    rescore=[job for job in jobs if job[1].relative_to(root).as_posix() in work_plan['rescore']]
    for src,dest,fmt,version,enc,side in rescore:
        rel=dest.relative_to(root).as_posix()
        try:
            doc=ezdxf.readfile(dest) if fmt=='DXF' else reader.read_dwg_many([dest])[dest]
        except Exception as ex:
            doc=str(ex)
        converter=None if fmt=='DXF' else f'{reader.name} {reader.build}'
        if isinstance(doc,str):
            rows=[dict(file=rel,intent_id=side['intent_id'],field='open',reader=f'ezdxf {ezdxf.__version__}',converter=converter,self_read=False,status='refused',expected=None,actual=None,tolerance=0,detail=doc)]
        else:
            rows=compare(doc,intents[side['intent_id']],f'ezdxf {ezdxf.__version__}',VERSIONS[version] if fmt=='DWG' else None)
            for row in rows:row.update(file=rel,converter=converter,self_read=(fmt=='DWG' and reader.name==resaver.name))
        annotate(rows,root,side['intent_id'],resaver_name,'ezdxf' if fmt=='DXF' else (reader_name or READER[resaver_name]))
        rows_by_file[rel]=rows
        record_score(rows,root,side['intent_id'],checks_path,rel,f'ezdxf {ezdxf.__version__}',converter)
    if rescore:
        write_json(checks_path,[r for k,v in sorted(rows_by_file.items()) for r in v])
    emit(f'{pair}: {len(jobs)} outputs planned, {len(todo)} to resave, {len(rescore)} to rescore')
    size = CHUNK[resaver_name]
    for start in range(0, len(todo), size):
        if budget and time.time() - t0 > budget:
            emit(f'{pair}: time budget reached with {len(todo) - start} outputs left; run again to resume')
            return True
        chunk = todo[start:start + size]; stage = Path(workdir('cross-'))
        for job in chunk:
            key=pair+'|'+job[1].relative_to(root).as_posix()
            not_run.pop(key,None);gap_builds.pop(key,None)
        try:
            staged = {dest: stage / f'{i}{dest.suffix}' for i, (src, dest, *_ ) in enumerate(chunk)}
            sjobs = [(src, staged[dest], fmt, version, enc) for src, dest, fmt, version, enc, side in chunk]
            if resaver_name == 'cadcraft':
                from concurrent.futures import ThreadPoolExecutor
                groups = [sjobs[i::4] for i in range(4)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = {}
                    for part in pool.map(resaver.save_many, [g for g in groups if g]):
                        results.update(part)
            else:
                results = resaver.save_many(sjobs)
            written = []
            for src, dest, fmt, version, enc, side in chunk:
                err = results.get(staged[dest])
                if err is None and not staged[dest].exists():
                    err = f'{resaver.name} produced no output'
                rel = dest.relative_to(root).as_posix()
                if err is None:
                    written.append((src, dest, fmt, version, enc, side)); continue
                if any(k in err for k in CAPABILITY_GAP):
                    not_run[f'{pair}|{rel}'] = err
                    gap_builds[f'{pair}|{rel}'] = resaver.build
                    rows_by_file.pop(rel,None)
                else:
                    rows_by_file[rel] = [dict(file=rel, intent_id=side['intent_id'], field='open', reader=f'{resaver.name} {resaver.build}', converter=None, self_read=False,
                                              status='refused', expected=None, actual=None, tolerance=0, detail=err[:300])]
            dwg = [(s, d, f, v, e, sd) for s, d, f, v, e, sd in written if f == 'DWG']
            docs = reader.read_dwg_many([staged[d] for s, d, *_ in dwg]) if dwg else {}
            for src, dest, fmt, version, enc, side in written:
                rel = dest.relative_to(root).as_posix(); intent = intents[side['intent_id']]
                if fmt == 'DXF':
                    converter = None
                    try:
                        doc = ezdxf.readfile(staged[dest]); converter = None; digest_reader = None
                    except Exception as ex:
                        doc = str(ex)
                else:
                    doc = docs[staged[dest]]; converter = f'{reader.name} {reader.build}'; digest_reader = converter
                if isinstance(doc, str):
                    if retain_unreadable:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(staged[dest], dest)
                        meta = dict(side, program=resaver.name, build=resaver.build, format=fmt, version=version, encoding=enc,
                                    made_by={'script': 'compare_build.py', 'input_digest': side['content_digest']},
                                    content_digest=hashlib.sha256(dest.read_bytes()).hexdigest(),
                                    digest_algorithm='raw-sha256 (unreadable output)', read_error=doc)
                        write_json(dest.with_suffix(dest.suffix + '.provenance.json'), meta)
                    rows_by_file[rel] = [dict(file=rel, intent_id=side['intent_id'], field='open', reader=f'ezdxf {ezdxf.__version__}', converter=converter, self_read=False,
                                              status='refused', expected=None, actual=None, tolerance=0, detail=doc[:300])]
                    if fmt == 'DXF' or True:
                        pass
                    continue
                meta = sidecar(dest, doc, intent, resaver, version, enc, side['content_digest'])
                meta['ezdxf_based'] = side['ezdxf_based']; meta['made_by']['script'] = 'generators/run_cross.py'
                if digest_reader:
                    meta['digest_reader'] = digest_reader
                privacy.assert_clean(staged[dest])
                publish(staged[dest], dest, meta, force=force)
                sc = dest.with_suffix(dest.suffix + '.provenance.json')
                if json.loads(sc.read_text()) != meta:   # publish keeps an unchanged output; its sidecar must still name the current source
                    write_json(sc, meta)
                rows = compare(doc, intent, f'ezdxf {ezdxf.__version__}', VERSIONS[version] if fmt == 'DWG' else None)
                for row in rows:
                    row.update(file=rel, converter=converter, self_read=(fmt == 'DWG' and reader.name == resaver.name))
                rows_by_file[rel] = rows
                record_score(rows,root,side['intent_id'],checks_path,rel,f'ezdxf {ezdxf.__version__}',converter)
            del docs
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        for _, dest, *_ in chunk:
            rel=dest.relative_to(root).as_posix();rows=rows_by_file[rel]
            if rows:
                record_score(rows,root,rows[0]['intent_id'],checks_path,rel)
                annotate(rows,root,rows[0]['intent_id'],resaver_name,'ezdxf' if rel.endswith('.dxf') else (reader_name or READER[resaver_name]))
        refused = {k: v for k, v in rows_by_file.items() if v and v[0]['status'] == 'refused'}
        write_json(checks_path, [r for k, v in sorted(rows_by_file.items()) if k not in refused or writer_name != 'oda' for r in v])
        if writer_name == 'oda':
            write_json(refused_path, [r for v in refused.values() for r in v])
        write_json(root / 'results/cross_not_run.json', dict(sorted(not_run.items())))
        write_json(root / 'results/cross_gap_builds.json', dict(sorted(gap_builds.items())))
        emit(f'{pair}: {min(start + size, len(todo))}/{len(todo)} done')
    for rel in work_plan['gaps']:
        gap_builds.setdefault(pair+'|'+rel,resaver.build)
    if work_plan['gaps']:
        write_json(root/'results/cross_gap_builds.json',dict(sorted(gap_builds.items())))
    counts = collections.Counter(r['status'] for v in rows_by_file.values() for r in v)
    emit(f'{pair}: finished; rows {dict(counts)}; not run {sum(1 for k in not_run if k.startswith(pair + "|"))}')
    return False


if __name__ == '__main__':
    main()
