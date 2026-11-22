"""Shared executable settings. Copy settings.example.json to settings.local.json."""
from pathlib import Path
import json, os
ROOT = Path(__file__).resolve().parents[1]
def load():
    path = Path(os.environ.get('CAD_DATASET_SETTINGS', ROOT/'settings.local.json'))
    return json.loads((path if path.exists() else ROOT/'settings.example.json').read_text())
SETTINGS = load()
if __name__ == '__main__':
    import sys
    print(SETTINGS[sys.argv[1]])
