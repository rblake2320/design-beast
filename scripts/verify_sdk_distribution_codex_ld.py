"""Build and exercise installed SDKs against a disposable real Studio server.

No inference, GPU operation, paid provider, or replacement HTTP implementation.
The process uses this checkout's SQLite database and uploads, never a live clone.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


BOOTSTRAP = r'''
import asyncio, json, pathlib, sys
repo, ready, stop = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(repo / "studio"))
import server, uvicorn
async def main():
    owner = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=0, log_level="warning"))
    running = asyncio.create_task(owner.serve())
    while not owner.started:
        if running.done():
            await running
            raise RuntimeError("Server exited before readiness")
        await asyncio.sleep(.02)
    port = owner.servers[0].sockets[0].getsockname()[1]
    ready.write_text(json.dumps({"url": f"http://127.0.0.1:{port}", "db": str(server.jobs.DB_PATH), "pid": __import__("os").getpid()}))
    while not running.done():
        if stop.exists():
            owner.should_exit = True
        await asyncio.sleep(.05)
    await running
asyncio.run(main())
'''

PYTHON_PROBE = r'''
import base64, hashlib, importlib.metadata, json, pathlib, sys
from beast_studio_client import BeastStudioClient, BeastStudioError
import beast_studio_client
url, png, output = sys.argv[1:]
rows = []
def check(name, action):
    try:
        actual = action()
        rows.append({"name": name, "status": "worked", "actual": actual})
    except Exception as exc:
        rows.append({"name": name, "status": "failed", "error": str(exc), "type": type(exc).__name__})
def require(test, message):
    if not test: raise AssertionError(message)
    return message
c = BeastStudioClient(base_url=url, timeout=3)
check("wheel_import", lambda: require(pathlib.Path(beast_studio_client.__file__).is_relative_to(pathlib.Path(sys.prefix)), "import belongs to installed consumer"))
check("health", lambda: require(c.health()["db"] is True, "real SQLite healthy"))
check("recipes", lambda: require(len(c.recipes()) > 0, "real recipe files returned"))
check("cloud_disabled_registry", lambda: require(all(b["hosting"] == "local" for b in c.registry(kind="image", allow_cloud=False)["eligible"]), "only local backends eligible"))
check("runs_empty", lambda: require(c.runs() == [], "no source jobs inherited"))
check("ledger", lambda: require(c.ledger_verify()["ok"] is True, "real empty ledger accepted"))
raw = pathlib.Path(png).read_bytes()
def upload():
    name = c.upload("distribution-python.png", "data:image/png;base64," + base64.b64encode(raw).decode())["file"]
    response = c.session.get(url + "/uploads/" + name, timeout=3)
    require(response.status_code == 200 and response.content == raw, "uploaded bytes served unchanged")
    return {"file": name, "sha256": hashlib.sha256(response.content).hexdigest()}
check("upload_and_download", upload)
def duplicate_names():
    second = pathlib.Path(png).with_name("owned2.png").read_bytes()
    one = c.upload("same-name.png", base64.b64encode(raw).decode())["file"]
    two = c.upload("same-name.png", base64.b64encode(second).decode())["file"]
    require(one != two, "each upload needs its own immutable URI")
    for name, content in ((one, raw), (two, second)):
        response = c.session.get(url + "/uploads/" + name, timeout=3)
        require(response.status_code == 200 and response.content == content, "both same-name originals retained")
    return {"files": [one, two]}
check("same_name_artifact_integrity", duplicate_names)
check("missing_status", lambda: require("error" in c.status("distribution-missing"), "missing status JSON refused"))
check("missing_cancel", lambda: require("error" in c.cancel("distribution-missing"), "missing cancel JSON refused"))
check("missing_retry", lambda: require("error" in c.retry("distribution-missing"), "missing retry JSON refused"))
check("invalid_image", lambda: require("error" in c.upload("invalid.png", base64.b64encode(b"not an image").decode()), "invalid image JSON refused"))
check("malformed_base64", lambda: require("error" in c.upload("bad-base64.png", "x"), "malformed base64 JSON refused"))
check("invalid_base64_alphabet", lambda: require("error" in c.upload("invalid-alphabet.png", "!!!!" + base64.b64encode(raw).decode()), "out-of-alphabet data JSON refused"))
check("server_after_refusals", lambda: require(c.health()["db"] is True, "server healthy after refusals"))
package = pathlib.Path(beast_studio_client.__file__).parent
pathlib.Path(output).write_text(json.dumps({"checks": rows, "version": importlib.metadata.version("beast-studio-client"), "module": beast_studio_client.__file__, "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob("*.py")}}, indent=2))
sys.exit(int(any(r["status"] != "worked" for r in rows)))
'''

NODE_PROBE = r'''
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, dirname } from "node:path";
import { BeastStudioClient, VERSION } from "beast-studio-client";
const [url, png, output] = process.argv.slice(2);
const checks = [];
async function check(name, action) {
  try { checks.push({ name, status: "worked", actual: await action() ?? true }); }
  catch (error) { checks.push({ name, status: "failed", error: String(error) }); }
}
const c = new BeastStudioClient({ baseUrl: url, timeoutMs: 3000 });
await check("tarball_import", () => assert.equal(VERSION, "1.0.0"));
await check("health", async () => assert.equal((await c.health()).db, true));
await check("recipes", async () => assert.ok((await c.recipes()).length > 0));
await check("cloud_disabled_registry", async () => {
  const result = await c.registry({kind:"image", allowCloud:false});
  assert.ok(result.eligible.every(b => b.hosting === "local"));
});
await check("runs_empty", async () => assert.deepEqual(await c.runs(), []));
await check("ledger", async () => assert.equal((await c.ledgerVerify()).ok, true));
const raw = readFileSync(png);
await check("upload_and_download", async () => {
  const result = await c.upload("distribution-node.png", "data:image/png;base64," + raw.toString("base64"));
  const response = await fetch(url + "/uploads/" + result.file);
  assert.equal(response.status, 200);
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), raw);
  return { file:result.file, sha256:createHash("sha256").update(raw).digest("hex") };
});
await check("same_name_artifact_integrity", async () => {
  const second = readFileSync(join(dirname(png), "owned2.png"));
  const one = await c.upload("same-name-node.png", raw.toString("base64"));
  const two = await c.upload("same-name-node.png", second.toString("base64"));
  assert.notEqual(one.file, two.file);
  for (const [result, original] of [[one, raw], [two, second]]) {
    const response = await fetch(url + "/uploads/" + result.file);
    assert.equal(response.status, 200);
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), original);
  }
  return { files:[one.file, two.file] };
});
await check("missing_status", async () => assert.ok((await c.status("distribution-missing")).error));
await check("missing_cancel", async () => assert.ok((await c.cancel("distribution-missing")).error));
await check("missing_retry", async () => assert.ok((await c.retry("distribution-missing")).error));
await check("invalid_image", async () => assert.ok((await c.upload("invalid.png", Buffer.from("not an image").toString("base64"))).error));
await check("malformed_base64", async () => assert.ok((await c.upload("bad-base64.png", "x")).error));
await check("invalid_base64_alphabet", async () => assert.ok((await c.upload("invalid-alphabet.png", "!!!!" + raw.toString("base64"))).error));
await check("server_after_refusals", async () => assert.equal((await c.health()).db, true));
writeFileSync(output, JSON.stringify({checks, node:process.version, entry:import.meta.resolve("beast-studio-client")}, null, 2));
process.exitCode = checks.some(r => r.status !== "worked") ? 1 : 0;
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--typescript-only", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    # A clean disposable worktree is required: refuse existing application data.
    if (repo / "studio/jobs.db").exists() or any((repo / "studio/runs").glob("*/status.json")):
        parser.error("Use a disposable worktree with no existing Studio database or runs")
    out = (args.outdir or repo / "artifacts" / f"sdk-distribution-{time.time_ns()}").resolve()
    out.mkdir(parents=True, exist_ok=False)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        parser.error("npm is required")
    commands: list[dict] = []
    report = {"status": "failed", "repo_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(), "commands": commands, "mocked_tool_calls": 0, "scope": "installed SDKs; real disposable Studio HTTP; no inference or GPU operations"}
    sources = [repo / "studio/server.py", repo / "bin/beast.ps1", *sorted((repo / "sdk/python/beast_studio_client").glob("*.py")), *sorted((repo / "sdk/typescript/src").glob("*.ts")), repo / "sdk/typescript/package.json", repo / "sdk/typescript/tsconfig.build.json"]
    report["source_files_sha256"] = {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.exists()}

    def run(name: str, argv: list[str], cwd: Path, *, required: bool = True) -> subprocess.CompletedProcess:
        started = time.monotonic()
        log = out / f"{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
        commands.append({"name": name, "argv": argv, "cwd": str(cwd), "exit_code": result.returncode, "seconds": time.monotonic()-started, "log": str(log)})
        print(name, result.returncode, flush=True)
        if required and result.returncode:
            raise RuntimeError(f"{name} failed; see {log}")
        return result

    owner = None
    server_log = None
    try:
        (out / "dist").mkdir()
        pyconsumer = out / "python-consumer"
        run("venv", [sys.executable, "-m", "venv", str(pyconsumer)], out)
        pypath = pyconsumer / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run("runtime-install", [str(pypath), "-m", "pip", "install", "-r", str(repo / "requirements.txt")], out)
        if not args.typescript_only:
            run("wheel-build", [sys.executable, "-m", "build", str(repo / "sdk/python"), "--wheel", "--outdir", str(out / "dist")], repo)
            wheels = list((out / "dist").glob("*.whl"))
            if len(wheels) != 1:
                raise RuntimeError("Expected exactly one fresh SDK wheel")
            run("wheel-install", [str(pypath), "-m", "pip", "install", str(wheels[0])], out)
            report["python_wheel_sha256"] = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
        ts = repo / "sdk/typescript"
        run("npm-ci", [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], ts)
        run("npm-pack", [npm, "pack", "--pack-destination", str(out / "dist"), "--json"], ts)
        tarballs = list((out / "dist").glob("*.tgz"))
        if len(tarballs) != 1:
            raise RuntimeError("Expected exactly one fresh npm tarball")
        consumer = out / "node-consumer"
        consumer.mkdir()
        (consumer / "package.json").write_text('{"private":true,"type":"module"}')
        run("tarball-install", [npm, "install", str(tarballs[0]), "--ignore-scripts", "--no-audit", "--no-fund"], consumer)
        report["node_tarball_sha256"] = hashlib.sha256(tarballs[0].read_bytes()).hexdigest()
        from PIL import Image
        image_bytes = io.BytesIO()
        Image.new("RGB", (3, 2), (30, 90, 150)).save(image_bytes, format="PNG")
        png = out / "owned.png"
        png.write_bytes(image_bytes.getvalue())
        Image.new("RGB", (3, 2), (80, 90, 100)).save(out / "owned2.png", format="PNG")
        bootstrap = out / "server-bootstrap.py"
        bootstrap.write_text(BOOTSTRAP)
        ready = out / "ready.json"
        server_log = (out / "server.log").open("w", encoding="utf-8")
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMDATA", "COMSPEC") if key in os.environ}
        owner = subprocess.Popen([str(pypath), "-I", str(bootstrap), str(repo), str(ready), str(out / "STOP")], cwd=out, env=env, stdout=server_log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+25
        while not ready.exists():
            if owner.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Actual Studio server failed readiness; see server.log")
            time.sleep(.05)
        report["server"] = json.loads(ready.read_text())
        if Path(report["server"]["db"]).resolve() != repo / "studio/jobs.db":
            raise RuntimeError("Server database escaped disposable checkout")
        url = report["server"]["url"]
        if not args.typescript_only:
            probe = out / "python-probe.py"
            probe.write_text(PYTHON_PROBE)
            run("python-live", [str(pypath), "-I", str(probe), url, str(png), str(out / "python-controls.json")], out, required=False)
            report["python_controls"] = json.loads((out / "python-controls.json").read_text())
        probe = consumer / "probe.mjs"
        probe.write_text(NODE_PROBE)
        run("node-live", [shutil.which("node") or "node", str(probe), url, str(png), str(out / "node-controls.json")], consumer, required=False)
        report["node_controls"] = json.loads((out / "node-controls.json").read_text())
        # Run the permanent real-HTTP deadline controls against the artifacts
        # just installed, isolated from source-tree imports and pytest settings.
        report["installed_deadlines"] = {}
        if not args.typescript_only:
            run("deadline-test-runtime", [str(pypath), "-m", "pip", "install", "pytest==9.0.3"], out)
            checks = out / "installed-deadlines"
            checks.mkdir()
            source_test = repo / "sdk/python/tests/test_deadline_claude_ld.py"
            copied_test = checks / source_test.name
            shutil.copyfile(source_test, copied_test)
            config = checks / "pytest.ini"
            config.write_text("[pytest]\n")
            junit = checks / "python.xml"
            run("python-installed-deadlines", [str(pypath), "-I", "-m", "pytest", "-q", "-c", str(config),
                "--confcutdir", str(checks), str(copied_test), f"--junitxml={junit}"], checks)
            cases = list(ET.parse(junit).iter("testcase"))
            if not cases or any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
                raise RuntimeError("Installed Python deadline controls must all run and pass")
            report["installed_deadlines"]["python"] = {
                "passed": len(cases), "junit": str(junit),
                "test_sha256": hashlib.sha256(copied_test.read_bytes()).hexdigest(),
                "scope": "permanent real HTTP controls; installed wheel; isolated interpreter"}
        source_test = repo / "sdk/typescript/tests/client.test.ts"
        test_text = source_test.read_text()
        old_import = 'from "../src/client.ts"'
        if test_text.count(old_import) != 1:
            raise RuntimeError("Cannot bind TypeScript deadline tests to the installed tarball")
        copied_test = consumer / "installed-deadlines.ts"
        copied_test.write_text(test_text.replace(old_import, 'from "beast-studio-client"'))
        run("node-installed-deadlines", [shutil.which("node") or "node", "--test", "--test-reporter=tap",
            "--test-name-pattern=^deadline:|^deadline control:|^unbounded streamEvents", str(copied_test)], consumer)
        deadline_log = (out / "node-installed-deadlines.log").read_text()
        passed = re.search(r"^# pass (\d+)$", deadline_log, re.MULTILINE)
        if passed is None or int(passed[1]) == 0:
            raise RuntimeError("No installed TypeScript deadline controls executed")
        report["installed_deadlines"]["node"] = {
            "passed": int(passed[1]), "log": str(out / "node-installed-deadlines.log"),
            "test_sha256": hashlib.sha256(copied_test.read_bytes()).hexdigest(),
            "scope": "permanent real HTTP deadline controls; installed npm tarball"}
        rows = [r for key in ("python_controls", "node_controls") if key in report for r in report[key]["checks"]]
        report["worked"] = sum(r["status"] == "worked" for r in rows)
        report["failed"] = sum(r["status"] != "worked" for r in rows)
        report["status"] = "worked" if rows and report["failed"] == 0 else "failed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if owner is not None:
            (out / "STOP").write_text("stop owned disposable server\n")
            try:
                owner.wait(timeout=15)
            except subprocess.TimeoutExpired:
                report["status"] = "failed"
                report["cleanup_error"] = "Owned server did not finish graceful stop"
                owner.kill()
                owner.wait(timeout=5)
            report["owned_server_exit"] = owner.returncode
        if server_log is not None:
            server_log.close()
        if owner is not None:
            # Preserve this invocation's database after the owned server exited.
            # The initial refusal guarantees these files did not predate the run.
            for name in ("jobs.db", "jobs.db-wal", "jobs.db-shm", "jobs.db-journal"):
                own_db = repo / "studio" / name
                if own_db.exists():
                    try:
                        own_db.rename(out / name)
                    except OSError as exc:
                        report["status"] = "failed"
                        report["cleanup_error"] = f"Owned database retention failed: {type(exc).__name__}"
        (out / "receipt.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"status": report["status"], "worked": report.get("worked", 0), "failed": report.get("failed", 0), "receipt": str(out / "receipt.json")}))
    return int(report["status"] != "worked")


if __name__ == "__main__":
    raise SystemExit(main())
