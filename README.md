# BMAS Gauge Blocks: CAD

Open DWG and DXF interchange test files

A public set of invented drawings and measured results for testing how CAD programs read and write DWG and DXF. Use it to check whether drawings keep their content when moved between programs. Each member of the BMAS Gauge Blocks family is its own repository.

These are test input files and measured results; they are not calibrated standards and do not certify any program.

## Getting started

Clone the repository and install the pinned Python dependencies from its root. The drawings occupy **585,710,531 bytes (558.58 MiB)** in the working tree, excluding provenance sidecars and other files. Every native and resaved drawing is stored in git.

```sh
git clone https://github.com/Breen-Machine-Automation-Services-LLC/gauge-blocks-cad.git
cd gauge-blocks-cad
python -m pip install -r requirements.txt
python -I intent/validate.py
python -I checker/check.py native/ezdxf/layers_2018_ASCII.dxf
```

The first release is `v0.1.0`. Its scope is 2D drafting for industrial automation schematics and panel layouts. 3D modeling and other domains are planned for later releases. [DESIGN.md](DESIGN.md) describes the design.

## Drawings and results

The background set covers six topics, with 77 native drawings and resaves made by ODA File Converter. The feature set covers text, geometry, layouts, dimensions, visual styles, block extents, blocks, attributes, draw order, dictionaries, raster images, custom proxy classes, and miscellaneous geometry. BricsCAD authors tables, regions, and solids under `native/bricscad/`. OLE objects wait for an authoring program that can embed one, and SURFACE entities are planned.

Open [the interactive map](map/index.html) for coverage and measured compatibility, or [COVERAGE.md](COVERAGE.md) for intent status counts. Filter by coverage or compatibility, program pair, format, and status. Expand a topic or use Table view, then select a square for measured fields, the reader, and drawing links. Planned and blocked rows remain visible. ODA-written DWG results include self-reads and BricsCAD reads. BricsCAD and ODA share ODA libraries, so these are separate programs using the same DWG engine. See [contributor instructions](CONTRIBUTING.md) and [open issues](OPEN-ITEMS.md).

| Directory or file | Contents |
| --- | --- |
| `intent/` | Independent expectations, references, schemas, authoring and validation scripts |
| `generators/` | Invented background and feature generators; staged BricsCAD scripts |
| `programs/` | Adapter interface, ezdxf, ODA, BricsCAD and CADCraft adapters, batch wrapper and measured capability limits |
| `native/ezdxf/`, `native/bricscad/` | Native drawings and provenance records |
| `cross/<writer>__<resaver>/` | Resaved drawings and provenance records, stored in git |
| `checker/` | DXF/DWG checker, digest, volatility evidence and verification scripts |
| `results/` | Field-level JSON/CSV tables, audits, digest evidence, barriers and size measurements |
| `SIZE.md` | Measured drawing and sidecar bytes, four-program estimates, and git storage policy |
| `map/` | Generated coverage and compatibility views, builder, link check, and Firefox interaction checks |
| `CONTRIBUTING.md` | Community authoring and provenance rules |
| `OPEN-ITEMS.md` | Reproduction requests and measured open questions |

For an external DXF, supply a matching intent, such as `--intent intent/background_layers.json`. DWG checking also needs a named converter: `python -I checker/check.py drawing.dwg --intent intent/background_layers.json --converter oda`. Each field reports `same`, `differs` with expected and actual values, or `absent`. Numeric tolerances come from the intent; Fit text permits a declared relative tolerance around a font-measured recomputation. Each row names its reader and converter. A converter failure means the file could not be read.

## Regenerating

Regeneration requires the relevant programs. Copy `settings.example.json` to ignored `settings.local.json` and configure their locations. ODA regeneration also requires `xvfb-run`, a C compiler named `cc`, and the installed build recorded in [program capabilities](programs/CAPABILITIES.md). See the [schema](intent/SCHEMA.md) and [volatile fields](checker/VOLATILE.md) for limitations, including independent reading of ODA-written DWG.

```sh
python -B -I regenerate.py --with-bricscad
```

This runs in the foreground and rebuilds native inputs, declared cross pairs, checks, and the map. Without `--with-bricscad`, it lists skipped BricsCAD resaves and uses ODA for DWG reading. Preview the selected outputs without launching programs or writing files with `python -B -I regenerate.py --dry-run --with-bricscad`.

The separate feature runner builds native DXFs and measurements without launching BricsCAD. Coverage, the map, and results are generated artifacts. Drawing and provenance files are rewritten only when their content digest or writer build changes; measurement tables may be refreshed. Regeneration does not commit, push, or run network git commands. ODA's DXB option produces binary DXF.

```sh
python -I generators/run_features.py
python -I map/build.py
python -I map/check_links.py
python -I checker/test_digest.py
python -I checker/verify.py
python -I measure_size.py
```

Firefox interaction checks produce a phone-size render and link evidence under `results/`; see [map/TESTING.md](map/TESTING.md) for `python map/browser_test.py`.

Code and data: MIT OR Apache-2.0, at the user's option.
