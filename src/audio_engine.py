"""Local WASAPI microphone / playback capture. No files, network or playback."""
from __future__ import annotations
import threading
import time
import numpy as np
import pyaudiowpatch as pa

class AudioCapture:
    def __init__(self):
        self.pa=None; self.stream=None; self.sources=[]; self.lock=threading.Lock()
        self.samples=np.zeros((4096,2),dtype=np.float32); self.rate=48000; self.channels=2
        self.last_callback=0.; self.error=''; self.source=None; self.overflow=False
    def refresh(self):
        self.stop()
        if self.pa: self.pa.terminate()
        self.pa=pa.PyAudio(); self.sources=[]
        api=self.pa.get_host_api_info_by_type(pa.paWASAPI)
        default_output=self.pa.get_device_info_by_index(api['defaultOutputDevice'])['name'] if api['defaultOutputDevice']>=0 else ''
        for i in range(self.pa.get_device_count()):
            d=self.pa.get_device_info_by_index(i)
            if d['hostApi']!=api['index'] or d['maxInputChannels']<1: continue
            loop=bool(d.get('isLoopbackDevice'))
            self.sources.append(dict(id=('playback:' if loop else 'input:')+d['name'],
                                     name=d['name'].replace(' [Loopback]',''), index=i,loopback=loop,
                                     channels=int(d['maxInputChannels']),rate=int(d['defaultSampleRate']),
                                     default=loop and default_output in d['name']))
        self.sources.sort(key=lambda d:(not d['default'],not d['loopback'],d['name']))
        return self.sources
    def start(self,source_id):
        self.stop(); self.error=''; self.overflow=False
        source=next((s for s in self.sources if s['id']==source_id),None)
        if source is None: raise ValueError('This audio source is unavailable. Refresh sources and choose one.')
        self.source=source; self.rate=source['rate']; self.channels=min(source['channels'],2)
        with self.lock: self.samples=np.zeros((4096,self.channels),dtype=np.float32); self.last_callback=0.
        def callback(data,count,info,status):
            try:
                x=np.frombuffer(data,dtype=np.float32).reshape(-1,self.channels)
                with self.lock:
                    n=min(4096,len(x))
                    self.samples=np.concatenate((self.samples[n:],x[-n:]),axis=0)
                    self.last_callback=time.monotonic(); self.overflow=bool(status)
                return (None,pa.paContinue)
            except Exception as e:
                self.error=str(e); return (None,pa.paAbort)
        try:
            self.stream=self.pa.open(format=pa.paFloat32,channels=self.channels,rate=self.rate,
                                     input=True,input_device_index=source['index'],
                                     frames_per_buffer=1024,stream_callback=callback)
        except Exception:
            self.stream=None; self.source=None; raise
    def read(self):
        if not self.stream: return None,'Audio stopped'
        try:
            if self.error: raise RuntimeError(self.error)
            if not self.stream.is_active(): raise RuntimeError('The audio source stopped. Refresh and choose a connected source.')
            with self.lock: x=self.samples.copy(); age=time.monotonic()-self.last_callback
            if age>.5: x.fill(0)
            mono=self.channels==1
            text='Mono input · mirrored to both halves' if mono else '2-channel input · left and right analyzed separately'
            if age>1.5: text='Waiting for audio · play music or check the selected source'
            elif self.overflow: text+=' · audio buffer recovered'
            return x,text
        except Exception as e:
            self.error=str(e); self.stop(); return None,str(e)
    def stop(self):
        if self.stream:
            stream=self.stream; self.stream=None
            try: stream.stop_stream()
            finally: stream.close()
        self.source=None
        with self.lock: self.samples=np.zeros((4096,self.channels),dtype=np.float32); self.last_callback=0.
    def close(self):
        self.stop()
        if self.pa: self.pa.terminate(); self.pa=None
