"""Device layout is separate from effects and profile data."""
from dataclasses import dataclass
import copy
import numpy as np
from model import Key,KEYS,render_colors,rgb

@dataclass
class Layout:
    name: str
    identity: str
    keys: list
    width: float
    height: float
    spatial: bool
    led_ids: list
    note: str

DIRECT_LAYOUT=Layout('Huntsman V3 Pro / Full size','huntsman-1532-02a6',KEYS,23,6.4,True,[],
                     'Per-key RGB · direct USB · hardware tested here')

def led_id(name,index):
    # The device signature protects this index/name pair against reordered LEDs.
    return f'led:{index}:{name}'

def bridge_layout(d,mapping=None):
    ids=[led_id(name,i) for i,name in enumerate(d.leds)]
    points={}; offset=0; width=0; height=0
    for z in d.zones:
        if z.matrix:
            # OpenRGB's zone matrix entries are LOCAL to that zone.
            for y,row in enumerate(z.matrix):
                for x,index in enumerate(row):
                    if 0<=index<z.count:
                        idx=offset+index
                        if idx<len(ids) and idx not in points: points[idx]=(x,y)
            width=max(width,len(z.matrix[0])); height=max(height,len(z.matrix))
        offset+=z.count
    custom=mapping or {}
    if custom:
        points={i:tuple(custom[k]) for i,k in enumerate(ids) if k in custom}
        width=max((p[0]+1 for p in points.values()),default=1); height=max((p[1]+1 for p in points.values()),default=1)
    visible=[i for i,name in enumerate(d.leds) if name.strip() or i in points]
    if not visible: visible=list(range(len(ids)))
    spatial=bool(points) and all(i in points for i in visible)
    keys=[]
    if spatial:
        for i in visible:
            name=d.leds[i]
            x,y=points[i]; lbl=name.removeprefix('Key: ').removeprefix('Key ').replace('Keyboard ','')
            aliases={'Escape':'Esc','Print Screen':'PrtSc','Scroll Lock':'ScrLk','Page Up':'PgUp','Page Down':'PgDn','Caps Lock':'Caps','Backspace':'Back','Left Shift':'Shift','Right Shift':'Shift','Left Control':'Ctrl','Right Control':'Ctrl','Left Windows':'Win','Right Windows':'Win','Left Alt':'Alt','Right Alt':'Alt','Number Lock':'Num','Application':'Menu','Volume':'Vol'}
            lbl=aliases.get(lbl,lbl).replace('Number Pad ','N').replace('Numpad ','N').replace('Keypad ','N')
            keys.append(Key(ids[i],lbl,x,y,1,1,int(y),int(x),'Keys'))
        note=(f'{len(visible)} lighting zones · bridge positions · limited audio detail' if len(visible)<=16 else f'Per-key RGB · {len(visible)} visible lights · bridge matrix') if not custom else 'Your saved physical layout'
    else:
        # List order is explicitly NOT interpreted as physical position.
        width=12; height=max(1,(len(ids)+11)//12)
        for i,name in enumerate(d.leds): keys.append(Key(ids[i],name.removeprefix('Key: '),i%12,i//12,1,1,i//12,i%12,'Unmapped'))
        note=f'{len(ids)} lighting addresses · layout needs mapping · audio is mirrored'
    if len(ids)==1: note='One lighting zone · all colors/audio are mirrored'
    return Layout(d.name,d.identity+':'+d.signature,keys,width,height,spatial,ids,note)

def painted(profile,layout):
    if layout.identity==DIRECT_LAYOUT.identity: return profile['overrides']
    return profile.setdefault('device_overrides',{}).setdefault(layout.identity,{})

def render_layout(profile,t,levels,layout):
    p=copy.deepcopy(profile); p['overrides']=painted(profile,layout)
    if layout.spatial:
        return render_colors(p,t,levels,layout.keys,layout.width,layout.height)
    # Without physical coordinates, use a uniform response instead of false stereo.
    anchor=Key('uniform','',0,0,1,1,0,0)
    if p['effect']=='Audio':
        l=np.zeros((2,6)) if levels is None else levels
        weights=l.max(axis=0); total=weights.sum()
        c=sum((rgb(c)*weights[i] for i,c in enumerate(p['audio']['colors'])),np.zeros(3))/max(1,total)
        color=tuple(int(v) for v in np.clip(c*weights.max()*p['brightness']/100,0,255))
    else:
        color=render_colors(p,t,levels,[anchor],1,1)['uniform']
    result={k.id:color for k in layout.keys}
    for k,col in p['overrides'].items():
        if k in result: result[k]=tuple(int(v) for v in rgb(col)*p['brightness']/100)
    return result

def validate_mapping(mapping,layout):
    if set(mapping)!={k.id for k in layout.keys}: raise ValueError('Map every visible lighting address exactly once.')
    seen=set(); result={}
    for key,coords in mapping.items():
        if not isinstance(coords,(list,tuple)) or len(coords)!=2: raise ValueError('Use [column, row] for every address.')
        x,y=coords
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=100 for v in coords): raise ValueError('Coordinates must be numbers from 0 to 100.')
        if (x,y) in seen: raise ValueError('Two addresses cannot share one position.')
        seen.add((x,y)); result[key]=[x,y]
    return result
