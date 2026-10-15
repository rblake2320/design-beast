"""Validate retained audit conclusions, not new live media or customer outcomes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/'proofs/product-value-audit'


def receipt(name):
    return json.loads((ROOT/f'{name}.json').read_bytes())


def test_prepare_produced_review_not_automatic_tutorial():
    assert receipt('prepare')['returncode'] == 0
    data = receipt('browser')
    assert data['frames'] == 62
    assert data['caption_author'].startswith('audit operator')
    assert data['human_time'] is None
    assert not data['browser_errors']
    assert not data['mobile_overflow']


def test_playable_source_only_output():
    report = receipt('render-report')
    assert report['duration_ms'] == 2000
    assert report['generated_visuals'] == 0
    assert report['verified_procedure'] is False
    assert report['publication_allowed'] is False
    playback = receipt('playback')
    assert playback['duration'] == 2
    assert playback['time'] > .4
    assert playback['error'] is None
    assert receipt('decode')['returncode'] == 0


def test_automatic_failure_is_not_success():
    result = receipt('automatic')
    assert result['returncode'] != 0
    assert json.loads(result['stderr'])['type'] == 'URLError'


def test_fidelity_is_one_sample_not_whole_video_proof():
    result = receipt('source-fidelity')
    assert result['samples'] == 1
    assert result['caption_band_excluded']
    assert all(0 <= x < 1 for x in result['mean_absolute_error_rgb'])


def test_no_customer_savings_claim():
    assert receipt('complete')['customer_savings_measured'] is False
    assert receipt('intent')['real_users_recruited'] == 0


def test_main_help_is_not_feature_execution():
    result = receipt('main-entrypoint')
    assert result['returncode'] == 0
    assert 'beast doctor' in result['stdout']
    assert 'watch-training' not in result['stdout']
