"""Offline MP4 export from a raw capture folder. No camera is opened."""
import argparse
import json
from pathlib import Path
import cv2
from raw_capture import read_capture
from video_recorder import Recorder
from xreal_windows import StreamParser, Pairer, Cleaner, decode, compose

def export(source, output=None, view='stereo', camera=0, clean=True):
    source=Path(source)
    metadata=json.loads((source/'capture.json').read_text(encoding='utf-8'))
    if metadata.get('version')!=1 or metadata.get('frame_bytes')!=640*482:
        raise ValueError('Unsupported raw capture format.')
    # Reuse validation on the captured preferences, not current live settings.
    settings=metadata.get('preferences',{})
    if (any(not isinstance(settings.get(k),list) or len(settings[k])!=2
            or any(type(v) is not bool for v in settings[k]) for k in ['rotations','mirrors'])
            or type(settings.get('swapped')) is not bool):
        raise ValueError('Invalid captured orientation settings.')
    parser=StreamParser(True,None if view=='stereo' else camera)
    pairer=Pairer()
    cleaners=[Cleaner(),Cleaner()]
    writer=None
    count=skipped=0
    try:
        for i,(frame,elapsed) in enumerate(read_capture(source)):
            try:raw,cam,counter=parser.parse(frame,i)
            except ValueError:
                skipped+=1
                continue
            image=decode(raw,cam)
            if clean:image=cleaners[cam].apply(image,equalize=False)
            combined=image if view=='mono' else pairer.add(counter,cam,image)
            if combined is None:continue
            rotations=settings['rotations'] if view=='stereo' else [settings['rotations'][camera],False]
            mirrors=settings['mirrors'] if view=='stereo' else [settings['mirrors'][camera],False]
            result=compose(combined,settings['swapped'],rotations,mirrors)
            if writer is None:writer=Recorder(output or source/'exported',result)
            writer.push(result,elapsed)
            count+=1
        if writer is None:raise ValueError('No usable frames/pairs in this capture.')
        path=writer.path
        print(f'EXPORTED: {path} | processed={count}, skipped={skipped}')
        return path,count
    finally:
        if writer:writer.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',nargs='?')
    p.add_argument('--output')
    p.add_argument('--view',choices=['mono','stereo'],default='stereo')
    p.add_argument('--camera',type=int,choices=[0,1],default=0)
    p.add_argument('--no-clean',action='store_true')
    a=p.parse_args()
    source=a.source or input('Paste raw_... folder path: ').strip().strip('"')
    export(source,a.output,a.view,a.camera,not a.no_clean)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,RuntimeError,cv2.error) as e:
        print(f'ERROR: {e}')
        raise SystemExit(1)
