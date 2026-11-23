"""Synthetic proxy, layer flag, and linetype comparisons."""
import io
import ezdxf
import pytest
from checker.core import compare


def row(d, selector, value):
    f = dict(id='field', selector=selector, value=value, tolerance=0, versions=[d.dxfversion])
    return compare(d, dict(intent_id='synthetic', expected=[f]), 'test')[0]


def proxy(kind, payload=7, envelope=None):
    d = ezdxf.new('R2018')
    stream = io.StringIO()
    d.write(stream)
    text = stream.getvalue()
    subclass = 'AcDbProxyEntity' if kind == 'ENTITY' else 'AcDbProxyObject'
    envelope_tag = '' if envelope is None else ' 90\n%d\n' % envelope
    common = '  0\nACAD_PROXY_%s\n  5\nFEED\n' % kind
    if kind == 'ENTITY':
        common += '100\nAcDbEntity\n  8\nZEV_PROXY\n'
    entity = common + '100\n%s\n%s 90\n%d\n 40\n2.5\n' % (subclass, envelope_tag, payload)
    marker = '  2\n%s\n' % ('ENTITIES' if kind == 'ENTITY' else 'OBJECTS')
    if kind == 'ENTITY':
        text = text.replace(marker, marker + entity, 1)
    else:
        end = text.index('  0\nENDSEC\n', text.index(marker))
        text = text[:end] + entity + text[end:]
    d = ezdxf.read(io.StringIO(text))
    if kind == 'OBJECT':
        d.rootdict['ZEV_PROXY'] = d.entitydb['FEED']
    return d


def proxy_selector(kind):
    if kind == 'ENTITY':
        return dict(kind='feature_attr', table='ACAD_PROXY_ENTITY', name='ZEV_PROXY', attr='opaque_values')
    return dict(kind='object', dictionary='ROOT', name='ZEV_PROXY', attr='opaque_values')


@pytest.mark.parametrize('kind,envelope', [('OBJECT', 499), ('ENTITY', 498)])
def test_proxy_envelope_is_not_payload(kind, envelope):
    result = row(proxy(kind, envelope=envelope), proxy_selector(kind), [[90, 7], [40, 2.5]])
    assert result['status'] == 'same'
    assert [90, envelope] in result['actual']


@pytest.mark.parametrize('kind,envelope', [('OBJECT', 499), ('ENTITY', 498)])
def test_changed_proxy_payload_is_changed(kind, envelope):
    assert row(proxy(kind, payload=8, envelope=envelope), proxy_selector(kind), [[90, 7], [40, 2.5]])['status'] == 'differs'


@pytest.mark.parametrize('kind,envelope', [('OBJECT', 498), ('ENTITY', 499), ('OBJECT', None), ('ENTITY', None)])
def test_proxy_wrong_or_missing_envelope_is_absent(kind, envelope):
    result = row(proxy(kind, envelope=envelope), proxy_selector(kind), [[90, 7], [40, 2.5]])
    assert result['status'] == 'absent'
    assert 'envelope' in result['detail'].lower()


@pytest.mark.parametrize('flags,expected,status', [(64, 0, 'same'), (1, 0, 'differs'), (4, 0, 'differs'), (2, 0, 'differs'), (16, 0, 'differs')])
def test_layer_flag_bits(flags, expected, status):
    d = ezdxf.new()
    layer = d.layers.new('ZEV_LAYER')
    layer.dxf.flags = flags
    result = row(d, dict(kind='table', table='layers', name='ZEV_LAYER', attr='flags'), expected)
    assert result['status'] == status
    assert result['actual'] == flags


def test_linetype_scalar_tag_order_is_irrelevant():
    d = ezdxf.new()
    d.linetypes.new('ZEV_DASH', dxfattribs={'pattern': [1.0, 0.6, -0.4]})
    selector = dict(kind='linetype_pattern', name='ZEV_DASH')
    expected = [[73, 2], [72, 65], [40, 1.0], [49, 0.6], [49, -0.4]]
    result = row(d, selector, expected)
    assert result['status'] == 'same'
    assert result['actual'] != expected


def test_linetype_dash_order_matters():
    d = ezdxf.new()
    d.linetypes.new('ZEV_DASH', dxfattribs={'pattern': [1.0, 0.6, -0.4]})
    selector = dict(kind='linetype_pattern', name='ZEV_DASH')
    assert row(d, selector, [[72, 65], [73, 2], [40, 1.0], [49, -0.4], [49, 0.6]])['status'] == 'differs'
