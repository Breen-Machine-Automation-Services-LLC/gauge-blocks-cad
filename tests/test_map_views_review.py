"""Regression cases from the WP6 independent review; no CAD or browser needed."""
import json
import re
import shutil
import subprocess
from collections import Counter
from urllib.parse import parse_qs, urlsplit

import pytest

from test_map_views import ROOT, builder, corpus, comparison, main_rows, write_json


def rows(data):
    return [row for group in data['groups'] for row in group['rows']]


def assert_summary_matches_rows(data):
    # A feature may appear under several items, but has one summary outcome.
    statuses = {}
    for row in rows(data):
        key = (row['intent_id'], row['feature'])
        status = row['round_trip']['status']
        assert key not in statuses or statuses[key] == status
        statuses[key] = status
    counts = Counter(statuses.values())
    summary = data['summary']
    assert summary['total'] == len(statuses)
    for status, key in [('kept', 'kept'), ('changed', 'changed'), ('lost', 'lost'),
                        ('refused', 'refused')]:
        assert summary[key] == counts[status]
    assert summary['not_measured'] == counts['not measured'] + counts['not scored']


@pytest.mark.parametrize('field', ['open', ''])
def test_refused_open_reaches_all_features_in_both_views(builder, corpus, field):
    path = 'cross/ezdxf__cadcraft/text_2000.dxf'
    for result in (corpus / 'results').glob('*checks.json'):
        data = json.loads(result.read_text())
        write_json(corpus, result.relative_to(corpus), [r for r in data if r['file'] != path])
    refusal = dict(file=path, intent_id='text', field=field, status='refused',
                   expected=None, actual=None, reader='ezdxf synthetic-public',
                   converter=None, error='Synthetic open refusal')
    write_json(corpus, 'results/refusal_checks.json', [refusal])
    main = next(r for r in rows(main_rows(builder, corpus)) if r['name'] == 'TEXT')
    cell = main['programs']['cadcraft']['round_trip']
    assert cell['status'] == 'refused'
    assert refusal in cell['evidence']
    text_rows = [r for r in rows(comparison(builder, corpus)) if r['intent_id'] == 'text']
    assert len(text_rows) == 5
    for row in text_rows:
        assert row['round_trip']['status'] == 'refused'
        assert refusal in row['round_trip']['evidence']
        assert row['round_trip']['total'] == 2


def test_summary_counts_displayed_item_filtered_status(builder, corpus):
    # One feature spans two standard items, and another feature is unique to TEXT.
    inventory = json.loads((corpus / 'standard/dxf-inventory.json').read_text())
    text = next(i for i in inventory if i['name'] == 'TEXT')
    layer = next(i for i in inventory if i['name'] == 'LAYER')
    layer['dataset']['intents'].append('text')
    write_json(corpus, 'standard/dxf-inventory.json', inventory)
    intent = json.loads((corpus / 'intent/text.json').read_text())
    intent['features'] = ['Spanning', 'Text only']
    intent['feature_fields'] = {'Spanning': ['align', 'color2'], 'Text only': ['fit']}
    intent['expected'] = [dict(e, reference=dict(e['reference'], url=layer['reference_url']))
                          if e['id'] == 'width' else e for e in intent['expected']
                          if e['id'] in ('align', 'width', 'fit')]
    next(e for e in intent['expected'] if e['id'] == 'width')['id'] = 'color2'
    write_json(corpus, 'intent/text.json', intent)
    for result in (corpus / 'results').glob('*checks.json'):
        data = json.loads(result.read_text())
        for r in data:
            if r['intent_id'] == 'text' and r['field'] == 'width':
                r['field'] = 'color2'
                if 'ezdxf__cadcraft' in r['file']:
                    r['status'] = 'differs'
        write_json(corpus, result.relative_to(corpus), data)
    data = comparison(builder, corpus)
    text_group = next(g for g in data['groups'] if g['name'] == text['name'])
    layer_group = next(g for g in data['groups'] if g['name'] == layer['name'])
    # The same feature must have the same displayed outcome wherever it appears.
    assert next(r for r in text_group['rows'] if r['feature'] == 'Spanning')['round_trip']['status'] == 'changed'
    assert next(r for r in layer_group['rows'] if r['feature'] == 'Spanning')['round_trip']['status'] == 'changed'
    assert_summary_matches_rows(data)


def test_repository_comparison_refusals_and_summary_reconcile(builder):
    data = comparison(builder, ROOT)
    assert data['summary']['refused'] >= 1
    assert_summary_matches_rows(data)


def test_duplicate_item_names_have_unique_links_and_filter_details(builder, corpus):
    inventory = json.loads((corpus / 'standard/dxf-inventory.json').read_text())
    for kind, original in [('entity', 'TEXT'), ('object', 'LAYER')]:
        source = next(i for i in inventory if i['name'] == original)
        inventory.append(dict(source, kind=kind, name='SECTION'))
    write_json(corpus, 'standard/dxf-inventory.json', inventory)
    main = main_rows(builder, corpus)
    sections = {g['kind']: next(r for r in g['rows'] if r['name'] == 'SECTION')
                for g in main['groups'] if any(r['name'] == 'SECTION' for r in g['rows'])}
    links = {kind: row['programs']['cadcraft']['round_trip']['detail_link']
             for kind, row in sections.items()}
    assert links['entity'] != links['object']
    comp = comparison(builder, corpus)
    groups = [g for g in comp['groups'] if g['name'] == 'SECTION']
    for group in groups:
        for row in group['rows']:
            comparison_query = parse_qs(urlsplit(row['round_trip']['detail_link']).fragment.partition('?')[2])
            main_query = parse_qs(urlsplit(links[group['kind']]).fragment.partition('?')[2])
            assert all(comparison_query.get(key) == value for key, value in main_query.items())
    # Execute the page's actual filter against the builder's duplicate-name payload.
    node = shutil.which('node')
    assert node, 'Node.js is required to exercise the detailed-view filter without a browser'
    template = (ROOT / 'map/template.html').read_text()
    match = re.search(r'function detailFeatures\(topic\)\s*\{.*?\n\}', template, re.S)
    assert match, 'detailed view must provide a feature filter'
    script = '''const DATA = %s;
let detailFilter;
%s
for (const [kind, link] of Object.entries(%s)) {
  detailFilter = new URLSearchParams(link.split('?')[1]);
  const topic = {id:'text', features:[{name:'Aligned'}, {name:'Fit'}]};
  const got = detailFeatures(topic).map(f => f.name);
  if (kind === 'entity' && got.length !== 2) process.exit(1);
  if (kind === 'object' && got.length !== 0) process.exit(2);
}
''' % (json.dumps({'comparisons': {'pair': comp}, 'main_view': main}), match.group(), json.dumps(links))
    subprocess.run([node, '-e', script], check=True, capture_output=True, text=True)
