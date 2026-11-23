"""Synthetic comparison contracts for symbol names and dictionary paths."""
import ezdxf
import pytest
from checker.core import compare


def row(d, selector, value):
    field = dict(id='field', selector=selector, value=value, tolerance=0, versions=[d.dxfversion])
    return compare(d, dict(intent_id='synthetic', expected=[field]), 'test')[0]


def feature(layer, attr, table='TEXT'):
    return dict(kind='feature_attr', table=table, name=layer, attr=attr)


def test_r12_uppercase_layer_selection_and_raw_name():
    d = ezdxf.new('R12')
    d.modelspace().add_text('Hello', dxfattribs={'layer': 'ZEV_LAYER'})
    result = row(d, feature('zev_layer', 'layer'), 'zev_layer')
    assert result['status'] == 'same'
    assert result['actual'] == 'ZEV_LAYER'


@pytest.mark.parametrize('actual,expected,status', [('ZEV_A', 'zev_a', 'same'), ('ZEV_A', 'zev_b', 'differs')])
def test_symbol_values(actual, expected, status):
    d = ezdxf.new()
    d.modelspace().add_text('Hello', dxfattribs={'layer': actual})
    assert row(d, feature(actual, 'layer'), expected)['status'] == status


def test_text_content_remains_case_sensitive():
    d = ezdxf.new()
    d.modelspace().add_text('Hello', dxfattribs={'layer': 'ZEV_TEXT'})
    assert row(d, feature('ZEV_TEXT', 'text'), 'hello')['status'] == 'differs'


def test_linetype_token_case():
    d = ezdxf.new()
    d.modelspace().add_line((0, 0), (1, 1), dxfattribs={'layer': 'ZEV_LINE', 'linetype': 'BYLAYER'})
    result = row(d, feature('ZEV_LINE', 'linetype', 'LINE'), 'ByLayer')
    assert result['status'] == 'same'
    assert result['actual'] == 'BYLAYER'


def test_symbol_query_and_prefix_count():
    d = ezdxf.new()
    d.layers.new('zev_layer')
    d.blocks.new('zev_block')
    d.modelspace().add_blockref('zev_block', (0, 0))
    assert row(d, {'kind': 'layer_count'}, 1)['status'] == 'same'


def test_insert_query_name_case():
    d = ezdxf.new()
    d.blocks.new('zev_block')
    d.modelspace().add_blockref('zev_block', (0, 0))
    assert row(d, {'kind': 'query_count', 'name': 'INSERT[name=="ZEV_BLOCK"]'}, 1)['status'] == 'same'


def test_frozen_layers_are_case_insensitive_sets():
    d = ezdxf.new()
    vp = d.layouts.new('ZEV_PAPER').add_viewport(center=(0, 0), size=(4, 4), view_center_point=(0, 0), view_height=4, dxfattribs={'layer': 'ZEV_VP'})
    vp.frozen_layers = ['zev_b', 'ZEV_A']
    result = row(d, feature('ZEV_VP', 'frozen_layers', 'VIEWPORT'), ['zev_a', 'ZEV_B'])
    assert result['status'] == 'same'
    assert result['actual'] == ['zev_b', 'ZEV_A']


def test_empty_frozen_list_is_not_nonempty():
    d = ezdxf.new()
    d.layouts.new('ZEV_PAPER').add_viewport(center=(0, 0), size=(4, 4), view_center_point=(0, 0), view_height=4, dxfattribs={'layer': 'ZEV_VP'})
    assert row(d, feature('ZEV_VP', 'frozen_layers', 'VIEWPORT'), ['ZEV_A'])['status'] == 'differs'


def test_draw_order_names_ignore_case_but_order_matters():
    d = ezdxf.new()
    space = d.modelspace()
    for layer in ('ZEV_A', 'ZEV_B'):
        space.add_line((0, 0), (1, 1), dxfattribs={'layer': layer})
    selector = feature('zev_a', 'redraw_order', 'LINE')
    assert row(d, selector, ['zev_a', 'zev_b'])['status'] == 'same'


def test_draw_order_remains_ordered():
    d = ezdxf.new()
    for layer in ('ZEV_A', 'ZEV_B'):
        d.modelspace().add_line((0, 0), (1, 1), dxfattribs={'layer': layer})
    assert row(d, feature('ZEV_A', 'redraw_order', 'LINE'), ['ZEV_B', 'ZEV_A'])['status'] == 'differs'


