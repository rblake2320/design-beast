"""Fail-closed lifecycle gates for Beast Packs.

This module does not promote a capability.  It derives whether a previously
supported pack is currently eligible for trusted retrieval and whether matched
fitness/practice evidence is sufficient to propose a lifecycle change.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
ACTIVE = "active"
STALE = "stale_unproven"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def value_at(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def selected_facts(output: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    return {path: value_at(output, path) for path in paths}


def evaluate_assertions(output: dict[str, Any], assertions: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for assertion in assertions:
        path = assertion["path"]
        try:
            actual = value_at(output, path)
        except (KeyError, IndexError, TypeError, ValueError):
            failures.append(f"{path}: missing")
            continue
        op = assertion["op"]
        expected = assertion["value"]
        passed = {
            "eq": actual == expected,
            "gte": actual >= expected if op == "gte" else False,
            "startswith": str(actual).startswith(str(expected)) if op == "startswith" else False,
            "contains": expected in actual if op == "contains" else False,
        }.get(op)
        if passed is None:
            failures.append(f"{path}: unsupported operator {op}")
        elif not passed:
            failures.append(f"{path}: expected {op} {expected!r}, got {actual!r}")
    return failures


def run_json_probe(probe: dict[str, Any], *, repo: Path = REPO) -> dict[str, Any]:
    """Run one exact argv without a shell and require a JSON object response."""
    argv = list(probe.get("argv", []))
    if not argv:
        raise ValueError("probe argv is required")
    if argv[0] not in {"python", "python.exe"}:
        raise ValueError("v1 lifecycle probes permit only repository Python scripts")
    script = (repo / argv[1]).resolve()
    if not script.is_relative_to(repo.resolve()) or not script.is_file():
        raise ValueError("probe script must be a repository file")
    result = subprocess.run(
        argv,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=int(probe.get("timeout_seconds", 60)),
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"probe exited {result.returncode}: {result.stderr.strip()}")
    output = json.loads(result.stdout)
    if not isinstance(output, dict):
        raise ValueError("probe output must be a JSON object")
    return output


def assess(manifest: dict[str, Any], output: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    failures = evaluate_assertions(output, manifest["probe"]["assertions"])
    facts = selected_facts(output, manifest["fingerprint_fields"])
    actual_fingerprint = canonical_hash(facts)
    expected_fingerprint = manifest["baseline"]["fingerprint"]
    if actual_fingerprint != expected_fingerprint:
        failures.append("environment fingerprint drift")
    verified_at = datetime.fromisoformat(manifest["baseline"]["verified_at"].replace("Z", "+00:00"))
    age_days = (now - verified_at).total_seconds() / 86400
    if age_days > float(manifest["baseline"]["max_age_days"]):
        failures.append("verification expired")
    status = ACTIVE if not failures else STALE
    return {
        "schema": "beast.lifecycle-assessment/v1",
        "pack_id": manifest["pack_id"],
        "status": status,
        "trusted_retrieval": status == ACTIVE,
        "failures": failures,
        "expected_fingerprint": expected_fingerprint,
        "actual_fingerprint": actual_fingerprint,
        "facts": facts,
        "assessed_at": now.isoformat(),
        "claim_boundary": "Active means this smoke probe still matches its enrolled environment; it does not generalize the pack.",
    }


def evaluate_fitness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare baseline and candidate across every matched run, never best-of."""
    errors: list[str] = []
    grouped: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = row.get("condition")
        if condition not in {"baseline", "candidate"}:
            errors.append(f"invalid condition {condition!r}")
            continue
        key = (str(row.get("task_id", "")), str(row.get("variant_id", "")), int(row.get("repetition", -1)))
        if condition in grouped[key]:
            errors.append(f"duplicate {condition} run {key}")
        grouped[key][condition] = row
    improvements: list[float] = []
    regressions: list[str] = []
    for key, pair in grouped.items():
        if set(pair) != {"baseline", "candidate"}:
            errors.append(f"unmatched run {key}")
            continue
        baseline, candidate = pair["baseline"], pair["candidate"]
        if baseline.get("envelope_fingerprint") != candidate.get("envelope_fingerprint"):
            errors.append(f"envelope mismatch {key}")
        if not all(candidate.get("hard_gates", {}).values()) or not candidate.get("hard_gates"):
            regressions.append(f"candidate hard-gate failure {key}")
        if int(candidate.get("unsupported_claims", 0)) != 0:
            regressions.append(f"candidate unsupported claim {key}")
        bscore = float(baseline.get("score", 0))
        cscore = float(candidate.get("score", 0))
        improvements.append(cscore - bscore)
        if cscore < bscore:
            regressions.append(f"candidate score regression {key}")
    eligible = bool(grouped) and not errors and not regressions and any(delta > 0 for delta in improvements)
    return {
        "schema": "beast.skill-fitness/v1",
        "ok": not errors,
        "errors": errors,
        "matched_runs": len(grouped),
        "score_deltas": improvements,
        "regressions": regressions,
        "promotion_proposal_eligible": eligible,
        "claim_boundary": "Eligibility is a review proposal, never authority to activate or supersede a pack.",
    }


def practice_envelope(rows: list[dict[str, Any]], required_variants: list[str]) -> dict[str, Any]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[str(row.get("variant_id", ""))].append(row)
    missing = sorted(set(required_variants) - set(by_variant))
    verified = sorted(
        variant for variant, attempts in by_variant.items()
        if attempts and all(item.get("passed") is True for item in attempts)
    )
    failed = sorted(set(by_variant) - set(verified))
    return {
        "schema": "beast.practice-envelope/v1",
        "required_variants": required_variants,
        "verified_variants": verified,
        "failed_variants": failed,
        "missing_variants": missing,
        "complete": not missing and not failed,
        "evidence_level_ceiling": "generalized" if len(verified) >= 3 and not missing and not failed else "verified",
        "claim_boundary": "The envelope covers only named, executed variants; variant count alone does not prove arbitrary generalization.",
    }


def curriculum_proposals(graph: dict[str, Any]) -> dict[str, Any]:
    proposals = []
    for capability in graph.get("capabilities", []):
        next_test = str(capability.get("next_test", "")).strip()
        if next_test:
            proposals.append({
                "capability_id": capability["id"],
                "reason": "declared_next_test",
                "proposal": next_test,
                "authority": "human_review_required",
            })
    return {
        "schema": "beast.curriculum-proposals/v1",
        "proposals": proposals,
        "may_execute": False,
        "claim_boundary": "Graph analysis proposes work; it does not browse, download, spend, or change capability state.",
    }
