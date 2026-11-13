"""Prism 2.1 pattern recipes and deterministic spatial effects. GPL-2.0-or-later."""
import colorsys
import math

# name, category, description, suggested palette, directional, palette editable
RECIPES = [
 ('Gradient','Static','A smooth blend across the keyboard.','Neon nights',True,True),
 ('Rainbow wave','Waves and motion','A moving ribbon of the full color spectrum.','Neon nights',True,False),
 ('Solid','Static','One clean color on every light.','Cyber mint',False,True),
 ('Breathing','Glow and ambience','Your palette slowly fades in and out.','Violet hour',False,True),
 ('Color flow','Waves and motion','Soft palette colors roll across the keys.','Cyber mint',True,True),
 ('Sparkle','Sparkles and particles','Bright individual lights over a dim palette.','Arctic',False,True),
 ('Audio','Audio','Bass through treble respond to your selected audio source.','Neon nights',False,False),
 ('Rainbow cycle','Glow and ambience','The whole keyboard smoothly cycles through the spectrum.','Neon nights',False,False),
 ('Rainbow spiral','Waves and motion','A rainbow curls around the center of your keyboard.','Neon nights',True,False),
 ('Aurora','Glow and ambience','Soft curtains of color drift above a dark background.','Aurora greens',False,True),
 ('Ocean waves','Glow and ambience','Layered waves wash across the keys like a moonlit sea.','Deep ocean',False,True),
 ('Fire','Glow and ambience','Warm, flickering plumes rise from the bottom row.','Solar flare',False,True),
 ('Lava lamp','Glow and ambience','Glowing blobs slowly float and merge.','Molten',False,True),
 ('Candy stripes','Waves and motion','Bands of your three colors slide across the keyboard.','Bubblegum',True,True),
 ('Color chase','Waves and motion','Three bright runners chase each other across the keys.','Retro arcade',True,True),
 ('Comet','Waves and motion','A bright head sweeps by with a long, fading tail.','Arctic',True,True),
 ('Scanner','Waves and motion','A soft beam sweeps out and returns.','Laser red',True,True),
 ('Ripple','Waves and motion','Automatic rings expand from the center in a repeating loop.','Deep ocean',True,True),
 ('Rain','Sparkles and particles','Independent trails of light fall across the keyboard.','Matrix green',True,True),
 ('Starfield','Sparkles and particles','Scattered stars brighten and fade against the dark.','Starlight',False,True),
 ('Twinkle','Sparkles and particles','A dense, gentle shimmer of independent lights.','Champagne',False,True),
 ('Fireflies','Sparkles and particles','Small glowing lights wander softly over the keys.','Aurora greens',False,True),
 ('Heartbeat','Glow and ambience','A gentle double pulse runs through your palette.','Laser red',False,True),
 ('Sunset drift','Glow and ambience','A warm horizon slowly moves through your colors.','Sunset',False,True),
 ('Plasma','Glow and ambience','Intersecting color waves form a moving, liquid texture.','Retro arcade',True,True),
 ('Galaxy','Glow and ambience','Rotating arms of color glow around a bright core.','Nebula',False,True),
 ('Radar','Waves and motion','A rotating beam sweeps around a dim circular field.','Matrix green',True,True),
 ('Pinwheel','Waves and motion','Three soft palette blades turn around the center.','Bubblegum',True,True),
 ('Checkerboard','Static','Alternating blocks of your first two palette colors.','Retro arcade',False,True),
 ('Diagonal bands','Static','Diagonal ribbons blend all three of your colors.','Sunset',True,True),
 ('Confetti','Sparkles and particles','Colored flecks gently appear and dissolve.','Bubblegum',False,True),
]
PATTERNS={r[0]:dict(category=r[1],description=r[2],palette=r[3],directional=r[4],uses_palette=r[5]) for r in RECIPES}
EXTRA_PATTERNS=[r[0] for r in RECIPES[7:]]
STATIC_PATTERNS={'Gradient','Solid','Checkerboard','Diagonal bands'}
DIRECTIONAL={name for name,info in PATTERNS.items() if info['directional']}
NEW_PALETTES={
 'Aurora greens':['#072846','#39fca1','#a87dff'],
 'Deep ocean':['#061d57','#007ea7','#69f5eb'],
 'Molten':['#470d65','#f34836','#ffd55e'],
 'Bubblegum':['#ff5caf','#a879ff','#67f0ff'],
 'Retro arcade':['#ff3b8d','#29ffe1','#ffe561'],
 'Laser red':['#ff254b','#ff6b39','#ffe9ba'],
 'Matrix green':['#082417','#31ef78','#d1ff85'],
 'Starlight':['#28396c','#95bcff','#fff4d6'],
 'Champagne':['#634b83','#ffce8d','#fff6dc'],
 'Sunset':['#5d2a92','#f25c79','#ffc76a'],
 'Nebula':['#181c61','#9e4dff','#ff73bd'],
}

