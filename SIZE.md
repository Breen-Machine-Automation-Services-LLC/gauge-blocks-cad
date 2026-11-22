# Size and storage

Measured by `measure_size.py`; bytes include drawings and identity sidecars, and exclude measurement tables, code, and intent definitions.

| Set | Drawings | Drawing bytes | Sidecar bytes | Total bytes |
| --- | ---: | ---: | ---: | ---: |
| cross/bricscad__cadcraft | 24 | 2,026,773 | 12,348 | 2,039,121 |
| cross/bricscad__oda | 40 | 16,728,516 | 19,138 | 16,747,654 |
| cross/ezdxf__bricscad | 449 | 248,594,427 | 225,814 | 248,820,241 |
| cross/ezdxf__cadcraft | 322 | 10,245,248 | 167,230 | 10,412,478 |
| cross/ezdxf__oda | 154 | 9,908,014 | 68,327 | 9,976,341 |
| cross/oda__bricscad | 149 | 81,926,903 | 74,936 | 82,001,839 |
| native/bricscad | 40 | 16,646,393 | 20,014 | 16,666,407 |
| native/ezdxf | 233 | 8,649,513 | 102,569 | 8,752,082 |

Measured total: **395,416,163 bytes** (377.10 MiB).

Mean drawing size by the program that wrote the file (sidecar program) and format:

| Writer | Format | Files | Mean bytes |
| --- | --- | ---: | ---: |
| bricscad | DWG | 300 | 422,402 |
| bricscad | DXF ASCII | 180 | 1,146,945 |
| bricscad | DXF binary | 158 | 88,587 |
| cadcraft | DWG | 226 | 22,444 |
| cadcraft | DXF ASCII | 120 | 59,995 |
| ezdxf | DXF ASCII | 125 | 38,024 |
| ezdxf | DXF binary | 108 | 36,078 |
| oda | DWG | 89 | 66,300 |
| oda | DXF ASCII | 55 | 303,076 |
| oda | DXF binary | 50 | 81,330 |

BricsCAD writes ASCII DXF files of about one megabyte even for a few entities, and DWG 2000 to 2010 of several hundred kilobytes (its default objects and preview), so the BricsCAD streams dominate the total.

For four programs, the design has four native streams and twelve ordered cross streams: sixteen streams total. Treating each of the thirteen drawn-content topics and six background topics as one intent gives nineteen intents before expanding justifications, block transforms, hatch islands, old and lightweight polylines, and multilingual encodings. Forty to eighty intents is a planning range for that expansion. The current six background intents supply the per-intent baseline. The estimate scales the measured ezdxf native set to four native streams and the measured ODA cross set to twelve cross streams. Other programs may have different formats, compression, and overhead, so this extrapolation is uncertain.

| Planned intents | Estimated bytes for four programs | MiB |
| ---: | ---: | ---: |
| 19 | 489,960,663 | 467.26 |
| 40 | 1,031,496,133 | 983.71 |
| 80 | 2,062,992,267 | 1967.42 |

These estimates assume all programs can build every intent and all ordered cross streams exist. They are capacity estimates, not measured output sizes. Tables, images, dense hatches, embedded previews, and conversion behavior can increase or decrease the average considerably. AutoCAD-only dynamic blocks and proxies remain placeholders, without fabricated byte estimates.

Recommendation: publish the expanded drawing sets as versioned release archives, with source, schemas, intents, and compact results in plain git. The measured sample is small enough for plain git. Git LFS is an alternative if direct checkout of all expanded binaries is essential, but adds client and hosting requirements for public consumers. Re-measure the expanded set before choosing final release storage. Regeneration preserves drawing and sidecar bytes and mtimes when the content digest and writer build are unchanged; it never commits anything.
