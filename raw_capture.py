"""Lossless bytes for frames delivered to the viewer, plus arrival times."""
import csv
import json
import time
from pathlib import Path
import numpy as np

FRAME_BYTES = 640*482

class RawRecorder:
    def __init__(self, folder, preferences):
        self.path = Path(folder)/f'raw_{time.time_ns()}'
        self.path.mkdir(parents=True)
        self.data = self.file = None
        try:
            self.data = (self.path/'frames.bin').open('wb')
            self.file = (self.path/'frames.csv').open('w',newline='',encoding='utf-8')
            self.csv = csv.writer(self.file)
            self.csv.writerow(['index','elapsed_seconds'])
            (self.path/'capture.json').write_text(json.dumps(dict(version=1,
                frame_bytes=FRAME_BYTES,preferences=preferences),indent=2),encoding='utf-8')
        except OSError:
            self.close()
            raise
        self.start = None
        self.frames = 0

    def push(self, frame, now=None):
        if frame.dtype!=np.uint8 or frame.size!=FRAME_BYTES:
            raise ValueError('Raw recording requires unconverted 640x482 bytes.')
        now = time.monotonic() if now is None else now
        if self.start is None:self.start=now
        self.data.write(np.ascontiguousarray(frame).tobytes())
        self.csv.writerow([self.frames,f'{now-self.start:.9f}'])
        self.frames+=1

    def close(self):
        if self.data:self.data.close()
        if self.file:self.file.close()
        return self.path

def read_capture(folder):
    folder=Path(folder)
    size=(folder/'frames.bin').stat().st_size
    if size%FRAME_BYTES:
        raise ValueError('Raw capture has an incomplete final frame; source was not modified.')
    with (folder/'frames.bin').open('rb') as data, (folder/'frames.csv').open(newline='',encoding='utf-8') as log:
        previous=-1.0
        rows=csv.DictReader(log)
        for index in range(size//FRAME_BYTES):
            row=next(rows,None)
            if row is None or int(row['index'])!=index:
                raise ValueError('Raw capture timestamp index is missing or inconsistent.')
            elapsed=float(row['elapsed_seconds'])
            if not np.isfinite(elapsed) or elapsed<0 or elapsed<previous:
                raise ValueError('Raw capture timestamps must be finite and monotonic.')
            previous=elapsed
            yield np.frombuffer(data.read(FRAME_BYTES),np.uint8).reshape(482,640),elapsed
        if next(rows,None) is not None:
            raise ValueError('Timestamp count exceeds frame count.')
