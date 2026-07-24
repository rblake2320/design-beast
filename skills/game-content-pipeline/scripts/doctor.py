#!/usr/bin/env python3
"""Environment doctor for the game-content-pipeline skill.

Checks every dependency in the Blender + UE 5.8 + Higgsfield pipeline and
prints PASS/WARN/MISS with an exact fix command for anything missing.
Exit code = number of hard misses.
"""
import json
import os
import shutil
import socket
import subprocess
import sys

GREEN, YELLOW, RED, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[0m"
results = []  # (status, name, detail, fix)


def check(status, name, detail, fix=""):
    results.append((status, name, detail, fix))


def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)


# --- Blender ---------------------------------------------------------------
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
if os.path.exists(BLENDER):
    check("PASS", "Blender 5.1", BLENDER)
else:
    check("MISS", "Blender 5.1", "not found", "Install Blender 5.1 from blender.org")

try:
    s = socket.create_connection(("localhost", 9876), timeout=3)
    s.close()
    check("PASS", "Blender MCP bridge", "listening on :9876")
except OSError:
    check("WARN", "Blender MCP bridge", "port 9876 not answering (Blender not running?)",
          f'cmd /c start "" "{BLENDER}"  — bridge starts with Blender (BlenderLab extension)')

# --- Unreal Engine 5.8 ------------------------------------------------------
UE_ROOT = r"C:\Program Files\Epic Games\UE_5.8"
UE_CMD = os.path.join(UE_ROOT, r"Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
if os.path.exists(UE_CMD):
    check("PASS", "Unreal Engine 5.8", UE_ROOT)
else:
    check("MISS", "Unreal Engine 5.8", "not installed",
          "Epic Games Launcher > Unreal Engine > Library > + > 5.8.0 (~120GB; C: conservative, "
          "D: OK after SMART check). Launcher: https://store.epicgames.com/download")

# UE MCP config in nearby projects
try:
    port8000 = socket.create_connection(("127.0.0.1", 8000), timeout=2)
    port8000.close()
    check("PASS", "UE MCP server", "something answering on :8000 (verify it's UE: /mcp endpoint)")
except OSError:
    check("WARN", "UE MCP server", ":8000 quiet (editor closed or server not started)",
          "In UE console: ModelContextProtocol.StartServer, then "
          "ModelContextProtocol.GenerateClientConfig ClaudeCode")

# --- C++ toolchain (Build Tools is enough for UE — full VS not required) ----
MSVC_DIR = r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
SDK_DIR = r"C:\Program Files (x86)\Windows Kits\10\Include"
msvc_vers = os.listdir(MSVC_DIR) if os.path.isdir(MSVC_DIR) else []
sdk_vers = os.listdir(SDK_DIR) if os.path.isdir(SDK_DIR) else []
if msvc_vers and sdk_vers:
    check("PASS", "C++ toolchain", f"VS Build Tools MSVC {msvc_vers[-1]} + Win SDK {sdk_vers[-1]}")
else:
    check("MISS", "C++ toolchain", "MSVC/Windows SDK not found (needed to build VibeUE)",
          'winget install -e --id Microsoft.VisualStudio.2022.BuildTools --override '
          '"--add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.Windows11SDK.26100 '
          '--includeRecommended --passive"  (VS Code alone cannot compile C++)')

# --- Higgsfield -------------------------------------------------------------
if shutil.which("higgsfield"):
    rc, out = run("higgsfield account status", timeout=30)
    if rc == 0:
        check("PASS", "Higgsfield CLI + auth", out.splitlines()[0] if out else "authenticated")
    else:
        check("WARN", "Higgsfield auth", "session expired",
              "User must run: higgsfield auth login  (interactive browser flow)")
else:
    check("MISS", "Higgsfield CLI", "not on PATH",
          "curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh")

# --- Media tools ------------------------------------------------------------
import glob as _glob

def find_tool(name, patterns):
    hit = shutil.which(name)
    if hit:
        return hit
    for pat in patterns:
        matches = _glob.glob(pat)
        if matches:
            return matches[0]
    return None

MEDIA_TOOLS = [
    ("ffmpeg", "Gyan.FFmpeg", [
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe")]),
    ("magick", "ImageMagick.ImageMagick", [r"C:\Program Files\ImageMagick-*\magick.exe"]),
]
for tool, winget_id, patterns in MEDIA_TOOLS:
    path = find_tool(tool, patterns)
    if path:
        note = "" if shutil.which(tool) else " (installed, not in this shell's PATH — new terminals fine)"
        check("PASS", tool, path + note)
    else:
        check("MISS", tool, "not installed", f"winget install -e --id {winget_id}")

# --- Python packages --------------------------------------------------------
for mod, pipname in [("PIL", "pillow"), ("rembg", '"rembg[gpu,cli]"')]:
    try:
        __import__(mod)
        check("PASS", f"python:{pipname}", "importable")
    except ImportError:
        check("MISS", f"python:{pipname}", "not installed",
              f"pip install {pipname}" + ("  (5090 needs onnxruntime-gpu>=1.21)" if mod == "rembg" else ""))

# --- Disk -------------------------------------------------------------------
try:
    usage = shutil.disk_usage("C:\\")
    free_gb = usage.free / 1e9
    status = "PASS" if free_gb > 200 else ("WARN" if free_gb > 130 else "MISS")
    check(status, "C: free space", f"{free_gb:.0f} GB free (UE needs ~120GB)",
          "" if status == "PASS" else "Free up space on C: before UE install")
except Exception:
    pass
check("WARN", "D: drive", "failed 2026-06 but chkdsk-repaired 2026-06-20, clean since; OK for builds once SMART check passes", "")

# --- Report -----------------------------------------------------------------
colors = {"PASS": GREEN, "WARN": YELLOW, "MISS": RED}
misses = 0
print("\n=== game-content-pipeline doctor ===\n")
for status, name, detail, fix in results:
    print(f"{colors[status]}[{status}]{RESET} {name}: {detail}")
    if fix:
        print(f"       fix: {fix}")
    if status == "MISS":
        misses += 1
print(f"\n{len(results)} checks, {misses} missing.")
if misses:
    print("Full install order: references/setup-checklist.md")
sys.exit(misses)
