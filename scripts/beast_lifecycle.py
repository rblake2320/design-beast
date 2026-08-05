"""Operate fail-closed Beast Pack lifecycle gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from beast import lifecycle  # noqa: E402


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(value, path: Path | None) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    print(payload, end="")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("manifest", type=Path)
    assess.add_argument("--probe-output", type=Path)
    assess.add_argument("--out", type=Path)
    fitness = sub.add_parser("fitness")
    fitness.add_argument("results", type=Path)
    fitness.add_argument("--out", type=Path)
    practice = sub.add_parser("practice")
    practice.add_argument("results", type=Path)
    practice.add_argument("--required", nargs="+", required=True)
    practice.add_argument("--out", type=Path)
    curriculum = sub.add_parser("curriculum")
    curriculum.add_argument("--graph", type=Path, default=REPO / "beast" / "capabilities.json")
    curriculum.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    if args.command == "assess":
        manifest = read(args.manifest)
        output = read(args.probe_output) if args.probe_output else lifecycle.run_json_probe(manifest["probe"])
        result = lifecycle.assess(manifest, output)
        write(result, args.out)
        return 0 if result["trusted_retrieval"] else 3
    if args.command == "fitness":
        result = lifecycle.evaluate_fitness(read(args.results))
    elif args.command == "practice":
        result = lifecycle.practice_envelope(read(args.results), args.required)
    else:
        result = lifecycle.curriculum_proposals(read(args.graph))
    write(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
