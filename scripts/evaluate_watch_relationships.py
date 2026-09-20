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
from watch.relationships import FrameObservation, summarize, needs_rewind, prior_control, contains_pointer
from watch.rewind import ChangeSample, budget_fps, refinement, request


def ocr_mosaic(image: np.ndarray) -> tuple[bytes, list[tuple[int,int,int,int,int]]]:
    """Append border-free panel crops, with exact source-coordinate mappings."""
    white=((image[:,:,0]>225)&(image[:,:,1]>225)&(image[:,:,2]>225)).astype('uint8')*255
    contours,_=cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    rectangles=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w>=80 and 60<=h<=300 and w*h<image.shape[0]*image.shape[1]/2:
            rectangles.append((x+7,y+7,w-14,h-14))
    gold=((image[:,:,0]>180)&(image[:,:,1]>130)&(image[:,:,2]<120)).astype('uint8')*255
    joined=cv2.morphologyEx(gold,cv2.MORPH_CLOSE,np.ones((5,30),dtype='uint8'))
    lines,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for contour in lines:
        x,y,w,h=cv2.boundingRect(contour)
        if w>40 and 10<=h<=45:
            x0,y0=max(0,x-10),max(0,y-10)
            rectangles.append((x0,y0,min(image.shape[1]-x0,w+20),min(image.shape[0]-y0,h+20)))
    rectangles=sorted(rectangles,key=lambda r:(r[1],r[0]))
    height=image.shape[0]+sum(h+30 for x,y,w,h in rectangles)
    canvas=Image.new('RGB',(image.shape[1],height),'white')
    canvas.paste(Image.fromarray(image),(0,0))
    mappings=[]
    top=image.shape[0]+15
    for x,y,w,h in rectangles:
        crop=cv2.cvtColor(image[y:y+h,x:x+w],cv2.COLOR_RGB2GRAY)
        if float(np.median(crop))<128: crop=255-crop
        canvas.paste(Image.fromarray(crop).convert('RGB'),(15,top))
        mappings.append((top,x,y,w,h))
        top+=h+30
    data=io.BytesIO()
    canvas.save(data,format='PNG')
    return data.getvalue(),mappings


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


def result_bracket(observations: list[FrameObservation]) -> Interval | None:
    rows=sorted((o for o in observations if o.result is not None),key=lambda o:o.ms)
    for before,after in zip(rows,rows[1:]):
        if before.result!=after.result and after.result.lower()!='idle':
            return Interval(start_ms=before.ms,end_ms=after.ms)
    return None


def inspect_pixels(pixels: bytes, frame: dict, tesseract: str, timeout: float) -> tuple[FrameObservation, list[dict]]:
    if hashlib.sha256(pixels).hexdigest() != frame['sha256']:
        raise ValueError('frame snapshot hash mismatch')
    image = np.asarray(Image.open(io.BytesIO(pixels)).convert('RGB'))
    ocr_pixels,mappings=ocr_mosaic(image)
    completed = subprocess.run([tesseract,'stdin','stdout','--psm','11','tsv'], input=ocr_pixels,
        capture_output=True,check=True,timeout=timeout)
    rows = list(csv.DictReader(io.StringIO(completed.stdout.decode('utf-8')),delimiter='\t'))
    words = [{'text':r['text'],'box':[int(r[k]) for k in ('left','top','width','height')],
              'line':[r['block_num'],r['par_num'],r['line_num']]} for r in rows if r.get('text','').strip()]
    for word in words:
        word['origin']='global'
        for top,x,y,w,h in mappings:
            if top<=word['box'][1]<top+h:
                word['box'][0]+=x-15
                word['box'][1]+=y-top
                word['origin']='border_free_crop'
                word['panel_box']=[x,y,w,h]
                break
    detected = parse_overlay(' '.join(w['text'] for w in words))
    mask = ((image[:,:,0]>190)&(image[:,:,1]>135)&(image[:,:,1]<235)&(image[:,:,2]<110)).astype('uint8')
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    targets = []
    for x,y,w,h,area in stats[1:]:
        if area < 3000: continue
        text = ' '.join(item['text'] for item in words
            if item['origin']=='border_free_crop' and x <= item['box'][0]+item['box'][2]/2 <= x+w and y <= item['box'][1]+item['box'][3]/2 <= y+h)
        targets.append((text or None, (int(x),int(y),int(w),int(h))))
    control, bounds = targets[0] if detected and len(targets)==1 else (None,None)
    pointer_mask = (image[:,:,0]>180)&(image[:,:,1]<125)&(image[:,:,2]>160)
    ys,xs = np.where(pointer_mask)
    pointer = (round(float(xs.mean())),round(float(ys.mean()))) if len(xs)>30 else None
    result = None
    for index, word in enumerate(words[:-1]):
        if word['origin']=='border_free_crop' and word['text'].rstrip(':').lower() == 'status' and word['line'] == words[index+1]['line']:
            result = words[index+1]['text'].strip('.,:')
    return FrameObservation(ms=round(frame['source_seconds']*1000),sha256=frame['sha256'],file=frame['file'],
        modality=detected['kind'] if detected else None,key=detected['key'] if detected else None,
        control=control,control_bounds=bounds,pointer=pointer,result=result), words


