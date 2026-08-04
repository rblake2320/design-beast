"""Operate Beast's hash-bound media evidence intake and promotion gates."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from watch.evidence import (  # noqa: E402
    EvidenceContractError,
    build_source_manifest,
    check_dataset_export,
    compile_procedure_bundle,
    create_execution_receipt,
    create_procedure_claim,
    events_from_timeline,
)
from watch.evidence.google_vision import GoogleVisionExtractor  # noqa: E402


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(value: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get(key), list):
        return value[key]
    if isinstance(value, dict) and isinstance(value.get("schema"), str):
        return [value]
    raise EvidenceContractError(f"expected an array or object containing {key!r}")


def _write_json(path: Path, value: Any) -> None:
    """Atomically replace one JSON artifact after a complete serialization."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _admit(args: argparse.Namespace) -> int:
    manifest = build_source_manifest(
        args.source,
        authorization_status=args.status,
        approved_by=args.approved_by,
        authorization_basis=args.basis,
        allowed_uses=args.allow_use,
        approved_at=args.approved_at or _now(),
        source_uri=args.source_uri,
    )
    _write_json(args.output, manifest)
    print(json.dumps({"ok": True, "output": str(args.output),
                      "source_id": manifest["source_id"],
                      "manifest_fingerprint": manifest["manifest_fingerprint"]}))
    return 0


def _timeline_events(args: argparse.Namespace) -> int:
    manifest = _read_json(args.manifest)
    timeline = _read_json(args.timeline)
    events = events_from_timeline(
        manifest, timeline, args.bundle_dir or args.timeline.resolve().parent,
    )
    output = {
        "schema": "beast.evidence.event-set/v1",
        "source_manifest_fingerprint": manifest["manifest_fingerprint"],
        "events": events,
    }
    _write_json(args.output, output)
    print(json.dumps({"ok": True, "output": str(args.output),
                      "event_count": len(events)}))
    return 0


def _claim(args: argparse.Namespace) -> int:
    claim = create_procedure_claim(
        args.description,
        args.event_id,
        review_state=args.state,
        requires_human_review=args.requires_human_review,
        execution_receipt_id=args.execution_receipt_id,
    )
    _write_json(args.output, claim)
    print(json.dumps({"ok": True, "output": str(args.output),
                      "claim_id": claim["claim_id"]}))
    return 0


def _receipt(args: argparse.Namespace) -> int:
    spec = _read_json(args.spec)
    spec_dir = args.spec.resolve().parent
    artifacts = []
    for row in spec.get("artifacts", []):
        path = Path(row["path"])
        if not path.is_absolute():
            path = spec_dir / path
        artifacts.append((row["label"], path))
    base = spec.get("artifact_base")
    artifact_base = None
    if base:
        artifact_base = Path(base)
        if not artifact_base.is_absolute():
            artifact_base = spec_dir / artifact_base
    receipt = create_execution_receipt(
        spec["claim_ids"],
        success=spec["success"],
        environment_fingerprint=spec["environment_fingerprint"],
        artifacts=artifacts,
        checks=spec["checks"],
        executed_at=spec.get("executed_at") or _now(),
        receipt_id=spec.get("receipt_id"),
        artifact_base=artifact_base,
    )
    _write_json(args.output, receipt)
    print(json.dumps({"ok": True, "output": str(args.output),
                      "receipt_id": receipt["receipt_id"],
                      "success": receipt["success"]}))
    return 0


def _compile(args: argparse.Namespace) -> int:
    manifest = _read_json(args.manifest)
    events = _records(_read_json(args.events), "events")
    claims = _records(_read_json(args.claims), "claims")
    receipts = _records(_read_json(args.receipts), "execution_receipts")
    bundle = compile_procedure_bundle(
        manifest, events, claims, receipts, artifact_root=args.artifact_root,
    )
    _write_json(args.output, bundle)
    print(json.dumps({"ok": bundle["gates"]["promotion_allowed"],
                      "output": str(args.output), "gates": bundle["gates"],
                      "bundle_fingerprint": bundle["bundle_fingerprint"]}))
    return 0 if bundle["gates"]["promotion_allowed"] else 1


def _dataset_check(args: argparse.Namespace) -> int:
    manifests = [_read_json(path) for path in args.manifest]
    result = check_dataset_export(manifests, _read_json(args.rights))
    _write_json(args.output, result)
    print(json.dumps(result))
    return 0 if result["ready"] else 1


