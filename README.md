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

Our initial focus is 2D drafting for industrial automation schematics and panel layouts. Broader 3D coverage and other domains remain [planned work](DESIGN.md#later-releases).
Formats include DWG, ASCII DXF, and binary DXF, with R12 inputs and versions 2000, 2004, 2007, 2010, 2013, and 2018 where supported.
Features include text, geometry, blocks, attributes, dimensions, layouts, images, tables, regions, and background settings such as layers, styles, and metadata.
See the [coverage table](COVERAGE.md) for details: **measured** means a file exists and every declared writable pair has results, whether or not they show loss; **partly measured** means some results are missing.

## Results

Each program re-saves drawings written by another program; ezdxf 1.4.4 compares its fields (each value it reads, such as a text rotation) with the drawing's intent.
A result tells you whether a feature survives a round trip through that program, as ezdxf reads it.

Measured with ezdxf 1.4.4, BricsCAD V26 (26.2.07-1), ODA File Converter 27.1.0.143450, CADCraft upstream commit a70b9b02, and AutoCAD LT 2027.1.
A result holds for those builds only, so each [release](DESIGN.md#releases-and-versions) names the builds it measured, and each drawing's provenance record names the build that wrote it.
[programs/CAPABILITIES.md](programs/CAPABILITIES.md) gives the full build details.

For DXF read directly, with no DWG step, here is how much each re-saving program keeps; each program's counts cover only files it can write (CADCraft writes neither R12 nor binary DXF), so the rows are not a ranking:

| Re-saving program | Measured features kept in every file | Files keeping every measured field |
| --- | ---: | ---: |
| BricsCAD | 166 of 173 | 88% (412 of 466) |
| CADCraft | 167 of 177 | 74% (88 of 119) |
| ODA File Converter | 169 of 177 | 88% (225 of 255) |
| AutoCAD LT | 167 of 177 | 89% (228 of 255) |

Sources: the [ezdxf-to-BricsCAD](results/cross_ezdxf__bricscad_checks.json), [ODA-to-BricsCAD](results/cross_oda__bricscad_checks.json), [ezdxf-to-CADCraft](results/cross_ezdxf__cadcraft_checks.json), [BricsCAD-to-CADCraft](results/cross_bricscad__cadcraft_checks.json), [ezdxf-to-ODA](results/cross_ezdxf__oda_checks.json), [BricsCAD-to-ODA](results/cross_bricscad__oda_checks.json), [ezdxf-to-AutoCAD](results/cross_ezdxf__autocad_checks.json), and [BricsCAD-to-AutoCAD](results/cross_bricscad__autocad_checks.json) result files; counts combine every source program, DXF version and ASCII or binary file, and skip values the checker cannot score. They describe these drawings rather than full program support.
A feature groups the values assigned to it by its intent and is kept only if every one of its scored values matches in every file. The file count also checks [identity values](DESIGN.md#identity-of-every-file), which identify the intent and its representation.

Here is what you can answer today:

- **Can your program read other programs' output and the standard's forms?** Partly: use [native drawings](native/) and the map's Reads columns. Reader-specific measurements are sparse. AutoCAD LT opens and re-saves the declared ezdxf and BricsCAD inputs, with refusals recorded separately. Whether a successful open loads all intended content still needs a dedicated [drawing-load acceptance test](OPEN-ITEMS.md#autocad-drawing-load-acceptance).
- **Can other programs read your output?** The map's “Program A to program B” view shows round trips through the re-savers above. AutoCAD supplies an independent DWG writing engine; its DWG output is still read through ODA. [Independent reads of ODA-written DWG](OPEN-ITEMS.md#independently-read-oda-written-dwg) remain a gap.
- **Does your program follow the standard?** The [standard inventory](standard/README.md) and “Standard and programs” view link tests to Reference items: 33 of 331 standard items have a tested property, and 7 more are tested in part. The inventory lists missing forms; these tests do not establish conformance.
- **What does each program write for each feature?** Compare [native drawings](native/) from 2 writers and their provenance records. [More native writers](DESIGN.md#programs) and [alternative representations](DESIGN.md#later-releases), such as different encodings of center-justified text, remain gaps.
- **Can you automatically check against read and write sets?** Partly: [drawings](native/), [intents](intent/), and the [checker](checker/check.py) give you a read set. The [compatible write set](#why-this-exists) has no derived manifest yet.

A loss counts against a program only when the source drawing read cleanly. “Source not readable” means the source value did not match its intent; “lost in the DWG writer or converter” means the value survives in DXF but fails through DWG, leaving the writer and converter unresolved. Read failures are shown separately; [capability gaps](programs/CAPABILITIES.md), meaning formats a program does not write, are listed rather than counted as failures.

### Limitations

Read these before relying on a result: each is a way a result can be wrong. [OPEN-ITEMS.md](OPEN-ITEMS.md) tracks the work to close them.

- **One reader judges every value.** Manfred Moitzi's [ezdxf](https://github.com/mozman/ezdxf) has been a strong foundation for this work: it writes the ezdxf version of every drawing from its intent, and it reads every saved file back, across every DXF version and encoding we test. Like any library, it doesn't yet cover every feature. Where we know ezdxf cannot read a feature, the map shows a failed read, meaning the other program's handling of that feature is unknown rather than lost. One example is 3D solid and region data in binary DXF written by BricsCAD at versions 2000 to 2010 ([details](OPEN-ITEMS.md#ezdxf-reads-of-bricscad-binary-dxf-acis-data-before-2013)). Gaps we have not found yet are not flagged.
- **DWG is judged through a second program.** ezdxf does not read DWG, so another program opens each DWG file and saves it as DXF first: ODA File Converter for DWG written by BricsCAD, CADCraft, or AutoCAD, and BricsCAD for DWG written by ODA File Converter. A DWG result therefore reflects the writer and that conversion together.
- **BricsCAD and ODA share a DWG library.** Both use the Open Design Alliance's Teigha library. Agreement between them is evidence of consistency within that engine. AutoCAD writes DWG with an independent engine, but its measured DWG output still passes through ODA before ezdxf reads it.
- **AutoCAD coverage has limits.** AutoCAD LT is a re-saver here, driven by script in a Windows VM. It does not write R12 DWG. It refuses the R12 DXF dimensions and nested-blocks drawings. Its DXF preserves viewport freeze and color settings from 2004 on; at 2000 the freeze settings change while color survives. Some dictionary entries disappear, and ezdxf cannot read some AutoCAD ACIS data. See the measured cases in [OPEN-ITEMS.md](OPEN-ITEMS.md).

Explore the [map](map/index.html): “Standard and programs” separates reads, writes, and round trips; “Program A to program B” compares a pair; “Detailed coverage and compatibility” shows individual files and fields. You can inspect the evidence in [results/](results/) and follow the gaps in [OPEN-ITEMS.md](OPEN-ITEMS.md).

## Contributing and regenerating

Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and regeneration steps, [AGENTS.md](AGENTS.md) for coding-agent instructions, and [DESIGN.md](DESIGN.md) for the design. Regeneration needs the CAD programs installed and configured.

Made by Breen Machine Automation Services.
Code and data: [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE), at your option.
