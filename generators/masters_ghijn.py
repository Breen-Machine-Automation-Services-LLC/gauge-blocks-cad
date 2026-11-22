from pathlib import Path
ASSETS=Path(__file__).resolve().parents[1]/"native/ezdxf"
import warnings, logging, struct, zlib
from pathlib import Path
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
from ezdxf.entities import MText

def new():
    return ezdxf.new('R2018', setup=True)

def lay(d, name, color=7):
    if name not in d.layers:
        d.layers.add(name, color=color)
    return name

def asym(blk, layer):
    """L-shaped asymmetric outline so rotation, mirroring and scale are visible."""
    blk.add_lwpolyline([(0, 0), (6, 0), (6, 2), (2, 2), (2, 8), (0, 8)], close=True, dxfattribs={'layer': layer})

def master_g():
    d = new()
    msp = d.modelspace()
    lay(d, 'F100_block_basepoint')
    b = d.blocks.new('G_BASEOFF', base_point=(5, 5))
    b.add_circle((5, 5), 3, dxfattribs={'layer': 'F100_block_basepoint'})
    b.add_line((0, 0), (10, 10), dxfattribs={'layer': 'F100_block_basepoint'})
    msp.add_blockref('G_BASEOFF', (0, 0), dxfattribs={'layer': 'F100_block_basepoint'})
    for n in ('F101_nested_inner', 'F101_nested_outer'):
        lay(d, n)
    inner = d.blocks.new('G_INNER')
    inner.add_line((0, 0), (4, 0), dxfattribs={'layer': 'F101_nested_inner'})
    inner.add_circle((4, 0), 1, dxfattribs={'layer': 'F101_nested_inner'})
    outer = d.blocks.new('G_OUTER')
    outer.add_line((0, 0), (0, 6), dxfattribs={'layer': 'F101_nested_outer'})
    outer.add_blockref('G_INNER', (3, 1), dxfattribs={'layer': 'F101_nested_outer', 'rotation': 45, 'xscale': 1.5, 'yscale': 1.5})
    msp.add_blockref('G_OUTER', (30, 0), dxfattribs={'layer': 'F101_nested_outer'})
    for n in ('F102_insert_rotated', 'F103_insert_mirrored', 'F104_insert_nonuniform', 'F105_insert_minsert'):
        lay(d, n)
    a = d.blocks.new('G_ASYM')
    asym(a, 'F102_insert_rotated')
    msp.add_blockref('G_ASYM', (60, 0), dxfattribs={'layer': 'F102_insert_rotated', 'rotation': 30})
    msp.add_blockref('G_ASYM', (80, 0), dxfattribs={'layer': 'F103_insert_mirrored', 'xscale': -1.0})
    msp.add_blockref('G_ASYM', (100, 0), dxfattribs={'layer': 'F104_insert_nonuniform', 'xscale': 2.0, 'yscale': 0.5, 'zscale': 1.5, 'rotation': 10})
    msp.add_blockref('G_ASYM', (0, 40), dxfattribs={'layer': 'F105_insert_minsert', 'row_count': 2, 'column_count': 3, 'row_spacing': 12.0, 'column_spacing': 9.0})
    lay(d, 'F106_unused_block')
    u = d.blocks.new('G_UNUSED')
    u.add_circle((0, 0), 2, dxfattribs={'layer': 'F106_unused_block'})
    for n in ('F107_wipeout_in_block', 'F108_wipeout_block_text', 'F109_wipeout_model'):
        lay(d, n)
    w = d.blocks.new('G_WIPE')
    w.add_wipeout([(0, 0), (12, 0), (12, 5), (0, 5)]).dxf.layer = 'F107_wipeout_in_block'
    t = w.add_text('OVER WIPE', height=2, dxfattribs={'layer': 'F108_wipeout_block_text'})
    t.set_placement((1, 1))
    w.add_line((0, 0), (12, 5), dxfattribs={'layer': 'F108_wipeout_block_text'})
    msp.add_blockref('G_WIPE', (0, 70), dxfattribs={'layer': 'F107_wipeout_in_block'})
    msp.add_wipeout([(30, 70), (40, 70), (42, 76), (30, 76)]).dxf.layer = 'F109_wipeout_model'
    lay(d, 'F110_none_arrowhead')
    d.blocks.new('_None')
    d.dimstyles.new('G_NONE', dxfattribs={'dimblk': '_None', 'dimblk1': '_None', 'dimblk2': '_None'})
    msp.add_linear_dim(base=(60, 70), p1=(60, 60), p2=(90, 60), dimstyle='G_NONE', dxfattribs={'layer': 'F110_none_arrowhead'}).render()
    lay(d, 'F111_anonymous_block')
    an = d.blocks.new('*U77')
    an.add_circle((0, 0), 3, dxfattribs={'layer': 'F111_anonymous_block'})
    msp.add_blockref('*U77', (110, 70), dxfattribs={'layer': 'F111_anonymous_block'})
    lay(d, 'F112_blockdefs_marker')
    msp.add_line((0, -10), (10, -10), dxfattribs={'layer': 'F112_blockdefs_marker'})
    return d
