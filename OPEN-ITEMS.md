# Open items

## Reproduce DWG 2007 container acceptance across readers

Investigate the reported case where DWG 2007 output opens in its writer but is refused by another reader. The 2007 container differs from other versions. This repository has no measured refusal row for that pair, so the report is an unverified reproduction request, not a defect attributed to a program. Add a minimal synthetic input, exact public builds, reader error, and per-version acceptance rows. Acceptance requires reproducing or closing the report with measured evidence.

## Compare Fit and Aligned text through DXF and DWG

Investigate the report that one reader interprets Fit and Aligned text differently in DXF and DWG. There is no measured row for that reader in this repository. Use the text intent with both alignment points, height, width factor, rotation, and horizontal and vertical justification. Record exact builds and both result rows before attributing a defect. Acceptance requires a format comparison with an independent DWG reader.

## Independently read ODA-written DWG

The DWG rows in `results/checks.json` identify ODA as converter and `self_read: true`. Add an independent DWG reader with an exact public build, preserve the self-read evidence, and compare both readers against the intents. Acceptance requires independent rows for every ODA-written DWG.

## Investigate measured ezdxf to ODA field changes

`results/checks.json` contains the measured evidence below. These are field observations, not proof that the writer is defective; DWG observations use ODA self-read. Preserve writer, reader, converter, build, format, and version when reproducing each row.

| Topic | Differing | Missing | Fields | Evidence row file |
| --- | ---: | ---: | --- | --- |
| background_blocks | 0 | 1 | Missing embedded identity in R12 DWG | `cross/ezdxf__oda/blocks_R12_ASCII.dwg` |
| background_layers | 100 | 49 | 100 linetype-name capitalization differences (Continuous versus CONTINUOUS); 24 missing viewport freeze and 24 missing viewport color fields; one missing R12 DWG identity | `cross/ezdxf__oda/layers_2000_ASCII.dxf` |
| background_metadata | 0 | 1 | Missing embedded identity in R12 DWG | `cross/ezdxf__oda/metadata_R12_ASCII.dwg` |
| background_named | 0 | 1 | Missing embedded identity in R12 DWG | `cross/ezdxf__oda/named_R12_ASCII.dwg` |
| background_styles | 0 | 1 | Missing embedded identity in R12 DWG | `cross/ezdxf__oda/styles_R12_ASCII.dwg` |

Representative measured rows in `results/checks.json`: `cross/ezdxf__oda/layers_R12_ASCII.dxf`, field `ZEV_000.linetype`, expected `Continuous`, actual `CONTINUOUS`; `cross/ezdxf__oda/layers_2000_ASCII.dxf`, fields `vp.freeze` and `vp.color`, actual absent; `cross/ezdxf__oda/blocks_R12_ASCII.dwg`, field `identity`, actual absent (ODA self-read).

Acceptance requires a minimized reproduction for each feature, an independent interpretation of the DXF Reference, and before/after measured rows. Total: 100 differing and 53 missing fields.

## AutoCAD dynamic blocks

Blocked on a program that can author dynamic blocks. AutoCAD LT is available as a re-saver but cannot author them; full AutoCAD is needed. See `intent/future_dynamic_blocks.json`. Author invented dynamic-block evaluation data and test preservation. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## AutoCAD AEC proxy objects

Blocked on an AEC authoring product. AutoCAD LT is available as a re-saver but cannot author AEC objects. See `intent/future_aec_proxy.json`. Author invented AEC objects and test class, payload, and proxy preservation. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## AutoCAD drawing-load acceptance

Observation: opening and re-saving ezdxf and BricsCAD inputs is measured in `results/cross_ezdxf__autocad_checks.json` and `results/cross_bricscad__autocad_checks.json`; refused inputs have field `open`, status `refused`, and a diagnostic in `detail`. Saved fields are compared with the intents by ezdxf, with ODA conversion for DWG. This does not independently establish the content present in the AutoCAD session. See `intent/future_acceptance.json`. Verify that a successful open actually loads the intended drawing content. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## BricsCAD and CADCraft measurements (phase 2b)

Each entry below is a measured observation with its evidence row in `results/`. None of them names a program defective: the DXF rows use ezdxf as the direct reader, the DWG rows name their converter, and an expected value comes from the intent. Reproduce with the exact builds in `programs/CAPABILITIES.md` (BricsCAD V26 26.2.07-1, CADCraft a70b9b02, ODA 27.1.0.143450, ezdxf 1.4.4).

## CADCraft DWG 2007 refused by both converters for one drawing

