"""Attribute observations using source provenance and measured reading paths."""
from collections import defaultdict

BUCKETS = {'kept':'kept', 'changed':'changed', 'lost':'lost', 'refused':'refused',
           'source not readable':'source_not_readable',
           'lost in writer or converter':'writer_or_converter',
           'unreadable by reader':'unreadable_by_reader'}
ORDER = ['refused','lost in writer or converter','unreadable by reader',
         'source not readable','lost','changed','reader_error','not scored','kept']
RAW = {'same':'kept','differs':'changed','absent':'lost','not_scored':'not scored',
       'reader_error':'reader_error','refused':'refused'}

def outcome(rows):
    states = {r.get('attribution', RAW.get(r['status'], r['status'])) for r in rows}
    return next((s for s in ORDER if s in states), 'not measured')

def counts(states):
    result = dict.fromkeys(['total', *BUCKETS.values(), 'not_measured'], 0)
    for state in states:
        result['total'] += 1
        result[BUCKETS.get(state, 'not_measured')] += 1
    return result

class Attribution:
    def __init__(self, provenance, rows, declarations):
        self.provenance = provenance
        self.rows = rows
        self.declarations = {p['writer']+'__'+p['resaver']:p for p in declarations}
        self.dxf_kept = {(r["file"].split("/")[1],r.get("intent_id")) for r in rows
                         if r["file"].startswith("cross/") and r["status"]=="same" and not r.get("converter")
                         and provenance.get(r["file"],{}).get("format")=="DXF"}
        self.by_file = defaultdict(list)
        self.by_digest = defaultdict(list)
        for row in rows:self.by_file[row['file']].append(row)
        for path, meta in provenance.items():
            self.by_digest[meta.get('content_digest')].append((path,meta))

    def direct_summary(self, pair=None):
        """Count directly read DXF fields for headline fidelity figures."""
        selected = [r for r in self.rows if r['file'].startswith('cross/')
                    and r['file'].endswith('.dxf') and not r.get('converter')
                    and r['status']!='not_scored'
                    and (pair is None or r['file'].split('/')[1]==pair)]
        unique = {tuple(r.get(k) for k in ('file','field','reader','converter')):r for r in selected}
        return counts(outcome([self.attribute(r)]) for r in unique.values())

    def native_converter(self, rows):
        bad = []
        for row in rows:
            if not row.get('converter') or row['status'] not in ('absent','differs','reader_error'):continue
            direct = [r for r in self.by_file[row['file']] if r.get('field')==row.get('field')
                      and r.get('reader')==row.get('reader') and not r.get('converter') and r['status']=='same']
            if direct:bad.extend(direct+[row])
        return bad

    def attribute(self, row):
        result = dict(row)
        path = row['file'];parts = path.split('/')
        if len(parts)<3 or parts[0]!='cross' or row['status']=='not_scored':return result
        if row['status']=='refused' and row.get('field') in (None,'','open'):return result
        meta=self.provenance.get(path,{})
        declaration=self.declarations.get(parts[1],{})
        digest=meta.get('made_by',{}).get('input_digest')
        sources=[p for p,m in self.by_digest.get(digest,[]) if digest
                 and p.rsplit('/',1)[0]==declaration.get('sources')
                 and m.get('intent_id')==row.get('intent_id')
                 and m.get('version')==meta.get('version')
                 and (meta.get('format')!='DXF' or m.get('encoding')==meta.get('encoding'))]
        baseline=[r for p in sources for r in self.by_file[p]
                  if r.get('field')==row.get('field') and r.get('reader')==row.get('reader')]
        exact=[r for r in baseline if r.get('converter')==row.get('converter')]
        direct=[r for r in baseline if not r.get('converter')]
        candidates=exact or direct
        source=next((r for r in candidates if r['status']=='same'),next(iter(candidates),{}))
        if source.get('status')!='same':result['source_status']=source.get('status','not measured')
        # A measured converter failure takes precedence over an ineligible baseline.
        converter_bad=[r for r in exact if r['status'] in ('absent','differs','reader_error')]
        dxf_kept=(parts[1],row.get('intent_id')) in self.dxf_kept
        if row.get('converter') and row['status'] in ('absent','differs') and (converter_bad or (meta.get('format')=='DWG' and dxf_kept)):
            result['attribution']='lost in writer or converter'
        elif source.get('status')!='same':result['attribution']='source not readable'
        elif row['status']=='reader_error':result['attribution']='unreadable by reader'
        return result

def reading_label(status, rows):
    paths=sorted({r.get('reader','unspecified')+(' through '+r['converter'] if r.get('converter') else '') for r in rows})
    if status=='lost in writer or converter':
        return 'lost in writer or converter: lost in DWG write or DWG read (read through '+', '.join(paths)+')'
    if status=='unreadable by reader':return 'unreadable by '+', '.join(paths)
    return status
