"""Full-watching capture - real desktop footage at true frame rate, for the semantic-codec loop.

The replay ring in event_probe.py uses mss (~7.7 fps at 5K) - a slideshow you can prove from,
not footage. This module captures the REAL desktop continuously and encodes it with the GPU's
hardware H.264/H.265 encoder, so the "video" step of the loop has actual footage whose visuals
are, by construction, the true UI.

Design:
  backend   pluggable frame source. `dxcam` (DXGI Desktop Duplication, ~156 fps at 5K on this
            box, zero install) is implemented now; `wgc` (windows_capture / Windows.Graphics.
            Capture, single backend shared with event_probe) is behind --backend, install-gated.
  clock     every frame is stamped time.perf_counter_ns() == QPC*100 - the SAME domain as
            event_probe's uia/win32/present/wgc streams - so a semantic event's t_obs_ns maps to
            an exact video PTS with no cross-library timing reconciliation.
  encode    PyAV -> NVENC. H.264 NVENC caps at 4096 wide, so native 5120 desktops auto-fall back
            to HEVC (or downscale). Measured on this box: h264_nvenc 2560x1080 ~43 enc-fps,
            hevc_nvenc 5120x2160 ~19 enc-fps.
  gating    'continuous' encodes every frame at target fps. 'semantic' keeps full rate while the
            screen is changing or an external event window is active, and drops static stretches
            (variable PTS) - "semantic FPS" applied to recording, so a long idle costs ~nothing.
  ledger    frames.jsonl maps frame_idx -> pts_ms -> t_obs_ns -> wall_ns (+ kept/trigger). This is
            the bridge the assembler needs to sync generated narration to the real footage.

Nothing here drives the UI; it only records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

NS = 1_000_000
H264_MAX_WIDTH = 4096  # NVENC H.264 hard cap; wider must use HEVC or downscale


def now_ns() -> int:
    return time.perf_counter_ns()


# ------------------------------------------------------------------ backends
@dataclass
class Frame:
    idx: int
    t_obs_ns: int
    bgra: np.ndarray  # HxWx4 uint8, BGRA (dxcam / WGC native order)


class CaptureBackend:
    name = "base"
    width = 0
    height = 0

    def start(self, target_fps: float) -> None: ...
    def read(self) -> np.ndarray | None: ...  # latest BGRA frame, or None if none yet
    def stop(self) -> None: ...


class DxcamBackend(CaptureBackend):
    """DXGI Desktop Duplication via dxcam. Fast, zero install. Cannot capture DRM/HDCP content."""

    name = "dxcam"

    def __init__(self, output_idx: int = 0) -> None:
        import dxcam
        self._cam = dxcam.create(output_idx=output_idx, output_color="BGRA")
        self.width, self.height = self._cam.width, self._cam.height

    def start(self, target_fps: float) -> None:
        # video_mode duplicates the last frame when nothing changed, giving a steady cadence so the
        # encoder gets real wall-clock timing (semantic gating still drops the duplicates).
        self._cam.start(target_fps=int(round(target_fps)), video_mode=True)

    def read(self) -> np.ndarray | None:
        return self._cam.get_latest_frame()

    def stop(self) -> None:
        try:
            self._cam.stop()
        except Exception:  # noqa: BLE001
            pass
        del self._cam  # dxcam frees the duplicator on GC; no module-level clean_up in this version


class WgcBackend(CaptureBackend):
    """Windows.Graphics.Capture via the `windows-capture` package - single backend shared with
    event_probe's frame pool. Install-gated by owner rule; raises a clear message if absent."""

    name = "wgc"

    def __init__(self, monitor_index: int = 1) -> None:
        try:
            from windows_capture import WindowsCapture  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("wgc backend needs `pip install windows-capture` (owner-gated); "
                               "use --backend dxcam for the proven path") from exc
        raise NotImplementedError("wgc backend is a declared follow-up; dxcam is the built path")


def make_backend(name: str) -> CaptureBackend:
    if name == "dxcam":
        return DxcamBackend()
    if name == "wgc":
        return WgcBackend()
    raise ValueError(f"unknown backend {name!r}")


# ------------------------------------------------------------------ change gate
def downsample(bgra: np.ndarray, step: int) -> np.ndarray:
    return bgra[::step, ::step, :3]


