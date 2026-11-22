"""Common adapters: open, save(format, version, encoding), exact build.

Every adapter also offers save_many(jobs) for batches: jobs are (source, dest, format, version, encoding) tuples and the
result maps each dest to None (written) or an error string (refused or failed). Every written file is privacy scanned
(programs/privacy.py) before it reaches its destination, so an unneutralized writer cannot publish a name unnoticed.
"""
import os,shutil,subprocess,tempfile,threading
from pathlib import Path
import ezdxf
from programs import privacy
from programs.settings import SETTINGS
ROOT=Path(__file__).resolve().parents[1]
SCRATCH_ROOT=ROOT/'results'
VERSIONS={'2000':'AC1015','2004':'AC1018','2007':'AC1021','2010':'AC1024','2013':'AC1027','2018':'AC1032','R12':'AC1009'}
def workdir(prefix='work-'):
 """A private scratch directory inside the repository results folder (callers remove it)."""
 return tempfile.mkdtemp(dir=SCRATCH_ROOT,prefix=prefix)
class Ezdxf:
 name='ezdxf';build=ezdxf.__version__
 def open(self,path):return ezdxf.readfile(path)
 def save(self,doc,path,format,version,encoding):
  if format!='DXF':raise ValueError('ezdxf cannot write DWG')
  if doc.dxfversion!=VERSIONS[version]:raise ValueError('Generate at target version')
  doc.saveas(path,fmt='bin' if encoding=='binary' else 'asc')
_identity_lock=threading.Lock()
_identity_temp=None
def identity_library():
 global _identity_temp
 with _identity_lock:
  if _identity_temp is None:
   _identity_temp=tempfile.TemporaryDirectory(dir=SCRATCH_ROOT,prefix='oda-identity-')
   lib=Path(_identity_temp.name)/'identity.so'
   subprocess.run(['cc','-shared','-fPIC','-o',str(lib),str(Path(__file__).with_name('oda_identity.c')),'-ldl'],check=True,capture_output=True,text=True,timeout=60)
  return str(Path(_identity_temp.name)/'identity.so')
