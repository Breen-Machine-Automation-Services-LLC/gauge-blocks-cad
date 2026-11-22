# Map checks

Build with `python -I map/build.py`. Open `map/index.html` directly; it needs no server or network. The builder reads intents, native/cross provenance records, and result checks, and writes only `map/index.html`. Its presentation template is `map/template.html`.

Use Coverage or Compatibility, select a program pair, format, and status, and expand topics to see individual features. Table view shows all features with text status labels. Declared pairs are selectable, including unmeasured pairs that remain not run. Counts describe feature cells, before status filtering, rather than topic summary squares. The evidence panel compares measured output with intent values; source drawings and their provenance records are linked by provenance digest.

`python -I map/test_build.py` exercises refused conversion evidence when no output provenance record exists, using temporary fixtures.

`python -I map/check_links.py` checks all embedded links and writes `map/link-checks.json`.

For the browser suite, install `marionette_driver` in a temporary Python environment. Create two temporary Firefox profiles with these `user.js` preferences:

```js
// Light profile
user_pref("marionette.port", 2838);
user_pref("layout.css.prefers-color-scheme.content-override", 1);
// Dark profile: use port 2839 and content-override 0 instead.
```

Run each Firefox in a separate foreground terminal:

```sh
firefox --headless --no-remote --profile /tmp/cad-map-v2-profile --marionette about:blank
firefox --headless --no-remote --profile /tmp/cad-map-v2-dark --marionette about:blank
```

Then run `python map/browser_test.py` in that Python environment. Ports can be changed with `MARIONETTE_PORT` and `MARIONETTE_DARK_PORT`. Results go to `map/browser-checks.json`, and six screenshots go to `map/screens/`. Firefox clamps desktop windows to 500 CSS pixels; the phone check uses an exact 390 × 844 iframe browsing context, checks the page inside it, and captures the frame. Desktop screenshots have a 1400 × 900 content viewport.

`map/palette-check.txt` contains the required validator's raw output for the fixed status colors on both surfaces. Those exact required hexes fail its categorical lightness and separation gates. They have been preserved, with distinct icons, text labels, and neutral planned/wanted patterns. Resolving every validator FAIL requires changing the fixed palette or the validation requirement.

`python -I map/test_coverage.py` builds a synthetic repository with complete, missing-pair, capability-gap, cross-folder DWG source, undeclared-pair, and no-source cells. Browser checks include named missing pairs and the descriptive provenance link. The Coverage screenshot shows the collapsed topics and no-source legend.

Run every `checker/test_*.py` script with the configured Python. When CAD saves are prohibited, run `test_privacy.py --existing-evidence` and `test_volatile_new.py --existing-evidence`; these validate stored integration evidence, and the privacy mode also scans every current drawing. They do not claim fresh program saves. The other digest tests run ezdxf or ODA.
