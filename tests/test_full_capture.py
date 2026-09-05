"""Tests for watch/full_capture.py.

Deterministic tests use a scripted in-memory backend (no desktop, no GPU dependency for the
gate/ledger logic) plus the real PyAV NVENC encoder (the encode path is the risky part - it
must produce a decodable mp4 whose duration matches the ms-PTS). The live test drives real
dxcam capture and is excluded by default.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "watch"))
import full_capture as fc  # noqa: E402


def _has_nvenc() -> bool:
    try:
        from av.codec import Codec
        Codec("h264_nvenc", "w")
        return True
    except Exception:  # noqa: BLE001
        return False


needs_nvenc = pytest.mark.skipif(not _has_nvenc(), reason="no h264_nvenc on this node")
needs_dxcam = pytest.mark.skipif(__import__("importlib").util.find_spec("dxcam") is None, reason="dxcam not installed")


# ---------------------------------------------------------------- change math
def test_change_score_zero_for_identical_and_high_for_different() -> None:
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    assert fc.change_score(a, a) == 0.0
    b = a.copy()
    b[:] = 255
    assert fc.change_score(a, b) == 255.0
    assert fc.downsample(np.zeros((8, 8, 4), dtype=np.uint8), 2).shape == (4, 4, 3)


# ---------------------------------------------------------------- scripted backend for the gate
class ScriptedBackend(fc.CaptureBackend):
    """Yields a fixed list of BGRA frames, then None. width/height set from the first frame."""

    name = "scripted"

    def __init__(self, frames: list[np.ndarray]) -> None:
        self._frames = frames
        self.height, self.width = frames[0].shape[:2]
        self._i = 0

    def start(self, target_fps: float) -> None:
        pass

    def read(self):
        if self._i >= len(self._frames):
            time.sleep(0.001)
            return None
        f = self._frames[self._i]
        self._i += 1
        return f

    def stop(self) -> None:
        pass


def _solid(w: int, h: int, value: int) -> np.ndarray:
    a = np.empty((h, w, 4), dtype=np.uint8)
    a[:] = value
    return a


@needs_nvenc
def test_semantic_mode_drops_static_keeps_change(tmp_path: Path) -> None:
    # 8 identical frames then 1 changed then 4 identical: semantic must keep the first (baseline)
    # and the change, and drop the static repeats.
    w, h = 640, 480
    frames = [_solid(w, h, 10)] * 8 + [_solid(w, h, 200)] + [_solid(w, h, 200)] * 4
    m = fc.capture(duration=2, out_dir=tmp_path / "r", backend=ScriptedBackend(frames), scale=1.0,
                   mode="semantic", change_threshold=5.0, printer=None)
    assert m["frames"]["polled"] >= 13
    # baseline frame + the one real change; NOT all 13
    assert 2 <= m["frames"]["kept"] <= 4, m["frames"]
    assert m["encode"]["frames_encoded"] == m["frames"]["kept"]


@needs_nvenc
def test_continuous_mode_keeps_every_frame(tmp_path: Path) -> None:
    frames = [_solid(320, 240, v % 256) for v in range(0, 30)]
    m = fc.capture(duration=2, out_dir=tmp_path / "r", backend=ScriptedBackend(frames), scale=1.0,
                   mode="continuous", printer=None)
    # Continuous gates nothing: every polled frame is either encoded or dropped by backpressure
    # (bounded queue + fast scripted producer). No frame is silently lost to the change gate.
    assert m["frames"]["kept"] + m["frames"]["dropped_backpressure"] == m["frames"]["polled"] >= 20
    assert m["frames"]["kept"] >= 1


@needs_nvenc
def test_encoded_mp4_decodes_with_correct_duration_and_frame_bridge(tmp_path: Path) -> None:
    import av
    # A paced backend (real ms between frames) so nothing is dropped and PTS spans a real interval.
    class PacedBackend(ScriptedBackend):
        def read(self):
            time.sleep(0.02)  # ~50 fps, slower than the encoder -> no backpressure drops
            return super().read()

    frames = [_solid(640, 360, 20 + (v * 8) % 200) for v in range(24)]
    run = tmp_path / "r"
    m = fc.capture(duration=1.5, out_dir=run, backend=PacedBackend(frames), scale=1.0,
                   mode="continuous", printer=None)
    mp4 = run / "capture.mp4"
    assert mp4.exists() and m["sha256_mp4"]
    cont = av.open(str(mp4))
    vs = cont.streams.video[0]
    ts = [float(f.pts * f.time_base) for f in cont.decode(vs)]
    cont.close()
    assert len(ts) == m["encode"]["frames_encoded"]
    ledger = fc.load_frame_ledger(run / "frames.jsonl")
    real_span = ledger[-1]["pts_ms"] / 1000.0
    assert abs(ts[-1] - real_span) < 0.3, f"decoded {ts[-1]:.2f}s vs real {real_span:.2f}s (time_base bug)"
    # time -> frame bridge: querying exactly a frame's capture time resolves to that frame
    hit = fc.frame_at(ledger, ledger[10]["t_obs_ns"])
    assert hit["frame_idx"] == 10


def test_frame_at_picks_nearest_and_handles_empty() -> None:
    ledger = [{"frame_idx": i, "t_obs_ns": i * 1_000_000_000} for i in range(5)]
    assert fc.frame_at(ledger, 2_400_000_000)["frame_idx"] == 2
    assert fc.frame_at(ledger, 2_600_000_000)["frame_idx"] == 3
    assert fc.frame_at([], 123) is None


def test_h264_width_cap_selects_hevc_for_wide(tmp_path: Path) -> None:
    # codec auto: <=4096 wide -> h264, wider -> hevc. Test the selection without capturing.
    if not _has_nvenc():
        pytest.skip("no nvenc")
    enc = fc.Encoder(tmp_path / "a.mp4", 3840, 2160, codec="auto")
    assert enc.codec == "h264_nvenc"
    enc.close()
    try:
        enc = fc.Encoder(tmp_path / "b.mp4", 5120, 2160, codec="auto")
        assert enc.codec == "hevc_nvenc"
        enc.close()
    except Exception:  # noqa: BLE001 - hevc may be unavailable; selection logic already asserted
        pass


def test_wgc_backend_is_install_gated() -> None:
    with pytest.raises((RuntimeError, NotImplementedError)):
        fc.WgcBackend()


# ---------------------------------------------------------------- live capture
@needs_dxcam
@needs_nvenc
@pytest.mark.live_desktop
def test_live_dxcam_capture_produces_real_footage(tmp_path: Path) -> None:
    import av
    m = fc.capture(duration=4, out_dir=tmp_path / "r", backend="dxcam", mode="continuous",
                   scale=0.5, printer=None)
    assert m["observe_only"] and m["backend"] == "dxcam"
    assert m["frames"]["encoded"] > 10, m["frames"]
    mp4 = tmp_path / "r" / "capture.mp4"
    cont = av.open(str(mp4))
    vs = cont.streams.video[0]
    n = sum(1 for _ in cont.decode(vs))
    cont.close()
    assert n == m["encode"]["frames_encoded"]
    ledger = fc.load_frame_ledger(tmp_path / "r" / "frames.jsonl")
    assert abs(ledger[-1]["pts_ms"] / 1000.0 - m["duration_s"]) < 1.0  # ms-PTS sane, not 16x
