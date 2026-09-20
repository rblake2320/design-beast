import pytest
from scripts.observe_watch_input_overlays import parse_overlay


@pytest.mark.parametrize('text',['Status Saved','Save','Mouse button UP','Key S UP','mouse moved',''])
def test_result_or_motion_does_not_imply_input(text):
    assert parse_overlay(text) is None


def test_explicit_mouse_indicator():
    assert parse_overlay('Save Mouse button DOWN') == {'kind':'mouse_down','key':None}


def test_explicit_key_indicator():
    assert parse_overlay('Key S DOWN Status Unsaved') == {'kind':'key_down','key':'s'}


def test_ocr_uses_checked_byte_snapshot(tmp_path, monkeypatch):
    import hashlib,json,subprocess
    from scripts.observe_watch_input_overlays import observe
    pixels=b'checked synthetic pixels'
    (tmp_path/'f.jpg').write_bytes(pixels)
    payload={'frames':[{'file':'f.jpg','sha256':hashlib.sha256(pixels).hexdigest(),'source_seconds':1.0}]}
    raw=json.dumps(payload).encode()
    (tmp_path/'report.json').write_bytes(raw)
    def run(argv,**kwargs):
        (tmp_path/'f.jpg').write_bytes(b'changed after snapshot')
        (tmp_path/'report.json').write_bytes(b'changed after snapshot')
        assert argv[1]=='stdin' and kwargs['input']==pixels
        return subprocess.CompletedProcess(argv,0,stdout=b'level\tleft\ttop\twidth\theight\ttext\n',stderr=b'')
    monkeypatch.setattr(subprocess,'run',run)
    observe(tmp_path,tmp_path/'out','fake-ocr')
    intent=json.loads((tmp_path/'out/intent.json').read_bytes())
    assert intent['input_report_sha256']==hashlib.sha256(raw).hexdigest()
