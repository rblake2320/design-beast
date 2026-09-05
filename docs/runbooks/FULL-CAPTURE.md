# Full-Watching Capture — real footage for the semantic-codec loop

`python watch/full_capture.py --duration N` captures the **real desktop** at the source frame
rate and encodes it with the GPU's hardware H.264/H.265 encoder. Unlike event_probe's mss replay
ring (~7.7 fps at 5K — a provable slideshow), this is actual footage whose visuals are, by
construction, the true UI. Output: `watch/runs/full-capture-<ts>/capture.mp4` + `frames.jsonl` +
`manifest.json`. **Observe only** — it never drives the UI. `watch/runs/` is gitignored.

```
python watch/full_capture.py --duration 30                     # semantic, dxcam, half-res
python watch/full_capture.py --duration 30 --mode continuous   # every frame (encode-bound)
python watch/full_capture.py --scale 1.0 --codec hevc_nvenc    # native res, HEVC
python watch/full_capture.py --backend wgc                     # follow-up (install-gated)
```

## How it works

- **Backend** (pluggable): `dxcam` — DXGI Desktop Duplication, measured **59.8 fps at 5120×2160**,
  already installed, zero cost. `wgc` — `windows-capture` (WGC, single backend shared with
  event_probe), behind `--backend`, install-gated per owner rule; a declared follow-up.
- **Decoupled capture/encode**: a capture thread grabs + stamps + gates at the source rate into a
  bounded queue (max 8); the encoder drains it. NVENC is slower than capture, so on backpressure
  the queue drops the **oldest** pending frame (recorded as `dropped_backpressure`) — the video
  stays real-time. This is the blueprint's bounded-queue rule.
- **Semantic gate**: each polled frame is diffed on a **coarse ~320px grid** (a full-res diff
  capped idle polling at ~25 fps; coarse restores ~58). `continuous` encodes every delivered
  frame; `semantic` encodes only frames that changed (≥ `--change-threshold`) or that an external
  `keep_active(t_obs_ns)` callback forces — so a static screen costs ≈ nothing and a change is
  never missed. Measured idle: 58 fps poll, **0.85 %** encoded.
- **Encoder**: PyAV → NVENC. H.264 NVENC caps at **4096 wide**, so `--codec auto` picks
  `hevc_nvenc` for wider (native 5120) and `h264_nvenc` otherwise. yuv420p, VFR.
- **Clock / the assembler bridge**: every frame is stamped `perf_counter_ns` (== QPC×100 — the
  SAME domain as event_probe's uia/win32/present/wgc streams). `frames.jsonl` maps
  `frame_idx → pts_ms → t_obs_ns → wall_ns`. So a semantic event's `t_obs_ns` resolves to an exact
  video PTS via `frame_at(ledger, t_obs_ns)` — this is what lets generated narration sync to the
  real footage in the next milestone.

## Measured (this box, 2026-09-04, RTX 5090, 5120×2160)

- dxcam ceiling 59.8 fps; semantic-idle sustained 58.4 fps poll, 0.85 % encoded.
- Continuous is **encode-bound ~20 fps** at 2560×1080 h264_nvenc (NVENC + CPU colorspace-convert
  under the GIL). Semantic mode is the intended path; drop `--scale` or resolution for faster
  continuous.
- mp4 verified by **PyAV and ffprobe**: 160 frames, 2560×1080 h264_nvenc, decoded span
  0.03..8.00 s matching the ledger, SHA-256 recorded. Compression ~0.0002 of raw BGRA.
- Event→frame bridge exact (0.0 ms) in tests.

## Gotchas (measured, do not relearn)

- **mp4 time_base**: set `stream.codec_context.time_base = Fraction(1,1000)`, not just
  `stream.time_base` — with only the latter, `rate=60` governs and an 8 s clip decodes as 133 s.
- **Do NOT set `frame.time_base`** per frame — the mp4 muxer rescales from the stream and rejects
  the flushed packets with EINVAL (returned 22).
- dxcam (DDA) can't capture DRM/HDCP-protected windows (they go black); that's the reason the wgc
  backend exists as a follow-up.

## Guarantees / tests

`observe_only: true` in every manifest. `pytest tests/test_full_capture.py` — 7 deterministic
(scripted backend for the gate, real NVENC encode → decodable mp4 with correct ms-PTS duration,
frame bridge, H.264 width-cap → HEVC selection, wgc install gate) + 1 `live_desktop` dxcam run
(excluded by default; `-m live_desktop`). Ledger OPP-20260904-03.
