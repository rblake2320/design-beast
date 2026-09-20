"""Record ten controlled browser cases and retain independent input telemetry."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain


def record(output: Path) -> None:
    from playwright.sync_api import sync_playwright
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/watch-relationship-lab.html'
    output.mkdir(parents=True, exist_ok=False)
    # Kept outside observer inputs. Case names do not expose expected answers.
    cases = [
        ('', [('save', 1200, 350)]),
        ('', [('reset', 1200, 350)]),
        ('outcome=Rejected', [('save', 1200, 350)]),
        ('timer=2100', [('inspect', 1200, 350)]),
        ('timer=800&disabled=save', [('save', 1800, 350)]),
        ('', [('inspect', 900, 350), ('save', 1900, 350)]),
        ('', [('key:s', 1200, 350)]),
        ('', [('save', 1320, 40)]),
        ('delay=2200', [('save', 900, 350), ('inspect', 1800, 350)]),
        ('timer=1600', []),
    ]
    retain(output / 'intent.json', {'fixture_sha256': digest(fixture), 'case_count': len(cases),
        'protocol_sha256': digest(fixture.parents[2] / 'bench/watch-relationships-v1.json')})
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel='chrome')
            try:
                for n, (query, actions) in enumerate(cases, 1):
                    case = output / f'case-{n:02d}'
                    case.mkdir()
                    context = browser.new_context(viewport={'width':1280,'height':720},
                        record_video_dir=str(case), record_video_size={'width':1280,'height':720})
                    page = context.new_page()
                    page.goto(fixture.as_uri() + '?' + query)
                    for control, at, hold in actions:
                        page.wait_for_function('(t)=>performance.now()>=t', arg=at)
                        if control.startswith('key:'):
                            key = control.split(':')[1]
                            page.keyboard.down(key)
                            page.wait_for_timeout(hold)  # Deliberate recorded stimulus duration.
                            page.keyboard.up(key)
                        else:
                            page.get_by_role('button', name=control, exact=False).hover()
                            page.mouse.down()
                            page.wait_for_timeout(hold)
                            page.mouse.up()
                    page.wait_for_function('performance.now()>=4400')
                    telemetry = page.evaluate('({events:events,origin:performance.timeOrigin})')
                    video = page.video
                    context.close()
                    video.save_as(str(case / 'source.webm'))
                    retain(case / 'telemetry-private.json', telemetry)
                    retain(case / 'receipt.json', {'source_sha256':digest(case/'source.webm')})
            finally:
                browser.close()
    except Exception as exc:
        retain(output/'failure.json', {'error':str(exc), 'status':'incomplete'})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    record(parser.parse_args().output)
