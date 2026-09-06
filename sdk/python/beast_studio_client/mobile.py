"""Local Android observation and bounded actions shared by Beast and Vigil.

Original implementation; no PhoneClaw code or hosted services. A receipt records
what ADB returned and what was visible, not general task correctness. Callers
must supply a device serial, allowed package, and explicit action authority.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

SCHEMA = "beast.android-observation/v1"


class MobileError(ValueError):
    """Classified local mobile boundary failure."""


def _png(data: bytes) -> None:
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.width * image.height > 40_000_000:
                raise MobileError("invalid or oversized screenshot")
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise MobileError("invalid PNG screenshot") from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _json(path: Path, value: dict) -> None:
    _atomic(path, json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode())


def parse_ui(data: bytes, package: str) -> list[dict]:
    if not data or len(data) > 8_000_000 or b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise MobileError("invalid or oversized UI XML")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise MobileError("malformed UI XML") from exc
    if root.tag != "hierarchy":
        raise MobileError("UI XML must contain a hierarchy")
    nodes = []
    for node in root.iter("node"):
        row = node.attrib
        if row.get("package") != package:
            continue
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", row.get("bounds", ""))
        if not bounds:
            continue
        left, top, right, bottom = map(int, bounds.groups())
        if not (left < right <= 32768 and top < bottom <= 32768):
            continue
        nodes.append({
            "text": row.get("text", ""), "resource_id": row.get("resource-id", ""),
            "description": row.get("content-desc", ""), "package": package,
            "bounds": [left, top, right, bottom],
            "enabled": row.get("enabled") == "true",
            "clickable": row.get("clickable") == "true",
        })
    if not nodes:
        raise MobileError("allowed package has no visible bounded nodes")
    return nodes


def select(nodes: list[dict], selector: dict) -> dict:
    if (not isinstance(selector, dict) or not selector or
            set(selector) - {"text", "resource_id", "description"} or
            any(not isinstance(v, str) or not v.strip() for v in selector.values())):
        raise MobileError("selector requires exact nonempty text, resource_id or description")
    matches = [n for n in nodes if all(n.get(k) == v for k, v in selector.items())]
    if len(matches) != 1:
        raise MobileError(f"selector must resolve uniquely; found {len(matches)} nodes")
    return matches[0]


def load_observation(path: str | Path, *, serial: str, package: str,
                     max_age: float = 30) -> dict:
    if isinstance(max_age, bool) or not math.isfinite(max_age) or not 0 < max_age <= 300:
        raise MobileError("max_age must be finite and in (0, 300]")
    path = Path(path).resolve()
    if path.stat().st_size > 1_000_000:
        raise MobileError("oversized observation manifest")
    observation = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(observation, dict):
        raise MobileError("observation must be an object")
    if (observation.get("schema") != SCHEMA or observation.get("serial") != serial or
            observation.get("package") != package):
        raise MobileError("observation schema or target mismatch")
    stamp = observation.get("captured_unix")
    if (type(stamp) not in (float, int) or not math.isfinite(stamp) or
            not 0 <= time.time() - stamp <= max_age):
        raise MobileError("observation stale or timestamp invalid")
    artifacts = observation.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise MobileError("artifacts must be an object")
    ui_data = b""
    for role, name in (("ui", "ui.xml"), ("screenshot", "screen.png")):
        item = artifacts.get(role, {})
        if not isinstance(item, dict):
            raise MobileError("artifact record must be an object")
        if item.get("file") != name:
            raise MobileError("unexpected artifact path")
        artifact = (path.parent / name).resolve()
        if artifact.parent != path.parent or artifact.stat().st_size > 32_000_000:
            raise MobileError("artifact escapes bundle or exceeds size limit")
        data = artifact.read_bytes()
        if _digest(data) != item.get("sha256"):
            raise MobileError("artifact hash mismatch")
        if role == "ui":
            ui_data = data
        if role == "screenshot" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise MobileError("screenshot is not PNG")
        if role == "screenshot":
            _png(data)
    observation["nodes"] = parse_ui(ui_data, package)
    return observation


def check_observation(path: str | Path, *, serial: str, package: str,
                      selector: dict, max_age: float = 30) -> dict:
    observation = load_observation(path, serial=serial, package=package, max_age=max_age)
    node = select(observation["nodes"], selector)
    return {"schema": "beast.android-check/v1", "observation_id": observation["id"],
            "serial": serial, "package": package, "selector": selector,
            "passed": True, "node": node,
            "boundary": "Exact visible UI match; not proof of persistence or overall task completion."}


class AndroidDevice:
    def __init__(self, serial: str, package: str, *, adb: str = "adb"):
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", serial):
            raise MobileError("invalid device serial")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
            raise MobileError("invalid allowed package")
        resolved = shutil.which(adb)
        if not resolved:
            raise MobileError("ADB unavailable: install Android platform-tools or supply --adb")
        self.adb, self.serial, self.package = resolved, serial, package

    def _run(self, *args: str) -> bytes:
        try:
            result = subprocess.run([self.adb, "-s", self.serial, *args],
                                    capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MobileError(f"ADB transport failed: {type(exc).__name__}") from exc
        if result.returncode or len(result.stdout) > 32_000_000:
            raise MobileError("ADB command rejected or output oversized")
        return result.stdout

    def _ui(self) -> bytes:
        # Constant remote command arguments; no model/user shell text is executed.
        remote = "/data/local/tmp/beast-" + uuid.uuid4().hex + ".xml"
        try:
            self._run("shell", "uiautomator", "dump", remote)
            return self._run("exec-out", "cat", remote)
        finally:
            # Only the exact file allocated by this invocation; never a glob.
            self._run("shell", "rm", "-f", remote)

    def _foreground(self) -> None:
        windows = self._run("shell", "dumpsys", "window", "windows").decode("utf-8", "replace")
        focus = re.findall(r"mCurrentFocus=Window\{[^\n]*?\s([A-Za-z0-9_.]+)/[^\n]*\}", windows)
        if focus != [self.package]:
            raise MobileError("allowed package is not the uniquely focused window")

    def observe(self, root: str | Path) -> Path:
        if self._run("get-state").strip() != b"device":
            raise MobileError("device is not authorized and ready")
        started = time.time()
        clock_started = time.monotonic()
        self._foreground()
        before = self._ui()
        parse_ui(before, self.package)
        screen = self._run("exec-out", "screencap", "-p")
        after = self._ui()
        if before != after:
            raise MobileError("UI changed during capture or capture exceeded 15 seconds")
        if not screen.startswith(b"\x89PNG\r\n\x1a\n"):
            raise MobileError("ADB did not return a PNG screenshot")
        _png(screen)
        self._foreground()
        if time.monotonic() - clock_started > 15:
            raise MobileError("capture exceeded 15 seconds")
        bundle = Path(root).resolve() / str(uuid.uuid4())
        bundle.mkdir(parents=True, exist_ok=False)
        _atomic(bundle / "ui.xml", after)
        _atomic(bundle / "screen.png", screen)
        _json(bundle / "observation.json", {
            "schema": SCHEMA, "id": bundle.name, "serial": self.serial,
            "package": self.package, "captured_unix": started,
            "capture_started_unix": started, "producer": "beast-adb/v1",
            "artifacts": {"ui": {"file": "ui.xml", "sha256": _digest(after)},
                          "screenshot": {"file": "screen.png", "sha256": _digest(screen)}},
            "boundary": "Local unsigned capture; two matching UI trees bracket the screenshot, not atomic capture.",
        })
        return bundle / "observation.json"

    def tap(self, root: str | Path, selector: dict, expected: dict, *,
            allow_action: bool = False) -> dict:
        if allow_action is not True:
            raise MobileError("tap requires explicit allow_action")
        clock_started = time.monotonic()
        before_path = self.observe(root)
        before = load_observation(before_path, serial=self.serial, package=self.package)
        node = select(before["nodes"], selector)
        # Validate the expected selector even if it is not visible yet.
        try:
            select([], expected)
        except MobileError as exc:
            if "found 0 nodes" not in str(exc):
                raise
        if not node["enabled"] or not node["clickable"]:
            raise MobileError("target is not enabled and clickable")
        if self._ui() != (before_path.parent / "ui.xml").read_bytes():
            raise MobileError("UI changed before action; reinspect")
        self._foreground()
        if time.monotonic() - clock_started > 20:
            raise MobileError("action observation expired during guards")
        action_id = str(uuid.uuid4())
        receipt_path = before_path.parent / "action.json"
        receipt = {"schema": "beast.android-action/v1", "id": action_id,
                   "serial": self.serial, "package": self.package, "action": "tap",
                   "selector": selector, "expected": expected,
                   "before": str(before_path), "state": "outcome_unknown",
                   "replay": "never_automatically_reissue", "success": False}
        # Durable intent BEFORE any side effect. A crash leaves outcome_unknown.
        _json(receipt_path, receipt)
        left, top, right, bottom = node["bounds"]
        try:
            if time.monotonic() - clock_started > 20:
                raise MobileError("action observation expired before dispatch")
            self._run("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
            after_path = self.observe(root)
            result = check_observation(after_path, serial=self.serial, package=self.package,
                                       selector=expected)
            receipt.update(state="postcondition_observed", success=True,
                           after=str(after_path), check=result)
        except (MobileError, OSError, ValueError) as exc:
            receipt["error"] = str(exc)
        _json(receipt_path, receipt)
        return {**receipt, "receipt_path": str(receipt_path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["observe", "check", "tap"])
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--output", default="mobile-evidence")
    parser.add_argument("--observation")
    parser.add_argument("--selector", help='Exact selector JSON, e.g. {"text":"Settings"}')
    parser.add_argument("--expected", help="Post-tap selector JSON")
    parser.add_argument("--allow-action", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_observation(args.observation, serial=args.serial, package=args.package,
                                       selector=json.loads(args.selector or "{}"))
        else:
            device = AndroidDevice(args.serial, args.package, adb=args.adb)
            if args.command == "observe":
                result = {"observation": str(device.observe(args.output))}
            else:
                result = device.tap(args.output, json.loads(args.selector or "{}"),
                                    json.loads(args.expected or "{}"), allow_action=args.allow_action)
        print(json.dumps(result, allow_nan=False))
        return 0 if result.get("success", True) else 1
    except (MobileError, OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
