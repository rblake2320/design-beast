"""Known-frame diagnostic, explicitly separate from autonomous sampling scores."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_watch_relationships import inspect_pixels
from watch.inspection_runtime import digest,retain


def probe(review: Path, ms: int, output: Path, tesseract: str) -> None:
    manifest_bytes=(review/'manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes)
    matches=[r for r in manifest['frames'] if r['ms']==ms]
    if len(matches)!=1: raise ValueError('one exact native presentation required')
    row=matches[0]
    path=(review/row['image']).resolve()
    if not path.is_relative_to(review.resolve()): raise ValueError('frame escape')
    started=time.monotonic()
    observation,words=inspect_pixels(path.read_bytes(),{'sha256':row['sha256'],
        'file':row['image'],'source_seconds':ms/1000},tesseract,30)
    retain(output,{'classification':'oracle-selected native-frame diagnostic, not autonomous recovery',
        'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'source_sha256':manifest['source_sha256'],
        'observation':observation.model_dump(),'words':words,'ocr_calls':1,
        'wall_seconds':time.monotonic()-started,'publication_allowed':False,
        'observer_sha256':digest(Path(__file__).with_name('evaluate_watch_relationships.py'))})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--ms',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tesseract',default='tesseract')
    a=p.parse_args()
    probe(a.review,a.ms,a.output,a.tesseract)
