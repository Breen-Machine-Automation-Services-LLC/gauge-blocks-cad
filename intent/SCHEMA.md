# Intent and representation schema

An intent specifies drawing meaning independently of any writer. Six topic files contain invented values and expectations authored in `create.py`. They never derive expectations from generated files. `intent.schema.json` and `provenance.schema.json` use JSON Schema Draft 2020-12.

Every intent has `intent_id`, `title`, and `description`. Only requests without drawings state `status`: `wanted`, `planned`, or `blocked`. Blocked descriptions name the capability needed. Intents with drawings omit status and provide `representation_id`, `features`, and independently authored `expected` fields. The validator rejects handwritten `covered` and `partial` statuses. Each expected field supplies a selector, value, absolute tolerance, applicable DXF versions, and DXF Reference citation.

Coverage is computed for each feature, format, version, and encoding. A drawing in a declared source folder plus a measured result for every declared writable pair with a source in the cell is covered. Missing measurements make it partial and are named. Capability gaps are listed as not possible and do not reduce coverage. The overall intent is covered only when every applicable cell is covered; otherwise it is partial.

The selectors resolve named tables, blocks, attributes, model-space usage counts, linetype definitions, layouts, viewport settings, dictionary objects, XDATA, XRECORDs, and groups. Table defaults specified by DXF are materialized when omitted. VIEW center is normalized to its two DCS coordinates. Simple linetype patterns normalize optional zero element flags. Complex patterns resolve the style handle to its style name. Numeric group-code values and named values are compared as meaning, rather than requiring a particular handle assignment.

The Autodesk DXF Reference sections are given for each field. The viewport color override dictionary mapping is not fully specified there. That field explicitly records the design's AutoCAD tie-breaker requirement, which remains unverified because this phase prohibits using AutoCAD. An ezdxf read-back verifies the stored override, not independent conformance of that undocumented mapping.

All modern versions carry all six topics. R12 carries five topic subsets: it omits named layouts, page setups, plot flags and lineweights, viewport overrides, extension dictionaries, DICTIONARYVAR, groups, scale lists, and complex linetypes. It retains blocks and attributes, 100 layers and supported states, simple linetypes and styles, APPID/XDATA, named views, and UCS records. Applicability lists express these format limitations explicitly.

Each drawing carries identity as `ZEV_IDENTITY` XDATA on the model-space BLOCK: two code-1000 strings for intent and representation. The provenance record repeats both IDs, with writer program and exact build, format, version, encoding, creation script, input digest, content digest, and an ezdxf-based marker. DWG uses `binary` as its encoding; that does not imply binary DXF. Provenance records are named `<drawing>.provenance.json`.

Run from the repository root:

```sh
python -I intent/validate.py
```

Validation checks every intent JSON and every native/cross provenance record, rejects unknown keys and duplicate expected-field IDs, checks identity links and file existence, and requires a provenance record for every drawing. `checker/verify.py` additionally checks embedded identities, provenance record digests, every expected value, audits, and regeneration stability.

Feature selectors resolve entity type and feature layer, then compare an explicit DXF attribute or normalized points, polyline vertices, wipeout boundary, frozen layers, or embedded MTEXT presence. Layer inventory expectations describe source-declared feature layers. R12 is a supported-entity subset; modern objects and layouts are omitted. The native feature runner records audits and expected-field comparisons in `results/features_*.json`.

`feature_fields` maps each feature to its expected-field IDs. The validator checks every mapping and the map uses these associations to show feature-specific differences and version applicability. An unsupported version appears as not applicable, rather than implying the feature exists because the same file carries another feature.

The `identity` selector is checked for every file and is excluded from feature associations and map feature counts. `python -I intent/alignment_expectations.py` applies the independently authored Aligned and Fit policy. `python -I checker/recheck_alignment.py` rechecks those fields using existing DXFs and saved DWG measurements, without CAD saves. An optional `recomputed_width_relative_tolerance` accepts the measured two-point span divided by reader-font width for Fit text, within the declared relative tolerance.