def arm(source: Path, output: Path, mode: str, duration_ms: int, tesseract: str, expected_source_hash: str) -> dict:
    started = time.monotonic()
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
    observations: dict[int,FrameObservation] = {}
    snapshots: dict[int,bytes] = {}
    known_controls: list[tuple[tuple[int,int,int,int],str,int,str]] = []
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
            if observation.modality and observation.control_bounds:
                match=prior_control(known_controls,observation.control_bounds,ms)
                if match:
                    name,prior_ms,prior_hash=match
                    observation=observation.model_copy(update={'control':name,
                        'control_reference_ms':prior_ms,'control_reference_sha256':prior_hash})
                elif contains_pointer(observation.control_bounds,observation.pointer):
                    observation=observation.model_copy(update={'control':None})
            if observation.modality is None:
                panels={tuple(w['panel_box']) for w in words if w.get('panel_box')}
                for box in panels:
                    labels=[w['text'] for w in words if tuple(w.get('panel_box',()))==box]
                    if len(labels)==1 and labels[0].isalpha() and not contains_pointer(box,observation.pointer):
                        known_controls.append((box,labels[0],ms,frame['sha256']))
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
                # Two cheap early context frames can recover unoccluded labels.
                # They consume the SAME remaining budget, not extra free work.
                first_gap=duration_ms//4
                inspect(Interval(start_ms=max(1,first_gap//4),end_ms=3*first_gap//4),2,'control-context')
                for stamp,observation in list(observations.items()):
                    if observation.modality and observation.control_bounds:
                        match=prior_control(known_controls,observation.control_bounds,stamp)
                        if match:
                            name,prior_ms,prior_hash=match
                            observations[stamp]=observation.model_copy(update={'control':name,
                                'control_reference_ms':prior_ms,'control_reference_sha256':prior_hash})
                bracket=result_bracket(list(observations.values()))
                decision = request(bracket,'Known-case repair: prioritize observed result transition bracket') if bracket else refinement(span,snapshot_changes(snapshots))
                routing = 'no_pixel_change_preserve_uncertainty'
                if decision:
                    routing = 'rewind_unresolved_temporal_candidate'
                    inspect(decision.target_interval,16-charged,'rewind')
        if digest(source) != source_hash: raise ValueError('source changed')
        elapsed = time.monotonic()-started
        if elapsed > 120: raise TimeoutError('shared wall budget exceeded')
        report = {'mode':mode,'source_sha256':source_hash,'summary':summarize(list(observations.values())),
            'observations':[o.model_dump() for o in sorted(observations.values(),key=lambda o:o.ms)],
            'routing':routing,'frame_requests':charged,'ocr_calls':ocr_calls,'wall_seconds':elapsed,
            'gpu_seconds':0,'model_tokens':0,'internal_codec_decodes':None,'status':'completed'}
        report['inspection_interval_ms']=[0,duration_ms]
        report['wall_scope']='arm entry through final source verification; final report write excluded'
        retain(output/'report.json',report)
        return report
    except Exception as exc:
        retain(output/'failure.json',{'error':str(exc),'frame_requests':charged,'ocr_calls':ocr_calls,
            'wall_seconds':time.monotonic()-started,'status':'incomplete_do_not_score'})
        raise


def run(root: Path, labels_a: Path, labels_b: Path, output: Path, tesseract: str, baseline_from: Path | None = None) -> None:
    output.mkdir(parents=True,exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    retain(output/'intent.json',{'labels_sha256':[digest(labels_a),digest(labels_b)],
        'protocol_sha256':digest(repo/'bench/watch-relationships-v1.json'),
        'code_sha256':{p:digest(repo/p) for p in ('watch/relationships.py','scripts/evaluate_watch_relationships.py',
            'scripts/observe_watch_input_overlays.py','watch/rewind.py','watch/inspection.py',
            'watch/inspection_runtime.py','watch/seek.py','watch/core.py')},
        'boundary':'label bytes hashed only, contents unavailable to observer; causal sufficiency never accepted'})
    if baseline_from:
        retain(output/'repair-lineage.json',{'baseline_from':str(baseline_from),
            'baseline_intent_sha256':digest(baseline_from/'intent.json'),
            'classification':'known-case routing repair, not fresh blind graduation or paired timing',
            'changes':'two budgeted early unoccluded-control frames, then result bracket; prior label time guard; conflicting OCR does not split held spatial event'})
    for i in range(1,11):
        source = root/f'case-{i:02d}'/'source.webm'
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
            '-of','json',str(source)],capture_output=True,check=True,timeout=20).stdout)
        duration_ms=int(float(probe['format']['duration'])*1000)-80
        expected_source_hash=digest(source)
        for mode in (('baseline','conditional') if i%2 else ('conditional','baseline')):
            destination=output/f'case-{i:02d}'/mode
            if mode=='baseline' and baseline_from:
                original=baseline_from/f'case-{i:02d}'/mode
                report=json.loads((original/'report.json').read_bytes())
                if report['source_sha256']!=expected_source_hash: raise ValueError('retained baseline source mismatch')
                shutil.copytree(original,destination)
                retain(destination/'reuse-receipt.json',{'original_report_sha256':digest(original/'report.json'),
                    'execution':'retained original; not rerun under current code'})
            else:
                arm(source,destination,mode,duration_ms,tesseract,expected_source_hash)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('root','labels-a','labels-b','output'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--tesseract',default='tesseract')
    parser.add_argument('--baseline-from',type=Path)
    a=parser.parse_args()
    run(a.root,a.labels_a,a.labels_b,a.output,a.tesseract,a.baseline_from)
