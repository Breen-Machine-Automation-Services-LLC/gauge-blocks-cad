# BMAS Gauge Blocks: CAD

Synthetic drawings to help you build CAD software that works across programs.

## Why this exists

We want to support the creation and testing of open CAD programs for maximum interoperability with other CAD applications and standards.
It helps you answer:

1. Can my program read what other programs write, and everything the standard allows?
2. Can other programs read what my program writes?
3. Does my program follow the standard where one is published?
4. What does each program write for each feature?
5. Is there a read set and a write set I can check my program against automatically?

The read set is here now: the drawings in this repository, covering the variety of forms we have collected. A write set will follow in a later release, derived from measured results: forms every measured program reads back intact, with the most widely compatible form used where a standard is silent.

## What this is

This is a test set of synthetic DWG and DXF drawings, two computer-aided design (CAD) file formats, giving you examples of each feature and variation in each file type, one feature or related topic per file.
Each drawing comes with an **intent**, its expected values written independently of any program, and a **provenance record**, which tells you how it was made.
Several programs write the same content and others open and save it again, so you can see how existing software represents each feature; the [coverage table](COVERAGE.md) shows what is covered and on the roadmap.
This is a best-effort project, not affiliated with any CAD vendor or standards body.

## Pick your path

### Use the test set

You do not need to install anything to use the drawings.
Get the drawings archive, with drawings, intents, provenance records, and results, from the [latest GitHub release](https://github.com/Breen-Machine-Automation-Services-LLC/gauge-blocks-cad/releases/latest), or clone the repo (about 560 MB):

```sh
git clone https://github.com/Breen-Machine-Automation-Services-LLC/gauge-blocks-cad.git
```

Here is how the test set is organized:

- `native/<program>/` holds drawings as each program wrote them.
- `cross/<writer>__<resaver>/` holds drawings after another program opened and saved them again.
- `intent/` holds the expected values. Each drawing has a `<drawing>.provenance.json` beside it.

File names give you the feature or topic, version, and encoding (how the file stores its data).
For example, `native/ezdxf/layers_2018_ASCII.dxf` tests layers in the 2018 version using ASCII text encoding; `native/ezdxf/a_text_2000_binary.dxf` tests text in the 2000 version using binary encoding.
Here, ezdxf is an open-source Python library for reading and writing DXF.

Open a drawing beside its intent, such as the layers drawing and [its expected values](intent/background_layers.json).
The [interactive map](map/index.html) and `results/` show what each program kept or changed.
Point your reader at `native/` and compare what it reads with the intents, or compare how two programs wrote the same feature.

### Run it, test your program, or extend it

From the repository root, use a Python environment with pip and install the pinned dependencies, then run one check:

```sh
python -m pip install -r requirements.txt
python checker/check.py native/ezdxf/layers_2018_ASCII.dxf
```

The checker reads DXF directly with ezdxf. Here are a few real lines of output, trimmed:

```json
      "field": "layer_count",
      "reader": "ezdxf 1.4.4",
      "expected": 100,
      "tolerance": 0,
      "actual": 100,
      "status": "same",
```

`same` means the field matches within the intent's tolerance, `differs` means it changed, and `absent` means it was not found.
To test your program, open a native drawing, save it to a new file, and check that output against the original drawing's intent with `--intent`.
Replace the drawing path with your saved file:

```sh
python checker/check.py native/ezdxf/layers_2018_ASCII.dxf --intent intent/background_layers.json
```

DWG checking needs ODA File Converter, a DWG/DXF conversion tool, or BricsCAD, a desktop CAD program, installed and configured as described in [CONTRIBUTING.md](CONTRIBUTING.md#checks-and-regeneration).
The converter makes DXF for ezdxf to read. You can also use `--converter bricscad`:

```sh
python checker/check.py cross/ezdxf__bricscad/layers_2018_ASCII.dwg --intent intent/background_layers.json --converter oda
```

When the converter cannot open the DWG, the checker prints `"status": "refused"` with the converter's message in `detail` and exits with code 2.
To track your program across builds, follow [compare your build](CONTRIBUTING.md#program-developers-compare-your-build).
To add a feature, drawing, or program, start with [CONTRIBUTING.md](CONTRIBUTING.md).

## What is covered

Our initial focus is 2D drafting for industrial automation schematics and panel layouts. We'll add 3D and other domains in the future.
Formats include DWG, ASCII DXF, and binary DXF, with R12 inputs and versions 2000, 2004, 2007, 2010, 2013, and 2018 where supported.
Features include text, geometry, blocks, attributes, dimensions, layouts, images, tables, regions, and background settings such as layers, styles, and metadata.
See the [coverage table](COVERAGE.md) for details and planned work.

## Results

Explore the [interactive map](map/index.html) or inspect `results/` for measurements.
In [the ezdxf-to-BricsCAD results](results/cross_ezdxf__bricscad_checks.json), **97.4% of measured DXF fields match their intents after BricsCAD resaves ezdxf drawings**, read directly by ezdxf 1.4.4.
This includes ASCII and binary DXF; it is a field count, not a drawing pass rate.
BricsCAD and ODA File Converter use the same DWG library, so agreement between them is not independent confirmation.
CADCraft, an open-source CAD program, is also measured as a resaver. See [open items](OPEN-ITEMS.md) for observations needing follow-up.

## Contributing and regenerating

Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and regeneration steps, [AGENTS.md](AGENTS.md) for coding-agent instructions, and [DESIGN.md](DESIGN.md) for the design. Regeneration needs the CAD programs installed and configured.

Made by Breen Machine Automation Services.
Code and data: [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE), at your option.
