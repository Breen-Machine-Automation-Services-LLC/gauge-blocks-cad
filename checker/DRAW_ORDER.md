# Effective drawing order

`redraw_order` compares the relative order of the intent's named entities within their space. Sort all space entities numerically by the SORTENTSTABLE sort handle, falling back to their own handle when unlisted, then select the intent entities. Missing intent entities still fail the comparison. The literal table (entity/sort handle pairs) and full effective space order remain informational in row detail.

Reference: Autodesk DXF Reference, [OBJECTS / SORTENTSTABLE](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-462F4378-F850-4E89-90F2-3C1880F55779.htm), codes 331 and 5, describes ascending handle order with table overrides. Autodesk's [AcDbSortentsTable::sortAs](https://help.autodesk.com/cloudhelp/2024/ENU/OARX-RefGuide/files/OARX-RefGuide-AcDbSortentsTable__sortAs_AcDbObjectId_AcDbHandle__const.html) explicitly states the own-handle fallback for unlisted entities.

F130 expects d, c, b, a in model space; F131 expects c, b, a in I_SORTBLK. Equivalent partial and full tables pass alike. Recheck existing evidence with `python -m checker.recheck_draw_order --runs PATH`; this reads saved DXFs only, and records inaccessible DWG evidence without inferring it from another drawing or a literal list.
