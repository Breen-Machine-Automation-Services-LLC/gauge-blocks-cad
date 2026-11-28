"""Check the links the heatmap and the repository documents carry.

Default (no network): every drawing, provenance record and intent link embedded in the heatmap
resolves inside the repository, and every Autodesk reference link in the heatmap is a DXF item
page in the edition set by standard/reference_catalog.py.

--online: also open every distinct external link in the heatmap and the tracked text files in
headless Firefox (needs `marionette_driver` and `firefox`, see map/TESTING.md) and fail on any
page that does not load or that shows a "Page Not Found" page. Autodesk's help pages answer 200
and then redirect to a viewer that can still say "Page Not Found", so only a browser can tell.
Firefox shows Autodesk's 2025 and later pages that Chromium does not; the pinned-edition test in
tests/test_reference_links.py covers that case.
"""
from pathlib import Path
import importlib.util
import json
import base64
import gzip
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r'https?://[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:/[^\s"\'<>()`\\\]]*)?')
AUTODESK = 'https://help.autodesk.com/'
# Links that are identifiers or placeholders rather than pages a reader follows.
NOT_PAGES = re.compile(r'example\.(?:invalid|com)|\{|^https://json-schema\.org/|\.git$')
NOT_FOUND = re.compile(r'page not found|\b404\b', re.I)
PORT = int(os.environ.get('MARIONETTE_PORT', '2858'))


def catalog():
    spec = importlib.util.spec_from_file_location('reference_catalog', ROOT / 'standard/reference_catalog.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_data(page):
    encoded = json.loads(page.split('const DATA_GZIP=', 1)[1].split(';\n', 1)[0])
    return json.loads(gzip.decompress(base64.b64decode(encoded)))


def local_links(data):
    links = set()
    for topic in data['topics']:
        links.add('intent/'+topic['id']+'.json')
        for feature in topic['features']:
            for cell in feature['cells']:
                paths = set(cell['files'])
                for run in cell['runs']:
                    assert run['inputs'], f'Missing input provenance: {run["output"]}'
                    paths.update(run['inputs'])
                    if not run.get('unavailable'):
                        paths.add(run['output'])
                for path in paths:
                    links.update((path, path+'.provenance.json'))
    for link in links:
        path = (ROOT/link).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), link
    return links


def clean(url):
    return url.rstrip('.,;:!*')


def reference_links(page):
    if 'const DATA_GZIP=' in page:
        page += json.dumps(page_data(page))
    item = catalog().ITEM_URL
    refs = {clean(u) for u in URL.findall(page) if u.startswith(AUTODESK)}
    bad = sorted(u for u in refs if not item.fullmatch(u))
    assert not bad, f'Autodesk links outside the pinned DXF edition: {bad[:5]}'
    return refs


def tracked_text_files():
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    for name in filter(None, (n.decode() for n in names)):
        if name.split('/')[0] in {'results', 'cross', 'native', 'logs'} or name.endswith(('.dxf', '.dwg', '.png', '.zip')):
            continue
        try:
            yield name, (ROOT/name).read_text()
        except (UnicodeDecodeError, OSError):
            continue


def external_links(page):
    if 'const DATA_GZIP=' in page:
        page += json.dumps(page_data(page))
    found = {}
    for name, text in [('map/index.html', page), *tracked_text_files()]:
        for url in URL.findall(text):
            found.setdefault(clean(url), set()).add(name)
    return found


def start_firefox(workdir):
    profile = Path(workdir) / 'profile'
    profile.mkdir()
    (profile / 'user.js').write_text(f'user_pref("marionette.port", {PORT});\n'
                                     'user_pref("pdfjs.disabled", false);\n')
    process = subprocess.Popen(['firefox', '--headless', '--no-remote', '--profile', str(profile), '--marionette', 'about:blank'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        try:
            socket.create_connection(('127.0.0.1', PORT), timeout=1).close()
            return process
        except OSError:
            time.sleep(0.5)
    process.kill()
    raise RuntimeError('Firefox did not open its Marionette port')


def settled_title(m, timeout=20, quiet=3):
    """Wait until the title stops changing; Autodesk's viewer rewrites it after a redirect."""
    end, last, since = time.time() + timeout, None, time.time()
    while time.time() < end:
        title = m.execute_script('return document.title') or ''
        if title != last:
            last, since = title, time.time()
        elif time.time() - since >= quiet and title not in ('', 'Help'):
            break
        time.sleep(0.5)
    return last or '', m.get_url()


def online(found):
    from marionette_driver.marionette import Marionette
    pages = sorted(u for u in found if not NOT_PAGES.search(u))
    skipped = sorted(u for u in found if u not in pages)
    rows = []
    with tempfile.TemporaryDirectory() as workdir:
        firefox = start_firefox(workdir)
        m = Marionette(port=PORT)
        try:
            m.start_session()
            m.timeout.page_load = 60
            for url in pages:
                try:
                    m.navigate(url)
                    title, landed = settled_title(m)
                    ok = not NOT_FOUND.search(title)
                except Exception as error:
                    title, landed, ok = f'load failed: {type(error).__name__}', '', False
                rows.append(dict(url=url, ok=ok, title=title, landed=landed, used_in=sorted(found[url])))
                print(('ok   ' if ok else 'FAIL ') + url + ' | ' + title, flush=True)
        finally:
            try:
                m.delete_session()
            except Exception:
                pass
            firefox.terminate()
    return rows, skipped


def main(argv):
    page = (ROOT/'map/index.html').read_text()
    links = local_links(page_data(page))
    refs = reference_links(page)
    report = dict(links=len(links), broken=0, reference_links=len(refs),
                  method='All embedded intent, input/output drawing and provenance record targets resolve inside '
                         'repository; every Autodesk reference link is a DXF item page in the pinned edition')
    (ROOT/'map/link-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    (ROOT/'results/map_links.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(links)} links resolve; {len(refs)} reference links use the pinned edition')
    if '--online' not in argv:
        return 0
    rows, skipped = online(external_links(page))
    failed = [r for r in rows if not r['ok']]
    out = ROOT/'logs/link-check-online.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(checked=len(rows), failed=len(failed), skipped=skipped, rows=rows), indent=2)+'\n')
    print(f'online: {len(rows)} pages opened, {len(failed)} failed, {len(skipped)} skipped (identifiers, placeholders); details in {out.relative_to(ROOT)}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
