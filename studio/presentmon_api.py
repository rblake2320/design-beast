"""ctypes client for the Intel PresentMon 2.x service API (PresentMonAPI2).

Why this exists: the PresentMon *console* app opens its own ETW trace, which needs
elevation or the "Performance Log Users" group. The PresentMon *shared service*
(PresentMonService.exe, installed by ``winget install Intel.PresentMon``, runs as
SYSTEM) already owns a trace; any user-mode client can ask it over a named pipe for
per-frame events and windowed statistics. Verified on this box 2026-09-04 from a
non-elevated Python: ``pmOpenSession`` succeeded, dwm.exe reported 164 fps, and GPU
temperature / power / clock / utilisation / VRAM came back for the RTX 5090.
Fan speed is NOT served for NVIDIA adapters (Intel-only metric) - use nvidia-smi.

Enum values are parsed from the SDK header the installer dropped next to the DLL,
so they always match the installed service instead of a vendored copy.
"""

from __future__ import annotations

import ctypes
import os
import re
import struct
from ctypes import (POINTER, Structure, byref, c_char, c_char_p, c_double, c_int, c_size_t,
                    c_uint8, c_uint16, c_uint32, c_uint64, c_void_p)
from pathlib import Path
from typing import Any, Iterable, NamedTuple

SDK_DIR = Path(r"C:\Program Files\Intel\PresentMon\SDK")
SERVICE_DIR = Path(r"C:\Program Files\Intel\PresentMonSharedService")
INSTALL_FIX = "winget install Intel.PresentMon (installs the shared service + SDK header)"
_ENUMS_WANTED = ("PM_STATUS", "PM_METRIC", "PM_STAT", "PM_DEVICE_TYPE", "PM_DEVICE_VENDOR",
                 "PM_PRESENT_MODE", "PM_GRAPHICS_RUNTIME", "PM_FRAME_TYPE")


def find_dll() -> Path | None:
    for candidate in (SDK_DIR / "PresentMonAPI2Loader.dll", SERVICE_DIR / "PresentMonAPI2.dll"):
        if candidate.exists():
            return candidate
    return None


def find_header() -> Path | None:
    header = SDK_DIR / "PresentMonAPI.h"
    return header if header.exists() else None


def load_enums(header: Path) -> dict[str, dict[str, int]]:
    src = header.read_text(encoding="utf-8", errors="replace")
    out: dict[str, dict[str, int]] = {}
    for name in _ENUMS_WANTED:
        m = re.search(r"enum\s+%s\s*\{(.*?)\}" % name, src, re.S)
        if not m:
            raise RuntimeError(f"enum {name} not found in {header}")
        body = re.sub(r"//.*", "", m.group(1))
        names = [t.strip() for t in body.split(",") if t.strip()]
        out[name] = {n: i for i, n in enumerate(names)}
    return out


# ------------------------------------------------------------------ C structures
class QueryElement(Structure):
    _fields_ = [("metric", c_int), ("stat", c_int), ("deviceId", c_uint32),
                ("arrayIndex", c_uint32), ("dataOffset", c_uint64), ("dataSize", c_uint64)]


class _Str(Structure):
    _fields_ = [("pData", c_char_p)]


class _ObjArray(Structure):
    _fields_ = [("pData", POINTER(c_void_p)), ("size", c_size_t)]


class _Luid(Structure):
    _fields_ = [("pData", c_void_p), ("size", c_uint32)]


class _Device(Structure):
    _fields_ = [("id", c_uint32), ("type", c_int), ("vendor", c_int),
                ("pName", POINTER(_Str)), ("pLuid", POINTER(_Luid))]


class _Root(Structure):
    _fields_ = [("pMetrics", POINTER(_ObjArray)), ("pEnums", POINTER(_ObjArray)),
                ("pDevices", POINTER(_ObjArray)), ("pUnits", POINTER(_ObjArray))]


