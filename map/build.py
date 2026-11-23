"""Build a standalone heatmap from intents, drawing sidecars and results only."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = dict(zip(['R12','2000','2004','2007','2010','2013','2018'],
                    ['AC1009','AC1015','AC1018','AC1021','AC1024','AC1027','AC1032']))

def read(path):
    return json.loads(path.read_text())

def main():
    intents = [read(p) for p in sorted((ROOT/'intent').glob('*.json')) if not p.name.endswith('.schema.json')]
    declared = read(ROOT/'programs/pairs.json')
    pairs = {p['writer']+'__'+p['resaver']: p for p in declared}
    files = []
    builds = set()
    for folder in ('native','cross'):
        for p in sorted((ROOT/folder).rglob('*.json')):
            s = read(p)
            path = p.relative_to(ROOT).as_posix()[:-len('.provenance.json')]
            pair = p.parts[-2] if folder == 'cross' else ''
            files.append(dict(s, path=path, pair=pair, unavailable=not (ROOT/path).is_file()))
            builds.add(s['program']+' '+s['build'])
    checks = defaultdict(list)
    seen = set()
    for p in sorted((ROOT/'results').glob('*checks.json')):
        rows = read(p)
        if not isinstance(rows, list): continue
        for row in rows:
            key = tuple(row.get(k) for k in ('file','field','reader','converter'))
            if key in seen: continue
            seen.add(key)
            checks[row['file']].append(row)
    # A refused open may leave no cross drawing or sidecar. Recover its
    # target slot from the checked path and the matching native source sidecar.
    known_paths = {s['path'] for s in files}
    for path, measured in checks.items():
        if path in known_paths or not any(r['status']=='refused' for r in measured):
            continue
        target = Path(path)
        if len(target.parts)!=3 or target.parts[0]!='cross' or '__' not in target.parts[1]:
            raise ValueError(f'Refused result lacks a cross-pair path: {path}')
        pair = target.parts[1]
        writer, resaver = pair.split('__',1)
        sources = [s for s in files if not s['pair'] and s['program']==writer
                   and Path(s['path']).stem==target.stem]
        if len(sources)!=1 or target.suffix.lower() not in ('.dwg','.dxf'):
            raise ValueError(f'Cannot place refused result without source provenance: {path}')
        source = sources[0]
        files.append(dict(source, path=path, pair=pair, program=resaver,
                          format=target.suffix[1:].upper(),
                          encoding='binary' if target.suffix.lower()=='.dwg' else source['encoding'],
                          made_by={'input_digest':source['content_digest']}, unavailable=True))
    columns = [[fmt,v,enc] for fmt in ('DWG','DXF') for enc in (['binary'] if fmt=='DWG' else ['ASCII','binary']) for v in VERSIONS]
    capabilities = read(ROOT/'programs/capabilities.json')
    topics = []
    for i in intents:
        topic = dict(title=i['title'], id=i['intent_id'], description=i.get('description',''), features=[])
        own = [s for s in files if s['intent_id']==i['intent_id']]
        for feature in [f for f in i.get('features',[]) if f.lower() != 'file identity'] or [i['title']]:
            ids = i.get('feature_fields',{}).get(feature,[])
            expected = [e for e in i.get('expected',[]) if not ids or e['id'] in ids]
            cells = []
            for fmt,v,enc in columns:
                applicable = not expected or any(VERSIONS[v] in e.get('versions',VERSIONS.values()) for e in expected)
                fs = [s for s in own if (s['format'],s['version'],s['encoding'])==(fmt,v,enc)]
                missing, impossible = [], []
                has_source = False
                for pair, declaration in pairs.items():
                    sources = [s for s in fs if not s.get('unavailable') and
                               str(Path(s['path']).parent)==declaration['sources']]
                    if not sources: continue
                    has_source = True
                    writer, resaver = declaration['writer'], declaration['resaver']
                    caps = capabilities[resaver]
                    label = capabilities[writer]['name']+' to '+caps['name']
                    if [fmt,v,enc] not in caps['outputs']:
                        impossible.append('not possible: '+label+' cannot write '+fmt+' '+v+' '+enc)
                        continue
                    measured = any(s['pair']==pair and any(not ids or r.get('field') in ids or r['status']=='refused' for r in checks[s['path']]) for s in fs)
                    if not measured: missing.append('not yet run: '+label)
                # A source folder is reachable when its native author can write this
                # cell, or a declared preceding pair can produce it from such a source.
                slot = [fmt, v, enc]
                reachable = {str(Path(s['path']).parent) for s in own
                             if s['path'].startswith('native/') and
                             (slot in capabilities[s['program']]['outputs'] or
                              (fmt == 'DWG' and any(o[0] == 'DXF' and o[1] == v for o in capabilities[s['program']]['outputs'])))}
                changed = True
                while changed:
                    before = len(reachable)
                    for declaration in declared:
                        if declaration['sources'] in reachable and slot in capabilities[declaration['resaver']]['outputs']:
                            reachable.add('cross/'+declaration['writer']+'__'+declaration['resaver'])
                    changed = len(reachable) != before
                possible_source = any(d['sources'] in reachable for d in declared)
                coverage = ('not applicable' if not applicable else
                            ('partial' if missing else 'covered') if has_source else
                            'no source' if own and not possible_source else i.get('status','planned'))
                runs = []
                for s in fs:
                    if not s['pair']: continue
                    selected = [r for r in checks[s['path']] if not ids or r.get('field') in ids or r['status']=='refused']
                    diffs = [r for r in selected if r['status']!='same']
                    state = 'not run'
                    if selected:
                        state = 'refused' if any(r['status']=='refused' for r in selected) else 'lost' if any(r['status']=='absent' for r in selected) else 'changed' if any(r['status']=='differs' for r in selected) else 'not_scored' if any(r['status']=='not_scored' for r in selected) else 'kept'
                    # Match the source by provenance digest, including DXF-to-DWG conversion.
                    sources = [x for x in own if not x.get('unavailable') and x['path']!=s['path'] and x['content_digest']==s.get('made_by',{}).get('input_digest')]
                    stale = False
                    if not sources and s['pair'] in pairs:
                        declaration = pairs[s['pair']]
                        sources = [x for x in own if not x.get('unavailable') and
                                   str(Path(x['path']).parent)==declaration['sources'] and
                                   Path(x['path']).stem==Path(s['path']).stem and
                                   (declaration['writer']=='ezdxf' or x['format']==s['format'])]
                        stale = bool(sources)
                    runs.append(dict(pair=s['pair'], status=state, diffs=diffs, stale=stale,
                                     readers=sorted({r.get('reader','unspecified')+(' via '+str(r['converter']) if r.get('converter') else '') for r in selected}),
                                     self=any(r.get('shared_engine',r.get('self_read')) for r in selected), shared_engine=any(r.get('shared_engine') for r in selected), output=s['path'], unavailable=s.get('unavailable',False), inputs=[x['path'] for x in sources]))
                cells.append(dict(coverage=coverage, missing=missing, impossible=impossible, applicable=applicable, runs=runs, files=[s['path'] for s in fs if not s.get('unavailable')]))
            topic['features'].append(dict(name=feature,cells=cells))
        topics.append(topic)
    data = dict(topics=topics, columns=columns, pairs=list(pairs), builds=sorted(builds), generated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    from collections import Counter
    print('Coverage cells:', dict(Counter(c['coverage'] for t in topics for f in t['features'] for c in f['cells'])))
    template = (ROOT/'map/template.html').read_text()
    (ROOT/'map/index.html').write_text(template.replace('/*DATA*/',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')))
    print(f'{len(topics)} topics; {sum(len(t["features"]) for t in topics)} features; {sum(map(len,checks.values()))} measured fields')

if __name__=='__main__':
    main()
