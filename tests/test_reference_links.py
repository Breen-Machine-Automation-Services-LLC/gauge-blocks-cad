"""Every Autodesk help link stays on an edition whose viewer opens in Chromium-based browsers.

In those browsers Autodesk's viewer shows "Page Not Found" for its 2025 and later pages (Firefox shows
them), so a browser check alone does not catch a newer link. No network access.
"""
import importlib.util
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELP_YEAR = re.compile(r'help\.autodesk\.com/(?:cloudhelp|view/[A-Za-z0-9_-]+)/(\d{4})/')
DXF_YEAR = re.compile(r'help\.autodesk\.com/cloudhelp/(\d{4})/ENU/AutoCAD-DXF/')


def module(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def tracked_text():
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    for name in filter(None, (n.decode() for n in names)):
        if name.endswith(('.dxf', '.dwg', '.png', '.zip', '.pdf')):
            continue
        try:
            yield name, (ROOT / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue


def edition_violations(files, edition):
    """DXF reference pages use exactly the pinned edition; other Autodesk help links use it or an older one."""
    bad = []
    for name, text in files:
        bad += [(name, y) for y in DXF_YEAR.findall(text) if int(y) != edition]
        bad += [(name, y) for y in HELP_YEAR.findall(text) if int(y) > edition]
    return bad


def test_every_autodesk_help_link_in_the_repository_uses_a_working_edition():
    edition = module('standard/reference_catalog.py').EDITION
    bad = edition_violations(tracked_text(), edition)
    assert not bad, bad[:10]


@pytest.mark.parametrize('link,rejected', [
    ('https://help.autodesk.com/cloudhelp/{newer}/ENU/AutoCAD-DXF/files/GUID-747865D5-51F0-45F2-BEFE-9572DBC5B151.htm', True),
    ('https://help.autodesk.com/cloudhelp/{older}/ENU/AutoCAD-DXF/files/GUID-747865D5-51F0-45F2-BEFE-9572DBC5B151.htm', True),
    ('https://help.autodesk.com/view/OARX/{newer}/ENU/?guid=GUID-747865D5-51F0-45F2-BEFE-9572DBC5B151', True),
    ('https://help.autodesk.com/cloudhelp/{newer}/PLK/AutoCAD-AutoLISP/files/GUID-EB9BFDAA-487A-4586-A556-1F5F84BCF2F3.htm', True),
    ('https://help.autodesk.com/cloudhelp/{older}/ENU/OARX-DevGuide/files/GUID-83ABF20A-57D4-4AB3-8A49-D91E0F70DBFF.htm', False),
    ('https://help.autodesk.com/view/OARX/{edition}/ENU/', False),
])
def test_edition_rule_on_each_link_shape(link, rejected):
    edition = module('standard/reference_catalog.py').EDITION
    text = link.format(newer=edition + 1, older=edition - 1, edition=edition)
    assert bool(edition_violations([('probe.md', text)], edition)) is rejected


def test_map_link_check_rejects_a_reference_outside_the_pinned_edition():
    check = module('map/check_links.py')
    catalog = check.catalog()
    good = catalog.url('747865D5-51F0-45F2-BEFE-9572DBC5B151')
    assert check.reference_links(f'<a href="{good}">') == {good}
    newer = good.replace(f'/{catalog.EDITION}/', f'/{catalog.EDITION + 1}/')
    with pytest.raises(AssertionError):
        check.reference_links(f'<a href="{newer}">')
