from pathlib import Path
ASSETS=Path(__file__).resolve().parents[1]/"native/ezdxf"
import warnings, logging
from pathlib import Path
import math
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
from ezdxf.lldxf.types import DXFTag
from ezdxf.entities import MText
JUST = ['LEFT', 'CENTER', 'RIGHT', 'ALIGNED', 'MIDDLE', 'FIT', 'BOTTOM_LEFT', 'BOTTOM_CENTER', 'BOTTOM_RIGHT', 'MIDDLE_LEFT', 'MIDDLE_CENTER', 'MIDDLE_RIGHT', 'TOP_LEFT', 'TOP_CENTER', 'TOP_RIGHT']

def new(ver='R2018'):
    d = ezdxf.new(ver, setup=True)
    return d

def lay(d, name, color=7):
    if name not in d.layers:
        d.layers.add(name, color=color)
    return name

def master_a():
    d = new()
    msp = d.modelspace()
    d.styles.add('F07STYLE', font='', dxfattribs={'width': 0.8, 'oblique': 15})
    for i, j in enumerate(JUST):
        ln = lay(d, f'F01_text_{j.lower()}', 1 + i % 7)
        y = -12 * i
        t = msp.add_text(f'Just {j.title()}', height=2.5, dxfattribs={'layer': ln, 'style': 'Standard'})
        if j in ('ALIGNED', 'FIT'):
            t.set_placement((0, y), (30, y + (4 if j == 'ALIGNED' else 0)), align=getattr(TA, j))
            t.dxf.rotation = math.degrees(math.atan2(t.dxf.align_point.y-t.dxf.insert.y, t.dxf.align_point.x-t.dxf.insert.x))
        else:
            t.set_placement((10, y), align=getattr(TA, j))
    blk = d.blocks.new('F02_ATTBLK')
    for i, j in enumerate(JUST):
        ln = lay(d, f'F03_attdef_{j.lower()}', 1 + i % 7)
        y = -12 * i
        ad = blk.add_attdef(f'T_{j}', (10, y), f'def {j.title()}', height=2.5, dxfattribs={'layer': ln})
        ad.dxf.prompt = f'Prompt {j}'
        ad.dxf.field_length = 0
        if j in ('ALIGNED', 'FIT'):
            ad.set_placement((10, y), (40, y + (4 if j == 'ALIGNED' else 0)), align=getattr(TA, j))
            ad.dxf.rotation = math.degrees(math.atan2(ad.dxf.align_point.y-ad.dxf.insert.y, ad.dxf.align_point.x-ad.dxf.insert.x))
        else:
            ad.set_placement((10, y), align=getattr(TA, j))
    lay(d, 'F04_attdef_multiline')
    ml = blk.add_attdef('T_MULTI', (60, 0), 'line one\\Pline two', height=2.5, dxfattribs={'layer': 'F04_attdef_multiline'})
    ml.dxf.field_length = 0
    mt = MText.new(dxfattribs={'insert': (60, 0), 'char_height': 2.5, 'attachment_point': 1})
    mt.text = 'line one\\Pline two'
    ml.embed_mtext(mt)
    ml.dxf.layer = 'F04_attdef_multiline'
    lay(d, 'F02_insert')
    ins = msp.add_blockref('F02_ATTBLK', (100, 0), dxfattribs={'layer': 'F02_insert'})
    vals = {f'T_{j}': f'val {j.title()}' for j in JUST}
    vals['T_MULTI'] = 'alpha\\Pbeta'
    ins.add_auto_attribs(vals)
    for a in ins.attribs:
        a.dxf.field_length = 0
        if a.dxf.tag == 'T_MULTI':
            mt2 = MText.new(dxfattribs={'insert': (60 + 100, 0), 'char_height': 2.5, 'attachment_point': 1})
            mt2.text = 'alpha\\Pbeta'
            a.embed_mtext(mt2)
    for a in ins.attribs:
        tag = a.dxf.tag
        if tag == 'T_MULTI':
            a.dxf.layer = 'F04_attrib_multiline'
            lay(d, 'F04_attrib_multiline')
        else:
            nm = tag[2:].lower()
            a.dxf.layer = f'F05_attrib_{nm}'
            lay(d, a.dxf.layer)
    mtexts = [('F10_mtext_tl_width', 1, 40, 'Plain \\H1.5x;big\\H1x; then {\\C1;red run} and font run\\Pnew para'), ('F11_mtext_mc_nowidth', 5, 0, 'Mid center {\\C3;green} \\S1/2; stack \\Pline two'), ('F12_mtext_tl_nowidth', 1, 0, 'Top left no width \\Pline two ital'), ('F13_mtext_mc_width', 5, 35, 'Mid center with width \\H2x;tall\\H1x; \\S1#2; \\Pnext line that wraps around the reference width')]
    for k, (ln, ap, w, s) in enumerate(mtexts):
        lay(d, ln)
        m = msp.add_mtext(s, dxfattribs={'layer': ln, 'char_height': 2.5, 'attachment_point': ap, 'insert': (200, -20 * k)})
        if w:
            m.dxf.width = w
    lay(d, 'F14_text_rotated')
    t = msp.add_text('Rotated 33', height=2.5, dxfattribs={'layer': 'F14_text_rotated', 'rotation': 33})
    t.set_placement((250, 0), align=TA.MIDDLE_CENTER)
    lay(d, 'F07_style_widthobl')
    t = msp.add_text('Wide oblique', height=2.5, dxfattribs={'layer': 'F07_style_widthobl', 'style': 'F07STYLE'})
    t.set_placement((250, -20), align=TA.LEFT)
    return d