TAU=2*math.pi
def clamp(x):return max(0.,min(1.,x))
def frac(x):return x-math.floor(x)
def hash01(n):return frac(math.sin(n*12.9898+78.233)*43758.5453)
def blend(a,b,f):return tuple(a[i]+(b[i]-a[i])*f for i in range(3))
def ramp(p,x):
    x=clamp(x)*2;i=min(1,int(x));return blend(p[i],p[i+1],x-i)
def cycle(p,x):
    x=frac(x)*3;i=int(x);return blend(p[i],p[(i+1)%3],x-i)
def shade(c,v):return tuple(x*clamp(v) for x in c)
def glow(distance,width):return math.exp(-.5*(distance/width)**2)
def wrapped_distance(a,b):return (a-b+.5)%1-.5
def noise(x,y,t):
    return .5+(math.sin(x*5.7+y*3.1+t*.7)+math.sin(x*11.3-y*7.1-t*1.1)+math.sin(x*2.1+y*13.7+t*.4))/6

def pattern_color(name,x,y,t,direction,p):
    """Coordinates are normalized from each device's physical matrix.

    Frame-independent hashes keep sparkles deterministic across refresh rates;
    particles fade continuously instead of choosing random LEDs on each frame.
    """
    phase=t*.19; sign=-1 if direction in ('Left','Up') else 1
    vertical=direction in ('Up','Down');axis=y if vertical else x
    u=axis if sign>0 else 1-axis
    dx=(x-.5)*1.6;dy=y-.5;r=math.hypot(dx,dy);angle=math.atan2(dy,dx)/TAU
    seed=math.floor(x*181)*53+math.floor(y*89)*97
    if name=='Rainbow cycle':return tuple(c*255 for c in colorsys.hsv_to_rgb(frac(phase*.45),.86,1))
    if name=='Rainbow spiral':return tuple(c*255 for c in colorsys.hsv_to_rgb(frac(angle+r*.9-sign*phase*.5),.88,1))
    if name=='Aurora':
        curtain=.37+.22*math.sin(x*5+phase*1.5)+.13*math.sin(x*12-phase*1.7)
        strength=.12+.75*glow(y-curtain,.18)+.13*noise(x,y,phase)
        return shade(cycle(p,x*.45+phase*.06+y*.3),strength)
    if name=='Ocean waves':
        waves=(math.sin(x*10+y*3-phase*2.3)+math.sin(x*5-y*9+phase*1.5)+2)/4
        return shade(ramp(p,waves),.3+.7*waves)
    if name=='Fire':
        heat=clamp(y*.73+noise(x*1.7,y-phase*.7,phase)*.63-.21)
        return shade(ramp(p,heat),.08+.92*heat**1.2)
    if name=='Lava lamp':
        field=0.
        for i in range(4):
            cx=.5+.38*math.sin(phase*(.37+i*.09)+i*2.1)
            cy=.5+.4*math.cos(phase*(.51+i*.08)+i*1.7)
            field+=glow(math.hypot((x-cx)*1.5,y-cy),.22)
        return shade(ramp(p,field*.48),.1+.75*clamp(field))
    if name=='Candy stripes':return cycle(p,axis*2.1-sign*phase*.55)
    if name=='Color chase':
        values=[glow(wrapped_distance(u,phase*.5+i/3),.045) for i in range(3)]
        return tuple(sum(p[j][c]*values[j] for j in range(3))*.9+p[0][c]*.04 for c in range(3))
    if name=='Comet':
        head=frac(phase*.6);behind=frac(head-u)
        light=max(glow(wrapped_distance(u,head),.026),math.exp(-behind/.13)*.75)
        return shade(ramp(p,clamp(1-behind*4)),.025+.975*light)
    if name=='Scanner':
        head=.5-.46*math.cos(phase*2.4)
        return shade(ramp(p,u),.035+.965*glow(u-head,.075))
    if name=='Ripple':
        wave=.5+.5*math.cos(TAU*(r*2.7-sign*phase*.6))
        return shade(cycle(p,r*.8-sign*phase*.12),.035+.965*wave**5)
    if name=='Rain':
        # Down/right follows the chosen axis; each perpendicular lane has its own trail.
        lane=math.floor((x if vertical else y)*18);v=y if vertical else x
        if direction in ('Up','Left'):v=1-v
        head=frac(phase*(.43+hash01(lane)*.5)+hash01(lane+19))
        tail=frac(head-v);strength=math.exp(-tail/.1)
        return shade(ramp(p,1-tail*3),.02+.98*strength)
    if name=='Starfield':
        star=hash01(seed)>.67;wave=.5+.5*math.sin(phase*(1+hash01(seed+1)*2)+hash01(seed+2)*TAU)
        return shade(ramp(p,hash01(seed+3)),.018+(wave**4*.98 if star else 0))
    if name=='Twinkle':
        wave=.5+.5*math.sin(phase*(1.5+hash01(seed)*2.5)+hash01(seed+1)*TAU)
        return shade(ramp(p,hash01(seed+2)),.18+.82*wave**2)
    if name=='Fireflies':
        intensity=0.;hue=0.
        for i in range(7):
            cx=.5+.45*math.sin(phase*(.25+i*.021)+i*2.4)
            cy=.5+.42*math.sin(phase*(.4+i*.015)+i*3.7)
            g=glow(math.hypot((x-cx)*1.6,y-cy),.075)*(.55+.45*math.sin(phase*.7+i)**2)
            if g>intensity:intensity=g;hue=i/6
        return shade(ramp(p,hue),.025+.975*intensity)
    if name=='Heartbeat':
        beat=frac(phase*.55);pulse=glow(beat-.20,.055)+.62*glow(beat-.39,.07)
        return shade(ramp(p,x),.1+.86*pulse)
    if name=='Sunset drift':
        horizon=.5+.23*math.sin(phase*.65);a=clamp(y-horizon+.5)
        return shade(ramp(p,a),.75+.25*math.sin(x*3+phase*.3)**2)
    if name=='Plasma':
        field=(math.sin(x*7+sign*phase*1.4)+math.sin(y*8-phase*.9)+math.sin((x+y)*6+phase*.7)+math.cos(r*11-phase*1.8)+4)/8
        return cycle(p,field+phase*.035)
    if name=='Galaxy':
        arm=(.5+.5*math.cos((angle*2+r*1.7-phase*.12)*TAU))**4
        field=.08+.74*arm*math.exp(-r*1.1)+.36*glow(r,.12)
        return shade(cycle(p,r*.8+angle*.22+phase*.02),field)
    if name=='Radar':
        behind=frac(sign*phase*.25-angle);beam=math.exp(-behind/.075)
        rings=(.5+.5*math.cos(r*28))**14*.08
        return shade(ramp(p,clamp(r)),.02+.9*beam+rings)
    if name=='Pinwheel':return shade(cycle(p,angle*3-sign*phase*.5),.55+.45*clamp(r*2))
    if name=='Checkerboard':return p[(math.floor(x*12)+math.floor(y*6))%2]
    if name=='Diagonal bands':return cycle(p,(x+sign*y*.55)*2)
    if name=='Confetti':
        time_cell=math.floor(phase*.4);f=frac(phase*.4);f=f*f*(3-2*f)
        def particle(cell):
            hit=hash01(seed+cell*137)>.7
            return shade(cycle(p,hash01(seed+cell*71+5)),.92 if hit else .035)
        return blend(particle(time_cell),particle(time_cell+1),f)
    raise ValueError('Unknown pattern: '+name)
