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

Blocked on AutoCAD availability. See `intent/future_dynamic_blocks.json`. Author invented dynamic-block evaluation data and test preservation. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## AutoCAD AEC proxy objects

Blocked on AutoCAD availability. See `intent/future_aec_proxy.json`. Author invented AEC objects and test class, payload, and proxy preservation. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## AutoCAD drawing-load acceptance

Blocked on AutoCAD availability. See `intent/future_acceptance.json`. Verify that a successful open actually loads the intended drawing content. Record exact public builds and measured evidence. Acceptance requires a native input, sidecar, reader-named results, and populated map cells.

## BricsCAD and CADCraft measurements (phase 2b)

Each entry below is a measured observation with its evidence row in `results/`. None of them names a program defective: the DXF rows use ezdxf as the direct reader, the DWG rows name their converter, and an expected value comes from the intent. Reproduce with the exact builds in `programs/CAPABILITIES.md` (BricsCAD V26 26.2.07-1, CADCraft a70b9b02, ODA 27.1.0.143450, ezdxf 1.4.4).

## CADCraft DWG 2007 refused by both converters for one drawing

Observation: CADCraft wrote a DWG 2007 for `native/ezdxf/e_objects_2007_ASCII.dxf` that ODA File Converter produced no output for (refused rows `cross/ezdxf__cadcraft/e_objects_2007_ASCII.dwg` and `e_objects_2007_binary.dwg` in `results/cross_ezdxf__cadcraft_checks.json`, field `open`). BricsCAD also refused to open it (`results/dwg2007_second_reader.json`: BricsCAD `E_FAIL`, ODA no output); the 2004 and 2010 files from the same input read in both. The other 2007 files from CADCraft read. The refused drawing is not kept in the repository. This is one measured case of the DWG 2007 container report above, with the writer identified. Both readers use ODA libraries, so it is one engine's verdict. Acceptance: a third DWG reader's result for the same drawing, and the minimized entity that triggers it.

## Per-viewport layer settings after BricsCAD and CADCraft resaves

Observation: per-viewport frozen layers and per-viewport layer color overrides are absent after the BricsCAD resave of the layers drawing (`cross/ezdxf__bricscad/layers_2000_ASCII.dxf` and `.dwg`, fields `vp.freeze` and `vp.color`, 12 rows each for DXF and DWG, from the 2000 version on) and the frozen layers of the viewport in the misc drawing differ (`cross/ezdxf__bricscad/n_misc_2000_ASCII.dxf` field `F168_viewport_frozen.frozen_layers`, expected `['F163_point']`, actual `[]`). CADCraft shows the same shape: `cross/ezdxf__cadcraft/layers_2000_ASCII.dxf` `vp.freeze` actual `[]`, and `n_misc_2000_ASCII.dxf` `frozen_layers` actual `[]`. ODA's resave also lacks the viewport fields (see the ezdxf to ODA entry above). Acceptance: whether the DXF Reference stores these in the layer extension dictionary or in the viewport, and an AutoCAD row.

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
