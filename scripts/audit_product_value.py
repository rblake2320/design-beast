"""Read-only product commands against an existing checkout; writes isolated receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--ffmpeg-bin', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment['PATH'] = str(args.ffmpeg_bin) + os.pathsep + environment['PATH']
    write(output/'intent.json', {'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'research_head': subprocess.check_output(['git','-C',str(args.research),'rev-parse','HEAD'], text=True).strip(),
        'main_head': subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip(),
        'goal': 'source -> review -> operator caption -> export -> playback; no product changes',
        'real_users_recruited': 0, 'publication_allowed': False})

    def command(name: str, argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
        if argv[0] == 'ffmpeg':
            argv[0] = str(args.ffmpeg_bin/'ffmpeg.exe')
        started = time.perf_counter()
        write(output/f'{name}-intent.json', {'argv': argv, 'cwd': str(cwd)})
        try:
            result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, timeout=240)
            write(output/f'{name}.json', {'seconds': time.perf_counter()-started,
                'returncode': result.returncode, 'stdout': result.stdout.decode('utf-8', errors='replace'),
                'stderr': result.stderr.decode('utf-8', errors='replace')})
            return result
        except Exception as exc:
            write(output/f'{name}-failure.json', {'seconds': time.perf_counter()-started,
                'error': str(exc), 'type': type(exc).__name__})
            raise

    command('main-entrypoint', ['powershell','-NoProfile','-File',str(root/'bin/beast.ps1'),
        'watch-training','prepare','--source',str(args.source),'--output',str(output/'main-output')], root)
    command('prepare', [sys.executable,'scripts/watch_training.py','prepare','--source',str(args.source),
        '--output',str(output/'prepared')], args.research)
    review = output/'prepared/review'
    if not (review/'index.html').exists():
        raise RuntimeError('Real source prepare did not create review; inspect receipt')
    from playwright.sync_api import sync_playwright
    data = json.loads((review/'review-data.json').read_bytes())
    errors = []
    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel='chrome')
        page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto((review/'index.html').as_uri(), wait_until='networkidle')
        page.wait_for_function("document.querySelector('video').readyState >= 1")
        page.locator('video').evaluate('v=>v.play()')
        page.wait_for_function("document.querySelector('video').currentTime > .25")
        page.locator('video').evaluate('v=>v.pause()')
        page.locator('#scrub').fill('20')
        page.locator('#scrub').dispatch_event('input')
        target = data['frames'][20]['clip_ms']/1000
        page.wait_for_function("t=>Math.abs(document.querySelector('video').currentTime-t)<.15", arg=target)
        page.locator('#start').fill('9')
        page.locator('#end').fill('11')
        caption = 'The model and annotation become smaller on screen.'
        page.locator('#caption').fill(caption)
        page.get_by_role('button', name='Add draft segment', exact=True).click()
        with page.expect_download() as download:
            page.get_by_role('button', name='Download source-linked plan').click()
        download.value.save_as(output/'operator-plan.json')
        page.screenshot(path=str(output/'review.png'), full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
        write(output/'browser.json', {'automated_operator_seconds':time.perf_counter()-started,
            'human_time':None, 'caption_author':'audit operator, based on prior independent V4 reference',
            'caption':caption, 'seek_seconds':target, 'frames':len(data['frames']),
            'browser_errors':errors, 'mobile_overflow':overflow, 'downloaded_plan':True})
        command('render', [sys.executable,'scripts/watch_training.py','render','--review',str(review),
            '--plan',str(output/'operator-plan.json'),'--output',str(output/'rendered')],args.research)
        movie = output/'rendered/training-draft.mp4'
        if not movie.is_file():
            raise RuntimeError('Render did not produce actual video')
        page.locator('video').evaluate('(v,url)=>{v.src=url;v.load()}', movie.as_uri())
        page.wait_for_function("document.querySelector('video').readyState >= 1")
        page.locator('video').evaluate('v=>v.play()')
        page.wait_for_function("document.querySelector('video').currentTime > .4")
        media = page.locator('video').evaluate('v=>({time:v.currentTime,duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error})')
        page.locator('video').evaluate('v=>v.pause()')
        page.screenshot(path=str(output/'playback.png'))
        write(output/'playback.json', media)
        browser.close()
    command('decode-output', ['ffmpeg','-v','error','-i',str(movie),'-f','null','-'], args.research)
    command('direct-trim-baseline', ['ffmpeg','-v','error','-nostdin','-n','-ss','9','-i',str(args.source),
        '-t','2','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18',str(output/'direct-trim.mp4')],args.research)
    command('automatic', [sys.executable,'scripts/watch_training.py','auto','--review',str(review),
        '--count','1','--output',str(output/'automatic')],args.research)
    write(output/'complete.json', {'audit_steps_completed':True,'tutorial_automatically_generated':False,
        'paid_provider_calls':0,'human_value_trial':False,'source_minutes':data['end_ms']/60000})


if __name__ == '__main__':
    main()
