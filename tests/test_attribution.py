# Expected functions: checker.core.decode_sat_records(tags), applicable_fields(intent,
# version, encoding); compare accepts source_version and source_encoding;
# checker.scoring.applicable_fields is the same rule; map.build.main_view_rows(root)
# and comparison_rows(writer, resaver, root) are read-only builders.
"""WP8 acceptance tests: independent intents and synthetic observations; no CAD.

Proposed contract: decode_sat_records joins group 3 continuations to group 1
records and returns decoded SAT lines. applicable_fields returns expected-field
objects. Version means the source DXF AC code, encoding means ASCII/binary;
optional field encodings restrict applicability, omission permits both.

Map contract extends WP6: source_not_readable and writer_or_converter are
separate feature summary buckets. Main round_trip cells expose the same counts
as a summary (total counts distinct features). Evidence retains source_status
on baseline-ineligible slots. Labels use spaces, summary keys underscores.
Source matching uses input_digest, reader and converter, never filename alone.
These schema choices are explicit proposals where the draft spec is silent.
"""
import json
from collections import Counter, defaultdict

import ezdxf
import pytest
from ezdxf.lldxf.types import DXFTag

from checker import core, scoring
from test_map_views import ROOT, builder, write_json, item_rows, features


@pytest.mark.parametrize('padded', [False, True], ids=['unpadded', 'padded'])
def test_sat_raw_records_preserve_characters_and_join_continuations(padded):
    # Hand-authored ciphertext, not ezdxf.encode output: "ACIS Builder" and
    # "Alliance". '^' encodes A; only the padded representation adds a space.
    a = '^ ' if padded else '^'
    tags = [DXFTag(100, 'AcDbModelerGeometry'), DXFTag(70, 1),
            DXFTag(1, a + '\\VL '), DXFTag(3, ']*63;:-'),
            DXFTag(1, a + '336>1<:'), DXFTag(8, 'ignored')]
    decode = getattr(core, 'decode_sat_records', None)
    assert callable(decode), 'WP8 requires raw-tag SAT decoding'
    assert list(decode(tags)) == ['ACIS Builder', 'Alliance']


@pytest.mark.parametrize('attr', ['acis_body_count', 'acis_bbox_size'])
def test_real_unpadded_binary_sat_uses_independent_intent(attr):
    intent = json.loads((ROOT / 'intent/future_k_regions_solids.json').read_text())
    expected = next(f for f in intent['expected']
                    if f['id'] == 'F154_solid3d.' + attr)
    doc = ezdxf.readfile(ROOT / 'native/bricscad/k_regions_solids_2000_binary.dxf')
    # Do not audit: the content must be consumed as read.
    actual = core.extract(doc, expected['selector'])
    assert actual == pytest.approx(expected['value'], abs=expected['tolerance'])


@pytest.mark.parametrize('version,encoding,ids', [
    ('AC1015', 'ASCII', ['both', 'ascii']),
    ('AC1015', 'binary', ['both', 'binary']),
    ('AC1032', 'binary', ['later']),
    ('AC1009', 'ASCII', []),
])
def test_native_and_cross_share_applicability(version, encoding, ids):
    fields = [dict(id=name, versions=versions, value=0, tolerance=0,
                   selector=dict(kind='query_count', name='LINE'), **extra)
              for name, versions, extra in [
                  ('both', ['AC1015'], {}),
                  ('ascii', ['AC1015'], {'encodings': ['ASCII']}),
                  ('binary', ['AC1015'], {'encodings': ['binary']}),
                  ('later', ['AC1032'], {})]]
    intent = dict(intent_id='synthetic', expected=fields)
    rule = getattr(core, 'applicable_fields', None)
    assert callable(rule), 'WP8 requires one applicability rule'
    assert getattr(scoring, 'applicable_fields', None) is rule
    assert [f['id'] for f in rule(intent, version, encoding)] == ids
    for doc_version in ('R2000', 'R2018'):
        rows = core.compare(ezdxf.new(doc_version), intent, 'ezdxf synthetic',
                            source_version=version, source_encoding=encoding)
        assert [r['field'] for r in rows] == ids
        assert all(r['status'] == 'same' for r in rows)


