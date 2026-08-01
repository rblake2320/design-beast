"""Run proof 001 after the editor is initialized and keep it alive for latent tasks."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[2] / "build_replay_capture.py"))
