## BricsCAD and CADCraft measurements (phase 2b)

Each entry below is a measured observation with its evidence row in `results/`. None of them names a program defective: the DXF rows use ezdxf as the direct reader, the DWG rows name their converter, and an expected value comes from the intent. Reproduce with the exact builds in `programs/CAPABILITIES.md` (BricsCAD V26 26.2.07-1, CADCraft a70b9b02, ODA 27.1.0.143450, ezdxf 1.4.4).

## CADCraft DWG 2007 refused by both converters for one drawing

Observation: CADCraft wrote a DWG 2007 for `native/ezdxf/e_objects_2007_ASCII.dxf` that ODA File Converter produced no output for (refused rows `cross/ezdxf__cadcraft/e_objects_2007_ASCII.dwg` and `e_objects_2007_binary.dwg` in `results/cross_ezdxf__cadcraft_checks.json`, field `open`). BricsCAD also refused to open it (`results/dwg2007_second_reader.json`: BricsCAD `E_FAIL`, ODA no output); the 2004 and 2010 files from the same input read in both. The other 2007 files from CADCraft read. The refused drawing is not kept in the repository. This is one measured case of the DWG 2007 container report above, with the writer identified. Both readers use ODA libraries, so it is one engine's verdict. Acceptance: a third DWG reader's result for the same drawing, and the minimized entity that triggers it.

## Per-viewport layer settings after BricsCAD and CADCraft resaves

Observation: per-viewport frozen layers and per-viewport layer color overrides are absent after the BricsCAD resave of the layers drawing (`cross/ezdxf__bricscad/layers_2000_ASCII.dxf` and `.dwg`, fields `vp.freeze` and `vp.color`, 12 rows each for DXF and DWG, from the 2000 version on) and the frozen layers of the viewport in the misc drawing differ (`cross/ezdxf__bricscad/n_misc_2000_ASCII.dxf` field `F168_viewport_frozen.frozen_layers`, expected `['F163_point']`, actual `[]`). CADCraft shows the same shape: `cross/ezdxf__cadcraft/layers_2000_ASCII.dxf` `vp.freeze` actual `[]`, and `n_misc_2000_ASCII.dxf` `frozen_layers` actual `[]`. ODA's resave also lacks the viewport fields (see the ezdxf to ODA entry above). Acceptance: whether the DXF Reference stores these in the layer extension dictionary or in the viewport, and an AutoCAD row.

## CADCraft: scale list entries and polyline widths

Observation: in the CADCraft resave, scale-list entries are absent from the DWG (`cross/ezdxf__cadcraft/named_2000_ASCII.dwg`, fields `scale.name`, `scale.paper_units`, `scale.drawing_units`, ODA reader only) and from the DXF of the misc drawing (`cross/ezdxf__cadcraft/n_misc_2000_ASCII.dxf`, fields `N_1_TO_37.name`, `.paper_units`, `.drawing_units`); the 2D polyline with widths and bulges has no readable vertices (`F160_polyline2d_width_bulge.vertices` absent, 18 rows in all, DXF and DWG). Redraw order of the sorted-entities dictionary is empty (`cross/ezdxf__cadcraft/i_dictionaries_2000_ASCII.dwg`, `F130_sortents_a.redraw_order`, 36 rows), hatch loop flags change (`b_geometry_2000_ASCII.dwg`, `F23_hatch_flags7_22.loop_flags` expected `[7, 22]`, actual `[3, 2]`), and the attribute text generation flag changes (`h_attributes_2000_ASCII.dwg`, `F120_attrib_textmirror.text_generation_flag` 2 to 0). The DWG rows rest on ODA as the only reader; a BricsCAD read of the same DWG would separate writer from reader.

## ezdxf reads of BricsCAD binary DXF ACIS data before 2013

Observation: the checker's ezdxf read of a BricsCAD-written binary DXF at 2000 to 2010 yields no ACIS body for the region and solid (`results/native_bricscad_checks.json`, `native/bricscad/k_regions_solids_2004_binary.dxf`, fields `F152_region.acis_body_count`, `F154_solid3d.acis_body_count`, `F154_solid3d.acis_bbox_size`, status `absent`, reader ezdxf direct). The same files converted to ASCII DXF by ODA and read by ezdxf give `same` for all three fields (rows with converter `oda ... (binary DXF to ASCII DXF)`), and the ASCII DXF from BricsCAD reads in ezdxf. The decoded ACIS header text of the binary file reads `Open Design Aliance AIS Builder` against `Open Design Alliance ACIS Builder` in the ASCII twin. Cause not established: the writer's string encoding in binary DXF or the reader's decoding of the caret escape. Test: compare the raw group 1 strings of both encodings against the Reference's caret notation.

## ODA conversion of the BricsCAD plain table

Observation: converting `native/bricscad/k_tables_2010_binary.dxf` (and 2013, 2018) from binary to ASCII DXF through ODA gives plain-table cell text `['A1', 'A2', 'B2', 'A3', 'B3']` against the expected six values (rows with converter `oda ... (binary DXF to ASCII DXF)`, field `F151_table_plain.table_cell_text`); the BricsCAD files read directly give all six. BricsCAD's own drawn block for that table also lacks B1, so ODA's result matches the drawn block rather than the cell data. Acceptance: confirm with a table authored where the title row is not merged.

## BricsCAD DXF R12

Observation: BricsCAD writes table, region and solid content as INSERT or POLYLINE at R12 (`results/native_bricscad_observations.json`), and upper-cases layer names (`cross/ezdxf__bricscad/a_text_R12_ASCII.dxf`, `F01_text_aligned.layer` expected `F01_text_aligned`, actual `F01_TEXT_ALIGNED`; 134 layer rows in all); the fields looked up by layer name are then absent in R12 rows. Whether upper case is required of R12 names is a Reference question, not settled here.

## Table drawing digest reproducibility at DWG 2004 and 2007

Observation: two runs of the BricsCAD table generator give different content digests for the DWG 2004 or the DWG 2007 read-back (varies by run); DWG 2018 and the DXF files match. Evidence: `results/bricscad_generator_rerun_evidence.json` (`k_tables:k_tables_2004_binary.dwg`) and `results/bricscad_regeneration_stability.json`. See `checker/VOLATILE.md`, known exception.

Compared fields for the unresolved table digest: `results/bricscad_generator_rerun_evidence.json`, `k_tables:k_tables_2004_binary.dwg`, handle `38C`, two group-330 pointers swap from `95, AC` to `AC, 95`; both entities have 12 tags. Header changes are already excluded volatile fields. The evidence does not establish whether pointer order is meaningful, so no additional digest exclusion is applied.
