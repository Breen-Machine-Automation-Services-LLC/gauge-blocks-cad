# BMAS Gauge Blocks: CAD

Open DWG and DXF interchange test files

Each member of the BMAS Gauge Blocks family is its own repository.

These are test input files and measured results; they are not calibrated standards and do not certify any program.

A public set of invented drawings for testing how CAD programs read and write DWG and DXF, so drawings move between programs without losing content. Anyone may use it to test or improve a CAD program or library. [DESIGN.md](DESIGN.md) defines the agreed design.

Scope of the first release: 2D drafting as used for industrial automation schematics and panel layouts. That is expected to cover most common 2D features. 3D modeling and other domains come in later releases.

The background set covers six topics, with 77 native drawings and ODA DXF and DWG resaves. The feature set ports synthetic masters A through N: text, geometry, layouts, dimensions, visual-style objects, block extents, blocks, attributes, draw order and dictionaries, raster images, custom proxy classes, and miscellaneous geometry. Tables, regions, and solids are authored by BricsCAD (native/bricscad). OLE has a blocked intent and SURFACE a planned one.

Open [the interactive map](map/index.html) for coverage and measured compatibility, or [COVERAGE.md](COVERAGE.md) for intent status counts. Use the Coverage/Compatibility selector, program pair, format, and status filters; select a topic to expand it or switch to Table view for text labels. Select a square for field values, reader, and input/output links. Each compatibility result names its reader and links to the drawing. Planned and blocked rows remain visible. ODA-written DWG measurements keep their self-read rows and also have BricsCAD-read rows (BricsCAD and ODA share the ODA libraries, so that is an independent program, not an independent DWG engine). See [contributor instructions](CONTRIBUTING.md) and [open issues](OPEN-ITEMS.md).

| Directory or file | Contents |
| --- | --- |
| `intent/` | Independent expectations, references, schemas, authoring and validation scripts |
| `generators/` | Invented background and feature generators; staged BricsCAD scripts |
| `programs/` | Adapter interface, ezdxf, ODA, BricsCAD and CADCraft adapters, batch wrapper and measured capability limits |
| `native/ezdxf/`, `native/bricscad/` | Native drawings and provenance records (ezdxf for most intents; BricsCAD for tables, regions and solids) |
| `cross/<writer>__<resaver>/` | Resaves: ezdxf to ODA, BricsCAD and CADCraft; ODA to BricsCAD; BricsCAD to ODA and CADCraft |
| `checker/` | DXF/DWG checker, digest, volatility evidence and verification scripts |
| `results/` | Field-level JSON/CSV tables, audits, digest evidence, barriers and size measurements |
| `SIZE.md` | Measured bytes, four-program estimates and storage recommendation |
| `map/` | Generated self-contained coverage and compatibility views, builder, link check, and Firefox interaction checks |
| `CONTRIBUTING.md` | Community authoring and provenance rules |
| `OPEN-ITEMS.md` | Reproduction requests and measured open questions |

Python dependencies are pinned in `requirements.txt`. ODA regeneration also requires `xvfb-run`, a C compiler named `cc`, and the installed ODA build recorded in the capabilities document. Use the supplied environment from the repository root, with isolated Python and script paths:

```sh
python -I intent/validate.py
python -I checker/check.py native/ezdxf/layers_2018_ASCII.dxf
python -I regenerate.py
python -I generators/run_features.py
python -I map/build.py
python -I map/check_links.py
# Firefox interaction checks: see map/TESTING.md
# python map/browser_test.py
python -I checker/test_digest.py
python -I checker/verify.py
python -I measure_size.py
```

The browser smoke check requires Firefox and writes a phone-size render plus link-check evidence under `results/`.

For an external DXF, pass `--intent intent/background_layers.json` or another matching intent. DWG requires an explicitly named converter: `checker/check.py drawing.dwg --intent intent/background_layers.json --converter oda`, with the same Python invocation. Each field reports `same`, `differs` with expected and actual values, or `absent`. Numeric tolerances come from the intent. Most are absolute; Fit text also permits a declared relative tolerance around a font-measured recomputation. The reader and converter are named in each row. A converter failure is a failure to read, not evidence of missing drawing content.

Regeneration runs in the foreground, creates background native files and ODA DXF and DWG resaves, then rebuilds feature native files and the map. The separate feature runner creates native DXFs and measurements without launching BricsCAD. Coverage, the map, and results are generated, never hand-edited. ODA's DXB command-line option is verified to produce binary DXF. It rewrites a drawing and provenance record only when its content digest or writer build changes. Measurement tables may be refreshed. It does not commit, push, or use network git commands. See [program capabilities](programs/CAPABILITIES.md), [schema](intent/SCHEMA.md), and [volatile fields](checker/VOLATILE.md) for limitations, including the independent-converter requirement for assessing ODA-written DWG.

Code and data: MIT OR Apache-2.0, at the user's option.

Copy `settings.example.json` to ignored `settings.local.json` to configure program locations. The current alignment recheck reports 38 native DXF rotation disagreements against the two-point baseline; see `OPEN-ITEMS.md`. The strict native generator check will flag these until the generator rotation is corrected.

Before publishing, the owner can regenerate native inputs, all declared cross pairs (including BricsCAD), checks, and the map with:

```sh
python -B -I regenerate.py --with-bricscad
```

Without `--with-bricscad`, regeneration lists each skipped BricsCAD re-save output and uses ODA for DWG reading. Preview the opted-in cross outputs without launching programs or writing files with `python -B -I regenerate.py --dry-run --with-bricscad`.
