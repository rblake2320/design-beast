"""Score matched baseline-vs-Beast loop results without cherry-picking runs."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


LOWER_IS_BETTER = ("wall_clock_seconds", "tool_calls", "retries", "human_interventions")


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def analyze(rows: list[dict], protocol: dict, *, pilot: bool = False) -> dict:
    errors: list[str] = []
    seen: set[tuple[str, str, int]] = set()
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    domains: set[str] = set()
    for row in rows:
        key = (row.get("task_id", ""), row.get("condition", ""), row.get("repetition", -1))
        if key in seen:
            errors.append(f"duplicate run {key}")
        seen.add(key)
        if row.get("condition") not in {"baseline", "beast"}:
            errors.append(f"invalid condition for {key}")
            continue
        domains.add(row.get("domain", ""))
        grouped[row["task_id"]][row["condition"]].append(row)

    minimum = 1 if pilot else int(protocol["minimum_repetitions_per_condition"])
    for task_id, conditions in grouped.items():
        for condition in ("baseline", "beast"):
            if len(conditions.get(condition, [])) < minimum:
                errors.append(f"{task_id}/{condition}: fewer than {minimum} runs")
    if not pilot and len(domains - {""}) < int(protocol["minimum_domains"]):
        errors.append("insufficient materially different domains")

    summary = {}
    for condition in ("baseline", "beast"):
        selected = [row for row in rows if row.get("condition") == condition]
        gates = [all(row.get("hard_gates", {}).values()) for row in selected]
        metrics = {}
        for name in LOWER_IS_BETTER:
            values = [float(row.get("metrics", {}).get(name, 0)) for row in selected]
            metrics[f"median_{name}"] = statistics.median(values) if values else None
        visual_claims = sum(int(row.get("metrics", {}).get("visual_only_claims", 0)) for row in selected)
        visual_true = sum(int(row.get("metrics", {}).get("visual_only_true_positive", 0)) for row in selected)
        reinspect_required = sum(int(row.get("metrics", {}).get("reinspection_required", 0)) for row in selected)
        reinspect_triggered = sum(int(row.get("metrics", {}).get("reinspection_triggered", 0)) for row in selected)
        summary[condition] = {
            "runs": len(selected),
            "hard_gate_pass_rate": ratio(sum(gates), len(gates)),
            "unsupported_claims": sum(int(row.get("metrics", {}).get("unsupported_claims", 0)) for row in selected),
            "visual_only_fact_precision": ratio(visual_true, visual_claims),
            "reinspection_trigger_recall": ratio(reinspect_triggered, reinspect_required),
            **metrics,
        }

    improvements = {}
    if summary["baseline"]["runs"] and summary["beast"]["runs"]:
        for name in LOWER_IS_BETTER:
            key = f"median_{name}"
            improvements[name] = summary["beast"][key] < summary["baseline"][key]
    promotion_eligible = (
        not errors
        and bool(improvements)
        and any(improvements.values())
        and summary["beast"]["hard_gate_pass_rate"] >= summary["baseline"]["hard_gate_pass_rate"]
        and summary["beast"]["unsupported_claims"] <= summary["baseline"]["unsupported_claims"]
    )
    return {
        "schema": "beast.loop-benchmark-report/v1",
        "pilot": pilot,
        "ok": not errors,
        "errors": errors,
        "domains": sorted(domains - {""}),
        "tasks": sorted(grouped),
        "conditions": summary,
        "lower_is_better_improvements": improvements,
        "promotion_eligible": promotion_eligible,
        "claim_boundary": "A report is comparable only within its frozen envelope; pilot results cannot establish breadth."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("beast-loop-protocol.json"))
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.results.read_text(encoding="utf-8"))
    report = analyze(rows, json.loads(args.protocol.read_text(encoding="utf-8")), pilot=args.pilot)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
