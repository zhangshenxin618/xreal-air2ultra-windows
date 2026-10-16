import sys
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import xreal_windows as x

good = np.full((482, 640), 50, np.uint8)
good[481] = 0x5C
good[480, 26:28] = [25, 1]
good[480, 51:57] = [128, 2, 224, 1, 128, 2]
good[480, 59] = 0
good[480, 18:22] = 0
bad = good.copy()
bad[480, 51] = 0
parser = x.StreamParser(native=True)
assert parser.parse(good, 0)[1] == 0
try:
    parser.parse(bad, 1)
    raise AssertionError('Invalid dimensions accepted')
except ValueError:
    pass
good2 = good.copy()
good2[480, 18] = 2
assert parser.parse(good2, 2)[2] == 2
assert parser.mono

class Camera:
    def __init__(self):
        self.frames = iter([good, bad, good])
        self.released = False
    def isOpened(self): return True
    def read(self): return True, next(self.frames)
    def release(self): self.released = True

cam = Camera()
with patch.object(sys, 'argv', ['viewer']), patch.object(x, 'NativeCamera', return_value=cam), \
     patch.object(x.cv2, 'namedWindow'), patch.object(x.cv2, 'imshow') as show, \
     patch.object(x.cv2, 'waitKey', side_effect=[-1, -1, ord('q')]), \
     patch.object(x.cv2, 'getWindowProperty', return_value=1), \
     patch.object(x.cv2, 'destroyAllWindows'):
    x.main()
    assert show.call_count == 2
assert cam.released
print('PASS: malformed middle frame skipped; subsequent frame reaches display; camera released')

p = x.Pairer()
im0 = np.full((640,480), 10, np.uint8)
im1 = np.full((640,480), 20, np.uint8)
assert p.add(10, 1, im1) is None
assert p.add(11, 0, im0) is None
pair = p.add(10, 0, im0)
assert np.all(pair[:,:480] == 10) and np.all(pair[:,480:] == 20)
assert p.add(12, 1, im1) is None
assert p.add(11, 1, im1).shape == (640,960)
for k in range(100, 120): p.add(k, 0, im0)
assert len(p.pending) <= 8
im0 = np.arange(640*480, dtype=np.uint32).astype(np.uint8).reshape(640,480)
pair = np.hstack((im0, im1))
rotated = x.compose(pair, rotations=(True,False))
assert np.array_equal(rotated[:,:480], im0[::-1,::-1])
assert np.array_equal(rotated[:,480:], im1)
swapped = x.compose(pair, swapped=True)
assert np.array_equal(swapped[:,:480],im1)
assert np.array_equal(swapped[:,480:],im0)
print('PASS: reversed arrival, missing frames, bounded pending pairs, independent rotation and eye swap')

from viewer_display import letterbox_stereo, load_preferences, save_preferences
from tempfile import TemporaryDirectory
mirrored = x.compose(pair, mirrors=(True,True))
assert np.array_equal(mirrored[:,:480],im0[:,::-1])
assert np.array_equal(mirrored[:,480:],im1[:,::-1])
canvas = letterbox_stereo(np.hstack((np.full_like(im0,10), im1)),3840,1080)
assert canvas.shape == (1080,3840)
assert np.all(canvas[:, :555] == 0)
assert np.all(canvas[:,555:1365] == 10)
assert np.all(canvas[:,2475:3285] == 20)
with TemporaryDirectory() as folder:
    path = Path(folder)/'prefs.json'
    assert load_preferences(path)['mirrors'] == [True,True]
    save_preferences(path,[True,False],[False,True],True)
    assert load_preferences(path) == dict(rotations=[True,False],mirrors=[False,True],swapped=True)
    path.write_text('{broken',encoding='utf-8')
    assert load_preferences(path)['swapped'] is False
print('PASS: per-eye mirror, 3840x1080 aspect-preserving SBS, preferences roundtrip and corrupt-file recovery')

import msvcrt
with patch.object(x.cv2,'waitKey',return_value=-1), \
     patch.object(msvcrt,'kbhit',return_value=True), \
     patch.object(msvcrt,'getwch',return_value='V'):
    assert x.read_key()==ord('v')
with patch.object(x.cv2,'waitKey',return_value=ord('M')), \
     patch.object(msvcrt,'getwch') as console:
    assert x.read_key()==ord('m')
    console.assert_not_called()
print('PASS: terminal keyboard fallback and uppercase preview hotkeys')
