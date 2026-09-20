"""Verify historical receipt links without rewriting either byte representation.

Only exact bytes, or UTF-8 text with strictly LF-only newlines converted to CRLF,
are accepted. This is a packaging reconciliation, never a semantic evidence gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

SNAPSHOTS = {
    "33": "7753a48c982de22b492e95c62d572016f5a5aa9f",
    "34": "454dbf903ae38117b7a190671dc8cb42af7b2ba3",
    "35": "2305e2a1ffcdbc26c939aa666e54838469ec5099",
    "42": "4a7207b8ef758d7a4f14e0339cfb09239ec05283",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def representation(data: bytes, expected: str, path: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("invalid expected SHA256")
    if sha(data) == expected:
        return "identity"
    if PurePosixPath(path).suffix not in {".json", ".jsonl", ".md", ".txt", ".py"}:
        raise ValueError("binary or unapproved text extension cannot be transformed")
    data.decode("utf-8", errors="strict")
    if b"\r" in data or b"\x00" in data or b"\n" not in data:
        raise ValueError("transformation requires strictly LF-only UTF-8 text")
    if sha(data.replace(b"\n", b"\r\n")) == expected:
        return "strict_lf_to_crlf"
    raise ValueError("neither raw nor strict LF-to-CRLF bytes match receipt")


class GitSnapshot:
    def __init__(self, repo: Path, commit: str):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("full immutable commit required")
        self.repo, self.commit, self.cache = repo, commit, {}

    def read(self, path: str) -> bytes:
        if not path or "\\" in path or ":" in path or path.startswith("/") or any(
            part in {"", ".", ".."} for part in path.split("/")
        ):
            raise ValueError("unsafe Git path")
        if path not in self.cache:
            result = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(self.repo), "cat-file", "blob", f"{self.commit}:{path}"],
                capture_output=True, check=False,
            )
            if result.returncode:
                raise ValueError(f"missing blob at {self.commit}:{path}")
            self.cache[path] = result.stdout
        return self.cache[path]

    def document(self, path: str):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result
        return json.loads(self.read(path), object_pairs_hook=unique)


def historical_edges(snapshot: GitSnapshot, pr: str):
    """Yield receipt path, JSON field path, target path, and receipt's own digest."""
    if pr == "33":
        root = "proofs/watch-inspection/"
        report_path = root + "run-03/report.json"
        report = snapshot.document(report_path)
        yield report_path, "manifest_sha256", root + "corpus/manifest.json", report["manifest_sha256"]
        if len(report["results"]) != 8:
            raise ValueError("expected eight historical inspection arms")
        for result in report["results"]:
            receipt_path = root + "run-03/" + result["inspection_receipt"]
            receipt = snapshot.document(receipt_path)
            base = str(PurePosixPath(receipt_path).parent) + "/"
            yield receipt_path, "intent_sha256", base + "inspection.json", receipt["intent_sha256"]
            yield receipt_path, "timeline_after_sha256", base + "timeline.json", receipt["timeline_after_sha256"]
            for i, frame in enumerate(receipt["frames"]):
                yield receipt_path, f"frames/{i}/sha256", base + frame["file"], frame["sha256"]
    elif pr == "34":
        root = "proofs/watch-real-video/run-01/"
        receipt_path = root + "export.json"
        files = snapshot.document(receipt_path)["files"]
        if len(files) != 122:
            raise ValueError("expected 122 original exported entries")
        for path, expected in files.items():
            yield receipt_path, "files/" + path, root + path, expected
    elif pr == "35":
        root = "proofs/watch-repair/"
        receipt_path = root + "dense-ocr-recovery-01/intent.json"
        receipt = snapshot.document(receipt_path)
        for key, target in (("prior_report_sha256", "dense-instruct-01/report.json"),
                            ("timeline_sha256", "inputs/dense-repair-01/timeline.json")):
            yield receipt_path, key, root + target, receipt[key]
    elif pr == "42":
        root = "proofs/watch-positive-controls/"
        for name in ("SCORE.json", "SCORE-CUSTODY-CHECK.json"):
            receipt_path = root + name
            receipt = snapshot.document(receipt_path)
            yield receipt_path, "report_sha256", root + "comparison/report.json", receipt["report_sha256"]
    else:
        raise ValueError("unknown historical PR")


def verify(repo: Path) -> dict:
    rows, failures = [], []
    for pr, commit in SNAPSHOTS.items():
        snapshot = GitSnapshot(repo, commit)
        try:
            for receipt, field, target, expected in historical_edges(snapshot, pr):
                row = {"pr": int(pr), "commit": commit, "receipt": receipt,
                       "receipt_sha256": sha(snapshot.read(receipt)), "field": field,
                       "target": target, "expected_execution_sha256": expected}
                try:
                    data = snapshot.read(target)
                    row.update(git_blob_sha256=sha(data), git_blob_size=len(data),
                               representation=representation(data, expected, target))
                    row["git_blob_oid"] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                except (ValueError, UnicodeError) as exc:
                    row["error"] = str(exc)
                    failures.append(row)
                rows.append(row)
        except (ValueError, KeyError, TypeError) as exc:
            failures.append({"pr": int(pr), "commit": commit, "error": str(exc)})
    return {"schema": "watch.historical-representation/v1", "snapshots": SNAPSHOTS,
            "claim": "Named historical receipt edges reconcile to exact Git bytes or explicitly reconstructed CRLF bytes; not byte identity across representations or execution replay.",
            "coverage": {"33": "run-03 manifest, eight intent/timeline links, all receipt frames",
                         "34": "all 122 export entries", "35": "two OCR recovery input links",
                         "42": "two score-to-report links"},
            "rows": rows, "failures": failures, "passed": bool(rows) and not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-report", type=Path, help="Require a retained supplemental report to equal fresh verification")
    args = parser.parse_args()
    report = verify(args.repo)
    if args.check_report:
        try:
            retained = json.loads(args.check_report.read_bytes())
        except (OSError, ValueError) as exc:
            print(json.dumps({"passed": False, "error": f"supplemental report unavailable: {exc}"}))
            return 1
        if retained != report:
            print(json.dumps({"passed": False, "error": "supplemental report differs from fresh Git verification"}))
            return 1
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    print(json.dumps({"passed": report["passed"], "edges": len(report["rows"]), "failures": report["failures"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
