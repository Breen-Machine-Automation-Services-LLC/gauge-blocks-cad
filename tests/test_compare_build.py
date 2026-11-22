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
