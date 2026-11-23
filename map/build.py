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

from urllib.parse import urlencode


def _inventory(root):
    path = root/'standard/dxf-inventory.json'
    items = read(path) if path.is_file() else []
    names = defaultdict(int)
    for item in items:
        names[item['name']] += 1
    for item in items:
        if names[item['name']] > 1:
            item['duplicate_name'] = True
    return items


def _view_inputs(root):
    intents = {i['intent_id']: i for p in sorted((root/'intent').glob('*.json'))
               if not p.name.endswith('.schema.json') for i in [read(p)]}
    provenance = {}
    for folder in ('native', 'cross'):
        for p in sorted((root/folder).rglob('*.provenance.json')):
            provenance[p.relative_to(root).as_posix()[:-len('.provenance.json')]] = read(p)
    rows, seen = [], set()
    for p in sorted((root/'results').glob('*checks.json')):
        data = read(p)
        if not isinstance(data, list):
            continue
        for row in data:
            key = tuple(row.get(k) for k in ('file', 'field', 'reader', 'converter'))
            if key not in seen:
                rows.append(row)
                seen.add(key)
    return intents, provenance, rows


def _status(rows):
    states = {r['status'] for r in rows}
    for raw, label in [('refused', 'refused'), ('absent', 'lost'), ('differs', 'changed'),
                       ('not_scored', 'not scored'), ('same', 'kept')]:
        if raw in states:
            return label
    return 'not measured'


def _cell(status, item, program, evidence, label=None, pair=None, **extra):
    query = dict(item=item['name'], program=program)
    if item.get('duplicate_name'):
        query['kind'] = item['kind']
    if pair:
        query['pair'] = pair
    icons = {'kept': '✓', 'changed': '≠', 'lost': '−', 'refused': '×',
             'measured': '✓', 'native drawing': '✓', 'included': '✓', 'partial': '◐',
             'present': '□', 'future': '◇', 'omitted': '·'}
    return dict(status=status, label=label or status, icon=icons.get(status, '?'),
                evidence=evidence, detail_link='#detailed?' + urlencode(query), **extra)


def _item_features(intent, item):
    for feature in intent.get('features', [intent['title']]):
        if feature.lower() == 'file identity':
            continue
        fields = set(intent.get('feature_fields', {}).get(feature, []))
        expected = [e for e in intent.get('expected', []) if not fields or e['id'] in fields]
        if any(e.get('reference', {}).get('url') == item['reference_url'] for e in expected):
            yield feature


def _refused_open(row):
    return row['status'] == 'refused' and row.get('field') in (None, '', 'open')


def _item_evidence(item, intents, rows):
    fields = {iid: {e['id'] for e in intents.get(iid, {}).get('expected', [])
                    if e.get('reference', {}).get('url') == item['reference_url']}
              for iid in item['dataset']['intents']}
    return [r for r in rows if r.get('field') in fields.get(r.get('intent_id'), set())
            or (r.get('intent_id') in fields and _refused_open(r))]


def _feature_rows(intent, feature, rows):
    fields = set(intent.get('feature_fields', {}).get(feature, []))
    return [r for r in rows if r.get('intent_id') == intent['intent_id'] and
            (not fields or r.get('field') in fields or (_refused_open(r)))]


def comparison_rows(writer, resaver, root):
    intents, provenance, rows = _view_inputs(root)
    pair = writer + '__' + resaver
    declared = any(p['writer'] == writer and p['resaver'] == resaver
                   for p in read(root/'programs/pairs.json'))
    selected = [r for r in rows if r['file'].startswith('cross/' + pair + '/')] if declared else []
    selected_by_intent = defaultdict(list)
    for row in selected:
        selected_by_intent[row.get('intent_id')].append(row)
    native_ids = {p.get('intent_id') for path, p in provenance.items() if path.startswith('native/' + writer + '/')}
    summarized = set()
    groups, summary = [], dict(total=0, kept=0, changed=0, lost=0, refused=0, not_measured=0)
    for item in _inventory(root):
        features = []
        for iid in item['dataset']['intents']:
            intent = intents.get(iid)
            if not intent:
                continue
            for feature in _item_features(intent, item):
                # A feature has one outcome across every inventory item it references.
                evidence = _feature_rows(intent, feature, selected_by_intent[iid])
                slots = defaultdict(list)
                for r in evidence:
                    meta = provenance.get(r['file'], {})
                    slot = tuple(meta.get(k) for k in ('format', 'version', 'encoding'))
                    # Refusals without an output sidecar still identify a file slot.
                    slots[slot if any(slot) else r['file']].append(r)
                kept = sum(_status(rs) == 'kept' for rs in slots.values())
                status = _status(evidence)
                shared = any(r.get('shared_engine') for r in evidence)
                label = f'{status}: kept {kept} of {len(slots)} format/version/encoding slots (including not scored)'
                if shared:
                    label += ' · shared engine'
                native = iid in native_ids
                features.append(dict(intent_id=iid, feature=feature, native=native,
                                     round_trip=_cell(status, item, resaver, evidence, label,
                                                      pair, kept=kept, total=len(slots), shared_engine=shared)))
                if (iid, feature) not in summarized:
                    summarized.add((iid, feature))
                    summary['total'] += 1
                    summary_status = status
                    summary[summary_status if summary_status in ('kept', 'changed', 'lost', 'refused') else 'not_measured'] += 1
        if features:
            groups.append(dict(kind=item['kind'], name=item['name'], rows=features))
    summary['label'] = f"{summary['total']} features"
    return dict(declared=declared, label='measured' if selected else 'not measured', groups=groups, summary=summary)


