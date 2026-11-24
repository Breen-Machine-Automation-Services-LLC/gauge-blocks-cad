"""Count baseline-relative outcomes per pair and format from measured result rows.
DXF read directly supplies headline fidelity counts; DWG paths retain converter attribution.
Writes results/cross_summary.json and prints a markdown table. Usage: python -I generators/summarize_cross.py
"""
from pathlib import Path
import json, collections, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from checker.attribution import Attribution, outcome, BUCKETS
R = Path(__file__).resolve().parents[1]


def main(output=None):
    per_file = collections.defaultdict(list)
    for p in sorted((R / 'results').glob('cross_*checks.json')):
        for r in json.loads(p.read_text()):
            per_file[r['file']].append(r)
    provenance = {p.relative_to(R).as_posix()[:-len('.provenance.json')]:json.loads(p.read_text())
                  for folder in ('native','cross') for p in (R/folder).rglob('*.provenance.json')}
    all_rows = [r for p in (R/'results').glob('*checks.json') for data in [json.loads(p.read_text())]
                if isinstance(data,list) for r in data]
    attribution = Attribution(provenance,all_rows,json.loads((R/'programs/pairs.json').read_text()))
    table = collections.defaultdict(collections.Counter)
    for f, rows in per_file.items():
        parts = Path(f).parts; pair = parts[1]
        fmt = Path(f).suffix[1:].upper()
        state = BUCKETS.get(outcome([attribution.attribute(r) for r in rows]), 'not_measured')
        table[(pair, fmt)][state] += 1
    out = {f'{k[0]} {k[1]}': dict(v) for k, v in sorted(table.items())}
    nr = json.loads((R / 'results/cross_not_run.json').read_text())
    notrun = collections.Counter()
    for k in nr:
        pair, rel = k.split('|'); notrun[(pair, Path(rel).suffix[1:].upper())] += 1
    (Path(output) if output else R / 'results/cross_summary.json').write_text(json.dumps({'outputs_by_pair_and_format': out, 'direct_dxf_fields': {p:attribution.direct_summary(p) for p in attribution.declarations}, 'not_run_capability_gap': {f'{a} {b}': n for (a, b), n in sorted(notrun.items())}}, indent=1) + '\n')
    print('| Pair | Format | Kept | Changed | Lost | Refused | Source not readable | Writer or converter | Unreadable by reader | Not measured | Not run |\n| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
    for (pair, fmt), c in sorted(table.items()):
        print(f"| {pair} | {fmt} | {c['kept']} | {c['changed']} | {c['lost']} | {c['refused']} | {c['source_not_readable']} | {c['writer_or_converter']} | {c['unreadable_by_reader']} | {c['not_measured']} | {notrun[(pair, fmt)]} |")
    for (pair, fmt), n in sorted(notrun.items()):
        if (pair, fmt) not in table:
            print(f'| {pair} | {fmt} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | {n} |')


if __name__ == '__main__':
    main()
