"""Summarize existing measured cross discrepancies for issue preparation."""
from pathlib import Path
from collections import defaultdict,Counter
import json
R=Path(__file__).resolve().parents[1]
rows=json.loads((R/'results/checks.json').read_text());bad=[r for r in rows if r['file'].startswith('cross/ezdxf__oda/') and r['status']!='same']
text='''# Open items

## Reproduce DWG 2007 container acceptance across readers

Investigate the reported case where DWG 2007 output opens in its writer but is refused by another reader. The 2007 container differs from other versions. This repository has no measured refusal row for that pair, so the report is an unverified reproduction request, not a defect attributed to a program. Add a minimal synthetic input, exact public builds, reader error, and per-version acceptance rows. Acceptance requires reproducing or closing the report with measured evidence.

## Compare Fit and Aligned text through DXF and DWG

Investigate the report that one reader interprets Fit and Aligned text differently in DXF and DWG. There is no measured row for that reader in this repository. Use the text intent with both alignment points, height, width factor, rotation, and horizontal and vertical justification. Record exact builds and both result rows before attributing a defect. Acceptance requires a format comparison with an independent DWG reader.

## Independently read ODA-written DWG

The DWG rows in `results/checks.json` identify ODA as converter and `self_read: true`. Add an independent DWG reader with an exact public build, preserve the self-read evidence, and compare both readers against the intents. Acceptance requires independent rows for every ODA-written DWG.

## Investigate measured ezdxf to ODA field changes

`results/checks.json` contains the measured evidence below. These are field observations, not proof that the writer is defective; DWG observations use ODA self-read. Preserve writer, reader, converter, build, format, and version when reproducing each row.

| Topic | Differing | Missing | Fields | Evidence row file |
| --- | ---: | ---: | --- | --- |
'''
groups=defaultdict(list)
for r in bad:groups[r['intent_id']].append(r)
for topic,rs in sorted(groups.items()):
 c=Counter(r['status'] for r in rs)
 summary='Missing embedded identity in R12 DWG' if topic!='background_layers' else '100 linetype-name capitalization differences (Continuous versus CONTINUOUS); 24 missing viewport freeze and 24 missing viewport color fields; one missing R12 DWG identity'
 text+=f"| {topic} | {c['differs']} | {c['absent']} | {summary} | `{rs[0]['file']}` |\n"
text+='\nRepresentative measured rows in `results/checks.json`: `cross/ezdxf__oda/layers_R12_ASCII.dxf`, field `ZEV_000.linetype`, expected `Continuous`, actual `CONTINUOUS`; `cross/ezdxf__oda/layers_2000_ASCII.dxf`, fields `vp.freeze` and `vp.color`, actual absent; `cross/ezdxf__oda/blocks_R12_ASCII.dwg`, field `identity`, actual absent (ODA self-read).\n'
text+='\nAcceptance requires a minimized reproduction for each feature, an independent interpretation of the DXF Reference, and before/after measured rows. Total: '+str(sum(r['status']=='differs' for r in bad))+' differing and '+str(sum(r['status']=='absent' for r in bad))+' missing fields.\n'
for title,key,goal in [('AutoCAD dynamic blocks','dynamic_blocks','Author invented dynamic-block evaluation data and test preservation.'),('AutoCAD AEC proxy objects','aec_proxy','Author invented AEC objects and test class, payload, and proxy preservation.'),('AutoCAD drawing-load acceptance','acceptance','Verify that a successful open actually loads the intended drawing content.')]:
 text+=f'\n## {title}\n\nBlocked on AutoCAD availability. See `intent/future_{key}.json`. {goal} Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.\n'
text += '\n' + (R/'map/open_items_notes.md').read_text()
(R/'OPEN-ITEMS.md').write_text(text)
