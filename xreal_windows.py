"""Experimental Windows UVC viewer. Algorithm: sean9061/xreal-air2ultra-camera,
reorder table originally mazeasdamien/myXreal. See LICENSE-upstream.txt.
"""
import argparse
from collections import OrderedDict
from pathlib import Path
import time
import subprocess
import sys
import itertools
import queue
import threading
import numpy as np
import cv2
from viewer_display import monitors, letterbox_stereo, letterbox_mono, load_preferences, save_preferences
from video_recorder import Recorder
from raw_capture import RawRecorder

def read_key():
    key = cv2.waitKey(1) & 255
    # Accept console input too: the preview may be on the glasses while the
    # user naturally keeps the terminal focused on the laptop.
    if key == 255 and sys.platform == 'win32':
        import msvcrt
        if msvcrt.kbhit():
            character = msvcrt.getwch()
            if character in ('\x00', '\xe0'):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                return 255
            key = ord(character)
    return key + 32 if ord('A') <= key <= ord('Z') else key

REORDER = np.array([
119,54,21,0,108,22,51,63,93,99,67,7,32,112,52,43,
14,35,75,116,64,71,44,89,18,88,26,61,70,56,90,79,
87,120,81,101,121,17,72,31,53,124,127,113,111,36,48,
19,37,83,126,74,109,5,84,41,76,30,110,29,12,115,28,
102,105,62,103,20,3,68,49,77,117,125,106,60,69,98,9,
16,78,47,40,2,118,34,13,50,46,80,85,66,42,123,122,
96,11,25,97,39,6,86,1,8,82,92,59,104,24,15,73,65,
38,58,10,23,33,55,57,107,100,94,27,95,45,91,4,114])

def parse_frame(frame):
    if frame.dtype != np.uint8 or frame.size != 640 * 482:
        raise ValueError(f"Raw bytes unavailable: shape={frame.shape}, dtype={frame.dtype}. "
                         "Automatic color conversion or unsupported capture format.")
    raw = np.ascontiguousarray(frame).reshape(482, 640)
    meta = raw[480]
    if (int(meta[22]), int(meta[23])) != (0xAD, 0xDA) or int(meta[58]) not in (0x20, 0x21):
        raise ValueError("XREAL telemetry markers missing; refusing to decode converted data.")
    camera = int(meta[58]) & 1
    counter = (int(meta[6]) << 8) | int(meta[19])
    return raw[:480].copy(), camera, counter

def decode(raw, camera):
    blocks = raw.reshape(128, 2400)
    darkest = int(np.argmin(blocks[:, :128].sum(axis=1)))
    align = int(np.flatnonzero(REORDER == darkest)[0])
    image = blocks[REORDER[(align + np.arange(128)) % 128]].reshape(480, 640).T
    return np.ascontiguousarray(image if camera == 0 else image[::-1, ::-1])

class Cleaner:
    def __init__(self):
        self.stripe = None

    def apply(self, image, equalize=True):
        image = image.astype(np.float32)
        hp = image - cv2.blur(image, (31, 1))
        stripe = np.median(hp, axis=0)
        self.stripe = stripe if self.stripe is None else .95*self.stripe + .05*stripe
        image -= self.stripe[None, :]
        hp = image - cv2.blur(image, (1, 31))
        image -= np.median(hp, axis=1)[:, None]
        image = np.clip(image, 0, 255).astype(np.uint8)
        return cv2.equalizeHist(image) if equalize else image

