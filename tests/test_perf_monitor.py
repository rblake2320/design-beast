"""Real-path tests for studio/perf_monitor.py + studio/presentmon_api.py - no mocks.

Parser tests use rows captured verbatim from this box (RTX 5090, nvidia-smi 2026-09-04) and
the PresentMon column sets from the official README. Live tests drive the real binaries /
service and skip only when they are absent from the node (doctor reports that separately).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
import perf_monitor  # noqa: E402
import presentmon_api as pm  # noqa: E402

REAL_ROW = ("2026/09/04 16:40:35.829, NVIDIA GeForce RTX 5090, 53, N/A, 0, 10, 3, 1642, 7001, "
            "72.34, 600.00, 14585, 32607, P3, 0x0000000000000000")


def _service_available() -> bool:
    if pm.find_dll() is None or pm.find_header() is None:
        return False
    try:
        with pm.Session():
            return True
    except (OSError, pm.PresentMonError):
        return False


needs_service = pytest.mark.skipif(not _service_available(), reason="PresentMon service API unavailable")
needs_nvsmi = pytest.mark.skipif(shutil.which("nvidia-smi") is None, reason="no nvidia-smi on this node")


# ---------------------------------------------------------------- gpu lane parser
def test_parse_gpu_row_matches_real_nvidia_smi_output() -> None:
    g = perf_monitor.parse_gpu_row(REAL_ROW)
    assert g["available"] is True and g["name"] == "NVIDIA GeForce RTX 5090"
    assert g["temp_c"] == 53 and g["mem_temp_c"] is None
    assert g["fan_pct"] == 0 and g["util_pct"] == 10
    assert g["clock_gr_mhz"] == 1642 and g["clock_mem_mhz"] == 7001
    assert g["power_w"] == 72.34 and g["power_limit_w"] == 600.0
    assert g["vram_used_mib"] == 14585 and g["vram_total_mib"] == 32607
    assert g["pstate"] == "P3" and g["throttle_reasons"] == 0


def test_parse_gpu_row_rejects_wrong_width() -> None:
    with pytest.raises(ValueError):
        perf_monitor.parse_gpu_row("NVIDIA, 53, 0")


@needs_nvsmi
def test_sample_gpu_live() -> None:
    g = perf_monitor.sample_gpu()
    assert g["available"], g
    assert isinstance(g["temp_c"], int) and 0 < g["temp_c"] < 120
    assert g["vram_total_mib"] > 0 and 0 <= g["fan_pct"] <= 100


# ---------------------------------------------------------------- frame-time math (shared by both backends)
def test_reduce_frame_times_one_percent_low_is_mean_of_slowest_percent() -> None:
    ms = [10.0] * 99 + [50.0]
    r = perf_monitor.reduce_frame_times(ms, dropped=1)
    assert r == {"frames": 100, "dropped": 1, "avg_fps": 96.2, "avg_frame_ms": 10.4,
                 "low1_fps": 20.0, "max_frame_ms": 50.0}
    assert perf_monitor.reduce_frame_times([]) == {"frames": 0, "dropped": 0}
    assert perf_monitor.reduce_frame_times([0.0, -1.0, 8.0])["frames"] == 1  # non-positive ignored


# ---------------------------------------------------------------- console backend CSV reducer
V2_HEADER = ("Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,PresentFlags,"
             "AllowsTearing,PresentMode,FrameType,CPUStartTime,MsCPUBusy,MsCPUWait,MsGPULatency,"
             "MsGPUTime,MsGPUBusy,MsGPUWait,VideoBusy,DisplayLatency,DisplayedTime")


def _v2_row(app: str, start: float, busy: float, wait: float, displayed: str = "16.67") -> str:
    return (f"{app},1234,0x1,DXGI,1,0,0,Hardware: Independent Flip,Application,{start:.4f},"
            f"{busy},{wait},1,2,3,4,0,20,{displayed}")


def test_reducer_v2_cpu_busy_plus_wait_and_na_dropped() -> None:
    r = perf_monitor.FrameReducer()
    r.feed_line(V2_HEADER)
    t = 0.0
    for _ in range(99):
        r.feed_line(_v2_row("game.exe", t, 6.0, 4.0))
        t += 0.010
    r.feed_line(_v2_row("game.exe", t, 40.0, 10.0, displayed="NA"))
    e = r.reduce()[0]
    assert e["app"] == "game.exe" and e["pid"] == "1234"
    assert e["frames"] == 100 and e["dropped"] == 1 and e["low1_fps"] == 20.0
    assert r.reduce() == []


def test_reducer_v1_ms_between_presents_and_dropped_column() -> None:
    r = perf_monitor.FrameReducer()
    r.feed_line("Application,ProcessID,SwapChainAddress,Runtime,SyncInterval,PresentFlags,Dropped,"
                "TimeInSeconds,MsBetweenPresents,MsInPresentAPI")
    for i in range(10):
        r.feed_line(f"old.exe,7,0x2,DXGI,1,0,{1 if i == 3 else 0},{i * 0.02},20.0,1.0")
    e = r.reduce()[0]
    assert e["avg_fps"] == 50.0 and e["frames"] == 10 and e["dropped"] == 1


def test_reducer_derives_frame_time_from_cpustarttime_when_no_ms_columns() -> None:
    r = perf_monitor.FrameReducer()
    r.feed_line("Application,ProcessID,SwapChainAddress,CPUStartTime")
    for i in range(5):
        r.feed_line(f"x.exe,1,0xA,{i * 0.0125}")
    e = r.reduce()[0]
    assert e["frames"] == 4 and e["avg_fps"] == 80.0


def test_format_line_covers_all_lanes() -> None:
    rec = {"t": "2026-09-04T16:40:35", "gpu": perf_monitor.parse_gpu_row(REAL_ROW),
           "fps": [{"app": "game.exe", "pid": 9, "frames": 3, "dropped": 0, "avg_fps": 60.0,
                    "low1_fps": 55.0, "max_frame_ms": 18.2, "display_latency_ms": 11.3},
                   {"app": "idle.exe", "pid": 10, "frames": 0, "dropped": 0}]}
    line = perf_monitor.format_line(rec)
    assert line.startswith("16:40:35 | GPU 53C fan 0% util 10%")
    assert "game.exe:9 60.0fps (1%low 55.0, max 18.2ms) drop 0 lat 11.3ms" in line
    assert "idle.exe:10 no frames" in line
    svc_only = {"t": "2026-09-04T16:40:35", "gpu": {"available": False, "error": "x"},
                "gpu_svc": {"temp_c": 53.0, "util_pct": 1.0, "clock_gr_mhz": 1.0, "power_w": 2.0, "vram_used_mib": 3},
                "fps": {"error": "trace session refused: access denied"}}
    line = perf_monitor.format_line(svc_only)
    assert "GPU(svc) 53.0C" in line and "fps n/a: trace session refused" in line


@pytest.mark.skipif(perf_monitor.find_presentmon() is None, reason="PresentMon console not installed")
def test_console_args_and_privilege_diagnostic_are_honest() -> None:
    exe = perf_monitor.find_presentmon()
    assert exe is not None and exe.exists()
    args = perf_monitor.presentmon_args(exe, ["game.exe"], session="t", timed=2)
    assert args[1:] == ["--output_stdout", "--no_console_stats", "--stop_existing_session",
                        "--session_name", "t", "--process_name", "game.exe",
                        "--timed", "2", "--terminate_after_timed"]
    diag = perf_monitor.capture_privilege_diagnostic(exe)
    assert diag["ok"] or ("fix" in diag and diag["detail"]), diag


# ---------------------------------------------------------------- service backend (PresentMonAPI2, no elevation)
@needs_service
def test_service_session_version_and_gpu_device() -> None:
    with pm.Session() as s:
        assert s.version().split(".")[0].isdigit()
        devices = s.devices()
        assert any(d["type"] == "GRAPHICS_ADAPTER" for d in devices), devices
        gpu = s.gpu_device_id()
        assert gpu is not None and gpu in {d["id"] for d in devices}
        assert s.gpu_device_id(prefer="no-such-adapter-name") == gpu


@needs_service
def test_service_query_registration_drops_rejected_elements_individually() -> None:
    with pm.Session() as s:
        gpu = s.gpu_device_id()
        spec = [pm.Element("fps", "PM_METRIC_PRESENTED_FPS", "PM_STAT_AVG"),
                pm.Element("bad_stat", "PM_METRIC_DROPPED_FRAMES", "PM_STAT_COUNT"),  # rejected on 2.5.1
                pm.Element("temp", "PM_METRIC_GPU_TEMPERATURE", "PM_STAT_AVG", gpu)]
        q = s.dynamic_query(spec)
        try:
            assert [e.key for e in q.accepted] == ["fps", "temp"]
            assert [e.key for e in q.rejected] == ["bad_stat"]
            assert q.blob_size == 16
        finally:
            q.close()


@needs_service
def test_service_frame_events_from_desktop_compositor() -> None:
    """dwm.exe presents continuously on any interactive desktop - the always-on ground truth."""
    dwm = pm.pids_by_name(["dwm.exe"])
    if not dwm:
        pytest.skip("no dwm.exe (non-interactive session)")
    pid, name = dwm[0]
    assert name.lower() == "dwm.exe"
    # dwm is a protected process: OpenProcess-based lookup may be None, the snapshot path must not be
    assert pm.process_name(pid).lower() == "dwm.exe"
    assert pm.process_name(__import__("os").getpid()).lower().startswith("python")
    with pm.Session() as s:
        s.track(pid)
        fq = s.frame_query(perf_monitor.ServiceFpsLane.FRAMES)
        try:
            rows, deadline = [], time.time() + 6  # first window after track() is often empty
            while len(rows) < 20 and time.time() < deadline:
                time.sleep(0.5)
                rows += fq.consume(pid)
        finally:
            fq.close()
    assert len(rows) >= 20, len(rows)
    r = perf_monitor.reduce_frame_times(row["frame_ms"] for row in rows)
    assert 10 < r["avg_fps"] < 1000 and r["max_frame_ms"] >= r["avg_frame_ms"]


@needs_service
def test_service_lane_reports_stats_only_when_frames_arrived() -> None:
    dwm = pm.pids_by_name(["dwm.exe"])
    if not dwm:
        pytest.skip("no dwm.exe")
    lane = perf_monitor.ServiceFpsLane(perf_monitor.Targets(pids=[dwm[0][0], sys.maxsize % 2**31]))
    try:
        deadline = time.time() + 6
        while True:  # keep sampling until the live pid's window carries frames (warm-up)
            time.sleep(1.0)
            entries, gpu = lane.sample()
            by_pid = {e["pid"]: e for e in entries}
            if by_pid[dwm[0][0]]["frames"] or time.time() > deadline:
                break
    finally:
        lane.close()
    live = by_pid[dwm[0][0]]
    assert live["frames"] > 0 and live["presented_fps"] > 0 and "display_latency_ms" in live
    bogus = by_pid[sys.maxsize % 2**31]
    assert bogus["frames"] == 0 and "presented_fps" not in bogus  # no stale stats for a dead pid
    if lane.gpu_id is not None:
        assert 0 < gpu["temp_c"] < 120 and gpu["vram_used_mib"] > 0


@needs_service
def test_monitor_end_to_end_with_service_backend(tmp_path: Path) -> None:
    dwm = pm.pids_by_name(["dwm.exe"])
    if not dwm:
        pytest.skip("no dwm.exe")
    out = tmp_path / "perf.jsonl"
    summary = perf_monitor.monitor(targets=perf_monitor.Targets(processes=["dwm.exe"]), interval=1,
                                   duration=3, out_path=out, gpu=False, fps_backend="service", printer=None)
    assert summary["fps_lane"]["backend"] == "service" and summary["frames_seen"] > 0
    assert summary["automatic_process_termination"] is False
    records = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert records and records[0]["schema"] == "beast.perf-sample/v2"
    assert any(e["frames"] > 0 for rec in records for e in rec["fps"])
    assert "gpu_svc" in records[-1]


@needs_nvsmi
def test_cli_gpu_only_writes_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "perf.jsonl"
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "perf_monitor.py"), "--no-fps",
                           "--duration", "2", "--interval", "1", "--out", str(out), "--quiet"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) >= 2 and lines[0]["gpu"]["available"] and "fps" not in lines[0]
    assert json.loads(proc.stdout)["automatic_process_termination"] is False


def test_monitor_never_crashes_when_fps_backend_unavailable(tmp_path: Path) -> None:
    summary = perf_monitor.monitor(interval=0.2, duration=0.4, gpu=False, fps_backend="console"
                                   if perf_monitor.find_presentmon() is None else "auto", printer=None)
    lane = summary["fps_lane"]
    assert lane["available"] or (lane.get("error") and lane.get("fix")), lane