class Oda:
 name='oda';build=SETTINGS['oda_build']
 def open(self,path):return Path(path)
 def _run(self,inp,out,version,output_type,pattern,count=1,identity=True):
  command=[str(Path(__file__).with_name('oda.sh')),str(inp),str(out),'ACAD'+('12' if version=='R12' else version),output_type,'0','1',pattern]
  for attempt in range(3):
   r=subprocess.run(command,capture_output=True,text=True,timeout=60+8*count,env={**os.environ,'ODA_IDENTITY_LIB':identity_library() if identity else ''})
   if not r.returncode:break
   if not any(x in (r.stdout+r.stderr) for x in ('could not connect to display','X11 connection broke','Xvfb failed to start')):break
  if r.returncode:raise RuntimeError(f'ODA exited {r.returncode}: {r.stdout} {r.stderr}')
  return r
 def save(self,source,path,format,version,encoding):
  if format == 'DXF' and encoding not in ('ASCII','binary'):raise ValueError('Unsupported DXF encoding')
  if format == 'DWG' and encoding != 'binary':raise ValueError('DWG requires binary encoding')
  with tempfile.TemporaryDirectory(dir=SCRATCH_ROOT) as tmp:
   root=Path(tmp);inp=root/'in';out=root/'out';inp.mkdir();out.mkdir()
   shutil.copyfile(source,inp/Path(source).name)
   output_type='DXB' if format=='DXF' and encoding=='binary' else format
   r=self._run(inp,out,version,output_type,'*.dxf' if Path(source).suffix.lower()=='.dxf' else '*.dwg')
   files=list(out.glob('*.'+format.lower()))
   if len(files)!=1:raise RuntimeError('ODA did not produce one output: '+r.stdout+r.stderr)
   privacy.assert_clean(files[0])
   shutil.copyfile(files[0],path)
 def save_many(self,jobs):
  """One ODA launch per (source type, output type, version) group; inputs get unique numbered names."""
  results={};groups={}
  for source,dest,format,version,encoding in jobs:
   if format=='DXF' and encoding not in ('ASCII','binary') or format=='DWG' and encoding!='binary':results[dest]='unsupported encoding';continue
   groups.setdefault((Path(source).suffix.lower(),'DXB' if format=='DXF' and encoding=='binary' else format,version),[]).append((source,dest,format))
  for (suffix,output_type,version),items in groups.items():
   tmp=workdir('oda-');root=Path(tmp);inp=root/'in';out=root/'out';inp.mkdir();out.mkdir()
   try:
    for i,(source,dest,format) in enumerate(items):shutil.copyfile(source,inp/f'{i}{suffix}')
    try:self._run(inp,out,version,output_type,'*'+suffix,len(items))
    except Exception as ex:
     for _,dest,_ in items:results[dest]='ODA failed: '+str(ex)[:300]
     continue
    for i,(source,dest,format) in enumerate(items):
     produced=out/f'{i}.{format.lower()}'
     if not produced.exists():results[dest]='ODA produced no output';continue
     try:privacy.assert_clean(produced)
     except privacy.PrivacyError as ex:results[dest]=str(ex);continue
     shutil.copyfile(produced,dest);results[dest]=None
   finally:shutil.rmtree(tmp,ignore_errors=True)
  return results
 def read_dwg(self,path):
  with tempfile.TemporaryDirectory(dir=SCRATCH_ROOT) as tmp:
   p=Path(tmp)/'read.dxf';self.save(path,p,'DXF','2018','ASCII');return ezdxf.readfile(p)
 def read_dwg_many(self,paths):
  """Convert DWG files to ASCII DXF 2018 for reading. Returns {path: ezdxf document or error string}."""
  tmp=workdir('oda-read-');results={}
  try:
   jobs=[(p,Path(tmp)/f'{i}.dxf','DXF','2018','ASCII') for i,p in enumerate(paths)]
   status=self.save_many(jobs)
   for (p,dest,*_) in jobs:
    if status[dest] is not None:results[p]=status[dest]
    else:
     try:results[p]=ezdxf.readfile(dest)
     except Exception as ex:results[p]='read failed: '+str(ex)[:300]
  finally:shutil.rmtree(tmp,ignore_errors=True)
  return results
class BricsCad:
 """BricsCAD V26 driven through the shared locked wrapper; see programs/bricscad_batch.py."""
 name='bricscad'
 build='26.2.07-1 (bricscadv26 rpm, Linux x86_64)'
 # vla-SaveAs numeric types. Binary DXF is written with the DXFOUT command (spec "B:<version>").
 TYPES={('DXF','R12'):1,('DXF','2000'):13,('DXF','2004'):25,('DXF','2007'):37,('DXF','2010'):49,('DXF','2013'):61,('DXF','2018'):65,
        ('DWG','2000'):12,('DWG','2004'):24,('DWG','2007'):36,('DWG','2010'):48,('DWG','2013'):60,('DWG','2018'):64}
 def open(self,path):return Path(path)
 def spec(self,format,version,encoding):
  if format=='DXF' and encoding=='binary':return 'B:'+version
  if format=='DWG' and encoding!='binary':raise ValueError('DWG requires binary encoding')
  if (format,version) not in self.TYPES:raise ValueError(f'BricsCAD cannot write {format} {version}')
  return str(self.TYPES[(format,version)])
 def save(self,source,path,format,version,encoding):
  r=self.save_many([(source,path,format,version,encoding)])[path]
  if r is not None:raise RuntimeError(r)
 def save_many(self,jobs,tag='bcb',shield=True,scan=True):
  from programs.bricscad_batch import run_batch
  results={};work=Path(workdir('bricscad-'));inp=work/'in';out=work/'out';inp.mkdir();out.mkdir();tasks=[];planned={}
  try:
   by_source={}
   for i,(source,dest,format,version,encoding) in enumerate(jobs):
    try:spec=self.spec(format,version,encoding)
    except ValueError as ex:results[dest]=str(ex);continue
    by_source.setdefault(str(source),[]).append((i,dest,format,spec))
   for n,(source,items) in enumerate(by_source.items()):
    folder=inp/str(n);folder.mkdir();local=folder/Path(source).name;shutil.copyfile(source,local);outs=[]
    for i,dest,format,spec in items:
     produced=out/f'{i}.{format.lower()}';outs.append((str(produced),spec));planned[dest]=(produced,str(local))
    tasks.append((str(local),outs))
   log=run_batch(tasks,work,tag,shield=shield)
   for dest,(produced,local) in planned.items():
    st=log.get(local);save=st['saves'].get(str(produced)) if st else None
    if st is None or st['hang']:results[dest]='BricsCAD hung or did not reach the file';continue
    if st['open']!='ok':results[dest]='BricsCAD refused to open: '+str(st['open']);continue
    if save!='OK':results[dest]='BricsCAD save failed: '+str(save);continue
    try:
     if scan:privacy.assert_clean(produced)
    except privacy.PrivacyError as ex:results[dest]=str(ex);continue
    shutil.copyfile(produced,dest);results[dest]=None
  finally:shutil.rmtree(work,ignore_errors=True)
  return results
 def read_dwg_many(self,paths):
  """Open DWG files and write ASCII DXF 2018 for reading. Returns {path: ezdxf document or error string}."""
  tmp=Path(workdir('bricscad-read-'));results={}
  try:
   jobs=[(p,tmp/f'{i}.dxf','DXF','2018','ASCII') for i,p in enumerate(paths)]
   status=self.save_many(jobs,'bcr')
   for (p,dest,*_) in jobs:
    if status[dest] is not None:results[p]=status[dest]
    else:
     try:results[p]=ezdxf.readfile(dest)
     except Exception as ex:results[p]='read failed: '+str(ex)[:300]
  finally:shutil.rmtree(tmp,ignore_errors=True)
  return results
