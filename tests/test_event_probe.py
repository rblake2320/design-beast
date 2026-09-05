"""Tests for watch/event_probe.py.

Deterministic tests feed synthetic ledger rows to the real Ledger / Correlator / tile_diff -
no desktop, no mocks of our own code. The live tests (marked `live_desktop`, excluded by
default) drive a real four-stream run whose event source is a Notepad window this test opens
and closes itself.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
sys.path.insert(0, str(REPO / "watch"))
import event_probe as ep  # noqa: E402


# ---------------------------------------------------------------- ledger
def test_ledger_window_is_time_bounded(tmp_path: Path) -> None:
    led = ep.Ledger(tmp_path / "e.jsonl")
    for t in (100, 200, 300, 400):
        led.append({"src": "screen", "t_obs_ns": t, "dirty_rects": [], "dirty_px": 0})
    led.append({"src": "uia", "t_obs_ns": 250, "event": "X"})
    assert [r["t_obs_ns"] for r in led.window("screen", 150, 350)] == [200, 300]
    assert led.window("screen", 500, 600) == []
    assert len(led.window("uia", 0, 1000)) == 1
    led.close()
    reloaded = ep.Ledger.load(tmp_path / "e.jsonl")
    assert len(reloaded.rows) == 5 and len(reloaded.by_src["screen"]) == 4


def test_ledger_counts_bytes_per_source(tmp_path: Path) -> None:
    led = ep.Ledger(tmp_path / "e.jsonl")
    led.append({"src": "uia", "event": "A"})
    led.append({"src": "screen", "dirty_px": 1})
    assert set(led.bytes_by_src) == {"uia", "screen"} and all(v > 0 for v in led.bytes_by_src.values())
    led.close()


# ---------------------------------------------------------------- geometry + diff
def test_intersects() -> None:
    assert ep._intersects([0, 0, 10, 10], [5, 5, 10, 10])
    assert not ep._intersects([0, 0, 10, 10], [20, 20, 5, 5])
    assert not ep._intersects([0, 0, 10, 10], [10, 0, 5, 5])  # touching edge, not overlapping


def test_tile_diff_finds_only_the_changed_tile_in_full_res_coords() -> None:
    import numpy as np
    h = w = 128
    prev = np.zeros((h, w, 4), dtype=np.uint8)
    cur = prev.copy()
    cur[64:96, 32:64] = 255  # one 32x32 block changed, at tile (row 2, col 1)
    rects = ep.tile_diff(prev, cur, tile=32, threshold=6.0, scale=0.5)  # scale 0.5 -> *2 to full res
    assert rects == [[64, 128, 64, 64]]  # x=32*2, y=64*2, w=32*2, h=32*2
    assert ep.tile_diff(prev, prev, tile=32, threshold=6.0, scale=1.0) == []


# ---------------------------------------------------------------- correlator (the heart)
def _fact(src: str, event: str, t: int, **kw: object) -> dict[str, object]:
    return {"src": src, "event": event, "t_obs_ns": t, "schema": ep.SCHEMA_ROW, **kw}


def test_correlator_emits_window_events_from_win32_with_replay_and_screen(tmp_path: Path) -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=100, screen_mode="wgc")
    # a screen change overlapping the window's bounds, just after it opens
    led.append(_fact("win32", "appeared", 1000, hwnd=7, pid=42, app="notepad.exe",
                     title="Untitled - Notepad", bounds=[100, 100, 200, 200]))
    led.append({"src": "screen", "t_obs_ns": 1010, "frame_id": 5, "dirty_rects": [[120, 120, 40, 40]],
                "dirty_px": 1600, "t_src_ns": 1008})
    led.append(_fact("uia", "Window_WindowOpened", 1005, pid=42, name="Untitled - Notepad", runtime_id=[42, 9]))
    corr.tick(2000)  # past window -> emit
    assert len(corr.semantic) == 1
    e = corr.semantic[0]
    assert e["event_type"] == "window_opened" and e["classification"] == "observed"
    assert e["identity"] == {"src": "win32", "hwnd": 7, "pid": 42, "app": "notepad.exe",
                             "title": "Untitled - Notepad", "bounds": [100, 100, 200, 200]}
    assert e["evidence"]["screen"]["coverage"] == "matched" and e["evidence"]["screen"]["hits"][0]["frame_id"] == 5
    assert e["evidence"]["uia"]["coverage"] == "matched" and e["evidence"]["uia"]["count"] == 1


def test_correlator_screen_bounds_filter_excludes_unrelated_change() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=100, screen_mode="wgc")
    led.append(_fact("win32", "appeared", 1000, hwnd=7, pid=42, app="x", title="X", bounds=[0, 0, 50, 50]))
    led.append({"src": "screen", "t_obs_ns": 1010, "frame_id": 5, "dirty_rects": [[900, 900, 40, 40]],  # far away
                "dirty_px": 1600, "t_src_ns": 1008})
    corr.tick(2000)
    assert corr.semantic[0]["evidence"]["screen"]["coverage"] == "none"


def test_correlator_infers_invoke_then_window_opened_with_rule_recorded() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=100, screen_mode="wgc")
    led.append(_fact("uia", "Invoke_Invoked", 1000, pid=42, name="New", bounds=[0, 0, 10, 10]))
    led.append(_fact("win32", "appeared", 1200, hwnd=7, pid=42, app="x", title="Dialog", bounds=[0, 0, 50, 50]))
    corr.tick(3000)
    opened = [e for e in corr.semantic if e["event_type"] == "window_opened"][0]
    assert opened["inferred"]["claim"] == "invoke_then_window_opened"
    assert opened["inferred"]["classification"] == "inferred" and "400 ms" in opened["inferred"]["rule"]


def test_correlator_does_not_infer_when_invoke_is_too_old() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=100, screen_mode="wgc")
    led.append(_fact("uia", "Invoke_Invoked", 1000, pid=42, name="New"))
    led.append(_fact("win32", "appeared", 1000 + 500 * ep.NS, hwnd=7, pid=42, app="x", title="D", bounds=[0, 0, 5, 5]))
    corr.tick(10 ** 12)
    assert "inferred" not in [e for e in corr.semantic if e["event_type"] == "window_opened"][0]


def test_correlator_coalesces_text_storm_into_one_event() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=100, coalesce_ns=500 * ep.NS, screen_mode="wgc")
    base = 1_000_000
    for i in range(50):  # a terminal spraying TextChanged every 10 ms
        led.append(_fact("uia", "Text_TextChanged", base + i * 10 * ep.NS, pid=99, runtime_id=[1, 2], name="term"))
    corr.tick(base + 100 * ep.NS)  # first one is old enough to emit; rest arrive within coalesce window
    corr.flush()
    text_events = [e for e in corr.semantic if e["event_type"] == "text_changed"]
    assert len(text_events) == 1, [e["event_id"] for e in text_events]
    assert text_events[0]["coalesced"] >= 40 and corr.coalesced_count >= 40


def test_correlator_present_hit_picks_nearest_same_pid() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, window_ns=300 * ep.NS, screen_mode="wgc")
    led.append(_fact("win32", "appeared", 1000 * ep.NS, hwnd=7, pid=42, app="game.exe",
                     title="Game", bounds=[0, 0, 5, 5]))
    led.append({"src": "present", "t_obs_ns": 1050 * ep.NS, "t_src_ns": 1050 * ep.NS, "pid": 42, "app": "game.exe"})
    led.append({"src": "present", "t_obs_ns": 1200 * ep.NS, "t_src_ns": 1200 * ep.NS, "pid": 99, "app": "other"})
    corr.tick(10 ** 15)
    p = corr.semantic[0]["evidence"]["present"]
    assert p["pid"] == 42 and p["delta_ms"] == 50.0


def test_unexplained_changes_flag_only_screen_without_nearby_fact() -> None:
    led = ep.Ledger(None)
    corr = ep.Correlator(led, None, None, screen_mode="wgc")
    led.append(_fact("uia", "FocusChanged", 1000 * ep.NS, pid=1))
    led.append({"src": "screen", "t_obs_ns": 1050 * ep.NS, "frame_id": 1, "dirty_rects": [[0, 0, 4, 4]], "dirty_px": 999999})
    led.append({"src": "screen", "t_obs_ns": 9000 * ep.NS, "frame_id": 2, "dirty_rects": [[0, 0, 4, 4]], "dirty_px": 999999})
    gaps = corr.unexplained_changes(min_px=1000)
    assert [g["frame_id"] for g in gaps] == [2]  # frame 1 is explained by the nearby focus fact
    assert gaps[0]["event_type"] == "unexplained_visual_change" and gaps[0]["classification"] == "observed"


# ---------------------------------------------------------------- win32 helpers (live but read-only)
def test_window_table_snapshot_reads_real_windows() -> None:
    led = ep.Ledger(None)
    wt = ep.WindowTableStream(led)
    snap = wt.snapshot()
    assert isinstance(snap, dict)
    for d in snap.values():
        assert d["pid"] > 0 and isinstance(d["title"], str) and len(d["bounds"]) == 4


# ---------------------------------------------------------------- live four-stream run
@pytest.mark.live_desktop
def test_live_probe_recovers_window_open_and_close(tmp_path: Path) -> None:
    """Opens a Notepad window, closes it, and asserts the probe recovered both with replay evidence.

    This test IS the event driver - it performs the only desktop actions; the probe observes.
    """
    import ctypes
    import ctypes.wintypes as cwt
    import subprocess
    import threading

    u32 = ctypes.windll.user32

    def untitled() -> set[int]:
        out: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, cwt.HWND, cwt.LPARAM)
        def cb(h, _):
            if u32.IsWindowVisible(h):
                n = u32.GetWindowTextLengthW(h)
                b = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(h, b, n + 1)
                if b.value == "Untitled - Notepad":
                    out.append(h)
            return True

        u32.EnumWindows(cb, 0)
        return set(out)

    result: dict[str, object] = {}

    def drive() -> None:
        time.sleep(5)
        before = untitled()
        subprocess.Popen(["notepad.exe"])
        time.sleep(3.5)
        for h in untitled() - before:
            u32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
        time.sleep(2.5)

    driver = threading.Thread(target=drive)
    driver.start()
    manifest = ep.run(duration=13, out_dir=tmp_path / "run", ring_fps=8, screen="diff", printer=None)
    driver.join()

    assert manifest["observe_only"] and manifest["automation_actions"] == 0 and manifest["vlm_calls"] == 0
    sem = [json.loads(l) for l in (tmp_path / "run" / "semantic.jsonl").read_text(encoding="utf-8").splitlines()]
    notepad = [e for e in sem if e["identity"].get("pid") and "Notepad" in str(e["identity"].get("title") or "")]
    opened = [e for e in notepad if e["event_type"] == "window_opened"]
    closed = [e for e in notepad if e["event_type"] == "window_closed"]
    assert opened, "no Notepad window_opened recovered"
    assert closed, "no Notepad window_closed recovered"
    # every recovered window event carries identity + a replay handle into the raw ring
    for e in opened + closed:
        assert e["identity"]["pid"] > 0 and e["identity"]["title"]
        assert e["evidence"]["replay"].get("at"), "no replay frame at the event"
    assert manifest["emit_latency_ms"]["median"] < 400
