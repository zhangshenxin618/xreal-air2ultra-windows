import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import wave
import subprocess
import numpy as np
import cv2
import imageio_ffmpeg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio_capture import mux_audio,open_audio,AudioCapture
from video_recorder import Recorder

with TemporaryDirectory() as directory:
    folder=Path(directory)
    image=np.full((640,480),80,np.uint8)
    recorder=Recorder(folder,image)
    for i in range(60):recorder.push(image,100+i/30)
    silent=recorder.close()
    wav=folder/'tone.wav'
    rate=48000
    tone=(np.sin(np.arange(rate*3)*2*np.pi*440/rate)*12000).astype('<i2')
    with wave.open(str(wav),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate);stream.writeframes(tone.tobytes())
    for offset in [-.2,.2]:
        output=folder/f'mux_{offset}.mp4'
        mux_audio(silent,wav,output,offset,2)
        result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(output),
            '-map','0:a:0','-f','s16le','-ac','1','-ar',str(rate),'-'],capture_output=True,check=True)
        pcm=np.frombuffer(result.stdout,dtype='<i2').astype(float)
        assert 2*rate<=len(pcm)<2*rate+2048
        assert np.max(np.abs(pcm))>5000
        if offset>0:
            assert np.sqrt(np.mean(pcm[:int(.15*rate)]**2))<20
            assert np.sqrt(np.mean(pcm[int(.3*rate):int(.5*rate)]**2))>1000
        cap=cv2.VideoCapture(str(output));assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==60;cap.release()
    class CapturedAudio:
        device=dict(name='test tone',api='test')
        first_sample=100.2
        issue=None
        def close(self):return wav
    with patch('audio_capture.open_audio',return_value=CapturedAudio()):
        recorder=Recorder(folder,image,audio='auto')
        for i in range(60):recorder.push(image,100+i/30)
        merged=recorder.close()
        assert merged.name.endswith('_with_audio.mp4') and merged.exists()
    with patch('audio_capture.open_audio',side_effect=RuntimeError('test unavailable')):
        recorder=Recorder(folder,image,audio='auto')
        recorder.push(image,100)
        assert recorder.audio is None
        assert recorder.close().exists()
    class FakeStream:
        def __init__(self,**kwargs):self.callback=kwargs['callback']
        def start(self):
            from types import SimpleNamespace
            self.callback(tone[:480].tobytes(),480,SimpleNamespace(inputBufferAdcTime=9.9,currentTime=10),False)
        def stop(self):pass
        def close(self):pass
    with patch('audio_capture.choose_device',return_value=dict(index=0,name='test',api='test',rate=48000,channels=1)), \
         patch('audio_capture.sd.RawInputStream',FakeStream):
        capture=AudioCapture(folder/'callback.wav')
        capture.close()
        assert capture.samples==480 and capture.first_sample is not None
        with wave.open(str(folder/'callback.wav'),'rb') as stream:assert stream.getnframes()==480
        assert recorder.close().exists()
with patch('audio_capture.choose_device',return_value={'name':'XREAL'}), \
     patch('audio_capture.input_devices',return_value=[dict(index=1,name='XREAL',api='Windows WASAPI'),dict(index=2,name='XREAL',api='MME')]), \
     patch('audio_capture.AudioCapture',side_effect=[RuntimeError('blocked'),object()]) as capture:
    open_audio('unused.wav')
    assert capture.call_args.args[1]=='2'
print('PASS: MP4 contains decoded AAC audio, positive/negative offsets, retained video duration, microphone fallback and silent-video recovery')
