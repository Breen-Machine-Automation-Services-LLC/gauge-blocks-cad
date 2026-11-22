# Contributing

Intents are the source of truth. Propose a feature by submitting a pull request with a `wanted` intent containing `intent_id`, `title`, `description`, and `status`, or open an issue describing the desired behavior. Use invented content with no real company, person, or place names, local paths, or third-party fonts and images. Code and data are MIT OR Apache-2.0.

Accept a request by writing its expected result and setting `planned`. Add a generator under `generators/` and independent expected fields with DXF Reference sections, selectors, tolerances, and version applicability. Do not derive expected values from a writer's saved output. Put each feature on a distinct named layer. Omit status once drawings exist. Coverage derives covered and partial from native files and measured writable cross pairs. Use `blocked` only for a request awaiting a required capability and name that capability in the description.

Use stable lowercase intent IDs and representation IDs. Drawing filenames use topic, version, and encoding with underscores, no spaces or parentheses. Store native drawings under `native/<program>/` and cross drawings under `cross/<writer>__<resaver>/`. Every drawing needs embedded intent and representation IDs plus `<drawing>.provenance.json`. Record the exact program build, format, version, encoding, generator script, input digest, content digest, and whether the content is ezdxf-based. An input digest identifies the intent and generator inputs; it is separate from the normalized drawing digest.

To add a representation, keep the same intent and semantic expectations, assign a distinct representation ID, and declare the accepted IDs in the intent. Update validation and generator selection together; the initial schema currently supports one representation ID, so that extension remains planned. Do not invent a second intent for an alternative valid encoding of the same meaning.

To add a program adapter, implement the interface in `programs/interface.py`, register its name in the provenance record schema and adapter selection, record the exact public build and measured capabilities, and generate the native and cross sets. Report refused opens as refused, with the error and reader, rather than missing fields. DXF rows name the direct reader; DWG rows name both the reader and converter. Self-read DWG rows must be identified and need an independent reader before claiming independent fidelity. Do not publish results from private fix builds.

Run these commands from the repository root using Python with the pinned requirements installed:

```sh
python -I intent/validate.py
python -I generators/run_features.py
python -I map/build.py
python -I map/check_links.py
python -I checker/check_map_browser.py
```

`regenerate.py` rebuilds the original background native and ODA cross sets, then the feature native set and map. The browser check requires Firefox. `generators/run_features.py` builds and checks feature native DXFs without running BricsCAD. Program generators run from the repository root.

Coverage, the HTML map, and results are generated artifacts. Never hand-edit them. Regenerate them from intentions, provenance records, and measured runs. Review generated diffs along with source changes. Changes and questions about measured behavior go to issues labeled by program and feature, with the exact result row and build. Each entry in `OPEN-ITEMS.md` is ready to copy into an issue.

Copy `settings.example.json` to ignored `settings.local.json` and configure executable locations. All program adapters read these common settings. `CAD_DATASET_SETTINGS` can select a different settings file.

Declare requested writer and re-saver pairs in `programs/pairs.json`, with the source folder. Both the cross runner and map read this list. A declared pair without measurements appears as "not yet run"; undeclared pairs are not expected. A cell has a source when a declared source folder contains its intent, format, version, and encoding. Every writable declared pair with a source in that cell needs a measured result for covered status.

Use `regenerate.py --intent feature_a_text --pairs ezdxf__oda,ezdxf__cadcraft` for a limited regeneration. `--dry-run` lists stale outputs without launching any program or writing files.

## Program developers: compare your build

Use the configured Python environment and an output directory outside this repository:

```sh
python -B -I compare_build.py --program cadcraft --binary /path/to/cadcraft-cli --label my-fix --out /path/to/comparisons
```

This runs every declared pair re-saved by CADCraft, using ODA for DWG checking, without launching BricsCAD. Restrict a run with `--pairs ezdxf__cadcraft,bricscad__cadcraft` or `--intent feature_a_text`. Each label needs a new destination. Drawings, provenance, checks, scratch files, and progress logs live in `<out>/<label>/`; `<out>/<label>-compare.json` and `.md` compare published and new statuses and actual values by pair, file, and field. Feature/cell summaries count field transitions. Status order follows the map: same (kept), not run, differs (changed), absent (lost), refused. A refused open supplies the status for each field when the other build can read the file. Equal statuses count as unchanged even if their actual values differ; both values remain available in the report.

The report records the binary digest and its worktree commit where available, and checks the Git tracked/untracked file list and SHA-256 digests before and after. Imports suppress bytecode writes. Run the configured published binary with label `main` first; it should have zero improved and worsened fields. Private build results stay outside the published dataset.
