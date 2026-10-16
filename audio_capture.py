"""Microphone WAV capture and timestamp-aligned AAC/MP4 muxing."""
import queue
import subprocess
import threading
import time
import wave
from pathlib import Path
import sounddevice as sd
import imageio_ffmpeg

def input_devices():
    apis=sd.query_hostapis()
    return [dict(index=i,name=d['name'],api=apis[d['hostapi']]['name'],
                 rate=int(d['default_samplerate']),channels=d['max_input_channels'])
            for i,d in enumerate(sd.query_devices()) if d['max_input_channels']>0]

def choose_device(selection='auto'):
    devices=input_devices()
    if selection!='auto':
        selected=int(selection)
        matches=[d for d in devices if d['index']==selected]
        if not matches:raise RuntimeError('Selected microphone is unavailable; run list-audio.cmd again.')
        return matches[0]
    xreal=[d for d in devices if 'xreal' in d['name'].lower()]
    if xreal:
        return sorted(xreal,key=lambda d:(d['api']!='Windows WASAPI',d['index']))[0]
    default=int(sd.default.device[0])
    matches=[d for d in devices if d['index']==default]
    if matches:return matches[0]
    raise RuntimeError('No microphone input is available.')

class AudioCapture:
    def __init__(self,path,device='auto'):
        self.device=choose_device(device)
        self.path=Path(path)
        self.rate=self.device['rate']
        self.channels=min(2,self.device['channels'])
        self.first_sample=None
        self.samples=0
        self.issue=None
        self.queue=queue.Queue(maxsize=256)
        self.stream=None
        self.writer=wave.open(str(self.path),'wb')
        self.writer.setnchannels(self.channels)
        self.writer.setsampwidth(2)
        self.writer.setframerate(self.rate)
        def callback(data,frames,clock,status):
            if self.first_sample is None:
                self.first_sample=time.monotonic()+float(clock.inputBufferAdcTime-clock.currentTime)
            if status:self.issue=f'Audio buffer status: {status}'
            try:self.queue.put_nowait(bytes(data))
            except queue.Full:self.issue='Audio write queue overflow; some samples were dropped.'
        def write_loop():
            try:
                while True:
                    data=self.queue.get()
                    if data is None:break
                    self.writer.writeframesraw(data)
                    self.samples+=len(data)//(2*self.channels)
            except Exception as exc:
                self.issue=f'Audio file write failed: {exc}'
        self.thread=threading.Thread(target=write_loop,daemon=True)
        try:
            self.stream=sd.RawInputStream(device=self.device['index'],samplerate=self.rate,
                channels=self.channels,dtype='int16',callback=callback)
            self.thread.start()
            self.stream.start()
        except Exception:
            if self.stream:self.stream.close()
            if self.thread.is_alive():
                self.queue.put(None)
                self.thread.join(timeout=3)
            self.writer.close()
            raise

    def close(self):
        if self.stream:
            try:self.stream.stop()
            finally:self.stream.close()
            self.stream=None
        if self.thread.is_alive():
            self.queue.put(None,timeout=3)
            self.thread.join(timeout=5)
        if self.thread.is_alive():raise RuntimeError('Audio writer did not stop; WAV may be incomplete.')
        self.writer.close()
        if self.samples==0:raise RuntimeError('Microphone returned no audio samples.')
        return self.path

def open_audio(path,selection='auto'):
    if selection!='auto':return AudioCapture(path,selection)
    chosen=choose_device()
    devices=input_devices()
    candidates=[d for d in devices if 'xreal' in d['name'].lower()] if 'xreal' in chosen['name'].lower() else [chosen]
    priority={'Windows WASAPI':0,'MME':1,'Windows DirectSound':2}
    candidates=sorted([d for d in candidates if d['api'] in priority],key=lambda d:priority[d['api']])
    errors=[]
    for device in candidates:
        try:return AudioCapture(path,str(device['index']))
        except Exception as exc:errors.append(f"{device['api']}: {exc}")
    raise RuntimeError('Microphone could not open. Check Windows microphone and desktop-app access. '+' | '.join(errors))

def mux_audio(video,wav,output,offset,duration):
    """offset = first recorded audio sample time minus first video time."""
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error',
             '-nostdin','-y','-i',str(video)]
    if offset<0:command+=['-ss',f'{-offset:.9f}']
    command+=['-i',str(wav)]
    filters=[]
    if offset>0:filters.append(f'adelay={round(offset*1000)}:all=1')
    filters+=['apad',f'atrim=duration={duration:.9f}','asetpts=PTS-STARTPTS']
    command+=['-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
              '-af',','.join(filters),'-t',f'{duration:.9f}','-movflags','+faststart',str(output)]
    result=subprocess.run(command,capture_output=True,timeout=max(60,duration*.5),
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode!=0:
        raise RuntimeError('Audio/video merge failed: '+result.stderr.decode('utf-8',errors='replace')[-1000:])