class StreamParser:
    def __init__(self, native=False, mono_camera=0):
        self.native = native
        self.mono = False
        self.mono_camera = mono_camera

    def parse(self, frame, sequence):
        if not self.mono:
            try:
                return parse_frame(frame)
            except ValueError:
                if not self.native:
                    raise
        if frame.dtype != np.uint8 or frame.shape != (482, 640):
            raise ValueError('Skipping native frame with invalid size.')
        if frame[:480].mean() < 5:
            raise ValueError('Skipping startup/dark frame.')
        meta = frame[480]
        # Configuration bytes 26:28 vary between sessions, so never gate on them.
        # This unit reports dimensions 640,480,640 as little-endian values here.
        # Byte 59 separates empirically consistent image groups; physical L/R
        # identity remains unverified.
        if tuple(meta[51:57]) != (0x80, 2, 0xE0, 1, 0x80, 2) or int(meta[59]) not in (0, 1):
            raise ValueError('Unrecognized native image group; skipping instead of mixing cameras.')
        self.mono = True
        camera = int(meta[59])
        if self.mono_camera is not None and camera != self.mono_camera:
            raise ValueError('Skipping other camera group for stable mono preview.')
        # In two independent captures, bytes 18:22 are shared by both groups
        # and increment once per pair. Do not pair by arrival order.
        counter = int.from_bytes(meta[18:22].tobytes(), 'little')
        return frame[:480].copy(), camera, counter

class Pairer:
    def __init__(self):
        self.pending = OrderedDict()

    def add(self, counter, camera, image):
        pair = self.pending.setdefault(counter, {})
        pair[camera] = image
        while len(self.pending) > 8:
            self.pending.popitem(last=False)
        if len(pair) == 2:
            self.pending.pop(counter, None)
            return np.hstack((pair[0], pair[1]))
        return None

def compose(image, swapped=False, rotations=(False, False), mirrors=(False, False)):
    eyes = [image[:, :480], image[:, 480:]] if image.shape[1] == 960 else [image]
    eyes = [cv2.rotate(eye, cv2.ROTATE_180) if rotations[i] else eye
            for i, eye in enumerate(eyes)]
    eyes = [cv2.flip(eye, 1) if mirrors[i] else eye for i, eye in enumerate(eyes)]
    if swapped and len(eyes) == 2:
        eyes.reverse()
    return np.hstack(eyes)

def open_camera(index, backend, height, fourcc):
    api = cv2.CAP_DSHOW if backend == 'dshow' else cv2.CAP_MSMF
    cap = cv2.VideoCapture(index, api)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, 60)
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    return cap