def test_dictionary_path_case_and_value_case():
    d = ezdxf.new()
    nested = d.rootdict.add_new_dict('ZEV_DICT')
    nested.add_dict_var('ZEV_KEY', 'Mixed')
    selector = dict(kind='object', dictionary='zev_dict', name='zev_key', attr='value')
    result = row(d, selector, 'Mixed')
    assert result['status'] == 'same'
    assert result['actual'] == 'Mixed'
    assert row(d, selector, 'mixed')['status'] == 'differs'


def test_ambiguous_dictionary_key_fails_loudly():
    d = ezdxf.new()
    nested = d.rootdict.add_new_dict('ZEV_DICT')
    nested.add_dict_var('Key', 'one')
    nested.add_dict_var('KEY', 'two')
    result = row(d, dict(kind='object', dictionary='ZEV_DICT', name='key', attr='value'), 'one')
    assert result['status'] == 'absent'
    assert 'ambigu' in result['detail'].lower()


def test_renumbered_anonymous_block_reference():
    d = ezdxf.new()
    block = d.blocks.new_anonymous_block('U')
    block.add_line((0, 0), (1, 0))
    d.modelspace().add_blockref(block.name, (0, 0), dxfattribs={'layer': 'ZEV_INSERT'})
    result = row(d, feature('ZEV_INSERT', 'name', 'INSERT'), '*U77')
    assert result['status'] == 'same'
    assert result['actual'] == block.name


def test_anonymous_block_name_rejects_named_reference():
    d = ezdxf.new()
    d.blocks.new('ZEV_NAMED')
    d.modelspace().add_blockref('ZEV_NAMED', (0, 0), dxfattribs={'layer': 'F111_anonymous_block'})
    assert row(d, feature('F111_anonymous_block', 'name', 'INSERT'), '*U77')['status'] == 'differs'


@pytest.mark.parametrize('radius,expected_status', [(3, 'same'), (4, 'differs')])
def test_anonymous_block_referenced_circle_radius(radius, expected_status):
    d = ezdxf.new()
    block = d.blocks.new_anonymous_block('U')
    block.add_circle((0, 0), radius)
    d.modelspace().add_blockref(block.name, (0, 0), dxfattribs={'layer': 'F111_anonymous_block'})
    # Proposed intent field: feature_attr on the INSERT layer, with
    # attr='block_circle_radius' resolving the referenced block's CIRCLE radius.
    selector = feature('F111_anonymous_block', 'block_circle_radius', 'INSERT')
    assert row(d, selector, 3)['status'] == expected_status


def test_differently_named_blocks_remain_different():
    d = ezdxf.new()
    d.blocks.new('ZEV_A')
    d.modelspace().add_blockref('ZEV_A', (0, 0), dxfattribs={'layer': 'ZEV_INSERT'})
    assert row(d, feature('ZEV_INSERT', 'name', 'INSERT'), 'ZEV_B')['status'] == 'differs'


def test_anonymous_name_requires_flag():
    d = ezdxf.new()
    block = d.blocks.new_anonymous_block('U')
    block.block.dxf.flags &= ~1
    d.modelspace().add_blockref(block.name, (0, 0), dxfattribs={'layer': 'F111_anonymous_block'})
    assert row(d, feature('F111_anonymous_block', 'name', 'INSERT'), '*U77')['status'] == 'differs'


@pytest.mark.parametrize('radii,status', [([5, 3], 'same'), ([], 'absent')])
def test_anonymous_content_any_matching_circle(radii, status):
    d = ezdxf.new()
    block = d.blocks.new_anonymous_block('U')
    for radius in radii:
        block.add_circle((0, 0), radius)
    d.modelspace().add_blockref(block.name, (0, 0), dxfattribs={'layer': 'F111_anonymous_block'})
    assert row(d, feature('F111_anonymous_block', 'block_circle_radius', 'INSERT'), 3)['status'] == status


@pytest.mark.parametrize('attr,expected', [('name', 'zev_layer'), ('linetype', 'zev_dash')])
def test_r12_layer_table_symbol_case(attr, expected):
    d = ezdxf.new('R12')
    d.linetypes.new('ZEV_DASH', dxfattribs={'pattern': [1, .5, -.5]})
    d.layers.new('ZEV_LAYER', dxfattribs={'linetype': 'ZEV_DASH'})
    assert row(d, dict(kind='table', table='layers', name='zev_layer', attr=attr), expected)['status'] == 'same'


