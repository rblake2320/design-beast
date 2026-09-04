# Perf Monitor — live FPS + GPU thermals

`python scripts/perf_monitor.py` samples the lanes below on one clock and writes one JSONL
line per sample (schema `beast.perf-sample/v2`) to `session/perf/<ts>.jsonl`.

| Lane | Source | Fields |
|---|---|---|
| `gpu` | `nvidia-smi` (ships with the driver) | temp_c, mem_temp_c, **fan_pct**, util_pct, mem_util_pct, clock_gr_mhz, clock_mem_mhz, power_w, power_limit_w, vram_used/total_mib, pstate, throttle_reasons |
| `fps` | PresentMon (service backend preferred, console fallback) | per target: app, pid, frames, avg_fps, avg_frame_ms, low1_fps, max_frame_ms, dropped — service backend adds presented_fps, displayed_fps, display_latency_ms, gpu_busy_ms, present_mode |
| `gpu_svc` | PresentMon service | temp_c, power_w, power_limit_w, clock_gr_mhz, clock_mem_mhz, util_pct, vram_used_mib — independent cross-check of the `gpu` lane (no fan on NVIDIA) |

```
python scripts/perf_monitor.py                              # foreground window, until Ctrl+C
python scripts/perf_monitor.py --process RouteRush.exe --duration 120
python scripts/perf_monitor.py --pid 1980 --interval 0.5
python scripts/perf_monitor.py --no-fps --interval 2        # thermals only
```

Console line per sample:

```
16:40:35 | GPU 53C fan 0% util 10% 1642MHz 72.34W VRAM 14585/32607MiB | dwm.exe:1980 164.1fps (1%low 80.2, max 12.6ms) drop 0 lat 11.3ms
```

## Backends (why there are two)

**service** — `studio/presentmon_api.py` drives `PresentMonAPI2` (SDK loader DLL + header
installed by `winget install Intel.PresentMon`) against the **PresentMon Shared Service**,
which runs as SYSTEM and owns the ETW trace. Any user-mode client gets per-frame events and
windowed stats over its pipe — **no elevation, no group membership**. Enum values are parsed
from the installed header so they match the installed service.

**console** — `PresentMon-<ver>-x64.exe --output_stdout`, header-driven CSV reducer. Opens
its own ETW trace, so it needs elevation or the local **Performance Log Users** group;
otherwise `failed to start trace session: access denied`. One-time fix (elevated, then sign
out/in): `net localgroup "Performance Log Users" %USERNAME% /add`. Only used when the
service API is missing; `--fps-backend console` forces it.

`scripts/doctor.py` reports `PresentMon service API` (OK/WARN) and, only when the service is
unavailable, `PresentMon console privilege`.

## Truthfulness rules baked in

- **No frames → no stats.** The service echoes the last real process's windowed averages
  for pids that never presented (observed 2026-09-04: idle chrome pids reported the
  terminal's 19.85 fps). The lane consumes frame *events* per pid and only attaches the
  windowed stats when ≥ 1 frame arrived in the window.
- **Warm-up is visible, not hidden.** The first sample window after a pid starts being
  tracked is usually empty (`no frames`); frames flow from the next window. A run of
  `--duration N` therefore yields about N-1 populated windows.
- `1 % low` = 1000 / mean frame time of the slowest 1 % of frames in the window (same
  reducer for both backends: `reduce_frame_times`).
- Console reducer frame-time source order: `FrameTime` → `MsBetweenPresents` (1.x) →
  `MsCPUBusy + MsCPUWait` (2.x) → consecutive `CPUStartTime` delta. Dropped = `Dropped == 1`
  or `DisplayedTime == NA`.
- Never terminates a user process (`automatic_process_termination: false`; the only
  process it stops is its own console-PresentMon child).
- Exit 0 when at least one lane produced data, 2 when both were unavailable.

## Evidence (this box, 2026-09-04, RTX 5090, PresentMon 2.5.1 / API 3.3.0)

- **Measured:** non-elevated Python opened a service session; `dwm.exe` 164.06 presented /
  164.05 displayed fps (165 Hz panel), frame p99 8.0 ms, display latency 11.3 ms;
  `WindowsTerminal.exe` 19.85 fps. GPU via service: 53 °C, 73.8 W, 1663 MHz, 11.75 % util —
  matching `nvidia-smi` (53 °C, 72–74 W) in the same second.
- **Measured:** service rejects on NVIDIA: `GPU_FAN_SPEED*`, `GPU_CARD_POWER`,
  `GPU_EFFECTIVE_FREQUENCY`, `GPU_MEM_TEMPERATURE`, `GPU_VOLTAGE`, `*_LIMITED`, all `CPU_*`
  telemetry, `DROPPED_FRAMES` with COUNT/NON_ZERO_AVG. Registration drops rejected elements
  individually and records them in `fps_lane.rejected_metrics`.
- **Verified:** `pytest tests/test_perf_monitor.py` — parsers on verbatim rows, live
  nvidia-smi, live service session/query/frame events, end-to-end monitor run, CLI run.
- Console backend on this box: **observed** `access denied` (user not in Performance Log
  Users); its CSV reducer is verified against README column sets, not a live capture.
