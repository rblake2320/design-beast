"""Create keys and append strict signed Beast evidence receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from beast import signed_chain  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen")
    keygen.add_argument("--private", type=Path, required=True)
    keygen.add_argument("--public", type=Path, required=True)
    add = sub.add_parser("append")
    add.add_argument("--ledger", type=Path, required=True)
    add.add_argument("--private", type=Path, required=True)
    add.add_argument("--event", required=True)
    add.add_argument("--subject", required=True)
    add.add_argument("--evidence", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    if args.command == "keygen":
        signed_chain.generate_keypair(args.private, args.public)
        return 0
    records = []
    for path in args.evidence:
        records.append({"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    entry = signed_chain.append(args.ledger, args.private, event=args.event, subject=args.subject, evidence=records)
    print(json.dumps(entry, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
