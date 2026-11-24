"""The derived publications and their generators, in dependency order."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map import build
from generators import write_coverage, summarize_cross
import measure_size

ROOT = Path(__file__).resolve().parents[1]
def coverage(output):
    write_coverage.main(output, output.parent/'map/index.html')

DERIVED = (
    (('map/index.html',), 'map/build.py', lambda dest: build.main(dest/'map/index.html')),
    (('COVERAGE.md',), 'generators/write_coverage.py', lambda dest: coverage(dest/'COVERAGE.md')),
    (('results/cross_summary.json',), 'generators/summarize_cross.py', lambda dest: summarize_cross.main(dest/'results/cross_summary.json')),
    (('SIZE.md', 'results/size.json'), 'measure_size.py', measure_size.main),
)

def rebuild(destination=ROOT):
    destination = Path(destination)
    for names, _, generator in DERIVED:
        for name in names:(destination/name).parent.mkdir(parents=True, exist_ok=True)
        generator(destination)

if __name__ == '__main__':
    rebuild()
