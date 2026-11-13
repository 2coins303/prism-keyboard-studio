"""Verify old pacing and the extended speed range without hardware access."""
import copy,hashlib,json,math,sys,tempfile,traceback
from pathlib import Path
import numpy as np
from model import APP_NAME,VERSION,MAX_SPEED,ANIMATED,ProfileStore,new_profile,render_colors,matrix_frame,animation_rate,atomic_json
from verification_resize import settle,capture,readable_buttons

def check_old_frames():
    baseline=json.loads(Path(__file__).with_name('speed-baselines.json').read_text(encoding='utf-8'))
    count=0
    for name,speeds in baseline['frames'].items():
        for speed,digest in speeds.items():
            p=new_profile(effect=name);p['speed']=int(speed)
            frame=matrix_frame(render_colors(p,baseline['time'],np.ones((2,6))*baseline['audio_level']))
            assert hashlib.sha256(frame).hexdigest()==digest,(name,speed)
            count+=1
    return count

def check_maximum_pace():
    assert math.isclose(animation_rate(MAX_SPEED)/animation_rate(100),10)
    count=0
    for name in sorted(ANIMATED-{'Audio'}):
        p=new_profile(effect=name);p['speed']=MAX_SPEED
        for t in (.137,.813,2.71):
            fast=np.array(list(render_colors(p,t).values()))
            old=copy.deepcopy(p);old['speed']=100
            expected=np.array(list(render_colors(old,t*10).values()))
            assert (np.abs(fast-expected)<=1).all(),name
            assert ((fast>=0)&(fast<=255)).all(),name
        count+=1
    return count

def check_speed(app,Studio,report_path):
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(app=APP_NAME,version=VERSION,frozen=bool(getattr(sys,'frozen',False)),hardware_access=False)
    with tempfile.TemporaryDirectory(prefix='prism-speed-',dir=report_path.parent) as directory:
        window=Studio(directory,offline=True)
        try:
            report['unchanged_old_frames']=check_old_frames()
            report['animations_at_10x']=check_maximum_pace()
            window.show();window.use_pattern('Galaxy');settle(160);window.timer.stop()
            assert window.speed.maximum()==MAX_SPEED and window.speed.minimum()==0
            window.phase=17.25;before=window.phase*animation_rate(window.p['speed'])
            window.speed_value.setValue(MAX_SPEED)
            assert math.isclose(before,window.phase*animation_rate(window.p['speed']))
            window.speed_control.quick_buttons[500].click();assert window.p['speed']==500
            window.speed_control.quick_buttons[1000].click();assert window.p['speed']==MAX_SPEED
            assert window.speed.value()==MAX_SPEED and window.speed_value.value()==MAX_SPEED
            window.save_profile();assert ProfileStore(directory).get()['speed']==MAX_SPEED
            exported=Path(directory)/'fast-look.json';window.store.export_file(exported,window.p)
            assert window.store.import_file(exported)['speed']==MAX_SPEED
            window.tick();settle();readable_buttons(window)
            capture(window,report_path.parent/'Prism 2.5 faster speeds.png')
            window.resize(1100,740);settle()
            window.main_scroll.verticalScrollBar().setValue(window.main_scroll.verticalScrollBar().maximum());settle()
            readable_buttons(window);capture(window,report_path.parent/'Prism 2.5 compact speed controls.png')
            for name in ('Audio','Solid'):
                window.use_pattern(name);assert not window.speed_control.isEnabled()
            report.update(result='PASS',maximum_percent=MAX_SPEED,maximum_multiplier=10,old_low_range_unchanged=True,
                          quick_controls=True,phase_continuity=True,fast_profile_save_and_import=True,controls_readable=True)
        except Exception:report.update(result='FAIL',error=traceback.format_exc())
        finally:window.close();app.processEvents()
    atomic_json(report_path,report)
    return 0 if report['result']=='PASS' else 1
