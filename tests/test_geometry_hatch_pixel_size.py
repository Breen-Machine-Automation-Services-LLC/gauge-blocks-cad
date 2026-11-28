"""Check the serialized hatch tags needed for derived boundary paths."""
import pytest

from generators.features import build


@pytest.mark.parametrize('version', ['2000', '2007', '2018'])
def test_geometry_hatch_pixel_size(version, tmp_path):
    path = tmp_path / f'b_geometry_{version}.dxf'
    build('b_geometry', version).saveas(path, fmt='asc')
    lines = path.read_text(encoding='utf-8').splitlines()
    tags = [(int(code.strip()), value.strip())
            for code, value in zip(lines[::2], lines[1::2])]
    hatches = []
    entity = None
    for code, value in tags:
        if code == 0:
            if entity is not None:
                hatches.append(entity)
            entity = [] if value == 'HATCH' else None
        elif entity is not None:
            entity.append((code, value))
    if entity is not None:
        hatches.append(entity)

    target = [hatch for hatch in hatches
              if (8, 'F23_hatch_flags7_22') in hatch]
    assert len(target) == 1
    for hatch in hatches:
        pixels = [(index, value) for index, (code, value) in enumerate(hatch)
                  if code == 47]
        if hatch is target[0]:
            assert len(pixels) == 1
            index, value = pixels[0]
            assert float(value) == 0.0
            assert hatch[index + 1][0] == 98
        else:
            assert not pixels
