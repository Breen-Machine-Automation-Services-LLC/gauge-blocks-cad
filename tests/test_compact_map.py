"""WP10 acceptance tests: the main and comparison views use the detailed view's status squares.

Written before the implementation (spec: wp10-compact-map/SPEC.md). The page is built into a
temporary directory from the committed inputs (never over map/index.html). The page script then
runs under node against a small fake DOM (tests/compact_map_harness.js), so the tests exercise
the real template code, the real tooltip and the real click handler, without a browser.

Contract these tests rely on (the implementer may choose everything else):
  * a cell in the main or comparison view is a <button> carrying class "cell" (the detailed view's
    square) plus a status class; its only visible text is its icon;
  * the main view is one or more <table>s with a <thead> and <tbody>; each tbody row has a row
    header <th> (standard item name) then one <td> per cell, in DATA order: dataset, then
    reads, writes, round trip for each program in DATA.main_view.programs;
  * a comparison row ends with two cell buttons: round trip, then native reading path;
  * the page's own document-level mouseover, focusin and click listeners must fill the shared
    tooltip (#tooltip) and the evidence panel (#panel > #details) for those buttons.
Requirement 6 (layout) is checked by map/compact_check.py in Firefox, not here.
"""
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import contextlib
import io
from html.parser import HTMLParser
from pathlib import Path

import pytest

from checker.core import SAT_READ_CAUSE

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tests/compact_map_harness.js'
BASELINE_TEMPLATE = ROOT / 'tests/fixtures/wp10_baseline_template.html'
NAMES = {'ezdxf': 'ezdxf', 'oda': 'ODA File Converter', 'bricscad': 'BricsCAD', 'cadcraft': 'CADCraft'}
CHECK, CROSS, DOT = {'✓', '✔'}, {'×', '✗', '✕', '✘'}, {'·', '•', '∙', '⋅'}
CHECK_STATUSES = ('kept', 'measured', 'native drawing', 'included', 'present')
CROSS_STATUSES = ('reader_error', 'refused', 'unreadable by reader', 'source not readable')
DOT_STATUSES = ('not measured', 'no native drawing')
QUIET_CLASSES = {'not-run', 'no-source'}
SIZE_LIMIT = 12_000_000


# ------------------------------------------------------------------ node harness and page

def node():
    found = shutil.which('node') or next(iter(sorted(Path.home().glob('.nvm/versions/node/*/bin/node'))), None)
    assert found, 'node is required to run the page script (tests/compact_map_harness.js)'
    return str(found)


