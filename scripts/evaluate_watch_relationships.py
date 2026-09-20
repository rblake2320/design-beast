"""Matched CPU inspection and image-byte-bound OCR; hidden labels are never parsed."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageStat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.observe_watch_input_overlays import parse_overlay
from watch.inspection import Confidence, InspectionContext, Interval
from watch.inspection_runtime import digest, execute_inspection, retain
from watch.relationships import FrameObservation, summarize, needs_rewind
from watch.rewind import ChangeSample, budget_fps, refinement, request


def snapshot_changes(snapshots: dict[int, bytes]) -> tuple[ChangeSample, ...]:
    """Use the very same image snapshots inspected by OCR; never reopen files."""
    stamps = sorted(snapshots)
    pairs = []
    for before, after in zip(stamps,stamps[1:]):
        with Image.open(io.BytesIO(snapshots[before])) as a, Image.open(io.BytesIO(snapshots[after])) as b:
            if a.size != b.size: raise ValueError('frame dimensions changed')
            stat = ImageStat.Stat(ImageChops.difference(a.convert('RGB'),b.convert('RGB')))
            pairs.append(ChangeSample(start_ms=before,end_ms=after,mean_absolute_difference=sum(stat.mean)/3))
    return tuple(pairs)


def inspect_pixels(pixels: bytes, frame: dict, tesseract: str, timeout: float) -> tuple[FrameObservation, list[dict]]:
    if hashlib.sha256(pixels).hexdigest() != frame['sha256']:
        raise ValueError('frame snapshot hash mismatch')
    completed = subprocess.run([tesseract,'stdin','stdout','--psm','11','tsv'], input=pixels,
        capture_output=True,check=True,timeout=timeout)
    rows = list(csv.DictReader(io.StringIO(completed.stdout.decode('utf-8')),delimiter='\t'))
    words = [{'text':r['text'],'box':[int(r[k]) for k in ('left','top','width','height')],
              'line':[r['block_num'],r['par_num'],r['line_num']]} for r in rows if r.get('text','').strip()]
    detected = parse_overlay(' '.join(w['text'] for w in words))
    image = np.asarray(Image.open(io.BytesIO(pixels)).convert('RGB'))
    mask = ((image[:,:,0]>190)&(image[:,:,1]>135)&(image[:,:,1]<235)&(image[:,:,2]<110)).astype('uint8')
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    targets = []
    for x,y,w,h,area in stats[1:]:
        if area < 3000: continue
        text = ' '.join(item['text'] for item in words
            if x <= item['box'][0]+item['box'][2]/2 <= x+w and y <= item['box'][1]+item['box'][3]/2 <= y+h)
        if text: targets.append((text, (int(x),int(y),int(w),int(h))))
    control, bounds = targets[0] if detected and len(targets)==1 else (None,None)
    pointer_mask = (image[:,:,0]>180)&(image[:,:,1]<125)&(image[:,:,2]>160)
    ys,xs = np.where(pointer_mask)
    pointer = (round(float(xs.mean())),round(float(ys.mean()))) if len(xs)>30 else None
    result = None
    for index, word in enumerate(words[:-1]):
        if word['text'].rstrip(':').lower() == 'status' and word['line'] == words[index+1]['line']:
            result = words[index+1]['text'].strip('.,:')
    return FrameObservation(ms=round(frame['source_seconds']*1000),sha256=frame['sha256'],file=frame['file'],
        modality=detected['kind'] if detected else None,key=detected['key'] if detected else None,
        control=control,control_bounds=bounds,pointer=pointer,result=result), words


def arm(source: Path, output: Path, mode: str, duration_ms: int, tesseract: str, expected_source_hash: str) -> dict:
    output.mkdir(parents=True,exist_ok=False)
    source_hash = digest(source)
    if source_hash != expected_source_hash: raise ValueError('case source identity changed between arms')
    shutil.copyfile(source,output/'source.webm')
    retain(output/'timeline.json',{'schema':'beast.watch.timeline/v3',
        'source':{'local_video':'source.webm','range':{'start_seconds':0,'end_seconds':duration_ms/1000,
        'start':'0','end':str(duration_ms/1000)}},'sampling':{'height':720},'frames':[]})
    span = Interval(start_ms=0,end_ms=duration_ms)
    context = InspectionContext(source_interval=span,candidate_interval=span,
        confidence=Confidence(perception=0,transition=0,procedure=0))
    started = time.monotonic()
    observations: dict[int,FrameObservation] = {}
    snapshots: dict[int,bytes] = {}
    charged = 0
    ocr_calls = 0
    def inspect(interval: Interval, cap: int, phase: str) -> list[dict]:
        nonlocal charged, ocr_calls
        left = 120-(time.monotonic()-started)
        if left <= 0 or charged+cap > 16: raise TimeoutError('shared budget exhausted')
        receipt = execute_inspection(output,'ffmpeg',request(interval,'Bounded relationship experiment'),
            context,cap,output/(phase+'.json'),fixed_fps=budget_fps(interval,cap),
            max_seconds=left,expected_source_sha256=source_hash)
        charged += receipt['charged_frames']
        for frame in receipt['frames']:
            ms = round(frame['source_seconds']*1000)
            if ms in observations: continue
            if ocr_calls >= 16: raise ValueError('OCR cap exceeded')
            path = (output/frame['file']).resolve()
            if not path.is_relative_to(output.resolve()): raise ValueError('frame escape')
            left = 120-(time.monotonic()-started)
            if left <= 0: raise TimeoutError('shared wall budget exhausted')
            pixels = path.read_bytes()
            ocr_calls += 1
            observation, words = inspect_pixels(pixels,frame,tesseract,min(30,left))
            snapshots[ms] = pixels
            observations[ms] = observation
            retain(output/f'ocr-{ms:06d}.json',{'observation':observation.model_dump(),'words':words})
        return receipt['frames']
    try:
        frames = inspect(span,16 if mode=='baseline' else 5,'initial')
        routing = 'baseline_full_budget'
        if mode == 'conditional':
            initial = summarize(list(observations.values()))
            retain(output/'initial-summary.json',initial)
            routing = 'stop_temporal_candidate_complete'
            if needs_rewind(initial):
                decision = refinement(span,snapshot_changes(snapshots))
                routing = 'no_pixel_change_preserve_uncertainty'
                if decision:
                    routing = 'rewind_unresolved_temporal_candidate'
                    inspect(decision.target_interval,16-charged,'rewind')
        elapsed = time.monotonic()-started
        if elapsed > 120: raise TimeoutError('shared wall budget exceeded')
        if digest(source) != source_hash: raise ValueError('source changed')
        report = {'mode':mode,'source_sha256':source_hash,'summary':summarize(list(observations.values())),
            'observations':[o.model_dump() for o in sorted(observations.values(),key=lambda o:o.ms)],
            'routing':routing,'frame_requests':charged,'ocr_calls':ocr_calls,'wall_seconds':elapsed,
            'gpu_seconds':0,'model_tokens':0,'internal_codec_decodes':None,'status':'completed'}
        retain(output/'report.json',report)
        return report
    except Exception as exc:
        retain(output/'failure.json',{'error':str(exc),'frame_requests':charged,'ocr_calls':ocr_calls,
            'wall_seconds':time.monotonic()-started,'status':'incomplete_do_not_score'})
        raise


def run(root: Path, labels_a: Path, labels_b: Path, output: Path, tesseract: str) -> None:
    output.mkdir(parents=True,exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    retain(output/'intent.json',{'labels_sha256':[digest(labels_a),digest(labels_b)],
        'protocol_sha256':digest(repo/'bench/watch-relationships-v1.json'),
        'code_sha256':{p:digest(repo/p) for p in ('watch/relationships.py','scripts/evaluate_watch_relationships.py',
            'scripts/observe_watch_input_overlays.py','watch/rewind.py','watch/inspection.py',
            'watch/inspection_runtime.py','watch/seek.py','watch/core.py')},
        'boundary':'label bytes hashed only, contents unavailable to observer; causal sufficiency never accepted'})
    for i in range(1,11):
        source = root/f'case-{i:02d}'/'source.webm'
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
            '-of','json',str(source)],capture_output=True,check=True,timeout=20).stdout)
        duration_ms=int(float(probe['format']['duration'])*1000)-80
        expected_source_hash=digest(source)
        for mode in (('baseline','conditional') if i%2 else ('conditional','baseline')):
            arm(source,output/f'case-{i:02d}'/mode,mode,duration_ms,tesseract,expected_source_hash)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('root','labels-a','labels-b','output'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--tesseract',default='tesseract')
    a=parser.parse_args()
    run(a.root,a.labels_a,a.labels_b,a.output,a.tesseract)
