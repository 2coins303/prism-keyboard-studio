"""Scoped OpenRGB SDK 6 connection. No device scanning, driver or firmware operations.

Protocol derived from OpenRGB 1.1 NetworkProtocol.h / RGBController.cpp (GPL-2.0+).
Require SDK 6: controller IDs survive changes to the enumeration order.
"""
from __future__ import annotations
import hashlib
import json
import socket
import struct
from dataclasses import dataclass
from types import SimpleNamespace as NS


class BridgeError(RuntimeError): pass

class Reader:
    def __init__(self,data): self.data=data; self.pos=0
    def take(self,n):
        if n<0 or self.pos+n>len(self.data): raise BridgeError('Incomplete OpenRGB device description.')
        value=self.data[self.pos:self.pos+n]; self.pos+=n; return value
    def num(self,fmt='I'): return struct.unpack('<'+fmt,self.take(struct.calcsize('<'+fmt)))[0]
    def string(self,wide=False):
        n=self.num('I' if wide else 'H')
        if n>65536: raise BridgeError('Oversized device name.')
        return self.take(n).rstrip(b'\0').decode('utf-8','replace')
    def matrix(self):
        size=self.num('H')
        if not size: return None
        h=self.num(); w=self.num()
        if not (0<h<=128 and 0<w<=256) or size!=8+4*h*w: raise BridgeError('Invalid keyboard matrix.')
        return [[self.num() for _ in range(w)] for _ in range(h)]
    def mode(self):
        name=self.string(); values=[self.num() for _ in range(11)]
        self.take(self.num('H')*4)
        return NS(name=name,flags=values[0],color_mode=values[-1])
    def zone(self):
        name=self.string(); typ=self.num(); low=self.num(); high=self.num(); count=self.num(); matrix=self.matrix()
        for _ in range(self.num('H')):
            self.string(); self.take(12); self.matrix(); self.take(4)
        flags=self.num(); self.take(4)
        modes=[self.mode() for _ in range(self.num('H'))]; self.string()
        return NS(name=name,type=typ,count=count,matrix=matrix,flags=flags,modes=modes)

def parse_controller(raw,controller_id):
    r=Reader(raw)
    if r.num()!=len(raw): raise BridgeError('Invalid OpenRGB description length.')
    typ=r.num(); name=r.string()
    vendor,description,version,serial,location=[r.string() for _ in range(5)]
    n=r.num('H'); active=r.num(); modes=[r.mode() for _ in range(n)]
    zones=[r.zone() for _ in range(r.num('H'))]
    leds=[r.string() for _ in range(r.num('H'))]
    ncolors=r.num('H'); colors=[tuple(r.take(4)[:3]) for _ in range(ncolors)]
    for _ in range(r.num('H')): r.string()
    flags=r.num(); r.string(); r.string(True)
    if r.pos!=len(raw) or ncolors!=len(leds) or len(leds)>2048: raise BridgeError('Unsupported device description.')
    d=NS(id=controller_id,type=typ,name=name,vendor=vendor,description=description,version=version,
         serial=serial,location=location,modes=modes,zones=zones,leds=leds,colors=colors,flags=flags)
    d.identity=identity(d); d.signature=signature(d)
    return d

def identity(d):
    # Without a serial, the USB location is the identity. A port change requires reselection.
    token=d.serial.strip() or d.location.strip()
    if not token: return ''
    return hashlib.sha256(json.dumps([d.vendor,d.name,token],ensure_ascii=False).encode()).hexdigest()[:24]

def signature(d):
    return hashlib.sha256(json.dumps([d.leds,[(z.name,z.count,z.matrix) for z in d.zones]],sort_keys=True).encode()).hexdigest()[:24]

def direct_mode(d):
    for name in ('direct','custom','static'):
        for m in d.modes:
            if m.name.casefold()==name and (getattr(m,'color_mode',1) in (1,2) or m.flags&32): return m
    return None

def supports_direct(d): return direct_mode(d) is not None

def static_only(d):
    mode=direct_mode(d)
    return bool(mode and mode.flags&512)

