"""Byte-search every drawing in native/ and cross/ for the login name, the full name, the legacy account and the host name.
Writes results/privacy_scan.json. Exits nonzero on any hit. Run from the repository root.
"""
from pathlib import Path
import json, sys
R = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R))
from programs import privacy


def main():
    files = [p for root in ('native', 'cross') for p in sorted((R / root).rglob('*')) if p.suffix.lower() in ('.dxf', '.dwg')]
    hits = {}
    for p in files:
        h = privacy.scan(p)
        if h:
            hits[p.relative_to(R).as_posix()] = sorted({a + '/' + b for a, b in h})
    (R / 'results/privacy_scan.json').write_text(json.dumps({'drawings_scanned': len(files), 'files_with_hits': len(hits), 'hits': hits,
                                                             'searched': 'login name, full name, legacy account name, host name; ASCII and UTF-16LE, case-insensitive (values withheld)'}, indent=1) + '\n')
    print(f'{len(files)} drawings scanned; {len(hits)} with hits')
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
