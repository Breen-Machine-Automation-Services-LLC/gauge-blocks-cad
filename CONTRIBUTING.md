# Contributing

Glad you're here. Here are a few ways to help; pick the one that fits.

- [Report a result that looks wrong](#report-a-result-that-looks-wrong)
- [Request a feature or drawing variation](#request-a-feature-or-drawing-variation)
- [Add a drawing for an existing feature](#add-a-drawing-for-an-existing-feature)
- [Add a program (adapter)](#add-a-program-adapter)
- [Compare your own program's builds](#program-developers-compare-your-build)
- [Fix or improve the scripts](#fix-or-improve-the-scripts)

## Before you start

Search existing issues and open and closed pull requests before starting. Read the
issue comments, and say which part you are working on in an issue comment. If someone
is already working on it, coordinate there before starting a duplicate. Recheck for
related work before opening your pull request. If you stop, leave an update.

Keep each pull request to one change. Describe the behavior you changed, why, and
how you checked it. A person is accountable for every contribution, including
AI-assisted work. Review everything you submit. Report only the checks you actually
ran, their outcomes, and anything you did not run.

Use synthetic content only: invented values with no real company, person, or place
names, local paths, or third-party fonts and images. Code and data are
[MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE). Unless you say otherwise,
anything you contribute is licensed the same way, as MIT OR Apache-2.0, with no
additional terms.

## Report a result that looks wrong

Open an issue with the drawing file, exact result row and field, program and exact
public build, reader, and converter if used. Include expected and actual values,
the intent, reproduction steps, and any error message. Name the program and feature
in the issue title. [Open items](OPEN-ITEMS.md) contains entries ready to copy into issues.

Check the expected value against the intent first. For a DXF, you can check a file
without launching a CAD program:

```sh
python checker/check.py native/ezdxf/layers_2018_ASCII.dxf
```

DXF rows name the direct reader. DWG rows name both reader and converter. Report a
refused open as `refused`, with the error and reader, rather than as missing fields.
Identify self-read DWG rows, where the writer also supplies the reading engine.
Those rows need an independent reader before you claim independent fidelity.
Describe the observation without assuming which program caused it. Do not publish
results from private fix builds; use the [build comparison workflow](#program-developers-compare-your-build).

## Request a feature or drawing variation

Open an issue describing the desired behavior, a small synthetic example, and what
you expect a reader to find. Name the feature, formats, versions, and encodings you
need. Check [coverage](COVERAGE.md) and [open items](OPEN-ITEMS.md) for existing work.
An issue needs no command checks; say what evidence you inspected.

You can instead submit a `wanted` intent with `intent_id`, `title`, `description`,
and `status`. Intents are the source of truth. To accept a request, write its
expected result and set `planned`. Use `blocked` only when a required capability is
unavailable, and name it in the description. Omit status once drawings exist.
Coverage derives `covered` and `partial` from native files and measured writable
cross pairs. Run `python intent/validate.py` for an intent submission.

A representation is an accepted encoding of the same meaning. For an alternative
valid encoding, keep the same intent and semantic expectations, assign a distinct
representation ID, and declare the accepted IDs in the intent. Do not create a
second intent for it. The initial schema supports one representation ID; extending
that remains planned. Update validation and generator selection together when
adding that support. See the [intent schema](intent/SCHEMA.md).

## Add a drawing for an existing feature

Add a generator under `generators/` and independently authored expected fields to
the intent. Give each field a DXF Reference section, selector (how to find the
value), tolerance, and applicable versions. Set `reference.basis_type` to
`synthetic`, `normative`, `application_semantics`, or `compatibility_policy`, and
set `reference.url` to the exact owning item URL in the [standard inventory](standard/README.md).
Explain any missing item page in `basis`; regenerate intent JSON through its
authoring script or `python intent/traceability.py`. Never derive expected values from a
program's saved output. Put each feature on a distinct named layer.

Use stable lowercase intent and representation IDs. Drawing filenames use topic,
version, and encoding separated by underscores, with no spaces or parentheses.
Store native drawings under `native/<program>/` and cross drawings under
`cross/<writer>__<resaver>/`.

Every drawing needs embedded intent and representation IDs and a sidecar file,
`<drawing>.provenance.json`, recording how it was made. Include the exact program
build, format, version, encoding, generator script, input digest, content digest,
and whether the content is ezdxf-based. The input digest identifies intent and
generator inputs; it is separate from the normalized drawing content digest.
Compute the content digest on the drawing as read, before any audit. See
[digest limitations](checker/VOLATILE.md).

Submit the generator, intent, provenance, and regenerated drawings and measurements
together. Run the [shared checks](#checks-and-regeneration) and regenerate the
changed set. For feature native DXFs, run:

```sh
python generators/run_features.py
python map/build.py
python map/check_links.py
python checker/check_map_browser.py
```

The feature runner builds and checks feature native DXFs without running BricsCAD.
The browser check requires Firefox; see [map testing](map/TESTING.md).

## Add a program (adapter)

An adapter connects a program's open and save operations to the dataset scripts.
Implement [the interface](programs/interface.py), register the name in the
[provenance schema](intent/provenance.schema.json) and adapter selection, and record
the exact public build and measured capabilities. Generate the native and cross
sets. Include those measurements, provenance, and any refused-open evidence in
your pull request. Follow the reader and self-read rules in
[result reports](#report-a-result-that-looks-wrong).

Declare requested writer and re-saver pairs with their source folder in
[programs/pairs.json](programs/pairs.json). Both the cross runner and map read it.
A declared pair without measurements appears as "not yet run"; undeclared pairs
are not expected. A cell has a source when a declared source folder contains its
intent, format, version, and encoding. Every writable declared pair with a source
in that cell needs a measured result for covered status.

Use the [common settings and regeneration steps](#checks-and-regeneration), run
the shared checks, and review generated diffs with your adapter changes. Published
results must use public builds, never private fix builds.

## Program developers: compare your build

Use the configured Python environment and an output directory outside this repository:

```sh
python compare_build.py --program cadcraft --binary /path/to/cadcraft-cli --label my-fix --out /path/to/comparisons
```

This runs every declared pair re-saved by CADCraft, using ODA for DWG checking,
without launching BricsCAD. Restrict a run with
`--pairs ezdxf__cadcraft,bricscad__cadcraft` or `--intent feature_a_text`.
Each label needs a new destination. Drawings, provenance, checks, scratch files,
and progress logs live in `<out>/<label>/`. The `<out>/<label>-compare.json` and
`.md` reports compare published and new statuses and actual values by pair, file,
and field. Feature/cell summaries count field transitions.

Status order follows the map: same (kept), not run, differs (changed), absent
(lost), refused. A refused open supplies the status for each field when the other
build can read the file. Equal statuses count as unchanged even if actual values
differ; both values remain in the report.

The report records the binary digest and its worktree commit where available.
It checks the Git tracked/untracked file list and SHA-256 digests before and after.
Imports suppress bytecode writes. As your baseline check, run the configured
published binary with label `main` first; it should have zero improved and worsened
fields. Keep private build results outside the published dataset. If you report a
published result, include the evidence listed in
[result reports](#report-a-result-that-looks-wrong).

## Fix or improve the scripts

Describe the problem and the resulting behavior in your pull request. Include a
small synthetic reproduction and a regression test when behavior needs one. Keep
unrelated cleanup separate. Run the shared checks below and any tests for the
changed code. If the change affects generated output, regenerate the affected set
and review its diff with the source changes.

## Checks and regeneration

Run commands from the repository root with Python and the pinned requirements:

```sh
python -m pip install -r requirements.txt
python intent/validate.py
python -m pytest tests -q
python map/check_links.py
python map/check_links.py --online   # opens every external link; needs Firefox, see map/TESTING.md
python checker/test_phase2.py
python checker/check_artifacts.py
```

These checks do not replace regeneration when you change drawing generation.
For full verification, `python checker/verify.py` also regenerates outputs and
requires the configured CAD programs. Say explicitly if you could not run it.

Copy [settings.example.json](settings.example.json) to ignored `settings.local.json`
and configure executable locations. All adapters read these common settings.
`CAD_DATASET_SETTINGS` can select another settings file.

`regenerate.py` rebuilds the original background native and ODA cross sets, then
the feature native set and map. Program generators run from the repository root.
Use a limited regeneration for the affected intent and pairs:

```sh
python regenerate.py --intent feature_a_text --pairs ezdxf__oda,ezdxf__cadcraft
```

Add `--dry-run` to list stale outputs without launching programs or writing files.
Regeneration can launch desktop CAD programs and take a long time. Run it in the
foreground and wait for it to finish.

Coverage, the HTML map, and results are generated artifacts. Never edit them by
hand. Regenerate them from intents, provenance records, and measured runs. Review
generated diffs along with source changes.

Published results must be current. `python checker/check_artifacts.py` rejects
missing or stale `scored_with` stamps and reports the row count per results file.
Re-score with `python regenerate.py --intent <intent_id> --pairs <pair_ids>`;
`python generators/run_features.py` refreshes all feature scores, and
`python generators/run_bricscad.py` refreshes native BricsCAD scores.
Current drawings are read again when their scores are stale, without resaving.
`python regenerate.py --dry-run` lists resave and rescore counts before running.