def main_view_rows(root):
    intents, provenance, rows = _view_inputs(root)
    by_intent = defaultdict(list)
    for row in rows:
        by_intent[row.get('intent_id')].append(row)
    caps = read(root/'programs/capabilities.json')
    programs = []
    for pid, cap in caps.items():
        engine = cap.get('engine', pid)
        shared = sum(c.get('engine', p) == engine for p, c in caps.items()) > 1
        name = 'ODA File Converter' if pid == 'oda' else cap['name']
        programs.append(dict(id=pid, name=name, engine=engine, shared_engine=shared,
                             label=name + ' · ' + engine + (' · shared engine' if shared else '')))
    declarations = read(root/'programs/pairs.json')
    groups = []
    for kind in ('entity', 'object', 'table', 'header'):
        items = []
        for item in _inventory(root):
            if item['kind'] != kind:
                continue
            ids = item['dataset']['intents']
            relevant = _item_evidence(item, intents, [row for iid in ids for row in by_intent[iid]])
            cells = {}
            for program in programs:
                pid = program['id']
                reads = [r for r in relevant if r.get('intent_id') in ids and
                         str(r.get('reader', '')).split(' ')[0] == pid and r['status'] != 'not_scored']
                writes = [p for path, p in provenance.items() if path.startswith('native/' + pid + '/') and p.get('intent_id') in ids]
                pairs = {p['writer']+'__'+p['resaver'] for p in declarations if p['resaver'] == pid}
                evidence = [r for r in relevant if r.get('intent_id') in ids and
                            len(r['file'].split('/')) > 2 and r['file'].split('/')[0] == 'cross' and r['file'].split('/')[1] in pairs]
                measured = []
                for iid in ids:
                    intent = intents.get(iid, {})
                    for feature in _item_features(intent, item):
                        rs = _feature_rows(intent, feature, evidence)
                        if any(r['status'] != 'not_scored' for r in rs):
                            measured.append(_status(rs))
                kept, total = measured.count('kept'), len(measured)
                status = _status(evidence) if total else 'not measured'
                if total and kept == total:
                    status = 'kept'
                cells[pid] = dict(reads=_cell('measured' if reads else 'not measured', item, pid, reads),
                                  writes=_cell('native drawing' if writes else 'no native drawing', item, pid, writes),
                                  round_trip=_cell(status, item, pid, evidence,
                                                   f'kept {kept} of {total}' if total else 'not measured', kept=kept, total=total))
            dataset = _cell(item['dataset']['status'], item, '', [item['dataset']], intents=ids)
            items.append(dict(item, dataset=dataset, programs=cells))
        groups.append(dict(kind=kind, rows=items))
    return dict(programs=programs, groups=groups)


def _page_evidence(data):
    """Share compact evidence across cells; detailed runs retain expected/actual values."""
    # Small datasets retain inline evidence without a shared-table indirection.
    views = [data['main_view'], data['comparisons']]
    if len(json.dumps(views)) < 1_000_000:
        return
    rows, indices = [], {}

    def pack(node):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key == 'evidence':
                    refs = []
                    for row in value:
                        # Result cells show field identity and measurement provenance.
                        # Dataset and native-writing cells retain their own metadata.
                        compact = ({k: row[k] for k in
                                    ('intent_id', 'field', 'file', 'status', 'reader',
                                     'converter', 'shared_engine') if k in row}
                                   if 'file' in row else row)
                        signature = json.dumps(compact, sort_keys=True, ensure_ascii=False)
                        if signature not in indices:
                            indices[signature] = len(rows)
                            rows.append(compact)
                        refs.append(indices[signature])
                    # Consecutive evidence indices use inclusive ranges on disk.
                    spans = []
                    for index in refs:
                        if spans and index == spans[-1][1] + 1:
                            spans[-1][1] = index
                        else:
                            spans.append([index, index])
                    node[key] = ','.join(str(a) if a == b else f'{a}:{b}'
                                         for a, b in spans)
                else:
                    pack(value)
        elif isinstance(node, list):
            for value in node:
                pack(value)

    pack(data['main_view'])
    pack(data['comparisons'])
    # File and reader metadata is shared by the fields measured in that context.
    contexts, context_ids, fields, field_ids, packed = [], {}, [], {}, []
    for row in rows:
        if 'file' not in row:
            packed.append(row)
            continue
        context = {k: v for k, v in row.items() if k not in ('field', 'status')}
        signature = json.dumps(context, sort_keys=True)
        if signature not in context_ids:
            context_ids[signature] = len(contexts)
            contexts.append(context)
        field = row.get('field')
        if field not in field_ids:
            field_ids[field] = len(fields)
            fields.append(field)
        packed.append([context_ids[signature], field_ids[field], row['status']])
    data['evidence_rows'] = packed
    data['evidence_contexts'] = contexts
    data['evidence_fields'] = fields


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
    data = dict(main_view=main_view_rows(ROOT), comparisons={key: comparison_rows(p['writer'], p['resaver'], ROOT) for key, p in pairs.items()}, topics=topics, columns=columns, pairs=list(pairs), builds=sorted(builds), generated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    _page_evidence(data)
    from collections import Counter
    print('Coverage cells:', dict(Counter(c['coverage'] for t in topics for f in t['features'] for c in f['cells'])))
    template = (ROOT/'map/template.html').read_text()
    (ROOT/'map/index.html').write_text(template.replace('/*DATA*/',json.dumps(data,ensure_ascii=False,separators=(',', ':')).replace('<','\\u003c')))
    print(f'{len(topics)} topics; {sum(len(t["features"]) for t in topics)} features; {sum(map(len,checks.values()))} measured fields')

if __name__=='__main__':
    main()
