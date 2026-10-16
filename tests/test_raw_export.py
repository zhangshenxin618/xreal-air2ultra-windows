import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from raw_capture import RawRecorder,read_capture
from export_recording import export

from fixtures import synthetic_capture
frames=synthetic_capture()
prefs=dict(rotations=[False,False],mirrors=[True,True],swapped=False)
with TemporaryDirectory() as temp:
    recorder=RawRecorder(temp,prefs)
    for i,frame in enumerate(frames):recorder.push(frame,100+i/60)
    folder=recorder.close()
    reread=list(read_capture(folder))
    assert len(reread)==len(frames)
    assert all(np.array_equal(f,source) for (f,t),source in zip(reread,frames))
    for view,expected_width in [('stereo',960),('mono',480)]:
        path,count=export(folder,folder/view,view)
        assert count==45
        cap=cv2.VideoCapture(str(path))
        decoded=0
        while True:
            ok,image=cap.read()
            if not ok:break
            assert image.shape==(640,expected_width,3)
            decoded+=1
        cap.release()
        assert decoded==45
    # Incomplete raw frames are rejected, never silently reshaped or truncated.
    with (folder/'frames.bin').open('ab') as stream:stream.write(b'X')
    try:
        list(read_capture(folder))
        raise AssertionError('Truncated capture accepted')
    except ValueError:pass
print('PASS: 90 synthetic frames preserved byte-for-byte; 45 stereo and 45 mono frames exported and decoded; incomplete capture rejected')

from unittest.mock import patch
import xreal_windows as x
class Camera:
    released=False
    def isOpened(self):return True
    def read(self):return True,frames[0]
    def release(self):self.released=True
with TemporaryDirectory() as temp:
    camera=Camera()
    with patch.object(sys,'argv',['viewer','--output',temp]), \
         patch.object(x,'NativeCamera',return_value=camera),patch.object(x,'read_key',side_effect=[ord('b'),-1,ord('b'),ord('q')]), \
         patch.object(x.cv2,'namedWindow'),patch.object(x.cv2,'imshow'), \
         patch.object(x.cv2,'getWindowProperty',return_value=1),patch.object(x.cv2,'destroyAllWindows'):
        x.main()
    paths=list(Path(temp).glob('raw_*'))
    assert len(paths)==1 and len(list(read_capture(paths[0])))==2
    assert camera.released
print('PASS: b starts/stops raw capture in preview; files close and read back')