ATTR_CASES = [('constant', 2), ('invisible', 1), ('verify', 4), ('preset', 8), ('lockpos', 0), ('valuediff', 0)]

def master_h():
    d = new()
    msp = d.modelspace()
    d.styles.add('H_STYLE_A', font='', dxfattribs={'width': 0.7})
    d.styles.add('H_STYLE_B', font='', dxfattribs={'width': 1.2, 'oblique': 20})
    x = 0
    ly = {}

    def L(n):
        lay(d, n)
        return n

    def one(num, name, flags, ins_kw=None, lock=0, value='VAL', default='DEFAULT', attr_kw=None, attrib=True, tag=None, ad_kw=None):
        nonlocal x
        tag = tag or name.upper()
        bn = f'H_{name.upper()}'
        la, li, lr = (L(f'F{num}_attdef_{name}'), L(f'F{num}_insert_{name}'), L(f'F{num}_attrib_{name}'))
        b = d.blocks.new(bn)
        b.add_line((0, 0), (8, 0), dxfattribs={'layer': la})
        akw = {'layer': la, 'flags': flags}
        akw.update(ad_kw or {})
        ad = b.add_attdef(tag, (1, 2), default, height=1.5, dxfattribs=akw)
        ad.dxf.prompt = f'Prompt {name}'
        ad.dxf.field_length = 0
        if lock:
            ad.dxf.lock_position = 1
        ikw = {'layer': li}
        ikw.update(ins_kw or {})
        ins = msp.add_blockref(bn, (x, 0), dxfattribs=ikw)
        if attrib:
            ak = {'layer': lr, 'flags': flags}
            ak.update(attr_kw or {})
            a = ins.add_attrib(tag, value, insert=(x + 1, 2), dxfattribs=dict(ak, height=1.5))
            a.dxf.field_length = 0
            if lock:
                a.dxf.lock_position = 1
        x += 25
        return ins
    one(113, 'constant', 2, attrib=False, default='CONST TEXT')
    one(114, 'invisible', 1, value='HIDDEN VAL')
    one(115, 'verify', 4, value='VERIFY VAL')
    one(116, 'preset', 8, value='DEFAULT')
    one(117, 'lockpos', 0, lock=1, value='LOCKED')
    one(118, 'rotinsert', 0, ins_kw={'rotation': 40}, attr_kw={'rotation': 40}, value='ROT INS')
    one(119, 'mirinsert', 0, ins_kw={'xscale': -1.0}, value='MIR INS')
    one(120, 'textmirror', 0, attr_kw={'text_generation_flag': 2}, ad_kw={'text_generation_flag': 2}, value='MIR TXT')
    one(121, 'valuediff', 0, value='CHANGED VALUE 9', default='DEFAULT TXT')
    one(122, 'nodef', 0, attrib=False, default='NO ATTRIB INSTANCE')
    for n in ('F123_attdef_style_a', 'F124_attdef_style_b', 'F123_insert_styles', 'F123_attrib_style_a', 'F124_attrib_style_b'):
        L(n)
    b = d.blocks.new('H_STYLES')
    b.add_line((0, 0), (8, 0), dxfattribs={'layer': 'F123_attdef_style_a'})
    for tag, st, ln, y in (('STA', 'H_STYLE_A', 'F123_attdef_style_a', 2), ('STB', 'H_STYLE_B', 'F124_attdef_style_b', 5)):
        ad = b.add_attdef(tag, (1, y), 'def ' + tag, height=1.5, dxfattribs={'layer': ln, 'style': st})
        ad.dxf.prompt = tag
        ad.dxf.field_length = 0
    ins = msp.add_blockref('H_STYLES', (x, 0), dxfattribs={'layer': 'F123_insert_styles'})
    for tag, st, ln, y in (('STA', 'H_STYLE_A', 'F123_attrib_style_a', 2), ('STB', 'H_STYLE_B', 'F124_attrib_style_b', 5)):
        a = ins.add_attrib(tag, 'val ' + tag, insert=(x + 1, y), dxfattribs={'layer': ln, 'style': st, 'height': 1.5})
        a.dxf.field_length = 0
    return d