def test_repository_cross_scored_fields_have_scored_native_source_at_same_slot():
    provenance = {}
    for folder in ('native', 'cross'):
        for p in (ROOT / folder).rglob('*.provenance.json'):
            provenance[p.relative_to(ROOT).as_posix()[:-len('.provenance.json')]] = json.loads(p.read_text())
    rows = []
    for p in (ROOT / 'results').glob('*checks.json'):
        data = json.loads(p.read_text())
        if isinstance(data, list):
            rows.extend(data)
    scored = {'same', 'differs', 'absent'}
    native = {(r['file'], r['field']) for r in rows
              if r['file'].startswith('native/') and r['status'] in scored}
    sources_by_digest = defaultdict(list)
    for path, meta in provenance.items():
        if path.startswith('native/'):
            sources_by_digest[(path.split('/')[1], meta.get('content_digest'))].append((path, meta))
    native_pairs = {p['writer'] + '__' + p['resaver']
                    for p in json.loads((ROOT / 'programs/pairs.json').read_text())
                    if p['sources'].startswith('native/')}
    violations, checked = [], 0
    for row in rows:
        path = row['file']
        if not path.startswith('cross/') or row['status'] not in scored:
            continue
        # Chained pairs have a cross source rather than a native baseline.
        if path.split('/')[1] not in native_pairs:
            continue
        meta = provenance.get(path)
        assert meta is not None, path
        writer = path.split('/')[1].split('__')[0]
        digest = meta.get('made_by', {}).get('input_digest')
        sources = [(p, m) for p, m in sources_by_digest[(writer, digest)]
                   if m['intent_id'] == meta['intent_id'] and m['version'] == meta['version']]
        # DWG is binary regardless of the input DXF encoding. Match the actual
        # source digest first, then its version/encoding, not the output suffix.
        if meta['format'] == 'DXF':
            sources = [(p, m) for p, m in sources if m['encoding'] == meta['encoding']]
        checked += 1
        if not sources or not any((p, row['field']) in native for p, _ in sources):
            violations.append((path, row['field'], [(p, m['version'], m['encoding']) for p, m in sources]))
    assert checked > 0
    assert not violations, f'{len(violations)} cross fields lack a scored source: {violations[:20]}'


@pytest.fixture
def attribution_corpus(tmp_path):
    root = tmp_path
    url = 'https://example.invalid/reference/PROXY'
    write_json(root, 'standard/dxf-inventory.json', [dict(kind='entity', name='PROXY',
               reference_url=url, dataset=dict(status='included', intents=['synthetic']))])
    write_json(root, 'programs/capabilities.json', {
        p: dict(name=p, engine=p, outputs=[]) for p in ('ezdxf', 'cadcraft', 'oda')})
    write_json(root, 'programs/pairs.json', [dict(writer='ezdxf', resaver=p, sources='native/ezdxf')
                                          for p in ('cadcraft', 'oda')])
    return root, url


def populate(corpus, cases):
    root, url = corpus
    expected, mapping, rows = [], {}, []
    for index, case in enumerate(cases):
        field = 'field_' + str(index)
        mapping[field] = [field]
        expected.append(dict(id=field, value=7, tolerance=0, versions=['AC1015'],
                             reference=dict(url=url, basis_type='synthetic')))
        native = f'native/ezdxf/synthetic_{index}_2000_ASCII.dxf'
        source_meta = dict(intent_id='synthetic', program='ezdxf', format='DXF',
                           version='2000', encoding='ASCII', content_digest=f'digest-{index}')
        write_json(root, native + '.provenance.json', source_meta)

        def observation(path, status, converter=None, reader='ezdxf synthetic-public'):
            return dict(file=path, intent_id='synthetic', field=field, expected=7,
                        actual=7 if status == 'same' else None, status=status,
                        reader=reader, converter=converter)

        if case['source'] is not None:
            rows.append(observation(native, case['source'], reader=case.get('source_reader', 'ezdxf synthetic-public')))
        fmt = case.get('format', 'DXF')
        target = f'cross/ezdxf__cadcraft/synthetic_{index}_2000.{fmt.lower()}'
        meta = dict(source_meta, program='cadcraft', format=fmt,
                    encoding='binary' if fmt == 'DWG' else 'ASCII',
                    made_by=dict(input_digest=case.get('digest', f'digest-{index}')))
        write_json(root, target + '.provenance.json', meta)
        converter = 'oda synthetic-public' if fmt == 'DWG' else None
        rows.append(observation(target, case['cross'], converter))
        if fmt == 'DWG':
            direct = target[:-4] + '.dxf'
            write_json(root, direct + '.provenance.json', dict(meta, format='DXF', encoding='ASCII'))
            rows.append(observation(direct, 'same'))
            # Same reader-converter loses the proxy on the converter's own save.
            control = f'cross/ezdxf__oda/synthetic_{index}_2000.dwg'
            write_json(root, control + '.provenance.json', dict(meta, program='oda'))
            rows.append(observation(control, 'absent', converter))
    write_json(root, 'intent/synthetic.json', dict(intent_id='synthetic', title='Synthetic',
               features=list(mapping), feature_fields=mapping, expected=expected))
    write_json(root, 'results/fixture_checks.json', rows)
    return root


