# BMAS Gauge Blocks: CAD

This repo includes synthetic CAD drawings, the scripts that create them, and measured results.
It is for you if you build or maintain software that reads or writes DWG or DXF and want to
know which content survives a trip between programs. The drawings are ordinary files,
about 560 MB checked out. They're a best-effort example of how these programs represent
features and settings, not affiliated with any CAD vendor or standards body.

## Quick start

Clone the repo and install the pinned Python dependencies. This check reads a DXF with
ezdxf, an open-source Python library for reading and writing DXF:

```sh
git clone https://github.com/Breen-Machine-Automation-Services-LLC/gauge-blocks-cad.git
cd gauge-blocks-cad
python -m pip install -r requirements.txt
python checker/check.py native/ezdxf/layers_2018_ASCII.dxf
```

Each drawing has an **intent**, an independent file of expected values. The check prints
JSON comparing the drawing with its intent. Here are a few lines from this run, trimmed:

```json
      "field": "layer_count",
      "reader": "ezdxf 1.4.4",
      "expected": 100,
      "tolerance": 0,
      "actual": 100,
      "status": "same",
```

`same` means the value matches within the intent's tolerance; `differs` means it does not;
`absent` means the expected field could not be found. Numeric tolerances come from the intent.

## Test your own program

Open a supplied drawing in your program and save it to a new file. Pass the original
intent with `--intent` so the checker knows what your output should contain:

```sh
python checker/check.py /path/to/your-output.dxf --intent intent/background_layers.json
python checker/check.py /path/to/your-output.dwg --intent intent/background_layers.json --converter oda
```

DWG needs `--converter oda` for ODA File Converter, a DWG/DXF conversion tool, or
`--converter bricscad` for BricsCAD, a desktop CAD program. Configure the installed program
as described below. The converter produces DXF for ezdxf to read; rows name both tools.
When the converter cannot open the DWG, the checker prints `"status": "refused"` with the converter's message and exits with code 2.
For comparisons across your program's builds, see [compare your build](CONTRIBUTING.md#program-developers-compare-your-build).

## What is covered

The scope is 2D drafting for industrial automation schematics and panel layouts.
Drawings exercise text, geometry, dimensions, layouts, blocks, attributes, dictionaries,
raster images, synthetic proxies, tables, regions, solids, and background settings such as
layers, styles, and metadata. Formats include DWG, ASCII DXF, and binary DXF, with R12
inputs and versions from 2000 through 2018 where supported.
A **native drawing** is written by the program that authored it. A **resaved** or **cross
drawing** is opened and saved again by another program. CADCraft, an open-source CAD program,
is also measured as a re-saver. See [program capabilities](programs/CAPABILITIES.md) for builds and limits.

## Where to find results

Use [the interactive map](map/index.html) to explore coverage and compatibility, or
[COVERAGE.md](COVERAGE.md) for a summary. The `results/` folder holds measured fields and audits.
In [the ezdxf-to-BricsCAD results](results/cross_ezdxf__bricscad_checks.json), **97.4% of measured
DXF fields match their intents after BricsCAD resaves ezdxf drawings**, read directly by
ezdxf 1.4.4. This includes ASCII and binary DXF; it is a field count, not a drawing pass rate.
BricsCAD and ODA File Converter use the same DWG library, so agreement between them is not
independent confirmation. See [open questions](OPEN-ITEMS.md) for observations needing follow-up.

## Contribute or regenerate

See [CONTRIBUTING.md](CONTRIBUTING.md) for synthetic-content and provenance rules,
[DESIGN.md](DESIGN.md) for the design, and [AGENTS.md](AGENTS.md) for coding-agent instructions.
Coverage, the map, and `results/` are generated. Expected values come from intents,
never from a program's saved output.

Regeneration needs the relevant programs installed. Copy [settings.example.json](settings.example.json)
to `settings.local.json` and configure their locations. ODA also needs `xvfb-run`, a C compiler
named `cc`, and the installed build listed in [program capabilities](programs/CAPABILITIES.md).
Run `python regenerate.py --with-bricscad` to rebuild drawings, checks, and the map.
See [the intent schema](intent/SCHEMA.md) and [digest limitations](checker/VOLATILE.md) before changing generators.

Made by Breen Machine Automation Services.
Code and data: [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE), at your option.
