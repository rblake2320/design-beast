"""Apply frozen Watch schedules and pixel-only overlay OCR with matched caps."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_watch_rewind import evaluate
from scripts.observe_watch_input_overlays import observe
from watch.inspection_runtime import digest,retain


def run(root: Path, seeds: Path, output: Path, tesseract: str) -> None:
    output.mkdir(parents=True,exist_ok=False)
    retain(output/'protocol.json',{'frozen_labels_sha256':digest(seeds/'BLIND-LABELS.json'),
        'request_cap_per_arm':16,'requested_output_frame_cap_per_arm':16,
        'frame_charge_unit':'requested output-frame timestamp; repeated endpoints are charged again',
        'internal_decoder_frames_measured':False,'internal_decoder_frame_cap':None,
        'ocr_cap_per_arm':16,'model_token_cap':0,
        'sampling_seconds_cap':60,'ocr_seconds_cap':60,'cases':4,
        'input':'videos, reviewed result anchors; no DOM, private telemetry or blind-label contents',
        'graduation':'more independently labeled input events recovered than baseline, no additional false input events',
        'boundary':'explicit input-indicator OCR test; no VLM or causal-chain certification',
        'code_sha256':{p:digest(Path(__file__).resolve().parents[1]/p) for p in
            ('scripts/compare_watch_positive_controls.py','scripts/observe_watch_input_overlays.py','scripts/evaluate_watch_rewind.py')}})
    results=[]
    try:
        for index in range(1,5):
            name=f'case-{index:02d}'
            trial=output/name
            evaluate(root/name/'review',seeds/f'{name}-units.json',trial,reverse_order=bool(index%2))
            for arm in ('watch-adaptive-bounded','debt-rewind'):
                result=observe(trial/arm,trial/(arm+'-ocr'),tesseract)
                results.append({'case':name,'arm':arm,'observed_inputs':result['observed_inputs'],
                    'ocr_calls':result['ocr_calls'],'elapsed_seconds':result['elapsed_seconds']})
        retain(output/'report.json',{'results':results,'status':'ready_for_blind_label_scoring','publication_allowed':False})
    except Exception as exc:
        retain(output/'failure.json',{'status':'incomplete_do_not_score','error':str(exc),'type':type(exc).__name__})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('root','seeds','output'): p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--tesseract',default='tesseract')
    a=p.parse_args()
    run(a.root,a.seeds,a.output,a.tesseract)