class CadCraft:
 """CADCraft command-line server. Public upstream commit only; never a local fix build."""
 name='cadcraft'
 build='a70b9b02 (upstream main, cadcraft-cli 0.21.0-dev)'
 binary=SETTINGS['cadcraft_binary']
 SAVEAS_VERSIONS={'2000':2000,'2004':2004,'2007':2007,'2010':2010,'2013':2013,'2018':2018}
 def open(self,path):return Path(path)
 def save(self,source,path,format,version,encoding):
  r=self.save_many([(source,path,format,version,encoding)])[path]
  if r is not None:raise RuntimeError(r)
 def save_many(self,jobs):
  from programs.cadcraft_mcp import MCP, HarnessError
  results={};by_source={}
  for source,dest,format,version,encoding in jobs:
   if version not in self.SAVEAS_VERSIONS:results[dest]=f'CADCraft cannot write {version} (saveas versions 2000 to 2018)';continue
   if format=='DXF' and encoding=='binary':results[dest]='CADCraft cannot write binary DXF';continue
   by_source.setdefault(str(source),[]).append((dest,format,version))
  for source,items in by_source.items():
   tmp=Path(workdir('cadcraft-'));m=None
   try:
    m=MCP(self.binary,tmp);(tmp/'in').mkdir();local=tmp/'in'/Path(source).name;shutil.copyfile(source,local)
    for k,(dest,format,version) in enumerate(items):
     produced=tmp/f'o{k}.{format.lower()}'
     try:
      m.call('open',path=str(local))   # saveas renames the session drawing: reopen the original for every save
      m.ex('saveas',path=str(produced),version=self.SAVEAS_VERSIONS[version])
     except HarnessError:raise
     except Exception as ex:results[dest]='CADCraft: '+str(ex)[:300];continue
     if not produced.exists():results[dest]='CADCraft wrote no file';continue
     try:privacy.assert_clean(produced)
     except privacy.PrivacyError as ex:results[dest]=str(ex);continue
     shutil.copyfile(produced,dest);results[dest]=None
   except HarnessError:raise
   except Exception as ex:
    for dest,_,_ in items:results.setdefault(dest,'CADCraft: '+str(ex)[:300])
   finally:
    if m:m.close()
    shutil.rmtree(tmp,ignore_errors=True)
  return results
ADAPTERS={'ezdxf':Ezdxf,'oda':Oda,'bricscad':BricsCad,'cadcraft':CadCraft}