Observation: CADCraft wrote a DWG 2007 for `native/ezdxf/e_objects_2007_ASCII.dxf` that ODA File Converter produced no output for (refused rows `cross/ezdxf__cadcraft/e_objects_2007_ASCII.dwg` and `e_objects_2007_binary.dwg` in `results/cross_ezdxf__cadcraft_checks.json`, field `open`). BricsCAD also refused to open it (`results/dwg2007_second_reader.json`: BricsCAD `E_FAIL`, ODA no output); the 2004 and 2010 files from the same input read in both. The other 2007 files from CADCraft read. The refused drawing is not kept in the repository. This is one measured case of the DWG 2007 container report above, with the writer identified. Both readers use ODA libraries, so it is one engine's verdict. Acceptance: a third DWG reader's result for the same drawing, and the minimized entity that triggers it.

## Per-viewport layer settings after resaving

Observation: the direct DXF rows distinguish layer overrides from the viewport's frozen-layer list. All versions below refer to the measured versions in `results/cross_ezdxf__<program>_checks.json`.

| Re-saver | `vp.freeze` | `vp.color` | `F168_viewport_frozen.frozen_layers` |
| --- | --- | --- | --- |
| BricsCAD | Absent from 2000 through 2018 | Absent from 2000 through 2018 | Empty at 2000; matches from 2004 through 2018 |
| CADCraft | Empty at 2000; matches from 2004 through 2018 | Matches from 2000 through 2018 | Empty at 2000; matches from 2004 through 2018 |
| ODA | Absent from 2000 through 2018 | Absent from 2000 through 2018 | Empty at 2000; matches from 2004 through 2018 |
| AutoCAD LT | Empty at 2000; matches from 2004 through 2018 | Matches from 2000 through 2018 | Empty at 2000; matches from 2004 through 2018 |

Evidence: `layers_2000_ASCII.dxf` and `n_misc_2000_ASCII.dxf` under each `cross/ezdxf__<program>/` folder, compared with their later-version rows. ASCII and binary DXF agree wherever both are writable. AutoCAD DWG rows still show `vp.freeze` and `vp.color` absent through ODA conversion, even where direct DXF matches. Acceptance: a minimized input and an independent reading of how the DXF Reference stores each setting, with separate direct DXF and converted DWG evidence.

## AutoCAD refusal of R12 anonymous dimension blocks

Observation: AutoCAD refuses the dimensions and nested-blocks R12 ASCII DXF inputs with "Invalid anonymous block *D1" and "drawing discarded". Evidence: `results/cross_ezdxf__autocad_checks.json`, files `cross/ezdxf__autocad/d_dimensions_R12_ASCII.dxf` and `g_blocks_R12_ASCII.dxf`, field `open`, status `refused`, diagnostic in `detail`. Raw BLOCK records in `native/ezdxf/d_dimensions_R12_ASCII.dxf` name `*D1` through `*D6` and give each block group 70 a value of 0. This is a file observation, not a finding that the flags caused the refusal. Acceptance: minimize the input, establish the applicable block-flag rule, and measure AutoCAD acceptance with only that representation changed.

## AutoCAD object-drawing dictionary entries

Observation: entries selected by `F70_plain.description`, `F71_marker.description`, `F71_marker.acad_marker`, `F72_xrecord.tags`, and `F73_dictionaryvar.value` are absent at 2013 and 2018 in ASCII DXF, binary DXF, and DWG read through ODA. `F70_plain.end` still matches, so the rows do not show the whole drawing lost. At 2007 the descriptions are empty; at 2010 they match. Marker tags differ in direct DXF at 2007 and 2010 but match through the DWG conversion. Evidence: `results/cross_ezdxf__autocad_checks.json`, `cross/ezdxf__autocad/e_objects_2013_ASCII.dxf` and the corresponding version, encoding, and format rows. Acceptance: minimized dictionary entries with version-specific AutoCAD observations and an independent DWG read before attributing the DWG loss to its writer.

## ezdxf reads of AutoCAD ACIS data

Observation: ezdxf reports `reader_error` for regions and solids at DXF 2007 and 2010, and for solids at DXF 2013, in both ASCII and binary output. Evidence: `results/cross_bricscad__autocad_checks.json`, `cross/bricscad__autocad/k_regions_solids_2007_ASCII.dxf` and the corresponding rows, fields `F152_region.acis_body_count`, `F154_solid3d.acis_body_count`, and `F154_solid3d.acis_bbox_size`. The diagnostic is a parsing error in `detail`. This leaves preservation unknown to this reader. Acceptance: a minimized ACIS payload, an independent read, and a successful ezdxf read against the intent; keep reader failures distinct from measured loss.

## CADCraft: scale list entries and polyline widths

