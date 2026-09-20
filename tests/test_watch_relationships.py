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
