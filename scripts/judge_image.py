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
import sys
import urllib.request

OLLAMA = "http://localhost:11434/api/generate"
PROMPT = """You are a ruthless art director. Score this image 1-10 against the brief.

Brief: {brief}

Judge: (1) matches brief, (2) single clear focal point, (3) consistent light direction,
(4) no AI artifacts (melted hands/text, plastic skin, oversaturation), (5) composed edges.
Reply ONLY with JSON: {{"score": <1-10>, "kill": <true if unusable>, "fix": "<one sentence: weakest thing and how to fix it>"}}"""


def judge(path: str, brief: str, model: str) -> dict:
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    body = json.dumps({
        "model": model,
        "prompt": PROMPT.format(brief=brief),
        "images": [img],
        "stream": False,
        "format": "json",
        "think": False,
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read())
    # thinking models sometimes emit the JSON into "thinking" with an empty "response"
    return json.loads(out["response"] or out.get("thinking", ""))


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
    print(f"\nWINNER: {results[0][1]}")
    return 0 if results[0][0] >= 7 else 1


if __name__ == "__main__":
    sys.exit(main())
