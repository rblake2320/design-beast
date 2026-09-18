"""Two bounded same-case CPU vision calls; failed-case diagnostic only."""
from pathlib import Path
import json
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.frame_observer import observe_frame
from watch.inspection_runtime import retain


def main():
    bundle = Path("watched/dense-repair-01")
    output = Path("proofs/watch-repair/cpu-27b-probe-01")
    output.mkdir(parents=True, exist_ok=False)
    model = "qwen3.8:27b-review-cpu"
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        identity = next(item for item in json.loads(response.read())["models"] if item["name"] == model)
    retain(output / "protocol.json", {"selection": "failed-case diagnostic", "frames": [0, 23],
        "model": model, "model_digest": identity["digest"], "max_calls": 2,
        "num_gpu": 0, "cpu_threads": 4, "output_tokens_per_call": 400})
    rows = sorted(json.loads((bundle / "timeline.json").read_text())["frames"], key=lambda row: row["source_seconds"])
    for index in (0, 23):
        row = rows[index]
        try:
            observe_frame(bundle / row["file"], round(row["source_seconds"] * 1000), row["sha256"],
                          output / f"frame-{index:03d}", model, expected_model_digest=identity["digest"])
            print(index, "retained", flush=True)
        except Exception as exc:
            retain(output / f"failed-{index:03d}.json", {"error": str(exc), "type": type(exc).__name__})
            print(index, type(exc).__name__, flush=True)
            break  # Do not queue another request behind a timed-out server computation.


if __name__ == "__main__":
    main()
