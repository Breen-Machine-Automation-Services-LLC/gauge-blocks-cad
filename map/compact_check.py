"""WP10 layout check: the main view is a grid of small status squares (Firefox headless).

Not a pytest test. It starts its own headless Firefox with Marionette, so `marionette_driver`
must be importable (see map/TESTING.md), and it needs `firefox` on PATH. Usage:

    python map/compact_check.py [path/to/index.html]

Measures, at a 1400 px desktop viewport and at a 390 px phone viewport:
  * desktop: the main view tables need no horizontal scrolling, the page does not scroll
    sideways, every body row is at most 24 px tall, the cells are the detailed view's 16 px
    squares with no visible words, hovering a square shows the shared tooltip and clicking opens
    the evidence panel;
  * phone: the page itself does not scroll sideways (a table may scroll inside its own box).
Screenshots go to logs/screens/. One JSON summary line is printed; the exit code is non-zero if
any check failed.
"""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from marionette_driver import By
from marionette_driver.marionette import Actions, Marionette

ROOT = Path(__file__).resolve().parents[1]
PAGE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'map/index.html'
SHOTS = ROOT / 'logs/screens'
PORT = int(os.environ.get('MARIONETTE_PORT', '2848'))
MAX_ROW = 24
results = []


def check(name, passed, evidence=None):
    results.append(dict(check=name, passed=bool(passed), evidence=evidence))
    return passed


def start_firefox(workdir):
    profile = Path(workdir) / 'profile'
    profile.mkdir()
    (profile / 'user.js').write_text(f'user_pref("marionette.port", {PORT});\n'
                                     'user_pref("layout.css.prefers-color-scheme.content-override", 1);\n')
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


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as workdir:
        firefox = start_firefox(workdir)
        m = Marionette(port=PORT)
        try:
            m.start_session()
            m.set_context('content')
            run(m)
        finally:
            try:
                m.delete_session()
            except Exception:
                pass
            firefox.terminate()
    failed = [r['check'] for r in results if not r['passed']]
    print(json.dumps(dict(page=str(PAGE), checks=len(results), failed=failed, results=results)))
    return 1 if failed else 0


def run(m):
    def js(script):
        return m.execute_script(script, sandbox=None)

    def shot(name, element=None):
        js("document.getElementById('tooltip').hidden=true")
        data = m.screenshot(element=element) if element else m.screenshot(full=False)
        (SHOTS / f'{name}.png').write_bytes(base64.b64decode(data))

    # ---- desktop, 1400 px content width
    m.set_window_rect(width=1400, height=900)
    m.set_window_rect(width=1400, height=900 + (900 - js('return innerHeight')))
    m.navigate(PAGE.as_uri())
    check('default view is the main view', js('return document.getElementById("view").value==="main" && !document.getElementById("views").hidden'))
    check('desktop viewport is 1400 px wide', js('return innerWidth') == 1400, js('return innerWidth'))
    tables = js('''return [...document.querySelectorAll("#views table")].map(t=>{
      const box=t.closest(".view-scroll")||t.parentElement;
      return {width:t.getBoundingClientRect().width,box:box.clientWidth,scroll:box.scrollWidth,
        heights:[...t.querySelectorAll("tbody tr")].map(r=>r.getBoundingClientRect().height)}})''')
    check('main view has tables', len(tables) >= 1, len(tables))
    check('desktop: no table needs horizontal scrolling', all(t['scroll'] <= t['box'] + 1 and t['width'] <= t['box'] + 1 for t in tables),
          [(t['width'], t['box'], t['scroll']) for t in tables])
    check('desktop: page does not scroll sideways', js('return document.documentElement.scrollWidth<=innerWidth'),
          js('return [document.documentElement.scrollWidth,innerWidth]'))
    heights = [h for t in tables for h in t['heights']]
    check(f'desktop: every row is at most {MAX_ROW} px tall', bool(heights) and max(heights) <= MAX_ROW,
          dict(rows=len(heights), max=max(heights) if heights else None))
    squares = js('''return [...document.querySelectorAll("#views tbody button")].map(b=>{const r=b.getBoundingClientRect();
      return [Math.round(r.width),Math.round(r.height),b.textContent.trim().length]})''')
    check('desktop: cells are 16 px squares', bool(squares) and all(s[0] == 16 and s[1] == 16 for s in squares),
          sorted({tuple(s[:2]) for s in squares})[:5])
    check('desktop: cells show no words', all(s[2] <= 2 for s in squares), max((s[2] for s in squares), default=None))
    check('desktop: sub-columns are R, W, T',
          js('''const t=document.querySelector("#views table");const s=[...t.querySelectorAll("thead th")].map(x=>x.textContent.trim()).filter(x=>["R","W","T"].includes(x));
          return s.length>0 && s.every((x,i)=>x==="RWT"[i%3])'''))
    shot('wp10-main-desktop')
    cell = m.find_element(By.CSS_SELECTOR, '#views tbody button')
    Actions(m).sequence('pointer', 'mouse', {'pointerType': 'mouse'}).pointer_move(0, 0, origin='viewport').pointer_move(0, 0, origin=cell).perform()
    check('desktop: hovering a square shows the shared tooltip',
          js('const t=document.getElementById("tooltip");return !t.hidden && t.textContent.trim().length>0'))
    shot('wp10-main-desktop-tooltip')
    cell.click()
    check('desktop: clicking a square opens the evidence panel',
          js('const p=document.getElementById("panel");return !p.hidden && p.textContent.trim().length>0'))
    shot('wp10-main-desktop-panel')
    m.find_element(By.ID, 'close').click()
    js('document.getElementById("view").value="comparison";document.getElementById("view").dispatchEvent(new Event("change"))')
    check('desktop: comparison view page does not scroll sideways', js('return document.documentElement.scrollWidth<=innerWidth'))
    shot('wp10-comparison-desktop')

    # ---- phone, 390 px: a 390 px iframe gives an exact phone viewport (Firefox clamps desktop windows)
    harness = ROOT / 'map/phone-harness.html'
    harness.write_text(f'<!doctype html><meta charset="utf-8"><style>body{{margin:0}}iframe{{width:390px;height:844px;border:0}}</style><iframe src="{PAGE.name}"></iframe>')
    try:
        if PAGE.parent != harness.parent:
            raise RuntimeError('the phone harness needs the page inside map/')
        m.navigate(harness.as_uri())
        frame = m.find_element(By.TAG_NAME, 'iframe')
        for view in ('main', 'comparison'):
            m.switch_to_frame(frame)
            js(f'document.getElementById("view").value="{view}";document.getElementById("view").dispatchEvent(new Event("change"))')
            check(f'phone {view}: page does not scroll sideways',
                  js('return innerWidth===390 && document.documentElement.scrollWidth<=innerWidth'),
                  js('return [innerWidth,document.documentElement.scrollWidth]'))
            check(f'phone {view}: tables scroll inside their own box', js('return !!document.querySelector(".view-scroll")'))
            m.switch_to_frame()
            (SHOTS / f'wp10-{view}-phone.png').write_bytes(base64.b64decode(m.screenshot(element=frame)))
    finally:
        harness.unlink()


if __name__ == '__main__':
    sys.exit(main())
