"""Check every drawing, provenance record and intent link embedded in the heatmap."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT/'map/index.html').read_text()
data = json.loads(page.split('const DATA=', 1)[1].split(';\nconst icons=', 1)[0])
links = set()
for topic in data['topics']:
    links.add('intent/'+topic['id']+'.json')
    for feature in topic['features']:
        for cell in feature['cells']:
            paths = set(cell['files'])
            for run in cell['runs']:
                assert run['inputs'], f'Missing input provenance: {run["output"]}'
                paths.update(run['inputs'])
                if not run.get('unavailable'):
                    paths.add(run['output'])
            for path in paths:
                links.update((path, path+'.provenance.json'))
for link in links:
    path = (ROOT/link).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), link
report = dict(links=len(links), broken=0, method='All embedded intent, input/output drawing and provenance record targets resolve inside repository')
(ROOT/'map/link-checks.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'results/map_links.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(links)} links resolve')
