"""Independent reader rows for the existing ODA-written DWG files (cross/ezdxf__oda).

Those files were read only through ODA (self-read rows in results/checks.json, kept as they are). BricsCAD opens each
DWG and writes ASCII DXF 2018, which ezdxf reads and the checker grades against the intent. Rows go to
results/cross_ezdxf__oda_independent_checks.json. BricsCAD uses ODA libraries internally, so this is an independent
program, not an independent DWG engine; programs/CAPABILITIES.md records that. Usage: python -I generators/run_independent.py
"""
from pathlib import Path
import sys, json, collections
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
import ezdxf
from checker.core import compare
from programs.adapters import BricsCad, VERSIONS
from regenerate import write_json


def main():
    bc = BricsCad(); intents = {p.stem: json.loads(p.read_text()) for p in (R / 'intent').glob('*.json') if not p.name.endswith('.schema.json')}
    files = sorted((R / 'cross/ezdxf__oda').glob('*.dwg')); rows = []; refused = 0
    for i in range(0, len(files), 20):
        part = files[i:i + 20]
        docs = bc.read_dwg_many(part)
        for p in part:
            side = json.loads(p.with_suffix('.dwg.provenance.json').read_text()); rel = p.relative_to(R).as_posix(); d = docs[p]
            if isinstance(d, str):
                refused += 1
                rows.append(dict(file=rel, intent_id=side['intent_id'], field='open', reader='ezdxf ' + ezdxf.__version__, converter='bricscad ' + bc.build, self_read=False,
                                 status='refused', expected=None, actual=None, tolerance=0, detail=d[:300])); continue
            for row in compare(d, intents[side['intent_id']], 'ezdxf ' + ezdxf.__version__, VERSIONS[side['version']]):
                row.update(file=rel, converter='bricscad ' + bc.build, self_read=False); rows.append(row)
        print(f'{min(i + 20, len(files))}/{len(files)} read', flush=True)
    write_json(R / 'results/cross_ezdxf__oda_independent_checks.json', rows)
    print(len(files), 'DWG files;', dict(collections.Counter(r['status'] for r in rows)), '; refused', refused)


if __name__ == '__main__':
    main()
