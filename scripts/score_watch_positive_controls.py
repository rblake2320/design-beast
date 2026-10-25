"""Score case-level visible-input recovery against frozen reviewer labels."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest,retain


def score(run: Path, labels: Path, output: Path) -> dict:
    protocol=json.loads((run/'protocol.json').read_bytes())
    label_bytes=labels.read_bytes()
    label_hash=hashlib.sha256(label_bytes).hexdigest()
    report_bytes=(run/'report.json').read_bytes()
    if label_hash!=protocol['frozen_labels_sha256']: raise ValueError('blind labels changed')
    truth=json.loads(label_bytes)
    report=json.loads(report_bytes)
    mapping={'mouse_down_indicator_over_save':('mouse_down',None),'key_s_down_indicator':('key_down','s'),
        'not_observed_in_sparse_samples':None}
    expected={c['case_id']:mapping[c['visible_input_kind']] for c in truth['cases']}
    tally={arm:{'recovered_positive_cases':0,'false_input_cases':0,'correct_negative_cases':0} for arm in ('watch-adaptive-bounded','debt-rewind')}
    seen=set()
    for row in report['results']:
        identity=(row['case'],row['arm'])
        if identity in seen: raise ValueError('duplicate scored arm')
        seen.add(identity)
        wanted=expected[row['case']]
        proposals={(p['kind'],p['key']) for p in row['observed_inputs']}
        totals=tally[row['arm']]
        if wanted is not None and wanted in proposals: totals['recovered_positive_cases']+=1
        if proposals-({wanted} if wanted is not None else set()): totals['false_input_cases']+=1
        if wanted is None and not proposals: totals['correct_negative_cases']+=1
    if len(seen)!=len(expected)*2: raise ValueError('incomplete matrix')
    baseline,rewind=tally['watch-adaptive-bounded'],tally['debt-rewind']
    verdict='PASS' if rewind['recovered_positive_cases']>baseline['recovered_positive_cases'] and rewind['false_input_cases']<=baseline['false_input_cases'] else 'FAIL'
    result={'labels_sha256':label_hash,'report_sha256':hashlib.sha256(report_bytes).hexdigest(),'tally':tally,
        'rewind_graduation':verdict,'unit':'case-level recognition of explicit visible input indicators, not number of frames or causal chains',
        'publication_allowed':False}
    retain(output,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('run','labels','output'): p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    score(a.run,a.labels,a.output)
