import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import check_stereo as c
from viewer_display import save_preferences,load_preferences

assert c.identify([100,100],[10,100],[100,10])[0]==0
assert c.identify([100,100],[100,10],[10,100])[0]==1
for baseline,left,right in [([1,100],[0,100],[1,10]),
                            ([100,100],[10,10],[10,10]),
                            ([100,100],[90,100],[100,90]),
                            ([100,100],[10,100],[10,100])]:
    try:
        c.identify(baseline,left,right)
        raise AssertionError('Ambiguous measurements accepted')
    except ValueError:pass
with TemporaryDirectory() as folder:
    root=Path(folder)
    settings=root/'view-settings.json'
    save_preferences(settings,[True,False],[False,True],False)
    with patch.object(c,'ROOT',root),patch('builtins.input',return_value=''), \
         patch.object(c,'measure',side_effect=[[100,100],[100,10],[10,100]]):
        c.calibrate()
    assert load_preferences(settings)==dict(rotations=[True,False],mirrors=[False,True],swapped=True)
    assert json.loads((root/'camera-mapping.json').read_text())['left_group']==1
    previous=settings.read_bytes()
    with patch.object(c,'ROOT',root),patch('builtins.input',return_value=''), \
         patch.object(c,'measure',side_effect=[[100,100],[10,10],[10,10]]):
        try:c.calibrate()
        except ValueError:pass
    assert settings.read_bytes()==previous
pattern=c.test_pattern(3840,1080)
assert pattern.shape==(1080,3840,3) and pattern[:,:1920].max()>0 and pattern[:,1920:].max()>0
with patch.object(c,'monitors',return_value=[dict(name='2D',width=1920,height=1080)]), \
     patch('builtins.input',return_value='0'),patch.object(c.cv2,'namedWindow') as window:
    try:c.eye_test()
    except ValueError:pass
    window.assert_not_called()
print('PASS: left/right identification, ambiguity rejection, preference preservation, SBS pattern and 2D guard')
