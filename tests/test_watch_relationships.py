import pytest
from watch.relationships import FrameObservation, summarize, needs_rewind


def frame(ms, modality=None, control=None, result='Idle', key=None):
    return FrameObservation(ms=ms,sha256='a'*64,file=f'{ms}.jpg',modality=modality,control=control,result=result,key=key)


def test_consolidates_hits_not_independent_events():
    result=summarize([frame(0),frame(100,'mouse_down','Save'),frame(140,'mouse_down','Save'),frame(200),frame(400,result='Saved')])
    assert len(result['events'])==1
    assert len(result['events'][0]['frame_refs'])==2
    assert not needs_rewind(result)
    assert result['causal_sufficiency']=='unknown'
    assert result['accepted_causal_chains']==[]
    assert result['publication_allowed'] is False


def test_result_before_input_has_no_candidate():
    result=summarize([frame(0,result='Saved'),frame(100,'mouse_down','Save',result='Saved')])
    assert not result['temporal_candidates']
    assert needs_rewind(result)


def test_absent_hit_splits_events():
    result=summarize([frame(100,'mouse_down','Save'),frame(140),frame(180,'mouse_down','Save')])
    assert len(result['events'])==2


def test_multiple_inputs_remain_alternatives():
    result=summarize([frame(0),frame(100,'mouse_down','Inspect'),frame(150),frame(200,'mouse_down','Save'),frame(500,result='Saved')])
    assert len(result['temporal_candidates'])==2
    assert needs_rewind(result)


def test_indicator_without_control_cannot_complete_debt():
    result=summarize([frame(0),frame(100,'mouse_down'),frame(500,result='Saved')])
    assert needs_rewind(result)
    assert not result['temporal_candidates']


def test_keyboard_target_does_not_require_pointer():
    result=summarize([frame(0),frame(100,'key_down','Save',key='s'),frame(500,result='Saved')])
    assert not needs_rewind(result)
    assert result['events'][0]['pointer'] is None


def test_duplicate_stamp_rejected():
    with pytest.raises(ValueError): summarize([frame(100),frame(100)])


def test_empty_preserves_debt():
    result=summarize([])
    assert needs_rewind(result)
    assert result['confidence']=={'perception':None,'transition':None,'procedure':None}


def test_snapshot_change_detection_never_reopens_source(tmp_path):
    import io
    from PIL import Image
    from scripts.evaluate_watch_relationships import snapshot_changes
    snapshots={}
    for stamp, color in ((0,'black'),(100,'white')):
        output=io.BytesIO()
        Image.new('RGB',(8,8),color).save(output,format='PNG')
        snapshots[stamp]=output.getvalue()
    source=tmp_path/'frame.png'
    source.write_bytes(b'changed after snapshot')
    result=snapshot_changes(snapshots)
    assert result[0].mean_absolute_difference==255


def test_wrong_pixel_hash_fails_before_ocr():
    from scripts.evaluate_watch_relationships import inspect_pixels
    with pytest.raises(ValueError,match='snapshot hash'):
        inspect_pixels(b'wrong',{'sha256':'0'*64},'nonexistent-tesseract',1)


def scoring_case():
    result=summarize([frame(0),FrameObservation(ms=100,sha256='a'*64,file='100.jpg',
        modality='mouse_down',control='Save',control_bounds=(60,400,140,100)),frame(400,result='Saved')])
    report={'status':'completed','source_sha256':'b'*64,'frame_requests':3,'ocr_calls':3,
        'wall_seconds':1.0,'model_tokens':0,'summary':result}
    truth={'source_sha256':'b'*64,'events':[{'start_ms':100,'end_ms':100,'modality':'mouse_down',
        'key':None,'control':'Save','control_bounds':[60,400,140,100]}],
        'results':[{'start_ms':400,'end_ms':500,'identity':'Status: Saved'}],
        'permitted_temporal_pairs':[{'event_index':0,'result_index':0}],
        'causal_sufficiency':'unknown','required_abstention':True}
    return report,truth


def test_score_display_prefix_without_mutating_labels():
    from scripts.score_watch_relationships import grade
    report,truth=scoring_case()
    result=grade(report,truth)
    assert result['results_correct']==1
    assert result['temporal_pairs_correct']==1
    assert truth['results'][0]['identity']=='Status: Saved'


def test_wrong_control_gets_no_relationship_credit():
    from scripts.score_watch_relationships import grade
    report,truth=scoring_case()
    report['summary']['events'][0]['control']='Inspect'
    result=grade(report,truth)
    assert result['recovered_events']==1
    assert result['control_identity_correct']==0
    assert result['temporal_pairs_correct']==0
    assert result['false_temporal_pairs']==1


@pytest.mark.parametrize('seconds',[float('nan'),float('inf'),-1,121])
def test_invalid_budget_cannot_be_scored(seconds):
    from scripts.score_watch_relationships import grade
    report,truth=scoring_case()
    report['wall_seconds']=seconds
    with pytest.raises(ValueError): grade(report,truth)


def test_invented_event_span_rejected():
    from scripts.score_watch_relationships import grade
    report,truth=scoring_case()
    report['summary']['events'][0]['end_ms']=500
    with pytest.raises(ValueError,match='interval'): grade(report,truth)


def test_backwards_candidate_is_false_not_credit():
    from scripts.score_watch_relationships import grade
    report,truth=scoring_case()
    report['summary']['results'][1]['start_ms']=90
    truth['results'][0]['start_ms']=80
    result=grade(report,truth)
    assert result['temporal_pairs_correct']==0
    assert result['false_temporal_pairs']==1
