"""Shared UE 5.8 disposable-project guardrails."""

from __future__ import annotations

import os
import re
import json
from pathlib import Path

import unreal


def require_context() -> dict[str, str]:
    version = str(unreal.SystemLibrary.get_engine_version())
    if not version.startswith("5.8"):
        raise RuntimeError(f"UE 5.8 is required; active engine is {version}")
    active_project = os.path.normcase(os.path.abspath(str(unreal.Paths.get_project_file_path())))
    allowed_project = os.environ.get("BEAST_ALLOWED_UPROJECT", "").strip()
    if not allowed_project:
        raise RuntimeError("BEAST_ALLOWED_UPROJECT must name the exact disposable .uproject")
    allowed_project = os.path.normcase(os.path.abspath(allowed_project))
    if active_project != allowed_project:
        raise RuntimeError(f"Active project is not authorized: {active_project}")
    if os.environ.get("BEAST_USER_CONFIRMED_DISPOSABLE_PROJECT") != "1":
        raise RuntimeError("User must explicitly confirm this is a disposable project")
    project_name = Path(active_project).stem
    if not re.search(r"(?:proof|sandbox|disposable)", project_name, re.IGNORECASE):
        raise RuntimeError(
            "Disposable project name must contain Proof, Sandbox, or Disposable: " + project_name
        )
    run_id = os.environ.get("BEAST_RUN_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,40}", run_id):
        raise RuntimeError("BEAST_RUN_ID must be a fresh 3-40 character identifier")
    content_root = f"/Game/MoodBuddyProof/{run_id}"
    receipt_dir = os.path.abspath(
        os.path.join(str(unreal.Paths.project_saved_dir()), "BeastProof", run_id)
    )
    return {
        "version": version,
        "project": active_project,
        "run_id": run_id,
        "content_root": content_root,
        "receipt_dir": receipt_dir,
    }


def require_under_run(path: str, context: dict[str, str]) -> str:
    prefix = context["content_root"] + "/"
    if not path.startswith(prefix) or ".." in path:
        raise RuntimeError(f"Path must remain under fresh proof root {prefix}: {path}")
    return path


def receipt_path(context: dict[str, str], name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        raise RuntimeError(f"Invalid receipt name: {name}")
    return os.path.join(context["receipt_dir"], name + ".json")


def write_receipt(context: dict[str, str], name: str, payload: dict) -> str:
    os.makedirs(context["receipt_dir"], exist_ok=True)
    path = receipt_path(context, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_receipt(context: dict[str, str], name: str, required_state: str) -> dict:
    path = receipt_path(context, name)
    if not os.path.isfile(path):
        raise RuntimeError(f"Required receipt is missing: {path}")
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("project") != context["project"] or payload.get("run_id") != context["run_id"]:
        raise RuntimeError(f"Receipt identity mismatch: {path}")
    if payload.get("state") != required_state:
        raise RuntimeError(f"Receipt state is not {required_state}: {path}")
    return payload
