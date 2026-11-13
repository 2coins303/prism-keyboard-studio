"""Only USB 1532:02A6. Lighting only; no input interception or firmware writes."""
from __future__ import annotations
import logging
import threading
import time
from openrazer_win.hid.win32 import Win32HidBackend
from openrazer_win.core.transport import open_transport
from openrazer_win.protocol import chroma
from openrazer_win.protocol.report import Status, RazerReportError

log=logging.getLogger(__name__)

class Huntsman:
    def __init__(self):
        self.transport=None; self.acks=0; self.original_brightness=None; self.owned=False; self.brightness_ready=False
        self.firmware=''; self.interface=None
    def command(self,report,txid=0x1f):
        report.transaction_id=txid
        answer=self.transport.send_payload(report,True)
        if answer is None or answer.status!=Status.SUCCESSFUL:
            raise RazerReportError('The keyboard has not confirmed this command. Another lighting app may be using it.')
        if answer.transaction_id != txid:
            raise RazerReportError(f'Another controller replied with transaction 0x{answer.transaction_id:02X}; Prism sent 0x{txid:02X}. Pause the other lighting app.')
        self.acks+=1
        return answer
    def connect(self):
        from managed_bridge import openrgb_running
        if openrgb_running(): raise RuntimeError("OpenRGB is running. Close it to use direct USB, or select this keyboard through the bridge.")
        self.close()
        # Enumeration filters VID and PID BEFORE opening/describing any collection.
        self.transport=open_transport(Win32HidBackend(),0x1532,0x02a6,preferred_index=3,wait_us=600)
        self.interface=self.transport.info.interface
        try:
            a=self.command(chroma.standard_get_firmware_version(),0xff)
            self.firmware=f'{a.arguments[0]}.{a.arguments[1]}'
            # The upstream standard read is rejected by this firmware. Its matching
            # extended read is supported and was verified on the user's keyboard.
            a=self.command(chroma.extended_matrix_get_brightness(1,5))
            if self.original_brightness is None: self.original_brightness=int(a.arguments[2])
            self.brightness_ready=False
        except Exception:
            self.close(); raise
    def write_frame(self,data):
        if not isinstance(data,bytes) or len(data)!=396: raise ValueError('A frame must have exactly 6 × 22 RGB colors.')
        if not self.brightness_ready:
            self.owned=True  # Even a lost response can follow a completed brightness write.
            self.command(chroma.extended_matrix_brightness(1,5,255))
            self.brightness_ready=True
        # Use the exact report builders and transaction ID from OpenRazer's 02A6 recipes.
        for row in range(6):
            self.command(chroma.extended_matrix_set_custom_frame(row,0,21,data[row*66:(row+1)*66]))
        self.command(chroma.extended_matrix_effect_custom_frame())
    def heartbeat(self): self.command(chroma.standard_get_firmware_version(),0xff)
    def rainbow(self):
        self.command(chroma.extended_matrix_effect_spectrum(1,5))
    def restore_brightness(self):
        if self.owned and self.original_brightness is not None and self.transport:
            self.command(chroma.extended_matrix_brightness(1,5,self.original_brightness))
            self.owned=False; self.brightness_ready=False
    def close(self):
        if self.transport: self.transport.close(); self.transport=None
        self.brightness_ready=False

class DeviceWorker(threading.Thread):
    """A latest-frame mailbox: USB never blocks the UI or builds a frame backlog."""
    def __init__(self,device_factory=Huntsman):
        super().__init__(name='Prism USB',daemon=True)
        self.device=device_factory(); self.lock=threading.Lock(); self.wake=threading.Event()
        self.alive=True; self.enabled=False; self.latest=None; self.revision=0; self.action=None
        self.snapshot=dict(state='Connecting',message='Looking for your Huntsman V3 Pro…',acks=0,frames=0,firmware='',fps=0.)
    def update(self,**values):
        with self.lock: self.snapshot.update(values)
    def status(self):
        with self.lock: return self.snapshot.copy()
    def submit(self,frame):
        with self.lock: self.latest=frame; self.revision+=1
        self.wake.set()
    def enable(self,enabled):
        with self.lock:
            self.enabled=bool(enabled)
            if enabled: self.revision+=1
        self.wake.set()
    def request(self,action):
        with self.lock:
            self.action=action
            if action in ('release','rainbow'): self.enabled=False
        self.wake.set()
    def shutdown(self):
        self.alive=False; self.wake.set(); self.join(timeout=8)
        if self.is_alive(): raise RuntimeError("The previous keyboard connection is still closing. Try again shortly.")
    def run(self):
        connected=False; retry=0.; sent=-1; last_frame=None; last_write=0.; frames=0
        while self.alive:
            now=time.monotonic()
            with self.lock: action=self.action; self.action=None; enabled=self.enabled; frame=self.latest; rev=self.revision
            if action=='retry': retry=0
            if not connected and now>=retry:
                try:
                    self.device.connect(); connected=True; sent=-1; last_frame=None
                    self.update(state='Ready',message='Keyboard connected. Apply a look when you are ready.',firmware=self.device.firmware)
                except Exception as e:
                    self.update(state='Unavailable',message=f'Cannot reach the keyboard: {e}'); retry=now+5
            try:
                if connected and action in ('release','rainbow'):
                    if action=='rainbow': self.device.rainbow()
                    self.device.restore_brightness()
                    self.update(state='Ready',message='Rainbow applied; USB streaming stopped.' if action=='rainbow' else 'Keyboard released. Last colors may remain until another app takes over.')
                    last_frame=None; sent=-1
                if connected and enabled and frame is not None and (rev!=sent):
                    if frame!=last_frame or now-last_write>2:
                        start=time.monotonic(); self.device.write_frame(frame)
                        elapsed=time.monotonic()-start; frames+=1; last_write=now; last_frame=frame
                        self.update(state='Live',message=('OpenRGB accepted the lighting frame; physical lights are not verified.' if self.device.__class__.__name__=='OpenRGBKeyboard' else 'Keyboard acknowledged the lighting frame.'),frames=frames,fps=min(24,1/max(.001,elapsed)))
                    if getattr(self.device,"static_only",False):
                        self.enable(False);self.update(state="Ready",message="Static look applied. Press Apply again to send changes.")
                    sent=rev
                elif connected and not enabled and self.status()['state']=='Live':
                    self.update(state='Paused',message='Paused. No lighting frames are being sent; the last colors can remain.')
                if connected and now-last_write>4 and not enabled:
                    # Read only heartbeat, including when previewing offline from hardware.
                    self.device.heartbeat(); last_write=now
                self.update(acks=self.device.acks)
            except Exception as e:
                log.warning('Keyboard transfer stopped: %s',e)
                self.device.close(); connected=False; retry=now+5; last_frame=None
                self.update(state='Unavailable',message=f'Lighting interrupted: {e}. Reconnecting in 5 seconds.')
            self.wake.wait(.042); self.wake.clear()
        try: self.device.restore_brightness()
        except Exception: log.warning('Could not restore the initial brightness on exit.',exc_info=True)
        self.device.close()
