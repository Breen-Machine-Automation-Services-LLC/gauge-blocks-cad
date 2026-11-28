# Size and storage

Measured by `measure_size.py`; bytes include drawings and identity sidecars, and exclude measurement tables, code, and intent definitions.

| Set | Drawings | Drawing bytes | Sidecar bytes | Total bytes |
| --- | ---: | ---: | ---: | ---: |
| cross/bricscad__autocad | 40 | 4,244,555 | 21,062 | 4,265,617 |
| cross/bricscad__cadcraft | 24 | 2,026,773 | 12,348 | 2,039,121 |
| cross/bricscad__oda | 40 | 16,728,578 | 18,898 | 16,747,476 |
| cross/ezdxf__autocad | 447 | 39,826,757 | 237,415 | 40,064,172 |
| cross/ezdxf__bricscad | 449 | 248,594,577 | 225,598 | 248,820,175 |
| cross/ezdxf__cadcraft | 322 | 10,245,892 | 167,014 | 10,412,906 |
| cross/ezdxf__oda | 466 | 33,605,272 | 218,775 | 33,824,047 |
| cross/oda__bricscad | 449 | 249,212,901 | 224,950 | 249,437,851 |
| native/bricscad | 40 | 16,646,393 | 20,014 | 16,666,407 |
| native/ezdxf | 233 | 8,650,291 | 102,569 | 8,752,860 |

Measured total: **631,030,632 bytes** (601.80 MiB).

Mean drawing size by the program that wrote the file (sidecar program) and format:

| Writer | Format | Files | Mean bytes |
| --- | --- | ---: | ---: |
| autocad | DWG | 228 | 56,770 |
| autocad | DXF ASCII | 137 | 140,931 |
| autocad | DXF binary | 122 | 96,885 |
| bricscad | DWG | 444 | 425,071 |
| bricscad | DXF ASCII | 264 | 1,154,120 |
| bricscad | DXF binary | 230 | 91,454 |
| cadcraft | DWG | 226 | 22,445 |
| cadcraft | DXF ASCII | 120 | 59,999 |
| ezdxf | DXF ASCII | 125 | 38,028 |
| ezdxf | DXF binary | 108 | 36,080 |
| oda | DWG | 245 | 45,951 |
| oda | DXF ASCII | 139 | 201,581 |
| oda | DXF binary | 122 | 90,622 |

BricsCAD writes ASCII DXF files of about one megabyte even for a few entities, and DWG 2000 to 2010 of several hundred kilobytes (its default objects and preview), so the BricsCAD streams dominate the total.

For four programs, the design has four native streams and twelve ordered cross streams: sixteen streams total. Treating each of the thirteen drawn-content topics and six background topics as one intent gives nineteen intents before expanding justifications, block transforms, hatch islands, old and lightweight polylines, and multilingual encodings. Forty to eighty intents is a planning range for that expansion. The current six background intents supply the per-intent baseline. The estimate scales the measured ezdxf native set to four native streams and the measured ODA cross set to twelve cross streams. Other programs may have different formats, compression, and overhead, so this extrapolation is uncertain.

| Planned intents | Estimated bytes for four programs | MiB |
| ---: | ---: | ---: |
| 19 | 1,396,183,346 | 1331.50 |
| 40 | 2,939,333,360 | 2803.17 |
| 80 | 5,878,666,720 | 5606.33 |

These estimates assume all programs can build every intent and all ordered cross streams exist. They are capacity estimates, not measured output sizes. Tables, images, dense hatches, embedded previews, and conversion behavior can increase or decrease the average considerably. AutoCAD-only dynamic blocks and proxies remain placeholders, without fabricated byte estimates.

Every drawing, native and resaved, is stored in git.
