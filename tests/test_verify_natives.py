import json

import pytest

from checker import verify


def test_native_counts():
    counts = verify.check_natives()
    assert counts['ezdxf'] > 0
    assert counts['bricscad'] > 0


def test_changed_recorded_status_fails(tmp_path, monkeypatch):
    for name in ('native', 'intent'):
        (tmp_path / name).symlink_to(verify.R / name, target_is_directory=True)
    (tmp_path / 'results').mkdir()
    rows = json.loads((verify.R / 'results/native_bricscad_checks.json').read_text())
    row = min((x for x in rows if x['converter'] is None), key=lambda x: x['file'])
    row['status'] = 'differs' if row['status'] == 'same' else 'same'
    (tmp_path / 'results/native_bricscad_checks.json').write_text(json.dumps(rows))
    monkeypatch.setattr(verify, 'R', tmp_path)
    with pytest.raises(AssertionError, match=row['field'].replace('.', r'\.')) as exc:
        verify.check_natives()
    assert row['file'] in str(exc.value)


def test_extra_recorded_row_for_empty_drawing_fails(tmp_path, monkeypatch):
    for name in ('native', 'intent'):
        (tmp_path / name).symlink_to(verify.R / name, target_is_directory=True)
    (tmp_path / 'results').mkdir()
    rows = json.loads((verify.R / 'results/native_bricscad_checks.json').read_text())
    drawing = 'native/bricscad/k_tables_R12_ASCII.dxf'
    assert not any(x['file'] == drawing and x['converter'] is None for x in rows)
    rows.append({'file': drawing, 'converter': None, 'field': 'extra',
                 'status': 'same', 'expected': 1, 'actual': 1})
    (tmp_path / 'results/native_bricscad_checks.json').write_text(json.dumps(rows))
    monkeypatch.setattr(verify, 'R', tmp_path)
    with pytest.raises(AssertionError, match='extra differs from recorded result') as exc:
        verify.check_natives()
    assert drawing in str(exc.value)