class _Version(Structure):
    _fields_ = [("major", c_uint16), ("minor", c_uint16), ("patch", c_uint16),
                ("tag", c_char * 22), ("hash", c_char * 8), ("config", c_char * 4)]


class Element(NamedTuple):
    """One query column: record key, PM_METRIC_* name, PM_STAT_* name, device id."""
    key: str
    metric: str
    stat: str = "PM_STAT_NONE"
    device: int = 0


class PresentMonError(RuntimeError):
    def __init__(self, call: str, status: str) -> None:
        super().__init__(f"{call} -> {status}")
        self.call, self.status = call, status


# ------------------------------------------------------------------ session
class Session:
    """One connection to the PresentMon service. Use as a context manager."""

    def __init__(self, dll_path: Path | None = None, header_path: Path | None = None) -> None:
        dll_path = dll_path or find_dll()
        header_path = header_path or find_header()
        if dll_path is None or header_path is None:
            raise FileNotFoundError(f"PresentMon SDK not installed: {INSTALL_FIX}")
        self.dll_path, self.header_path = dll_path, header_path
        self.enums = load_enums(header_path)
        self._status_name = {v: k for k, v in self.enums["PM_STATUS"].items()}
        self._dll = ctypes.WinDLL(str(dll_path))
        self._handle = c_void_p()
        self._tracked: set[int] = set()

    # -- plumbing
    def _call(self, name: str, *args: Any, ok: Iterable[str] = ("PM_STATUS_SUCCESS",)) -> str:
        status = self._status_name.get(getattr(self._dll, name)(*args), "PM_STATUS_UNKNOWN")
        if status not in ok:
            raise PresentMonError(name, status)
        return status

    def metric(self, name: str) -> int:
        return self.enums["PM_METRIC"][name]

    def stat(self, name: str) -> int:
        return self.enums["PM_STAT"][name]

    def enum_name(self, enum: str, value: int) -> str:
        for k, v in self.enums[enum].items():
            if v == value:
                return k.replace(enum + "_", "")
        return str(value)

    # -- lifecycle
    def open(self, telemetry_ms: int = 250) -> "Session":
        self._call("pmOpenSession", byref(self._handle))
        self._call("pmSetTelemetryPollingPeriod", self._handle, c_uint32(0), c_uint32(telemetry_ms))
        return self

    def close(self) -> None:
        if self._handle.value:
            for pid in list(self._tracked):
                self.untrack(pid)
            self._dll.pmCloseSession(self._handle)
            self._handle = c_void_p()

    def __enter__(self) -> "Session":
        return self.open() if not self._handle.value else self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- introspection
    def version(self) -> str:
        v = _Version()
        self._call("pmGetApiVersion", byref(v))
        return f"{v.major}.{v.minor}.{v.patch} {v.config.decode()} {v.hash.decode()}".strip()

    def devices(self) -> list[dict[str, Any]]:
        root = POINTER(_Root)()
        self._call("pmGetIntrospectionRoot", self._handle, byref(root))
        try:
            arr = root.contents.pDevices.contents
            out = []
            for i in range(arr.size):
                d = ctypes.cast(arr.pData[i], POINTER(_Device)).contents
                out.append({"id": d.id, "type": self.enum_name("PM_DEVICE_TYPE", d.type),
                            "vendor": self.enum_name("PM_DEVICE_VENDOR", d.vendor),
                            "name": d.pName.contents.pData.decode(errors="replace")})
            return out
        finally:
            self._dll.pmFreeIntrospectionRoot(root)

    def gpu_device_id(self, prefer: str | None = None) -> int | None:
        adapters = [d for d in self.devices() if d["type"] == "GRAPHICS_ADAPTER"]
        if prefer:
            for d in adapters:
                if prefer.lower() in d["name"].lower():
                    return d["id"]
        discrete = [d for d in adapters if d["vendor"] != "AMD" or "Radeon(TM) Graphics" not in d["name"]]
        return (discrete or adapters)[0]["id"] if adapters else None

    # -- tracking
    def track(self, pid: int) -> None:
        self._call("pmStartTrackingProcess", self._handle, c_uint32(pid),
                   ok=("PM_STATUS_SUCCESS", "PM_STATUS_ALREADY_TRACKING_PROCESS"))
        self._tracked.add(pid)

    def untrack(self, pid: int) -> None:
        self._dll.pmStopTrackingProcess(self._handle, c_uint32(pid))
        self._tracked.discard(pid)

    @property
    def tracked(self) -> frozenset[int]:
        return frozenset(self._tracked)

    # -- queries
    def _elements(self, spec: list[Element]) -> Any:
        arr = (QueryElement * len(spec))()
        for i, e in enumerate(spec):
            arr[i] = QueryElement(self.metric(e.metric), self.stat(e.stat), e.device, 0, 0, 0)
        return arr

    def _register(self, kind: str, spec: list[Element], **kw: Any) -> tuple[list[Element], list[Element], Any, Any]:
        """Register; on QUERY_MALFORMED drop the individually rejected elements and retry."""
        accepted, rejected = list(spec), []
        while accepted:
            arr, handle = self._elements(accepted), c_void_p()
            status = self._try_register(kind, arr, len(accepted), handle, **kw)
            if status == "PM_STATUS_SUCCESS":
                return accepted, rejected, arr, handle
            if status != "PM_STATUS_QUERY_MALFORMED":
                raise PresentMonError(f"pmRegister{kind}Query", status)
            keep = []
            for e in accepted:
                one, h1 = self._elements([e]), c_void_p()
                if self._try_register(kind, one, 1, h1, **kw) == "PM_STATUS_SUCCESS":
                    getattr(self._dll, f"pmFree{kind}Query")(h1)
                    keep.append(e)
                else:
                    rejected.append(e)
            if len(keep) == len(accepted):  # nothing individually bad yet combined fails
                raise PresentMonError(f"pmRegister{kind}Query", "PM_STATUS_QUERY_MALFORMED")
            accepted = keep
        raise PresentMonError(f"pmRegister{kind}Query", "all elements rejected")

    def _try_register(self, kind: str, arr: Any, n: int, handle: Any, **kw: Any) -> str:
        if kind == "Dynamic":
            code = self._dll.pmRegisterDynamicQuery(self._handle, byref(handle), arr, c_uint64(n),
                                                    c_double(kw["window_ms"]), c_double(kw["offset_ms"]))
        else:
            code = self._dll.pmRegisterFrameQuery(self._handle, byref(handle), arr, c_uint64(n),
                                                  byref(kw["blob_size"]))
        return self._status_name.get(code, "PM_STATUS_UNKNOWN")

    def dynamic_query(self, spec: list[Element], *, window_ms: float = 1000.0,
                      offset_ms: float = 1000.0) -> "DynamicQuery":
        accepted, rejected, arr, handle = self._register("Dynamic", spec, window_ms=window_ms, offset_ms=offset_ms)
        return DynamicQuery(self, handle, accepted, rejected, arr)

    def frame_query(self, spec: list[Element]) -> "FrameQuery":
        blob = c_uint32(0)
        accepted, rejected, arr, handle = self._register("Frame", spec, blob_size=blob)
        return FrameQuery(self, handle, accepted, rejected, arr, blob.value)