class NativeCamera:
    """Copy DirectShow raw packets without pixel conversion; target glasses only."""
    def __init__(self):
        import imageio_ffmpeg
        self.log = open(Path(__file__).with_name(f'native-capture-{time.time_ns()}.log'), 'w', encoding='utf-8')
        self.proc = subprocess.Popen([
            imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-nostats',
            '-f', 'dshow', '-video_size', '640x241', '-pixel_format', 'yuyv422',
            '-i', 'video=UVC Camera 0', '-map', '0:v:0', '-c:v', 'copy',
            '-f', 'rawvideo', 'pipe:1'], stdout=subprocess.PIPE, stderr=self.log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.frames = queue.Queue(maxsize=4)
        self.stopped = threading.Event()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while not self.stopped.is_set():
            data = bytearray()
            while len(data) < 640*482:
                part = self.proc.stdout.read(640*482-len(data))
                if not part:
                    return
                data.extend(part)
            frame = np.frombuffer(data, np.uint8).reshape(482, 640)
            try:
                self.frames.put_nowait(frame)
            except queue.Full:
                pass

    def isOpened(self):
        return self.proc.poll() is None

    def read(self):
        try:
            return True, self.frames.get(timeout=10)
        except queue.Empty:
            return False, None

    def release(self):
        self.stopped.set()
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        self.log.close()

def auto_detect():
    """Probe each candidate in a separate process so a blocked driver times out."""
    script = str(Path(__file__).resolve())
    report = []
    # Prefer device discovery over silently assuming camera 0 is the glasses.
    for backend, height, fourcc in [('dshow', 241, 'UYVY'),
                                    ('dshow', 482, 'Y800'),
                                    ('msmf', 241, 'UYVY')]:
        for device in range(6):
            args = ['--device', str(device), '--backend', backend,
                    '--height', str(height), '--fourcc', fourcc]
            print(f'Checking device {device}: {backend} {fourcc} 640x{height}', flush=True)
            try:
                result = subprocess.run([sys.executable, script, *args, '--probe'],
                                        capture_output=True, text=True, errors='replace', timeout=12)
                report.append(' '.join(args) + '\n' + result.stdout + result.stderr)
                if result.returncode == 0 and 'VERIFIED_STEREO' in result.stdout:
                    Path('diagnostics.txt').write_text('\n'.join(report), encoding='utf-8')
                    return args
            except subprocess.TimeoutExpired:
                report.append(' '.join(args) + '\nDriver read timed out after 12 seconds.\n')
    Path('diagnostics.txt').write_text('\n'.join(report), encoding='utf-8')
    raise RuntimeError('No validated XREAL stereo stream found on camera indices 0-5. '
                       'Send diagnostics.txt for further analysis. Check USB data connection and camera permissions.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', type=int, default=None)
    p.add_argument('--backend', choices=['native', 'dshow', 'msmf'], default='native')
    p.add_argument('--height', type=int, choices=[241, 482], default=241)
    p.add_argument('--fourcc', choices=['UYVY', 'YUY2', 'Y800'], default='UYVY')
    p.add_argument('--probe', action='store_true', help='Read up to 30 frames, report format, then exit')
    p.add_argument('--output', default='captures')
    p.add_argument('--view', choices=['mono', 'stereo'], default='mono')
    p.add_argument('--list-displays', action='store_true')
    p.add_argument('--display', type=int, help='Display index from --list-displays')
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--passthrough', action='store_true', help='Fullscreen SBS on a selected 3D display')
    modes.add_argument('--passthrough-2d', action='store_true', help='Fullscreen single camera on a normal display')
    p.add_argument('--record', action='store_true', help='Start MP4 recording immediately')
    p.add_argument('--list-audio', action='store_true',help='List microphone inputs without opening a camera')
    p.add_argument('--audio-device',default='auto',help='Microphone index, or auto (prefers XREAL)')
    p.add_argument('--no-audio',action='store_true',help='Record silent videos')
    p.add_argument('--record-raw', action='store_true', help='Record delivered native bytes and timestamps')
    p.add_argument('--mono-camera', type=int, choices=[0, 1], default=0,
                   help='Select one empirical camera group in native mono mode')
    p.add_argument('--check-frames', type=int, default=0,
                   help='Process N valid frames without opening a window, then exit')
    a = p.parse_args()
    if a.list_audio:
        from audio_capture import input_devices
        for device in input_devices():
            print(f"{device['index']}: {device['name']} [{device['api']}]")
        return
    target = None
    if a.list_displays or a.passthrough or a.passthrough_2d or a.display is not None:
        displays = monitors()
        for i, monitor in enumerate(displays):
            print(f"{i}: {monitor['name']} {monitor['width']}x{monitor['height']}"
                  + (' primary' if monitor['primary'] else ''))
        if a.list_displays:
            return
        if a.display is None:
            try:
                a.display = int(input('Select glasses display index (q to cancel): '))
            except ValueError:
                return
        if not 0 <= a.display < len(displays):
            raise ValueError('Display index out of range.')
        target = displays[a.display]
        if a.passthrough_2d:
            a.view = 'mono'
            if target['width']/target['height'] >= 3:
                raise ValueError('2D mode needs a normal display; selected screen appears to use full SBS.')
        if a.passthrough:
            if target['width']/target['height'] < 3:
                raise ValueError('Selected display is not full-width SBS. Enable glasses 3D/SBS mode, '
                                 'use Windows extended desktop, then restart. No display mode was changed.')
            a.view = 'stereo'
    if a.device is None and a.backend != 'native':
        args = auto_detect()
        return subprocess.call([sys.executable, str(Path(__file__).resolve()), *args,
                                '--output', a.output] + (['--probe'] if a.probe else []))
    cap = NativeCamera() if a.backend == 'native' else open_camera(a.device, a.backend, a.height, a.fourcc)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError('Cannot open camera. Check device index, USB connection and Windows camera permissions.')
    cleaners, pairer = [Cleaner(), Cleaner()], Pairer()
    settings_path = Path(__file__).with_name('view-settings.json')
    settings = load_preferences(settings_path)
    clean, swapped, fullscreen = True, settings['swapped'], a.passthrough or a.passthrough_2d
    rotations, mirrors = settings['rotations'], settings['mirrors']
    window = 'XREAL Windows - q:quit m:mirror r:rotate x:swap s:snapshot v:record f:fullscreen'
    window_created = False
    last, error, valid = None, 'No frames received', 0
    probe_pairer = Pairer()
    started = time.monotonic()
    unknown = False
    parser = StreamParser(a.backend == 'native', None if a.view == 'stereo' else a.mono_camera)
    last_valid = time.monotonic()
    skipped = 0
    rendered = 0
    last_pair = time.monotonic()
    recorder = None
    start_recording = a.record
    raw_recorder = None
    start_raw = a.record_raw
    pending_key = 255
    feedback = 'v:video b:raw s:save m:mirror r:rotate q:quit'
    feedback_until = time.monotonic() + 8
    if not a.probe and not a.check_frames:
        print('Click the preview OR the terminal, then press a key (no Enter needed). '+feedback, flush=True)
    try:
        for attempt in range(30) if a.probe else itertools.count():
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('Camera read failed; try another format or backend.')
            if start_raw:
                if a.backend!='native':
                    raise ValueError('Raw recording requires the native backend.')
                raw_recorder=RawRecorder(a.output,dict(rotations=rotations,mirrors=mirrors,swapped=swapped))
                print(f'Raw recording: {raw_recorder.path}',flush=True)
                start_raw=False
            if raw_recorder:
                raw_recorder.push(frame)
            try:
                raw, camera, counter = parser.parse(frame, attempt)
            except ValueError as e:
                error = str(e)
                skipped += 1
                if a.probe:
                    continue
                if time.monotonic() - last_valid > 10:
                    raise RuntimeError(f'No usable frame for 10 seconds ({skipped} skipped): {error}') from e
                # A single malformed/startup frame must not terminate a live preview.
                if not a.check_frames:
                    key = read_key()
                    if key in (ord('q'), 27):
                        break
                    if key != 255:
                        pending_key = key
                continue
            last_valid = time.monotonic()
            if parser.mono and not unknown:
                print(f'{a.view} preview: native camera groups; physical left/right unverified.', flush=True)
                unknown = True
                pairer = Pairer()
                last = None
            valid += 1
            if a.probe:
                if unknown and a.view == 'mono':
                    print('RAW_ONLY: native bytes received; stereo identity not verified.')
                    return
                print(f'Valid raw frame: camera={camera}, counter={counter}, shape={frame.shape}')
                pair = probe_pairer.add(counter, camera, raw)
                if valid >= 4 and pair is not None:
                    print('VERIFIED_STEREO')
                    return
                continue
            image = decode(raw, camera)
            image = cleaners[camera].apply(image, equalize=not unknown) if clean else image
            mono = a.view == 'mono'
            combined = image if mono else pairer.add(counter, camera, image)
            if combined is None:
                if time.monotonic() - last_pair > 10:
                    raise RuntimeError('Valid raw data, but no matching left/right pair within 10 seconds.')
                continue
            last = combined
            last_pair = time.monotonic()
            rendered += 1
            active_rotations = rotations if last.shape[1] == 960 else [rotations[a.mono_camera], False]
            active_mirrors = mirrors if last.shape[1] == 960 else [mirrors[a.mono_camera], False]
            display = compose(last, swapped, active_rotations, active_mirrors)
            if start_recording:
                recorder = Recorder(a.output, display,audio=None if a.no_audio else a.audio_device)
                print(f'Recording: {recorder.path}', flush=True)
                start_recording = False
            if recorder:
                recorder.push(display)
            if a.passthrough:
                display = letterbox_stereo(display, target['width'], target['height'])
            elif a.passthrough_2d:
                display = letterbox_mono(display, target['width'], target['height'])
            if recorder and not a.check_frames:
                display = display.copy()
                cv2.putText(display, 'REC + MIC - v: stop' if recorder.audio else 'REC VIDEO ONLY - v: stop', (16, 32),
                            cv2.FONT_HERSHEY_SIMPLEX, .7, 255, 2)
            if raw_recorder and not a.check_frames:
                display=display.copy()
                cv2.putText(display,'RAW REC - b: stop',(16,64),cv2.FONT_HERSHEY_SIMPLEX,.7,255,2)
            if not a.check_frames and time.monotonic() < feedback_until:
                display = display.copy()
                cv2.rectangle(display, (0, display.shape[0]-48), (display.shape[1],display.shape[0]), 0, -1)
                # Short ASCII labels are supported by OpenCV's built-in font.
                cv2.putText(display, feedback, (10, display.shape[0]-16),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, 255, 1)
            if a.check_frames:
                if rendered >= a.check_frames:
                    print(f'STREAM_OK: decoded={valid}, displayed={rendered}, skipped={skipped}, shape={display.shape}')
                    return
                continue
            if not window_created:
                cv2.namedWindow(window, cv2.WINDOW_NORMAL)
                if target:
                    cv2.moveWindow(window, target['x']+10, target['y']+10)
                    cv2.resizeWindow(window, min(960, target['width']), min(640, target['height']))
                if fullscreen:
                    cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                window_created = True
            cv2.imshow(window, display)
            if pending_key != 255:
                key, pending_key = pending_key, 255
            else:
                key = read_key()
            if key in (ord('q'), 27):
                print('Exiting preview.', flush=True)
                break
            if key in tuple(map(ord, 'bcvxr1234mfs')):
                feedback = {'c':'Cleaning toggled', 'v':'Recording toggled',
                            'b':'Raw recording toggled',
                            'x':'Camera positions swapped', 'r':'Rotation changed',
                            '1':'Group 0 rotation changed', '2':'Group 1 rotation changed',
                            '3':'Group 0 mirror changed', '4':'Group 1 mirror changed',
                            'm':'Mirror changed', 'f':'Fullscreen toggled',
                            's':'Snapshot requested'}[chr(key)]
                feedback_until = time.monotonic()+3
                print(feedback, flush=True)
            if key == ord('c'):
                clean = not clean
                pairer = Pairer()
            if key == ord('v'):
                if recorder:
                    print(f'Video saved: {recorder.close()}', flush=True)
                    recorder = None
                else:
                    start_recording = True
            if key == ord('b'):
                if raw_recorder:
                    print(f'Raw saved: {raw_recorder.close()}',flush=True)
                    raw_recorder=None
                else:
                    start_raw=True
            if key == ord('x'):
                swapped = not swapped
            if key == ord('r'):
                rotations = [not value for value in rotations]
            if key in (ord('1'), ord('2')):
                eye = key - ord('1')
                rotations[eye] = not rotations[eye]
            if key == ord('m'):
                mirrors = [not value for value in mirrors]
            if key in (ord('3'), ord('4')):
                eye = key - ord('3')
                mirrors[eye] = not mirrors[eye]
            if key in tuple(map(ord, 'xr1234m')):
                save_preferences(settings_path, rotations, mirrors, swapped)
            if key == ord('f'):
                fullscreen = not fullscreen
                cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            if key == ord('s'):
                out = Path(a.output)
                out.mkdir(parents=True, exist_ok=True)
                path = out / f'stereo_{time.time_ns()}.png'
                if not cv2.imwrite(str(path), display):
                    raise RuntimeError(f'Could not save {path}')
                print(f'Saved {path}')
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
        if a.probe:
            raise RuntimeError(f'Stereo validation incomplete ({valid} valid frames): {error}')
    finally:
        if raw_recorder:
            print(f'Raw saved: {raw_recorder.close()}',flush=True)
        if recorder:
            print(f'Video saved: {recorder.close()}', flush=True)
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, cv2.error) as exc:
        print(f'ERROR: {exc}')
        raise SystemExit(1)
