import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np
import cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import xreal_windows as x
from viewer_display import letterbox_mono
from video_recorder import Recorder

image=np.full((640,480),100,np.uint8)
out=letterbox_mono(image,1920,1080)
assert out.shape==(1080,1920)
assert np.all(out[:,:555]==0) and np.all(out[:,555:1365]==100)
with TemporaryDirectory() as folder:
    rec=Recorder(folder,image)
    for i in range(30):
        rec.push(np.full_like(image,30+i*4),100+i/30)
    path=rec.close()
    cap=cv2.VideoCapture(str(path))
    frames=[]
    while True:
        ok,frame=cap.read()
        if not ok:break
        frames.append(frame)
    cap.release()
    assert len(frames)==30 and frames[0].shape==(640,480,3)
    assert frames[-1].mean()>frames[0].mean()+80
    assert len(path.with_suffix('.csv').read_text().splitlines())==31
    # Missing input frames retain elapsed playback duration.
    rec=Recorder(folder,image)
    rec.push(image,100)
    rec.push(image,100.1)
    assert rec.frames==4
    rec.close()
print('PASS: normal 1920x1080 letterbox, MP4 encode/decode, timestamp CSV, dropped-frame duration')

frame=np.full((482,640),50,np.uint8)
frame[480,51:57]=[128,2,224,1,128,2]
frame[480,59]=0
class Camera:
    released=False
    def isOpened(self):return True
    def read(self):return True,frame
    def release(self):self.released=True
camera=Camera()
with patch.object(sys,'argv',['viewer','--passthrough-2d','--display','0']), \
     patch.object(x,'monitors',return_value=[dict(name='test',x=2560,y=0,width=1920,height=1080,primary=False)]), \
     patch.object(x,'NativeCamera',return_value=camera), \
     patch.object(x.cv2,'namedWindow'),patch.object(x.cv2,'moveWindow') as move, \
     patch.object(x.cv2,'resizeWindow'),patch.object(x.cv2,'setWindowProperty'), \
     patch.object(x.cv2,'imshow') as show,patch.object(x.cv2,'waitKey',return_value=ord('q')), \
     patch.object(x.cv2,'destroyAllWindows'):
    x.main()
    assert show.call_args.args[1].shape==(1080,1920)
    assert move.call_args.args[1:]==(2570,10)
assert camera.released
print('PASS: 2D display selected, fullscreen rendering path, correct monitor position, clean exit')
