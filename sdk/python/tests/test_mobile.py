import io
import json
from pathlib import Path
import sys
import time

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from beast_studio_client import mobile as m

UI = b'<hierarchy><node package="com.example.test" text="Save" resource-id="save" bounds="[0,0][4,4]" clickable="true" enabled="true" /></hierarchy>'


@pytest.fixture
def bundle(tmp_path):
    data = io.BytesIO()
    Image.new("RGB", (4, 4)).save(data, "PNG")
    screen = data.getvalue()
    (tmp_path / "ui.xml").write_bytes(UI)
    (tmp_path / "screen.png").write_bytes(screen)
    path = tmp_path / "observation.json"
    path.write_text(json.dumps({"schema": m.SCHEMA, "id": "test", "serial": "test-device",
        "package": "com.example.test", "captured_unix": time.time(),
        "artifacts": {"ui": {"file": "ui.xml", "sha256": m._digest(UI)},
                      "screenshot": {"file": "screen.png", "sha256": m._digest(screen)}}}))
    return path


def test_exact_state_and_tamper(bundle):
    args = {"serial": "test-device", "package": "com.example.test", "selector": {"text": "Save"}}
    assert m.check_observation(bundle, **args)["passed"]
    (bundle.parent / "ui.xml").write_bytes(UI.replace(b"Save", b"Saved"))
    with pytest.raises(m.MobileError, match="hash"):
        m.check_observation(bundle, **args)


@pytest.mark.parametrize("field,value", [("serial", "another-device"),
    ("captured_unix", 0), ("captured_unix", float("nan")), ("captured_unix", True),
    ("captured_unix", time.time() + 3600)])
def test_target_and_freshness(bundle, field, value):
    doc = json.loads(bundle.read_text())
    doc[field] = value
    bundle.write_text(json.dumps(doc))
    with pytest.raises(m.MobileError):
        m.load_observation(bundle, serial="test-device", package="com.example.test")


@pytest.mark.parametrize("selector", [{}, {"text": ""}, {"text": "Sa"}, {"shell": "anything"}])
def test_selector_denies_ambiguous_or_freeform(selector):
    with pytest.raises(m.MobileError):
        m.select(m.parse_ui(UI, "com.example.test"), selector)


def test_duplicate_selector_and_bad_xml():
    nodes = m.parse_ui(UI, "com.example.test")
    with pytest.raises(m.MobileError):
        m.select(nodes + nodes, {"text": "Save"})
    with pytest.raises(m.MobileError):
        m.parse_ui(b'<!DOCTYPE x><hierarchy/>', "com.example.test")
    with pytest.raises(m.MobileError):
        m._png(b'\x89PNG\r\n\x1a\n')


def test_action_requires_authority_before_transport(tmp_path):
    device = m.AndroidDevice.__new__(m.AndroidDevice)
    with pytest.raises(m.MobileError, match="allow_action"):
        device.tap(tmp_path, {"text": "Save"}, {"text": "Saved"})


def test_failed_transport_retains_unknown_intent(bundle, monkeypatch):
    device = m.AndroidDevice.__new__(m.AndroidDevice)
    device.serial, device.package = "test-device", "com.example.test"
    monkeypatch.setattr(device, "observe", lambda root: bundle)
    monkeypatch.setattr(device, "_ui", lambda: UI)
    monkeypatch.setattr(device, "_foreground", lambda: None)
    def fail(*args):
        intent = json.loads((bundle.parent / "action.json").read_text())
        assert intent["state"] == "outcome_unknown"
        raise m.MobileError("transport interrupted")
    monkeypatch.setattr(device, "_run", fail)
    result = device.tap(bundle.parent, {"text": "Save"}, {"text": "Saved"}, allow_action=True)
    assert result["state"] == "outcome_unknown" and result["success"] is False


def test_foreground_wrong_package_rejected(monkeypatch):
    device = m.AndroidDevice.__new__(m.AndroidDevice)
    device.package = "com.example.test"
    monkeypatch.setattr(device, "_run", lambda *args: b'mCurrentFocus=Window{abc u0 com.other.app/.Main}')
    with pytest.raises(m.MobileError):
        device._foreground()


@pytest.mark.parametrize("value", [[], None, {"artifacts": None}, {"artifacts": {"ui": []}}])
def test_malformed_manifest_is_classified(bundle, value):
    if isinstance(value, dict):
        doc = json.loads(bundle.read_text())
        doc.update(value)
        value = doc
    bundle.write_text(json.dumps(value))
    with pytest.raises(m.MobileError):
        m.load_observation(bundle, serial="test-device", package="com.example.test")


def test_slow_pre_dispatch_guard_never_taps(bundle, monkeypatch):
    device = m.AndroidDevice.__new__(m.AndroidDevice)
    device.serial, device.package = "test-device", "com.example.test"
    clock = [0]
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(device, "observe", lambda root: bundle)
    def slow_ui():
        clock[0] = 21
        return UI
    monkeypatch.setattr(device, "_ui", slow_ui)
    monkeypatch.setattr(device, "_foreground", lambda: None)
    calls = []
    monkeypatch.setattr(device, "_run", lambda *args: calls.append(args))
    with pytest.raises(m.MobileError, match="expired"):
        device.tap(bundle.parent, {"text": "Save"}, {"text": "Saved"}, allow_action=True)
    assert not calls and not (bundle.parent / "action.json").exists()


def test_ui_parsed_from_single_hash_checked_read(bundle, monkeypatch):
    original = Path.read_bytes
    reads = []
    def read(path):
        if path.name == "ui.xml":
            reads.append(path)
            if len(reads) > 1:
                return UI.replace(b"Save", b"Wrong")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", read)
    assert m.check_observation(bundle, serial="test-device", package="com.example.test",
                               selector={"text": "Save"})["passed"]
    assert len(reads) == 1