def run_harness(page, scenario, tmp):
    scenario_file = Path(tmp) / 'scenario.json'
    scenario_file.write_text(json.dumps(scenario))
    done = subprocess.run([node(), str(HARNESS), str(page), str(scenario_file)],
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp('wp10_build')
    for name in ('intent', 'native', 'cross', 'results', 'programs', 'standard'):
        (root / name).symlink_to(ROOT / name, target_is_directory=True)
    (root / 'map').mkdir()
    shutil.copy(ROOT / 'map/template.html', root / 'map/template.html')
    spec = importlib.util.spec_from_file_location('wp10_build_map', ROOT / 'map/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    patch = pytest.MonkeyPatch()
    try:
        patch.setattr(module, 'ROOT', root)
        with contextlib.redirect_stdout(io.StringIO()):
            module.main()
    finally:
        patch.undo()
    page = root / 'map/index.html'
    text = page.read_text()
    data_json = re.search(r'const DATA=(.*?);\s*\n', text).group(1)
    return dict(root=root, page=page, text=text, data=json.loads(data_json), data_json=data_json,
                template=(ROOT / 'map/template.html').read_text(), tmp=root)


@pytest.fixture(scope='module')
def main_render(built):
    return run_harness(built['page'], dict(view='main'), built['tmp'])


@pytest.fixture(scope='module')
def comparison_renders(built):
    out = {}
    for pair in built['data']['pairs']:
        writer, resaver = pair.split('__')
        out[pair] = run_harness(built['page'], dict(view='comparison', writer=writer, resaver=resaver), built['tmp'])
    return out


# ------------------------------------------------------------------ HTML structure helpers

class Tables(HTMLParser):
    """Tables as rows of cells; each cell keeps its text pieces and its buttons."""

    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell, self.button, self.section = [], None, None, None, None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.table = dict(rows=[])
            self.tables.append(self.table)
        elif tag in ('thead', 'tbody'):
            self.section = tag
        elif tag == 'tr' and self.table is not None:
            self.row = dict(section=self.section, cells=[])
            self.table['rows'].append(self.row)
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = dict(tag=tag, attrs=attrs, pieces=[], buttons=[])
            self.row['cells'].append(self.cell)
        elif tag == 'button' and self.cell is not None:
            self.button = dict(attrs=attrs, pieces=[])
            self.cell['buttons'].append(self.button)

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.cell = None
        elif tag == 'button':
            self.button = None
        elif tag == 'tr':
            self.row = None
        elif tag == 'table':
            self.table = None

    def handle_data(self, data):
        text = data.strip()
        if text and self.cell is not None:
            self.cell['pieces'].append(text)
            if self.button is not None:
                self.button['pieces'].append(text)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def parse_tables(markup):
    parser = Tables()
    parser.feed(markup)
    return parser.tables


def plain_text(markup):
    parser = PlainText()
    parser.feed(markup)
    return ' '.join(' '.join(parser.parts).split())


def classes(button):
    return set(button['attrs'].get('class', '').split())


def glyph(button):
    return ''.join(button['pieces'])


def body_rows(tables):
    return [r for t in tables for r in t['rows'] if r['section'] == 'tbody']


def head_rows(tables):
    return [r for t in tables for r in t['rows'] if r['section'] == 'thead']


def main_cells(built, render):
    """(row name, column, td, button, DATA cell) for every cell of the main view."""
    data = built['data']['main_view']
    keys = [(p['id'], k) for p in data['programs'] for k in ('reads', 'writes', 'round_trip')]
    rows = [r for g in data['groups'] for r in g['rows']]
    html_rows = body_rows(parse_tables(render['views']))
    assert len(html_rows) == len(rows), (len(html_rows), len(rows))
    out = []
    for row, html_row in zip(rows, html_rows):
        tds = [c for c in html_row['cells'] if c['tag'] == 'td']
        assert len(tds) == 1 + len(keys), (row['name'], len(tds))
        data_cells = [row['dataset']] + [row['programs'][p][k] for p, k in keys]
        for column, (td, cell) in enumerate(zip(tds, data_cells)):
            assert len(td['buttons']) == 1, (row['name'], column, 'one cell button per cell')
            out.append((row, column, td, td['buttons'][0], cell))
    return out


def comparison_cells(built, renders):
    out = []
    for pair, render in renders.items():
        rows = [r for g in built['data']['comparisons'][pair]['groups'] for r in g['rows']]
        html_rows = body_rows(parse_tables(render['views']))
        assert len(html_rows) == len(rows), (pair, len(html_rows), len(rows))
        for row, html_row in zip(rows, html_rows):
            holders = [c for c in html_row['cells'] if c['buttons']]
            assert len(holders) >= 2, (pair, row['feature'])
            for td, cell in zip(holders[-2:], (row['round_trip'], row['native_read'])):
                assert len(td['buttons']) == 1
                out.append((pair, row, td, td['buttons'][0], cell))
    return out


def hover_main(built, cells):
    return run_harness(built['page'], dict(view='main', hover=[b['attrs'] for *_, b, _ in cells]), built['tmp'])['tooltips']


def hover_comparison(built, pair, buttons):
    writer, resaver = pair.split('__')
    return run_harness(built['page'], dict(view='comparison', writer=writer, resaver=resaver,
                                           hover=[b['attrs'] for b in buttons]), built['tmp'])['tooltips']


# ------------------------------------------------ requirement 1: squares, no words

def assert_square_without_words(td, button, where):
    assert 'cell' in classes(button), (where, 'must reuse the detailed view square (class "cell")', button['attrs'])
    text = glyph(button)
    assert 1 <= len(text) <= 2 and not re.search(r'[A-Za-z0-9]', text), (where, 'visible text must be only the icon', text)
    assert td_text(td) == ' '.join(button['pieces']), (where, 'no visible text beside the square', td['pieces'])


def td_text(td):
    return ' '.join(td['pieces'])


def test_req1_main_view_cells_are_squares_with_only_an_icon(built, main_render):
    cells = main_cells(built, main_render)
    assert len(cells) > 1000
    for row, column, td, button, cell in cells:
        assert_square_without_words(td, button, (row['name'], column))


def test_req1_comparison_view_cells_are_squares_with_only_an_icon(built, comparison_renders):
    cells = comparison_cells(built, comparison_renders)
    assert len(cells) > 50
    for pair, row, td, button, cell in cells:
        assert_square_without_words(td, button, (pair, row['feature']))


def test_req1_main_cells_tooltip_carries_full_label_on_hover_and_focus(built, main_render):
    cells = main_cells(built, main_render)
    tips = hover_main(built, cells)
    bad = []
    for (row, column, td, button, cell), tip in zip(cells, tips):
        for how in ('hover', 'focus'):
            if cell['label'] not in tip[how]:
                bad.append((row['name'], column, how, cell['label'], tip[how][:80], tip.get(how + '_error')))
        if column == 0:
            bad += [(row['name'], 'dataset intent missing from tooltip', i) for i in cell['intents'] if i not in tip['hover']]
    assert not bad, bad[:5]


def test_req1_comparison_cells_tooltip_carries_full_label_on_hover_and_focus(built, comparison_renders):
    bad = []
    for pair in comparison_renders:
        cells = [c for c in comparison_cells(built, {pair: comparison_renders[pair]})]
        tips = hover_comparison(built, pair, [c[3] for c in cells])
        for (_, row, td, button, cell), tip in zip(cells, tips):
            for how in ('hover', 'focus'):
                if cell['label'] not in tip[how]:
                    bad.append((pair, row['feature'], how, cell['label'], tip[how][:80], tip.get(how + '_error')))
    assert not bad, bad[:5]


def click_cells(built, selected, view='main', pair=None):
    scenario = dict(view=view, click=[b['attrs'] for b in selected])
    if pair:
        scenario.update(writer=pair.split('__')[0], resaver=pair.split('__')[1])
    return run_harness(built['page'], scenario, built['tmp'])['panels']


def test_req1_click_opens_evidence_panel_with_every_sentence(built, main_render):
    cells = main_cells(built, main_render)
    wanted = [c for c in cells if c[0]['name'] in ('3DSOLID', 'ACAD_PROXY_ENTITY', 'TEXT') or c[1] == 0 and c[0]['name'] == 'LAYER']
    assert wanted
    panels = click_cells(built, [c[3] for c in wanted])
    bad = []
    for (row, column, td, button, cell), panel in zip(wanted, panels):
        text = html.unescape(panel['html'])
        if panel.get('error') or panel['hidden'] or cell['label'] not in text:
            bad.append((row['name'], column, panel.get('error'), panel['hidden'], cell['label']))
    assert not bad, bad[:5]


def test_req1_3dsolid_ezdxf_reads_panel_still_shows_the_cause(built, main_render):
    cells = main_cells(built, main_render)
    index = [p['id'] for p in built['data']['main_view']['programs']].index('ezdxf')
    target = next(c for c in cells if c[0]['name'] == '3DSOLID' and c[1] == 1 + 3 * index)
    assert target[4]['label'].startswith('read failed')
    panel = click_cells(built, [target[3]])[0]
    assert not panel['hidden'] and not panel.get('error'), panel.get('error')
    assert SAT_READ_CAUSE in html.unescape(panel['html'])


def test_req1_template_reuses_the_detailed_squares_and_tooltip(built):
    template = built['template']
    script = template[template.index('<script>'):]
    assert script.count('class="cell') == 1, 'one place builds the square; main and comparison views must call it'
    assert script.count("$('tooltip').textContent=") == 1, 'one shared tooltip; do not build a second one'
    assert 'class="view-cell' not in script, 'the old labelled cell is replaced by the shared square'


# ------------------------------------------------ requirement 2: not measured is quiet

def quiet_cases(built, main_render, comparison_renders):
    for row, column, td, button, cell in main_cells(built, main_render):
        yield ('main', row['name'], column), button, cell
    for pair, row, td, button, cell in comparison_cells(built, comparison_renders):
        yield (pair, row['feature']), button, cell


def test_req2_not_measured_and_no_native_drawing_use_the_quiet_square(built, main_render, comparison_renders):
    seen = {s: 0 for s in DOT_STATUSES}
    for where, button, cell in quiet_cases(built, main_render, comparison_renders):
        if cell['status'] in DOT_STATUSES:
            seen[cell['status']] += 1
            assert classes(button) & QUIET_CLASSES, (where, cell['status'], classes(button))
            assert not classes(button) & {'kept', 'covered', 'changed', 'partial', 'lost', 'refused', 'reader_error'}, where
        else:
            assert not classes(button) & QUIET_CLASSES or cell['status'] in ('omitted', 'future', 'present'), (
                where, cell['status'], 'only unmeasured cells use the quiet style')
    assert all(seen.values()), seen


def test_req2_quiet_classes_exist_in_the_stylesheet(built):
    style = built['template'][:built['template'].index('</style>')]
    for name in QUIET_CLASSES:
        assert '.' + name in style


# ------------------------------------------------ requirement 3: one mark per status family

def family_ok(status, mark):
    if status in CHECK_STATUSES:
        return mark in CHECK
    if status in CROSS_STATUSES:
        return mark in CROSS
    if status in DOT_STATUSES or status in ('not scored', 'not_scored'):
        return mark in DOT
    return mark not in CHECK | CROSS | DOT | {'?'} or status in ('omitted',)


def test_req3_rendered_marks_follow_one_table(built, main_render, comparison_renders):
    marks = {}
    for where, button, cell in quiet_cases(built, main_render, comparison_renders):
        marks.setdefault(cell['status'], {}).setdefault(glyph(button), where)
    assert all(len(v) == 1 for v in marks.values()), {k: list(v) for k, v in marks.items() if len(v) > 1}
    wrong = {s: list(v) for s, v in marks.items() if not family_ok(s, next(iter(v)))}
    assert not wrong, wrong
    assert not any('?' in v for v in marks.values())
    lost, changed = marks.get('lost'), marks.get('changed')
    if lost and changed:
        assert set(lost) != set(changed), 'loss and change each get their own mark'


def test_req3_read_failed_cells_show_the_cross(built, main_render):
    failed = [c for c in main_cells(built, main_render) if c[4]['label'].startswith('read failed')]
    assert failed, 'the committed results contain read failures'
    for row, column, td, button, cell in failed:
        assert glyph(button) in CROSS, (row['name'], column, glyph(button))
        assert cell['icon'] in CROSS, (row['name'], column, cell['icon'])


def test_req3_page_data_icons_follow_the_families(built):
    data = built['data']
    cells = [c for g in data['main_view']['groups'] for r in g['rows'] for c in [r['dataset']] + [x for p in r['programs'].values() for x in p.values()]]
    cells += [c for comparison in data['comparisons'].values() for g in comparison['groups'] for r in g['rows'] for c in (r['round_trip'], r['native_read'])]
    by_status = {}
    for cell in cells:
        by_status.setdefault(cell['status'], set()).add(cell['icon'])
    assert all(len(v) == 1 for v in by_status.values()), by_status
    assert not any('?' in v for v in by_status.values()), {k: v for k, v in by_status.items() if '?' in v}
    assert not {s for s, v in by_status.items() if not family_ok(s, next(iter(v)))}


def test_req3_template_icon_table_uses_only_the_family_marks(main_render):
    icons = main_render['icons']
    assert icons, 'the page script keeps one icon table named icons'
    assert '?' not in icons.values(), {k: v for k, v in icons.items() if v == '?'}
    for status in ('reader_error', 'unreadable by reader', 'source not readable', 'refused'):
        assert icons[status] in CROSS, status
    for status in ('kept', 'covered'):
        assert icons[status] in CHECK, status
    for status in ('not run', 'not_scored'):
        assert icons[status] in DOT, status
    assert icons['lost'] != icons['changed'] and not {icons['lost'], icons['changed']} & (CHECK | CROSS | DOT)


def test_req3_panel_heading_for_a_read_failure_never_shows_a_question_mark(built, main_render):
    cells = main_cells(built, main_render)
    target = next(c for c in cells if c[4]['label'].startswith('read failed'))
    panel = click_cells(built, [target[3]])[0]
    head = html.unescape(panel['html']).split('<pre')[0]
    head = re.sub(r'href="[^"]*"', '', head)  # a link's query string is not a mark
    assert '?' not in head and not panel.get('error'), (head, panel.get('error'))


# ------------------------------------------------ requirement 4: plain headers

def test_req4_program_headers_show_the_display_name_once(built, main_render):
    programs = built['data']['main_view']['programs']
    assert [p['name'] for p in programs] == [NAMES[p['id']] for p in programs]
    tables = parse_tables(main_render['views'])
    assert tables
    for table in tables:
        head = [c for r in table['rows'] if r['section'] == 'thead' for c in r['cells'] if c['pieces'] and c['pieces'][0] in NAMES.values()]
        assert [c['pieces'][0] for c in head] == [p['name'] for p in programs], 'one header per program, in order'
        for cell, program in zip(head, programs):
            text = ' '.join(cell['pieces'])
            assert text.count(program['name']) == 1, text
            if program['shared_engine']:
                assert len(cell['pieces']) == 2, (program['name'], cell['pieces'])
                second = cell['pieces'][1]
                assert 'ODA' in second and second.endswith('library') and 'teigha' not in second.lower(), second
            else:
                assert cell['pieces'] == [program['name']], cell['pieces']


def test_req4_no_engine_slug_or_shared_engine_in_main_view_text(main_render):
    text = ' '.join(plain_text(main_render[k]) for k in ('views', 'legend_html', 'summary_html', 'instructions', 'method'))
    text += ' ' + main_render['summary_text']
    assert not re.search(r'teigha|shared engine', text, re.I), re.findall(r'.{20}(?:teigha|shared engine).{20}', text, re.I)[:3]


# ------------------------------------------------ requirement 5: column legend

def test_req5_sub_columns_are_r_w_t(built, main_render):
    programs = built['data']['main_view']['programs']
    tables = parse_tables(main_render['views'])
    for table in tables:
        subs = [c['pieces'][0] for r in table['rows'] if r['section'] == 'thead' for c in r['cells']
                if c['pieces'] and c['pieces'][0] in ('R', 'W', 'T', 'Reads', 'Writes', 'Round trip')]
        assert subs == ['R', 'W', 'T'] * len(programs), subs[:9]


def test_req5_one_line_explains_r_w_t(main_render):
    text = ' '.join(plain_text(main_render[k]) for k in ('views', 'legend_html', 'method', 'instructions'))
    assert re.search(r'\bR\b[^.;\n]{0,40}\breads?\b', text), text[-400:]
    assert re.search(r'\bW\b[^.;\n]{0,40}\bwrites natively\b', text), text[-400:]
    assert re.search(r'\bT\b[^.;\n]{0,40}\bround trip\b', text, re.I), text[-400:]


def test_req5_status_legend_is_shown_like_the_detailed_view(main_render):
    markup = main_render['legend_html'] + main_render['views']
    assert len(re.findall(r'<span class="swatch', markup)) >= 5, 'a swatch legend like the detailed view'
    text = plain_text(markup).lower()
    for word in ('kept', 'not measured', 'read failed'):
        assert word in text, word


# ------------------------------------------------ requirement 7: the detailed view is the reference

def detailed_attrs(grid, limit=40):
    buttons = [b['attrs'] for t in parse_tables('<table><tbody>' + grid + '</tbody></table>')
               for r in t['rows'] for c in r['cells'] for b in c['buttons']]
    step = max(1, len(buttons) // limit)
    return buttons[::step][:limit]


@pytest.mark.parametrize('mode', ['coverage', 'compatibility'])
def test_req7_detailed_view_is_unchanged(built, mode):
    """The baseline template is the pre-WP10 template; both are rendered over the same DATA."""
    baseline = built['tmp'] / 'baseline.html'
    baseline.write_text(BASELINE_TEMPLATE.read_text().replace('/*DATA*/', built['data_json']))
    scenario = dict(view='detailed', mode=mode)
    before = run_harness(baseline, scenario, built['tmp'])
    scenario['hover'] = detailed_attrs(before['grid'])
    before = run_harness(baseline, scenario, built['tmp'])
    after = run_harness(built['page'], scenario, built['tmp'])
    assert before['grid'], 'the detailed view renders its grid'
    # Requirement 3 sets one mark per status page-wide, so the glyphs may change here;
    # layout, labels and tooltips may not.
    marks = re.compile('[\u2713\u2260\u2212\u00d7?\u00b7/\u25d0\u25a1\u25c7\u26bf]')
    norm = lambda v: marks.sub('*', json.dumps(v, ensure_ascii=False))
    for key in ('grid', 'summary_html', 'legend_html', 'method', 'instructions', 'tooltips'):
        assert norm(after[key]) == norm(before[key]), key


# ------------------------------------------------ requirement 8: budget

def test_req8_built_page_is_within_budget(built):
    assert built['page'].stat().st_size <= SIZE_LIMIT


def test_req8_committed_page_is_within_budget():
    assert (ROOT / 'map/index.html').stat().st_size <= SIZE_LIMIT
