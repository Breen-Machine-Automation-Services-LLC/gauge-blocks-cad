# Map checks

Build with `python map/build.py`. Open `map/index.html` directly; it needs no server or network. The builder reads intents, native/cross provenance records, and result checks, and writes only `map/index.html`. Its JSON payload is embedded as base64-encoded gzip in the single inline script. The browser uses the standard `DecompressionStream` API before initializing any view; no side files or fetch requests are needed. Offline checks decode the same payload with `map.check_links.page_data`. Its presentation template is `map/template.html`.

The default **Standard and programs** view groups the DXF inventory by kind, shows dataset coverage, and gives each program Reads, Writes and Round trip cells. **Program A to program B** offers writers and resavers from the declared pairs, with feature outcomes, slot counts, reader/converter evidence, and a feature summary. Select a cell in either view to inspect its evidence and follow its filtered link into **Detailed coverage and compatibility**.

The detailed view retains Coverage and Compatibility modes, pair/format/status filters, expandable topics, and the accessible table. Counts name feature cells, measured features, or format/version/encoding slots as appropriate; unknown measurements remain unknown.

`python map/test_build.py` exercises refused conversion evidence when no output provenance record exists, using temporary fixtures.

`python map/check_links.py` checks that every drawing, provenance record and intent link in the page resolves, and that every Autodesk reference link points at the DXF reference edition set in `standard/reference_catalog.py`. It writes `map/link-checks.json`. Add `--online` to open every external link in the page and the tracked text files in headless Firefox (same `marionette_driver` setup as the browser suite below); it fails on any page that does not load or shows "Page Not Found", and writes `logs/link-check-online.json`. Autodesk's help pages answer normally and then hand over to a viewer that can still show "Page Not Found", so only a browser can check them. In a Chromium-based browser that viewer fails on the 2025 and later editions, while Firefox shows them, so the online check cannot catch that case; `tests/test_reference_links.py` instead keeps DXF reference links at exactly the 2024 edition and every other Autodesk help link at 2024 or older.

For the browser suite, install `marionette_driver` in a temporary Python environment. Create your own scratch directory (for example `/tmp/wp6-codex/`) and two temporary Firefox profiles within it with these `user.js` preferences:

```js
// Light profile
user_pref("marionette.port", 2838);
user_pref("layout.css.prefers-color-scheme.content-override", 1);
// Dark profile: use port 2839 and content-override 0 instead.
```

Run each Firefox in a separate foreground terminal:

```sh
firefox --headless --no-remote --profile /tmp/wp6-codex/light --marionette about:blank
firefox --headless --no-remote --profile /tmp/wp6-codex/dark --marionette about:blank
```

Then run `python map/browser_test.py` in that Python environment. Ports can be changed with `MARIONETTE_PORT` and `MARIONETTE_DARK_PORT`. Results go to `map/browser-checks.json`, and screenshots of both new views in light/dark and at phone width, plus the detailed view, go to `map/screens/`. Firefox clamps desktop windows to 500 CSS pixels; the phone check uses an exact 390 × 844 iframe browsing context, checks the page inside it, and captures the frame. Desktop screenshots have a 1400 × 900 content viewport.

`map/palette-check.txt` contains the required validator's raw output for the fixed status colors on both surfaces. Those exact required hexes fail its categorical lightness and separation gates. They have been preserved, with distinct icons, text labels, and neutral planned/wanted patterns. Resolving every validator FAIL requires changing the fixed palette or the validation requirement.

`python map/test_coverage.py` builds a synthetic repository with complete, missing-pair, capability-gap, cross-folder DWG source, undeclared-pair, and no-source cells. Browser checks include named missing pairs and the descriptive provenance link. The Coverage screenshot shows the collapsed topics and no-source legend.

Run every `checker/test_*.py` script with the configured Python. When CAD saves are prohibited, run `test_privacy.py --existing-evidence` and `test_volatile_new.py --existing-evidence`; these validate stored integration evidence, and the privacy mode also scans every current drawing. They do not claim fresh program saves. The other digest tests run ezdxf or ODA.

Round trips use source baselines matched by provenance digest and reading path.
A kept field stays kept. A non-kept field with an existing non-kept source is
source not readable; a missing source baseline counts against the resaver and
records source status not measured. A DWG-only loss is lost in writer or converter
only when every directly read DXF output for the same pair, intent, field and
version is kept, naming the converter. A resaved query that raises after a clean
or unmeasured source read is unreadable by reader. These outcomes have
separate summary buckets and reconcile with kept, changed, lost and refused.
Reads cells expose `reader_error` counts and public `read_observation` evidence,
including the ezdxf SAT binary Teigha gap; a native conversion failure after direct
success is lost by converter. Packed evidence preserves the cause and source status.
Real losses, changes and unreadable outputs outrank source and converter excuses
in every roll-up. Round-trip cells, comparison summaries and detailed output runs
also expose `field_counts`, independently of feature and slot totals; output runs
omit zero-valued counters to keep the standalone page within 12,000,000 bytes.
Serialized output runs also omit false flags and repeated `scored_with` stamps
from differences; result files retain the stamps, and positive flags and all
expected/actual values, reading evidence and attribution remain in the page.
Comparison summary field counts deduplicate observations across inventory items
and features. The SAT note applies only to binary DXF with unpadded raw SAT records;
other public-reader failures retain their exception text.
