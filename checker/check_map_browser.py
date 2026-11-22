"""Render the map in a headless browser and verify all local targets."""
from pathlib import Path
import json,os,shutil,subprocess,sys,tempfile
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from programs.settings import SETTINGS
subprocess.run([SETTINGS['python'],'-I',str(R/'map/check_links.py')],check=True)
firefox=shutil.which('firefox')
if not firefox:raise RuntimeError('Firefox is required for the headless map render')
with tempfile.TemporaryDirectory(prefix='cad-map-',dir='/tmp') as scratch:
 profile=Path(scratch)/'profile';profile.mkdir()
 env=dict(os.environ,XDG_CACHE_HOME=scratch,GSETTINGS_BACKEND='memory')
 completed=subprocess.run([firefox,'--headless','--no-remote','--profile',str(profile),'--screenshot',str(R/'results/map-mobile.png'),'--window-size','390,844',(R/'map/index.html').as_uri()],env=env,capture_output=True,text=True,timeout=45)
 assert completed.returncode==0,completed.stderr
 assert (R/'results/map-mobile.png').stat().st_size>0
 evidence=dict(browser='Firefox',headless=True,exit_code=completed.returncode,viewport=[390,844],screenshot='results/map-mobile.png',links=json.loads((R/'map/link-checks.json').read_text()),cache_warnings='Fontconfig error' in completed.stderr)
 (R/'results/map_browser.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
