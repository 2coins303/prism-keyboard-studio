"""Launch only the packaged, hash-pinned OpenRGB with one keyboard detector."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from bridge import SDK,BridgeError
from model import atomic_json

RESOURCE_DIR=Path(__file__).resolve().parent
PACKAGE_DIR=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else RESOURCE_DIR.parent

def catalog(): return json.loads((RESOURCE_DIR/'compatibility.json').read_text(encoding='utf-8'))

def openrgb_running():
    """Read-only process inventory, used to prevent two USB owners."""
    if os.name!='nt': return False
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),
                  ('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),
                  ('flags',wintypes.DWORD),('exe',wintypes.WCHAR*260)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    k.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]; k.Process32NextW.argtypes=k.Process32FirstW.argtypes
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=k.CreateToolhelp32Snapshot(2,0); e=Entry(); e.size=ctypes.sizeof(e)
    try:
        ok=k.Process32FirstW(handle,ctypes.byref(e))
        while ok:
            if e.exe.casefold()=='openrgb.exe': return True
            ok=k.Process32NextW(handle,ctypes.byref(e))
        return False
    finally:k.CloseHandle(handle)

class ManagedBridge:
    def __init__(self,data_dir): self.directory=Path(data_dir).resolve()/'keyboard-bridge-v1.1'; self.process=None; self.port=None; self.log=None
    def start(self,model,nodetect=False):
        self.stop()
        if openrgb_running(): raise BridgeError('OpenRGB is already running. Close it yourself before starting Prism’s private bridge, or use Connect existing server.')
        root=PACKAGE_DIR/'bridge'
        if not (root/'OpenRGB.exe').exists(): root=PACKAGE_DIR/'managed-bridge'
        manifest=json.loads((RESOURCE_DIR/'bridge-manifest.json').read_text())
        if list(root.glob('*.bin')): raise BridgeError('This bridge contains low-level hardware modules. Restore Prism’s supplied bridge folder.')
        for name,digest in manifest.items():
            file=root/name
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
                raise BridgeError('The bundled bridge is missing or changed. Restore the supplied bridge folder.')
        info=catalog()
        if model['detector'] not in {x['detector'] for x in info['models']}: raise BridgeError('Choose a keyboard from the compatibility list.')
        self.directory.mkdir(parents=True,exist_ok=True)
        settings={'Detectors':{'detectors':{name:name==model['detector'] for name in info['detectors']},'hid_safe_mode':False},
                  'QMKOpenRGBDevices':{'devices':[]},'QMKVialRGBDevices':{'devices':[]},
                  'AutoStart':{'enabled':False}}
        atomic_json(self.directory/'OpenRGB.json',settings)
        with socket.socket() as s: s.bind(('127.0.0.1',0)); self.port=s.getsockname()[1]
        args=[str(root/'OpenRGB.exe'),'--noautoconnect','--server','--server-host','127.0.0.1',
              '--server-port',str(self.port),'--config',str(self.directory),'--loglevel','5']
        if nodetect: args.append('--nodetect')
        env=os.environ.copy()
        # OpenRGB reads APPDATA once before processing --config; isolate that read too.
        env['APPDATA']=str(self.directory/'bootstrap')
        for key in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM'): env.pop(key,None)
        self.log=open(self.directory/'bridge.log','w',encoding='utf-8')
        # Frozen Python's DLL search directory must not leak into the separate Qt app.
        if os.name=='nt': ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            self.process=subprocess.Popen(args,cwd=root,stdout=self.log,stderr=subprocess.STDOUT,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        finally:
            if os.name=='nt' and getattr(sys,'frozen',False): ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
        started=time.monotonic(); deadline=started+25
        while time.monotonic()<deadline:
            if self.process.poll() is not None: raise BridgeError('The private bridge stopped. See the local bridge log in Help.')
            try:
                sdk=SDK(self.port).connect()
                try: devices=sdk.devices()
                finally:sdk.close()
                if devices or nodetect or time.monotonic()-started>8: return devices
                time.sleep(.2)
            except (OSError,BridgeError): time.sleep(.15)
        self.stop(); raise BridgeError('The private bridge did not start in time. Check the keyboard connection and close its other lighting app.')
    def stop(self):
        if self.process and self.process.poll() is None:
            # Only terminate the exact child created by this instance; never another app.
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill(); self.process.wait(timeout=2)
        self.process=None
        if self.log:self.log.close(); self.log=None
