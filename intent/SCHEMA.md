# Intent and representation schema

An intent specifies drawing meaning independently of any writer. Six topic files contain invented values and expectations authored in `create.py`. They never derive expectations from generated files. `intent.schema.json` and `provenance.schema.json` use JSON Schema Draft 2020-12.

Every intent has `intent_id`, `title`, and `description`. Only requests without drawings state `status`: `wanted`, `planned`, or `blocked`. Blocked descriptions name the capability needed. Intents with drawings omit status and provide `representation_id`, `features`, and independently authored `expected` fields. The validator rejects handwritten `covered` and `partial` statuses. Each expected field supplies a selector, value, absolute tolerance, applicable DXF versions, and DXF Reference citation.

Coverage is computed for each feature, format, version, and encoding. A drawing in a declared source folder plus a measured result for every declared writable pair with a source in the cell is covered. Missing measurements make it partial and are named. Capability gaps are listed as not possible and do not reduce coverage. The overall intent is covered only when every applicable cell is covered; otherwise it is partial.

The selectors resolve named tables, blocks, attributes, model-space usage counts, linetype definitions, layouts, viewport settings, dictionary objects, XDATA, XRECORDs, and groups. Table defaults specified by DXF are materialized when omitted. VIEW center is normalized to its two DCS coordinates. Simple linetype patterns normalize optional zero element flags. Complex patterns resolve the style handle to its style name. Numeric group-code values and named values are compared as meaning, rather than requiring a particular handle assignment.

The Autodesk DXF Reference sections are given for each field. The viewport color override dictionary mapping is not fully specified there. That field retains the authored expected color 6; independent compatibility evidence for that mapping remains unverified. An ezdxf read-back verifies the stored override, not independent conformance of that undocumented mapping.

All modern versions carry all six topics. R12 carries five topic subsets: it omits named layouts, page setups, plot flags and lineweights, viewport overrides, extension dictionaries, DICTIONARYVAR, groups, scale lists, and complex linetypes. It retains blocks and attributes, 100 layers and supported states, simple linetypes and styles, APPID/XDATA, named views, and UCS records. Applicability lists express these format limitations explicitly.

Each drawing carries identity as `ZEV_IDENTITY` XDATA on the model-space BLOCK: two code-1000 strings for intent and representation. The provenance record repeats both IDs, with writer program and exact build, format, version, encoding, creation script, input digest, content digest, and an ezdxf-based marker. DWG uses `binary` as its encoding; that does not imply binary DXF. Provenance records are named `<drawing>.provenance.json`.

Run from the repository root:

```sh
python intent/validate.py
```

Validation checks every intent JSON and every native/cross provenance record, rejects unknown keys and duplicate expected-field IDs, checks identity links and file existence, and requires a provenance record for every drawing. `checker/verify.py` additionally checks embedded identities, provenance record digests, every expected value, audits, and regeneration stability.

Feature selectors resolve entity type and feature layer, then compare an explicit DXF attribute or normalized points, polyline vertices, wipeout boundary, frozen layers, or embedded MTEXT presence. Layer inventory expectations describe source-declared feature layers. R12 is a supported-entity subset; modern objects and layouts are omitted. The native feature runner records audits and expected-field comparisons in `results/features_*.json`.

`feature_fields` maps each feature to its expected-field IDs. The validator checks every mapping and the map uses these associations to show feature-specific differences and version applicability. An unsupported version appears as not applicable, rather than implying the feature exists because the same file carries another feature.

The `identity` selector is checked for every file and is excluded from feature associations and map feature counts. `python intent/alignment_expectations.py` applies the independently authored Aligned and Fit policy. `python checker/recheck_alignment.py` rechecks those fields using existing DXFs and saved DWG measurements, without CAD saves. An optional `recomputed_width_relative_tolerance` accepts the measured two-point span divided by reader-font width for Fit text, within the declared relative tolerance.

## Semantic comparison

`actual` retains the extracted spelling, flags, and tag values. Comparison changes status only.
The shared name helper folds ASCII A to Z for the synthetic name alphabet; it makes no
locale-wide Unicode equivalence claim.