def cells(builder, root):
    comparison = builder.comparison_rows('ezdxf', 'cadcraft', root)
    main = item_rows(builder.main_view_rows(root))['PROXY']['programs']['cadcraft']['round_trip']
    return comparison, main


@pytest.mark.parametrize('source,cross,status', [
    ('same', 'same', 'kept'), ('same', 'differs', 'changed'),
    ('same', 'absent', 'lost'), ('same', 'refused', 'refused'),
    ('absent', 'absent', 'source not readable'),
    ('differs', 'absent', 'source not readable'),
    ('not_scored', 'absent', 'source not readable'),
    ('refused', 'absent', 'source not readable'),
    (None, 'absent', 'source not readable'),
    ('absent', 'same', 'source not readable'),
])
def test_baseline_relative_status_in_both_views(builder, attribution_corpus, source, cross, status):
    root = populate(attribution_corpus, [dict(source=source, cross=cross)])
    comparison, main = cells(builder, root)
    rt = features(comparison)[('synthetic', 'field_0')]['round_trip']
    for cell in (rt, main):
        assert cell['status'] == status
        assert cell['total'] == 1
        assert cell['kept'] == int(status == 'kept')
        assert status in cell['label']
        if status == 'source not readable':
            evidence = next(r for r in cell['evidence'] if r['file'].startswith('cross/'))
            assert evidence['source_status'] == (source or 'not measured')
    key = 'source_not_readable' if status == 'source not readable' else status
    assert comparison['summary'][key] == 1
    assert comparison['summary']['total'] == 1


@pytest.mark.parametrize('override', [dict(source_reader='other synthetic-public'), dict(digest='unmatched')])
def test_unmatched_source_cannot_authorize_loss(builder, attribution_corpus, override):
    root = populate(attribution_corpus, [dict(source='same', cross='absent', **override)])
    comparison, main = cells(builder, root)
    assert main['status'] == 'source not readable'
    assert features(comparison)[('synthetic', 'field_0')]['round_trip']['status'] == 'source not readable'


def test_source_bucket_and_totals_reconcile_in_both_views(builder, attribution_corpus):
    root = populate(attribution_corpus, [dict(source=s, cross=c) for s, c in [
        ('same', 'same'), ('same', 'differs'), ('same', 'absent'),
        ('same', 'refused'), ('absent', 'absent')]])
    comparison, main = cells(builder, root)
    counts = Counter(r['round_trip']['status'] for r in features(comparison).values())
    expected = dict(kept=1, changed=1, lost=1, refused=1, source_not_readable=1,
                    writer_or_converter=0, not_measured=0)
    for summary in (comparison['summary'], main):
        assert {key: summary[key] for key in expected} == expected
        assert summary['total'] == sum(summary[key] for key in expected) == 5
    assert counts == Counter({'kept': 1, 'changed': 1, 'lost': 1, 'refused': 1, 'source not readable': 1})


def test_dwg_only_loss_has_reading_path_and_its_own_bucket(builder, attribution_corpus):
    root = populate(attribution_corpus, [dict(source='same', cross='same'),
                                       dict(source='same', cross='absent', format='DWG')])
    comparison, main = cells(builder, root)
    rt = features(comparison)[('synthetic', 'field_1')]['round_trip']
    assert rt['status'] == 'lost in writer or converter'
    for cell in (rt, main):
        assert 'ezdxf synthetic-public' in cell['label']
        assert 'oda synthetic-public' in cell['label']
        assert any(r['converter'] == 'oda synthetic-public' for r in cell['evidence'])
    for summary in (comparison['summary'], main):
        assert summary['lost'] == 0
        assert summary['writer_or_converter'] == 1
        assert summary['kept'] == 1
        assert summary['total'] == 2
