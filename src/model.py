"""Prism Keyboard Studio. GPL-2.0-or-later. Pure profiles, layout and effects."""
from __future__ import annotations
import colorsys
import copy
import json
import math
import os
import re
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from patterns import EXTRA_PATTERNS,STATIC_PATTERNS,NEW_PALETTES,pattern_color

APP_NAME = 'Prism Keyboard Studio'
VERSION = '2.5.1'
MAX_SPEED = 1000
EFFECTS = ['Gradient', 'Rainbow wave', 'Solid', 'Breathing', 'Color flow', 'Sparkle', 'Audio']
EFFECTS += EXTRA_PATTERNS
ANIMATED = set(EFFECTS)-STATIC_PATTERNS
BANDS = [(25, 140, 'Bass'), (140, 400, 'Low mids'), (400, 1000, 'Mids'),
         (1000, 2800, 'Presence'), (2800, 6500, 'Treble'), (6500, 20000, 'Air')]
BAND_COLORS = ['#ff3e7f', '#ff8a3d', '#ffe45e', '#7bff82', '#35d8ff', '#a473ff']
PALETTES = {
    'Neon nights': ['#9b4dff', '#fa368d', '#27e3ff'],
    'Cyber mint': ['#05f7a1', '#23d1ff', '#4364ff'],
    'Solar flare': ['#ff3e64', '#ff882f', '#ffe567'],
    'Arctic': ['#3375ff', '#43d7ff', '#daffff'],
    'Violet hour': ['#4524c4', '#a663ff', '#ff62cf'],
    'Toxic': ['#2eff36', '#e4ff38', '#00cf97'],
}

PALETTES.update(NEW_PALETTES)

@dataclass(frozen=True)
class Key:
    id: str
    label: str
    x: float
    y: float
    w: float
    h: float
    row: int
    col: int
    group: str = 'Typing'

