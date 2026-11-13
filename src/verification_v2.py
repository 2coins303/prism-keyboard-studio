"""Explicit, noninteractive release verification; isolated data, no desktop input."""
import json,re,tempfile,time,sys
from pathlib import Path
from model import atomic_json,new_profile,render_colors,matrix_frame
from managed_bridge import catalog

def check_bridge(app,Studio,path):
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    discovery_only='--check-discovery' in sys.argv
    report={'version':'2.0.0','frozen':bool(getattr(sys,'frozen',False)),'check_scope':'setup and discovery only' if discovery_only else 'live lighting and audio'}
    def run(seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until:app.processEvents();time.sleep(.01)
    with tempfile.TemporaryDirectory(prefix='prism-bridge-check-',dir=path.parent) as data:
        w=Studio(data,offline=False)
        try:
            w.show();app.processEvents();w.stop_connection()
            model=next(m for m in catalog()['models'] if (m['vid'],m['pid'])==('1532','02A6'))
            from keyboard_setup import KeyboardSetup
            setup=KeyboardSetup(w);setup.search.setText('1532:02A6');setup.show();setup.start_bridge()
            deadline=time.monotonic()+20
            while w.selected_device is None and time.monotonic()<deadline:
                run(.1)
                if setup.job and setup.job.isFinished():
                    app.processEvents()
                    if w.selected_device is None and setup.state.text()!='Starting connection…':break
            assert w.selected_device is not None,setup.state.text()
            ds=setup.devices;assert len(ds)==1 and ds[0].type==5,[(d.name,d.type) for d in ds]
            report['in_app_connect_flow_verified']=True
            run(.3)
            first={'frames':0};second={'frames':0,'acks':0}
            if not discovery_only:
                w.p['effect']='Rainbow wave';w.p['overrides']={};w.load_controls();w.apply();run(2.2)
                first=w.worker.status();assert first['state']=='Live' and first['frames']>=8,first
                w.pause();run(.15);assert w.worker.status()['state']=='Paused'
                w.p['effect']='Audio';w.load_controls();w.apply();run(2.2)
                second=w.worker.status();assert second['state']=='Live' and second['frames']>first['frames'],second
                assert w.capture.last_callback>0
                w.preset('Neon nights');run(.2)
                w.grab().save(str(path.with_suffix('.png')))
            settings=json.loads((w.bridge.directory/'OpenRGB.json').read_text())
            enabled=[k for k,v in settings['Detectors']['detectors'].items() if v]
            assert enabled==[model['detector']],enabled
            report.update(result='PASS',real_server='Official OpenRGB 1.1',protocol=6,
                discovered_keyboard=ds[0].name,discovered_devices=len(ds),physical_matrix=w.layout.spatial,
                visible_keys=len(w.layout.keys),lighting_addresses=len(w.layout.led_ids),
                animation_frames=first['frames'],frames_after_live_audio=second['frames'],sdk_acceptances=second['acks'],
                pause_verified=not discovery_only,audio_callback_verified=not discovery_only,enabled_detectors=enabled,
                other_detectors_disabled=True,physical_lights_verified=False)
        except Exception as e:
            import traceback
            report.update(result='FAIL',error=str(e),traceback=traceback.format_exc())
        finally:
            w.close();app.processEvents()
            report['managed_helper_stopped']=w.bridge.process is None
    if discovery_only:
        atomic_json(path,report);return 0 if report.get('result')=='PASS' else 1
    # Restore the user's prior v1 Neon look after the explicitly requested live test.
    from device import Huntsman
    d=Huntsman()
    try:
        d.connect();d.write_frame(matrix_frame(render_colors(new_profile(),0)));d.restore_brightness()
        report['direct_connection_reverified']=dict(firmware=d.firmware,acks=d.acks)
    except Exception as e:report['direct_restore_error']=str(e)
    finally:d.close()
    atomic_json(path,report);return 0 if report.get('result')=='PASS' else 1