def _decode(buf: Any, base: int, accepted: list[Element], arr: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for e, ce in zip(accepted, arr):
        raw = bytes(buf[base + ce.dataOffset: base + ce.dataOffset + ce.dataSize])
        if ce.dataSize == 260:
            out[e.key] = raw.split(b"\0")[0].decode(errors="replace")
        elif ce.dataSize == 8:
            out[e.key] = struct.unpack("<d", raw)[0]
        elif ce.dataSize == 4:
            out[e.key] = struct.unpack("<I", raw)[0]
        elif ce.dataSize == 1:
            out[e.key] = bool(raw[0])
        else:
            out[e.key] = raw.hex()
    return out


class DynamicQuery:
    """Windowed statistics (avg / p99 / max ...) per swap chain of a tracked pid."""

    def __init__(self, session: Session, handle: Any, accepted: list[Element],
                 rejected: list[Element], arr: Any) -> None:
        self.session, self._handle, self.accepted, self.rejected, self._arr = session, handle, accepted, rejected, arr
        self.blob_size = sum(int(e.dataSize) for e in arr)
        self._buf = (c_uint8 * (self.blob_size * 8))()

    def poll(self, pid: int) -> list[dict[str, Any]]:
        n = c_uint32(8)
        self.session._call("pmPollDynamicQuery", self._handle, c_uint32(pid), self._buf, byref(n))
        return [_decode(self._buf, i * self.blob_size, self.accepted, self._arr) for i in range(n.value)]

    def close(self) -> None:
        if self._handle.value:
            self.session._dll.pmFreeDynamicQuery(self._handle)
            self._handle = c_void_p()


class FrameQuery:
    """Per-frame events of a tracked pid since the last consume() - the honest signal."""

    def __init__(self, session: Session, handle: Any, accepted: list[Element],
                 rejected: list[Element], arr: Any, blob_size: int, max_frames: int = 8192) -> None:
        self.session, self._handle, self.accepted, self.rejected, self._arr = session, handle, accepted, rejected, arr
        self.blob_size, self.max_frames = blob_size, max_frames
        self._buf = (c_uint8 * (blob_size * max_frames))()

    def consume(self, pid: int) -> list[dict[str, Any]]:
        n = c_uint32(self.max_frames)
        self.session._call("pmConsumeFrames", self._handle, c_uint32(pid), self._buf, byref(n))
        return [_decode(self._buf, i * self.blob_size, self.accepted, self._arr) for i in range(n.value)]

    def close(self) -> None:
        if self._handle.value:
            self.session._dll.pmFreeFrameQuery(self._handle)
            self._handle = c_void_p()


# ------------------------------------------------------------------ win32 process helpers
def exe_name(pid: int) -> str | None:
    k32 = ctypes.windll.kernel32
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        buf, size = ctypes.create_unicode_buffer(1024), c_uint32(1024)
        if not k32.QueryFullProcessImageNameW(handle, 0, buf, byref(size)):
            return None
        return buf.value.rsplit("\\", 1)[-1]
    finally:
        k32.CloseHandle(handle)


def foreground_pid() -> tuple[int, str | None]:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = c_uint32()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    return pid.value, process_name(pid.value)


class _ProcessEntry(Structure):
    _fields_ = [("dwSize", c_uint32), ("cntUsage", c_uint32), ("th32ProcessID", c_uint32),
                ("th32DefaultHeapID", c_void_p), ("th32ModuleID", c_uint32), ("cntThreads", c_uint32),
                ("th32ParentProcessID", c_uint32), ("pcPriClassBase", c_int), ("dwFlags", c_uint32),
                ("szExeFile", ctypes.c_wchar * 260)]


def snapshot() -> list[tuple[int, str]]:
    """(pid, exe) for every process - works for protected ones (dwm.exe) unlike OpenProcess."""
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    out: list[tuple[int, str]] = []
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(_ProcessEntry)
        ok = k32.Process32FirstW(snap, byref(entry))
        while ok:
            out.append((entry.th32ProcessID, entry.szExeFile))
            ok = k32.Process32NextW(snap, byref(entry))
    finally:
        k32.CloseHandle(snap)
    return out


def process_name(pid: int) -> str | None:
    """exe name via OpenProcess, falling back to the Toolhelp snapshot for protected processes."""
    return exe_name(pid) or next((name for p, name in snapshot() if p == pid), None)


def pids_by_name(names: Iterable[str]) -> list[tuple[int, str]]:
    wanted = {n.lower() for n in names}
    return [(pid, name) for pid, name in snapshot() if name.lower() in wanted and pid != os.getpid()]