def test_complex_pattern_style_case():
    d = ezdxf.new()
    d.styles.new('ZEV_TEXT', dxfattribs={'font': 'txt'})
    lt = d.linetypes.new('ZEV_TEXT_PATTERN')
    lt.setup_pattern('A,.5,-.2,["ZEV",ZEV_TEXT,S=.1,R=0,X=0,Y=0],-.2', length=.9)
    assert row(d, dict(kind='complex_pattern', name='zev_text_pattern', attr='style'), 'zev_text')['status'] == 'same'


def test_viewport_freeze_case():
    d = ezdxf.new()
    vp = d.layouts.new('zev_paper').add_viewport((5, 5), (10, 10), (0, 0), 10)
    vp.freeze('zev_001')
    assert row(d, dict(kind='viewport_freeze'), ['ZEV_001'])['status'] == 'same'


def test_viewport_color_layer_case():
    d = ezdxf.new()
    layer = d.layers.new('zev_002')
    vp = d.layouts.new('zev_paper').add_viewport((5, 5), (10, 10), (0, 0), 10)
    overrides = layer.get_vp_overrides()
    overrides.set_color(vp.dxf.handle, 6)
    overrides.commit()
    assert row(d, dict(kind='viewport_color', name='ZEV_002'), 6)['status'] == 'same'


def test_identity_application_key_case():
    d = ezdxf.new()
    d.modelspace().block_record.block.set_xdata('zev_identity', [(1000, 'synthetic'), (1000, 'reference_1')])
    assert row(d, dict(kind='identity'), ['synthetic', 'reference_1'])['status'] == 'same'


def test_xdata_application_key_case():
    d = ezdxf.new()
    d.modelspace().add_point((0, 0)).set_xdata('zev_app', [(1000, 'ZEV_DATA')])
    assert row(d, dict(kind='xdata'), [[1000, 'ZEV_DATA']])['status'] == 'same'


def test_appid_table_name_case():
    d = ezdxf.new()
    d.appids.new('zev_app')
    assert row(d, dict(kind='table', table='appids', name='ZEV_APP', attr='name'), 'ZEV_APP')['status'] == 'same'


def test_xrecord_key_case():
    d = ezdxf.new()
    record = d.modelspace().add_point((0, 0)).new_extension_dict().add_xrecord('zev_record')
    record.reset([(1, 'ZEV_RECORD_VALUE'), (90, 42)])
    assert row(d, dict(kind='xrecord'), [[1, 'ZEV_RECORD_VALUE'], [90, 42]])['status'] == 'same'


def test_layout_name_case():
    d = ezdxf.new()
    d.layouts.new('zev_empty')
    assert row(d, dict(kind='layout_count', name='ZEV_EMPTY'), 0)['status'] == 'same'


def test_group_name_case():
    d = ezdxf.new()
    group = d.groups.new('zev_group')
    group.set_data([d.modelspace().add_point((0, 0))])
    assert row(d, dict(kind='group', name='ZEV_GROUP'), 1)['status'] == 'same'


def test_query_count_layer_case():
    d = ezdxf.new()
    d.modelspace().add_point((0, 0), dxfattribs={'layer': 'zev_000'})
    assert row(d, dict(kind='query_count', name='*[layer=="ZEV_000"]'), 1)['status'] == 'same'


def test_unsupported_query_fails_loudly():
    d = ezdxf.new()
    result = row(d, dict(kind='query_count', name='*[color>1]'), 0)
    assert result['status'] == 'absent'
    assert result['detail']


def test_query_count_does_not_import_ezdxf_parser_internals(monkeypatch):
    import builtins
    original_import = builtins.__import__

    def public_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'ezdxf.queryparser' or (name == 'ezdxf.query' and any(
                item in {'Relation', 'BoolExpression', 'build_entity_name_matcher'} for item in fromlist)):
            raise AssertionError('query parser internals imported')
        return original_import(name, globals, locals, fromlist, level)

    d = ezdxf.new()
    d.modelspace().add_point((0, 0), dxfattribs={'layer': 'zev_000'})
    monkeypatch.setattr(builtins, '__import__', public_import)
    assert row(d, dict(kind='query_count', name='*[layer=="ZEV_000"]'), 1)['status'] == 'same'