def make_layout():
    # ANSI full size. Matrix from OpenRazer keymap, with ANSI backslash and
    # Huntsman V3 Pro media zones from OpenRGB's device-specific layout.
    keys = []
    def add(id, label, x, y, row, col, w=1, h=1, group='Typing'):
        keys.append(Key(id, label, x, y, w, h, row, col, group))
    add('ESC','Esc',0,0,0,1,group='Function')
    for i in range(12): add(f'F{i+1}',f'F{i+1}',2+i+(i//4)*.5,0,0,3+i,group='Function')
    for j,(id,lbl) in enumerate([('PRTSCR','PrtSc'),('SCRLK','ScrLk'),('PAUSE','Pause')]):
        add(id,lbl,15.5+j,0,0,15+j,group='Navigation')
    add('MEDIA','Media',19,.05,0,18,w=1.65,h=.8,group='Media')
    add('DIAL','Dial',21,.0,0,20,w=1,h=1,group='Media')
    for i,lbl in enumerate('`1234567890-='): add('BACKTICK' if i==0 else lbl,lbl,i,1.4,1,1+i)
    add('BACKSPACE','Backspace',13,1.4,1,14,w=2)
    add('TAB','Tab',0,2.4,2,1,w=1.5)
    for i,lbl in enumerate('QWERTYUIOP[]'): add(lbl,lbl,1.5+i,2.4,2,2+i)
    add('BACKSLASH','\\',13.5,2.4,2,14,w=1.5)
    add('CAPSLK','Caps',0,3.4,3,1,w=1.75)
    for i,lbl in enumerate("ASDFGHJKL;'"): add(lbl,lbl,1.75+i,3.4,3,2+i)
    add('RETURN','Enter',12.75,3.4,3,14,w=2.25)
    add('LEFTSHIFT','Shift',0,4.4,4,1,w=2.25)
    for i,lbl in enumerate('ZXCVBNM,./'): add(lbl,lbl,2.25+i,4.4,4,3+i)
    add('RIGHTSHIFT','Shift',12.25,4.4,4,14,w=2.75)
    for id,lbl,x,w,c in [('LEFTCTRL','Ctrl',0,1.25,1),('SUPER','Win',1.25,1.25,2),('LEFTALT','Alt',2.5,1.25,3),
                        ('SPACE','Space',3.75,6.25,7),('RIGHTALT','Alt',10,1.25,11),('FN','Fn',11.25,1.25,12),
                        ('CTXMENU','Menu',12.5,1.25,13),('RIGHTCTRL','Ctrl',13.75,1.25,14)]:
        add(id,lbl,x,5.4,5,c,w=w)
    for r,y,items in [(1,1.4,[('INS','Ins'),('HOME','Home'),('PAGEUP','PgUp')]),
                      (2,2.4,[('DELETE','Del'),('END','End'),('PAGEDOWN','PgDn')])]:
        for j,(id,lbl) in enumerate(items): add(id,lbl,15.5+j,y,r,15+j,group='Navigation')
    for id,lbl,x,y,r,c in [('UP','↑',16.5,4.4,4,16),('LEFT','←',15.5,5.4,5,15),
                          ('DOWN','↓',16.5,5.4,5,16),('RIGHT','→',17.5,5.4,5,17)]:
        add(id,lbl,x,y,r,c,group='Arrows')
    for j,(id,lbl) in enumerate([('NUMLK','Num'),('NPDIV','/'),('NPMUL','*'),('NPSUB','−')]):
        add(id,lbl,19+j,1.4,1,18+j,group='Numpad')
    for r,nums in [(2,'789'),(3,'456'),(4,'123')]:
        for j,n in enumerate(nums): add('NP'+n,n,19+j,r+.4,r,18+j,group='Numpad')
    add('NPPLUS','+',22,2.4,2,21,h=2,group='Numpad')
    add('NPENTER','Enter',22,4.4,4,21,h=2,group='Numpad')
    add('NP0','0',19,5.4,5,19,w=2,group='Numpad')
    add('NPPERIOD','.',21,5.4,5,20,group='Numpad')
    return keys

KEYS = make_layout()
KEY_BY_ID = {k.id:k for k in KEYS}

def new_profile(name='Neon nights', effect='Gradient', palette=None):
    return dict(id=uuid.uuid4().hex, name=name, effect=effect,
                palette=list(palette or PALETTES['Neon nights']), brightness=85,
                speed=45, direction='Right', overrides={}, device_overrides={},
                audio=dict(source='', gain=12, smoothing=65, channel_mode='Auto',
                           colors=list(BAND_COLORS)))

def defaults():
    return [new_profile(), new_profile('Rainbow rush','Rainbow wave'),
            new_profile('Arctic glow','Breathing',PALETTES['Arctic']),
            new_profile('Audio arena','Audio')]

def color_ok(x): return isinstance(x,str) and bool(re.fullmatch(r'#[0-9a-fA-F]{6}',x))

def validate_profile(obj, new_id=False):
    if not isinstance(obj,dict): raise ValueError('The profile must be a JSON object.')
    p=new_profile()
    name=obj.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>60: raise ValueError('Profile names must contain 1–60 characters.')
    p['name']=name.strip()
    ident=obj.get('id','')
    if not new_id and isinstance(ident,str) and re.fullmatch(r'[a-f0-9]{32}',ident): p['id']=ident
    if obj.get('effect') not in EFFECTS: raise ValueError('This profile uses an unknown lighting effect.')
    p['effect']=obj['effect']
    pal=obj.get('palette')
    if not isinstance(pal,list) or len(pal)!=3 or not all(color_ok(x) for x in pal): raise ValueError('The palette must have three hex colors.')
    p['palette']=pal.copy()
    def number(container,key,low,high,default):
        n=container.get(key,default)
        if isinstance(n,bool) or not isinstance(n,(float,int)) or not math.isfinite(n) or not low<=n<=high:
            raise ValueError(f'{key} must be between {low} and {high}.')
        return n
    p['brightness']=number(obj,'brightness',0,100,p['brightness'])
    p['speed']=number(obj,'speed',0,MAX_SPEED,p['speed'])
    if obj.get('direction','Right') not in ['Right','Left','Down','Up']: raise ValueError('Unknown direction.')
    p['direction']=obj.get('direction','Right')
    overrides=obj.get('overrides',{})
    if not isinstance(overrides,dict) or len(overrides)>len(KEYS): raise ValueError('Invalid key colors.')
    if any(k not in KEY_BY_ID or not color_ok(v) for k,v in overrides.items()): raise ValueError('Unknown key or invalid key color.')
    p['overrides']=overrides.copy()
    devices=obj.get('device_overrides',{})
    if not isinstance(devices,dict) or len(devices)>100: raise ValueError('Invalid device colors.')
    for identity,values in devices.items():
        if not isinstance(identity,str) or len(identity)>100 or not isinstance(values,dict) or len(values)>2048: raise ValueError('Invalid device colors.')
        if any(not isinstance(k,str) or len(k)>512 or not color_ok(v) for k,v in values.items()): raise ValueError('Invalid device key color.')
    p['device_overrides']=copy.deepcopy(devices)
    a=obj.get('audio',{})
    if not isinstance(a,dict): raise ValueError('Invalid audio settings.')
    p['audio']['gain']=number(a,'gain',-12,36,12)
    p['audio']['smoothing']=number(a,'smoothing',0,95,65)
    if a.get('channel_mode','Auto') not in ['Auto','Mono mirror']: raise ValueError('Unknown audio channel mode.')
    p['audio']['channel_mode']=a.get('channel_mode','Auto')
    source=a.get('source','')
    if not isinstance(source,str) or len(source)>512: raise ValueError('Invalid audio source.')
    p['audio']['source']=source
    colors=a.get('colors',BAND_COLORS)
    if not isinstance(colors,list) or len(colors)!=6 or not all(color_ok(c) for c in colors): raise ValueError('Audio needs six frequency colors.')
    p['audio']['colors']=colors.copy()
    return p

def atomic_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,indent=2,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

class ProfileStore:
    def __init__(self,directory):
        self.directory=Path(directory); self.path=self.directory/'profiles.json'; self.warning=''
        self.profiles=defaults(); self.last=self.profiles[0]['id']
        self.drafts={}
        if self.path.exists():
            try:
                raw=json.loads(self.path.read_text(encoding='utf-8'))
                if raw.get('version')!=1 or not isinstance(raw.get('profiles'),list) or not 1<=len(raw['profiles'])<=200:
                    raise ValueError('Unsupported profile library format.')
                loaded=[validate_profile(x) for x in raw['profiles']]
                if len({p['id'] for p in loaded})!=len(loaded): raise ValueError('Duplicate profile identifiers.')
                self.profiles=loaded; self.last=raw.get('last',loaded[0]['id'])
                if self.last not in {p['id'] for p in loaded}: self.last=loaded[0]['id']
                for ident,draft in raw.get('drafts',{}).items():
                    if ident in {p['id'] for p in loaded}: self.drafts[ident]=validate_profile(draft)
            except (ValueError,TypeError,KeyError,AttributeError,OSError) as e:
                backup=self.path.with_name(f'profiles.recovery-{time.time_ns()}.json')
                # Keep the unreadable original before any replacement is permitted.
                backup.write_bytes(self.path.read_bytes())
                self.profiles=defaults(); self.last=self.profiles[0]['id']; self.drafts={}
                self.warning=f'Your previous library could not be read. A recovery copy was kept at {backup}. {e}'
    def get(self,ident=None): return copy.deepcopy(next(p for p in self.profiles if p['id']==(ident or self.last)))
    def save(self):
        atomic_json(self.path,dict(version=1,last=self.last,profiles=self.profiles,drafts=self.drafts))
    def commit(self,p):
        p=validate_profile(p)
        for i,old in enumerate(self.profiles):
            if old['id']==p['id']: self.profiles[i]=copy.deepcopy(p); break
        else:
            if len(self.profiles)>=200: raise ValueError('The library can hold up to 200 profiles.')
            self.profiles.append(copy.deepcopy(p))
        self.drafts.pop(p['id'],None); self.last=p['id']; self.save()
    def import_file(self,path):
        path=Path(path)
        if path.stat().st_size>1024*1024: raise ValueError('Choose a profile smaller than 1 MB.')
        raw=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(raw,dict) or raw.get('format')!='prism-profile' or raw.get('version')!=1:
            raise ValueError('Choose a Prism profile exported by this app.')
        p=validate_profile(raw.get('profile'),new_id=True); self.commit(p); return p
    def export_file(self,path,p):
        atomic_json(path,dict(format='prism-profile',version=1,profile=validate_profile(p)))

def rgb(h): return np.array([int(h[i:i+2],16) for i in (1,3,5)],dtype=float)

def mix_palette(palette,position):
    pos=max(0.,min(1.,position))*(len(palette)-1)
    i=min(int(pos),len(palette)-2); f=pos-i
    return rgb(palette[i])*(1-f)+rgb(palette[i+1])*f

class AudioAnalyzer:
    """FFT bands from a short in-memory window; no audio is written to disk."""
    def __init__(self): self.levels=np.zeros((2,6)); self.meters=np.zeros(2)
    def reset(self): self.levels.fill(0); self.meters.fill(0)
    def analyze(self,samples,rate,gain=12,smoothing=65,mono=False,dt=.04):
        x=np.asarray(samples,dtype=float)
        if x.ndim==1: x=x[:,None]
        if x.ndim!=2 or x.shape[1]<1: raise ValueError('Audio needs one or more channels.')
        x=np.nan_to_num(x[-4096:],nan=0.,posinf=0.,neginf=0.)
        if len(x)<128: x=np.pad(x,((128-len(x),0),(0,0)))
        if x.shape[1]==1: x=np.repeat(x,2,axis=1)
        else: x=x[:,:2]
        if mono: x=np.repeat(x.mean(axis=1,keepdims=True),2,axis=1)
        rms=np.sqrt(np.mean(x*x,axis=0))
        self.meters=np.clip((20*np.log10(rms+1e-9)+60+gain)/60,0,1)
        x=x-x.mean(axis=0,keepdims=True)
        window=np.hanning(len(x)); freqs=np.fft.rfftfreq(len(x),1/rate)
        mag=np.abs(np.fft.rfft(x*window[:,None],axis=0))/(window.sum()/2)
        energies=np.zeros((2,6))
        for i,(lo,hi,_) in enumerate(BANDS):
            section=mag[(freqs>=lo)&(freqs<min(hi,rate/2)),:]
            if len(section): energies[:,i]=np.sqrt(np.sum(section*section,axis=0))
        levels=np.clip((20*np.log10(energies+1e-9)+55+gain)/55,0,1)
        # Fast attack, adjustable decay. dt makes smoothing independent of FPS.
        decay=.03+(smoothing/100.)**2*1.2
        alpha=1-np.exp(-max(.001,dt)/np.where(levels>self.levels,.025,decay))
        self.levels += (levels-self.levels)*alpha
        return self.levels.copy()

def animation_rate(speed):
    """Keep the original low range exact; extend the upper range to 10x old max."""
    if speed<=100:return .12+speed/45
    return (.12+100/45)*(speed/100)

def render_colors(profile,t,levels=None,keys=None,width=23,height=6.4):
    pal=profile['palette']; effect=profile['effect']; speed=animation_rate(profile['speed'])
    palette_rgb=[tuple(rgb(c)) for c in pal]
    result={}
    for k in (KEYS if keys is None else keys):
        x=(k.x+k.w/2)/width; y=(k.y+k.h/2)/height
        axis=y if profile['direction'] in ('Up','Down') else x
        sign=-1 if profile['direction'] in ('Left','Up') else 1
        if effect=='Audio':
            left=x<.5; side=0 if left else 1; local=x*2 if left else (x-.5)*2
            band=min(5,int(local*6)); level=float(levels[side,band]) if levels is not None else 0.
            # Six bars in each physical half. No shared normalization across channels.
            lit=max(0.,min(1.,(level-(1-y)) * 6 + .5)) * level
            col=rgb(profile['audio']['colors'][band])*lit
        elif effect in EXTRA_PATTERNS: col=np.array(pattern_color(effect,x,y,t*speed,profile['direction'],palette_rgb))
        elif effect=='Solid': col=rgb(pal[0])
        elif effect=='Rainbow wave': col=np.array(colorsys.hsv_to_rgb((axis-sign*t*speed*.12)%1,.88,1))*255
        elif effect=='Breathing': col=mix_palette(pal,axis)*(.08+.92*(.5+.5*math.sin(t*speed*2)))
        elif effect=='Color flow': col=mix_palette(pal,.5+.5*math.sin(axis*5-sign*t*speed))
        elif effect=='Sparkle':
            seed=k.row*31+k.col*17
            glow=max(0.,math.sin(t*speed*(1+(seed%7)/5)+seed))**12
            col=mix_palette(pal,(seed%23)/22)*(.06+.94*glow)
        else: col=mix_palette(pal,1-axis if sign<0 else axis)
        if k.id in profile['overrides']: col=rgb(profile['overrides'][k.id])
        result[k.id]=tuple(int(v) for v in np.clip(col*profile['brightness']/100,0,255))
    return result

def matrix_frame(colors):
    frame=np.zeros((6,22,3),dtype=np.uint8)
    for k in KEYS: frame[k.row,k.col]=colors[k.id]
    return frame.tobytes()
