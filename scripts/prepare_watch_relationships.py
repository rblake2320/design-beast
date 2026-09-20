"""Retain native frames and PTS for independent labels, never scheduler input."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest, retain


def prepare(root: Path) -> None:
    for case in sorted(root.glob('case-*')):
        source = case/'source.webm'
        review = case/'visual-review'
        review.mkdir(exist_ok=False)
        probe = json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','format=duration:stream=avg_frame_rate,width,height:frame=best_effort_timestamp_time',
            '-of','json',str(source)],capture_output=True,check=True,timeout=30).stdout)
        subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-i',str(source),
            '-fps_mode','passthrough','-q:v','2',str(review/'f-%04d.jpg')],capture_output=True,check=True,timeout=30)
        images = sorted(review.glob('f-*.jpg'))
        stamps = probe['frames']
        if len(images) != len(stamps):
            raise ValueError('native frame count mismatch')
        retain(review/'manifest.json', {'source_sha256':digest(source), 'probe':probe,
            'frames':[{'image':p.name, 'ms':round(float(t['best_effort_timestamp_time'])*1000),
                       'sha256':digest(p)} for p,t in zip(images,stamps)]})


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    prepare(p.parse_args().root)
