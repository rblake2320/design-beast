"""Freeze captured positive/negative clips and source-linked review frames."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import digest,retain


def prepare(root: Path) -> None:
    negative=root/'case-04'
    negative.mkdir(exist_ok=False)
    subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-ss','2.0','-i',str(root/'case-03/source.webm'),
        '-an','-c:v','libx264','-threads','2',str(negative/'source.mp4')],check=True,capture_output=True,timeout=30)
    retain(negative/'trim-private.json',{'parent_sha256':digest(root/'case-03/source.webm'),'removed_seconds':2.0,
        'purpose':'input outside retained footage; visible delayed result remains'})
    for index in range(1,5):
        case=root/f'case-{index:02d}'
        source=case/('source.mp4' if index==4 else 'source.webm')
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=avg_frame_rate,width,height',
            '-of','json',str(source)],check=True,capture_output=True).stdout)
        duration=float(probe['format']['duration'])
        review=case/'review'
        (review/'media').mkdir(parents=True)
        import shutil
        shutil.copyfile(source,review/'media/source.mp4')
        frames=[]
        for n in range(int((duration-.08)/.25)+1):
            stamp=n*.25
            image=review/f'media/frame-{n:03d}.jpg'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-ss',str(stamp),'-i',str(source),
                '-frames:v','1','-q:v','3',str(image)],check=True,capture_output=True,timeout=30)
            frames.append({'clip_ms':round(stamp*1000),'sha256':digest(image),'image':f'media/{image.name}'})
        retain(review/'review-data.json',{'source_sha256':digest(source),'end_ms':int((duration-.04)*1000),
            'source_offset_ms':2000 if index==4 else 0,'frames':frames})
        retain(review/'report.json',{'review_data_sha256':digest(review/'review-data.json'),'probe':probe,
            'boundary':'actual browser recording; sparse frame review, not pixel-state analysis'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    prepare(parser.parse_args().root)
