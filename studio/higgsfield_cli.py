"""Native Higgsfield boundary: one paid attempt, retained intent, verified artifact.

The caller owns spending authorization. An existing output/receipt is never
reissued, even after failure; reconcile the provider job before any new request.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit
import uuid
import warnings

from PIL import Image

# Observed in retained provider receipts; never accept arbitrary *.cloudfront.net.
PROVIDER_HOSTS = frozenset({"d8j0ntlcm91z4.cloudfront.net"})
MAX_BYTES = 128 * 1024 * 1024
MAX_PIXELS = 64_000_000
EXTRA_FLAGS = frozenset({"--aspect_ratio", "--resolution", "--quality", "--image",
                         "--start-image", "--end-image", "--duration"})


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def resolve_cli():
    """Resolve npm's real native executable, never execute cmd/ps1 via a shell."""
    found = shutil.which("higgsfield")
    candidates = []
    if found:
        path = Path(found)
        if path.suffix.lower() not in {".cmd", ".bat", ".ps1", ".js"}:
            candidates.append(path)
        candidates.append(path.parent / "node_modules/@higgsfield/cli/vendor/hf.exe")
    if os.name == "nt" and os.environ.get("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "npm/node_modules/@higgsfield/cli/vendor/hf.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise FileNotFoundError("native Higgsfield executable unavailable")


def parse_job(text):
    """Observed get/wait object contract; create may return one such object in an array."""
    _require(isinstance(text, str) and len(text) <= 2_000_000, "invalid CLI output size")
    def pairs(items):
        obj = {}
        for key, value in items:
            _require(key not in obj, "duplicate CLI JSON key")
            obj[key] = value
        return obj
    data = json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    if isinstance(data, list):
        _require(len(data) == 1, "expected exactly one provider job")
        data = data[0]
    _require(isinstance(data, dict), "expected a provider job object")
    _require(isinstance(data.get("id"), str), "missing provider job ID")
    _require(str(uuid.UUID(data["id"])) == data["id"].lower(), "invalid provider job ID")
    for key in ("status", "job_type"):
        _require(isinstance(data.get(key), str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", data[key]),
                 "invalid provider metadata")
    return data


def checked_url(url):
    _require(isinstance(url, str) and len(url) <= 8192 and not any(ord(c) < 33 for c in url),
             "invalid provider URL")
    parts = urlsplit(url)
    _require(parts.scheme == "https" and parts.hostname in PROVIDER_HOSTS and
             parts.port in (None, 443) and not parts.username and not parts.password and
             not parts.fragment and "\\" not in url, "unapproved provider URL")
    return parts


def _connection(parts):
    # Pin a validated public DNS answer. No proxy, DNS re-resolution, or redirect.
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    _require(bool(addresses), "provider DNS returned no addresses")
    _require(all(ipaddress.ip_address(row[4][0]).is_global for row in addresses),
             "provider DNS returned nonpublic address")
    address = addresses[0][4]
    raw = socket.socket(addresses[0][0], socket.SOCK_STREAM)
    raw.settimeout(15)
    try:
        raw.connect(address)
        secure = ssl.create_default_context().wrap_socket(raw, server_hostname=parts.hostname)
    except BaseException:
        raw.close()
        raise
    secure.settimeout(10)
    conn = http.client.HTTPSConnection(parts.hostname, timeout=10)
    conn.sock = secure
    return conn


def download(url, partial):
    parts = checked_url(url)
    connection = _connection(parts)
    started = time.monotonic()
    try:
        connection.request("GET", urlunsplit(("", "", parts.path or "/", parts.query, "")),
                           headers={"Accept-Encoding": "identity", "User-Agent": "DesignBeast/1"})
        response = connection.getresponse()
        _require(response.status == 200, "provider download rejected (redirects are disabled)")
        _require(response.getheader("Content-Encoding", "identity").lower() in ("identity", ""),
                 "encoded downloads are unsupported")
        length = response.getheader("Content-Length")
        expected = int(length) if length is not None else None
        _require(expected is None or 0 < expected <= MAX_BYTES, "invalid download length")
        size = 0
        with Path(partial).open("xb") as handle:
            while True:
                _require(time.monotonic() - started <= 90, "download deadline exceeded")
                # read1 performs at most one socket read: a slow trickle cannot
                # keep filling a 64KB read forever while bypassing our deadline.
                chunk = response.read1(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                _require(size <= MAX_BYTES, "download exceeds byte limit")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        _require(size > 0 and (expected is None or size == expected), "truncated or empty download")
        return size
    finally:
        connection.close()


def _validate_media(path, suffix):
    if suffix == ".mp4":
        ffprobe = shutil.which("ffprobe")
        _require(bool(ffprobe), "ffprobe is required to validate video")
        result = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                                 "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                                capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _require(result.returncode == 0, "invalid video artifact")
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        _require(any(s.get("codec_type") == "video" and s.get("width", 0) > 0 and
                     s.get("height", 0) > 0 for s in streams), "video stream missing")
        _require(0 < float(data["format"]["duration"]) <= 3600, "invalid video duration")
        return {"media_type": "video"}
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            _require(image.format in {"PNG", "JPEG", "WEBP"} and
                     0 < image.width * image.height <= MAX_PIXELS, "unsupported image")
            image.verify()
        with Image.open(path) as image:
            image.load()
            return {"media_type": "image", "dimensions": list(image.size), "format": image.format}


def _write_receipt(path, data, *, first=False):
    target = path if first else path.with_name(path.name + ".tmp")
    with target.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    if not first:
        for attempt in range(5):
            try:
                os.replace(target, path)
                break
            except PermissionError as exc:
                if attempt == 4 or getattr(exc, "winerror", None) not in (5, 32, 33):
                    raise
                time.sleep(0.02 * (2 ** attempt))


def generate(model, prompt, out_file, extra=None):
    output = Path(out_file).absolute()
    receipt_path = output.with_name(output.name + ".higgsfield.json")
    partial = output.with_name(output.name + ".higgsfield.part")
    receipt = {"schema": "beast.higgsfield.execution/v1", "transport": "native_cli",
               "status": "outcome_unknown", "ok": False,
               "started_at": datetime.now(timezone.utc).isoformat(), "output": output.name}
    try:
        _require(isinstance(model, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", model), "invalid model")
        _require(isinstance(prompt, str) and 0 < len(prompt) <= 100_000 and "\0" not in prompt,
                 "invalid prompt")
        extra = [] if extra is None else extra
        _require(isinstance(extra, list) and len(extra) % 2 == 0 and len(extra) <= 16,
                 "invalid extra flags")
        _require(all(extra[i] in EXTRA_FLAGS and isinstance(extra[i + 1], str) and
                     "\0" not in extra[i + 1] for i in range(0, len(extra), 2)), "unsupported extra flags")
        _require(output.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4"}, "unsupported output")
        _require(output.parent.is_dir(), "output parent missing")
        if output.exists() or receipt_path.exists() or partial.exists():
            return {"error": "Existing Higgsfield output or intent; reconcile before any new submission.",
                    "outcome": "outcome_unknown", "receipt": receipt_path.name}
        cli = resolve_cli()
        if output.suffix.lower() == ".mp4":
            _require(bool(shutil.which("ffprobe")), "ffprobe required before video submission")
        request = json.dumps({"model": model, "prompt": prompt, "extra": extra}, sort_keys=True)
        receipt.update(model=model, request_sha256=hashlib.sha256(request.encode()).hexdigest())
        _write_receipt(receipt_path, receipt, first=True)
    except (OSError, ValueError, TypeError):
        return {"error": "Higgsfield preflight rejected or native CLI unavailable; no submission made.",
                "outcome": "not_submitted"}
    # Everything after intent creation is conservatively unknown until proven.
    try:
        command = [cli, "generate", "create", model, "--prompt", prompt,
                   "--wait", "--wait-timeout", "15m", "--json"] + extra
        try:
            process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                     timeout=1000, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            receipt["status"] = "not_submitted"
            raise
        receipt["exit_code"] = process.returncode
        if process.returncode != 0:
            # Keep a usable identity if the failed command did emit one, but
            # never interpret even completed JSON on a failed exit as success.
            try:
                known = parse_job(process.stdout)
                receipt.update(job_id=known["id"], provider_status=known["status"], job_type=known["job_type"])
            except (ValueError, TypeError, AttributeError, RecursionError):
                pass  # No reliable job identity; unknown receipt still retained.
        _require(process.returncode == 0, "CLI exit unsuccessful")
        job = parse_job(process.stdout)
        receipt.update(job_id=job["id"], provider_status=job["status"], job_type=job["job_type"])
        _write_receipt(receipt_path, receipt)
        _require(job["status"] == "completed", "provider job is not completed")
        parts = checked_url(job.get("result_url"))
        # Query strings may carry bearer signatures. Preserve only their hash.
        public_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        receipt.update(status="provider_completed_artifact_pending", result_url=public_url,
                       result_url_sha256=hashlib.sha256(job["result_url"].encode()).hexdigest())
        _write_receipt(receipt_path, receipt)
        size = download(job["result_url"], partial)
        media = _validate_media(partial, output.suffix.lower())
        receipt.update(artifact_sha256=_sha(partial), artifact_bytes=size, **media)
        # Same-directory hard-link publish is atomic and refuses an existing target.
        os.link(partial, output)
        partial.unlink()
        receipt.update(status="completed", ok=True)
        _write_receipt(receipt_path, receipt)
        return {"url": public_url, "file": output.name, "job_id": job["id"],
                "source": "higgsfield:native_cli", "receipt": receipt_path.name,
                "sha256": receipt["artifact_sha256"]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError,
            subprocess.SubprocessError, http.client.HTTPException,
            Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        receipt["ok"] = False
        if receipt["status"] == "completed":
            receipt["status"] = "outcome_unknown"
        receipt["error_type"] = type(exc).__name__
        try:
            _write_receipt(receipt_path, receipt)
        except OSError:
            pass  # Original write-ahead intent remains; never replay this request.
        result = {"error": "Higgsfield result not verified; inspect receipt and reconcile provider job before retrying.",
                  "outcome": receipt["status"], "receipt": receipt_path.name}
        if "exit_code" in receipt:
            result["exit_code"] = receipt["exit_code"]
        return result
