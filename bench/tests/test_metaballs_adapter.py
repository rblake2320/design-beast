import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw


PATH = Path(__file__).parents[1] / "heldout-typed-compiler" / "metaballs_adapter.py"
SPEC = importlib.util.spec_from_file_location("metaballs_adapter", PATH)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def state_values():
    data = {"object_count": 2, "shape_kind": "circle",
            "layout_axis": "horizontal", "grouped": True,
            "circle_diameter": 248.922, "initial_group_width": 602.857,
            "initial_group_height": 248.922,
            "spacing_strategy": "move_closer",
            "success_condition": "single_connected_component",
            "primitive_1": "feGaussianBlur", "primitive_2": "feColorMatrix",
            "primitive_3": "feColorMatrix", "color_matrix_type": "matrix",
            "std_deviation_x": 34.79, "std_deviation_y": 34.79}
    for row in range(4):
        for column in range(5):
            data[f"a{row}{column}"] = 1.0 if row == column and row < 3 else 0.0
    data["a33"], data["a34"] = 20.0, -10.0
    return data


def test_svg_contains_exact_typed_filter_chain():
    payload = adapter.build_svg(state_values(), filtered=True)
    assert payload.count("<feColorMatrix") == 2
    assert '<feGaussianBlur stdDeviation="34.79 34.79"' in payload
    assert "0 0 0 20 -10" in payload
    assert 'width="800" height="480"' in payload


def test_component_measure_distinguishes_two_shapes_from_one():
    separate = Image.new("RGBA", (60, 30), (0, 0, 0, 0))
    draw = ImageDraw.Draw(separate)
    draw.rectangle((2, 5, 15, 20), fill=(255, 0, 0, 255))
    draw.rectangle((40, 5, 55, 20), fill=(255, 0, 0, 255))
    joined = separate.copy()
    ImageDraw.Draw(joined).rectangle((15, 10, 40, 15), fill=(255, 0, 0, 255))
    assert adapter.connected_components(separate) == 2
    assert adapter.connected_components(joined) == 1
