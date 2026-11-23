"""BricsCAD reader rows for the existing ODA-written DWG files (cross/ezdxf__oda).

ODA reader rows live in results/cross_ezdxf__oda_checks.json. BricsCAD opens each
DWG and writes ASCII DXF 2018, which ezdxf reads and the checker grades against the intent. Rows go to
results/cross_ezdxf__oda_read_by_bricscad_checks.json. BricsCAD uses ODA libraries internally, so this is a shared engine
reader cohort; programs/CAPABILITIES.md records that. Usage: python -I generators/run_independent.py
"""
from pathlib import Path
import sys, json, collections
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from checker.core import encoding_intent, compare
from checker.scoring import annotate, current, load_rows, reading_current
import hashlib
from programs.adapters import BricsCad, VERSIONS
from regenerate import write_json


def plan(intent_id=None, force=False, root=None):
    from checker.scoring import empty_plan, file_current
    root=R if root is None else Path(root)
    work=empty_plan();path=root/'results/cross_ezdxf__oda_read_by_bricscad_checks.json';previous=load_rows(path)
    for p in sorted((root/'cross/ezdxf__oda').glob('*.dwg')):
        side=json.loads(p.with_suffix('.dwg.provenance.json').read_text());iid=side['intent_id']
        if intent_id and iid!=intent_id:continue
        rel=p.relative_to(root).as_posix();old=[r for r in previous if r['file']==rel]
        identity=hashlib.sha256(p.read_bytes()).hexdigest()
        kind='carried' if not force and file_current(old,root,iid,path,rel,current,'ezdxf '+ezdxf.__version__,'bricscad '+BricsCad.build,identity) else 'rescore'
        work[kind].append(rel)
    return work


def main(intent_id=None, force=False, root=None):
    from checker.scoring import record_score
    root = R if root is None else Path(root)
    work_plan=plan(intent_id,force,root)
    bc = BricsCad(); intents = {p.stem: json.loads(p.read_text()) for p in (root / 'intent').glob('*.json') if not p.name.endswith('.schema.json')}
    path = root / 'results/cross_ezdxf__oda_read_by_bricscad_checks.json'
    previous = load_rows(path); rows = [r for r in previous if intent_id and r['intent_id'] != intent_id]; refused = 0; files = []
    for p in sorted((root / 'cross/ezdxf__oda').glob('*.dwg')):
        side = json.loads(p.with_suffix('.dwg.provenance.json').read_text())
        if intent_id and side['intent_id'] != intent_id:
            continue
        old = [r for r in previous if r['file'] == p.relative_to(root).as_posix()]
        rel=p.relative_to(root).as_posix()
        if rel in work_plan['carried']:
            rows.extend(old)
        elif rel in work_plan['rescore']:
            files.append(p)
    carried_count = len(rows)
    for i in range(0, len(files), 20):
        part = files[i:i + 20]
        docs = bc.read_dwg_many(part)
        for p in part:
            side = json.loads(p.with_suffix('.dwg.provenance.json').read_text()); rel = p.relative_to(root).as_posix(); d = docs[p]
            if isinstance(d, str):
                refused += 1
                rows.append(dict(file=rel, intent_id=side['intent_id'], field='open', reader='ezdxf ' + ezdxf.__version__, converter='bricscad ' + bc.build, self_read=False,
                                 status='refused', expected=None, actual=None, tolerance=0, detail=d[:300])); continue
            checks=compare(d, encoding_intent(intents[side['intent_id']], side.get('encoding')), 'ezdxf ' + ezdxf.__version__, VERSIONS[(side['version'] if 'version' in side else p.stem.rsplit('_',2)[-2])])
            record_score(checks,root,side['intent_id'],path,rel,'ezdxf '+ezdxf.__version__,'bricscad '+bc.build,hashlib.sha256(p.read_bytes()).hexdigest())
            for row in checks:
                row.update(file=rel, converter='bricscad ' + bc.build, self_read=False); rows.append(row)
        print(f'{min(i + 20, len(files))}/{len(files)} read', flush=True)
    for row in rows[carried_count:]:
        row['read_input_digest'] = hashlib.sha256((root / row['file']).read_bytes()).hexdigest()
        annotate([row],root,row['intent_id'],'oda','bricscad')
    write_json(root / 'results/cross_ezdxf__oda_read_by_bricscad_checks.json', rows)
    print(len(files), 'DWG files;', dict(collections.Counter(r['status'] for r in rows)), '; refused', refused)


if __name__ == '__main__':
    main()
