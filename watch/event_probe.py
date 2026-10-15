"""Four-stream desktop event probe - OBSERVE ONLY.

Records, on one clock, what Windows already knows about screen change and writes an
append-only JSONL ledger shaped for Vigil's tamper-evident ledger (no crypto chain here).

  win32    top-level window table (EnumWindows, polled every 100 ms): appeared / vanished /
           title_changed / moved, always with hwnd + pid + title.              [identity]
  uia      UI Automation events with CACHED identity (window opened/closed, focus, invoke,
           menu, text, selection, name/value changes).                        [semantics]
  screen   changed regions per frame: Windows.Graphics.Capture DirtyRegions when the
           `winrt-Windows.Foundation.Collections` binding is present, else a labelled
           numpy tile-diff fallback over the ring frames.                     [pixels-where]
  present  PresentMon frame events (CPU start QPC) per tracked pid, service API, no
           elevation. Pids are tracked as soon as a window for them appears.  [when]
  ring     bounded raw replay frames (mss, half resolution by default), SHA-256 each;
           before/at/after frames exported per semantic event on a worker thread.

Correlator: window_opened / window_closed come from the win32 table (has identity even after
the process is gone) with UIA WindowOpened/WindowClosed attached as corroboration; other
UIA facts (invoke, menu, text, selection, focus on a Window) become their own events.
Classification is strict: `observed` for facts; "invoke then window opened" is `inferred`
with its rule + window recorded; screen changes with no semantic event nearby are listed as
`unexplained_visual_change` coverage gaps - never explained by heuristics.
No VLM, no OCR, no clicks, no typing, no window changes by this process.

Clock domains (kept separate; all QPC-based on Windows):
  t_obs_ns  time.perf_counter_ns() at the Python callback  (= QPC * 100)
  present   PM_METRIC_CPU_START_QPC * 100
  wgc       Direct3D11CaptureFrame.SystemRelativeTime (measured offset to t_obs: -2..+6 ms)
  uia/win32 observer time only (no source timestamp exists)
"""
from __future__ import annotations

import sys

if "comtypes" not in sys.modules:
    sys.coinit_flags = 0  # UIA event handlers need an MTA apartment; must precede comtypes import

import argparse
import bisect
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio"))
import presentmon_api as pm  # noqa: E402

SCHEMA_ROW = "beast.event-probe.row/v1"
SCHEMA_SEMANTIC = "beast.event-probe.semantic/v1"
SCHEMA_MANIFEST = "beast.event-probe.manifest/v1"
NS = 1_000_000


