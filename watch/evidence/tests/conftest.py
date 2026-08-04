"""Path setup for the package's flat-import style.

Extractors import siblings directly (``from base import BaseExtractor``), so
both the evidence root and extractors/ must be importable. Without this, any
test that imports an extractor fails collection — latent until the safety
extractor tests first exercised it.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "extractors")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
