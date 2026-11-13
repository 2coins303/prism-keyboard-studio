"""Run: python -m unittest -v test_studio (no real device/audio writes)."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from model import *
from device import Huntsman, DeviceWorker
from audio_engine import AudioCapture
from openrazer_win.protocol import chroma
from openrazer_win.protocol.report import Status, RazerReportError

class Profiles(unittest.TestCase):
    def test_round_trip_keeps_audio_keys_and_last_profile(self):
        with tempfile.TemporaryDirectory() as root:
            s=ProfileStore(root); p=s.get(); p['name']='Colorful ✨'; p['effect']='Audio'
            p['overrides']={'W':'#123456','NP0':'#fedcba'}; p['audio']['source']='input:Test mic'
            p['audio']['colors'][2]='#abcdef'; p['audio']['gain']=24; s.commit(p)
            s.export_file(Path(root)/'export.json',p); imported=s.import_file(Path(root)/'export.json')
            self.assertNotEqual(p['id'],imported['id']); self.assertEqual(p['audio'],imported['audio'])
            reopened=ProfileStore(root); self.assertEqual(reopened.last,imported['id'])
            self.assertEqual(reopened.get()['overrides'],p['overrides'])
    def test_bad_import_is_atomic(self):
        with tempfile.TemporaryDirectory() as root:
            s=ProfileStore(root); s.save(); original=s.path.read_bytes()
            p=s.get(); p['brightness']=float('nan')
            path=Path(root)/'invalid.json'; atomic_json(path,dict(format='prism-profile',version=1,profile=p))
            with self.assertRaises(ValueError): s.import_file(path)
            self.assertEqual(original,s.path.read_bytes()); self.assertEqual(len(s.profiles),4)
    def test_rejects_unknown_keys_and_wrong_audio_shape(self):
        for mutate in [lambda p:p.update(overrides={'FAKE':'#ffffff'}),lambda p:p['audio'].update(colors=['#ffffff']),
                       lambda p:p.update(effect='execute'),lambda p:p.update(speed=True)]:
            p=new_profile(); mutate(p)
            with self.assertRaises(ValueError): validate_profile(p)
    def test_corrupt_library_keeps_recovery_copy(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'profiles.json'; path.write_text('{broken')
            s=ProfileStore(root); self.assertTrue(s.warning); s.save()
            recovery=list(Path(root).glob('profiles.recovery-*.json'))
            self.assertEqual(len(recovery),1); self.assertEqual(recovery[0].read_text(),'{broken')
    def test_drafts_survive_without_overwriting_saved(self):
        with tempfile.TemporaryDirectory() as root:
            s=ProfileStore(root); p=s.get(); p['effect']='Sparkle'; s.drafts[p['id']]=p; s.save()
            s=ProfileStore(root); self.assertEqual(s.get()['effect'],'Gradient'); self.assertEqual(s.drafts[p['id']]['effect'],'Sparkle')

class FrequencyTests(unittest.TestCase):
    @staticmethod
    def tone(left=0,right=0,mono=False):
        t=np.arange(4096)/48000
        a=.08*np.sin(2*np.pi*left*t) if left else np.zeros(len(t))
        b=.08*np.sin(2*np.pi*right*t) if right else np.zeros(len(t))
        return a[:,None] if mono else np.stack((a,b),axis=1)
    def test_each_frequency_hits_its_own_band(self):
        for index,freq in enumerate([80,240,650,1800,4200,10000]):
            a=AudioAnalyzer(); levels=a.analyze(self.tone(left=freq),48000,gain=0,smoothing=0,dt=1)
            self.assertEqual(np.argmax(levels[0]),index)
            self.assertGreater(levels[0,index],.45)
            self.assertLess(levels[1].max(),1e-5)
    def test_stereo_channels_do_not_cross(self):
        a=AudioAnalyzer(); levels=a.analyze(self.tone(80,4200),48000,gain=0,smoothing=0,dt=1)
        self.assertEqual(np.argmax(levels[0]),0); self.assertEqual(np.argmax(levels[1]),4)
        self.assertLess(levels[1,0],.01); self.assertLess(levels[0,4],.01)
    def test_mono_is_mirrored(self):
        a=AudioAnalyzer(); levels=a.analyze(self.tone(left=650,mono=True),48000,dt=1)
        np.testing.assert_allclose(levels[0],levels[1])
    def test_silence_decays_and_nan_is_safe(self):
        a=AudioAnalyzer(); a.analyze(self.tone(80,4200),48000,dt=1)
        for _ in range(100): a.analyze(np.zeros((4096,2)),48000,dt=.1)
        self.assertLess(a.levels.max(),1e-5)
        self.assertTrue(np.isfinite(a.analyze(np.full((4096,2),np.nan),48000)).all())
    def test_audio_color_uses_frequency_and_physical_side(self):
        p=new_profile(effect='Audio'); p['brightness']=100
        levels=np.zeros((2,6)); levels[0,0]=1
        colors=render_colors(p,0,levels)
        for k in KEYS:
            if k.x+k.w/2>=11.5: self.assertEqual(colors[k.id],(0,0,0))
        self.assertEqual(colors['LEFTCTRL'],tuple(int(x) for x in rgb(BAND_COLORS[0])))
        self.assertEqual(colors['RIGHTCTRL'],(0,0,0))

class Effects(unittest.TestCase):
    def test_all_effects_have_bounded_complete_frames(self):
        for effect in EFFECTS:
            p=new_profile(effect=effect)
            for t in [0,1.25,12345.6]:
                colors=render_colors(p,t,np.ones((2,6)))
                self.assertEqual(set(colors),set(KEY_BY_ID)); self.assertEqual(len(matrix_frame(colors)),396)
                self.assertTrue(all(0<=v<=255 for c in colors.values() for v in c))
    def test_mapped_keys_have_unique_cells(self):
        self.assertEqual(len(KEYS),106)
        self.assertEqual(len({(k.row,k.col) for k in KEYS}),len(KEYS))
        self.assertEqual((KEY_BY_ID['W'].row,KEY_BY_ID['W'].col),(2,3))
        self.assertEqual((KEY_BY_ID['BACKSLASH'].row,KEY_BY_ID['BACKSLASH'].col),(2,14))
    def test_overrides_and_brightness(self):
        p=new_profile(); p['overrides']={'W':'#ff0000'}; p['brightness']=50
        self.assertEqual(render_colors(p,0)['W'],(127,0,0))
        p['brightness']=0; self.assertEqual(set(render_colors(p,0).values()),{(0,0,0)})

class AudioLifecycle(unittest.TestCase):
    def test_switch_closes_previous_input_and_clears_samples(self):
        events=[]
        class Stream:
            def __init__(self,index): self.index=index
            def stop_stream(self): events.append(('stop',self.index))
            def close(self): events.append(('close',self.index))
            def is_active(self): return True
        class PA:
            def open(self,**kw): events.append(('open',kw['input_device_index'])); return Stream(kw['input_device_index'])
        c=AudioCapture(); c.pa=PA(); c.sources=[dict(id='a',rate=48000,channels=2,index=1),dict(id='b',rate=48000,channels=1,index=2)]
        c.start('a'); c.samples.fill(1); c.start('b')
        self.assertEqual(events,[('open',1),('stop',1),('close',1),('open',2)])
        self.assertEqual(c.samples.shape,(4096,1)); self.assertEqual(c.samples.max(),0)
        c.stop(); self.assertIsNone(c.stream)
    def test_unavailable_source_never_reuses_old_capture(self):
        c=AudioCapture()
        with self.assertRaisesRegex(ValueError,'unavailable'): c.start('missing')
        self.assertIsNone(c.stream)
    def test_unplugged_capture_reports_error_and_closes(self):
        class Stream:
            def is_active(self): return False
            def stop_stream(self): pass
            def close(self): pass
        c=AudioCapture(); c.stream=Stream(); samples,text=c.read()
        self.assertIsNone(samples); self.assertIn('stopped',text); self.assertIsNone(c.stream)

class DeviceBehavior(unittest.TestCase):
    def test_another_controllers_transaction_is_rejected(self):
        class Transport:
            def send_payload(self,r,w): r.status=Status.SUCCESSFUL; r.transaction_id=0x98; return r
        d=Huntsman(); d.transport=Transport()
        with self.assertRaisesRegex(RazerReportError,'Another controller'): d.command(chroma.standard_get_firmware_version())
        self.assertEqual(d.acks,0)
    def test_busy_is_not_success(self):
        class Transport:
            def send_payload(self,r,w): r.status=Status.BUSY; return r
        d=Huntsman(); d.transport=Transport()
        with self.assertRaises(RazerReportError): d.command(chroma.standard_get_firmware_version())
        self.assertEqual(d.acks,0)
    def test_full_frame_ack_count_and_shape(self):
        class Transport:
            def __init__(self): self.requests=[]
            def send_payload(self,r,w): self.requests.append(r); r.status=Status.SUCCESSFUL; return r
        d=Huntsman(); d.transport=Transport(); d.write_frame(bytes(396))
        self.assertEqual(d.acks,8)
        self.assertEqual([(r.command_class,r.command_id) for r in d.transport.requests],[(15,4)]+[(15,3)]*6+[(15,2)])
        with self.assertRaises(ValueError): d.write_frame(bytes(395))
    def test_worker_disconnect_pause_reconnect(self):
        class Fake:
            def heartbeat(self): pass
            def __init__(self): self.firmware='test'; self.acks=0; self.calls=0; self.fail=False; self.restored=False
            def connect(self): self.acks+=1
            def write_frame(self,data):
                if self.fail: raise OSError('unplugged')
                self.calls+=1; self.acks+=7
            def command(self,*a): self.acks+=1
            def close(self): pass
            def restore_brightness(self): self.restored=True
        def wait_for(fn):
            end=time.monotonic()+2
            while time.monotonic()<end:
                if fn(): return
                time.sleep(.01)
            self.fail('Worker did not reach expected state')
        w=DeviceWorker(Fake); w.start()
        try:
            wait_for(lambda:w.status()['state']=='Ready'); w.submit(bytes(396)); w.enable(True)
            wait_for(lambda:w.status()['state']=='Live'); w.enable(False)
            wait_for(lambda:w.status()['state']=='Paused'); count=w.device.calls; time.sleep(.1); self.assertEqual(w.device.calls,count)
            w.device.fail=True; w.submit(bytes([1])*396); w.enable(True)
            wait_for(lambda:w.status()['state']=='Unavailable')
            w.device.fail=False; w.request('retry'); wait_for(lambda:w.status()['state']=='Live')
        finally: w.shutdown()
        self.assertTrue(w.device.restored)

if __name__=='__main__': unittest.main()
