"""Invented opaque proxy classes ported from master L."""
from pathlib import Path
import tempfile
import ezdxf
def master_l():
 with tempfile.TemporaryDirectory() as tmp:
  d = ezdxf.new("R2018", setup=True)
  for n in ("F180_proxy_entity", "F181_proxy_entity_b", "F182_proxy_object_marker"):
      d.layers.add(n)
  d.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "F182_proxy_object_marker"})
  d.modelspace().add_circle((20, 0), 2, dxfattribs={"layer": "F180_proxy_entity"})   # neighbour so the layer is not empty if the proxy is dropped
  p = Path(tmp) / "proxy.dxf"
  d.saveas(p)
  txt = p.read_text().split("\n")
  # pairs (code, value) lines
  def find(code, val, start=0):
      for i in range(start, len(txt) - 1, 2):
          if txt[i].strip() == code and txt[i + 1].strip() == val:
              return i
      raise SystemExit(f"{code} {val} not found")
  cls = [("0", "CLASS"), ("1", "SYNTH_WIDGET"), ("2", "AcDbSynthWidget"), ("3", "SynthApp"), ("90", "0"), ("91", "1"), ("280", "0"), ("281", "1"),
         ("0", "CLASS"), ("1", "SYNTH_GADGET"), ("2", "AcDbSynthGadget"), ("3", "SynthApp"), ("90", "0"), ("91", "1"), ("280", "0"), ("281", "1"),
         ("0", "CLASS"), ("1", "SYNTH_OBJ"), ("2", "AcDbSynthObj"), ("3", "SynthApp"), ("90", "0"), ("91", "1"), ("280", "0"), ("281", "0")]
  i = find("2", "CLASSES")
  # insert after the section name pair
  ins = []
  for c, v in cls:
      ins += [c if len(c) >= 3 else f"{int(c):>3}", v]
  txt[i + 2:i + 2] = ins
  # entities: find ENTITIES section end
  j = find("2", "ENTITIES")
  k = find("0", "ENDSEC", j)
  ents = []
  for h, name, layer, cl in (("7F00", "SYNTH_WIDGET", "F180_proxy_entity", "AcDbSynthWidget"), ("7F01", "SYNTH_GADGET", "F181_proxy_entity_b", "AcDbSynthGadget")):
      ents += ["  0", name, "  5", h, "330", d.modelspace().block_record_handle, "100", "AcDbEntity", "  8", layer, "100", cl, " 90", "7", " 40", "2.5", " 10", "40.0", " 20", "0.0", " 30", "0.0"]
  txt[k:k] = ents
  # object: in OBJECTS section, a dictionary under root dictionary; need root dict handle
  o = find("2", "OBJECTS")
  root_h = txt[o + 5]   # first object after the section name is the root DICTIONARY: 0 DICTIONARY / 5 handle
  assert txt[o + 3].strip() == "DICTIONARY", txt[o:o + 8]
  obj_end = find("0", "ENDSEC", o)
  objs = ["  0", "SYNTH_OBJ", "  5", "7F10", "330", root_h, "100", "AcDbSynthObj", " 90", "3", " 40", "1.25"]
  txt[obj_end:obj_end] = objs
  # register in the root dictionary: add 3 / 350 pair before first 100 AcDbDictionary? simply after the existing entries (before ENDSEC of root = next 0)
  r_end = find("0", "", o + 6) if False else None
  # root dictionary ends at the next '  0' pair after o+4
  n = o + 4
  while not (txt[n].strip() == "0"):
      n += 2
  txt[n:n] = ["  3", "SYNTH_OBJ_REF", "350", "7F10"]
  p.write_text("\n".join(txt))
  return ezdxf.readfile(p)
