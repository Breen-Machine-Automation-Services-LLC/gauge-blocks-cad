"""WP9 rulings 16 and 17: one currency rule for the planners and the artifact check, and one check run
that reports every failure.  Temporary copies only; the repository's own files are never written."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('CAD_DATASET_SETTINGS', str(ROOT / 'settings.example.json'))
sys.path.insert(0, str(ROOT))

from generators import run_cross
from test_public_wording import check_artifacts, derived_copy, edit_coverage

OLD_STAMP = '0' * 64
REFUSAL_FILE = 'results/cross_ezdxf__cadcraft_checks.json'
REFUSAL_PAIR = 'ezdxf__cadcraft'
SCORED_FILE = 'results/cross_ezdxf__oda_checks.json'
SCORED_PAIR = 'ezdxf__oda'


def rewrite(root, relative, change):
    """Replace a symlinked results file in the temporary repository with an edited copy; return the rows."""
    path = root / relative
    rows = json.loads(path.read_text())
    change(rows)
    path.unlink()
    path.write_text(json.dumps(rows))
    return rows


def refusal_names(root):
    rows = json.loads((root / REFUSAL_FILE).read_text())
    return sorted({r['file'] for r in rows if r.get('status') == 'refused'})


def age_stamp(rows, files):
    for row in rows:
        if row['file'] in files:
            row['scored_with'] = dict(row['scored_with'], checker=OLD_STAMP)


def plan_kinds(root, pair, rel):
    work = run_cross.plan(pair, root=root)
    return {kind for kind, files in work.items() if rel in files}


def output(result):
    return result.stdout + result.stderr


# ---------------------------------------------------------------- ruling 16: one rule, both consumers

def test_ruling16_committed_refusal_rows_exist_with_the_expected_shape():
    rows = json.loads((ROOT / REFUSAL_FILE).read_text())
    refused = [r for r in rows if r.get('status') == 'refused']
    assert len(refused) >= 1, 'the fixtures below need a committed refusal row'
    assert all(r.get('attempt_input_digest') and r.get('attempt_build') for r in refused)


def test_ruling16_refusal_with_old_stamp_is_current_to_the_plan(tmp_path):
    root = derived_copy(tmp_path)
    names = refusal_names(root)
    rewrite(root, REFUSAL_FILE, lambda rows: age_stamp(
        [r for r in rows if r.get('status') == 'refused'], names))
    for rel in names:
        assert plan_kinds(root, REFUSAL_PAIR, rel) == {'carried'}, rel


def test_ruling16_refusal_with_old_stamp_is_current_to_the_artifact_check(tmp_path):
    root = derived_copy(tmp_path)
    names = refusal_names(root)
    rewrite(root, REFUSAL_FILE, lambda rows: age_stamp(
        [r for r in rows if r.get('status') == 'refused'], names))
    result = check_artifacts(root)
    assert result.returncode == 0, output(result)[-1500:]
    assert REFUSAL_FILE.split('/')[-1] not in output(result)


def test_ruling16_scored_row_with_old_stamp_is_stale_to_the_plan(tmp_path):
    root = derived_copy(tmp_path)
    rel = json.loads((root / SCORED_FILE).read_text())[0]['file']
    rewrite(root, SCORED_FILE, lambda rows: age_stamp(rows, {rel}))
    assert plan_kinds(root, SCORED_PAIR, rel) == {'rescore'}


def test_ruling16_scored_row_with_old_stamp_is_stale_to_the_artifact_check(tmp_path):
    root = derived_copy(tmp_path)
    rel = json.loads((root / SCORED_FILE).read_text())[0]['file']
    rewrite(root, SCORED_FILE, lambda rows: age_stamp(rows, {rel}))
    result = check_artifacts(root)
    assert result.returncode != 0, 'a scored row with an old stamp must fail the check'
    assert SCORED_FILE.split('/')[-1] in output(result), output(result)[-1500:]


def change_build(rows):
    for row in rows:
        if row.get('status') == 'refused':
            row['attempt_build'] = 'an older build'


def test_ruling16_refusal_with_changed_build_is_stale_to_the_plan(tmp_path):
    root = derived_copy(tmp_path)
    names = refusal_names(root)
    rewrite(root, REFUSAL_FILE, change_build)
    for rel in names:
        kinds = plan_kinds(root, REFUSAL_PAIR, rel)
        assert kinds and not kinds & {'carried', 'gaps'}, (rel, kinds)


def test_ruling16_refusal_with_changed_build_is_stale_to_the_artifact_check(tmp_path):
    root = derived_copy(tmp_path)
    rewrite(root, REFUSAL_FILE, change_build)
    result = check_artifacts(root)
    assert result.returncode != 0, 'a refusal recorded for another build must fail the check'
    assert REFUSAL_FILE.split('/')[-1] in output(result), output(result)[-1500:]


def test_ruling16_refusal_with_changed_input_digest_is_stale_to_the_plan(tmp_path):
    root = derived_copy(tmp_path)
    names = refusal_names(root)

    def change(rows):
        for row in rows:
            if row.get('status') == 'refused':
                row['attempt_input_digest'] = OLD_STAMP
    rewrite(root, REFUSAL_FILE, change)
    for rel in names:
        kinds = plan_kinds(root, REFUSAL_PAIR, rel)
        assert kinds and not kinds & {'carried', 'gaps'}, (rel, kinds)


def test_ruling16_committed_results_pass_the_check_and_plan_no_work(tmp_path):
    result = check_artifacts(derived_copy(tmp_path))
    assert result.returncode == 0, output(result)[-1500:]
    for pair in run_cross.PAIRS:
        work = run_cross.plan(pair)
        if pair.endswith('__autocad') and not (ROOT / 'results' / f'cross_{pair}_checks.json').exists():
            assert work['resave'], pair
            continue
        assert not work['resave'] and not work['rescore'], (pair, work['resave'][:3], work['rescore'][:3])


# ----------------------------------------------------- ruling 17: every failing check in one run

def test_ruling17_stale_row_and_edited_derived_file_are_both_reported(tmp_path):
    root = derived_copy(tmp_path)
    rel = json.loads((root / SCORED_FILE).read_text())[0]['file']
    rewrite(root, SCORED_FILE, lambda rows: age_stamp(rows, {rel}))
    edit_coverage(root)
    result = check_artifacts(root)
    text = output(result)
    assert result.returncode != 0
    assert SCORED_FILE.split('/')[-1] in text, 'the stale row is not reported:\n' + text[-1500:]
    assert 'COVERAGE.md' in text, 'the edited derived file is not reported:\n' + text[-1500:]
    # the derived files that were not edited are not blamed
    assert 'map/index.html' not in text and 'results/cross_summary.json' not in text, text[-1500:]


def test_ruling17_stale_row_and_stored_twice_row_are_both_reported(tmp_path):
    root = derived_copy(tmp_path)
    rows = json.loads((root / SCORED_FILE).read_text())
    rel = rows[0]['file']
    rewrite(root, SCORED_FILE, lambda r: age_stamp(r, {rel}))
    other = json.loads((ROOT / 'results/cross_ezdxf__bricscad_checks.json').read_text())[0]
    (root / 'results/cross_zz_copied_checks.json').write_text(json.dumps([other]))
    result = check_artifacts(root)
    text = output(result)
    assert result.returncode != 0
    assert 'cross_ezdxf__oda_checks.json' in text, 'the stale row is not reported:\n' + text[-1500:]
    assert 'cross_zz_copied_checks.json' in text and 'cross_ezdxf__bricscad_checks.json' in text, text[-1500:]
