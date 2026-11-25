import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompareHarnessTest(unittest.TestCase):
    def test_exiting_server_is_not_a_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'fake-cadcraft'
            binary.write_text('#!/bin/sh\nexit 1\n')
            binary.chmod(0o755)
            subprocess.run([sys.executable, str(ROOT / 'compare_build.py'), '--program', 'cadcraft',
                            '--binary', str(binary), '--label', 'fake', '--out', str(root),
                            '--pairs', 'ezdxf__cadcraft'], check=True, capture_output=True, text=True)
            result = json.loads((root / 'fake-compare.json').read_text())
            self.assertEqual(result['counts']['worsened'], 0)
            self.assertEqual(result['rows'], [])
            self.assertIn('MCP server failed to start', result['failures']['ezdxf__cadcraft'])
            self.assertIn('could not run this build:', (root / 'fake-compare.md').read_text())


if __name__ == '__main__':
    unittest.main()


def test_real_run_pair_with_exiting_program(tmp_path):
    binary = tmp_path / 'fake-cadcraft'
    binary.write_text('#!/bin/sh\nexit 1\n')
    binary.chmod(0o755)
    subprocess.run([sys.executable, str(ROOT / 'compare_build.py'), '--program', 'cadcraft',
                    '--binary', str(binary), '--label', 'signature', '--out', str(tmp_path),
                    '--pairs', 'ezdxf__cadcraft'], check=True, capture_output=True, text=True)
    report = json.loads((tmp_path / 'signature-compare.json').read_text())
    assert 'MCP server failed to start' in report['failures']['ezdxf__cadcraft']


def test_published_document_tracks_final_file(tmp_path):
    import ezdxf
    from regenerate import publish
    staged = tmp_path / 'staged.dxf'
    final = tmp_path / 'final.dxf'
    ezdxf.new().saveas(staged)
    doc = ezdxf.readfile(staged)
    meta = dict(content_digest='synthetic', build='test', encoding='ASCII')
    publish(staged, final, meta, doc=doc)
    assert Path(doc.filename) == final
    assert Path(doc.filename).read_bytes() == final.read_bytes()


def test_all_checker_statuses_have_rank_and_unknown_names_status():
    import pytest
    from checker.attribution import RAW
    from compare_build import status_rank
    for status in RAW:
        assert isinstance(status_rank(status), (int, float))
    assert isinstance(status_rank('not run'), (int, float))
    with pytest.raises(ValueError, match='unexpected-status'):
        status_rank('unexpected-status')