def master_i():
    d = new()
    msp = d.modelspace()
    cols = [1, 3, 5, 6]
    hs = []
    for i, n in enumerate('abcd'):
        ln = lay(d, f'F130_sortents_{n}', cols[i])
        e = msp.add_solid([(i * 4, 0), (i * 4 + 10, 0), (i * 4, 10), (i * 4 + 10, 10)], dxfattribs={'layer': ln})
        hs.append(e.dxf.handle)
    msp.set_redraw_order([(h, f'{1024 - 256 * i:X}') for i, h in enumerate(hs)])
    for n in 'abc':
        lay(d, f'F131_sortents_block_{n}')
    lay(d, 'F131_insert_sorted_block')
    b = d.blocks.new('I_SORTBLK')
    bh = []
    for i, n in enumerate('abc'):
        e = b.add_solid([(i * 3, 0), (i * 3 + 8, 0), (i * 3, 8), (i * 3 + 8, 8)], dxfattribs={'layer': f'F131_sortents_block_{n}'})
        bh.append(e.dxf.handle)
    b.set_redraw_order([(h, f'{768 - 256 * i:X}') for i, h in enumerate(bh)])
    msp.add_blockref('I_SORTBLK', (60, 0), dxfattribs={'layer': 'F131_insert_sorted_block'})
    for n in ('F132_xdict_line', 'F132_xdict_circle'):
        lay(d, n)
    ln = msp.add_line((0, 30), (20, 30), dxfattribs={'layer': 'F132_xdict_line'})
    xd = ln.new_extension_dict()
    xr = xd.add_xrecord('G_XR')
    xr.reset([(1, 'entity xrecord string'), (40, 3.25), (70, 7)])
    sub = xd.add_dictionary('G_SUB')
    xr2 = sub.add_xrecord('G_XR2')
    xr2.reset([(1, 'nested xrecord'), (90, 123456)])
    c = msp.add_circle((40, 30), 4, dxfattribs={'layer': 'F132_xdict_circle'})
    xd2 = c.new_extension_dict()
    xr3 = xd2.add_xrecord('G_ONLY')
    xr3.reset([(1, 'circle xrecord'), (10, (1.0, 2.0, 3.0))])
    lay(d, 'F133_dictionary_marker')
    msp.add_line((0, 50), (10, 50), dxfattribs={'layer': 'F133_dictionary_marker'})
    root = d.rootdict
    nd = d.objects.add_dictionary(owner=root.dxf.handle)
    root['G_NAMED_DICT'] = nd
    x1 = d.objects.add_xrecord(nd.dxf.handle)
    x1.reset([(1, 'named xrecord'), (40, 9.5), (70, 3)])
    nd['G_X1'] = x1
    v1 = d.objects.add_dictionary_var(nd.dxf.handle, 'dictvar value 77')
    nd['G_V1'] = v1
    sd = d.objects.add_dictionary(owner=nd.dxf.handle)
    nd['G_SUBDICT'] = sd
    x2 = d.objects.add_xrecord(sd.dxf.handle)
    x2.reset([(1, 'in sub dictionary')])
    sd['G_X2'] = x2
    lay(d, 'F134_xdict_owners')
    msp.add_line((0, 60), (10, 60), dxfattribs={'layer': 'F134_xdict_owners'})
    lx = d.layers.get('F134_xdict_owners').new_extension_dict()
    lxr = lx.add_xrecord('G_LAYER_XR')
    lxr.reset([(1, 'layer xrecord'), (70, 5)])
    bk = d.blocks.new('I_XDBLK')
    bk.add_circle((0, 0), 1, dxfattribs={'layer': 'F134_xdict_owners'})
    bx = bk.block_record.new_extension_dict()
    bxr = bx.add_xrecord('G_BLOCK_XR')
    bxr.reset([(1, 'block record xrecord'), (40, 1.5)])
    return d

def make_png(path, w=64, h=48):
    rows = b''
    for y in range(h):
        rows += b'\x00' + b''.join((bytes((int(255 * x / w), int(255 * y / h), 128)) for x in range(w)))

    def chunk(t, data):
        c = struct.pack('>I', len(data)) + t + data
        return c + struct.pack('>I', zlib.crc32(t + data) & 4294967295)
    content = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
    if not path.exists() or path.read_bytes()!=content:
        path.write_bytes(content)

