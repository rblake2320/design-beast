"""Static-asset handoff: bounded Meshy retrieval, owned Blender, UE 5.8 receipts.

The free route only GETs existing provider tasks. Generation is a separate,
explicitly priced operation and is never retried automatically.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import struct
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import config

MAX_MODEL_BYTES = 50 * 1024 * 1024
TASK_TYPES = {"image-to-3d", "text-to-3d"}
TASK_ID = re.compile(r"^[a-zA-Z0-9-]{1,64}$")
GENERATION_CREDITS = 30


class AssetError(Exception):
    """Safe public error; never includes provider bodies or signed URLs."""


def atomic_json(path: Path, data: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_glb(path: Path) -> dict:
    """Reject truncated files and external dependencies before either tool opens it."""
    try:
        return _validate_glb(path)
    except AssetError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError,
            RecursionError, struct.error):
        raise AssetError("Malformed GLB structure or geometry") from None


def _validate_glb(path: Path) -> dict:
    size = path.stat().st_size
    if size < 20 or size > MAX_MODEL_BYTES:
        raise AssetError("GLB must be between 20 bytes and 50 MiB")
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != size:
        raise AssetError("Invalid or truncated GLB 2.0")
    offset, document, binary = 12, None, None
    while offset < size:
        if offset + 8 > size:
            raise AssetError("Truncated GLB chunk")
        chunk_size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if chunk_size % 4 or offset + chunk_size > size:
            raise AssetError("Invalid GLB chunk length")
        if document is None:
            if kind != 0x4E4F534A:
                raise AssetError("GLB must begin with a JSON chunk")
            try:
                document = json.loads(data[offset:offset + chunk_size])
            except (ValueError, UnicodeError):
                raise AssetError("Invalid GLB JSON") from None
        elif kind == 0x004E4942:
            if binary is not None:
                raise AssetError("GLB has multiple binary chunks")
            binary = data[offset:offset + chunk_size]
        elif kind == 0x4E4F534A:
            raise AssetError("GLB has multiple JSON chunks")
        offset += chunk_size
    if not isinstance(document, dict) or not isinstance(document.get("meshes"), list) or not document["meshes"]:
        raise AssetError("GLB has no meshes")
    if document.get("asset", {}).get("version") != "2.0":
        raise AssetError("Unsupported glTF version")
    # A self-contained asset cannot read local files or contact another host.
    for item in document.get("buffers", []) + document.get("images", []):
        if not isinstance(item, dict) or item.get("uri"):
            raise AssetError("GLB must embed all buffers and images")
    if document.get("skins") or document.get("animations"):
        raise AssetError("This static-asset workflow does not accept rigs or animation")
    if not isinstance(binary, bytes) or not binary:
        raise AssetError("GLB has no embedded geometry buffer")
    buffers, views, accessors = document.get("buffers"), document.get("bufferViews"), document.get("accessors")
    if (not isinstance(buffers, list) or len(buffers) != 1 or not isinstance(views, list)
            or not isinstance(accessors, list)):
        raise AssetError("GLB requires embedded buffers, views, and accessors")
    def integer(value, minimum=0):
        if type(value) is not int or value < minimum:
            raise AssetError("Invalid GLB integer")
        return value
    buffer_size = integer(buffers[0]["byteLength"], 1)
    if buffer_size > len(binary) or len(binary) - buffer_size > 3:
        raise AssetError("GLB buffer length does not match its binary chunk")
    for view in views:
        if not isinstance(view, dict) or view.get("buffer") != 0:
            raise AssetError("Invalid GLB buffer view")
        start = integer(view.get("byteOffset", 0))
        if start + integer(view["byteLength"], 1) > buffer_size:
            raise AssetError("GLB buffer view exceeds embedded bytes")
    def accessor(index, components, types):
        index = integer(index)
        if index >= len(accessors):
            raise AssetError("GLB accessor index is out of range")
        item = accessors[index]
        if not isinstance(item, dict) or item.get("sparse") or item.get("type") != components:
            raise AssetError("Unsupported GLB accessor")
        component = item.get("componentType")
        if component not in types:
            raise AssetError("Unsupported GLB component type")
        count = integer(item["count"], 1)
        view_index = integer(item["bufferView"])
        if view_index >= len(views):
            raise AssetError("GLB buffer view index is out of range")
        view = views[view_index]
        element = {5121: 1, 5123: 2, 5125: 4, 5126: 4}[component] * (3 if components == "VEC3" else 1)
        stride = integer(view.get("byteStride", element), element)
        local = integer(item.get("byteOffset", 0))
        if local + (count - 1) * stride + element > view["byteLength"]:
            raise AssetError("GLB accessor exceeds its buffer view")
        return count, component, view.get("byteOffset", 0) + local, stride
    triangle_count = 0
    for mesh in document["meshes"]:
        if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives"), list) or not mesh["primitives"]:
            raise AssetError("GLB mesh has no primitives")
        for primitive in mesh["primitives"]:
            if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
                raise AssetError("Static assets require triangle primitives")
            attributes = primitive.get("attributes")
            if not isinstance(attributes, dict) or "POSITION" not in attributes:
                raise AssetError("GLB primitive has no positions")
            count, _, start, stride = accessor(attributes["POSITION"], "VEC3", {5126})
            for n in range(count):
                if not all(math.isfinite(value) for value in struct.unpack_from("<fff", binary, start + n * stride)):
                    raise AssetError("GLB contains non-finite geometry")
            if "indices" in primitive:
                indices, component, begin, step = accessor(primitive["indices"], "SCALAR", {5121, 5123, 5125})
                fmt = {5121: "<B", 5123: "<H", 5125: "<I"}[component]
                if indices % 3:
                    raise AssetError("Triangle index count must be a multiple of three")
                for n in range(indices):
                    if struct.unpack_from(fmt, binary, begin + n * step)[0] >= count:
                        raise AssetError("GLB index references a missing vertex")
                triangle_count += indices // 3
            else:
                if count % 3:
                    raise AssetError("Triangle position count must be a multiple of three")
                triangle_count += count // 3
    if not triangle_count:
        raise AssetError("GLB has no triangle geometry")
    nodes = document.get("nodes")
    if not isinstance(nodes, list) or not any(isinstance(n, dict) and "mesh" in n for n in nodes):
        raise AssetError("GLB scene has no mesh nodes")
    for node in nodes:
        if not isinstance(node, dict):
            raise AssetError("Invalid GLB node")
        if "mesh" in node and integer(node["mesh"]) >= len(document["meshes"]):
            raise AssetError("GLB node references a missing mesh")
        for transform, width in (("translation", 3), ("scale", 3), ("rotation", 4), ("matrix", 16)):
            if transform in node:
                values = node[transform]
                if (not isinstance(values, list) or len(values) != width or
                        not all(type(v) in (float, int) and math.isfinite(v) for v in values)):
                    raise AssetError("GLB has an invalid node transform")
    return {"bytes": size, "sha256": hashlib.sha256(data).hexdigest(),
            "meshes": len(document["meshes"]), "triangles": triangle_count, "units": "meters"}


def meshy_key() -> str:
    key = os.environ.get("MESHY_API_KEY") or os.environ.get("BEAST_MESHY_API_KEY")
    if not key and config.get("meshy_key_file"):
        path = config.path("meshy_key_file")
        try:
            # An explicit node-local reference can reuse the existing MCP key.
            data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
            key = data["mcp_servers"]["meshy"]["env"]["MESHY_API_KEY"]
        except (OSError, ValueError, KeyError):
            raise AssetError("Meshy credential reference could not be read") from None
    if not isinstance(key, str) or not key.strip():
        raise AssetError("Meshy API key is not configured on this node")
    return key.strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Meshy:
    base = "https://api.meshy.ai/openapi/v1"
    text_base = "https://api.meshy.ai/openapi/v2"

    def __init__(self):
        self.key = meshy_key()
        self.opener = urllib.request.build_opener(NoRedirect)

    def read(self, url: str, *, data: dict | None = None, checkpoint=lambda: None,
             limit: int = 2 * 1024 * 1024, authenticated: bool = True) -> bytes:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.key
        if data is not None:
            headers["Content-Type"] = "application/json"
        checkpoint()
        req = urllib.request.Request(url, headers=headers,
                                     data=json.dumps(data).encode() if data is not None else None)
        until = time.monotonic() + 60
        try:
            with self.opener.open(req, timeout=10) as response:
                parts, count = [], 0
                while True:
                    checkpoint()
                    if time.monotonic() >= until:
                        raise AssetError("Meshy response exceeded its time budget")
                    block = response.read1(65536)
                    if not block:
                        break
                    count += len(block)
                    if count > limit:
                        raise AssetError("Meshy response exceeds the size limit")
                    parts.append(block)
            checkpoint()
            return b"".join(parts)
        except urllib.error.HTTPError as exc:
            raise AssetError(f"Meshy request rejected (HTTP {exc.code})") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise AssetError("Meshy connection failed; no automatic submission retry") from None

    def api(self, route: str, *, data=None, checkpoint=lambda: None):
        try:
            base = self.text_base if route.startswith("/text-to-3d") else self.base
            result = json.loads(self.read(base + route, data=data, checkpoint=checkpoint))
        except (ValueError, UnicodeError):
            raise AssetError("Meshy returned malformed JSON") from None
        if not isinstance(result, (dict, list)):
            raise AssetError("Meshy returned an invalid response")
        return result

    def task(self, kind: str, task_id: str, checkpoint=lambda: None):
        if kind not in TASK_TYPES or not TASK_ID.fullmatch(task_id):
            raise AssetError("Invalid Meshy task reference")
        out = self.api(f"/{kind}/{task_id}", checkpoint=checkpoint)
        if not isinstance(out, dict) or out.get("id") != task_id:
            raise AssetError("Meshy task identity mismatch")
        return out

    def download(self, task: dict, destination: Path, checkpoint=lambda: None):
        if task.get("status") != "SUCCEEDED":
            raise AssetError("Meshy task has not succeeded")
        url = task.get("model_urls", {}).get("glb", "")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "assets.meshy.ai"
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise AssetError("Meshy returned an unsupported model download host")
        # Signed URL is consumed in memory, never put in a run/status/log.
        data = self.read(url, checkpoint=checkpoint, limit=MAX_MODEL_BYTES, authenticated=False)
        temp = destination.with_suffix(".partial")
        try:
            temp.write_bytes(data)
            info = validate_glb(temp)
            os.replace(temp, destination)
            return info
        finally:
            temp.unlink(missing_ok=True)


def run_owned(command: list[str], folder: Path, log_name: str, *, env=None,
              timeout=300, checkpoint=lambda: None):
    """Cancel only this child/tree; no global editor or GPU process control."""
    checkpoint()
    started = time.monotonic()
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | 0x4
             if os.name == "nt" else 0)  # CREATE_SUSPENDED until bound to an owned job.
    with (folder / log_name).open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                env=env, creationflags=flags, start_new_session=os.name != "nt")
        close_job = None
        try:
            if os.name == "nt":
                from owned_process import resume_in_job
                close_job = resume_in_job(proc.pid)
            while proc.poll() is None:
                checkpoint()
                if time.monotonic() - started > timeout:
                    raise AssetError(f"{log_name} exceeded its time budget")
                time.sleep(.1)
            checkpoint()
            if proc.returncode:
                raise AssetError(f"{log_name} failed (exit {proc.returncode}); see retained log")
        finally:
            if close_job:
                close_job()  # Atomically kills this tree, including launcher descendants.
            if proc.poll() is None:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)


def prepare(source: Path, folder: Path, max_triangles: int, checkpoint=lambda: None):
    original = validate_glb(source)
    exe = config.path("blender")
    if not exe.is_file():
        raise AssetError("Blender is unavailable on this node")
    script = Path(__file__).parent / "bridge" / "prepare_asset.py"
    run_owned([str(exe), "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(script), "--", str(source), str(folder), str(max_triangles)],
              folder, "blender.log", checkpoint=checkpoint)
    for name in ("model.glb", "asset.fbx", "asset.blend", "preview.png", "blender-receipt.json"):
        if not (folder / name).is_file():
            raise AssetError(f"Blender did not produce {name}")
    info = json.loads((folder / "blender-receipt.json").read_text())
    exported = validate_glb(folder / "model.glb")
    if info.get("source_sha256") != original["sha256"] or not info.get("triangles"):
        raise AssetError("Blender receipt does not match its source")
    if info["triangles"] > max_triangles:
        raise AssetError("Export exceeds the selected triangle budget")
    return {"source": original, "export": exported, "blender": info}


def preflight_blender():
    exe = config.path("blender")
    if not exe.is_file():
        raise AssetError("Blender is unavailable; no provider submission was made")
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run([str(exe), "--version"], capture_output=True,
                                timeout=5, creationflags=flags)
        if result.returncode or not result.stdout.startswith(b"Blender "):
            raise AssetError("Blender version check failed; no provider submission was made")
    except (OSError, subprocess.SubprocessError):
        raise AssetError("Blender could not start; no provider submission was made") from None


def unreal_target() -> tuple[Path, Path]:
    exe = config.path("ue58_exe")
    if not exe.is_file():
        raise AssetError("Unreal 5.8 is unavailable on this node")
    build = exe.parents[2] / "Build" / "Build.version"
    try:
        version = json.loads(build.read_text())
    except (OSError, ValueError):
        raise AssetError("Unreal engine version could not be verified") from None
    if (version.get("MajorVersion"), version.get("MinorVersion")) != (5, 8):
        raise AssetError("This workflow requires Unreal 5.8")
    project = (Path(__file__).resolve().parents[1] / ".beast" / "unreal-assets"
               / "BeastAssets.uproject")
    return exe, project


def import_unreal(source: Path, folder: Path, checkpoint=lambda: None):
    validate_glb(source)
    exe, project = unreal_target()
    project.parent.mkdir(parents=True, exist_ok=True)
    expected = {"FileVersion": 3, "EngineAssociation": "5.8", "Plugins": [
        {"Name": "PythonScriptPlugin", "Enabled": True}]}
    if project.exists():
        if json.loads(project.read_text()) != expected:
            raise AssetError("Dedicated Unreal workspace has unexpected configuration")
    else:
        atomic_json(project, expected)
    script = Path(__file__).parent / "bridge" / "import_asset_ue58.py"
    receipt = folder / "unreal-receipt.json"
    if receipt.exists():
        raise AssetError("Unreal receipt already exists; start a new import job")
    env = os.environ.copy()
    env.update(BEAST_ASSET_INPUT=str(source), BEAST_ASSET_RECEIPT=str(receipt),
               BEAST_ASSET_RUN=folder.name)
    # Asset import/save is CPU-only. NullRHI avoids loading a GPU rendering workload.
    run_owned([str(exe), str(project), "-run=pythonscript", f"-script={script}",
               "-nullrhi", "-unattended", "-nop4", "-nosplash", "-stdout"],
              folder, "unreal.log", env=env, timeout=900, checkpoint=checkpoint)
    try:
        out = json.loads(receipt.read_text())
    except (OSError, ValueError):
        raise AssetError("Unreal did not produce a receiving-side receipt") from None
    if (out.get("source_sha256") != sha256(source) or out.get("run_id") != folder.name
            or not str(out.get("engine_version", "")).startswith("5.8.")
            or Path(out.get("project", "")).resolve() != project.resolve()
            or not out.get("meshes") or not out.get("reloaded")):
        raise AssetError("Unreal receipt identity or asset verification failed")
    expected_destination = "/Game/BeastAssets/Run_" + folder.name
    if out.get("destination") != expected_destination or not isinstance(out["meshes"], list):
        raise AssetError("Unreal receipt has a different asset destination")
    for mesh in out["meshes"]:
        if not isinstance(mesh, dict):
            raise AssetError("Unreal receipt has invalid mesh metadata")
        asset = mesh.get("asset", "")
        extents = mesh.get("bounds_extent_cm")
        if (not isinstance(asset, str) or not asset.startswith(expected_destination + "/")
                or ".." in asset or "\\" in asset
                or not isinstance(extents, list) or len(extents) != 3
                or not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in extents)
                or max(extents) <= 0 or type(mesh.get("lods")) is not int or mesh["lods"] < 1
                or type(mesh.get("material_slots")) is not int or mesh["material_slots"] < 0):
            raise AssetError("Unreal mesh is outside its job or has invalid geometry")
    return out
