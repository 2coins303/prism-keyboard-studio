from pathlib import Path
import re,json,hashlib,shutil
base=Path(__file__).parent; root=base/'upstream/openrgb'; out=base/'source'
allnames=set(); catalog={}
for file in root.rglob('*.cpp'):
    text=file.read_text(encoding='utf-8',errors='replace')
    clean=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    allnames.update(re.findall(r'REGISTER_\w*DETECTOR\w*\s*\(\s*"([^"]+)"',clean))
    if 'Controllers' not in file.parts: continue
    defs={}
    for f in file.parent.rglob('*'):
        if f.suffix in ('.h','.cpp'):
            defs.update(re.findall(r'^\s*#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+|\w+)\s*(?://.*)?$',f.read_text(encoding='utf-8',errors='replace'),re.M))
    def val(v):
        for _ in range(8):
            try:return int(v,0)
            except ValueError: v=defs.get(v,'?')
        return None
    for m in re.finditer(r'REGISTER_HID_DETECTOR\w*\s*\(\s*"([^"]+)"\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)',clean):
        name,func,vid,pid=m.groups()
        allow=(name.startswith('Razer ') and any(s in name.casefold() for s in ['blackwidow','huntsman','ornata','cynosa','deathstalker','anansi']))
        allow |= (name.startswith('Logitech ') and ('Keyboard' in func or name=='Logitech G213'))
        allow |= bool(re.match(r'Corsair K\d',name)) and 'RED' not in name and name not in ['Corsair K70 LUX']
        allow |= name.startswith('SteelSeries Apex') or name.startswith('HyperX Alloy')
        allow |= name.startswith('ASUS ') and 'Keyboard' in func
        allow |= name=='Keychron Gaming Keyboard 1'
        if name.startswith('Razer ') and any(x in name for x in ['Ultimate','2013','2014']): allow=False
        if name.startswith('Corsair ') and not any(x in name for x in ['RGB','K100']): allow=False
        if not allow: continue
        vid=val(vid); pid=val(pid)
        if vid is None or pid is None or not 0<vid<=65535 or not 0<pid<=65535: continue
        capability='Per-key RGB (layout supplied by bridge)'
        if any(s in name for s in ['G213','Cynosa Lite','Ornata V3','Deathstalker Chroma','Apex 3','K55 RGB','Apex (OG)','Apex 350']): capability='Zone lighting; limited spatial/audio detail'
        if name in ['ASUS TUF Gaming K1','ASUS TUF Gaming K5']: capability='Five-zone RGB; limited spatial/audio detail'
        if name=='Corsair K55 RGB PRO XT': capability='Per-key RGB (layout supplied by bridge)'
        if name=='Razer Anansi': capability='One lighting zone; mirrored audio'
        transport='USB; wireless modes not claimed'
        if any(s in name for s in ['2.4GHz','(Wireless)','(Receiver']): transport='2.4 GHz receiver variant'
        if 'G915' in name and '(Wired)' not in name: transport='2.4 GHz receiver variant'
        if name=='Keychron Gaming Keyboard 1':
            display='Keychron K3 V2 Optical RGB'; capability='Per-key static colors; automatic hardware saving; no streaming/audio'
        else: display=name
        source=file.relative_to(root).as_posix()
        item=dict(name=display,detector=name,vid=f'{vid:04X}',pid=f'{pid:04X}',capability=capability,connection=transport,
                  evidence='Hardware tested on this PC (direct connection)' if (vid,pid)==(0x1532,0x2a6) else 'Upstream supported; not physically tested here',
                  source='https://codeberg.org/OpenRGB/OpenRGB/src/tag/release_1.1/'+source,
                  source_line=clean[:m.start()].count('\n')+1)
        catalog[(name,vid,pid)]=item
allnames.update(['Corsair DRAM','Gigabyte RGB Fusion 2 USB','Gigabyte RGB Fusion 2 SMBus','Patriot Viper','Patriot Viper Steel'])
data=dict(version='OpenRGB 1.1 / SDK 6',source='https://openrgb.org/releases.html',models=sorted(catalog.values(),key=lambda x:x['name'].casefold()),detectors=sorted(allnames))
(out/'compatibility.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
bridge=base/'managed-bridge'; bridge.mkdir(exist_ok=True)
for f in (base/'bridge/OpenRGB Windows 64-bit').iterdir():
    if f.suffix.lower()=='.bin': continue # No PawnIO modules, including all SMBus/LPC modules.
    if f.is_dir():shutil.copytree(f,bridge/f.name,dirs_exist_ok=True)
    else:shutil.copy2(f,bridge/f.name)
manifest={f.relative_to(bridge).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in bridge.rglob('*') if f.is_file()}
(out/'bridge-manifest.json').write_text(json.dumps(manifest,indent=2))
print('Catalog',len(catalog),'USB model variants;',len(allnames),'detectors; bridge files',len(manifest))
print('\n'.join(x['name']+' '+x['vid']+':'+x['pid'] for x in data['models']))
