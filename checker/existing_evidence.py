"""Offline contracts for saved integration evidence; never launches a CAD program."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def privacy():
    evidence=json.loads((ROOT/'results/privacy_evidence.json').read_text())
    for name in ['bricscad_neutralized','oda_neutralized','cadcraft']:
        rows=evidence[name]
        assert len(rows)==21 and sum(bool(r['written']) for r in rows)>10
        assert all(not r['hits'] for r in rows if r['written'])
        assert any(r['format']=='DWG' and r['version']=='2007' and r['written'] for r in rows)
    for name in ['bricscad_unneutralized','oda_unneutralized']:
        assert any(r['written'] and r['hits'] for r in evidence[name]), name
    from checker.verify_privacy import main
    main()

def volatile():
    for name,count in [('bricscad',16),('cadcraft',12)]:
        evidence=json.loads((ROOT/f'results/{name}_digest_evidence.json').read_text())
        assert evidence['build'] and (ROOT/evidence['input']).is_file()
        assert len(evidence['cases'])==count
        assert evidence['one_field_changes_digest'] and evidence['all_digests_equal']
        assert all(c['digests_equal'] for c in evidence['cases'])
        assert all(c['header_changes'] for c in evidence['cases'])
        assert {c['format'] for c in evidence['cases']}=={'DXF','DWG'}
    print('Saved two-save digest and sensitivity evidence passed (no fresh CAD saves)')
