"""Validate and inspect the machine-readable Beast control plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
BEAST = REPO / "beast"
GRAPH = BEAST / "capabilities.json"
POLICY = BEAST / "resource-policy.json"
BENCHMARK = REPO / "bench" / "beast-loop-protocol.json"
PACKS = BEAST / "packs"
LEVELS = ["observed", "reproduced", "measured", "verified", "generalized"]

sys.path.insert(0, str(REPO / "studio"))
import resource_guard  # noqa: E402
sys.path.insert(0, str(REPO / "scripts"))
import verify_recovery_checkpoint as recovery_verifier  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_path(value: str) -> Path:
    path = (REPO / value).resolve()
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {value}") from exc
    return path


def validate_graph(graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if graph.get("schema") != "beast.capability-graph/v1":
        errors.append("capability graph schema must be beast.capability-graph/v1")
    capabilities = graph.get("capabilities", [])
    ids = [item.get("id") for item in capabilities]
    if len(ids) != len(set(ids)):
        errors.append("capability IDs must be unique")
    known = set(ids)
    edges: dict[str, list[str]] = {}
    for item in capabilities:
        cid = item.get("id", "<missing>")
        edges[cid] = item.get("depends_on", [])
        for field in ("name", "domain", "claim", "boundary", "next_test"):
            if not str(item.get(field, "")).strip():
                errors.append(f"{cid}: missing {field}")
        level = item.get("level")
        if level not in LEVELS:
            errors.append(f"{cid}: invalid evidence level {level!r}")
        if level == "generalized" and int(item.get("breadth_count", 0)) < 3:
            errors.append(f"{cid}: generalized requires breadth_count >= 3")
        evidence = item.get("evidence", [])
        if not evidence:
            errors.append(f"{cid}: evidence is required")
        for value in evidence:
            try:
                path = repo_path(value)
                if not path.exists():
                    errors.append(f"{cid}: missing evidence {value}")
            except ValueError as exc:
                errors.append(f"{cid}: {exc}")
        for dep in edges[cid]:
            if dep not in known:
                errors.append(f"{cid}: unknown dependency {dep}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"capability dependency cycle includes {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in edges.get(node, []):
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for cid in known:
        visit(cid)
    return errors


def validate_pack(pack: dict[str, Any], graph_ids: set[str], path: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "schema", "id", "version", "lifecycle", "supersedes", "capability_id",
        "claim", "boundary", "evidence_level", "target", "procedure", "evidence",
        "validation", "recovery", "resource_profile",
    }
    missing = sorted(required - set(pack))
    if missing:
        errors.append(f"{path}: missing fields {', '.join(missing)}")
        return errors
    if pack["schema"] != "beast.pack/v1":
        errors.append(f"{path}: unsupported schema")
    if pack["lifecycle"] not in {"candidate", "active", "superseded", "deprecated"}:
        errors.append(f"{path}: invalid lifecycle")
    if pack["evidence_level"] not in LEVELS:
        errors.append(f"{path}: invalid evidence level")
    if pack["capability_id"] not in graph_ids:
        errors.append(f"{path}: unknown capability {pack['capability_id']}")
    policy = read_json(POLICY)
    if pack["resource_profile"] not in policy["workloads"]:
        errors.append(f"{path}: unknown resource profile {pack['resource_profile']}")
    for value in [pack["procedure"], *pack["evidence"]]:
        try:
            if not repo_path(value).is_file():
                errors.append(f"{path}: missing referenced file {value}")
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
    if pack["lifecycle"] in {"superseded", "deprecated"} and not pack.get("supersession_reason"):
        errors.append(f"{path}: inactive pack requires supersession_reason")
    return errors


def validate_all() -> dict[str, Any]:
    graph = read_json(GRAPH)
    errors = validate_graph(graph)
    graph_ids = {item["id"] for item in graph.get("capabilities", [])}
    pack_paths = sorted(PACKS.glob("*/pack.json"))
    for path in pack_paths:
        errors.extend(validate_pack(read_json(path), graph_ids, path.relative_to(REPO)))
    benchmark = read_json(BENCHMARK)
    if benchmark.get("schema") != "beast.loop-benchmark/v1":
        errors.append("benchmark schema must be beast.loop-benchmark/v1")
    if benchmark.get("status") != "protocol_only_unrun":
        errors.append("benchmark status may change only with retained run evidence")
    policy = read_json(POLICY)
    if policy.get("schema") != "beast.resource-policy/v1":
        errors.append("resource policy schema must be beast.resource-policy/v1")
    if policy.get("gpu", {}).get("automatic_process_termination") is not False:
        errors.append("resource policy must not terminate user processes automatically")
    fingerprint = hashlib.sha256(
        json.dumps(graph, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "ok": not errors,
        "errors": errors,
        "capabilities": len(graph_ids),
        "packs": len(pack_paths),
        "graph_fingerprint": fingerprint,
    }


def status() -> dict[str, Any]:
    graph = read_json(GRAPH)
    levels = Counter(item["level"] for item in graph["capabilities"])
    snapshot = resource_guard.measure_gpu(use_cache=False)
    policy = resource_guard.load_policy()
    return {
        "schema": "beast.operator-status/v1",
        "contract": "BEAST.md",
        "validation": validate_all(),
        "capability_levels": dict(sorted(levels.items())),
        "system_hypothesis": graph["system_hypothesis"],
        "gpu": snapshot,
        "resource_admission": {
            name: resource_guard.evaluate(snapshot, policy, name)["admitted"]
            for name in policy["workloads"]
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate capability graph, packs, benchmark, and policy")
    sub.add_parser("status", help="show capability and live resource state")
    resource = sub.add_parser("resource-check", help="test one workload against live VRAM")
    resource.add_argument("workload")
    recover = sub.add_parser("recover", help="verify a recovery checkpoint before resuming")
    recover.add_argument("checkpoint", type=Path)
    recover.add_argument("--allow-head-drift", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "validate":
        result = validate_all()
    elif args.command == "status":
        result = status()
    elif args.command == "recover":
        try:
            result = recovery_verifier.verify(
                args.checkpoint, allow_head_drift=args.allow_head_drift
            )
        except (OSError, ValueError, KeyError, subprocess.SubprocessError,
                json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
    else:
        try:
            result = resource_guard.admission(args.workload, use_cache=False)
        except ValueError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "validate":
        return 0 if result["ok"] else 1
    if args.command == "resource-check":
        return 0 if result["admitted"] else 3
    if args.command == "recover":
        return 0 if result["ok"] else 1
    return 0 if result["validation"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
