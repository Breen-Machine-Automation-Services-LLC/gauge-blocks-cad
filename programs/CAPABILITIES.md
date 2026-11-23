# Program adapters

`adapters.py` implements `open(path)` and `save(opened, path, format, version, encoding)` and reports the exact build. Each adapter also has `save_many(jobs)` for batches (jobs are `(source, dest, format, version, encoding)`; the result maps each dest to `None` or an error string). Every written file is byte-scanned for names (`privacy.py`) before it is kept. ODA runs its installed AppRun under `xvfb-run`; distinct display numbers permit simultaneous conversions. Subprocesses run in the foreground. Temporary files stay in this repository. The adapter compiles `oda_identity.c` with `cc` and loads it only into ODA so its automatic save-author metadata uses the fictional `ZEV_OPERATOR` instead of the machine account name. Other account properties and filesystem permissions are unchanged.

| Program | Exact build | Output | Versions and encoding |
| --- | --- | --- | --- |
| ezdxf | 1.4.4 | DXF | R12 ASCII; 2000, 2004, 2007, 2010, 2013 and 2018 ASCII and binary |
| ODA File Converter | 27.1.0.143450 | DWG | R12, 2000, 2004, 2007, 2010, 2013 and 2018, binary |
| ODA File Converter | 27.1.0.143450 | DXF | R12, 2000, 2004, 2007, 2010, 2013 and 2018, ASCII and binary |
| BricsCAD | V26, rpm `bricscadv26-26.2.07-1.x86_64` (its files carry Teigha 26.9.0.0) | DXF | R12, 2000, 2004, 2007, 2010, 2013 and 2018, ASCII (`SaveAs`) and binary (`DXFOUT`) |
| BricsCAD | same | DWG | 2000, 2004, 2007, 2010, 2013 and 2018, binary. No DWG R12 (no `SaveAs` type for it; recorded as not run) |
| CADCraft | upstream commit a70b9b02 (`cadcraft-cli 0.21.0 (dev)`, binary sha256 `c6849d54...0092`) | DXF | 2000, 2004, 2007, 2010, 2013 and 2018, ASCII only |
| CADCraft | same | DWG | 2000, 2004, 2007, 2010, 2013 and 2018 |

Each capability above was verified by a save followed by a read (`checker/test_privacy.py` writes every BricsCAD, ODA and CADCraft case; `generators/run_cross.py` and `generators/run_bricscad.py` read every output).

ODA's `DXB` command-line output type produces a `.dxf` file with the `AutoCAD Binary DXF` signature on this build. This was checked by reading the output with ezdxf, including R12 (`checker/probe_oda_r12_binary.py`). This observation concerns this converter's switch; the separate historical DXB interchange format is not being claimed to be binary DXF. The adapter selects `DXB` for binary DXF and `DXF` for ASCII DXF. `checker/verify_oda.py` verifies the cross-set versions and encodings, provenance records and checker coverage.

## BricsCAD

Launched only through the shared locked wrapper `bcad_run.sh` (one BricsCAD at a time across all agents), in chunks of 40 files per session, with a stall watchdog (`bricscad_batch.py`, `bricscad_batch.lsp`). A session needs about 5 to 20 seconds to start; a chunk of 40 saves takes about 35 seconds.

**Binary DXF is writable.** The earlier belief that BricsCAD cannot write binary DXF was wrong for the `DXFOUT` command: `DXFOUT <file> V <version> B` writes a file that starts with `AutoCAD Binary DXF`, and ezdxf reads it back at the requested version (R12, 2000 to 2018). Evidence: `native/bricscad/k_tables_2018_binary.dxf`, `native/bricscad/k_tables_R12_binary.dxf`. `SaveAs` has no binary type (types 2, 3, 6, 7, 10, 11, 15 and 16 were rejected as invalid arguments; 5, 9 wrote ASCII DXF, 8 an old DWG and 14 a template, none binary).

The plain table's drawn block (`*T2`) omits B1 although its cell data holds it. The tables intent expects cell data.

**Measured downgrade at R12.** BricsCAD writes tables as INSERT of anonymous blocks, regions as POLYLINE and solids as INSERT at DXF R12 (`results/native_bricscad_observations.json`), and writes `ACAD_TABLE` into DXF 2000 although the Reference introduces it with 2005 (same file).

**Native BricsCAD set.** Tables, regions and solids; 40 files across writable formats, versions and encodings. Other intents have cross-set measurements.

**Independence of readers.** BricsCAD writes and reads DWG through the Open Design Alliance's Teigha libraries (the DWG files carry `Teigha(R) 26.9.0.0`), and ODA File Converter is built on the same libraries. Reading a BricsCAD-written DWG with ODA, or an ODA-written DWG with BricsCAD, uses a different program but not an independent DWG engine. CADCraft's DWG code is separate; no CADCraft reader rows exist yet, so every DWG row still shares an engine with one of its programs.

## Privacy: where each program writes the user or author name

Test: a byte search (ASCII and UTF-16LE, case-insensitive) of every produced file for the login name, the full name for the login, the legacy Windows account and the host name finds nothing (`results/privacy_scan.json`: 1411 drawings, 0 hits; `results/privacy_evidence.json`: per format and version). `checker/test_privacy.py` is also a power test: it saves one input with each program's neutralization turned off and shows the scan sees the name.

| Program | Where the name appears (control run, neutralization off) | Neutralization |
| --- | --- | --- |
| BricsCAD | `$LASTSAVEDBY` in every DXF from 2000 on (ASCII and binary); the summary-information last-saved-by field in every DWG 2000 to 2018 (UTF-16LE from 2007); the full path of a text style's font file in DWG 2004 and later when the font lives in the home folder (`~/.local/share/fonts/arial.ttf` here); a `.dwl` lock file naming the host, written next to any file BricsCAD opens in place. DXF R12 carries no name | The wrapper runs BricsCAD in a private mount namespace (`bwrap`, no code injected): a passwd file maps the login and full name to `ZEV_OPERATOR`, and an empty folder hides the user font folder so BricsCAD falls back to a system font. Sources are copied into a scratch folder so no lock file lands beside a published drawing |
| ODA File Converter | `$LASTSAVEDBY` in every DXF and the summary-information field in every DWG from 2000 on | The identity library `oda_identity.c`, as before |
| CADCraft | Nothing: its files carry no last-saved-by field (control test: 0 hits in 12 files) and no font path | None needed |

BricsCAD ignores `USER` and `LOGNAME`; `LOGINNAME` is read-only and comes from the passwd entry. DWG 2004 and later compress some header sections; the control run shows the scan still sees the name in these formats because summary information and the font path are stored uncompressed, but the scan cannot see inside compressed sections, so this is evidence for those fields only.

## Cross sets and readers

DWG outputs are read through an independent converter: ODA reads BricsCAD- and CADCraft-written DWG; BricsCAD reads ODA-written DWG (`results/cross_ezdxf__oda_independent_checks.json` adds BricsCAD rows for the 77 existing ODA-written DWG files, next to the original self-read rows). Binary DXF written by BricsCAD is also read through ODA (binary to ASCII DXF) in the native set. The reader and converter are named on every row. A request a program cannot write (CADCraft: R12 and binary DXF; BricsCAD: DWG R12) is a capability gap in `results/cross_not_run.json`, not a failed row.

DWG comparisons identify the converter and ezdxf as reader.

Machine-readable output capabilities are in `capabilities.json`. A capability gap is not a failed measurement.