def master_b():
    d = new()
    msp = d.modelspace()
    sq = lambda x, y, s: [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
    for st in (0, 1, 2):
        ln = lay(d, f'F20_hatch_solid_style{st}', 1 + st)
        h = msp.add_hatch(color=1 + st, dxfattribs={'layer': ln, 'hatch_style': st})
        x0 = 30 * st
        h.paths.add_polyline_path(sq(x0, 0, 20), is_closed=True, flags=1 | 2)
        h.paths.add_polyline_path(sq(x0 + 4, 4, 12), is_closed=True, flags=0 | 2)
        h.paths.add_polyline_path(sq(x0 + 8, 8, 4), is_closed=True, flags=0 | 2)
    ln = lay(d, 'F23_hatch_flags7_22', 5)
    h = msp.add_hatch(color=5, dxfattribs={'layer': ln, 'hatch_style': 0})
    h.dxf.pixel_size = 0.0
    h.paths.add_polyline_path(sq(100, 0, 20), is_closed=True, flags=7)
    h.paths.add_polyline_path(sq(104, 4, 12), is_closed=True, flags=22)
    ln = lay(d, 'F24_hatch_pattern', 6)
    h = msp.add_hatch(color=6, dxfattribs={'layer': ln})
    h.set_pattern_fill('ANSI31', scale=0.5, angle=15)
    h.paths.add_polyline_path(sq(130, 0, 20), is_closed=True)
    ln = lay(d, 'F25_hatch_gradient', 3)
    h = msp.add_hatch(color=3, dxfattribs={'layer': ln})
    h.set_gradient((255, 0, 0), (0, 0, 255), rotation=30)
    h.paths.add_polyline_path(sq(160, 0, 20), is_closed=True)
    ln = lay(d, 'F30_lwpoly_bulge_width', 2)
    msp.add_lwpolyline([(0, 40, 0.5, 1.0, 0.8), (20, 40, 1.5, 0.2, -0.6), (40, 55, 0, 0, 0), (60, 40, 0.3, 0.3, 0)], format='xyseb', dxfattribs={'layer': ln})
    ln = lay(d, 'F31_arc')
    msp.add_arc((80, 45), 8, 20, 250, dxfattribs={'layer': ln})
    ln = lay(d, 'F32_circle')
    msp.add_circle((105, 45), 7, dxfattribs={'layer': ln})
    ln = lay(d, 'F33_ellipse')
    msp.add_ellipse((135, 45), major_axis=(12, 4, 0), ratio=0.5, start_param=0, end_param=5.0, dxfattribs={'layer': ln})
    ln = lay(d, 'F34_spline')
    msp.add_spline(fit_points=[(160, 40), (170, 55), (180, 38), (190, 52)], dxfattribs={'layer': ln})
    d.linetypes.add('F35CUSTOM', pattern=[8.0, 4.0, -2.0, 0.0, -2.0], description='custom dash dot')
    ln = lay(d, 'F35_linetype_custom')
    msp.add_line((0, 70), (80, 70), dxfattribs={'layer': ln, 'linetype': 'F35CUSTOM'})
    ln = lay(d, 'F36_linetype_dashed_ltscale')
    msp.add_line((0, 76), (80, 76), dxfattribs={'layer': ln, 'linetype': 'DASHED', 'ltscale': 2.5})
    return d

def master_b2():
    """B without the gradient hatch: BricsCAD cannot save a gradient hatch to DXF 2000 or R12 (probe/var), so this
    master supplies the rest of B at those versions."""
    d = master_b()
    msp = d.modelspace()
    for e in list(msp):
        if e.dxf.layer == 'F25_hatch_gradient':
            msp.delete_entity(e)
    return d

def master_c():
    d = new()
    msp = d.modelspace()
    lay(d, 'F40_model_marker')
    msp.add_circle((50, 50), 20, dxfattribs={'layer': 'F40_model_marker'})
    ml = d.layouts.get('Model').dxf_layout
    ml.dxf.paper_width = 279.4
    ml.dxf.paper_height = 215.9
    ml.dxf.plot_paper_units = 1
    ml.dxf.plot_rotation = 1
    ml.dxf.plot_type = 5
    ml.dxf.plot_layout_flags = 688
    ml.dxf.current_style_sheet = 'ZEV_MONO.ctb'
    ml.dxf.paper_size = 'ZEV_PAPER'
    ml.dxf.plot_origin_x_offset = 6.0
    ml.dxf.plot_origin_y_offset = 7.0
    ml.dxf.scale_numerator = 1.0
    ml.dxf.scale_denominator = 2.0
    ml.dxf.left_margin = 6.35
    ml.dxf.bottom_margin = 6.35
    ml.dxf.right_margin = 6.35
    ml.dxf.top_margin = 6.35
    specs = [('F41_LayoutA', 'Layout A', dict(size=(420, 297), margins=(10, 12, 14, 16), rotation=0, scale=(1, 2)), 4, 'ZEV_MONO.ctb'), ('F42_LayoutB', 'Layout B', dict(size=(279.4, 431.8), margins=(5, 5, 5, 5), rotation=1, scale=(1, 1)), 1, 'ZEV_COLOR.ctb')]
    for ln, name, ps, ptype, ctb in specs:
        lay(d, ln)
        lo = d.layouts.new(name)
        lo.page_setup(size=ps['size'], margins=ps['margins'], units='mm', offset=(3.5, 4.5), rotation=ps['rotation'], scale=ps['scale'], name=f"PS_{name.replace(' ', '_')}", device='ZEV_DEVICE.pc3')
        lo.set_plot_type(ptype)
        if ptype == 4:
            lo.set_plot_window((10, 20), (300, 220))
        lo.set_plot_style(ctb)
        lo.add_viewport(center=(100, 100), size=(150, 100), view_center_point=(50, 50), view_height=60, dxfattribs={'layer': ln})
        lo.add_text(f'label {name}', dxfattribs={'layer': ln, 'height': 5, 'insert': (20, 20)})
    return d

def master_d():
    d = new()
    msp = d.modelspace()
    for n in ('F50_dim_linear', 'F51_dim_aligned', 'F52_dim_angular', 'F53_dim_radial', 'F54_dim_override_text', 'F55_dim_dimstyle_xdata'):
        lay(d, n)
    msp.add_linear_dim(base=(0, 10), p1=(0, 0), p2=(40, 0), dimstyle='EZDXF', dxfattribs={'layer': 'F50_dim_linear'}).render()
    msp.add_aligned_dim(p1=(0, 30), p2=(30, 50), distance=5, dimstyle='EZDXF', dxfattribs={'layer': 'F51_dim_aligned'}).render()
    msp.add_angular_dim_2l(base=(110, 20), line1=((60, 0), (100, 0)), line2=((60, 0), (90, 30)), dimstyle='EZDXF', dxfattribs={'layer': 'F52_dim_angular'}).render()
    c = msp.add_circle((140, 20), 10, dxfattribs={'layer': 'F53_dim_radial'})
    msp.add_radius_dim(center=(140, 20), radius=10, angle=40, dimstyle='EZDXF', dxfattribs={'layer': 'F53_dim_radial'}).render()
    msp.add_linear_dim(base=(0, -15), p1=(0, -5), p2=(40, -5), text='OVR <> mm', dimstyle='EZDXF', dxfattribs={'layer': 'F54_dim_override_text'}).render()
    msp.add_linear_dim(base=(60, -15), p1=(60, -5), p2=(100, -5), dimstyle='EZDXF', override={'dimtxt': 1.5, 'dimclrt': 1, 'dimdec': 3}, dxfattribs={'layer': 'F55_dim_dimstyle_xdata'}).render()
    return d
