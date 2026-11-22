"""Cross sets for the BricsCAD and CADCraft phase: every native file of a writer, saved again by another program at
the same format and version, with a sidecar and checker rows per output.

Pairs and source folders are declared in programs/pairs.json. ezdxf sources also produce DWG.
Binary DXF is written by BricsCAD and ODA only. A request the re-saver cannot write is recorded in
results/cross_not_run.json (a capability gap), never as a failed row. DWG outputs are read through an independent
converter: ODA reads BricsCAD- and CADCraft-written DWG, BricsCAD reads ODA-written DWG. Rows go to
results/cross_<writer>__<resaver>_checks.json after every chunk, and a finished output is skipped on rerun.
Usage: python -I generators/run_cross.py [pair ...] [--limit N]. Foreground only; it does not commit or push.
"""
from pathlib import Path
import sys, json, shutil, collections, time, hashlib
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from checker.core import digest, compare
from programs import privacy
from programs.adapters import ADAPTERS, VERSIONS, workdir
from regenerate import sidecar, publish, write_json

CHUNK = {'bricscad': 40, 'cadcraft': 16, 'oda': 60}
PAIRS = {p['writer']+'__'+p['resaver']: (p['sources'], p['resaver']) for p in json.loads((R/'programs/pairs.json').read_text())}
READER = {'bricscad': 'oda', 'cadcraft': 'oda', 'oda': 'bricscad'}   # independent DWG reader for each re-saver's output
CAPABILITY_GAP = ('cannot write', 'requires binary')
LOG = R / '.codex-runs/phase2b-progress.log'


def log(msg):
    with LOG.open('a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S') + ' ' + msg + '\n')
    print(msg, flush=True)


def load_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def jobs_for(pair, limit=None, intent=None):
    folder, resaver = PAIRS[pair]; writer = pair.split('__')[0]; out = []
    for src in sorted((R / folder).glob('*.d[xw][fg]')):
        side = json.loads(src.with_suffix(src.suffix + '.provenance.json').read_text())
        if intent and side['intent_id'] != intent: continue
        if writer == 'ezdxf' and side['program'] != 'ezdxf':
            continue
        formats = ['DXF', 'DWG'] if (writer == 'ezdxf') else [side['format']]
        for fmt in formats:
            stem = src.stem
            dest = R / 'cross' / pair / (stem + '.' + fmt.lower())
            out.append((src, dest, fmt, side['version'], 'binary' if fmt == 'DWG' else side['encoding'], side))
    return out[:limit] if limit else out


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


def run_pair(pair, limit=None, t0=0, budget=None, intent=None, reader_name=None, retain_unreadable=False):
    writer_name, resaver_name = pair.split('__'); resaver = ADAPTERS[resaver_name](); reader = ADAPTERS[reader_name or READER[resaver_name]]()
    folder = R / 'cross' / pair; folder.mkdir(parents=True, exist_ok=True)
    checks_path = R / 'results' / f'cross_{pair}_checks.json'
    refused_path = R / 'results' / (f'cross_{pair}_refused.json' if writer_name == 'oda' else f'cross_{pair}_refused_checks.json')
    rows_by_file = collections.defaultdict(list)
    for r in load_json(checks_path, []):
        rows_by_file[r['file']].append(r)
    not_run = {k: v for k, v in load_json(R / 'results/cross_not_run.json', {}).items() if not (k.startswith(pair + '|') and (not intent or any(str(d.relative_to(R)) == k.split('|',1)[1] for _,d,*_ in jobs_for(pair, limit, intent))))}
    intents = {p.stem: json.loads(p.read_text()) for p in (R / 'intent').glob('*.json') if not p.name.endswith('.schema.json')}
    jobs = jobs_for(pair, limit, intent); todo = []
    for src, dest, fmt, version, enc, side in jobs:
        sc = dest.with_suffix(dest.suffix + '.provenance.json')
        if dest.exists() and sc.exists():
            m = json.loads(sc.read_text())
            if m['made_by']['input_digest'] == side['content_digest'] and m['build'] == resaver.build:
                continue
        todo.append((src, dest, fmt, version, enc, side))
    log(f'{pair}: {len(jobs)} outputs planned, {len(todo)} to do')
    size = CHUNK[resaver_name]
    for start in range(0, len(todo), size):
        if budget and time.time() - t0 > budget:
            log(f'{pair}: time budget reached with {len(todo) - start} outputs left; run again to resume')
            return True
        chunk = todo[start:start + size]; stage = Path(workdir('cross-'))
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
                rel = dest.relative_to(R).as_posix()
                if err is None:
                    written.append((src, dest, fmt, version, enc, side)); continue
                if any(k in err for k in CAPABILITY_GAP):
                    not_run[f'{pair}|{rel}'] = err
                else:
                    rows_by_file[rel] = [dict(file=rel, intent_id=side['intent_id'], field='open', reader=f'{resaver.name} {resaver.build}', converter=None, self_read=False,
                                              status='refused', expected=None, actual=None, tolerance=0, detail=err[:300])]
            dwg = [(s, d, f, v, e, sd) for s, d, f, v, e, sd in written if f == 'DWG']
            docs = reader.read_dwg_many([staged[d] for s, d, *_ in dwg]) if dwg else {}
            for src, dest, fmt, version, enc, side in written:
                rel = dest.relative_to(R).as_posix(); intent = intents[side['intent_id']]
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
                publish(staged[dest], dest, meta)
                sc = dest.with_suffix(dest.suffix + '.provenance.json')
                if json.loads(sc.read_text()) != meta:   # publish keeps an unchanged output; its sidecar must still name the current source
                    write_json(sc, meta)
                rows = compare(doc, intent, f'ezdxf {ezdxf.__version__}', VERSIONS[version] if fmt == 'DWG' else None)
                for row in rows:
                    row.update(file=rel, converter=converter, self_read=(fmt == 'DWG' and reader.name == resaver.name))
                rows_by_file[rel] = rows
            del docs
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        refused = {k: v for k, v in rows_by_file.items() if v and v[0]['status'] == 'refused'}
        write_json(checks_path, [r for k, v in sorted(rows_by_file.items()) if k not in refused or writer_name != 'oda' for r in v])
        if writer_name == 'oda':
            write_json(refused_path, [r for v in refused.values() for r in v])
        write_json(R / 'results/cross_not_run.json', dict(sorted(not_run.items())))
        log(f'{pair}: {min(start + size, len(todo))}/{len(todo)} done')
    counts = collections.Counter(r['status'] for v in rows_by_file.values() for r in v)
    log(f'{pair}: finished; rows {dict(counts)}; not run {sum(1 for k in not_run if k.startswith(pair + "|"))}')
    return False


if __name__ == '__main__':
    main()