- Symbol names (layers, linetypes including ByLayer/ByBlock, styles, blocks, dimension
  styles, views, UCS, viewports and registered applications) compare without case.
  Feature and draw-order layer selection, Fit entity/font lookup, symbol-valued query
  operands, name prefixes and returned references use this rule. Symbol lookups take
  the first case-insensitive match. Query counts support entity type selection with
  layer equality, plus INSERT name equality and plain entity type lists, through
  the public ezdxf query API;
  unsupported forms fail loudly.
  [Autodesk Symbol Tables](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-DevGuide/files/GUID-83ABF20A-57D4-4AB3-8A49-D91E0F70DBFF.htm)
  supplies application semantics; the [R12 implementation guidance](https://ezdxf.readthedocs.io/en/stable/r12strict.html)
  corroborates uppercase legacy naming. Text, attribute values, descriptions and filenames retain case.
- Draw-order name lists retain order. Frozen-layer names compare as sets under the
  same name rule; duplicates are ignored, and empty and nonempty sets differ.
  A `redraw_order` row stores the full effective space order in `actual`; comparison
  filters it to the expected names. Set membership is an explicit
  dataset policy for frozen layers; the source establishes name comparison, not list ordering.
  [Autodesk Symbol Tables](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-DevGuide/files/GUID-83ABF20A-57D4-4AB3-8A49-D91E0F70DBFF.htm).
- Dictionary and extension-dictionary path segments compare without case; a matching
  case collision is an ambiguous lookup failure. Object values remain literal.
  [DBDictionary](https://help.autodesk.com/cloudhelp/2019/ENU/OARX-ManagedRefGuide/files/OREFNET-Autodesk_AutoCAD_DatabaseServices_DBDictionary.html)
  defines key comparison; [DICTIONARY group 3](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-40B92C63-26F0-485B-A9C2-B349099B26D0.htm)
  identifies entry names separately from values.
- XDATA application keys follow symbol-name comparison; payload strings and repeated
  tags retain case and order.
  [Autodesk Symbol Tables](https://help.autodesk.com/cloudhelp/2018/ENU/OARX-DevGuide/files/GUID-83ABF20A-57D4-4AB3-8A49-D91E0F70DBFF.htm),
  [Extended Data](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-A2A628B0-3699-4740-A215-C560E7242F63.htm).
- `F111_anonymous_block.name` follows the feature INSERT to a resolved block with
  a `*U` numeric name and BLOCK flag bit 1. The allocated number does not affect
  status. `F111_anonymous_block.block_circle_radius` uses a `feature_attr` selector
  on that INSERT with `attr: block_circle_radius`; the referenced block contains a
  CIRCLE of independently authored radius 3. Missing references or circles are absent;
  any circle may match, and radii differ only when none matches. The raw `actual`
  contains every circle radius. Named blocks retain their name identity.
  [Anonymous Blocks](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-AutoLISP/files/GUID-EB9BFDAA-487A-4586-A556-1F5F84BCF2F3.htm),
  [BLOCK flags](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-66D32572-005A-4E23-8B8B-8726E8C14302.htm),
  [Open Design Specification, section 20.4.52](https://static.opendesign.com/files/guestdownloads/OpenDesign_Specification_for_.dwg_files.pdf).
- Proxy payload comparison separates the first group-90 class ID in the proxy
  subclass from application data and requires envelope value 499 for ACAD_PROXY_OBJECT
  or 498 for ACAD_PROXY_ENTITY. A missing or wrong envelope is absent with an
  envelope diagnostic. Subsequent group-90
  and group-40 payload values remain significant; custom native objects retain all
  those values. Raw extracted tags include the envelope.
  [ACAD_PROXY_OBJECT](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-F59F0EC3-D34D-4C1A-91AC-7FDA569EF016.htm),
  [ACAD_PROXY_ENTITY](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-89A690F9-E859-4D57-89EA-750F3FB76C6B.htm).
- Layer flag comparisons mask only advisory bit 64. Freeze, new-viewport freeze,
  lock and external-reference bits remain significant.
  [LAYER flags](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-D94802B0-8BE8-4AC9-8054-17197688AFDB.htm).
- Linetype pattern scalar groups 72, 73 and 40 compare independently of tag order;
  repeated group-49 dash lengths retain order and numeric tolerance.
  [Object and Entity Codes](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-A35B8C2A-1885-4A8E-8533-E61D8A423D62.htm),
  [LTYPE](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-F57A316C-94A2-416C-8280-191E34B182AC.htm).

## Expectation basis and citations

Every expected field's `reference` requires `basis_type`, an exact owning item
`url`, and explanatory `basis` text. Generic help landing pages are rejected.
The four basis types classify the whole expected value:

- `synthetic`: an invented fixture value, for example a CIRCLE radius of 7.
- `normative`: the standard fixes the whole value, for example LTYPE alignment
  group 72 equal to 65 in a hypothetical standalone alignment expectation.
- `application_semantics`: published application behavior settles the expectation,
  with a named published source in the basis text. The current fields use no such classification.
- `compatibility_policy`: a dataset choice where no standard settles it, for
  example viewport color override 6 with its provisional dictionary mapping.

A mixed linetype pattern is synthetic even though group 72 is fixed at 65;
its basis names that fixed part. Name comparison behavior does not turn an
invented symbol name into a normative value. Proxy class envelope IDs are
normative when independently asserted; invented opaque payloads are synthetic.

The authoring scripts apply `references.py`; `python intent/traceability.py`
regenerates citations on existing intents without changing scoring inputs.
Owning pages come from `reference_pages.py`, transcribed from the standard
catalog. Custom classes without an item page explain the fallback in `basis`.
Each row's intent stamp hashes only the expected fields, with each `reference`
removed. Every other field key, including future comparison settings, is hashed;
titles, descriptions, citations and explanations do not invalidate scores.

Every expectation constructor call supplies its basis type explicitly. The
reference helper rejects a missing or invalid type and never infers one.
Validation requires the owning page selected by the field selector. The documented
exceptions are: extension-record fields cite XRECORD; draw-order fields cite
SORTENTSTABLE; nested block-circle fields cite CIRCLE; wildcard layer-usage counts
cite LAYER; multi-type counts cite the first queried type; viewport color policy
cites LAYER; extended data cites APPID; custom synthetic classes cite the proxy
entity envelope; and scale-list entries cite OBJECTS because the cataloged
Reference contents provide no SCALE item page. Each missing-page fallback explains
the limitation in its basis. These exceptions identify the storage or property the
selector reads, rather than an unrelated entity page.
