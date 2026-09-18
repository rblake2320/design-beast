import hashlib

import pytest
from PIL import Image

from watch.temporal_observer import pixel_change


def test_fraction_uses_any_rgb_channel_and_strict_threshold(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (2, 2)).save(a)
    image = Image.new("RGB", (2, 2))
    image.putpixel((0, 0), (21, 0, 0))
    image.putpixel((1, 0), (0, 20, 0))
    image.putpixel((1, 1), (0, 0, 255))
    image.save(b)
    assert pixel_change(a, b, hashlib.sha256(a.read_bytes()).hexdigest(),
                        hashlib.sha256(b.read_bytes()).hexdigest()) == 0.5
    with pytest.raises(ValueError, match="custody"):
        pixel_change(a, b, "0" * 64)


def test_mismatched_dimensions_rejected(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (2, 2)).save(a)
    Image.new("RGB", (2, 3)).save(b)
    with pytest.raises(ValueError, match="invalid pair"):
        pixel_change(a, b)
