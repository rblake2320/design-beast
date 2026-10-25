"""Read explicit on-screen input indicators; no telemetry or causal authority."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest,retain


def parse_overlay(text: str) -> dict | None:
    normalized=' '.join(text.split())
    if re.search(r'\bMouse button DOWN\b',normalized,re.I):
        return {'kind':'mouse_down','key':None}
    match=re.search(r'\bKey (\S+) DOWN\b',normalized,re.I)
    return {'kind':'key_down','key':match.group(1).lower()} if match else None


def observe(bundle: Path, output: Path, tesseract: str) -> dict:
    raw=(bundle/'report.json').read_bytes()
    report=json.loads(raw)
    frames=report['frames']
    if not 1<=len(frames)<=16: raise ValueError('frame budget exceeded')
    output.mkdir(parents=True,exist_ok=False)
    retain(output/'intent.json',{'input_report_sha256':hashlib.sha256(raw).hexdigest(),'ocr_call_cap':16,
        'model_token_cap':0,'wall_seconds_cap':60,'parser':'explicit visible Mouse button DOWN / Key X DOWN indicators only',
        'scope':'overlay-aware OCR proposals, not arbitrary mouse detection or causal verification'})
    start=time.monotonic()
    observations=[]
    inputs=[]
    try:
        for index,frame in enumerate(frames):
            path=(bundle/frame['file']).resolve()
            if not path.is_relative_to(bundle.resolve()):
                raise ValueError('frame path escapes bundle')
            pixels=path.read_bytes()
            if hashlib.sha256(pixels).hexdigest()!=frame['sha256']:
                raise ValueError('frame custody failed')
            remaining=60-(time.monotonic()-start)
            if remaining<=0: raise TimeoutError('OCR budget exhausted')
            result=subprocess.run([tesseract,'stdin','stdout','--psm','11','tsv'],input=pixels,
                capture_output=True,check=True,timeout=min(30,remaining))
            tsv=result.stdout.decode('utf-8')
            rows=list(csv.DictReader(io.StringIO(tsv),delimiter='\t'))
            words=[{'text':r['text'],'box':[int(r[k]) for k in ('left','top','width','height')]} for r in rows if r.get('text','').strip()]
            text=' '.join(w['text'] for w in words)
            detected=parse_overlay(text)
            observation={'frame':frame,'words':words,'input_proposal':detected}
            retain(output/f'frame-{index:03d}.json',observation)
            observations.append(observation)
            if detected: inputs.append({'frame':frame,**detected})
        final={'observed_inputs':inputs,'ocr_calls':len(frames),'elapsed_seconds':time.monotonic()-start,
            'gpu_calls':0,'model_tokens':0,'publication_allowed':False,'causal_chains_accepted':0,
            'claim':'input indicators recognized from supplied frame pixels only; semantic review required'}
        retain(output/'report.json',final)
        return final
    except Exception as exc:
        retain(output/'failure.json',{'status':'incomplete_do_not_score','error':str(exc)})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('bundle','output'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--tesseract',default='tesseract')
    args=parser.parse_args()
    observe(args.bundle,args.output,args.tesseract)
