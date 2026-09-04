"""Live FPS + GPU thermal/fan monitor for the single-node Beast runtime.

Lanes, sampled on one clock and written as one JSONL stream:

  gpu      nvidia-smi point-in-time telemetry: temperature, FAN, utilisation, clocks,
           power, VRAM, P-state, throttle reasons. (Only source of fan speed on NVIDIA.)
  fps      per target process: frames in the window, avg / 1 %-low FPS, worst frame,
           dropped frames, plus presented/displayed FPS and display latency when the
           service backend is used.
  gpu_svc  GPU temp / power / clocks / util / VRAM as seen by the PresentMon service -
           a second, independent reading that cross-checks the nvidia-smi lane.

fps backends, chosen automatically:
  service  PresentMon shared service via PresentMonAPI2 (studio/presentmon_api.py).
           Needs NO elevation. Preferred.
  console  PresentMon console app streaming CSV. Needs elevation or the
           "Performance Log Users" group; kept as the fallback when the service is absent.

Targets: explicit --pid / --process, or (default) whatever owns the foreground window,
re-resolved every sample. Nothing here terminates a user process.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import presentmon_api as pm

REPO = Path(__file__).resolve().parents[1]
PRESENTMON_DIRS = (Path(r"C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication"),)
PRIVILEGE_FIX = (
    'one-time, elevated shell: net localgroup "Performance Log Users" %USERNAME% /add '
    "then sign out/in - or run the monitor from an elevated terminal"
)

# nvidia-smi query field -> record key. Order matters: it is the CSV column order.
GPU_FIELDS: tuple[tuple[str, str], ...] = (
    ("timestamp", "timestamp"), ("name", "name"), ("temperature.gpu", "temp_c"),
    ("temperature.memory", "mem_temp_c"), ("fan.speed", "fan_pct"), ("utilization.gpu", "util_pct"),
    ("utilization.memory", "mem_util_pct"), ("clocks.gr", "clock_gr_mhz"), ("clocks.mem", "clock_mem_mhz"),
    ("power.draw", "power_w"), ("power.limit", "power_limit_w"), ("memory.used", "vram_used_mib"),
    ("memory.total", "vram_total_mib"), ("pstate", "pstate"),
    ("clocks_throttle_reasons.active", "throttle_reasons"),
)
_TEXT_KEYS = {"timestamp", "name", "pstate"}


# --------------------------------------------------------------------------- gpu lane (nvidia-smi)
def _num(value: str) -> int | float | None:
    value = value.strip()
    if value in {"", "N/A", "[N/A]"}:
        return None
    try:
        return int(value)
    except ValueError:
        return float(value)


def parse_gpu_row(row: str) -> dict[str, Any]:
    parts = [p.strip() for p in row.strip().split(",")]
    if len(parts) != len(GPU_FIELDS):
        raise ValueError(f"unexpected nvidia-smi row ({len(parts)} cols): {row!r}")
    out: dict[str, Any] = {"available": True}
    for (_, key), raw in zip(GPU_FIELDS, parts):
        if key in _TEXT_KEYS:
            out[key] = raw
        elif key == "throttle_reasons":
            out[key] = int(raw, 16) if raw.startswith("0x") else _num(raw)
        else:
            out[key] = _num(raw)
    return out


def sample_gpu(*, timeout: float = 3.0) -> dict[str, Any]:
    query = ",".join(field_ for field_, _ in GPU_FIELDS)
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=timeout,
        )
        first = next(line for line in result.stdout.splitlines() if line.strip())
        return parse_gpu_row(first)
    except (FileNotFoundError, StopIteration, subprocess.SubprocessError, ValueError) as exc:
        return {"available": False, "error": str(exc)}


# --------------------------------------------------------------------------- frame-time reduction
def reduce_frame_times(ms: Iterable[float], dropped: int = 0) -> dict[str, Any]:
    """frames, avg/1 %-low FPS, worst frame. '1 % low' = mean of the slowest 1 % of frames."""
    ms = sorted(m for m in ms if m > 0)
    out: dict[str, Any] = {"frames": len(ms), "dropped": dropped}
    if ms:
        avg = sum(ms) / len(ms)
        slowest = ms[-max(1, len(ms) // 100):]
        low1 = sum(slowest) / len(slowest)
        out.update(avg_fps=round(1000.0 / avg, 1), avg_frame_ms=round(avg, 2),
                   low1_fps=round(1000.0 / low1, 1), max_frame_ms=round(ms[-1], 2))
    return out


# --------------------------------------------------------------------------- targets
@dataclass
class Targets:
    pids: list[int] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)

    @property
    def foreground(self) -> bool:
        return not self.pids and not self.processes

    def resolve(self) -> list[tuple[int, str]]:
        if self.foreground:
            pid, name = pm.foreground_pid()
            return [(pid, name or "?")] if pid else []
        out = [(pid, pm.process_name(pid) or "?") for pid in self.pids]
        out += pm.pids_by_name(self.processes)
        return out

    def describe(self) -> dict[str, Any]:
        return {"mode": "foreground" if self.foreground else "explicit",
                "pids": self.pids, "processes": self.processes}


# --------------------------------------------------------------------------- fps backend: service
class ServiceFpsLane:
    """PresentMon shared service via PresentMonAPI2 - no elevation needed."""

    STATS = [pm.Element("app", "PM_METRIC_APPLICATION"),
             pm.Element("presented_fps", "PM_METRIC_PRESENTED_FPS", "PM_STAT_AVG"),
             pm.Element("displayed_fps", "PM_METRIC_DISPLAYED_FPS", "PM_STAT_AVG"),
             pm.Element("display_latency_ms", "PM_METRIC_DISPLAY_LATENCY", "PM_STAT_AVG"),
             pm.Element("gpu_busy_ms", "PM_METRIC_GPU_BUSY", "PM_STAT_AVG"),
             pm.Element("present_mode", "PM_METRIC_PRESENT_MODE", "PM_STAT_MID_POINT")]
    GPU = {"temp_c": "PM_METRIC_GPU_TEMPERATURE", "power_w": "PM_METRIC_GPU_POWER",
           "power_limit_w": "PM_METRIC_GPU_SUSTAINED_POWER_LIMIT", "clock_gr_mhz": "PM_METRIC_GPU_FREQUENCY",
           "clock_mem_mhz": "PM_METRIC_GPU_MEM_FREQUENCY", "util_pct": "PM_METRIC_GPU_UTILIZATION",
           "vram_used_bytes": "PM_METRIC_GPU_MEM_USED", "fan_rpm": "PM_METRIC_GPU_FAN_SPEED",
           "fan_pct": "PM_METRIC_GPU_FAN_SPEED_PERCENT"}
    FRAMES = [pm.Element("frame_ms", "PM_METRIC_CPU_FRAME_TIME"),
              pm.Element("dropped", "PM_METRIC_DROPPED_FRAMES")]
    backend = "service"

    def __init__(self, targets: Targets, *, window_ms: float = 1000.0) -> None:
        self.targets = targets
        self.session = pm.Session().open()
        self.gpu_id = self.session.gpu_device_id()
        gpu_spec = ([pm.Element(k, m, "PM_STAT_AVG", self.gpu_id) for k, m in self.GPU.items()]
                    if self.gpu_id is not None else [])
        self.stats = self.session.dynamic_query(self.STATS + gpu_spec, window_ms=window_ms, offset_ms=window_ms)
        self.frames = self.session.frame_query(self.FRAMES)
        self.rejected = sorted({e.metric for e in self.stats.rejected + self.frames.rejected})
        self._anchor = os.getpid()  # GPU telemetry needs *a* tracked pid; ours never presents
        self.session.track(self._anchor)
        self.frames_seen = 0

    def info(self) -> dict[str, Any]:
        return {"available": True, "backend": self.backend, "api": self.session.version(),
                "gpu_device": self.gpu_id, "rejected_metrics": self.rejected,
                "targets": self.targets.describe()}

    def sample(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        wanted = self.targets.resolve()
        for pid, _ in wanted:
            if pid not in self.session.tracked:
                try:
                    self.session.track(pid)
                except pm.PresentMonError:
                    pass
        for pid in self.session.tracked - {self._anchor} - {p for p, _ in wanted}:
            self.session.untrack(pid)
        entries = []
        for pid, name in wanted:
            if pid not in self.session.tracked:
                entries.append({"app": name, "pid": pid, "frames": 0, "dropped": 0, "error": "not trackable"})
                continue
            rows = self.frames.consume(pid)
            self.frames_seen += len(rows)
            entry = {"app": name, "pid": pid,
                     **reduce_frame_times((r.get("frame_ms") or 0.0 for r in rows),
                                          sum(1 for r in rows if r.get("dropped")))}
            if entry["frames"]:  # only trust windowed stats when real frame events arrived
                for stat in self.stats.poll(pid):
                    entry.update(presented_fps=round(stat.get("presented_fps", 0.0), 1),
                                 displayed_fps=round(stat.get("displayed_fps", 0.0), 1),
                                 display_latency_ms=round(stat.get("display_latency_ms", 0.0), 2),
                                 gpu_busy_ms=round(stat.get("gpu_busy_ms", 0.0), 2),
                                 present_mode=self.session.enum_name("PM_PRESENT_MODE", stat.get("present_mode", 0)))
                    break
            entries.append(entry)
        gpu: dict[str, Any] = {}
        if self.gpu_id is not None:
            for stat in self.stats.poll(self._anchor):
                for key in self.GPU:
                    if key in stat:
                        gpu[key] = round(stat[key], 2)
                if "vram_used_bytes" in gpu:
                    gpu["vram_used_mib"] = int(gpu.pop("vram_used_bytes") // (1024 * 1024))
                break
        return entries, gpu

    def close(self) -> None:
        self.stats.close()
        self.frames.close()
        self.session.close()


# --------------------------------------------------------------------------- fps backend: console app
def find_presentmon() -> Path | None:
    on_path = shutil.which("PresentMon")
    if on_path:
        return Path(on_path)
    for directory in PRESENTMON_DIRS:
        hits = sorted(directory.glob("PresentMon-*-x64.exe"))
        if hits:
            return hits[-1]
    return None


def presentmon_args(exe: Path, processes: Iterable[str] = (), *, session: str = "beast",
                    timed: float | None = None) -> list[str]:
    args = [str(exe), "--output_stdout", "--no_console_stats", "--stop_existing_session",
            "--session_name", session]
    for name in processes:
        args += ["--process_name", name]
    if timed is not None:
        args += ["--timed", str(timed), "--terminate_after_timed"]
    return args


class FrameReducer:
    """Header-driven PresentMon CSV reducer (console backend).

    Frame time source, in order of preference:
      FrameTime | MsBetweenPresents          (explicit column)
      MsCPUBusy + MsCPUWait                  (PresentMon 2.x CPU frame time)
      delta of consecutive CPUStartTime      (seconds since capture start)
    Dropped frames: ``Dropped == 1`` (1.x) or ``DisplayedTime == NA`` (2.x).
    """

    def __init__(self) -> None:
        self.header: list[str] | None = None
        self._idx: dict[str, int] = {}
        self._lock = threading.Lock()
        self._frames: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._dropped: dict[tuple[str, str], int] = defaultdict(int)
        self._last_start: dict[tuple[str, str], float] = {}
        self.rows_seen = 0

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        row = next(csv.reader([line]))
        if self.header is None:
            self.header = row
            self._idx = {name: i for i, name in enumerate(row)}
            return
        self.feed_row(row)

    def _get(self, row: list[str], col: str) -> str | None:
        i = self._idx.get(col)
        return row[i] if i is not None and i < len(row) else None

    def _float(self, row: list[str], col: str) -> float | None:
        raw = self._get(row, col)
        if raw is None or raw.strip() in {"", "NA", "N/A"}:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def feed_row(self, row: list[str]) -> None:
        if self.header is None:
            raise RuntimeError("header row not seen yet")
        key = (self._get(row, "Application") or "?", self._get(row, "ProcessID") or "?")
        ms = self._float(row, "FrameTime")
        if ms is None:
            ms = self._float(row, "MsBetweenPresents")
        if ms is None:
            busy, wait = self._float(row, "MsCPUBusy"), self._float(row, "MsCPUWait")
            if busy is not None and wait is not None:
                ms = busy + wait
        start = self._float(row, "CPUStartTime")
        if ms is None and start is not None:
            prev = self._last_start.get(key)
            ms = (start - prev) * 1000.0 if prev is not None else None
        if start is not None:
            self._last_start[key] = start
        dropped = self._get(row, "Dropped") == "1" or (
            "DisplayedTime" in self._idx and self._float(row, "DisplayedTime") is None)
        with self._lock:
            self.rows_seen += 1
            if ms is not None and ms > 0:
                self._frames[key].append(ms)
            if dropped:
                self._dropped[key] += 1

    def reduce(self) -> list[dict[str, Any]]:
        """Summarise and clear the current window."""
        with self._lock:
            frames, dropped = dict(self._frames), dict(self._dropped)
            self._frames.clear()
            self._dropped.clear()
        return [{"app": key[0], "pid": key[1], **reduce_frame_times(frames.get(key, []), dropped.get(key, 0))}
                for key in sorted(set(frames) | set(dropped))]


def _looks_like_privilege_error(text: str) -> bool:
    return "access denied" in text.lower() or "administrative privileges" in text.lower()


def capture_privilege_diagnostic(exe: Path | None = None, *, seconds: float = 1.0) -> dict[str, Any]:
    """Try a real 1 s console trace. Returns ok/detail/fix - never raises."""
    exe = exe or find_presentmon()
    if exe is None:
        return {"ok": False, "detail": "PresentMon console not found", "fix": "winget install Intel.PresentMon"}
    try:
        proc = subprocess.run(presentmon_args(exe, session="beastdoctor", timed=seconds) + ["--no_csv"],
                              capture_output=True, text=True, timeout=seconds + 20)
    except subprocess.SubprocessError as exc:
        return {"ok": False, "detail": str(exc), "fix": PRIVILEGE_FIX}
    text = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode == 0:
        return {"ok": True, "detail": f"trace session opened ({exe.name})"}
    if _looks_like_privilege_error(text):
        return {"ok": False, "detail": "trace session refused: access denied", "fix": PRIVILEGE_FIX}
    return {"ok": False, "detail": f"exit {proc.returncode}: {text.strip()[:200]}", "fix": PRIVILEGE_FIX}


class ConsoleFpsLane:
    """PresentMon console app streaming CSV - needs elevation / Performance Log Users."""

    backend = "console"

    def __init__(self, targets: Targets) -> None:
        exe = find_presentmon()
        if exe is None:
            raise FileNotFoundError("PresentMon console not found")
        self.targets, self.exe = targets, exe
        self.reducer = FrameReducer()
        self._stderr: list[str] = []
        self.proc = subprocess.Popen(presentmon_args(exe, targets.processes), stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)

        def _pump(stream: Any, sink: Callable[[str], None]) -> None:
            for line in iter(stream.readline, ""):
                sink(line)

        threading.Thread(target=_pump, args=(self.proc.stdout, self.reducer.feed_line), daemon=True).start()
        threading.Thread(target=_pump, args=(self.proc.stderr, self._stderr.append), daemon=True).start()

    @property
    def frames_seen(self) -> int:
        return self.reducer.rows_seen

    def info(self) -> dict[str, Any]:
        return {"available": True, "backend": self.backend, "exe": str(self.exe),
                "targets": self.targets.describe()}

    def failure(self) -> dict[str, Any] | None:
        if self.proc.poll() is None:
            return None
        text = "".join(self._stderr)
        return {"available": False, "backend": self.backend, "exit": self.proc.returncode,
                "error": "trace session refused: access denied" if _looks_like_privilege_error(text)
                else text.strip()[:200], "fix": PRIVILEGE_FIX}

    def sample(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self.reducer.reduce(), {}

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()  # our own child PresentMon, never a user process
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def open_fps_lane(backend: str, targets: Targets, *, window_ms: float) -> tuple[Any, dict[str, Any]]:
    """Returns (lane or None, info). backend: auto | service | console."""
    errors: dict[str, str] = {}
    if backend in ("auto", "service"):
        try:
            lane = ServiceFpsLane(targets, window_ms=window_ms)
            return lane, lane.info()
        except (FileNotFoundError, OSError, pm.PresentMonError, RuntimeError) as exc:
            errors["service"] = str(exc)
    if backend in ("auto", "console"):
        try:
            lane = ConsoleFpsLane(targets)
            return lane, lane.info()
        except (FileNotFoundError, OSError) as exc:
            errors["console"] = str(exc)
    return None, {"available": False, "backend": None, "error": "; ".join(f"{k}: {v}" for k, v in errors.items()),
                  "fix": pm.INSTALL_FIX}


# --------------------------------------------------------------------------- combined loop
def format_line(record: dict[str, Any]) -> str:
    parts = [record["t"].split("T")[-1][:8]]
    g = record.get("gpu") or {}
    svc = record.get("gpu_svc") or {}
    if g.get("available"):
        parts.append(
            f"GPU {g.get('temp_c')}C fan {g.get('fan_pct')}% util {g.get('util_pct')}% "
            f"{g.get('clock_gr_mhz')}MHz {g.get('power_w')}W "
            f"VRAM {g.get('vram_used_mib')}/{g.get('vram_total_mib')}MiB"
            + (f" THROTTLE 0x{g['throttle_reasons']:x}" if g.get("throttle_reasons") else ""))
    elif svc:
        parts.append(f"GPU(svc) {svc.get('temp_c')}C util {svc.get('util_pct')}% "
                     f"{svc.get('clock_gr_mhz')}MHz {svc.get('power_w')}W VRAM {svc.get('vram_used_mib')}MiB")
    elif "gpu" in record:
        parts.append(f"GPU n/a ({g.get('error', '')[:40]})")
    fps = record.get("fps")
    if isinstance(fps, list):
        if not fps:
            parts.append("fps: no target")
        for e in fps:
            tag = f"{e['app']}:{e['pid']}"
            if e.get("frames"):
                parts.append(f"{tag} {e['avg_fps']}fps (1%low {e['low1_fps']}, max {e['max_frame_ms']}ms) "
                             f"drop {e['dropped']}"
                             + (f" lat {e['display_latency_ms']}ms" if "display_latency_ms" in e else ""))
            else:
                parts.append(f"{tag} {e.get('error', 'no frames')}")
    elif isinstance(fps, dict) and fps.get("error"):
        parts.append(f"fps n/a: {fps['error']}")
    return " | ".join(parts)


def monitor(*, targets: Targets | None = None, interval: float = 1.0, duration: float = 0.0,
            out_path: Path | None = None, fps: bool = True, gpu: bool = True,
            fps_backend: str = "auto", printer: Callable[[str], None] | None = print,
            stop_event: threading.Event | None = None) -> dict[str, Any]:
    """Run the lanes until ``duration`` seconds elapse (0 = until stop_event / Ctrl+C)."""
    stop_event = stop_event or threading.Event()
    targets = targets or Targets()
    lane, fps_lane = (open_fps_lane(fps_backend, targets, window_ms=interval * 1000.0)
                      if fps else (None, {"available": False, "error": "disabled"}))
    records = 0
    out_fh = None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_fh = out_path.open("a", encoding="utf-8")
    started = time.time()
    try:
        while not stop_event.is_set():
            time.sleep(interval)
            record: dict[str, Any] = {"schema": "beast.perf-sample/v2",
                                      "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
            if gpu:
                record["gpu"] = sample_gpu()
            if fps:
                if lane is not None and isinstance(lane, ConsoleFpsLane) and (failed := lane.failure()):
                    fps_lane, lane = failed, None
                if lane is not None:
                    try:
                        entries, svc = lane.sample()
                        record["fps"] = entries
                        if svc:
                            record["gpu_svc"] = svc
                    except pm.PresentMonError as exc:
                        fps_lane = {"available": False, "backend": lane.backend, "error": str(exc)}
                        lane.close()
                        lane = None
                if lane is None:
                    record["fps"] = {"error": fps_lane.get("error"), "fix": fps_lane.get("fix")}
            records += 1
            if out_fh:
                out_fh.write(json.dumps(record) + "\n")
                out_fh.flush()
            if printer:
                printer(format_line(record))
            if duration and time.time() - started >= duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if lane is not None:
            lane.close()
        if out_fh:
            out_fh.close()
    return {"schema": "beast.perf-run/v2", "records": records, "seconds": round(time.time() - started, 1),
            "out": str(out_path) if out_path else None, "gpu_lane": gpu, "fps_lane": fps_lane,
            "frames_seen": lane.frames_seen if lane is not None else 0,
            "automatic_process_termination": False}