Observation: in the CADCraft resave, scale-list entries are absent from the DWG (`cross/ezdxf__cadcraft/named_2000_ASCII.dwg`, fields `scale.name`, `scale.paper_units`, `scale.drawing_units`, ODA reader only) and from the DXF of the misc drawing (`cross/ezdxf__cadcraft/n_misc_2000_ASCII.dxf`, fields `N_1_TO_37.name`, `.paper_units`, `.drawing_units`); the 2D polyline with widths and bulges has no readable vertices (`F160_polyline2d_width_bulge.vertices` absent, 18 rows in all, DXF and DWG). Redraw order of the sorted-entities dictionary is empty (`cross/ezdxf__cadcraft/i_dictionaries_2000_ASCII.dwg`, `F130_sortents_a.redraw_order`, 36 rows), hatch loop flags change (`b_geometry_2000_ASCII.dwg`, `F23_hatch_flags7_22.loop_flags` expected `[7, 22]`, actual `[3, 2]`), and the attribute text generation flag changes (`h_attributes_2000_ASCII.dwg`, `F120_attrib_textmirror.text_generation_flag` 2 to 0). The DWG rows rest on ODA as the only reader; a BricsCAD read of the same DWG would separate writer from reader.

## ezdxf reads of BricsCAD binary DXF ACIS data before 2013

Observation: the checker's ezdxf read of a BricsCAD-written binary DXF at 2000 to 2010 yields no ACIS body for the region and solid (`results/native_bricscad_checks.json`, `native/bricscad/k_regions_solids_2004_binary.dxf`, fields `F152_region.acis_body_count`, `F154_solid3d.acis_body_count`, `F154_solid3d.acis_bbox_size`, status `absent`, reader ezdxf direct). The same files converted to ASCII DXF by ODA and read by ezdxf give `same` for all three fields (rows with converter `oda ... (binary DXF to ASCII DXF)`), and the ASCII DXF from BricsCAD reads in ezdxf. The decoded ACIS header text of the binary file reads `Open Design Aliance AIS Builder` against `Open Design Alliance ACIS Builder` in the ASCII twin. Cause: ezdxf 1.4.4's decoder for encrypted SAT text (`ezdxf/tools/crypt.py`, `decode`) drops the character after each `^`; BricsCAD's binary writer does not add the padding character ezdxf expects.

## ODA conversion of the BricsCAD plain table

Observation: converting `native/bricscad/k_tables_2010_binary.dxf` (and 2013, 2018) from binary to ASCII DXF through ODA gives plain-table cell text `['A1', 'A2', 'B2', 'A3', 'B3']` against the expected six values (rows with converter `oda ... (binary DXF to ASCII DXF)`, field `F151_table_plain.table_cell_text`); the BricsCAD files read directly give all six. BricsCAD's own drawn block for that table also lacks B1, so ODA's result matches the drawn block rather than the cell data. Acceptance: confirm with a table authored where the title row is not merged.

## BricsCAD DXF R12

Observation: BricsCAD writes table, region and solid content as INSERT or POLYLINE at R12 (`results/native_bricscad_observations.json`), and upper-cases layer names (`cross/ezdxf__bricscad/a_text_R12_ASCII.dxf`, `F01_text_aligned.layer` expected `F01_text_aligned`, actual `F01_TEXT_ALIGNED`; 134 layer rows in all); the fields looked up by layer name are then absent in R12 rows. Whether upper case is required of R12 names is a Reference question, not settled here.

## Table drawing digest reproducibility at DWG 2004 and 2007

Observation: two runs of the BricsCAD table generator give different content digests for the DWG 2004 or the DWG 2007 read-back (varies by run); DWG 2018 and the DXF files match. Evidence: `results/bricscad_generator_rerun_evidence.json` (`k_tables:k_tables_2004_binary.dwg`) and `results/bricscad_regeneration_stability.json`. See `checker/VOLATILE.md`, known exception.

Compared fields for the unresolved table digest: `results/bricscad_generator_rerun_evidence.json`, `k_tables:k_tables_2004_binary.dwg`, handle `38C`, two group-330 pointers swap from `95, AC` to `AC, 95`; both entities have 12 tags. Header changes are already excluded volatile fields. The evidence does not establish whether pointer order is meaningful, so no additional digest exclusion is applied.

The ODA resaves of the BricsCAD table drawing vary the same way. Two ODA runs from unchanged inputs gave different content digests for 9 of the 20 `cross/bricscad__oda/k_tables_*` outputs (DWG 2000, 2004, 2007, 2010, 2013 and 2018; DXF 2004 binary, 2010 ASCII and 2018 ASCII), while every field check stayed the same and none of the 20 `k_regions_solids_*` outputs changed.

