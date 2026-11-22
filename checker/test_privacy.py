"""Privacy power test: does the byte scan see an unneutralized name, and does each neutralized writer pass it?

For BricsCAD and ODA the control run turns the neutralization off (BricsCAD: no login remap; ODA: no identity library)
and saves one input at every format, version and encoding. A format whose control files carry no hit cannot be
trusted by the byte scan alone; the DXF written by the same program at the same version then serves as the twin check.
Writes results/privacy_evidence.json. Run from the repository root.
"""
from pathlib import Path
import json, shutil, sys
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
from programs import privacy
from programs.adapters import BricsCad, CadCraft, Oda, VERSIONS, workdir, identity_library

SOURCE = R / 'native/ezdxf/metadata_2018_ASCII.dxf'
VERS = ['R12', '2000', '2004', '2007', '2010', '2013', '2018']


def cases(program):
    out = []
    for v in VERS:
        for enc in ('ASCII', 'binary'):
            out.append(('DXF', v, enc))
        out.append(('DWG', v, 'binary'))
    return out


def run(label, writer, shield, scan_cases):
    tmp = Path(workdir('priv-')); rows = []
    try:
        jobs = [(SOURCE, tmp / f'{i}.{f.lower()}', f, v, e) for i, (f, v, e) in enumerate(scan_cases)]
        if label.startswith('bricscad'):
            res = writer.save_many(jobs, tag='priv', shield=shield, scan=False)
        elif label.startswith('oda'):
            res = {}
            for src, dest, f, v, e in jobs:
                try:
                    (tmp / 'in').mkdir(exist_ok=True); (tmp / 'out').mkdir(exist_ok=True)
                    shutil.copyfile(src, tmp / 'in' / 'a.dxf')
                    for old in (tmp / 'out').glob('*'):
                        old.unlink()
                    writer._run(tmp / 'in', tmp / 'out', v, 'DXB' if (f, e) == ('DXF', 'binary') else f, '*.dxf', identity=shield)
                    produced = next((tmp / 'out').glob('*.' + f.lower()))
                    shutil.copyfile(produced, dest); res[dest] = None
                except Exception as ex:
                    res[dest] = 'failed: ' + str(ex)[:120]
        else:
            res = writer.save_many(jobs)
        for src, dest, f, v, e in jobs:
            r = res.get(dest)
            hits = privacy.scan(dest) if r is None and dest.exists() else None
            rows.append({'format': f, 'version': v, 'encoding': e, 'written': r is None, 'error': r,
                         'hits': None if hits is None else sorted({h[0] + '/' + h[1] for h in hits}), 'bytes': dest.stat().st_size if dest.exists() else None})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def main():
    evidence = {'input': SOURCE.relative_to(R).as_posix(), 'tokens_checked': 'login name, full name, legacy account, host name (values withheld)'}
    bc, oda, cc = BricsCad(), Oda(), CadCraft()
    evidence['bricscad_unneutralized'] = run('bricscad control', bc, False, cases('bricscad'))
    evidence['bricscad_neutralized'] = run('bricscad', bc, True, cases('bricscad'))
    evidence['oda_unneutralized'] = run('oda control', oda, False, cases('oda'))
    evidence['oda_neutralized'] = run('oda', oda, True, cases('oda'))
    evidence['cadcraft'] = run('cadcraft', cc, True, cases('cadcraft'))
    summary = {}
    for k, rows in evidence.items():
        if isinstance(rows, list):
            summary[k] = {'written': sum(r['written'] for r in rows), 'with_hits': sum(bool(r['hits']) for r in rows),
                          'exposed_formats': sorted({f"{r['format']} {r['version']} {r['encoding']}" for r in rows if r['hits']})}
    evidence['summary'] = summary
    (R / 'results/privacy_evidence.json').write_text(json.dumps(evidence, indent=1) + '\n')
    print(json.dumps(summary, indent=1))
    for k in ('bricscad_neutralized', 'oda_neutralized', 'cadcraft'):
        assert summary[k]['with_hits'] == 0, k


if __name__ == '__main__':
    if '--existing-evidence' in sys.argv:
        from checker.existing_evidence import privacy
        privacy()
    else:
        main()
