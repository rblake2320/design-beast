"""Minimal source-frame binding diagnostic; no expected visual labels in prompts."""
from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio.resource_guard import admission
from watch.inspection_runtime import digest, retain

PROMPT = ('Describe ONLY this single image. Return JSON with exactly three short strings: '
          'screen_type, visible_content, visible_text. No inferred actions. At most 90 words total.')


def main() -> None:
    root = Path("watched/real-challenge-01")
    output = Path("proofs/watch-repair/binding-probe")
    output.mkdir(parents=True, exist_ok=False)
    for seconds in (10, 20):
        for endpoint in ("generate", "chat"):
            name = f"{seconds}-{endpoint}"
            gate = admission("judge", use_cache=False)
            retain(output / f"{name}-admission.json", gate)
            if not gate["admitted"]:
                raise RuntimeError("resource denied")
            frame = root / "frames" / f"f_{seconds * 1000:012d}.jpg"
            image = base64.b64encode(frame.read_bytes()).decode()
            payload = {"model": "qwen3-vl:8b", "stream": False, "format": "json", "think": False,
                       "options": {"num_ctx": 4096, "num_predict": 220, "temperature": 0}, "keep_alive": 0}
            if endpoint == "generate":
                payload.update(prompt=PROMPT, images=[image])
            else:
                payload["messages"] = [{"role": "user", "content": PROMPT, "images": [image]}]
            retain(output / f"{name}-intent.json", {"frame_sha256": digest(frame), "frame": str(frame),
                                                     "prompt": PROMPT, "endpoint": endpoint})
            request = urllib.request.Request(f"http://127.0.0.1:11434/api/{endpoint}",
                json.dumps(payload).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read())
            retain(output / f"{name}-result.json", raw)
            sys.stdout.write(json.dumps({"case": name, "response": raw.get("response"),
                                          "thinking": raw.get("thinking"), "message": raw.get("message")}) + "\n")


if __name__ == "__main__":
    main()