def now_ns() -> int:
    return time.perf_counter_ns()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _intersects(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# ------------------------------------------------------------------ ledger
class Ledger:
    """Append-only JSONL with per-source time indexes for O(log n) window queries."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._fh = path.open("a", encoding="utf-8") if path else None
        self._lock = threading.Lock()
        self.rows: list[dict[str, Any]] = []
        self.by_src: dict[str, list[dict[str, Any]]] = {}
        self.times: dict[str, list[int]] = {}
        self.bytes_by_src: dict[str, int] = {}

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        led = cls(None)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                led.append(json.loads(line))
        return led

    def append(self, row: dict[str, Any]) -> None:
        row.setdefault("schema", SCHEMA_ROW)
        row.setdefault("t_obs_ns", now_ns())
        line = json.dumps(row, separators=(",", ":"), default=str)
        with self._lock:
            if self._fh:
                self._fh.write(line + "\n")
            self.rows.append(row)
            src = row["src"]
            self.by_src.setdefault(src, []).append(row)
            self.times.setdefault(src, []).append(row["t_obs_ns"])
            self.bytes_by_src[src] = self.bytes_by_src.get(src, 0) + len(line) + 1

    def window(self, src: str, lo: int, hi: int) -> list[dict[str, Any]]:
        with self._lock:
            times, rows = self.times.get(src, []), self.by_src.get(src, [])
            return rows[bisect.bisect_left(times, lo): bisect.bisect_right(times, hi)]

    def flush(self) -> None:
        with self._lock:
            if self._fh:
                self._fh.flush()

    def close(self) -> None:
        with self._lock:
            if self._fh:
                self._fh.close()


# ------------------------------------------------------------------ win32 window table
class WindowTableStream:
    """Visible top-level windows via EnumWindows. Cheap (~1 ms), OS-native, identity survives close."""

    def __init__(self, ledger: Ledger, on_new_pid: Callable[[int], None] | None = None) -> None:
        self.ledger, self.on_new_pid = ledger, on_new_pid
        self.table: dict[int, dict[str, Any]] = {}
        self.count = 0
        self._u32, self._dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        self._cb = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(self._enum)
        self._seen: list[int] = []

    def _enum(self, hwnd: int, _: int) -> bool:
        self._seen.append(hwnd)
        return True

    def _describe(self, hwnd: int) -> dict[str, Any] | None:
        u32 = self._u32
        if not u32.IsWindowVisible(hwnd):
            return None
        cloaked = wt.DWORD(0)
        self._dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))  # DWMWA_CLOAKED
        if cloaked.value:
            return None
        length = u32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {"hwnd": hwnd, "pid": pid.value, "title": buf.value[:120],
                "bounds": [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top]}

    def snapshot(self) -> dict[int, dict[str, Any]]:
        self._seen = []
        self._u32.EnumWindows(self._cb, 0)
        out = {}
        for hwnd in self._seen:
            d = self._describe(hwnd)
            if d:
                out[hwnd] = d
        return out

    def poll(self) -> None:
        current = self.snapshot()
        t = now_ns()
        for hwnd, d in current.items():
            old = self.table.get(hwnd)
            if old is None:
                self._emit("appeared", d, t)
                if self.on_new_pid:
                    self.on_new_pid(d["pid"])
            elif old["title"] != d["title"]:
                self._emit("title_changed", d, t, {"previous_title": old["title"]})
            elif old["bounds"] != d["bounds"]:
                self._emit("moved", d, t, {"previous_bounds": old["bounds"]})
        for hwnd, d in self.table.items():
            if hwnd not in current:
                self._emit("vanished", d, t)
        self.table = current

    def _emit(self, event: str, d: dict[str, Any], t: int, extra: dict[str, Any] | None = None) -> None:
        self.count += 1
        row = {"src": "win32", "t_obs_ns": t, "event": event, "app": pm.process_name(d["pid"]) or "?", **d}
        if extra:
            row.update(extra)
        self.ledger.append(row)

    def start(self) -> None:
        self.table = self.snapshot()  # baseline: existing windows are not "appeared"

    def stop(self) -> None:
        pass

    def info(self) -> dict[str, Any]:
        return {"windows_at_end": len(self.table), "rows": self.count}


# ------------------------------------------------------------------ uia stream
class UIAStream:
    """UI Automation events with a cache request so identity survives element teardown."""

    EVENTS = ("UIA_Window_WindowOpenedEventId", "UIA_Window_WindowClosedEventId",
              "UIA_Invoke_InvokedEventId", "UIA_MenuOpenedEventId", "UIA_MenuClosedEventId",
              "UIA_Text_TextChangedEventId", "UIA_SelectionItem_ElementSelectedEventId")
    PROPS = ("UIA_NamePropertyId", "UIA_ValueValuePropertyId", "UIA_ToggleToggleStatePropertyId")
    CACHED = ("UIA_NamePropertyId", "UIA_ProcessIdPropertyId", "UIA_RuntimeIdPropertyId",
              "UIA_ControlTypePropertyId", "UIA_BoundingRectanglePropertyId", "UIA_ClassNamePropertyId",
              "UIA_AutomationIdPropertyId", "UIA_NativeWindowHandlePropertyId")

    def __init__(self, ledger: Ledger) -> None:
        import comtypes
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U
        self._U, self._comtypes = U, comtypes
        self.uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        self.root = self.uia.GetRootElement()
        self.cache = self.uia.CreateCacheRequest()
        for name in self.CACHED:
            self.cache.AddProperty(getattr(U, name))
        self.ledger = ledger
        self.event_names = {getattr(U, n): n.replace("UIA_", "").replace("EventId", "") for n in dir(U)
                            if n.startswith("UIA_") and n.endswith("EventId")}
        self.prop_names = {getattr(U, n): n.replace("UIA_", "").replace("PropertyId", "") for n in dir(U)
                           if n.startswith("UIA_") and n.endswith("PropertyId")}
        self.control_names = {getattr(U, n): n.replace("UIA_", "").replace("ControlTypeId", "") for n in dir(U)
                              if n.startswith("UIA_") and n.endswith("ControlTypeId")}
        self.pids_seen: set[int] = set()
        self.count = 0
        self._handlers: list[Any] = []

    def _describe(self, sender: Any) -> dict[str, Any]:
        U = self._U
        d: dict[str, Any] = {}

        def cached(prop: int, attr_current: str) -> Any:
            try:
                v = sender.GetCachedPropertyValue(prop)
                if v not in (None, "", 0):
                    return v
            except Exception:  # noqa: BLE001
                pass
            try:
                return getattr(sender, attr_current)
            except Exception:  # noqa: BLE001
                return None

        d["name"] = cached(U.UIA_NamePropertyId, "CurrentName")
        d["pid"] = cached(U.UIA_ProcessIdPropertyId, "CurrentProcessId")
        ct = cached(U.UIA_ControlTypePropertyId, "CurrentControlType")
        d["control_type"] = self.control_names.get(ct, ct)
        d["class_name"] = cached(U.UIA_ClassNamePropertyId, "CurrentClassName")
        d["automation_id"] = cached(U.UIA_AutomationIdPropertyId, "CurrentAutomationId")
        d["hwnd"] = cached(U.UIA_NativeWindowHandlePropertyId, "CurrentNativeWindowHandle")
        rid = cached(U.UIA_RuntimeIdPropertyId, "GetRuntimeId")
        d["runtime_id"] = list(rid) if isinstance(rid, (tuple, list)) else None
        try:
            r = sender.CachedBoundingRectangle
            d["bounds"] = [int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top)]
            if d["bounds"] == [0, 0, 0, 0]:
                d["bounds"] = None
        except Exception:  # noqa: BLE001
            d["bounds"] = None
        if d.get("name"):
            d["name"] = str(d["name"])[:120]
        if d.get("pid"):
            d["pid"] = int(d["pid"])
            self.pids_seen.add(d["pid"])
        return d

    def _emit(self, event: str, sender: Any, extra: dict[str, Any] | None = None) -> None:
        row = {"src": "uia", "t_obs_ns": now_ns(), "event": event, **self._describe(sender)}
        if extra:
            row.update(extra)
        self.count += 1
        self.ledger.append(row)

    def start(self) -> None:
        U, comtypes, stream = self._U, self._comtypes, self

        class AutomationHandler(comtypes.COMObject):
            _com_interfaces_ = [U.IUIAutomationEventHandler]

            def IUIAutomationEventHandler_HandleAutomationEvent(self, sender, event_id):
                stream._emit(stream.event_names.get(int(event_id), str(int(event_id))), sender)
                return 0

        class FocusHandler(comtypes.COMObject):
            _com_interfaces_ = [U.IUIAutomationFocusChangedEventHandler]

            def IUIAutomationFocusChangedEventHandler_HandleFocusChangedEvent(self, sender):
                stream._emit("FocusChanged", sender)
                return 0

        class PropertyHandler(comtypes.COMObject):
            _com_interfaces_ = [U.IUIAutomationPropertyChangedEventHandler]

            def IUIAutomationPropertyChangedEventHandler_HandlePropertyChangedEvent(self, sender, prop_id, new_value):
                try:
                    value = str(new_value)[:200]
                except Exception:  # noqa: BLE001
                    value = None
                stream._emit("PropertyChanged", sender,
                             {"property": stream.prop_names.get(int(prop_id), str(int(prop_id))), "value": value})
                return 0

        ah, fh, ph = AutomationHandler(), FocusHandler(), PropertyHandler()
        self._handlers = [ah, fh, ph]
        for name in self.EVENTS:
            self.uia.AddAutomationEventHandler(getattr(U, name), self.root, U.TreeScope_Subtree, self.cache, ah)
        self.uia.AddFocusChangedEventHandler(self.cache, fh)
        props = (ctypes.c_int * len(self.PROPS))(*[getattr(U, p) for p in self.PROPS])
        self.uia.AddPropertyChangedEventHandlerNativeArray(self.root, U.TreeScope_Subtree, self.cache, ph,
                                                          props, len(self.PROPS))

    def stop(self) -> None:
        # UIA callbacks run on COM RPC threads. Remove handlers, then DRAIN: a callback already
        # dispatched can still be executing against these Python COMObjects. Releasing them (or
        # letting the interpreter tear down) mid-callback corrupts the heap (0xc0000374). Wait for
        # in-flight callbacks to finish before dropping the strong refs.
        try:
            self.uia.RemoveAllEventHandlers()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
        self._handlers = []
        self.uia = None
        self.root = None
        self.cache = None

    def info(self) -> dict[str, Any]:
        return {"rows": self.count, "pids": sorted(self.pids_seen)}


# ------------------------------------------------------------------ present stream
class PresentStream:
    """PresentMon frame events per tracked pid (tracked as soon as a window appears for it)."""

    FRAMES = [pm.Element("qpc", "PM_METRIC_CPU_START_QPC", dtype="u64"),
              pm.Element("frame_ms", "PM_METRIC_CPU_FRAME_TIME"),
              pm.Element("displayed_ms", "PM_METRIC_DISPLAYED_TIME"),
              pm.Element("dropped", "PM_METRIC_DROPPED_FRAMES")]

    def __init__(self, ledger: Ledger, max_pids: int = 24) -> None:
        self.ledger, self.max_pids = ledger, max_pids
        self.session = pm.Session().open()
        self.etw_flush_ms: int | None = None
        try:
            self.session.set_etw_flush_period(50)  # measured default reporting lag is larger; 8..1000 allowed
            self.etw_flush_ms = 50
        except pm.PresentMonError:
            pass
        self.frames = self.session.frame_query(self.FRAMES)
        self.names: dict[int, str] = {}
        self.count = 0
        self._lock = threading.Lock()

    def want(self, pid: int) -> None:
        with self._lock:
            if pid in self.session.tracked or pid == os.getpid() or len(self.session.tracked) >= self.max_pids:
                return
            try:
                self.session.track(pid)
                self.names[pid] = pm.process_name(pid) or "?"
            except pm.PresentMonError:
                pass

    def poll(self) -> None:
        for pid in list(self.session.tracked):
            try:
                rows = self.frames.consume(pid)
            except pm.PresentMonError:
                continue
            for r in rows:
                qpc = int(r.get("qpc") or 0)
                self.count += 1
                self.ledger.append({"src": "present", "pid": pid, "app": self.names.get(pid, "?"),
                                    "t_src_ns": qpc * 100, "frame_ms": round(r.get("frame_ms") or 0.0, 3),
                                    "displayed_ms": round(r.get("displayed_ms") or 0.0, 3),
                                    "dropped": bool(r.get("dropped"))})

    def info(self) -> dict[str, Any]:
        return {"api": self.session.version(), "rejected": [e.metric for e in self.frames.rejected],
                "etw_flush_ms": self.etw_flush_ms, "tracked": sorted(self.names.items()), "rows": self.count}

    def stop(self) -> None:
        self.frames.close()
        self.session.close()


# ------------------------------------------------------------------ screen streams
def _d3d11_device() -> tuple[Any, int]:
    """ctypes D3D11CreateDevice(BGRA) -> (ID3D11Device ptr, IDXGIDevice ptr as int)."""
    dev, ctx, level = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_uint()
    hr = ctypes.windll.d3d11.D3D11CreateDevice(None, 1, None, 0x20, None, 0, 7,
                                                ctypes.byref(dev), ctypes.byref(level), ctypes.byref(ctx))
    if hr != 0:
        raise OSError(f"D3D11CreateDevice failed: {hr & 0xffffffff:#x}")

    class GUID(ctypes.Structure):
        _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    import uuid
    u = uuid.UUID("54ec77fa-1377-44e6-8c32-88fd5f44c84c")  # IDXGIDevice
    guid = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    vtbl = ctypes.cast(dev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    query = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID),
                               ctypes.POINTER(ctypes.c_void_p))(vtbl[0])
    dxgi = ctypes.c_void_p()
    hr = query(dev, ctypes.byref(guid), ctypes.byref(dxgi))
    if hr != 0:
        raise OSError(f"QueryInterface(IDXGIDevice) failed: {hr & 0xffffffff:#x}")
    return dev, dxgi.value


class ScreenStreamWGC:
    """Windows.Graphics.Capture with DirtyRegions - regions only, no pixel readback. Full-res coords."""

    mode = "wgc"

    def __init__(self, ledger: Ledger) -> None:
        import winrt.windows.foundation.collections  # noqa: F401 - IVectorView<RectInt32> wrapper
        from winrt.windows.graphics.capture import (Direct3D11CaptureFramePool, GraphicsCaptureDirtyRegionMode,
                                                    GraphicsCaptureSession)
        from winrt.windows.graphics.capture.interop import create_for_monitor
        from winrt.windows.graphics.directx import DirectXPixelFormat
        from winrt.windows.graphics.directx.direct3d11.interop import create_direct3d11_device_from_dxgi_device
        if not GraphicsCaptureSession.is_supported():
            raise RuntimeError("GraphicsCaptureSession not supported")
        self.ledger = ledger
        self._dev, dxgi = _d3d11_device()
        wdev = create_direct3d11_device_from_dxgi_device(dxgi)
        self.item = create_for_monitor(ctypes.windll.user32.MonitorFromPoint(wt.POINT(0, 0), 1))
        self.size = (self.item.size.width, self.item.size.height)
        self.pool = Direct3D11CaptureFramePool.create_free_threaded(
            wdev, DirectXPixelFormat.B8_G8_R8_A8_UINT_NORMALIZED, 2, self.item.size)
        self.session = self.pool.create_capture_session(self.item)
        self.session.dirty_region_mode = GraphicsCaptureDirtyRegionMode.REPORT_ONLY
        for attr in ("is_border_required", "is_cursor_capture_enabled"):
            try:
                setattr(self.session, attr, False)
            except Exception:  # noqa: BLE001
                pass
        self.frame_id = 0
        self.dirty_px = 0
        self.offsets_ms: list[float] = []
        self._token = self.pool.add_frame_arrived(self._on_frame)

    def _on_frame(self, sender: Any, args: Any) -> None:
        frame = sender.try_get_next_frame()
        if frame is None:
            return
        t_obs = now_ns()
        try:
            t_src = int(frame.system_relative_time.total_seconds() * 1e9)
            rects = [[r.x, r.y, r.width, r.height] for r in frame.dirty_regions]
        finally:
            frame.close()
        self.frame_id += 1
        px = sum(w * h for _, _, w, h in rects)
        self.dirty_px += px
        if len(self.offsets_ms) < 5000:
            self.offsets_ms.append((t_obs - t_src) / NS)
        if rects:
            self.ledger.append({"src": "screen", "mode": self.mode, "frame_id": self.frame_id, "t_obs_ns": t_obs,
                                "t_src_ns": t_src, "dirty_rects": rects, "dirty_px": px})

    def start(self) -> None:
        self.session.start_capture()

    def stop(self) -> None:
        self.session.close()
        self.pool.close()

    def info(self) -> dict[str, Any]:
        o = sorted(self.offsets_ms)
        return {"mode": self.mode, "size": list(self.size), "frames": self.frame_id, "dirty_px_total": self.dirty_px,
                "clock_offset_ms": {"min": round(o[0], 3), "median": round(o[len(o) // 2], 3), "max": round(o[-1], 3)}
                if o else None}


def tile_diff(prev: "Any", cur: "Any", tile: int, threshold: float, scale: float) -> list[list[int]]:
    """numpy tile-wise mean-abs-diff on HxWx4 uint8 arrays -> dirty rects in FULL-RES coordinates."""
    import numpy as np
    h, w = cur.shape[:2]
    ty, tx = -(-h // tile), -(-w // tile)
    pad_h, pad_w = ty * tile - h, tx * tile - w
    a = np.pad(cur[:, :, :3].astype(np.int16), ((0, pad_h), (0, pad_w), (0, 0)))
    b = np.pad(prev[:, :, :3].astype(np.int16), ((0, pad_h), (0, pad_w), (0, 0)))
    d = np.abs(a - b).mean(axis=2).reshape(ty, tile, tx, tile).mean(axis=(1, 3))
    ys, xs = np.nonzero(d > threshold)
    inv = 1.0 / scale
    return [[int(x * tile * inv), int(y * tile * inv), int(min(tile, w - x * tile) * inv),
             int(min(tile, h - y * tile) * inv)] for y, x in zip(ys.tolist(), xs.tolist())]


class ScreenStreamDiff:
    """Fallback: numpy tile-diff of consecutive ring frames. Labelled 'diff' - this IS the frame-diff the
    blueprint proposed; kept so the probe runs where WGC DirtyRegions is unavailable."""

    mode = "diff"

    def __init__(self, ledger: Ledger, scale: float, tile: int = 32, threshold: float = 6.0) -> None:
        self.ledger, self.scale, self.tile, self.threshold = ledger, scale, tile, threshold
        self._prev: Any = None
        self.frame_id = 0
        self.dirty_px = 0
        self.size = [0, 0]

    def feed(self, raw_rgba: bytes, width: int, height: int, t_obs: int) -> None:
        import numpy as np
        cur = np.frombuffer(raw_rgba, dtype=np.uint8).reshape(height, width, 4)
        self.size = [int(width / self.scale), int(height / self.scale)]
        self.frame_id += 1
        prev, self._prev = self._prev, cur
        if prev is None or prev.shape != cur.shape:
            return
        rects = tile_diff(prev, cur, self.tile, self.threshold, self.scale)
        px = sum(w * h for _, _, w, h in rects)
        self.dirty_px += px
        if rects:
            self.ledger.append({"src": "screen", "mode": self.mode, "frame_id": self.frame_id, "t_obs_ns": t_obs,
                                "t_src_ns": None, "dirty_rects": rects[:256], "dirty_px": px, "tiles": len(rects)})

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def info(self) -> dict[str, Any]:
        return {"mode": self.mode, "size": self.size, "frames": self.frame_id, "dirty_px_total": self.dirty_px,
                "tile": self.tile, "threshold": self.threshold,
                "note": "numpy tile-diff fallback over ring frames; rects scaled to full-res coordinates"}


# ------------------------------------------------------------------ ring buffer
@dataclass
class RingFrame:
    frame_id: int
    t_obs_ns: int
    sha256: str
    width: int
    height: int
    raw: bytes = field(repr=False)


class RingBuffer:
    """Bounded raw replay frames via mss at `scale` (5K full-res is 22 fps / 44 MB per frame in Python,
    measured 2026-09-04, so default is half-res). Never grows beyond `max_frames`."""

    def __init__(self, max_frames: int = 150, scale: float = 0.5, fps: float = 10.0,
                 on_frame: Callable[[bytes, int, int, int], None] | None = None) -> None:
        import mss
        self._mss = mss.mss()
        self.monitor = self._mss.monitors[1]
        self.scale, self.fps, self.on_frame = scale, fps, on_frame
        self.frames: deque[RingFrame] = deque(maxlen=max_frames)
        self.captured = 0
        self.bytes_per_frame = 0
        self.grab_ms: list[float] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="ring", daemon=True)
        self._lock = threading.Lock()

    def _grab(self) -> tuple[bytes, int, int]:
        """BGRA bytes. Downscale by integer stride (numpy view copy, ~5 ms) - PIL resize cost 170 ms at 5K."""
        shot = self._mss.grab(self.monitor)
        w, h = shot.size
        if self.scale == 1.0:
            return shot.raw, w, h
        import numpy as np
        step = max(1, int(round(1.0 / self.scale)))
        view = np.frombuffer(shot.raw, dtype=np.uint8).reshape(h, w, 4)[::step, ::step]
        return np.ascontiguousarray(view).tobytes(), view.shape[1], view.shape[0]

    def _loop(self) -> None:
        period = 1.0 / self.fps
        while not self._stop.is_set():
            t0 = time.perf_counter()
            raw, w, h = self._grab()
            t_obs = now_ns()
            self.captured += 1
            self.bytes_per_frame = len(raw)
            frame = RingFrame(self.captured, t_obs, sha256_bytes(raw), w, h, raw)
            with self._lock:
                self.frames.append(frame)
            if self.on_frame:
                self.on_frame(raw, w, h, t_obs)
            if len(self.grab_ms) < 5000:
                self.grab_ms.append((time.perf_counter() - t0) * 1000)
            self._stop.wait(max(0.0, period - (time.perf_counter() - t0)))

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def around(self, t_ns: int, after_ns: int = 500 * NS) -> dict[str, RingFrame | None]:
        with self._lock:
            frames = list(self.frames)
        return {"before": next((f for f in reversed(frames) if f.t_obs_ns < t_ns), None),
                "at": next((f for f in frames if f.t_obs_ns >= t_ns), None),
                "after": next((f for f in frames if f.t_obs_ns >= t_ns + after_ns), None)}

    @staticmethod
    def export(frame: RingFrame, path: Path) -> dict[str, Any]:
        from PIL import Image
        Image.frombuffer("RGBA", (frame.width, frame.height), frame.raw, "raw", "BGRA", 0, 1).convert("RGB") \
            .save(path, format="PNG")
        data = path.read_bytes()
        return {"frame_id": frame.frame_id, "t_obs_ns": frame.t_obs_ns, "raw_sha256": frame.sha256,
                "path": path.name, "png_sha256": sha256_bytes(data), "png_bytes": len(data)}

    def info(self) -> dict[str, Any]:
        g = sorted(self.grab_ms)
        return {"scale": self.scale, "target_fps": self.fps, "captured": self.captured, "retained": len(self.frames),
                "bytes_per_frame": self.bytes_per_frame,
                "grab_ms": {"median": round(g[len(g) // 2], 1), "max": round(g[-1], 1)} if g else None}


# ------------------------------------------------------------------ correlator
UIA_SEMANTIC = {"Invoke_Invoked": "control_invoked", "MenuOpened": "menu_opened", "MenuClosed": "menu_closed",
                "Text_TextChanged": "text_changed", "SelectionItem_ElementSelected": "item_selected"}
WIN32_SEMANTIC = {"appeared": "window_opened", "vanished": "window_closed", "title_changed": "window_title_changed"}
UIA_CORROBORATION = {"window_opened": "Window_WindowOpened", "window_closed": "Window_WindowClosed"}


class Correlator:
    """Facts -> SEMANTIC_EVENT rows with screen / present / replay evidence refs.

    Emits `window_ns` after the fact so trailing dirty rects can land; emit latency is recorded.
    Replay PNG export runs on a worker thread so it never inflates emit latency.
    """

    def __init__(self, ledger: Ledger, ring: RingBuffer | None, out_dir: Path | None, *,
                 window_ns: int = 200 * NS, screen_mode: str = "wgc", screen_window_ns: int | None = None,
                 coalesce_ns: int = 500 * NS) -> None:
        self.ledger, self.ring, self.out_dir = ledger, ring, out_dir
        self.window_ns, self.screen_mode = window_ns, screen_mode
        # diff mode only sees change at ring-frame granularity -> its lookup window must span >= 2 frames
        self.screen_window_ns = screen_window_ns or window_ns
        self.coalesce_ns = coalesce_ns
        self._coalesced: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.coalesced_count = 0
        self.semantic: list[dict[str, Any]] = []
        self._fh = (out_dir / "semantic.jsonl").open("a", encoding="utf-8") if out_dir else None
        self._cursor = 0
        self._pending: deque[dict[str, Any]] = deque()
        self._last_invoke: dict[str, Any] | None = None
        self.exports: list[dict[str, Any]] = []
        self._export_q: queue.Queue[tuple[str, dict[str, RingFrame | None]]] = queue.Queue()
        self._export_thread = threading.Thread(target=self._export_loop, name="export", daemon=True)
        if ring is not None and out_dir is not None:
            self._export_thread.start()

    # -- ingest
    def tick(self, now: int) -> None:
        rows = self.ledger.rows
        while self._cursor < len(rows):
            row = rows[self._cursor]
            self._cursor += 1
            if (row["src"] == "uia" and row["event"] in UIA_SEMANTIC) or \
               (row["src"] == "uia" and row["event"] == "FocusChanged" and row.get("control_type") == "Window") or \
               (row["src"] == "win32" and row["event"] in WIN32_SEMANTIC):
                self._pending.append(row)
        while self._pending and now - self._pending[0]["t_obs_ns"] >= max(self.window_ns, self.screen_window_ns):
            fact = self._pending.popleft()
            if fact["src"] == "uia" and fact["event"] in ("Text_TextChanged", "SelectionItem_ElementSelected",
                                                          "PropertyChanged"):
                key = (fact["event"], fact.get("pid"), tuple(fact.get("runtime_id") or ()), fact.get("name"))
                last = self._coalesced.get(key)
                if last and fact["t_obs_ns"] - last["t_last"] <= self.coalesce_ns:
                    last["t_last"] = fact["t_obs_ns"]
                    last["row"]["coalesced"] = last["row"].get("coalesced", 1) + 1
                    self.coalesced_count += 1
                    continue
                row = self._emit(fact, now)
                self._coalesced[key] = {"t_last": fact["t_obs_ns"], "row": row}
            else:
                self._emit(fact, now)

    def flush(self) -> None:
        self.tick(now_ns() + max(self.window_ns, self.screen_window_ns))

    def enrich_late_present(self) -> int:
        """ETW frame events can reach the consumer after a fact was emitted; attach them post hoc,
        labelled `matched_late` so live vs. retrospective evidence stays distinguishable."""
        n = 0
        for row in self.semantic:
            if "delta_ms" in row["evidence"]["present"]:
                continue
            hit = self._present_hit(row["t_obs_ns"], row["identity"].get("pid"))
            if hit:
                hit["coverage"] = "matched_late"
                row["evidence"]["present"] = hit
                n += 1
        return n

    # -- evidence lookups
    def _screen_hits(self, t: int, bounds: list[int] | None) -> list[dict[str, Any]]:
        hits = []
        for r in self.ledger.window("screen", t - 60 * NS, t + self.screen_window_ns):
            rects = r["dirty_rects"]
            if bounds:
                rects = [x for x in rects if _intersects(x, bounds)]
            if rects:
                hits.append({"frame_id": r["frame_id"], "t_obs_ns": r["t_obs_ns"], "t_src_ns": r.get("t_src_ns"),
                             "rects": rects[:8], "n_rects": len(rects), "dirty_px": sum(w * h for _, _, w, h in rects)})
        return hits

    def _present_hit(self, t: int, pid: int | None) -> dict[str, Any] | None:
        best = None
        for r in self.ledger.window("present", t - self.window_ns, t + self.window_ns):
            if pid and r["pid"] != pid:
                continue
            d = abs(r["t_src_ns"] - t)
            if best is None or d < best["delta_ns"]:
                best = {"pid": r["pid"], "app": r["app"], "t_src_ns": r["t_src_ns"], "delta_ns": d}
        if best:
            best["delta_ms"] = round(best.pop("delta_ns") / NS, 3)
        return best

    def _uia_corroboration(self, t: int, event: str, pid: int | None) -> list[dict[str, Any]]:
        out = []
        for r in self.ledger.window("uia", t - 300 * NS, t + 300 * NS):
            if r["event"] == event and (not pid or not r.get("pid") or r["pid"] == pid):
                out.append({"t_obs_ns": r["t_obs_ns"], "name": r.get("name"), "pid": r.get("pid"),
                            "runtime_id": r.get("runtime_id"), "hwnd": r.get("hwnd")})
        return out

    # -- export
    def _export_loop(self) -> None:
        while True:
            item = self._export_q.get()
            if item is None:
                return
            event_id, around = item
            for key, frame in around.items():
                if frame is not None:
                    meta = RingBuffer.export(frame, self.out_dir / f"{event_id}_{key}.png")
                    meta.update(event_id=event_id, role=key)
                    self.exports.append(meta)

    def _replay_refs(self, t: int, event_id: str) -> dict[str, Any]:
        if self.ring is None:
            return {"coverage": "none"}
        around = self.ring.around(t)
        self._export_q.put((event_id, around))
        return {k: ({"frame_id": f.frame_id, "t_obs_ns": f.t_obs_ns, "raw_sha256": f.sha256,
                     "path": f"{event_id}_{k}.png"} if f else None) for k, f in around.items()}

    # -- emit
    def _emit(self, fact: dict[str, Any], now: int) -> None:
        t = fact["t_obs_ns"]
        event_id = f"evt-{len(self.semantic):06d}"
        if fact["src"] == "win32":
            event_type = WIN32_SEMANTIC[fact["event"]]
            identity = {"src": "win32", "hwnd": fact["hwnd"], "pid": fact["pid"], "app": fact.get("app"),
                        "title": fact["title"], "bounds": fact["bounds"]}
            if "previous_title" in fact:
                identity["previous_title"] = fact["previous_title"]
        else:
            event_type = UIA_SEMANTIC.get(fact["event"], "focus_window")
            identity = {"src": "uia", "event": fact["event"], "name": fact.get("name"), "pid": fact.get("pid"),
                        "control_type": fact.get("control_type"), "automation_id": fact.get("automation_id"),
                        "class_name": fact.get("class_name"), "runtime_id": fact.get("runtime_id"),
                        "hwnd": fact.get("hwnd"), "bounds": fact.get("bounds")}
        screen = self._screen_hits(t, fact.get("bounds"))
        present = self._present_hit(t, fact.get("pid"))
        row: dict[str, Any] = {
            "schema": SCHEMA_SEMANTIC, "event_id": event_id, "classification": "observed",
            "event_type": event_type, "t_obs_ns": t, "t_emit_ns": now, "emit_latency_ms": round((now - t) / NS, 1),
            "identity": identity,
            "evidence": {"screen": {"mode": self.screen_mode, "coverage": "matched" if screen else "none", "hits": screen},
                         "present": present or {"coverage": "none"},
                         "replay": self._replay_refs(t, event_id)}}
        if event_type in UIA_CORROBORATION:
            corr = self._uia_corroboration(t, UIA_CORROBORATION[event_type], fact.get("pid"))
            row["evidence"]["uia"] = {"coverage": "matched" if corr else "none", "events": corr[:6], "count": len(corr)}
        if fact["src"] == "uia" and fact["event"] == "Invoke_Invoked":
            self._last_invoke = fact
        elif event_type == "window_opened" and self._last_invoke and 0 <= t - self._last_invoke["t_obs_ns"] <= 400 * NS:
            row["inferred"] = {"claim": "invoke_then_window_opened", "classification": "inferred",
                               "rule": "UIA Invoke_Invoked within 400 ms before this window_opened, same run",
                               "invoke": {k: self._last_invoke.get(k) for k in ("name", "pid", "t_obs_ns")}}
        self.semantic.append(row)
        if self._fh:
            self._fh.write(json.dumps(row, separators=(",", ":"), default=str) + "\n")
            self._fh.flush()
        return row

    def write_final(self) -> None:
        """Rewrite semantic.jsonl with coalesced counts and late present evidence (the live file is
        append-only during the run; the final file is the reviewed artifact)."""
        if self.out_dir:
            (self.out_dir / "semantic.jsonl").write_text(
                "".join(json.dumps(r, separators=(",", ":"), default=str) + "\n" for r in self.semantic), encoding="utf-8")

    def unexplained_changes(self, min_px: int, gap_ns: int = 300 * NS) -> list[dict[str, Any]]:
        """Screen changes with no semantic fact within +-gap: coverage-gap candidates, never explained."""
        fact_times = sorted(self.ledger.times.get("uia", []) + self.ledger.times.get("win32", []))
        out = []
        for r in self.ledger.by_src.get("screen", []):
            if r["dirty_px"] < min_px:
                continue
            i = bisect.bisect_left(fact_times, r["t_obs_ns"] - gap_ns)
            if i < len(fact_times) and fact_times[i] <= r["t_obs_ns"] + gap_ns:
                continue
            out.append({"frame_id": r["frame_id"], "t_obs_ns": r["t_obs_ns"], "dirty_px": r["dirty_px"],
                        "classification": "observed", "event_type": "unexplained_visual_change"})
        return out

    def close(self) -> None:
        if self._export_thread.is_alive():
            self._export_q.put(None)
            self._export_thread.join(timeout=60)
        if self._fh:
            self._fh.close()


# ------------------------------------------------------------------ run
def run(*, duration: float, out_dir: Path, ring_fps: float = 10.0, ring_scale: float = 0.5, ring_frames: int = 150,
        screen: str = "auto", disable: Iterable[str] = (),
        printer: Callable[[str], None] | None = print) -> dict[str, Any]:
    disable = set(disable)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out_dir / "events.jsonl")
    started_perf, started_wall = now_ns(), time.time_ns()
    streams: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if "present" not in disable:
        try:
            streams["present"] = PresentStream(ledger)
        except Exception as exc:  # noqa: BLE001
            errors["present"] = f"{type(exc).__name__}: {exc}"
    want = streams["present"].want if "present" in streams else None
    if "win32" not in disable:
        streams["win32"] = WindowTableStream(ledger, on_new_pid=want)
        streams["win32"].start()
        if want:
            for d in streams["win32"].table.values():
                want(d["pid"])
    if "uia" not in disable:
        try:
            streams["uia"] = UIAStream(ledger)
            streams["uia"].start()
        except Exception as exc:  # noqa: BLE001
            errors["uia"] = f"{type(exc).__name__}: {exc}"

    screen_stream: Any = None
    if screen in ("auto", "wgc"):
        try:
            screen_stream = ScreenStreamWGC(ledger)
        except Exception as exc:  # noqa: BLE001
            errors["screen_wgc"] = f"{type(exc).__name__}: {exc}"
    if screen_stream is None and screen in ("auto", "diff"):
        screen_stream = ScreenStreamDiff(ledger, scale=ring_scale)
    ring = RingBuffer(max_frames=ring_frames, scale=ring_scale, fps=ring_fps,
                      on_frame=screen_stream.feed if isinstance(screen_stream, ScreenStreamDiff) else None)
    if screen_stream is not None:
        streams["screen"] = screen_stream
        screen_stream.start()
    ring.start()
    diff_mode = isinstance(screen_stream, ScreenStreamDiff)
    correlator = Correlator(ledger, ring, out_dir, screen_mode=screen_stream.mode if screen_stream else "none",
                            screen_window_ns=int(2.2 * NS * 1000 / ring_fps) if diff_mode else None)
    if printer:
        printer(f"[probe] observing {duration:.0f}s -> {out_dir}  streams={list(streams)}  errors={errors}")

    end = time.time() + duration
    next_win32 = 0.0
    try:
        while time.time() < end:
            time.sleep(0.05)
            if "win32" in streams and time.time() >= next_win32:
                streams["win32"].poll()
                next_win32 = time.time() + 0.1
            if "present" in streams:
                streams["present"].poll()
            correlator.tick(now_ns())
    except KeyboardInterrupt:
        pass
    finally:
        correlator.flush()
        # Stop UIA FIRST and let it drain: its COM callbacks must not fire while the ring / export
        # threads and their buffers are being torn down (heap-corruption race, isolated 2026-09-04).
        if "uia" in streams:
            try:
                streams["uia"].stop()
            except Exception:  # noqa: BLE001
                pass
        for name, s in streams.items():
            if name == "uia":
                continue
            try:
                s.stop()
            except Exception:  # noqa: BLE001
                pass
        ring.stop()
        ledger.flush()
        correlator.enrich_late_present()
        correlator.close()  # waits for exports
        correlator.write_final()

    manifest = build_manifest(ledger, ring, correlator, streams, errors, started_perf, started_wall, out_dir, duration)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    ledger.close()
    if printer:
        printer(json.dumps({k: manifest[k] for k in ("counts", "bytes", "semantic_by_type", "emit_latency_ms",
                                                      "coverage_gaps")}, indent=2))
    return manifest


def build_manifest(ledger: Ledger, ring: RingBuffer, corr: Correlator, streams: dict[str, Any], errors: dict[str, str],
                   started_perf: int, started_wall: int, out_dir: Path, duration: float) -> dict[str, Any]:
    counts = {src: len(ledger.by_src.get(src, [])) for src in ("win32", "uia", "screen", "present")}
    dirty_px = sum(r["dirty_px"] for r in ledger.by_src.get("screen", []))
    raw_bytes = ring.captured * ring.bytes_per_frame
    native_bytes = sum(ledger.bytes_by_src.values())
    size = streams["screen"].size if "screen" in streams else [0, 0]
    full_px = size[0] * size[1]
    gaps = corr.unexplained_changes(min_px=max(1, full_px // 200))
    lat = sorted(e["emit_latency_ms"] for e in corr.semantic)
    return {
        "schema": SCHEMA_MANIFEST, "run_dir": str(out_dir), "duration_s": duration,
        "observe_only": True, "vlm_calls": 0, "ocr_calls": 0, "automation_actions": 0,
        "clock": {"perf_ns_at_start": started_perf, "wall_ns_at_start": started_wall,
                  "note": "perf_counter_ns == QPC*100; present t_src_ns = CPU_START_QPC*100; "
                          "wgc t_src_ns = SystemRelativeTime; uia/win32 observer time only"},
        "streams": {k: v.info() for k, v in streams.items()}, "ring": ring.info(), "errors": errors,
        "counts": {**counts, "ring_frames_captured": ring.captured, "ring_frames_retained": len(ring.frames),
                   "ring_fps_actual": round(ring.captured / duration, 2)},
        "bytes": {"native_event_rows": native_bytes, "dirty_pixels_if_shipped_bgra": dirty_px * 4,
                  "native_total": native_bytes + dirty_px * 4, "raw_ring_frames": raw_bytes,
                  "raw_full_res_60fps_equiv": full_px * 4 * int(60 * duration),
                  "ratio_native_vs_ring": round((native_bytes + dirty_px * 4) / raw_bytes, 6) if raw_bytes else None,
                  "ratio_native_vs_60fps_full": round((native_bytes + dirty_px * 4) / (full_px * 4 * 60 * duration), 8)
                  if full_px else None},
        "semantic_events": len(corr.semantic),
        "semantic_by_type": {t: sum(1 for e in corr.semantic if e["event_type"] == t)
                             for t in sorted({e["event_type"] for e in corr.semantic})},
        "evidence_coverage": {
            "screen_matched": sum(1 for e in corr.semantic if e["evidence"]["screen"]["coverage"] == "matched"),
            "present_matched_live": sum(1 for e in corr.semantic if "delta_ms" in e["evidence"]["present"]
                                        and e["evidence"]["present"].get("coverage") != "matched_late"),
            "present_matched_late": sum(1 for e in corr.semantic if e["evidence"]["present"].get("coverage") == "matched_late"),
            "uia_corroborated": sum(1 for e in corr.semantic if e["evidence"].get("uia", {}).get("coverage") == "matched"),
            "replay_at_frame": sum(1 for e in corr.semantic if e["evidence"]["replay"].get("at"))},
        "emit_latency_ms": {"min": lat[0], "median": lat[len(lat) // 2], "max": lat[-1]} if lat else None,
        "inferred_claims": sum(1 for e in corr.semantic if "inferred" in e),
        "coalesced_facts": corr.coalesced_count,
        "coverage_gaps": len(gaps), "coverage_gap_samples": gaps[:10],
        "exports": corr.exports, "files": {"events": "events.jsonl", "semantic": "semantic.jsonl"},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=None, help="run dir (default watch/runs/event-probe-<ts>)")
    ap.add_argument("--ring-fps", type=float, default=10.0,
                    help="replay ring rate; stride-downscaled mss grab measured ~50 ms at 5K -> 10 fps is honest")
    ap.add_argument("--ring-scale", type=float, default=0.5)
    ap.add_argument("--ring-frames", type=int, default=150)
    ap.add_argument("--screen", choices=["auto", "wgc", "diff", "off"], default="auto")
    ap.add_argument("--disable", action="append", default=[], choices=["uia", "present", "win32"],
                    help="turn a stream off (repeatable) - for fault isolation")
    args = ap.parse_args(argv)
    out = args.out or REPO / "watch" / "runs" / f"event-probe-{time.strftime('%Y%m%d-%H%M%S')}"
    m = run(duration=args.duration, out_dir=out, ring_fps=args.ring_fps, ring_scale=args.ring_scale,
            ring_frames=args.ring_frames, screen=args.screen, disable=args.disable)
    return 0 if any(m["counts"][k] for k in ("uia", "win32", "screen")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