class SDK:
    def __init__(self,port=6742): self.port=int(port); self.sock=None; self.changed=False
    def connect(self):
        self.close(); self.sock=socket.create_connection(('127.0.0.1',self.port),2); self.sock.settimeout(2)
        self.send(0,40,struct.pack('<I',6)); v=struct.unpack('<I',self.receive(0,40))[0]
        if v<6: self.close(); raise BridgeError('Use OpenRGB 1.1 or newer with SDK 6. Older SDKs cannot safely track unplugged keyboards.')
        self.send(0,50,b'Prism Keyboard Studio\0'); self.receive(0,10,50)
        self.send(0,52,struct.pack('<I',1)); self.receive(0,10,52)
        return self
    def close(self):
        if self.sock:
            try: self.sock.close()
            finally: self.sock=None
    def exact(self,n):
        b=bytearray()
        while len(b)<n:
            chunk=self.sock.recv(n-len(b))
            if not chunk: raise BridgeError('OpenRGB disconnected.')
            b.extend(chunk)
        return bytes(b)
    def send(self,ident,kind,data=b''):
        self.sock.sendall(struct.pack('<4sIII',b'ORGB',ident,kind,len(data))+data)
    def receive(self,ident,kind,acked=None):
        for _ in range(512):
            magic,dev,typ,n=struct.unpack('<4sIII',self.exact(16))
            if magic!=b'ORGB' or n>4*1024*1024: raise BridgeError('Invalid OpenRGB packet.')
            data=self.exact(n)
            if typ==100: self.changed=True
            if typ==10:
                if n!=8: raise BridgeError('Invalid OpenRGB acknowledgment.')
                packet,status=struct.unpack('<II',data)
                if dev==ident and packet==(acked if acked is not None else kind):
                    if status: raise BridgeError(f'OpenRGB rejected command {packet} (status {status}). Refresh keyboards.')
                    if kind==10: return data
            elif dev==ident and typ==kind: return data
        raise BridgeError('Too many unrelated OpenRGB messages.')
    def describe(self,ident):
        self.send(ident,1); return parse_controller(self.receive(ident,1),ident)
    def devices(self):
        self.send(0,0); data=self.receive(0,0); r=Reader(data); count=r.num()
        if count>512 or len(data)!=4+4*count: raise BridgeError('Invalid OpenRGB device list.')
        result=[self.describe(r.num()) for _ in range(count)]; self.changed=False; return result
    def write(self,ident,colors):
        values=b''.join(bytes((*c,0)) for c in colors)
        self.send(ident,1050,struct.pack('<IH',6+len(values),len(colors))+values)
        self.receive(ident,10,1050)
    def custom(self,ident): self.send(ident,1100); self.receive(ident,10,1100)

def resolve(devices,selected):
    matches=[d for d in devices if d.type==5 and d.identity==selected.identity and d.identity]
    if len(matches)!=1: raise BridgeError('The selected keyboard is missing or ambiguous. Refresh and select it again.')
    d=matches[0]
    if d.signature!=selected.signature: raise BridgeError('The keyboard layout changed. Refresh and select it again.')
    if not supports_direct(d): raise BridgeError('This keyboard does not expose a direct lighting mode.')
    return d

class OpenRGBKeyboard:
    """Only a selected keyboard can reach a lighting write. Never uses a global command."""
    def __init__(self,selected,port=6742):
        self.selected=selected; self.port=port; self.sdk=None; self.acks=0; self.firmware='OpenRGB SDK 6'
        self.device=None; self.started=False; self.original=None; self.static_only=static_only(selected)
    def connect(self):
        self.close(); self.sdk=SDK(self.port).connect()
        try:
            self.device=resolve(self.sdk.devices(),self.selected); self.original=list(self.device.colors); self.started=False
        except Exception: self.close(); raise
    def heartbeat(self):
        d=self.sdk.describe(self.device.id)
        if d.type!=5 or d.identity!=self.selected.identity or d.signature!=self.selected.signature: raise BridgeError('Keyboard identity changed. Select it again.')
    def write_frame(self,colors):
        if len(colors)!=len(self.device.leds): raise BridgeError('The frame does not match this keyboard.')
        self.heartbeat()
        if not self.started:
            self.sdk.custom(self.device.id); self.started=True; self.acks+=1
        self.sdk.write(self.device.id,colors); self.acks+=1
    def restore_brightness(self):
        # Restore the initial static colors, only while the original device ID still exists.
        if self.started and self.sdk and not self.static_only:
            self.heartbeat(); self.sdk.write(self.device.id,self.original); self.started=False
    def rainbow(self): raise BridgeError('Use Prism’s Rainbow wave effect, then Apply.')
    def close(self):
        if self.sdk: self.sdk.close(); self.sdk=None
        self.started=False
