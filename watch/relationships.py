"""Experimental visual-sequence proposals. No causal or publication authority."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


def box_iou(a: list | tuple | None, b: list | tuple | None) -> float:
    if a is None or b is None: return 0.0
    overlap=max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    union=a[2]*a[3]+b[2]*b[3]-overlap
    return overlap/union if union else 0.0


class FrameObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    ms: int = Field(ge=0)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    file: str
    modality: Literal['mouse_down', 'key_down'] | None = None
    key: str | None = None
    control: str | None = None
    control_bounds: tuple[int, int, int, int] | None = None
    control_reference_ms: int | None = None
    control_reference_sha256: str | None = None
    pointer: tuple[int, int] | None = None
    result: str | None = None


def summarize(observations: list[FrameObservation]) -> dict:
    """Group inspected hits, retaining gaps rather than claiming continuous input."""
    ordered = sorted(observations, key=lambda f: f.ms)
    if len({f.ms for f in ordered}) != len(ordered):
        raise ValueError('duplicate observation timestamp')
    events: list[dict] = []
    previous: FrameObservation | None = None
    for row in ordered:
        if row.modality:
            same = previous is not None and previous.modality == row.modality and previous.key == row.key and previous.control == row.control
            if not same:
                events.append({'start_ms':row.ms,'end_ms':row.ms,'modality':row.modality,
                    'key':row.key,'control':row.control,'control_bounds':row.control_bounds,
                    'pointer':row.pointer,'frame_refs':[], 'unsampled_continuity':'unknown'})
                events[-1]['control_reference']={'ms':row.control_reference_ms,'sha256':row.control_reference_sha256}
            events[-1]['end_ms'] = row.ms
            events[-1]['frame_refs'].append({'ms':row.ms,'sha256':row.sha256,'file':row.file})
        previous = row
    results: list[dict] = []
    last: str | None = None
    for row in ordered:
        if row.result is None:
            continue
        if row.result != last:
            results.append({'identity':row.result,'start_ms':row.ms,'end_ms':row.ms,
                            'frame_refs':[{'ms':row.ms,'sha256':row.sha256,'file':row.file}]})
        else:
            results[-1]['end_ms'] = row.ms
            results[-1]['frame_refs'].append({'ms':row.ms,'sha256':row.sha256,'file':row.file})
        last = row.result
    candidates: list[dict] = []
    for ri, result in enumerate(results):
        if result['identity'].lower() == 'idle':
            continue
        # Require a distinct, earlier observed state. A result already on screen
        # before input is not a transition attributed to that later input.
        prior = results[ri-1] if ri else None
        if prior is None:
            continue
        for ei, event in enumerate(events):
            if (event['control'] and prior['start_ms'] <= event['start_ms']
                    and event['end_ms'] < result['start_ms']):
                candidates.append({'event_index':ei,'result_index':ri,
                    'relationship':'temporal_candidate','causal_sufficiency':'unknown'})
    return {'events':events,'results':results,'temporal_candidates':candidates,
        'causal_sufficiency':'unknown','accepted_causal_chains':[], 'publication_allowed':False,
        'confidence':{'perception':None,'transition':None,'procedure':None}}


def needs_rewind(summary: dict) -> bool:
    """Routing on temporal-candidate debt only; never a procedure-complete flag."""
    return not (len(summary['events']) == 1 and summary['events'][0]['control']
                and len(summary['temporal_candidates']) == 1)
