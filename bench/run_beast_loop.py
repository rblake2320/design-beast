"""Score matched baseline-vs-Beast loop results without cherry-picking runs."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


LOWER_IS_BETTER = ("wall_clock_seconds", "tool_calls", "retries", "human_interventions")
REQUIRED_METRICS = LOWER_IS_BETTER + (
    "unsupported_claims", "visual_only_claims", "visual_only_true_positive",
    "reinspection_required", "reinspection_triggered", "acceptance_assertions_passed",
    "acceptance_assertions_total", "oom_count",
)
CONDITIONS = ("baseline", "adaptive_frames", "beast")
COUNT_METRICS = REQUIRED_METRICS[1:]


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def zero_failure_lower_bound(successful_tasks: int, *, alpha: float = 0.05) -> float | None:
    """One-sided exact lower bound when every independent task succeeds."""
    if successful_tasks <= 0:
        return None
    return alpha ** (1.0 / successful_tasks)


def analyze(
    rows: list[dict], protocol: dict, *, pilot: bool = False,
    custody_verified: bool | None = None, preflight_errors: list[str] | None = None,
) -> dict:
    errors: list[str] = list(preflight_errors or [])
    seen: set[tuple[str, str, int]] = set()
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    domains: set[str] = set()
    task_domains: dict[str, str] = {}
    envelope_fingerprints: set[str] = set()
    gate_ids = {gate["id"] for gate in protocol["hard_gates"]}
    for row in rows:
        key = (row.get("task_id", ""), row.get("condition", ""), row.get("repetition", -1))
        if key in seen:
            errors.append(f"duplicate run {key}")
        seen.add(key)
        if row.get("condition") not in CONDITIONS:
            errors.append(f"invalid condition for {key}")
            continue
        domain = row.get("domain", "")
        domains.add(domain)
        task_id = row.get("task_id", "")
        if not task_id or not domain:
            errors.append(f"run {key}: task_id and domain are required")
        elif task_id in task_domains and task_domains[task_id] != domain:
            errors.append(f"{task_id}: domain changed across runs")
        else:
            task_domains[task_id] = domain
        fingerprint = str(row.get("envelope_fingerprint", "")).strip()
        if not fingerprint:
            errors.append(f"run {key}: envelope_fingerprint is required")
        else:
            envelope_fingerprints.add(fingerprint)
        gates = row.get("hard_gates", {})
        missing_gates = sorted(gate_ids - set(gates))
        extra_gates = sorted(set(gates) - gate_ids)
        if missing_gates:
            errors.append(f"run {key}: missing hard gates {missing_gates}")
        if extra_gates:
            errors.append(f"run {key}: unknown hard gates {extra_gates}")
        non_boolean_gates = sorted(name for name, value in gates.items() if not isinstance(value, bool))
        if non_boolean_gates:
            errors.append(f"run {key}: hard gates must be booleans {non_boolean_gates}")
        metrics = row.get("metrics", {})
        missing_metrics = [name for name in REQUIRED_METRICS if name not in metrics]
        if missing_metrics:
            errors.append(f"run {key}: missing metrics {missing_metrics}")
        for name in REQUIRED_METRICS:
            if name not in metrics:
                continue
            value = metrics[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(f"run {key}: metric {name} must be a finite number")
                continue
            if value < 0:
                errors.append(f"run {key}: metric {name} cannot be negative")
            if name in COUNT_METRICS and int(value) != value:
                errors.append(f"run {key}: count metric {name} must be an integer")
        if metrics.get("visual_only_true_positive", 0) > metrics.get("visual_only_claims", 0):
            errors.append(f"run {key}: visual true positives exceed visual claims")
        if metrics.get("reinspection_triggered", 0) > metrics.get("reinspection_required", 0):
            errors.append(f"run {key}: reinspection triggers exceed required cases")
        if metrics.get("acceptance_assertions_passed", 0) > metrics.get("acceptance_assertions_total", 0):
            errors.append(f"run {key}: passed acceptance assertions exceed total")
        if metrics.get("acceptance_assertions_total", 0) <= 0:
            errors.append(f"run {key}: at least one acceptance assertion is required")
        grouped[row["task_id"]][row["condition"]].append(row)

    if len(envelope_fingerprints) > 1:
        errors.append("runs do not share one frozen envelope_fingerprint")

    minimum = 1 if pilot else int(protocol["minimum_repetitions_per_condition"])
    for task_id, conditions in grouped.items():
        for condition in CONDITIONS:
            if len(conditions.get(condition, [])) < minimum:
                errors.append(f"{task_id}/{condition}: fewer than {minimum} runs")
        repetition_sets = {
            condition: {row["repetition"] for row in conditions.get(condition, [])}
            for condition in CONDITIONS
        }
        if len({frozenset(values) for values in repetition_sets.values()}) != 1:
            errors.append(f"{task_id}: condition repetition IDs do not match")
    if not pilot and len(domains - {""}) < int(protocol["minimum_domains"]):
        errors.append("insufficient materially different domains")
    if not pilot:
        required_tasks = int(protocol["minimum_tasks_per_domain"])
        for domain in sorted(domains - {""}):
            count = sum(value == domain for value in task_domains.values())
            if count < required_tasks:
                errors.append(f"{domain}: fewer than {required_tasks} distinct tasks")

    summary = {}
    for condition in CONDITIONS:
        selected = [row for row in rows if row.get("condition") == condition]
        gates = [
            set(row.get("hard_gates", {})) == gate_ids
            and all(row["hard_gates"].values())
            for row in selected
        ]
        metrics = {}
        for name in LOWER_IS_BETTER:
            values = [float(row["metrics"][name]) for row in selected if name in row.get("metrics", {})]
            metrics[f"median_{name}"] = statistics.median(values) if values else None
        visual_claims = sum(int(row.get("metrics", {}).get("visual_only_claims", 0)) for row in selected)
        visual_true = sum(int(row.get("metrics", {}).get("visual_only_true_positive", 0)) for row in selected)
        reinspect_required = sum(int(row.get("metrics", {}).get("reinspection_required", 0)) for row in selected)
        reinspect_triggered = sum(int(row.get("metrics", {}).get("reinspection_triggered", 0)) for row in selected)
        assertions_passed = sum(int(row.get("metrics", {}).get("acceptance_assertions_passed", 0)) for row in selected)
        assertions_total = sum(int(row.get("metrics", {}).get("acceptance_assertions_total", 0)) for row in selected)
        summary[condition] = {
            "runs": len(selected),
            "hard_gate_pass_rate": ratio(sum(gates), len(gates)),
            "unsupported_claims": sum(int(row.get("metrics", {}).get("unsupported_claims", 0)) for row in selected),
            "visual_only_fact_precision": ratio(visual_true, visual_claims),
            "reinspection_trigger_recall": ratio(reinspect_triggered, reinspect_required),
            "acceptance_assertion_pass_rate": ratio(assertions_passed, assertions_total),
            "oom_count": sum(int(row.get("metrics", {}).get("oom_count", 0)) for row in selected),
            **metrics,
        }

    improvements = {}
    correctness_improved = False
    if summary["baseline"]["runs"] and summary["beast"]["runs"]:
        for name in LOWER_IS_BETTER:
            key = f"median_{name}"
            baseline_value = summary["baseline"][key]
            beast_value = summary["beast"][key]
            improvements[name] = (
                baseline_value is not None
                and beast_value is not None
                and beast_value < baseline_value
            )
        correctness_improved = any((
            summary["beast"]["hard_gate_pass_rate"]
            > summary["baseline"]["hard_gate_pass_rate"],
            summary["beast"]["acceptance_assertion_pass_rate"]
            > summary["baseline"]["acceptance_assertion_pass_rate"],
        ))
    thresholds = protocol["acceptance_thresholds"]
    criteria_met = (
        not errors
        and (pilot or custody_verified is True)
        and (correctness_improved or any(improvements.values()))
        and summary["beast"]["hard_gate_pass_rate"] == thresholds["beast_hard_gate_pass_rate"]
        and summary["beast"]["visual_only_fact_precision"] == thresholds["beast_visual_only_fact_precision"]
        and summary["beast"]["reinspection_trigger_recall"] == thresholds["beast_reinspection_trigger_recall"]
        and summary["beast"]["unsupported_claims"] == thresholds["beast_unsupported_claims"]
        and summary["beast"]["acceptance_assertion_pass_rate"] == 1.0
        and summary["beast"]["oom_count"] == 0
        and summary["beast"]["hard_gate_pass_rate"] >= summary["baseline"]["hard_gate_pass_rate"]
    )
    task_level_beast_success = {}
    for task_id, conditions in grouped.items():
        runs = conditions.get("beast", [])
        task_level_beast_success[task_id] = bool(runs) and all(
            set(run.get("hard_gates", {})) == gate_ids
            and all(value is True for value in run["hard_gates"].values())
            and run.get("metrics", {}).get("unsupported_claims") == 0
            and run.get("metrics", {}).get("oom_count") == 0
            and run.get("metrics", {}).get("acceptance_assertions_passed")
            == run.get("metrics", {}).get("acceptance_assertions_total")
            for run in runs
        )
    successful_task_count = sum(task_level_beast_success.values())
    all_tasks_succeeded = bool(task_level_beast_success) and successful_task_count == len(task_level_beast_success)
    reliability_lower_bound = (
        zero_failure_lower_bound(successful_task_count) if all_tasks_succeeded else None
    )
    promotion_eligible = criteria_met and not pilot
    return {
        "schema": "beast.loop-benchmark-report/v1",
        "pilot": pilot,
        "custody_verified": custody_verified,
        "ok": not errors,
        "errors": errors,
        "domains": sorted(domains - {""}),
        "tasks": sorted(grouped),
        "conditions": summary,
        "lower_is_better_improvements": improvements,
        "correctness_improved": correctness_improved,
        "envelope_fingerprint": next(iter(envelope_fingerprints), ""),
        "pilot_criteria_met": criteria_met if pilot else None,
        "promotion_eligible": promotion_eligible,
        "task_level_beast_success": task_level_beast_success,
        "successful_beast_tasks": successful_task_count,
        "one_sided_95pct_zero_failure_lower_bound": reliability_lower_bound,
        "target_population_reliability_eligible": (
            promotion_eligible
            and successful_task_count >= 29
            and reliability_lower_bound is not None
            and reliability_lower_bound >= 0.90
        ),
        "claim_boundary": "A report is comparable only within its frozen envelope. A pilot cannot promote. Nine tasks can support bounded sampled-domain generalization, not a 90%-reliable target-population claim; that requires at least 29 independently selected unseen tasks with zero task-level failures."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("beast-loop-protocol.json"))
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--seal", type=Path, help="required for a non-pilot promotion report")
    parser.add_argument("--artifact-root", type=Path, help="root for receipts in a sealed result chain")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    preflight_errors = []
    custody_verified = None
    if args.seal:
        if args.artifact_root is None:
            preflight_errors.append("--artifact-root is required with --seal")
        try:
            import beast_loop_custody as custody
            seal = json.loads(args.seal.read_text(encoding="utf-8"))
            rows = custody._read_records(args.results)
            custody_errors = custody.verify_result_chain(
                seal, rows, args.artifact_root, require_complete=True
            )
            preflight_errors.extend(f"custody: {error}" for error in custody_errors)
            custody_verified = not custody_errors and args.artifact_root is not None
        except (OSError, json.JSONDecodeError, custody.CustodyError) as exc:
            rows = []
            preflight_errors.append(f"custody: {exc}")
            custody_verified = False
    else:
        rows = json.loads(args.results.read_text(encoding="utf-8"))
        if not args.pilot:
            preflight_errors.append("non-pilot scoring requires a sealed custody chain")
            custody_verified = False
    report = analyze(
        rows, json.loads(args.protocol.read_text(encoding="utf-8")), pilot=args.pilot,
        custody_verified=custody_verified, preflight_errors=preflight_errors,
    )
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
