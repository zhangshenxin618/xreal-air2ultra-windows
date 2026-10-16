"""Windows display discovery, per-eye letterboxing and local preferences."""
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import cv2
import numpy as np

def monitors():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        user32.SetProcessDPIAware()
    class Info(ctypes.Structure):
        _fields_ = [('cbSize', w.DWORD), ('rect', w.RECT), ('work', w.RECT),
                    ('flags', w.DWORD), ('name', w.WCHAR * 32)]
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HDC,
                                      ctypes.POINTER(w.RECT), w.LPARAM)
    user32.GetMonitorInfoW.argtypes = [w.HANDLE, ctypes.POINTER(Info)]
    user32.GetMonitorInfoW.restype = w.BOOL
    user32.EnumDisplayMonitors.argtypes = [w.HDC, ctypes.POINTER(w.RECT), callback_type, w.LPARAM]
    user32.EnumDisplayMonitors.restype = w.BOOL
    found = []
    @callback_type
    def visit(handle, dc, rect, data):
        info = Info()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rect
            found.append(dict(name=info.name, x=r.left, y=r.top,
                              width=r.right-r.left, height=r.bottom-r.top,
                              primary=bool(info.flags & 1)))
        return True
    if not user32.EnumDisplayMonitors(None, None, visit, 0):
        raise RuntimeError('Windows display enumeration failed.')
    return sorted(found, key=lambda m: m['name'])

def letterbox_stereo(image, width, height):
    if image.shape[1] != 960 or width < 2 or height < 1:
        raise ValueError('Stereo output needs two eyes and valid display dimensions.')
    canvas = np.zeros((height, width), np.uint8)
    for i in range(2):
        left, right = i*width//2, (i+1)*width//2
        eye = image[:, i*480:(i+1)*480]
        scale = min((right-left)/eye.shape[1], height/eye.shape[0])
        ew, eh = max(1, int(eye.shape[1]*scale)), max(1, int(eye.shape[0]*scale))
        resized = cv2.resize(eye, (ew, eh), interpolation=cv2.INTER_LINEAR)
        x, y = left+(right-left-ew)//2, (height-eh)//2
        canvas[y:y+eh, x:x+ew] = resized
    return canvas

def letterbox_mono(image, width, height):
    if image.ndim != 2 or width < 1 or height < 1:
        raise ValueError('Invalid mono output dimensions.')
    scale = min(width/image.shape[1], height/image.shape[0])
    ew, eh = max(1, int(image.shape[1]*scale)), max(1, int(image.shape[0]*scale))
    canvas = np.zeros((height, width), np.uint8)
    x, y = (width-ew)//2, (height-eh)//2
    canvas[y:y+eh, x:x+ew] = cv2.resize(image, (ew, eh), interpolation=cv2.INTER_LINEAR)
    return canvas

def load_preferences(path):
    default = dict(rotations=[False, False], mirrors=[True, True], swapped=False)
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        for key in ('rotations', 'mirrors'):
            if (not isinstance(data.get(key), list) or len(data[key]) != 2
                    or any(type(v) is not bool for v in data[key])):
                raise ValueError(key)
        if type(data.get('swapped')) is not bool:
            raise ValueError('swapped')
        return {key: data[key] for key in default}
    except (ValueError, OSError):
        print('Invalid preferences; using defaults until next adjustment.')
        return default

def save_preferences(path, rotations, mirrors, swapped):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(rotations=rotations, mirrors=mirrors,
                                         swapped=swapped), indent=2), encoding='utf-8')
    temporary.replace(path)
