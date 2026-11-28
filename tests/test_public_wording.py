"""WP9 acceptance tests: public wording of statuses, gaps and coverage.

Written before the implementation. Where the spec leaves the exact words to the
implementer these tests check behavior (no repeated phrase, each program and
version named once, no exception class, cause words present), not sentences.
Nothing here launches a CAD program or a browser, and nothing writes into the
repository: pages are built into temporary directories that link the committed
inputs read-only.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from test_attribution_gaps import READER, acis_corpus, acis_intent, ACIS_FILE
from test_map_views import ROOT, builder, features, item_rows, write_json
from test_drawing_inputs import tree, harness
from test_runner_plans import corpus, plan, run
from test_runner_plans_review import forget_outputs

# Internal status vocabulary that must never reach a reader.
INTERNAL_KEYS = ('reader_error', 'not_scored', 'round_trip', 'read_observation', 'source_status',
                 'shared_engine', 'self_read', 'not_measured', 'source_not_readable',
                 'writer_or_converter', 'unreadable_by_reader', 'lost_by_converter')
KEY_PATTERN = re.compile(r'(?<![A-Za-z0-9_/.\-])(' + '|'.join(INTERNAL_KEYS) + r')(?![A-Za-z0-9_])')


# ---------------------------------------------------------------- helpers

class VisibleText(HTMLParser):
    """Text outside <script> and <style>, plus attribute text a reader can see."""

    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        for name, value in attrs:
            if name in ('title', 'aria-label', 'placeholder') and value:
                self.parts.append(value)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def split_page(page):
    from map.check_links import page_data
    data = page_data(page)
    script = re.search(r'<script>(.*)</script>', page, re.S).group(1)
    script = re.sub(r'const DATA_GZIP=.*?;\n', '', script, count=1)
    visible = VisibleText()
    visible.feed(page)
    return data, script, '\n'.join(visible.parts)


def script_prose(script):
    """String literals in the page script that read as prose (labels and method text)."""
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`", script):
        text = m.group(1) if m.group(1) is not None else m.group(2)
        if text.count(' ') >= 4:
            out.append(text)
    return out


def labels(node, path=''):
    """Every label-like display string in the page DATA (evidence stays internal)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ('evidence', 'evidence_rows', 'evidence_contexts', 'evidence_fields', 'diffs'):
                continue
            if key in ('label', 'missing', 'impossible') or key.endswith('_label'):
                for text in (value if isinstance(value, list) else [value]):
                    if isinstance(text, str):
                        yield path + '/' + key, text
            else:
                yield from labels(value, path + '/' + key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from labels(value, path + f'[{i}]')


def find_tables(node, key, value, path=''):
    """Paths of every dict in node that maps `key` to `value`."""
    if isinstance(node, dict):
        if node.get(key) == value:
            yield path
        for k, v in node.items():
            yield from find_tables(v, key, value, path + '/' + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from find_tables(v, key, value, path + f'[{i}]')


def repeated_phrase(text):
    """A word pair that occurs twice in one label signals a repeated phrase."""
    words = re.findall(r"[A-Za-z0-9_.\-]+", text.lower())
    pairs = [' '.join(words[i:i + 2]) for i in range(len(words) - 1)]
    return sorted({p for p in pairs if pairs.count(p) > 1})


def run_main(builder_module, root):
    with contextlib.redirect_stdout(io.StringIO()):
        builder_module.main()


def link_inputs(root):
    """Temporary repository: committed inputs linked read-only, outputs written here."""
    for name in ('intent', 'native', 'cross', 'results', 'programs', 'standard'):
        (root / name).symlink_to(ROOT / name, target_is_directory=True)
    (root / 'map').mkdir()
    shutil.copy(ROOT / 'map/template.html', root / 'map/template.html')
    return root


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    """Map page and COVERAGE.md built from the committed results into a temporary directory."""
    import importlib.util
    root = link_inputs(tmp_path_factory.mktemp('wp9_build'))
    spec = importlib.util.spec_from_file_location('wp9_build_map', ROOT / 'map/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from generators import write_coverage
    patch = pytest.MonkeyPatch()
    try:
        patch.setattr(module, 'ROOT', root)
        patch.setattr(write_coverage, 'R', root)
        patch.setattr(write_coverage, 'build_map', module.main)
        with contextlib.redirect_stdout(io.StringIO()):
            write_coverage.main()
    finally:
        patch.undo()
    page = (root / 'map/index.html').read_text()
    data, script, visible = split_page(page)
    return dict(root=root, page=page, data=data, script=script, visible=visible,
                coverage=(root / 'COVERAGE.md').read_text(), template=(ROOT / 'map/template.html').read_text())


@pytest.fixture(scope='module')
def real_views():
    """Map views computed from the committed results; the builders are read-only."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('wp9_real_map', ROOT / 'map/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = module._view_inputs(ROOT)
    main = module.main_view_rows(ROOT, inputs)
    pairs = [p['writer'] + '__' + p['resaver'] for p in json.loads((ROOT / 'programs/pairs.json').read_text())]
    comparisons = {pair: module.comparison_rows(*pair.split('__'), ROOT, inputs) for pair in pairs}
    return dict(main=main, comparisons=comparisons)


# ------------------------------------------- requirement 1: one display table

def test_req1_page_carries_one_display_table(built):
    data = built['data']
    outcome = list(find_tables(data, 'reader_error', 'read failed'))
    coverage = list(find_tables(data, 'covered', 'measured'))
    assert outcome, 'the page DATA must carry the display table (reader_error -> read failed)'
    assert coverage, 'the page DATA must carry the coverage words (covered -> measured)'
    # defined once, not scattered: a single place holds the outcome words
    assert len(outcome) == 1, outcome
    top = outcome[0].strip('/').split('/')[0]
    assert re.search(r"DATA(\.%s\b|\[['\"]%s['\"]\])" % (top, top), built['script']), \
        'the page script must read the display table from DATA'


def test_req1_script_no_longer_hardcodes_raw_status_in_filters_or_legends(built):
    script = built['script']
    # The old filter options and legend entries printed the internal key directly.
    assert '<option>${s}</option>' not in script
    assert '${swatch(s)} ${s}</span>' not in script
    assert 'feature cells ${s}' not in script


def test_req1_visible_page_text_has_no_status_keys(built):
    found = KEY_PATTERN.findall(built['visible'])
    assert not found, sorted(set(found))


def test_req1_page_labels_in_data_have_no_status_keys(built):
    bad = [(p, t) for p, t in labels(built['data']) if KEY_PATTERN.search(t)]
    assert not bad, bad[:5]


def test_req1_script_prose_and_method_text_have_no_status_keys(built):
    bad = [t for t in script_prose(built['script']) if KEY_PATTERN.search(t)]
    assert not bad, bad[:3]


def test_req1_coverage_md_has_no_status_keys(built):
    found = KEY_PATTERN.findall(built['coverage'])
    assert not found, sorted(set(found))


def test_req1_coverage_md_uses_the_same_words_as_the_page(built):
    text = built['coverage']
    section = text.split('## Cell status counts')[1].split('\n## ')[0]
    rows = {line.split('|')[1].strip() for line in section.splitlines()
            if line.startswith('| ') and not line.startswith('| Status') and not line.startswith('| Intent')}
    assert {'measured', 'partly measured'} <= rows, rows
    assert not {'covered', 'partial'} & rows, rows
    # intent status table uses the same words
    intent_rows = [line.split('|') for line in text.splitlines()
                   if re.match(r'\| \[[a-z0-9_]+\]\(intent/', line)]
    statuses = {r[3].strip() for r in intent_rows}
    assert statuses and not {'covered', 'partial'} & statuses, statuses
    assert not re.search(r'^\| covered \|', text, re.M)


# ------------------------------------------------------ requirement 2: words

@pytest.mark.parametrize('key,words', [('reader_error', 'read failed'), ('not_scored', 'not scored')])
def test_req2_outcome_words(built, key, words):
    paths = list(find_tables(built['data'], key, words))
    assert paths, f'{key} must display as {words!r}'


@pytest.mark.parametrize('key,words', [('covered', 'measured'), ('partial', 'partly measured')])
def test_req2_coverage_words(built, key, words):
    assert list(find_tables(built['data'], key, words)), f'coverage {key} must display as {words!r}'


def test_req2_other_statuses_keep_current_words(built):
    table_path = next(find_tables(built['data'], 'reader_error', 'read failed')).strip('/').split('/')
    table = built['data']
    for part in table_path:
        table = table[part]
    for key, words in table.items():
        if key == 'reader_error':
            continue
        assert words == key.replace('_', ' '), (key, words)
    # The standard-inventory dataset status "partial" (item tested in part) is a different
    # vocabulary from coverage "partial" and keeps its word.
    assert table.get('partial') == 'partial'
    # Coverage statuses have their own words; the two renamed ones differ, the rest are unchanged.
    coverage_path = next(find_tables(built['data'], 'covered', 'measured')).strip('/').split('/')
    coverage = built['data']
    for part in coverage_path:
        coverage = coverage[part]
    assert coverage['covered'] == 'measured' and coverage['partial'] == 'partly measured'
    for key, words in coverage.items():
        if key not in ('covered', 'partial'):
            assert words == key.replace('_', ' '), (key, words)


def test_req2_coverage_method_text_defines_measured(built):
    texts = [t for t in script_prose(built['script']) if 'source folder' in t]
    assert texts, 'coverage method text must say what measured means'
    text = ' '.join(texts).lower()
    assert 'measured' in text
    assert re.search(r'whether or not[^.]*loss', text), text
    assert 'declared' in text and 'source folder' in text
    assert 'covered requires' not in text


# --------------------------------- requirement 3: read failure cells (Reads)

CAUSE_WORDS = ('SAT', 'binary DXF', 'Teigha', 'R2000 to R2010')


@pytest.mark.parametrize('item', ['3DSOLID', 'REGION'])
def test_req3_known_cause_read_failure_label(real_views, item):
    cell = item_rows(real_views['main'])[item]['programs']['ezdxf']['reads']
    label = cell['label']
    assert label.startswith('read failed'), label
    assert len(re.findall(r'\bezdxf\b', label)) == 1, label
    assert len(re.findall(r'\d+\.\d+\.\d+', label)) == 1, label
    for word in CAUSE_WORDS:
        assert word in label, (word, label)
    assert not re.search(r'\w*Error\b|\w*Exception\b|list index', label), label
    assert not repeated_phrase(label), repeated_phrase(label)
    # the exception text stays available in the evidence panel
    assert 'IndexError' in json.dumps(cell['evidence'])


def test_req3_read_failure_without_known_cause(builder, tmp_path):
    intent = acis_intent()
    rows = []
    cross = 'cross/bricscad__oda/k_regions_solids_2000_binary.dxf'
    for file in (ACIS_FILE, cross):
        for f in intent['expected']:
            row = dict(file=file, intent_id=intent['intent_id'], field=f['id'], reader=READER,
                       converter=None, status='same', expected=f['value'], actual=f['value'])
            if f['selector'].get('attr', '').startswith('acis_'):
                row['read_observation'] = dict(reader=READER, status='reader_error', actual=None,
                                               detail=READER + ' ValueError: synthetic unexplained defect')
            rows.append(row)
    acis_corpus(tmp_path, rows)
    cell = item_rows(builder.main_view_rows(tmp_path))['3DSOLID']['programs']['ezdxf']['reads']
    assert cell['status'] == 'reader_error'
    assert cell['label'] == 'read failed: ' + READER, cell['label']
    assert 'ValueError' in json.dumps(cell['evidence'])


# ---------------------------------------------- requirement 4: round trip labels

def loss_labels(real_views):
    out = []
    for row in item_rows(real_views['main']).values():
        for program, cells in row['programs'].items():
            out.append((f"main {row['name']} {program}", cells['round_trip']))
    for pair, data in real_views['comparisons'].items():
        for group in data['groups']:
            for r in group['rows']:
                out.append((f"comparison {pair} {group['name']} {r['feature']}", r['round_trip']))
    return [(n, c) for n, c in out if 'lost' in c['label'] and 'DWG' in c['label']]


def main_rt(real_views, item, program):
    return item_rows(real_views['main'])[item]['programs'][program]['round_trip']


def test_req4_no_phrase_repeats_in_any_round_trip_label(real_views):
    cells = loss_labels(real_views)
    assert cells, 'the committed results contain DWG loss cells'
    bad = {name: repeated_phrase(c['label']) for name, c in cells if repeated_phrase(c['label'])}
    assert not bad, dict(list(bad.items())[:3])


def test_req4_each_program_version_named_once(real_views):
    for name, cell in loss_labels(real_views):
        label = cell['label']
        versions = re.findall(r'\d+\.\d+\.\d+[\w.\-]*', label)
        assert len(versions) == len(set(versions)), (name, label)
        assert len(re.findall(r'\bezdxf\b', label)) <= 1, (name, label)


def test_req4_3dsolid_round_trip_through_oda(real_views):
    label = main_rt(real_views, '3DSOLID', 'cadcraft')['label']
    assert re.search(r'kept 0 of 1 measured feature\b', label), label
    assert 'ezdxf 1.4.4' in label and label.count('ezdxf') == 1
    assert 'ODA File Converter 27.1.0.143450' in label and label.count('27.1.0.143450') == 1
    assert label.count('lost in') == 1 and 'DWG write' in label and 'DWG read' in label
    assert not repeated_phrase(label)


@pytest.mark.parametrize('program,reader_program,version', [('oda', 'BricsCAD', '26.2.07-1'),
                                                              ('bricscad', 'ODA File Converter', '27.1.0.143450')])
def test_req4_proxy_entity_round_trip_cells(real_views, program, reader_program, version):
    label = main_rt(real_views, 'ACAD_PROXY_ENTITY', program)['label']
    assert re.search(r'kept 0 of 2 measured features\b', label), label
    assert label.count('ezdxf') == 1 and label.count('1.4.4') == 1
    assert reader_program in label and label.count(version) == 1, label
    assert label.count('lost in') == 1 and not repeated_phrase(label)


def test_req4_counted_noun_follows_count_and_page_does_not_append_it_again(real_views, built):
    for row in item_rows(real_views['main']).values():
        for cells in row['programs'].values():
            cell = cells['round_trip']
            if cell['total']:
                noun = 'feature' if cell['total'] == 1 else 'features'
                assert re.search(rf"kept {cell['kept']} of {cell['total']} measured {noun}\b", cell['label']), cell['label']
    assert "' measured features'" not in built['template'], \
        'the label already carries the noun; the template must not append it a second time'


# --------------------------------------------------- requirement 5: gap reasons

@pytest.mark.parametrize('excluded', [('DXF', '2000', 'binary'), ('DXF', '2000', 'ASCII')])
def test_req5_gap_reason_names_program_and_missing_output(corpus, monkeypatch, excluded):
    h = corpus
    path = h.root / 'programs/capabilities.json'
    caps = json.loads(path.read_text())
    display = caps['oda']['name']
    caps['oda']['outputs'] = [o for o in caps['oda']['outputs'] if tuple(o) != excluded]
    path.write_text(json.dumps(caps))
    adapter = h.cross.ADAPTERS['oda']
    original = adapter.save_many
    sent = []

    def save(self, jobs):
        sent.extend(jobs)
        return original(self, jobs)
    monkeypatch.setattr(adapter, 'save_many', save)
    forget_outputs(h, 'cross')
    run(h, 'cross')
    gaps = sorted('ezdxf__oda|' + dest.relative_to(h.root).as_posix()
                  for _, dest, fmt, version, enc, _ in h.cross.jobs_for('ezdxf__oda', root=h.root)
                  if (fmt, version, enc) == excluded)
    assert gaps, 'fixture must contain an output of the excluded tuple'
    recorded = json.loads((h.root / 'results/cross_not_run.json').read_text())
    assert sorted(recorded) == gaps
    sentence = ' '.join(excluded)
    accepted = {f'{name} does not write {sentence}' for name in (display, 'ODA File Converter')}
    for key in gaps:
        assert recorded[key] in accepted, recorded[key]
        assert 'Undeclared' not in recorded[key]
    assert not [j for j in sent if (j[2], j[3], j[4]) == excluded], 'a gap is never sent to the program'


# ------------------------------------- requirement 6: no test rewrites a tracked file

def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout


def test_req6_phase2_check_leaves_the_working_tree_unchanged(tmp_path):
    """Run checker/test_phase2.py in a throwaway repository whose tracked evidence file differs
    from what the script would write, so any rewrite shows in git status."""
    shutil.copytree(ROOT / 'checker', tmp_path / 'checker', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'intent', tmp_path / 'intent')
    (tmp_path / 'results').mkdir()
    for name in ('features_checks.json', 'features_audits.json'):
        shutil.copy(ROOT / 'results' / name, tmp_path / 'results' / name)
    (tmp_path / 'results/phase2_verification.json').write_text('{"committed": "sentinel"}\n')
    (tmp_path / 'map').mkdir()
    for name in ('index.html', 'check_links.py'):
        shutil.copy(ROOT / 'map' / name, tmp_path / 'map' / name)
    for name in ('README.md', 'CONTRIBUTING.md', 'OPEN-ITEMS.md', 'COVERAGE.md'):
        shutil.copy(ROOT / name, tmp_path / name)
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'add', '-A')
    before = git(tmp_path, 'status', '--porcelain')
    snapshot = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*')
                if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
    result = subprocess.run([sys.executable, '-I', str(tmp_path / 'checker/test_phase2.py')], cwd=tmp_path,
                            capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stdout[-500:] + result.stderr[-1500:]
    after = git(tmp_path, 'status', '--porcelain')
    changed = sorted(str(p) for p, data in snapshot.items() if (tmp_path / p).read_bytes() != data)
    assert after == before and not changed, f'tracked files rewritten: {changed}'
    assert result.stdout.strip(), 'the evidence goes to standard output'


# ----------------------- requirement 8: every derived file rebuilt, stale one fails

def derived_copy(tmp_path):
    """Throwaway repository: code and derived files copied, large inputs linked."""
    for name in ('checker', 'generators', 'programs', 'map'):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns('__pycache__', 'screens'))
    for name in ('intent', 'standard', 'native', 'cross', 'placeholders'):
        if (ROOT / name).exists():
            (tmp_path / name).symlink_to(ROOT / name, target_is_directory=True)
    for name in ('regenerate.py', 'settings.example.json', 'README.md', 'CONTRIBUTING.md', 'OPEN-ITEMS.md',
                 'COVERAGE.md', 'SIZE.md', 'measure_size.py'):
        if (ROOT / name).exists():
            shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / 'results').mkdir()
    for p in (ROOT / 'results').iterdir():
        if p.name == 'cross_summary.json':
            shutil.copy(p, tmp_path / 'results' / p.name)
        elif p.is_file():
            (tmp_path / 'results' / p.name).symlink_to(p)
    return tmp_path


def check_artifacts(root):
    return subprocess.run([sys.executable, '-I', str(root / 'checker/check_artifacts.py')], cwd=root,
                          capture_output=True, text=True, timeout=900,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})


def edit_coverage(root):
    p = root / 'COVERAGE.md'
    p.write_text(p.read_text() + '\nEdited by hand.\n')


def edit_summary(root):
    p = root / 'results/cross_summary.json'
    data = json.loads(p.read_text())
    key = next(iter(data['outputs_by_pair_and_format']))
    data['outputs_by_pair_and_format'][key]['kept'] = data['outputs_by_pair_and_format'][key].get('kept', 0) + 1
    p.write_text(json.dumps(data, indent=1) + '\n')


def edit_map(root):
    p = root / 'map/index.html'
    text = p.read_text()
    assert '<title>BMAS Gauge Blocks: CAD</title>' in text
    p.write_text(text.replace('<title>BMAS Gauge Blocks: CAD</title>', '<title>Edited by hand</title>', 1))


def test_req8_untouched_copy_passes_the_artifact_check(tmp_path):
    result = check_artifacts(derived_copy(tmp_path))
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]


@pytest.mark.parametrize('relative,edit', [('COVERAGE.md', edit_coverage),
                                           ('results/cross_summary.json', edit_summary),
                                           ('map/index.html', edit_map)])
def test_req8_stale_derived_file_fails_the_check_and_is_named(tmp_path, relative, edit):
    root = derived_copy(tmp_path)
    edit(root)
    result = check_artifacts(root)
    output = result.stdout + result.stderr
    assert result.returncode != 0, 'a stale derived file must fail the check'
    assert relative in output, output[-1500:]
    assert re.search(r'python\S*\s+\S*(regenerate|write_coverage|summarize_cross|build)\S*\.py', output), \
        'the failure must name the command to run:\n' + output[-1500:]
    # the other derived files are not blamed
    for other in ('COVERAGE.md', 'results/cross_summary.json', 'map/index.html'):
        if other != relative:
            assert other not in output, (other, output[-1500:])


# ----------------------------- requirement 9: no measurement is stored twice

RETIRED_RESULTS = 'results/cross_ezdxf__oda_' + 'read_by_bricscad_checks.json'
RETIRED_MODULE = 'run_' + 'independent'


def result_rows(results_dir):
    """Row keys (file, field, reader, converter) mapped to the result files that hold them."""
    owner = {}
    for path in sorted(Path(results_dir).glob('*checks.json')):
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        for row in rows:
            key = tuple(row.get(k) for k in ('file', 'field', 'reader', 'converter'))
            owner.setdefault(key, set()).add(path.name)
    return owner


def test_req9_independent_runner_and_its_results_file_are_gone():
    assert not (ROOT / f'generators/{RETIRED_MODULE}.py').exists()
    assert not (ROOT / RETIRED_RESULTS).exists()


def test_req9_regenerate_has_no_bricscad_reading_step():
    text = (ROOT / 'regenerate.py').read_text()
    assert RETIRED_MODULE not in text
    assert 'read by bricscad' not in text


@pytest.mark.parametrize('doc', ['programs/CAPABILITIES.md', 'DESIGN.md', 'CONTRIBUTING.md', 'AGENTS.md',
                                 'checker/VOLATILE.md', 'map/TESTING.md'])
def test_req9_docs_do_not_mention_the_retired_step(doc):
    text = (ROOT / doc).read_text()
    assert RETIRED_MODULE not in text
    assert 'read_by_bricscad' not in text
    assert 'read by bricscad' not in text.lower()
    # ODA reads BricsCAD- and CADCraft-written DWG; it never reads its own output
    assert not re.search(r'\bODA\b[^.\n]{0,40}\breads?\b[^.\n]{0,20}\b(its own|ODA-written)\b', text), doc


def test_req9_committed_results_hold_each_row_once():
    twice = {key: files for key, files in result_rows(ROOT / 'results').items() if len(files) > 1}
    assert not twice, sorted({tuple(sorted(f)) for f in twice.values()})


def test_req9_check_fails_naming_both_files_when_a_row_is_stored_twice(tmp_path):
    root = derived_copy(tmp_path)
    source = ROOT / 'results/cross_ezdxf__oda_checks.json'
    row = json.loads(source.read_text())[0]
    copy = root / 'results/cross_zz_copied_checks.json'
    copy.write_text(json.dumps([row]))
    result = check_artifacts(root)
    output = result.stdout + result.stderr
    assert result.returncode != 0, 'a row held by two result files must fail the check'
    assert 'cross_zz_copied_checks.json' in output and 'cross_ezdxf__oda_checks.json' in output, output[-1500:]


def test_req9_check_passes_when_no_row_is_stored_twice(tmp_path):
    root = derived_copy(tmp_path)
    # a second file holding a different row is fine
    row = dict(json.loads((ROOT / 'results/cross_ezdxf__oda_checks.json').read_text())[0], field='wp9_unique_field')
    (root / 'results/cross_zz_unique_checks.json').write_text(json.dumps([row]))
    result = check_artifacts(root)
    output = result.stdout + result.stderr
    assert 'cross_zz_unique_checks.json' not in output, output[-1500:]


# ------------------------------------------------ rulings 10 to 15 (second round)

# Ruling 10: evidence scripts keep writing the evidence file they are run to produce.
EVIDENCE_WRITERS = [
    ('checker/test_digest.py', 'results/digest_evidence.json'),
    ('checker/test_oda_digest.py', 'results/oda_digest_evidence.json'),
    ('checker/test_oda_2000_digest.py', 'results/oda_2000_digest_evidence.json'),
    ('checker/test_privacy.py', 'results/privacy_evidence.json'),
    ('checker/test_volatile_new.py', '_digest_evidence.json'),
    ('checker/verify.py', 'results/verification.json'),
    ('checker/verify_feature_stability.py', 'results/feature_stability.json'),
    ('checker/verify_privacy.py', 'results/privacy_scan.json'),
    ('checker/probe_oda_r12_binary.py', 'results/oda_r12_binary_evidence.json'),
    ('checker/check_map_browser.py', 'results/map_browser.json'),
    ('map/check_links.py', 'map/link-checks.json'),
    ('map/check_links.py', 'results/map_links.json'),
    ('map/browser_test.py', 'map/browser-checks.json'),
    ('map/test_build.py', 'map/build-checks.json'),
]


def test_ruling10_phase2_verification_file_is_gone_and_unreferenced():
    assert not (ROOT / 'results/phase2_verification.json').exists()
    for path in list(ROOT.glob('*.py')) + list(ROOT.glob('*.md')) + [
            p for d in ('checker', 'generators', 'map', 'programs', 'tests') for p in (ROOT / d).rglob('*')
            if p.suffix in ('.py', '.md', '.json') and p.name != 'test_public_wording.py']:
        assert 'phase2_verification' not in path.read_text(errors='replace'), path


@pytest.mark.parametrize('script,evidence', EVIDENCE_WRITERS)
def test_ruling10_evidence_script_still_writes_its_evidence_file(script, evidence):
    lines = (ROOT / script).read_text().splitlines()
    assert any(evidence in line and 'write_text(' in line for line in lines), \
        f'{script} must still write {evidence}'


# Ruling 11: a DWG gap has no encoding in its words; one helper serves results and map.
DWG_WITH_ENCODING = re.compile(r'\bDWG\s+\S+\s+(binary|ASCII)\b')


def test_ruling11_gap_reason_on_hand_built_undeclared_tuple(tmp_path):
    from generators import run_cross
    write_json(tmp_path, 'programs/capabilities.json', {
        'bricscad': dict(name='BricsCAD', engine='bricscad', outputs=[['DWG', '2000', 'binary']]),
        'cadcraft': dict(name='CADCraft', engine='cadcraft', outputs=[['DWG', '2000', 'binary']])})
    assert run_cross.gap_reason(tmp_path, 'bricscad', 'DWG', 'R12', 'binary') == 'BricsCAD does not write DWG R12'
    assert run_cross.gap_reason(tmp_path, 'cadcraft', 'DWG', '2013', 'binary') == 'CADCraft does not write DWG 2013'
    # DXF keeps its encoding: it has two.
    assert run_cross.gap_reason(tmp_path, 'cadcraft', 'DXF', '2000', 'binary') == 'CADCraft does not write DXF 2000 binary'
    assert run_cross.gap_reason(tmp_path, 'bricscad', 'DXF', '2004', 'ASCII') == 'BricsCAD does not write DXF 2004 ASCII'


def map_gap_words(data):
    return {text for path, text in labels(data) if path.endswith('/impossible')}


def test_ruling11_committed_results_and_page_name_no_dwg_encoding(built):
    recorded = json.loads((ROOT / 'results/cross_not_run.json').read_text())
    assert recorded
    bad = sorted({v for v in recorded.values() if DWG_WITH_ENCODING.search(v)})
    assert not bad, bad
    page_words = map_gap_words(built['data'])
    assert page_words, 'the page DATA must carry capability gap words'
    assert not sorted(w for w in page_words if DWG_WITH_ENCODING.search(w))
    assert not DWG_WITH_ENCODING.search(built['coverage'])


def test_ruling11_results_file_and_map_use_the_same_words_for_the_same_tuple(built):
    from generators import run_cross
    recorded = set(json.loads((ROOT / 'results/cross_not_run.json').read_text()).values())
    page_words = map_gap_words(built['data'])
    for program in ('bricscad', 'cadcraft'):
        words = run_cross.gap_reason(ROOT, program, 'DWG', 'R12', 'binary')
        assert not DWG_WITH_ENCODING.search(words) and words.endswith('DWG R12'), words
        assert words in recorded, words
        assert words in page_words, words
    dxf = run_cross.gap_reason(ROOT, 'cadcraft', 'DXF', '2000', 'binary')
    assert dxf in recorded and dxf in page_words


def test_ruling11_map_and_results_build_the_words_in_one_place():
    assert 'does not write' not in (ROOT / 'map/build.py').read_text(), \
        'map/build.py must call the shared gap-wording helper, not build the sentence itself'
    holders = [p.relative_to(ROOT).as_posix() for d in ('generators', 'map', 'checker', 'programs')
               for p in (ROOT / d).rglob('*.py') if 'does not write' in p.read_text()]
    assert len(holders) == 1, holders


# Ruling 12: the main-view method sentence is whole.
def test_ruling12_main_view_method_sentence_is_whole(built):
    assert 'Round trip counts distinct measured features across declared pairs.' in built['page']
    assert 'counts distinct across' not in built['page']
    assert 'distinct measured features across declared pairs' in built['template']


# Ruling 13: the known read-failure cause is one shared constant in checker/core.py.
CAUSE_SENTENCE = 'cannot decode SAT from binary DXF written by Teigha programs, R2000 to R2010'


def cause_constants():
    from checker import core
    return {name: value for name, value in vars(core).items()
            if isinstance(value, str) and 'cannot decode SAT' in value}


def test_ruling13_cause_sentence_is_one_constant_in_core():
    constants = cause_constants()
    assert len(constants) == 1, sorted(constants)
    (value,) = constants.values()
    assert CAUSE_SENTENCE in value
    core_source = (ROOT / 'checker/core.py').read_text()
    assert core_source.count('cannot decode SAT') == 1, 'the sentence is written once, as the constant'
    build_source = (ROOT / 'map/build.py').read_text()
    assert 'cannot decode SAT' not in build_source, 'map/build.py must use the constant, not copy the text'
    assert "split('; '" not in build_source and 'split("; "' not in build_source


def reader_error_label(builder, tmp_path, detail):
    intent = acis_intent()
    cross = 'cross/bricscad__oda/k_regions_solids_2000_binary.dxf'
    rows = []
    for file in (ACIS_FILE, cross):
        for f in intent['expected']:
            row = dict(file=file, intent_id=intent['intent_id'], field=f['id'], reader=READER,
                       converter=None, status='same', expected=f['value'], actual=f['value'])
            if f['selector'].get('attr', '').startswith('acis_'):
                row['read_observation'] = dict(reader=READER, status='reader_error', actual=None, detail=detail)
            rows.append(row)
    acis_corpus(tmp_path, rows)
    return item_rows(builder.main_view_rows(tmp_path))['3DSOLID']['programs']['ezdxf']['reads']


def test_ruling13_exception_message_containing_separator_still_yields_the_cause(builder, tmp_path):
    (value,) = cause_constants().values()
    detail = READER + ' IndexError: odd; message with separator; list index out of range; ' + value
    cell = reader_error_label(builder, tmp_path, detail)
    label = cell['label']
    assert label.startswith('read failed: ' + READER), label
    for word in CAUSE_WORDS:
        assert word in label, (word, label)
    for leaked in ('IndexError', 'odd', 'separator', 'list index', 'out of range'):
        assert leaked not in label, (leaked, label)
    assert 'IndexError' in json.dumps(cell['evidence'])


def test_ruling13_separator_in_message_without_the_cause_gives_no_cause(builder, tmp_path):
    detail = READER + ' ValueError: first part; second part that is not a cause'
    label = reader_error_label(builder, tmp_path, detail)['label']
    assert label == 'read failed: ' + READER, label


# Ruling 14: no empty reading path.
@pytest.mark.parametrize('rows', [
    [dict(reader=READER, status='absent'), dict(reader=READER, status='differs', converter=None)],
    [dict(reader=READER, status='absent', converter='')],
])
def test_ruling14_lost_in_writer_or_converter_without_converter_names_the_reader(rows):
    from checker import attribution
    label = attribution.reading_label('lost in writer or converter', rows)
    assert READER in label and label.count(READER) == 1, label
    assert not re.search(r'read by\s+from', label), label
    assert not re.search(r'from\s*(output|$)', label), label
    assert '  ' not in label and not label.rstrip().endswith('from'), label
    assert 'read by ' + READER in label, label


def test_ruling14_with_a_converter_the_path_still_names_both():
    from checker import attribution
    rows = [dict(reader=READER, status='absent', converter='oda 27.1.0.143450 (binary DXF to ASCII DXF)')]
    label = attribution.reading_label('lost in writer or converter', rows)
    assert 'read by ' + READER in label and 'ODA File Converter 27.1.0.143450' in label, label


# Ruling 15: one display name per program in every label.
LOWERCASE_PROGRAM_BUILD = re.compile(r'\b(oda|bricscad|cadcraft)\s+\d+\.')


def test_ruling15_no_label_has_a_lowercase_program_id_and_build(built):
    bad = sorted({t for _, t in labels(built['data']) if LOWERCASE_PROGRAM_BUILD.search(t)})
    assert not bad, bad[:5]
    assert not LOWERCASE_PROGRAM_BUILD.search(built['visible'])
    assert not LOWERCASE_PROGRAM_BUILD.search(built['coverage'])


def test_ruling15_converter_evidence_in_reads_cell_uses_the_display_name(real_views):
    labels_seen = [cells['reads']['label'] for row in item_rows(real_views['main']).values()
                   for cells in row['programs'].values() if cells['reads']['status'] == 'lost by converter']
    assert labels_seen, 'the committed results contain converter read losses'
    for label in labels_seen:
        assert not LOWERCASE_PROGRAM_BUILD.search(label), label
        assert re.search(r'(ODA File Converter|BricsCAD) \d+\.\d+\.\d+', label), label
        assert '(binary DXF to ASCII DXF)' in label or '(' in label, label