def master_j():
    make_png(ASSETS / 'J_img.png')
    d = new()
    msp = d.modelspace()
    idef = d.add_image_def('J_img.png', (64, 48), name='J_IMG')
    specs = [('F140_image_plain', (0, 0), 0, None, {}), ('F141_image_rotated', (60, 0), 25, None, {}), ('F142_image_clip_rect', (0, 50), 0, [(10, 10), (50, 40)], {}), ('F143_image_clip_poly', (60, 50), 0, [(10, 5), (54, 12), (60, 40), (30, 46), (4, 30), (10, 5)], {}), ('F144_image_adjust', (120, 0), 0, None, {'brightness': 70, 'contrast': 30, 'fade': 20})]
    for ln, at, rot, clip, extra in specs:
        lay(d, ln)
        im = msp.add_image(idef, at, size_in_units=(40, 30), rotation=rot, dxfattribs={'layer': ln})
        if clip:
            im.set_boundary_path(clip)
        for k, v in extra.items():
            im.dxf.set(k, v)
    try:
        rv = d.objects.add_dxf_object_with_reactor('RASTERVARIABLES', dxfattribs={'owner': d.rootdict.dxf.handle, 'frame': 1, 'quality': 0, 'units': 3, 'class_version': 0})
        d.rootdict['ACAD_IMAGE_VARS'] = rv
    except Exception as e:
        print('rastervariables:', e)
    return d

def master_n():
    d = new()
    msp = d.modelspace()
    for n in ('F160_polyline2d_width_bulge', 'F161_polyline2d_closed', 'F162_polyline3d', 'F163_point', 'F164_solid', 'F165_scale_marker'):
        lay(d, n)
    pl = msp.add_polyline2d([(0, 0, 0.5, 1.5, 0.0), (10, 0, 1.0, 0.2, 0.5), (20, 5, 0, 0, -0.4), (30, 0, 0.8, 0.8, 0)], format='xyseb', dxfattribs={'layer': 'F160_polyline2d_width_bulge'})
    msp.add_polyline2d([(0, 20, 0.3, 0.3, 0.2), (10, 20, 0.3, 0.3, 0), (10, 30, 0.3, 0.3, 0), (0, 30, 0.3, 0.3, 0)], format='xyseb', close=True, dxfattribs={'layer': 'F161_polyline2d_closed'})
    msp.add_polyline3d([(0, 40, 0), (10, 42, 3), (20, 40, 6), (30, 44, 2)], dxfattribs={'layer': 'F162_polyline3d'})
    d.header['$PDMODE'] = 35
    d.header['$PDSIZE'] = 2.5
    for i in range(3):
        msp.add_point((i * 5, 60), dxfattribs={'layer': 'F163_point'})
    msp.add_solid([(0, 70), (10, 70), (0, 80), (10, 82)], dxfattribs={'layer': 'F164_solid', 'thickness': 2.0})
    msp.add_line((0, 90), (5, 90), dxfattribs={'layer': 'F165_scale_marker'})
    for n in ('F166_viewport_scaled', 'F167_viewport_twisted', 'F168_viewport_frozen'):
        lay(d, n)
    lo = d.layouts.new('N Layout')
    lo.page_setup(size=(297, 210), margins=(5, 5, 5, 5), units='mm')
    v1 = lo.add_viewport(center=(60, 100), size=(100, 80), view_center_point=(15, 30), view_height=40, dxfattribs={'layer': 'F166_viewport_scaled'})
    v2 = lo.add_viewport(center=(200, 100), size=(80, 80), view_center_point=(15, 30), view_height=100, dxfattribs={'layer': 'F167_viewport_twisted'})
    v2.dxf.view_twist_angle = 30
    v3 = lo.add_viewport(center=(60, 30), size=(60, 30), view_center_point=(15, 30), view_height=30, dxfattribs={'layer': 'F168_viewport_frozen'})
    v3.frozen_layers = ['F163_point']
    lay(d, 'F169_scale_list_marker')
    msp.add_line((0, 95), (5, 95), dxfattribs={'layer': 'F169_scale_list_marker'})
    sl = d.objects.add_dictionary(owner=d.rootdict.dxf.handle)
    d.rootdict['ACAD_SCALELIST'] = sl
    d.__scalelist_handle = sl.dxf.handle
    return d
