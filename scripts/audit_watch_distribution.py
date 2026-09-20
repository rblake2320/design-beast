"""Inventory declared Watch dependencies and tracked assets, without licensing approval.

No imports of model packages, downloads, installations or private-file scans.
Installed metadata describes this interpreter only, not a distributable lockfile.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import subprocess
from pathlib import Path

from packaging.requirements import Requirement


def requirements(root: Path, file: Path, seen: set[Path] | None = None) -> list[dict]:
    seen = set() if seen is None else seen
    file = file.resolve()
    if not file.is_relative_to(root.resolve()):
        raise ValueError("requirement include escapes repository")
    if file in seen:
        return []
    seen.add(file)
    rows = []
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            rows.extend(requirements(root, file.parent / line[3:].strip(), seen))
            continue
        req = Requirement(line)
        row = {"requirement": str(req), "name": req.name,
               "declared_in": file.relative_to(root.resolve()).as_posix(),
               "installed": False, "license_decision": "not_granted"}
        try:
            dist = metadata.distribution(req.name)
        except metadata.PackageNotFoundError:
            pass
        else:
            row.update(installed=True, installed_version=dist.version,
                       declared_version_matches=dist.version in req.specifier,
                       license_expression=dist.metadata.get("License-Expression"),
                       license_classifiers=[x for x in dist.metadata.get_all("Classifier", [])
                                            if x.startswith("License ::")],
                       # Hash legacy free text instead of duplicating long license bodies.
                       legacy_license_sha256=hashlib.sha256(
                           dist.metadata.get("License", "").encode()).hexdigest(),
                       direct_dependency_metadata=dist.requires or [])
        rows.append(row)
    return rows


def audit(root: Path) -> dict:
    git = lambda *args: subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True, check=True).stdout
    rows = []
    seen: set[Path] = set()
    inputs = {}
    for file in sorted(root.glob("requirements*.txt")):
        inputs[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        rows.extend(requirements(root, file, seen))
    tracked = [x.decode("utf-8") for x in git("ls-files", "-z").split(b"\0") if x]
    suffixes = {".mp4", ".webm", ".wav", ".mp3", ".jpg", ".jpeg", ".png",
                ".ttf", ".otf", ".woff", ".woff2", ".onnx", ".safetensors", ".pt"}
    assets = [name for name in tracked if Path(name).suffix.lower() in suffixes]
    return {"schema": "beast.distribution-inventory/v1",
            "commit": git("rev-parse", "HEAD").decode().strip(),
            "requirements_sha256": inputs, "dependencies": rows,
            "tracked_assets": assets, "tracked_asset_count": len(assets),
            "license_notice_paths": [x for x in tracked
                                     if Path(x).name.upper().startswith(("LICENSE", "NOTICE", "COPYING"))],
            "scope": "Declared Python roots, current interpreter metadata, tracked asset names only",
            "transitive_lock_verified": False, "media_rights_granted": False,
            "distribution_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"dependencies": len(result["dependencies"]),
                      "tracked_assets": result["tracked_asset_count"],
                      "distribution_approved": False}))
