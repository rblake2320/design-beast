#!/usr/bin/env python3
"""Score a generated image against its brief using a local Ollama vision model (free).

Usage:
  python judge_image.py hero.png --brief "rain-slicked neon alley, teal-orange, no people"
  python judge_image.py a.png b.png c.png d.png --brief "..."   # ranks candidates
  python judge_image.py x.png --brief "..." --model llava:7b    # fallback model

Exit code 0 if best score >= 7, else 1 (usable in loops).
"""
import argparse
import base64
import json
import math
import sys
import urllib.request

OLLAMA = "http://localhost:11434/api/generate"
PROMPT = """You are a ruthless art director. Score this image 1-10 against the brief.

Brief: {brief}

Judge: (1) matches brief, (2) single clear focal point, (3) consistent light direction,
(4) no AI artifacts (melted hands/text, plastic skin, oversaturation), (5) composed edges.
Reply ONLY with JSON: {{"score": <1-10>, "kill": <true if unusable>, "fix": "<one sentence: weakest thing and how to fix it>"}}"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "kill": {"type": "boolean"},
        "fix": {"type": "string"},
    },
    "required": ["score", "kill", "fix"],
    "additionalProperties": False,
}


class JudgeOutputError(ValueError):
    """A model response is not a usable quality verdict."""


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise JudgeOutputError(f"duplicate judge field: {key}")
        result[key] = value
    return result


def validate_verdict(value: object) -> dict:
    """Never let malformed model output become a passing score or edit command."""
    if not isinstance(value, dict) or set(value) != {"score", "kill", "fix"}:
        raise JudgeOutputError("judge must return exactly score, kill and fix")
    score = value["score"]
    if (type(score) not in (int, float) or not 1 <= score <= 10
            or not math.isfinite(score)):
        raise JudgeOutputError("judge score must be a finite number between 1 and 10")
    if type(value["kill"]) is not bool:
        raise JudgeOutputError("judge kill must be a boolean")
    if not isinstance(value["fix"], str) or len(value["fix"]) > 2000:
        raise JudgeOutputError("judge fix must be a string of at most 2000 characters")
    return value


def judge(path: str, brief: str, model: str) -> dict:
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    body = json.dumps({
        "model": model,
        "prompt": PROMPT.format(brief=brief),
        "images": [img],
        "stream": False,
        "format": JUDGE_SCHEMA,
        "options": {"temperature": 0},
        "think": False,
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    # generous timeout: first call cold-loads the vision model into VRAM
    with urllib.request.urlopen(req, timeout=420) as r:
        out = json.loads(r.read())
    # Some local Qwen adapters put even a schema-only answer into `thinking`
    # with an empty response. Accept only a complete, strictly validated JSON
    # object from that field, never prose or an extracted reasoning fragment.
    if not isinstance(out, dict):
        raise JudgeOutputError("judge returned an invalid response envelope")
    answer = out.get("response")
    if answer == "":
        answer = out.get("thinking")
    if not isinstance(answer, str) or not answer:
        raise JudgeOutputError("judge returned no structured answer")
    try:
        return validate_verdict(json.loads(answer, object_pairs_hook=_unique_object))
    except (ValueError, TypeError) as exc:
        raise JudgeOutputError(f"invalid judge response: {exc}") from exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--brief", required=True)
    ap.add_argument("--model", default="qwen3-vl:8b")
    args = ap.parse_args()

    results = []
    for path in args.images:
        try:
            v = judge(path, args.brief, args.model)
        except Exception as e:  # noqa: BLE001 — report and keep judging the rest
            print(f"{path}: JUDGE FAILED ({e})", file=sys.stderr)
            continue
        results.append((v.get("score", 0), path, v))

    if not results:
        print(f"No images judged — is Ollama up with {args.model} pulled?", file=sys.stderr)
        return 1

    results.sort(reverse=True)
    for score, path, v in results:
        flag = " [KILL]" if v.get("kill") else ""
        print(f"{score}/10{flag}  {path}\n        fix: {v.get('fix', '-')}")
    survivors = [item for item in results if not item[2]["kill"]]
    if not survivors:
        print("\nNO WINNER: all judged images were rejected")
        return 1
    print(f"\nWINNER: {survivors[0][1]}")
    return 0 if survivors[0][0] >= 7 else 1


if __name__ == "__main__":
    sys.exit(main())
