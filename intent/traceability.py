"""Regenerate citations on existing independently authored expectations.

This authoring pass preserves values, selectors and comparison settings. It reads
intents only, never drawing output. Run after any other intent authoring script.
"""
import json
from pathlib import Path
from references import author_references


def main():
    for path in sorted(Path(__file__).parent.glob('*.json')):
        if path.name.endswith('.schema.json'):
            continue
        intent = json.loads(path.read_text())
        policies = {
            'feature_a_text': [
                'F01_text_aligned.height', 'F03_attdef_aligned.height', 'F05_attrib_aligned.height',
                'F01_text_fit.width', 'F03_attdef_fit.width', 'F05_attrib_fit.width',
                'F01_text_aligned.alignment_rotation_error', 'F03_attdef_aligned.alignment_rotation_error',
                'F05_attrib_aligned.alignment_rotation_error', 'F01_text_fit.alignment_rotation_error',
                'F03_attdef_fit.alignment_rotation_error', 'F05_attrib_fit.alignment_rotation_error'],
            'feature_i_dictionaries': ['F130_sortents_a.redraw_order', 'F131_sortents_block_a.redraw_order'],
            'feature_e_objects': ['F71_marker.acad_marker'],
        }
        for field in intent.get('expected', []):
            if field['id'] in policies.get(intent['intent_id'], []):
                field['reference']['basis_type'] = 'compatibility_policy'
        author_references(intent)
        path.write_text(json.dumps(intent, indent=2) + '\n')


if __name__ == '__main__':
    main()
