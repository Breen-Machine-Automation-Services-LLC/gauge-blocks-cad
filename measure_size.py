from pathlib import Path
import json
R=Path(__file__).resolve().parent
stats={}
for folder in sorted(str(d.relative_to(R)) for root in ['native','cross'] for d in (R/root).iterdir() if d.is_dir()):
 files=[p for p in (R/folder).rglob('*') if p.is_file()]
 stats[folder]={'drawings':sum(p.suffix in ['.dxf','.dwg'] for p in files),'drawing_bytes':sum(p.stat().st_size for p in files if p.suffix in ['.dxf','.dwg']),'sidecar_bytes':sum(p.stat().st_size for p in files if p.suffix=='.json')}
 for v in [stats[folder]]:v['total_bytes']=v['drawing_bytes']+v['sidecar_bytes']
base=stats['native/ezdxf']['total_bytes'];total=sum(x['total_bytes'] for x in stats.values())
# Four native writers and twelve ordered writer/resaver pairs.
projection={str(n):round((4*base+12*stats['cross/ezdxf__oda']['total_bytes'])/6*n) for n in [19,40,80]}
(R/'results/size.json').write_text(json.dumps({'measured':stats,'total_bytes':total,'estimated_four_program_bytes_by_intent_count':projection,'assumptions':{'baseline_intents':6,'native_streams':4,'cross_streams':12,'native_baseline':'ezdxf','cross_baseline':'ezdxf__oda'}},indent=2)+'\n')
text='''# Size and storage

Measured by `measure_size.py`; bytes include drawings and identity sidecars, and exclude measurement tables, code, and intent definitions.

| Set | Drawings | Drawing bytes | Sidecar bytes | Total bytes |
| --- | ---: | ---: | ---: | ---: |
'''
for k,v in stats.items():text+=f"| {k} | {v['drawings']} | {v['drawing_bytes']:,} | {v['sidecar_bytes']:,} | {v['total_bytes']:,} |\n"
text+=f'\nMeasured total: **{total:,} bytes** ({total/1048576:.2f} MiB).\n\n'
import collections
agg=collections.defaultdict(lambda:[0,0])
for sc in list((R/'native').rglob('*.json'))+list((R/'cross').rglob('*.json')):
 m=json.loads(sc.read_text());d=Path(str(sc).removesuffix('.provenance.json'));k=(m['program'],m['format']+(' '+m['encoding'] if m['format']=='DXF' else ''));agg[k][0]+=1;agg[k][1]+=d.stat().st_size
text+='Mean drawing size by the program that wrote the file (sidecar program) and format:\n\n| Writer | Format | Files | Mean bytes |\n| --- | --- | ---: | ---: |\n'
for k,(n,b) in sorted(agg.items()):text+=f'| {k[0]} | {k[1]} | {n} | {b//n:,} |\n'
text+='\nBricsCAD writes ASCII DXF files of about one megabyte even for a few entities, and DWG 2000 to 2010 of several hundred kilobytes (its default objects and preview), so the BricsCAD streams dominate the total.\n\n'
text+='''For four programs, the design has four native streams and twelve ordered cross streams: sixteen streams total. Treating each of the thirteen drawn-content topics and six background topics as one intent gives nineteen intents before expanding justifications, block transforms, hatch islands, old and lightweight polylines, and multilingual encodings. Forty to eighty intents is a planning range for that expansion. The current six background intents supply the per-intent baseline. The estimate scales the measured ezdxf native set to four native streams and the measured ODA cross set to twelve cross streams. Other programs may have different formats, compression, and overhead, so this extrapolation is uncertain.

| Planned intents | Estimated bytes for four programs | MiB |
| ---: | ---: | ---: |
'''
for n,v in projection.items():text+=f'| {n} | {v:,} | {v/1048576:.2f} |\n'
text+='''
These estimates assume all programs can build every intent and all ordered cross streams exist. They are capacity estimates, not measured output sizes. Tables, images, dense hatches, embedded previews, and conversion behavior can increase or decrease the average considerably. AutoCAD-only dynamic blocks and proxies remain placeholders, without fabricated byte estimates.

Every drawing, native and resaved, is stored in git.
'''
(R/'SIZE.md').write_text(text);print(json.dumps(stats))
