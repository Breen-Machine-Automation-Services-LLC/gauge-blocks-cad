"""Every provenance record and result row names a program's build the same way."""
import json
import re
from collections import defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[1]
LABEL = re.compile(r'"(?:converter|reader)": "(oda|bricscad) ([^"]+)"')


def test_one_build_label_per_program():
    builds = defaultdict(set)
    for p in list((R / 'native').rglob('*.provenance.json')) + list((R / 'cross').rglob('*.provenance.json')):
        d = json.loads(p.read_text())
        builds[d['program']].add(d['build'])
    mixed = {k: sorted(v) for k, v in builds.items() if len(v) > 1}
    assert not mixed, f'provenance records with more than one build per program: {mixed}'

    stray = defaultdict(set)
    for p in (R / 'results').glob('*.json'):
        for program, label in LABEL.findall(p.read_text()):
            known = builds.get(program, set())
            if not any(label == b or label.startswith(b + ' (') for b in known):
                stray[program].add(label)
    assert not stray, f'result labels that match no recorded build: { {k: sorted(v)[:5] for k, v in stray.items()} }'