def _google_vision(args: argparse.Namespace) -> int:
    manifest = _read_json(args.manifest)
    parent = _read_json(args.parent_event)
    extractor = GoogleVisionExtractor(
        api_key=os.environ.get("GOOGLE_CLOUD_VISION_API_KEY"),
        timeout_seconds=args.timeout,
        safe_search_threshold=args.safe_search_threshold,
        max_results=args.max_results,
    )
    result = extractor.analyze(
        args.image,
        manifest,
        parent,
        authorize_cloud_call=args.authorize_cloud_call,
        allow_sensitive_review=args.allow_sensitive_review,
    )
    _write_json(args.output, result)
    print(json.dumps({"ok": not result["gate"]["blocked"],
                      "output": str(args.output), "gate": result["gate"],
                      "event_count": len(result["events"])}))
    return 0 if not result["gate"]["blocked"] else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    admit = commands.add_parser("admit", help="hash and authorize exact source bytes")
    admit.add_argument("source", type=Path)
    admit.add_argument("output", type=Path)
    admit.add_argument("--status", required=True,
                       choices=["owned", "licensed", "public_domain",
                                "fair_use_research", "unverified"])
    admit.add_argument("--approved-by", required=True)
    admit.add_argument("--basis", required=True)
    admit.add_argument("--allow-use", action="append", default=[],
                       choices=["evidence_analysis", "procedure_learning",
                                "cloud_analysis", "dataset_training", "redistribution"])
    admit.add_argument("--approved-at")
    admit.add_argument("--source-uri")
    admit.set_defaults(func=_admit)

    timeline = commands.add_parser(
        "timeline-events", help="convert a Watch v3 timeline into evidence events")
    timeline.add_argument("manifest", type=Path)
    timeline.add_argument("timeline", type=Path)
    timeline.add_argument("output", type=Path)
    timeline.add_argument("--bundle-dir", type=Path)
    timeline.set_defaults(func=_timeline_events)

    claim = commands.add_parser("claim", help="create one evidence-linked claim")
    claim.add_argument("output", type=Path)
    claim.add_argument("--description", required=True)
    claim.add_argument("--event-id", action="append", required=True)
    claim.add_argument("--state", required=True,
                       choices=["observed", "inferred", "uncertain",
                                "verified_by_execution", "rejected"])
    claim.add_argument("--requires-human-review", action="store_true")
    claim.add_argument("--execution-receipt-id")
    claim.set_defaults(func=_claim)

    receipt = commands.add_parser(
        "receipt", help="hash artifacts and create an execution receipt from JSON spec")
    receipt.add_argument("spec", type=Path)
    receipt.add_argument("output", type=Path)
    receipt.set_defaults(func=_receipt)

    compile_cmd = commands.add_parser(
        "compile", help="derive promotion gates from manifests, events, claims, receipts")
    compile_cmd.add_argument("manifest", type=Path)
    compile_cmd.add_argument("events", type=Path)
    compile_cmd.add_argument("claims", type=Path)
    compile_cmd.add_argument("receipts", type=Path)
    compile_cmd.add_argument("output", type=Path)
    compile_cmd.add_argument("--artifact-root", type=Path)
    compile_cmd.set_defaults(func=_compile)

    dataset = commands.add_parser(
        "dataset-check", help="fail closed unless every source has training rights")
    dataset.add_argument("rights", type=Path)
    dataset.add_argument("output", type=Path)
    dataset.add_argument("--manifest", type=Path, action="append", required=True)
    dataset.set_defaults(func=_dataset_check)

    vision = commands.add_parser(
        "google-vision", help="run SafeSearch, then optional Web Detection")
    vision.add_argument("manifest", type=Path)
    vision.add_argument("parent_event", type=Path)
    vision.add_argument("image", type=Path)
    vision.add_argument("output", type=Path)
    vision.add_argument("--authorize-cloud-call", action="store_true")
    vision.add_argument("--allow-sensitive-review", action="store_true")
    vision.add_argument("--safe-search-threshold", default="LIKELY",
                        choices=["UNKNOWN", "VERY_UNLIKELY", "UNLIKELY",
                                 "POSSIBLE", "LIKELY", "VERY_LIKELY"])
    vision.add_argument("--max-results", type=int, default=20)
    vision.add_argument("--timeout", type=float, default=30.0)
    vision.set_defaults(func=_google_vision)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.func(args))
    except (EvidenceContractError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
