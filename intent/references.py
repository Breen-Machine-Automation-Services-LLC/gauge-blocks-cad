"""Assign authored expectation bases and owning DXF item pages before saving."""
try:
    from .reference_pages import PAGES
except ImportError:
    from reference_pages import PAGES

TABLES = {'layers': 'LAYER', 'linetypes': 'LTYPE', 'styles': 'STYLE',
          'dimstyles': 'DIMSTYLE', 'appids': 'APPID', 'views': 'VIEW', 'ucs': 'UCS'}
ALIASES = {'ACAD_TABLE': 'TABLE', 'MULTILEADER': 'MLEADER'}


def author_references(intent):
    for field in intent.get('expected', []):
        selector = field['selector']
        kind, attr = selector['kind'], selector.get('attr')
        ref = field['reference']
        basis = ref['basis']
        basis_type = ref['basis_type']
        if basis_type not in {'synthetic', 'normative', 'application_semantics', 'compatibility_policy'}:
            raise ValueError(f'Invalid authored basis type: {basis_type}')
        if kind == 'feature_attr':
            item = ALIASES.get(selector['table'], selector['table'])
            if attr == 'alignment_rotation_error':
                ref['section'] = item + '; groups 10,11,50,72: alignment rotation'
            if attr == 'extension_record':
                item = 'XRECORD'
            elif attr == 'redraw_order':
                item = 'SORTENTSTABLE'
            elif attr == 'block_circle_radius':
                item = 'CIRCLE'
                ref['section'] = 'CIRCLE group 40; circle in INSERT-referenced block'
        elif kind == 'table':
            item = TABLES.get(selector['table'], selector['table'])
        elif kind == 'object':
            item = {'ACAD_PLOTSETTINGS': 'PLOTSETTINGS', 'ACAD_SCALELIST': 'SCALE',
                    'ACAD_VISUALSTYLE': 'VISUALSTYLE'}.get(selector['dictionary'])
            if item is None:
                item = {'value': 'DICTIONARYVAR', 'tags': 'XRECORD',
                        'opaque_values': 'ACAD_PROXY_OBJECT'}[attr]
        elif kind == 'query_count':
            item = selector['name'].split('[')[0].split()[0]
            if item == '*':
                item = 'LAYER'
        elif kind == 'block':
            item = 'INSERT' if attr == 'inserts' else 'ATTDEF'
        else:
            item = {'identity': 'BLOCK', 'insert_attributes': 'ATTRIB',
                    'linetype_pattern': 'LTYPE', 'complex_pattern': 'LTYPE',
                    'layer_count': 'LAYER', 'layout_count': 'LAYOUT',
                    'viewport_freeze': 'VIEWPORT', 'viewport_color': 'LAYER',
                    'xdata': 'APPID', 'xrecord': 'XRECORD', 'group': 'GROUP'}[kind]
        if kind == 'linetype_pattern' and [72, 65] in field['value'] and 'LTYPE group 72 is fixed' not in basis:
            basis += '; LTYPE group 72 is fixed at 65; dash lengths and pattern size are invented.'
        if item == 'SCALE':
            ref['section'] = 'OBJECTS section; scale-list entries'
            basis = basis.split('; No item page exists')[0]
            explanation = '; No item page exists for SCALE in the cataloged Reference contents; the OBJECTS section is the available reference, not a specification of scale-entry codes.'
            if explanation not in basis:
                basis += explanation
            item = 'OBJECTS'
        if item not in PAGES:
            if 'No item page exists' not in basis:
                basis += '; No item page exists for the invented custom class; the proxy entity page is the best available envelope reference.'
            item = 'ACAD_PROXY_ENTITY'
        if basis_type == 'synthetic' and 'invent' not in basis.lower():
            basis += '; The expected value is an invented fixture choice.'
        ref.update(url=PAGES[item], basis=basis)
        if kind == 'object' and item != 'OBJECTS':
            ref['section'] = item + '; ' + attr
    return intent
