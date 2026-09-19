"""Record actual browser inputs in a controlled fixture; keep telemetry separate."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest,retain


def record(output: Path) -> None:
    from playwright.sync_api import sync_playwright
    fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/watch-input-lab.html'
    output.mkdir(parents=True,exist_ok=False)
    retain(output/'protocol.json',{'fixture_sha256':digest(fixture),'kind':'controlled real browser video',
        'inputs':'Playwright mouse/keyboard events; trusted DOM event telemetry recorded independently of images',
        'overlay':'test application displays actual down/up events; not added to video afterward',
        'negative':'matched mouse recording trimmed after input; original full recording retained',
        'cases':['case-01','case-02','case-03','case-04'],'recovery_access':'video only; no DOM or telemetry',
        'claim':'positive controls, not natural third-party tutorials; browser recorder FPS must be measured'})
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,channel='chrome')
        try:
            for index,mode,delay in ((1,'mouse',250),(2,'keyboard',250),(3,'mouse',1500)):
                case=output/f'case-{index:02d}'
                case.mkdir()
                context=browser.new_context(viewport={'width':1280,'height':720},record_video_dir=str(case),record_video_size={'width':1280,'height':720})
                page=context.new_page()
                page.goto(fixture.as_uri()+f'?delay={delay}')
                page.wait_for_function('performance.now() >= 1200')
                if mode=='mouse':
                    page.get_by_role('button',name='Save').hover()
                    page.mouse.down()
                    page.wait_for_timeout(350)  # Deliberate observable held input, not synchronization.
                    page.mouse.up()
                else:
                    page.keyboard.down('s')
                    page.wait_for_timeout(350)
                    page.keyboard.up('s')
                page.wait_for_function("document.querySelector('#result').textContent === 'Status: Saved'")
                page.wait_for_timeout(1200)  # Retained result persistence window.
                telemetry=page.evaluate('({events:window.events,timeOrigin:performance.timeOrigin,elapsed:performance.now()})')
                video=page.video
                context.close()
                video.save_as(str(case/'source.webm'))
                retain(case/'telemetry-private.json',telemetry)
                retain(case/'receipt.json',{'source_sha256':digest(case/'source.webm'),'mode':mode,'delay_ms':delay,'events':len(telemetry['events'])})
        finally:
            browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    record(parser.parse_args().output)
