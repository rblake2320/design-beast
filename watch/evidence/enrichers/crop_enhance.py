"""
Reuses Design Beast's existing QUALITY-LOOP.md upscale/grade step, but
applied to a forensic crop instead of a generated image. CRITICAL:
always retains and hashes the ORIGINAL crop alongside the enhanced one —
generative enhancement must never be presented as recovered fact.
"""
import hashlib
import subprocess


def enhance_crop(input_path: str, output_path: str,
                  brightness: int = 100, saturation: int = 90,
                  black_point_pct: int = 2, white_point_pct: int = 98) -> dict:
    original_hash = hashlib.sha256(open(input_path, "rb").read()).hexdigest()
    cmd = ["magick", input_path, "-modulate", f"{brightness},{saturation}",
           "-level", f"{black_point_pct}%,{white_point_pct}%", output_path]
    subprocess.run(cmd, check=True)
    enhanced_hash = hashlib.sha256(open(output_path, "rb").read()).hexdigest()
    return {
        "original_path": input_path, "original_sha256": original_hash,
        "enhanced_path": output_path, "enhanced_sha256": enhanced_hash,
        "method": "deterministic_contrast_level",
        "generative": False,
    }