def change_score(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute BGR difference on already-downsampled frames (0..255)."""
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


# ------------------------------------------------------------------ encoder
class Encoder:
    """PyAV NVENC encoder. Variable-PTS: each frame carries its real wall-time offset (ms), so
    dropped-static stretches compress to nothing while kept frames keep true timing."""

    def __init__(self, path: Path, width: int, height: int, *, codec: str = "auto",
                 quality: int = 24) -> None:
        import av
        self._av = av
        if codec == "auto":
            codec = "h264_nvenc" if width <= H264_MAX_WIDTH else "hevc_nvenc"
        self.codec = codec
        self.container = av.open(str(path), "w")
        self.stream = self.container.add_stream(codec, rate=60)
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        # The CODEC time_base is what the mp4 muxer rescales packet PTS from. Setting only
        # stream.time_base leaves rate=60 governing (an 8 s clip decoded as 133 s). Set both to ms.
        self.stream.time_base = Fraction(1, 1000)
        self.stream.codec_context.time_base = Fraction(1, 1000)  # milliseconds - real VFR timing
        opts = {"rc": "vbr", "cq": str(quality)}
        if "nvenc" in codec:
            opts["preset"] = "p4"
        self.stream.options = opts
        self.frames_encoded = 0
        self._last_pts = -1

    def encode(self, bgr_or_bgra: np.ndarray, pts_ms: int) -> None:
        arr = bgr_or_bgra
        fmt = "bgra" if arr.shape[2] == 4 else "bgr24"
        frame = self._av.VideoFrame.from_ndarray(np.ascontiguousarray(arr), format=fmt)
        frame = frame.reformat(format="yuv420p")
        frame.pts = max(pts_ms, self._last_pts + 1)  # PTS must strictly increase, in stream.time_base (ms)
        self._last_pts = frame.pts
        # NB: do NOT set frame.time_base - the mp4 muxer rescales from stream.time_base, and a
        # per-frame time_base makes mux() reject the flushed packets with EINVAL (isolated 2026-09-04).
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.frames_encoded += 1

    def close(self) -> dict[str, Any]:
        for packet in self.stream.encode():  # flush
            self.container.mux(packet)
        self.container.close()
        return {"codec": self.codec, "frames_encoded": self.frames_encoded}


# ------------------------------------------------------------------ capture loop
def capture(*, duration: float, out_dir: Path, backend: "str | CaptureBackend" = "dxcam", target_fps: float = 60.0,
            scale: float = 0.5, mode: str = "semantic", change_threshold: float = 2.0,
            keep_active: Callable[[int], bool] | None = None, codec: str = "auto",
            quality: int = 24, printer: Callable[[str], None] | None = print) -> dict[str, Any]:
    """Record `duration` s of the real desktop to out_dir/capture.mp4 + frames.jsonl.

    mode 'continuous' encodes every polled frame; 'semantic' encodes only frames where the screen
    changed (>= change_threshold) or keep_active(t_obs_ns) is True, dropping static stretches.
    keep_active lets an external event source (event_probe) force full-rate windows.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    src = backend if isinstance(backend, CaptureBackend) else make_backend(backend)
    backend_name = src.name
    step = max(1, int(round(1.0 / scale)))
    # Change detection runs every polled frame, so it must be cheap: diff a COARSE grid (~320px wide),
    # not the encode-res frame. A full 2560x1080 diff was ~12 ms and capped idle polling at ~25 fps.
    gate_step = max(step, src.width // 320)
    enc_w = (src.width // step) & ~1  # even dims required by yuv420p
    enc_h = (src.height // step) & ~1
    encoder = Encoder(out_dir / "capture.mp4", enc_w, enc_h, codec=codec, quality=quality)
    frames_fh = (out_dir / "frames.jsonl").open("w", encoding="utf-8")

    import queue as _queue
    started_perf, started_wall = now_ns(), time.time_ns()

    # Capture and encode are decoupled: the capture thread grabs + stamps + gates at the source rate
    # (dxcam ~60 fps here) into a bounded queue; the encoder drains it. NVENC is slower than capture,
    # so on backpressure the queue drops the OLDEST pending frame - the video stays real-time and the
    # gate guarantees changed frames are prioritised. This is the blueprint's bounded-queue rule.
    q: _queue.Queue[tuple[int, np.ndarray, float, bool] | None] = _queue.Queue(maxsize=8)
    stats = {"polled": 0, "dropped_backpressure": 0}
    stop = threading.Event()

    def capture_thread() -> None:
        prev_small: np.ndarray | None = None
        end = time.time() + duration
        while not stop.is_set() and time.time() < end:
            raw = src.read()
            if raw is None:
                time.sleep(0.001)
                continue
            t_obs = now_ns()
            stats["polled"] += 1
            small = downsample(raw, gate_step)
            score = 255.0 if prev_small is None or prev_small.shape != small.shape else change_score(prev_small, small)
            prev_small = small
            forced = keep_active(t_obs) if keep_active else False
            if not (mode == "continuous" or score >= change_threshold or forced):
                continue
            frame = np.ascontiguousarray(raw[::step, ::step, :][:enc_h, :enc_w, :])
            try:
                q.put_nowait((t_obs, frame, score, forced))
            except _queue.Full:
                try:
                    q.get_nowait()  # drop oldest, keep newest
                    stats["dropped_backpressure"] += 1
                    q.put_nowait((t_obs, frame, score, forced))
                except _queue.Empty:
                    pass
        q.put(None)

    if printer:
        printer(f"[capture] {backend} {src.width}x{src.height} -> encode {enc_w}x{enc_h} "
                f"{encoder.codec} mode={mode} for {duration:.0f}s")
    src.start(target_fps)
    worker = threading.Thread(target=capture_thread, name="capture", daemon=True)
    worker.start()
    kept = 0
    try:
        while True:
            item = q.get()
            if item is None:
                break
            t_obs, frame, score, forced = item
            pts_ms = (t_obs - started_perf) // NS
            encoder.encode(frame, pts_ms)
            kept += 1
            frames_fh.write(json.dumps({
                "frame_idx": encoder.frames_encoded - 1, "pts_ms": pts_ms, "t_obs_ns": t_obs,
                "wall_ns": started_wall + (t_obs - started_perf), "change_score": round(score, 2),
                "trigger": "continuous" if mode == "continuous" else ("event" if forced else "change"),
            }, separators=(",", ":")) + "\n")
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        worker.join(timeout=3)
        src.stop()
        enc_info = encoder.close()
        frames_fh.close()

    polled = stats["polled"]
    elapsed = (now_ns() - started_perf) / 1e9
    mp4 = out_dir / "capture.mp4"
    mp4_bytes = mp4.stat().st_size if mp4.exists() else 0
    raw_equiv = polled * src.width * src.height * 4  # if every polled frame were stored raw BGRA
    manifest = {
        "schema": "beast.full-capture/v1", "run_dir": str(out_dir), "observe_only": True,
        "backend": backend_name, "source_size": [src.width, src.height], "encode_size": [enc_w, enc_h],
        "scale": scale, "mode": mode, "change_threshold": change_threshold,
        "clock": {"perf_ns_at_start": started_perf, "wall_ns_at_start": started_wall,
                  "note": "frame t_obs_ns == QPC*100, same domain as event_probe streams"},
        "duration_s": round(elapsed, 2),
        "frames": {"polled": polled, "kept": kept, "encoded": enc_info["frames_encoded"],
                   "dropped_backpressure": stats["dropped_backpressure"],
                   "poll_fps": round(polled / elapsed, 1), "kept_fps": round(kept / elapsed, 1),
                   "kept_fraction": round(kept / polled, 4) if polled else None},
        "encode": {**enc_info, "mp4_bytes": mp4_bytes,
                   "raw_bgra_equiv_bytes": raw_equiv,
                   "compression_vs_raw": round(mp4_bytes / raw_equiv, 6) if raw_equiv else None,
                   "bytes_per_second": int(mp4_bytes / elapsed) if elapsed else 0},
        "sha256_mp4": _sha256(mp4) if mp4_bytes else None,
        "files": {"video": "capture.mp4", "frame_ledger": "frames.jsonl"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if printer:
        printer(json.dumps({k: manifest[k] for k in ("frames", "encode", "duration_s")}, indent=2))
    return manifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ time <-> frame bridge (for the assembler)
def load_frame_ledger(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def frame_at(ledger: list[dict[str, Any]], t_obs_ns: int) -> dict[str, Any] | None:
    """The encoded frame whose capture time is nearest t_obs_ns - maps a semantic event to a video PTS."""
    if not ledger:
        return None
    return min(ledger, key=lambda r: abs(r["t_obs_ns"] - t_obs_ns))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--backend", choices=["dxcam", "wgc"], default="dxcam")
    ap.add_argument("--target-fps", type=float, default=60.0)
    ap.add_argument("--scale", type=float, default=0.5, help="integer-stride downscale (0.5 -> half)")
    ap.add_argument("--mode", choices=["semantic", "continuous"], default="semantic")
    ap.add_argument("--change-threshold", type=float, default=2.0)
    ap.add_argument("--codec", choices=["auto", "h264_nvenc", "hevc_nvenc", "libx264"], default="auto")
    ap.add_argument("--quality", type=int, default=24)
    args = ap.parse_args(argv)
    from pathlib import Path as _P
    repo = _P(__file__).resolve().parents[1]
    out = args.out or repo / "watch" / "runs" / f"full-capture-{time.strftime('%Y%m%d-%H%M%S')}"
    m = capture(duration=args.duration, out_dir=out, backend=args.backend, target_fps=args.target_fps,
                scale=args.scale, mode=args.mode, change_threshold=args.change_threshold,
                codec=args.codec, quality=args.quality)
    return 0 if m["encode"]["frames_encoded"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
