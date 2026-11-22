"""Refresh effective draw order from saved DXFs only; never run CAD programs."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json
import ezdxf
from checker.core import compare

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'F130_sortents_a.redraw_order','F131_sortents_block_a.redraw_order'}

def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--runs',required=True,type=Path);a=p.parse_args()
 intent=json.loads((ROOT/'intent/feature_i_dictionaries.json').read_text())
 intent['expected']=[f for f in intent['expected'] if f['id'] in FIELDS]
 report=[];blocked=[];cache={}
 for build,base in [('published',ROOT),('main',a.runs/'main'),('upr-2094',a.runs/'upr-2094')]:
  counts=defaultdict(lambda:dict(before=Counter(),after=Counter(),rechecked=0,unavailable=0))
  for pair in json.loads((ROOT/'programs/pairs.json').read_text()):
   counts[pair['writer']+'__'+pair['resaver']]
  for label in ('ezdxf','bricscad'):counts['native/'+label]
  for table in sorted((base/'results').glob('*checks.json')):
   rows=json.loads(table.read_text())
   if not isinstance(rows,list):continue
   changed=False
   for r in rows:
    if r.get('field') not in FIELDS:continue
    path=base/r['file'];parts=Path(r['file']).parts
    pair=parts[1] if parts[0]=='cross' else 'native/'+parts[1]
    c=counts[pair];c['before'][r['status']]+=1
    if path.suffix.lower()=='.dxf' and path.is_file():
     if path not in cache:
      cache[path]={x['field']:x for x in compare(ezdxf.readfile(path),intent,'offline')}
     measured=cache[path][r['field']]
     r.update({k:v for k,v in measured.items() if k not in ('reader',)})
     changed=True;c['rechecked']+=1
    else:
     r['detail']={'recheck':'unavailable: no saved DXF readback','comparison_basis':'legacy literal SORTENTS list; effective order has not been measured'}
     changed=True;c['unavailable']+=1
     blocked.append(dict(build=build,pair=pair,file=r['file'],field=r['field'],reason='No saved DXF readback with entity and sort handles; DWG cannot be rechecked without a program run.'))
    c['after'][r['status']]+=1
   if changed:write(table,rows)
  report.extend(dict(build=build,pair=pair,**c) for pair,c in sorted(counts.items()))
 # Refresh embedded published/build rows and transition aggregates in saved comparisons.
 for build in ('main','upr-2094'):
  path=a.runs/f'{build}-compare.json';data=json.loads(path.read_text())
  lookup={}
  for label,base in [('published',ROOT),('build',a.runs/build)]:
   for table in (base/'results').glob('cross_*_checks.json'):
    pair=table.name[len('cross_'):-len('_checks.json')]
    for r in json.loads(table.read_text()):lookup[label,pair,r['file'],r['field']]=r
  rank={'same':0,'not run':1,'differs':2,'absent':3,'refused':4}
  cells=defaultdict(Counter)
  for r in data['rows']:
   if r['field'] in FIELDS:
    for label in ('published','build'):
     fresh=lookup.get((label,r['pair'],r['file'],r['field']))
     if fresh:r[label]=fresh
   delta=rank[r['build']['status']]-rank[r['published']['status']]
   r['change']='improved' if delta<0 else 'worsened' if delta>0 else 'unchanged'
   sidepath=(a.runs/build/r['file']).with_suffix(Path(r['file']).suffix+'.provenance.json')
   if not sidepath.exists():
    declaration=next(p for p in json.loads((ROOT/'programs/pairs.json').read_text()) if p['writer']+'__'+p['resaver']==r['pair'])
    source=ROOT/declaration['sources']/Path(r['file']).name
    if declaration['writer']=='ezdxf':source=source.with_suffix('.dxf')
    sidepath=source.with_suffix(source.suffix+'.provenance.json')
   side=json.loads(sidepath.read_text())
   for feature in r['features']:
    key=(r['pair'],r['intent_id'],feature,Path(r['file']).suffix[1:].upper(),side['version'],'binary' if r['file'].endswith('.dwg') else side['encoding'])
    cells[key][r['change']]+=1
  data['counts']={k:sum(r['change']==k for r in data['rows']) for k in ('improved','worsened','unchanged')}
  data['cells']=[dict(cell=list(k),counts=dict(v)) for k,v in sorted(cells.items())]
  data['draw_order_recheck']='Saved DXFs rechecked; DWG rows retain prior literal-table measurements (see draw-order-recheck.json).'
  write(path,data)
  lines=[f'# {build}', '',json.dumps(data['provenance']), '',data['draw_order_recheck'],'',f"Field counts: {data['counts']}",'','| File | Field | Published status / value | Build status / value | Change |','| --- | --- | --- | --- | --- |']
  def value(r):return (r['status']+' / '+json.dumps(r.get('actual'))).replace('|','\\|')
  lines += [f"| {r['file']} | {r['field']} | {value(r['published'])} | {value(r['build'])} | {r['change']} |" for r in data['rows']]
  path.with_suffix('.md').write_text('\n'.join(lines)+'\n')
 write(a.runs/'draw-order-recheck.json',dict(counts=report,unavailable=blocked))
 lines=['# Offline draw-order recheck','','Counts combine both redraw_order fields. After counts retain unrechecked DWG statuses; the unavailable column identifies those rows.','','| Build | Pair | Before | After | Rechecked | Unavailable |','| --- | --- | --- | --- | ---: | ---: |']
 lines += [f"| {r['build']} | {r['pair']} | {dict(r['before'])} | {dict(r['after'])} | {r['rechecked']} | {r['unavailable']} |" for r in report]
 lines+=['','## upr-2094 effective orders','']
 for path,measured in sorted(cache.items()):
  if a.runs/'upr-2094' not in path.parents:continue
  lines.append(f'- `{path.relative_to(a.runs)}`: '+ '; '.join(f"{field}: {row.get('actual')} ({row['status']})" for field,row in measured.items()))
 (a.runs/'draw-order-recheck.md').write_text('\n'.join(lines)+'\n')
 print('\n'.join(lines[:len(report)+7]));print('Unavailable rows:',len(blocked))

if __name__=='__main__':main()
