"""Score independent event/control/result labels separately from temporal pairs."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import retain


def iou(a: list | tuple | None, b: list | tuple | None) -> float:
    if a is None or b is None: return 0.0
    x,y=max(a[0],b[0]),max(a[1],b[1])
    right,bottom=min(a[0]+a[2],b[0]+b[2]),min(a[1]+a[3],b[1]+b[3])
    overlap=max(0,right-x)*max(0,bottom-y)
    union=a[2]*a[3]+b[2]*b[3]-overlap
    return overlap/union if union else 0.0


def grade(report: dict, truth: dict) -> dict:
    if report['status']!='completed' or report['source_sha256']!=truth['source_sha256']:
        raise ValueError('incomplete or foreign source')
    if report['frame_requests']>16 or report['ocr_calls']>16 or report['wall_seconds']>120 or report['model_tokens']:
        raise ValueError('budget exceeded')
    summary=report['summary']
    if summary['accepted_causal_chains'] or summary['publication_allowed']:
        raise ValueError('causal/publication containment violation')
    mapping: dict[int,int]={}
    used: set[int]=set()
    controls=0
    boxes=0
    for pi,predicted in enumerate(summary['events']):
        for ti,actual in enumerate(truth['events']):
            if ti in used or (predicted['modality'],predicted['key'])!=(actual['modality'],actual['key']): continue
            if any(actual['start_ms']-40<=ref['ms']<=actual['end_ms']+40 for ref in predicted['frame_refs']):
                mapping[pi]=ti
                used.add(ti)
                controls+=predicted['control']==actual['control'] and actual['control'] is not None
                boxes+=iou(predicted['control_bounds'],actual['control_bounds'])>=0.5
                break
    result_mapping: dict[int,int]={}
    used_results: set[int]=set()
    for pi,predicted in enumerate(summary['results']):
        if predicted['identity'].lower()=='idle': continue
        for ti,actual in enumerate(truth['results']):
            if ti not in used_results and predicted['identity']==actual['identity'] and actual['start_ms']-40<=predicted['start_ms']<=actual['end_ms']+40:
                result_mapping[pi]=ti
                used_results.add(ti)
                break
    allowed={(p['event_index'],p['result_index']) for p in truth['permitted_temporal_pairs']}
    matched=set()
    false_pairs=0
    for pair in summary['temporal_candidates']:
        key=(mapping.get(pair['event_index'],-1),result_mapping.get(pair['result_index'],-1))
        if key in allowed and key not in matched: matched.add(key)
        else: false_pairs+=1
    return {'expected_events':len(truth['events']),'recovered_events':len(used),
        'false_event_extras':len(summary['events'])-len(used),'control_identity_correct':int(controls),
        'control_bounds_correct':int(boxes),'expected_results':len(truth['results']),
        'results_correct':len(used_results),'false_result_extras':sum(r['identity'].lower()!='idle' for r in summary['results'])-len(used_results),
        'expected_temporal_pairs':len(allowed),'temporal_pairs_correct':len(matched),'false_temporal_pairs':false_pairs,
        'causal_sufficiency_correct':summary['causal_sufficiency']==truth['causal_sufficiency'],
        'required_abstention':truth['required_abstention'],
        'abstention_correct':truth['required_abstention'] and summary['causal_sufficiency']=='unknown',
        'recovered_truth_events':sorted(used),
        'frame_requests':report['frame_requests'],'ocr_calls':report['ocr_calls'],'wall_seconds':report['wall_seconds']}


def score(run: Path, labels: list[Path], output: Path) -> None:
    raw=[p.read_bytes() for p in labels]
    intent=json.loads((run/'intent.json').read_bytes())
    if [hashlib.sha256(b).hexdigest() for b in raw]!=intent['labels_sha256']:
        raise ValueError('frozen labels changed')
    truths=[c for b in raw for c in json.loads(b)['cases']]
    if {c['case'] for c in truths}!={f'case-{i:02d}' for i in range(1,11)} or len(truths)!=10:
        raise ValueError('incomplete/duplicate frozen case set')
    rows=[]
    hashes={}
    for truth in truths:
        for mode in ('baseline','conditional'):
            path=run/truth['case']/mode/'report.json'
            snapshot=path.read_bytes()
            hashes[str(path.relative_to(run))]=hashlib.sha256(snapshot).hexdigest()
            rows.append({'case':truth['case'],'mode':mode,**grade(json.loads(snapshot),truth)})
    totals={mode:{key:sum(row[key] for row in rows if row['mode']==mode) for key in
        ('expected_events','recovered_events','false_event_extras','control_identity_correct','control_bounds_correct',
         'expected_results','results_correct','false_result_extras','expected_temporal_pairs','temporal_pairs_correct','false_temporal_pairs',
         'abstention_correct','frame_requests','ocr_calls','wall_seconds')} for mode in ('baseline','conditional')}
    additional=sum(len(set(next(r for r in rows if r['case']==c and r['mode']=='conditional')['recovered_truth_events'])-
        set(next(r for r in rows if r['case']==c and r['mode']=='baseline')['recovered_truth_events'])) for c in {r['case'] for r in rows})
    passed=(additional>=2 and totals['conditional']['false_temporal_pairs']<=totals['baseline']['false_temporal_pairs']
            and totals['conditional']['false_event_extras']<=totals['baseline']['false_event_extras']
            and totals['conditional']['recovered_events']>totals['baseline']['recovered_events'])
    retain(output,{'rows':rows,'totals':totals,'additional_recovered_events':additional,
        'graduation':'PASS' if passed else 'FAIL','report_sha256':hashes,'labels_sha256':intent['labels_sha256'],
        'boundary':'temporal candidates are not causal links; unknown causal labels test abstention, not successful causal recovery'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('run','labels-a','labels-b','output'): p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    score(a.run,[a.labels_a,a.labels_b],a.output)
