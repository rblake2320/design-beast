# Event Probe — screen "semantic codec" from OS-native change streams

`python watch/event_probe.py --duration N` records, on one clock, what Windows already knows
about screen change, correlates it into evidence-backed semantic events, and writes an
append-only ledger shaped for Vigil's tamper-evident ledger. **Observe only** — it never
clicks, types, or moves a window.

```
python watch/event_probe.py --duration 90                 # foreground desktop, auto backend
python watch/event_probe.py --duration 60 --screen wgc    # force dirty-region backend
python watch/event_probe.py --duration 60 --screen diff   # force numpy tile-diff fallback
python watch/event_probe.py --duration 60 --disable present   # fault isolation
```

Output: `watch/runs/event-probe-<ts>/` with `events.jsonl` (raw rows), `semantic.jsonl`
(correlated events), `manifest.json` (counts, bytes, coverage), and `evt-*_{before,at,after}.png`
replay frames. The whole `watch/runs/` tree is gitignored — it holds raw frames of the desktop.

## The four streams

| src | what | how | timestamp |
|---|---|---|---|
| `win32` | top-level windows: appeared / vanished / title_changed / moved, with hwnd+pid+title | `EnumWindows` polled every 100 ms | observer (`t_obs_ns`) |
| `uia` | UI Automation events (invoke, menu, text, selection, focus, name/value) with **cached** identity | comtypes event handlers (MTA) | observer |
| `screen` | changed regions per frame | WGC `DirtyRegions` if available, else numpy tile-diff of ring frames | `t_src_ns` (WGC = QPC-based SystemRelativeTime) |
| `present` | frame events (CPU start QPC) per tracked pid | PresentMon service API, no elevation | `t_src_ns` = QPC×100 |
| ring | bounded raw replay frames, SHA-256 each | mss, half-res, worker thread | observer |

## Why win32 AND uia for windows

UIA `WindowClosed` fires with **no identity** — by the time it arrives the element is gone, so
name/pid/bounds are empty (measured 2026-09-04). The win32 table has identity before and after,
because it diffs snapshots. So window open/close come from win32 (identity guaranteed) with the
UIA `WindowOpened`/`WindowClosed` attached as corroboration; other UIA facts (invoke, menu, text,
selection) become their own events. This is why the correlator reads both.

## Correlator rules (strict evidence)

- A win32/UIA fact → `SEMANTIC_EVENT` classified **`observed`**, carrying identity + screen hits
  (dirty rects intersecting the window bounds) + nearest same-pid present event + before/at/after
  replay frame handles.
- "Invoke_Invoked within 400 ms before window_opened" is added as an **`inferred`** block with the
  rule and time window recorded — never merged into the observed fact.
- Text/selection/property storms (a terminal spraying TextChanged) are **coalesced**: first event
  emitted, repeats within 500 ms fold into a `coalesced` count. (Cut 395 → 23 in a 22 s run.)
- A screen change with no semantic fact within ±300 ms is listed as an
  **`unexplained_visual_change`** coverage gap — never explained by a heuristic.

## Clocks (kept separate, never merged silently)

`perf_counter_ns()` == QPC×100 on Windows, so it, PresentMon's `CPU_START_QPC×100`, and WGC's
`SystemRelativeTime` share one domain (WGC callback offset measured −2…+6 ms). UIA and win32 have
no source timestamp — observer time only. Wall clock is anchored once in the manifest.

## Backends

- **wgc** (preferred): `Windows.Graphics.Capture` with `GraphicsCaptureDirtyRegionMode.ReportOnly`
  gives per-composited-frame dirty rectangles in full-res coords with no pixel readback. Needs the
  `winrt-Windows.Foundation.Collections` pywinrt binding to enumerate `Direct3D11CaptureFrame.DirtyRegions`
  (not installed on this box 2026-09-04 → owner decision pending). Requires Windows 11 build 26100+.
- **diff** (fallback): numpy tile-diff of consecutive ring frames. Labelled `diff`; coordinates are
  scaled back to full-res. This IS the frame-diff the blueprint proposed — kept only so the probe
  runs everywhere. Its screen-match window is widened to span ≥2 ring frames.

## Known limits (measured, honest)

- **Ring rate ~7.7 fps, not 60.** `mss` GDI grab of a 5120×2160 desktop is ~134 ms regardless of
  downscale — the grab, not the resize, is the cost. WGC frame-pool readback would give true 60 fps
  but is a bigger build; the ring is a replay buffer, not the perception path, so this is acceptable.
- **present evidence is `none` for window events.** A window opening is not a "present" for that
  process — DWM composites it. PresentMon frame events are the "when" only for continuously-rendering
  apps (games, video). Correct and expected.
- **First open after start has no screen evidence in diff mode** — tile-diff needs a 2-frame baseline.
  WGC reports the first frame's dirty region and would not have this gap.
- **UIA teardown is a heap-corruption trap.** COM callbacks run on RPC threads; releasing the Python
  COMObjects while a callback is in flight corrupts the heap (0xc0000374). The probe stops UIA first
  and drains 0.5 s before tearing down anything else. Do not remove that drain.

## Guarantees

`observe_only: true`, `automation_actions: 0`, `vlm_calls: 0`, `ocr_calls: 0` in every manifest.
`pytest tests/test_event_probe.py` — 12 deterministic correlator/ledger/diff tests; the
`live_desktop`-marked test opens and closes its own Notepad window and asserts both are recovered
with replay evidence (excluded by default; run with `-m live_desktop`).

## Where this goes

design-beast owns the probe (sampling / replay / timing). Vigil remains the canonical
tamper-evident ledger — the JSONL here is shaped to commit through it, its crypto is not duplicated.
See `docs/OPPORTUNITY-LEDGER.md` OPP-20260904-02. Second lane (game/video, `export_mvs` motion
vectors where dirty rects are useless) is separate and not yet built.
