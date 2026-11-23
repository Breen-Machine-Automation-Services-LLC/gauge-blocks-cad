# Content digest and volatile fields

The digest is SHA-256 over canonical JSON containing sorted nonvolatile header variables and the exported tags of every live database entity. Entities are exported to a common R2018 tag vocabulary even when the input is R12, avoiding the unsupported direct export of R12's inferred BLOCK_RECORD objects. The digest is computed on the drawing as read, before any audit. ezdxf's audit adds structure to some drawings, including R12 and the misc drawing, while reporting no fixes. This is a program-save comparison digest, not a promise that arbitrary handle renumbering or entity reordering preserves the digest. Handles and references remain significant; the header handle seed alone is excluded.

Excluded header fields:

| Fields | Reason and evidence |
| --- | --- |
| `$TDCREATE`, `$TDUCREATE` | Creation timestamps; change across independent generation runs |
| `$TDUPDATE`, `$TDUUPDATE` | Update timestamps; `$TDUPDATE` observed changing between saves |
| `$TDINDWG`, `$TDUSRTIMER` | Elapsed edit timers; volatile by definition, conservatively excluded |
| `$FINGERPRINTGUID`, `$VERSIONGUID` | File identifiers; version GUID observed changing between saves; R12 load also synthesizes identifiers |
| `$HANDSEED` | Next allocated handle, not drawing content; required exclusion |

Additional observed volatility in ezdxf 1.4.4:

* `EZDXF_META` dictionary entries `CREATED_BY_EZDXF` and `WRITTEN_BY_EZDXF` are DICTIONARYVAR strings containing the library version and a timestamp. Only the value tag (code 1) of those two entries is excluded. Unrelated DICTIONARYVAR values remain significant.
* R12 stores those metadata values as code-1000 strings following the corresponding keys in the `EZDXF` application XDATA on the model-space BLOCK. Only those values in that application are excluded; other XDATA, including the identity, remains significant.

`test_digest.py` saves the same metadata input twice at least one second apart for all six modern versions in ASCII and binary, plus R12 ASCII. `results/digest_evidence.json` records the observed header differences and equality/sensitivity results. A point-location field mutation must change the digest in every case. `checker/verify.py` also regenerates all topics from scratch and verifies that every drawing and provenance record retains identical bytes and modification time.

ODA File Converter build 27.1.0.143450 saved the same 2018 ASCII input twice, more than two seconds apart. The observed differences were `$TDUPDATE` and `$TDUUPDATE`; exported entity tags did not differ. Both headers were already excluded. The two content digests matched, and changing a point location changed the digest. Reproduce with `checker/test_oda_digest.py`; the observed values are in `results/oda_digest_evidence.json`. This sample does not establish that all ODA versions and drawings have no other volatile fields.

ODA's 2000 DXF output also stores drawing-properties timestamps in an XRECORD marked `DWGPROPS COOKIE`. Two saves changed its code 42 value, in addition to update headers. Codes 41 and 42 in that specific record represent creation and update times and are excluded; other XRECORD values remain significant. `checker/test_oda_2000_digest.py` and `results/oda_2000_digest_evidence.json` record the test.

## BricsCAD and CADCraft

`checker/test_volatile_new.py` saves `native/ezdxf/metadata_2018_ASCII.dxf` twice, more than 2.5 seconds apart, with each program, and compares header variables, entity tags and the content digest. DWG saves are read through ODA. Evidence: `results/bricscad_digest_evidence.json` (16 cases: DXF R12 to 2018 ASCII, DXF R12, 2000 and 2018 binary, DWG 2000 to 2018) and `results/cadcraft_digest_evidence.json` (12 cases: DXF and DWG 2000 to 2018).

| Program | Header variables that changed between saves | Entities that changed | Digest |
| --- | --- | --- | --- |
| BricsCAD | `$TDCREATE`, `$TDUPDATE`, `$TDUUPDATE`, `$VERSIONGUID`, `$TDINDWG`, `$TDUSRTIMER`, `$FINGERPRINTGUID` | The `DWGPROPS COOKIE` XRECORD at 2000 only (codes 41 and 42), the same record ODA changes | Equal in all 16 cases |
| CADCraft | `$TDCREATE`, `$TDUPDATE`, `$TDUUPDATE`, `$VERSIONGUID`, `$FINGERPRINTGUID` | None | Equal in all 12 cases |

Every field changed on that input was already excluded. Two regenerations of the BricsCAD region and solid generator (`results/bricscad_generator_rerun_evidence.json`) exposed two more volatile fields, now excluded for ACIS entities only (`REGION`, `3DSOLID`, `BODY`): the per-save unique id in group code 2 (a `{GUID}`), and the build time written in the ACIS data header (SAT text or SAB binary, for example `Sun Nov 22 13:24:09 2026`, blanked before hashing). After the exclusions the region and solid digests match across two runs (DXF 2018 and DWG 2004 sampled); `checker/test_digest.py` still passes, and no ezdxf or ODA drawing contains ACIS data, so no existing digest changed.

**Known exception.** The table drawing read back from BricsCAD's DWG 2004 and 2007 does not always reproduce across two generator runs: one entity (handle 38C in one read-back) lists two owner pointers (group 330) in swapped order, which changes the digest (`results/bricscad_generator_rerun_evidence.json`, entry `k_tables:k_tables_2004_binary.dwg`). DWG 2018 of the same drawing reproduced in every run. Which of the 2004 and 2007 files changes varies from run to run (a regeneration run, `results/bricscad_regeneration_stability.json`, rewrote only `k_tables_2007_binary.dwg`). The cause (writer ordering or the ODA read-back) is not established, and the swapped-pointer entry is a hypothesis about ordering, not a confirmed mechanism. Regeneration may therefore rewrite one of these files. A one-field change (a layer name) changed the digest for both programs. The samples do not establish that no other volatile field exists for other drawings. Two runs of the BricsCAD table and region generator also left every drawing and provenance record byte-identical (`generators/run_bricscad.py` rewrites a file only when its digest or build changes).

## Semantic status and digest

The content digest is unaffected by semantic name comparison. It is a regeneration
fingerprint, not a kept/changed comparison. Case, anonymous names, handles, references,
proxy envelopes, layer flags and tag order remain in its input under the exclusions
above. [Autodesk symbol-name semantics](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-DevGuide/files/GUID-83ABF20A-57D4-4AB3-8A49-D91E0F70DBFF.htm)
and [anonymous-number allocation](https://help.autodesk.com/cloudhelp/2026/PLK/AutoCAD-AutoLISP/files/GUID-EB9BFDAA-487A-4586-A556-1F5F84BCF2F3.htm)
govern semantic status only; they do not authorize dropping reference-graph identity
from the digest. Compute the digest on the drawing as read, before any audit.
