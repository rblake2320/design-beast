import hashlib
from types import SimpleNamespace

import pytest

from watch import ocr_observer


def test_utf8_and_same_verified_bytes_despite_source_replacement(tmp_path, monkeypatch):
    path = tmp_path / "frame.jpg"
    path.write_bytes(b"original")
    expected = hashlib.sha256(b"original").hexdigest()
    tsv = "level\tpage_num\ttext\n5\t1\tÉditer →\n"
    def run(command, **kwargs):
        path.write_bytes(b"replaced")
        assert kwargs["input"] == b"original"
        assert "text" not in kwargs
        return SimpleNamespace(stdout=tsv.encode("utf-8"))
    monkeypatch.setattr(ocr_observer.subprocess, "run", run)
    result = ocr_observer.observe_ocr(path, expected, "tesseract")
    assert result["tsv"] == tsv
    assert result["frame_sha256"] == expected


@pytest.mark.parametrize("response", [b"", b"not tsv", b"\xff"])
def test_invalid_ocr_cannot_be_recorded(tmp_path, monkeypatch, response):
    path = tmp_path / "frame.jpg"
    path.write_bytes(b"original")
    monkeypatch.setattr(ocr_observer.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=response))
    with pytest.raises(ValueError):
        ocr_observer.observe_ocr(path, hashlib.sha256(b"original").hexdigest(), "tesseract")
