"""Continue media checks without repeating successful intake or rendering."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops, ImageStat
import io


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--ffmpeg-bin', type=Path, required=True)
    parser.add_argument('--skip-playback', action='store_true')
    parser.add_argument('--suffix', default='')
    args = parser.parse_args()
    root = args.run.resolve()
    output = root/('media-continuation'+args.suffix)
    output.mkdir(exist_ok=False)
    env = os.environ.copy()
    env['PATH'] = str(args.ffmpeg_bin)+os.pathsep+env['PATH']
    def save(name, value):
        with (output/f'{name}.json').open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    def command(name, argv):
        if argv[0] == 'ffmpeg':
            argv[0] = str(args.ffmpeg_bin/'ffmpeg.exe')
        start = time.perf_counter()
        result = subprocess.run(argv, cwd=args.research, env=env, capture_output=True, timeout=180)
        save(name, {'argv':argv, 'seconds':time.perf_counter()-start,'returncode':result.returncode,
                    'stdout':result.stdout.decode('utf-8',errors='replace'),
                    'stderr':result.stderr.decode('utf-8',errors='replace')})
        return result
    movie = root/'rendered/training-draft.mp4'
    source = root/'prepared/review/media/source.mp4'
    save('intent', {'output_sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),
        'previous_failure':'Direct MP4 page.goto networkidle timeout; media status unclassified',
        'no_repeated_intake_or_render':True})
    if not args.skip_playback:
      with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='chrome')
        page = browser.new_page(viewport={'width':1440,'height':1050})
        page.goto((root/'prepared/review/index.html').as_uri(), wait_until='networkidle')
        page.locator('video').evaluate('(v,url)=>{v.src=url;v.load()}', movie.as_uri())
        page.wait_for_function("document.querySelector('video').readyState>=2")
        page.locator('video').evaluate('v=>v.play()')
        page.wait_for_function("document.querySelector('video').currentTime > .4")
        page.locator('video').evaluate('v=>v.pause()')
        save('playback', page.locator('video').evaluate('v=>({time:v.currentTime,duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error})'))
        page.locator('video').screenshot(path=str(output/'playback.png'))
        browser.close()
    command('decode', ['ffmpeg','-v','error','-i',str(movie),'-f','null','-'])
    frames = []
    for path, stamp in [(source,'9.5'),(movie,'0.5')]:
        raw = subprocess.run([str(args.ffmpeg_bin/'ffmpeg.exe'),'-v','error','-ss',stamp,'-i',str(path),'-frames:v','1',
            '-f','image2pipe','-vcodec','png','-'], env=env, capture_output=True,check=True,timeout=30).stdout
        frames.append(Image.open(io.BytesIO(raw)).convert('RGB'))
    difference = ImageStat.Stat(ImageChops.difference(frames[0], frames[1].crop((0,0,*frames[0].size))))
    save('source-fidelity', {'sample_source_seconds':9.5,'sample_output_seconds':.5,
        'mean_absolute_error_rgb':difference.mean,'samples':1,'caption_band_excluded':True})
    command('direct-trim', ['ffmpeg','-v','error','-nostdin','-n','-ss','9','-i',str(source),
        '-t','2','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18',str(output/'direct-trim.mp4')])
    command('resource-admission', [sys.executable,'scripts/beast_core.py','resource-check','judge'])
    command('automatic', [sys.executable,'scripts/watch_training.py','auto','--review',str(root/'prepared/review'),
        '--count','1','--output',str(output/'automatic')])
    save('complete', {'media_checks_executed':True,'paid_calls':0,'customer_savings_measured':False})


if __name__ == '__main__':
    main()
