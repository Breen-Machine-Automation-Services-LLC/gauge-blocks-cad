"""Count kept, changed, lost and refused outputs per pair, format and version, from the result rows.
An output is refused if any row is refused, lost if any field is absent, changed if any differs, otherwise kept.
Writes results/cross_summary.json and prints a markdown table. Usage: python -I generators/summarize_cross.py
"""
from pathlib import Path
import json, collections
R = Path(__file__).resolve().parents[1]


def main():
    per_file = collections.defaultdict(list)
    for p in sorted((R / 'results').glob('cross_*checks.json')):
        for r in json.loads(p.read_text()):
            per_file[r['file']].append(r)
    table = collections.defaultdict(collections.Counter)
    for f, rows in per_file.items():
        parts = Path(f).parts; pair = parts[1]
        fmt = Path(f).suffix[1:].upper()
        stat = {r['status'] for r in rows}
        state = 'refused' if 'refused' in stat else 'lost' if 'absent' in stat else 'changed' if 'differs' in stat else 'kept'
        table[(pair, fmt)][state] += 1
    out = {f'{k[0]} {k[1]}': dict(v) for k, v in sorted(table.items())}
    nr = json.loads((R / 'results/cross_not_run.json').read_text())
    notrun = collections.Counter()
    for k in nr:
        pair, rel = k.split('|'); notrun[(pair, Path(rel).suffix[1:].upper())] += 1
    (R / 'results/cross_summary.json').write_text(json.dumps({'outputs_by_pair_and_format': out, 'not_run_capability_gap': {f'{a} {b}': n for (a, b), n in sorted(notrun.items())}}, indent=1) + '\n')
    print('| Pair | Format | Kept | Changed | Lost | Refused | Not run |\n| --- | --- | ---: | ---: | ---: | ---: | ---: |')
    for (pair, fmt), c in sorted(table.items()):
        print(f"| {pair} | {fmt} | {c['kept']} | {c['changed']} | {c['lost']} | {c['refused']} | {notrun[(pair, fmt)]} |")
    for (pair, fmt), n in sorted(notrun.items()):
        if (pair, fmt) not in table:
            print(f'| {pair} | {fmt} | 0 | 0 | 0 | 0 | {n} |')


if __name__ == '__main__':
    main()
