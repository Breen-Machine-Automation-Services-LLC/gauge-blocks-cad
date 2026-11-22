"""Firefox/Marionette acceptance checks. Start Firefox with --headless --marionette.
Install marionette_driver in your test environment; set MARIONETTE_PORT if needed.
"""
import base64
import json
import os
from pathlib import Path
from marionette_driver.marionette import Marionette
from marionette_driver import By
from marionette_driver.marionette import Actions

ROOT = Path(__file__).resolve().parents[1]
m = Marionette(port=int(os.environ.get('MARIONETTE_PORT', '2838')))
m.start_session()
m.set_context('content')
results = []
def js(s):
    return m.execute_script(s)
def check(name, expression):
    value=js(expression)
    results.append(dict(behavior=name,passed=bool(value),evidence=value))
    assert value, name

def change(id,value):
    js(f'document.getElementById({json.dumps(id)}).value={json.dumps(value)};document.getElementById({json.dumps(id)}).dispatchEvent(new Event("change"));')

def shot(name):
    js("document.getElementById('tooltip').hidden=true")
    (ROOT/'map/screens'/f'{name}.png').write_bytes(base64.b64decode(m.screenshot(full=False)))

m.set_window_rect(width=1400,height=900)
m.set_window_rect(width=1400,height=900 + (900-js("return innerHeight")))
m.navigate((ROOT/'map/index.html').as_uri())
check('Coverage collapsed: all 30 topics fit 1400 × 900', 'return innerWidth===1400 && innerHeight===900 && document.querySelectorAll(".topic").length===30 && !document.querySelector(".feature") && document.getElementById("gridbox").getBoundingClientRect().bottom<=innerHeight')
check('16 px squares, 2 px gap, DWG and DXF groups', 'let c=document.querySelector(".cell").getBoundingClientRect();return c.width===16 && c.height===16 && getComputedStyle(document.getElementById("grid")).borderSpacing.startsWith("2px") && document.querySelectorAll("#grid .group").length===2')
check('Both views and status labels/icons', 'return document.querySelectorAll("#view option").length===2 && document.querySelectorAll("#legend .swatch").length===7 && [...document.querySelectorAll("#legend .swatch")].every(x=>x.textContent)')
shot('coverage-collapsed')
change('view','coverage')
no_source=m.find_element(By.CSS_SELECTOR,'#grid .no-source')
Actions(m).sequence('pointer','mouse',{'pointerType':'mouse'}).pointer_move(0,0,origin='viewport').pointer_move(0,0,origin=no_source).perform()
check('No-source tooltip explains source capability', 'return /no program in this dataset writes DXF R12 binary as a source/.test(document.getElementById("tooltip").textContent)')
no_source.click()
check('No-source cell opens evidence panel', 'return !document.getElementById("panel").hidden && /no source/.test(document.getElementById("panel").textContent)')
m.find_element(By.ID,'close').click()
change('view','compatibility');change('pair','ezdxf__oda')
check('Compatibility collapsed: all topics fit', 'return document.querySelectorAll(".topic").length===30 && document.getElementById("gridbox").getBoundingClientRect().bottom<=innerHeight')
shot('compatibility-ezdxf-to-oda')
before=js('return document.getElementById("grid").innerHTML')
change('pair','oda__bricscad')
assert before!=js('return document.getElementById("grid").innerHTML')
check('Declared pair selector changes cells and retains not run gaps', 'return document.getElementById("pair").value==="oda__bricscad" && !!document.querySelector("#grid .not-run")')
change('pair','ezdxf__oda')
m.find_element(By.CSS_SELECTOR,'.topic').click()
check('Topic expands to feature rows', 'return document.querySelectorAll(".feature").length===2 && document.querySelector(".topic").getAttribute("aria-expanded")==="true"')
shot('topic-expanded')
# Physical mouse movement exercises the hover handler.
js("document.querySelectorAll('.topic')[1].click()")
cell=m.find_element(By.CSS_SELECTOR,'#grid .lost')
Actions(m).sequence('pointer','mouse',{'pointerType':'mouse'}).pointer_move(0,0,origin='viewport').pointer_move(0,0,origin=cell).perform()
check('Hover tooltip includes feature, format/version, pair, status and fields', 'let t=document.getElementById("tooltip");return !t.hidden && /DWG/.test(t.textContent) && /ezdxf/.test(t.textContent) && /lost/.test(t.textContent) && /vp.freeze|identity/.test(t.textContent)')
cell.click()
check('Click opens panel with all differing fields, both values, reader and links', 'let p=document.getElementById("panel");return !p.hidden && /vp.freeze|identity/.test(p.textContent) && /Expected/.test(p.textContent) && /Actual/.test(p.textContent) && /Reader: ezdxf/.test(p.textContent) && /Input:/.test(p.textContent) && /Output:/.test(p.textContent) && p.querySelectorAll("a").length>=5')
links=js('return [...document.querySelectorAll("#panel a")].map(a=>a.getAttribute("href"))')
assert all((ROOT/'map'/p).resolve().is_file() for p in links)
results.append(dict(behavior='Panel input/output and sidecar links resolve',passed=True,evidence=links))
shot('side-panel')
m.find_element(By.ID,'close').click()
check('Self-read corner marks match measurements', 'return !!document.querySelector("#grid .self") && getComputedStyle(document.querySelector("#grid .self"),"::after").borderTopWidth==="5px"')
change('format','DXF')
check('Format filter limits columns', 'return document.querySelectorAll("#grid .group").length===1 && document.querySelector("#grid .group").textContent==="DXF"')
change('status','changed')
check('Status filter limits squares', 'return document.querySelectorAll("#grid .cell").length>0 && [...document.querySelectorAll("#grid .cell")].every(c=>c.classList.contains("changed"))')
check('Status filter exposes matching features within worse topics', 'return [...document.querySelectorAll("#grid .feature")].some(x=>/100 mixed-state layers/.test(x.textContent))')
changed=m.find_element(By.CSS_SELECTOR,'#grid .changed')
Actions(m).sequence('pointer','mouse',{'pointerType':'mouse'}).pointer_move(0,0,origin='viewport').pointer_move(0,0,origin=changed).perform()
check('Changed tooltip names differing fields', 'return /ZEV_000.linetype/.test(document.getElementById("tooltip").textContent)')
changed.click()
check('Changed panel lists every one of the 50 differing linetypes and both values', 'let p=document.getElementById("details");return p.querySelectorAll("pre").length===100 && [...p.querySelectorAll("h3")].filter(x=>/linetype/.test(x.textContent)).length===50')
m.find_element(By.ID,'close').click()
change('status','all');change('format','all')
check('Summary counts match underlying feature cells', 'return [...document.querySelectorAll("#summary b")].reduce((a,b)=>a+Number(b.textContent),0)===187*21')
m.find_element(By.ID,'tabletoggle').click()
check('Accessible table view uses same labels', 'return !document.getElementById("texttable").hidden && document.getElementById("grid").hidden && /kept/.test(document.getElementById("texttable").textContent) && document.querySelectorAll("#texttable tbody tr").length===217')
m.find_element(By.ID,'tabletoggle').click()
check('Generated timestamp and exact builds', 'return /Generated.*UTC/.test(document.getElementById("builds").textContent) && /1.4.4/.test(document.getElementById("builds").textContent) && /27.1.0.143450/.test(document.getElementById("builds").textContent)')
# Firefox clamps desktop windows to 500 px. An embedded 390 px browsing
# context gives an exact phone CSS viewport without privileged browser access.
harness=ROOT/'map/phone-harness.html'
harness.write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0}iframe{width:390px;height:844px;border:0}</style><iframe src="index.html"></iframe>')
m.navigate(harness.as_uri())
frame=m.find_element(By.TAG_NAME,'iframe')
m.switch_to_frame(frame)
check('Phone has internal grid scroll, no page horizontal overflow', 'let g=document.getElementById("gridbox");return innerWidth===390 && document.documentElement.scrollWidth<=innerWidth && g.scrollWidth>g.clientWidth')
m.switch_to_frame()
(ROOT/'map/screens/phone-width.png').write_bytes(base64.b64decode(m.screenshot(element=frame)))
harness.unlink()
m.navigate((ROOT/'map/index.html').as_uri())
blocked=m.find_element(By.CSS_SELECTOR,'#grid .blocked')
Actions(m).sequence('pointer','mouse',{'pointerType':'mouse'}).pointer_move(0,0,origin='viewport').pointer_move(0,0,origin=blocked).perform()
check('Blocked tooltip names the program it waits on', 'return /AutoCAD/.test(document.getElementById("tooltip").textContent) && /blocked/.test(document.getElementById("tooltip").textContent)')
check('Standalone page has no remote resources', 'return !document.querySelector("script[src],link[href],img[src]") && performance.getEntriesByType("resource").length===0')
m.delete_session()
m=Marionette(port=int(os.environ.get('MARIONETTE_DARK_PORT','2839')))
m.start_session()
m.set_window_rect(width=1400,height=986)
m.navigate((ROOT/'map/index.html').as_uri())
check('Dark scheme media query and surface apply', 'return matchMedia("(prefers-color-scheme: dark)").matches && getComputedStyle(document.documentElement).backgroundColor==="rgb(26, 26, 25)"')
shot('dark-mode')
(ROOT/'map/browser-checks.json').write_text(json.dumps(dict(browser=m.session_capabilities.get('browserVersion'),checks=results),indent=2)+'\n')
m.delete_session()

print(f"{len(results)} Firefox acceptance checks passed")
