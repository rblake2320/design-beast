"""Pinned V-JEPA 2 clip embeddings; no semantic labels or action authority."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio.resource_guard import admission
from watch.inspection_runtime import digest, retain

MODEL = "facebook/vjepa2-vitl-fpc64-256"
REVISION = "b3c1679b7c34d3255ef3547f27c7b226aefab26f"


def run(bundle: Path, output: Path) -> dict[str, object]:
    import torch
    import numpy as np
    from PIL import Image
    from transformers import AutoVideoProcessor, VJEPA2Model

    rows = json.loads((bundle / "timeline.json").read_text(encoding="utf-8"))["frames"]
    if len(rows) != 61 or [row["source_seconds"] for row in rows] != [i/2 for i in range(61)]:
        raise ValueError("frozen encoder experiment requires 61 chronological 2fps frames")
    output.mkdir(parents=True, exist_ok=False)
    gate = admission("judge", use_cache=False)
    retain(output / "admission.json", gate)
    if not gate["admitted"]:
        raise RuntimeError("GPU admission denied before model load")
    retain(output / "intent.json", {"model": MODEL, "revision": REVISION,
        "timeline_sha256": digest(bundle / "timeline.json"), "starts": [0, 8, 16, 24, 32, 40, 45],
        "frames_per_window": 16, "source_sample_rate": 2, "resolution": 256,
        "max_windows": 7, "gpu_allocator_cap_mib": 6144, "semantic_acceptances": 0,
        "warning": "Temporal embeddings, not pretrained GUI event labels; sampling differs from training"})
    started = time.monotonic()
    try:
        torch.set_num_threads(4)
        torch.cuda.set_per_process_memory_fraction(6144*1048576 / torch.cuda.get_device_properties(0).total_memory, 0)
        torch.cuda.reset_peak_memory_stats()
        processor = AutoVideoProcessor.from_pretrained(MODEL, revision=REVISION, trust_remote_code=False)
        model = VJEPA2Model.from_pretrained(MODEL, revision=REVISION, trust_remote_code=False,
                                          use_safetensors=True, torch_dtype=torch.float16,
                                          attn_implementation="sdpa").eval()
        device_gate = admission("judge", use_cache=False)
        retain(output / "device-admission.json", device_gate)
        if not device_gate["admitted"]:
            raise RuntimeError("GPU admission changed during download; refusing device load")
        model = model.to("cuda:0")
        windows = []
        previous = None
        for window, start in enumerate((0, 8, 16, 24, 32, 40, 45)):
            frames = []
            refs = []
            for row in rows[start:start+16]:
                path = (bundle / row["file"]).resolve()
                if not path.is_relative_to(bundle.resolve()):
                    raise ValueError("frame escapes bundle")
                pixels = path.read_bytes()
                if hashlib.sha256(pixels).hexdigest() != row["sha256"]:
                    raise ValueError("encoder input custody mismatch")
                with Image.open(io.BytesIO(pixels)) as image:
                    frames.append(np.array(image.convert("RGB")))
                refs.append({"clip_ms": round(row["source_seconds"]*1000), "sha256": row["sha256"]})
            inputs = processor(videos=np.stack(frames), return_tensors="pt")
            inputs = {key: value.to("cuda:0", dtype=torch.float16) for key, value in inputs.items()}
            with torch.inference_mode():
                encoded = model(**inputs, skip_predictor=True).last_hidden_state.float().mean(dim=1)[0]
                vector = torch.nn.functional.normalize(encoded, dim=0).cpu()
            if not bool(torch.isfinite(vector).all()) or vector.numel() != 1024:
                raise ValueError("invalid temporal embedding")
            distance = None if previous is None else float(1-torch.dot(previous, vector))
            result = {"window": window, "frames": refs, "embedding": vector.tolist(),
                "distance_from_previous": distance, "evidence_class": "uncalibrated_temporal_features",
                "procedure_confidence": None}
            retain(output / f"window-{window:02d}.json", result)
            previous = vector
            windows.append({"window": window, "start_ms": refs[0]["clip_ms"], "end_ms": refs[-1]["clip_ms"],
                            "distance_from_previous": distance})
            sys.stdout.write(json.dumps({"window": window, "status": "encoded"})+"\n")
            sys.stdout.flush()
        report = {"windows": windows, "model": MODEL, "revision": REVISION,
            "elapsed_seconds": time.monotonic()-started, "peak_allocated_mib": torch.cuda.max_memory_allocated()/1048576,
            "semantic_acceptances": 0, "procedure_promotions": 0, "provider_cost_usd": 0}
        retain(output / "report.json", report)
        return report
    except Exception as exc:
        retain(output / "failure.json", {"error": str(exc), "type": type(exc).__name__})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle, args.output)


if __name__ == "__main__":
    main()
