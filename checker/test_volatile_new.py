"""Volatile-field evidence for BricsCAD and CADCraft: two saves of one input, more than two seconds apart, must give the
same content digest, and a one-field change must change it. Reports every header variable and entity that differed
between the two saves, so the exclusions in checker/core.py and checker/VOLATILE.md rest on measured differences.
DWG saves are read through ODA (BricsCAD DWG, CADCraft DWG) as in the cross sets. Writes
results/bricscad_digest_evidence.json and results/cadcraft_digest_evidence.json. Run from the repository root.
"""
from pathlib import Path
import json, shutil, sys, time
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from checker.core import digest
from programs.adapters import BricsCad, CadCraft, Oda, workdir

SOURCE = R / 'native/ezdxf/metadata_2018_ASCII.dxf'
VERS = ['2000', '2004', '2007', '2010', '2013', '2018']


def tags(d):
    return {e.dxf.handle: [list(t) for t in TagCollector.dxftags(e, dxfversion='AC1032')] for e in d.entitydb.values() if e.is_alive}


def saves(writer, cases, tmp):
    jobs = [(SOURCE, tmp / f'{k}_{i}.{f.lower()}', f, v, e) for k, (f, v, e) in enumerate(cases) for i in [len(list(tmp.glob(f'{k}_*')))]]
    res = writer.save_many(jobs)
    return jobs, res


def one_run(writer, cases):
    tmp = Path(workdir('volatile-')); out = {}
    try:
        jobs = [(SOURCE, tmp / f'{k}.{f.lower()}', f, v, e) for k, (f, v, e) in enumerate(cases)]
        res = writer.save_many(jobs)
        dwg = [j[1] for j in jobs if j[2] == 'DWG' and res[j[1]] is None]
        read = Oda().read_dwg_many(dwg) if dwg else {}
        for (src, dest, f, v, e), case in zip(jobs, cases):
            if res[dest] is not None:
                out[case] = res[dest]; continue
            out[case] = ezdxf.readfile(dest) if f == 'DXF' else read[dest]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def evidence(writer, cases):
    a = one_run(writer, cases); time.sleep(2.5); b = one_run(writer, cases); rows = []
    for case in cases:
        x, y = a[case], b[case]
        row = {'format': case[0], 'version': case[1], 'encoding': case[2]}
        if isinstance(x, str) or isinstance(y, str):
            row['not_compared'] = x if isinstance(x, str) else y; rows.append(row); continue
        headers = {k: [str(x.header.get(k)), str(y.header.get(k))] for k in sorted(set(x.header.varnames()) | set(y.header.varnames())) if str(x.header.get(k)) != str(y.header.get(k))}
        ta, tb = tags(x), tags(y)
        changes = {h: [ta.get(h), tb.get(h)] for h in sorted(ta.keys() | tb.keys()) if ta.get(h) != tb.get(h)}
        row.update(header_changes=headers, entity_changes={h: [[str(t) for t in (v or [])][:12] for v in pair] for h, pair in list(changes.items())[:6]},
                   entity_change_count=len(changes), digests_equal=digest(x) == digest(y))
        rows.append(row)
    sample = next(v for v in a.values() if not isinstance(v, str))
    before = digest(sample); next(iter(sample.modelspace())).dxf.layer = 'ZEV_CHANGED'
    return {'build': writer.build, 'input': SOURCE.relative_to(R).as_posix(), 'saves_apart_seconds': '>2.5', 'cases': rows,
            'all_digests_equal': all(r.get('digests_equal', True) for r in rows), 'one_field_changes_digest': before != digest(sample)}


def main():
    bc = [('DXF', v, 'ASCII') for v in ['R12'] + VERS] + [('DXF', v, 'binary') for v in ['R12', '2000', '2018']] + [('DWG', v, 'binary') for v in VERS]
    cc = [('DXF', v, 'ASCII') for v in VERS] + [('DWG', v, 'binary') for v in VERS]
    for name, writer, cases in [('bricscad', BricsCad(), bc), ('cadcraft', CadCraft(), cc)]:
        ev = evidence(writer, cases)
        (R / f'results/{name}_digest_evidence.json').write_text(json.dumps(ev, indent=1) + '\n')
        bad = [r for r in ev['cases'] if not r.get('digests_equal', True)]
        print(name, 'cases', len(ev['cases']), 'digest differences', len(bad), 'one-field sensitive', ev['one_field_changes_digest'])
        for r in bad[:6]:
            print('  ', r['format'], r['version'], r['encoding'], list(r['header_changes'])[:8], 'entity changes', r['entity_change_count'])


if __name__ == '__main__':
    if '--existing-evidence' in sys.argv:
        from checker.existing_evidence import volatile
        volatile()
    else:
        main()
