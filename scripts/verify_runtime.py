#!/usr/bin/env python3
"""Exercise the actual Studio process and installed Python wheel, without GPU jobs."""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tts", action="store_true", help="exercise installed local Kokoro model")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, action):
        started = time.monotonic()
        try:
            detail = action()
            checks.append({"scenario": name, "status": "Worked", "detail": detail,
                           "seconds": round(time.monotonic() - started, 4)})
        except Exception as error:
            checks.append({"scenario": name, "status": "Failed", "error": str(error),
                           "seconds": round(time.monotonic() - started, 4)})

    with tempfile.TemporaryDirectory(prefix="beast-runtime-") as scratch:
        port_file = Path(scratch) / "port.txt"
        code = (
            "import socket,sys; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[1]); import jobs; "
            "jobs.DB_PATH=Path(sys.argv[2]); import server,uvicorn; "
            "s=socket.socket(); s.bind(('127.0.0.1',0)); "
            "Path(sys.argv[3]).write_text(str(s.getsockname()[1])); "
            "uvicorn.Server(uvicorn.Config(server.app,log_level='warning')).run(sockets=[s])"
        )
        with (args.output / "server.log").open("w", encoding="utf-8") as log:
            child = subprocess.Popen(
                [sys.executable, "-c", code, str(REPO / "studio"),
                 str(Path(scratch) / "jobs.db"), str(port_file)], stdout=log, stderr=log,
                cwd=REPO)
            try:
                deadline = time.monotonic() + 30
                while True:
                    if child.poll() is not None:
                        raise RuntimeError(f"Studio exited with {child.returncode}; see server.log")
                    if port_file.exists():
                        url = f"http://127.0.0.1:{port_file.read_text()}"
                        try:
                            if requests.get(url + "/api/health", timeout=0.5).ok:
                                break
                        except requests.RequestException:
                            pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Studio startup exceeded 30 seconds")
                    time.sleep(0.05)

                def health():
                    from beast_studio_client import BeastStudioClient
                    import beast_studio_client
                    location = Path(beast_studio_client.__file__).resolve()
                    assert not location.is_relative_to(REPO / "sdk"), "SDK must be wheel-installed"
                    result = BeastStudioClient(url).health()
                    assert result["ok"] and result["db"]
                    return {"response": result, "sdk_source": "installed wheel"}

                check("installed Python wheel talks to actual Studio", health)

                def interface():
                    response = requests.get(url, timeout=5)
                    assert response.ok and "beast" in response.text.lower(), (
                        f"HTTP {response.status_code}; expected Studio HTML")
                    return {"status": response.status_code, "html_bytes": len(response.content)}

                check("Studio serves browser interface", interface)

                def upload():
                    raw = io.BytesIO()
                    Image.new("RGB", (64, 64), (12, 80, 140)).save(raw, "PNG")
                    response = requests.post(url + "/api/upload", json={
                        "name": "runtime.png", "data": base64.b64encode(raw.getvalue()).decode()}, timeout=5)
                    assert response.ok, response.text
                    name = response.json()["file"]
                    received = requests.get(url + "/uploads/" + name, timeout=5)
                    assert received.ok
                    image = Image.open(io.BytesIO(received.content))
                    assert image.size == (64, 64)
                    assert image.getpixel((0, 0)) == (12, 80, 140)
                    return {"decoded_size": image.size, "pixel": image.getpixel((0, 0))}

                check("image upload and HTTP download preserve pixels", upload)

                def invalid():
                    response = requests.post(url + "/api/upload", json={
                        "name": "invalid.png", "data": "bm90YW5pbWFnZQ=="}, timeout=5)
                    assert response.status_code == 422, response.text
                    response = requests.post(url + "/api/run", json={"brief": "ab"}, timeout=5)
                    assert response.status_code == 422, response.text
                    response = requests.get(url + "/api/run/nonexistent", timeout=5)
                    assert response.status_code == 404, response.text
                    return {"bad_image": 422, "bad_brief": 422, "unknown_job": 404}

                check("invalid inputs fail without submitting generation jobs", invalid)

                if args.tts:
                    def speech():
                        import soundfile as sf
                        response = requests.post(url + "/api/tts", json={
                            "text": "Beast Studio runtime verification.", "voice": "af_heart"}, timeout=90)
                        assert response.ok, response.text
                        audio = requests.get(url + response.json()["url"], timeout=5)
                        audio.raise_for_status()
                        samples, rate = sf.read(io.BytesIO(audio.content))
                        assert len(samples) > rate and max(abs(samples)) > 0.01
                        (args.output / "speech.wav").write_bytes(audio.content)
                        return {"sample_rate": rate, "samples": len(samples),
                                "duration_seconds": round(len(samples) / rate, 3)}
                    check("updated Kokoro synthesizes decodable local speech", speech)
            except Exception as error:
                checks.append({"scenario": "Studio startup", "status": "Failed", "error": str(error)})
            finally:
                # The Windows venv launcher can own a second Python process;
                # terminate the whole tree we started, not just the launcher.
                if os.name == "nt" and child.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                                   capture_output=True, timeout=10, check=True)
                elif child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)

    receipt = {"ok": bool(checks) and all(c["status"] == "Worked" for c in checks),
               "python": sys.version.split()[0], "checks": checks}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
