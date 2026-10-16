"""Processed-view MP4 capture, with monotonic arrival times in a CSV sidecar."""
import csv
import time
from pathlib import Path
import cv2

class Recorder:
    def __init__(self, folder, image, fps=30, audio=None):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / f'capture_{time.time_ns()}.mp4'
        self.shape = image.shape
        self.fps = fps
        self.writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*'mp4v'),
                                      fps, (image.shape[1], image.shape[0]))
        if not self.writer.isOpened():
            self.writer.release()
            raise RuntimeError('MP4 encoder could not open; preview can be used without recording.')
        self.file = None
        try:
            self.file = self.path.with_suffix('.csv').open('w', newline='', encoding='utf-8')
            self.csv = csv.writer(self.file)
            self.csv.writerow(['input_frame', 'elapsed_seconds', 'output_frames'])
        except OSError:
            self.writer.release()
            raise
        self.start = None
        self.previous = None
        self.inputs = self.frames = 0
        self.audio=None
        self.closed=False
        if audio is not None:
            try:
                from audio_capture import open_audio
                self.audio=open_audio(self.path.with_suffix('.wav'),audio)
                print(f"Microphone: {self.audio.device['name']} ({self.audio.device['api']})",flush=True)
            except Exception as exc:
                print(f'AUDIO UNAVAILABLE: {exc}. Recording video only.',flush=True)

    def push(self, image, now=None):
        if image.shape != self.shape:
            raise ValueError('Recording image size changed.')
        now = time.monotonic() if now is None else now
        if self.start is None:
            self.start = now
        elapsed = now-self.start
        if elapsed < 0 or elapsed-self.frames/self.fps > 10:
            raise RuntimeError('Recording timestamp discontinuity.')
        # Hold the preceding image for missing time slots rather than speeding
        # up playback when capture drops frames. Save the unscaled corrected view.
        while self.frames/self.fps <= elapsed + 1e-6:
            frame = self.previous if self.previous is not None else image
            self.writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
            self.frames += 1
        self.previous = image.copy()
        self.csv.writerow([self.inputs, f'{elapsed:.6f}', self.frames])
        self.inputs += 1

    def close(self):
        if self.closed:return self.path
        self.closed=True
        self.writer.release()
        if self.file and not self.file.closed:
            self.file.close()
        if self.audio:
            try:
                wav=self.audio.close()
                if self.audio.issue:print('AUDIO WARNING: '+self.audio.issue,flush=True)
                if self.start is None or not self.frames:
                    raise RuntimeError('No video frames to merge with microphone audio.')
                from audio_capture import mux_audio
                combined=self.path.with_name(self.path.stem+'_with_audio.mp4')
                print('Combining video and microphone audio...',flush=True)
                mux_audio(self.path,wav,combined,self.audio.first_sample-self.start,self.frames/self.fps)
                self.path=combined
            except Exception as exc:
                print(f'AUDIO NOT MERGED: {exc}. Original video and any WAV are retained.',flush=True)
        return self.path
