import copy,json,socket,struct,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace as N
import numpy as np
from bridge import SDK,BridgeError,parse_controller,identity,signature,resolve,OpenRGBKeyboard
from layouts import bridge_layout,render_layout,painted,validate_mapping,DIRECT_LAYOUT
from model import new_profile,ProfileStore,validate_profile
from managed_bridge import catalog

def fixture(name='Test keyboard',width=14,height=6,typ=5,matrix=True,serial='ONE'):
    names=[f'Key: {i}' for i in range(width*height)]
    zone=N(name='Keyboard',count=len(names),matrix=[[y*width+x for x in range(width)] for y in range(height)] if matrix else None)
    d=N(id=27,name=name,type=typ,vendor='Fixture',description='Fixture only',version='1',serial=serial,location='USB: fixture',
        leds=names,zones=[zone],modes=[N(name='Direct',flags=0)],colors=[(0,0,0)]*len(names),flags=0)
    d.identity=identity(d);d.signature=signature(d);return d

def st(value,wide=False):
    b=value.encode()+b'\0';return struct.pack('<I' if wide else '<H',len(b))+b
def matrix_data(m):
    if m is None:return b'\0\0'
    b=struct.pack('<II',len(m),len(m[0]))+b''.join(struct.pack('<I',x) for row in m for x in row)
    return struct.pack('<H',len(b))+b
def packet_data(d):
    b=struct.pack('<I',d.type)+st(d.name)+b''.join(st(x) for x in [d.vendor,d.description,d.version,d.serial,d.location])
    b+=struct.pack('<Hi',1,0)+st('Direct')+struct.pack('<11IH',*([32]+[0]*9+[1]),0)
    b+=struct.pack('<H',len(d.zones))
    for z in d.zones:
        b+=st(z.name)+struct.pack('<4I',2 if z.matrix else 1,z.count,z.count,z.count)+matrix_data(z.matrix)
        b+=struct.pack('<HIIH',0,0,0,0)+st('')
    b+=struct.pack('<H',len(d.leds))+b''.join(st(x) for x in d.leds)
    b+=struct.pack('<H',len(d.colors))+b''.join(bytes((*x,0)) for x in d.colors)
    b+=struct.pack('<HI',0,0)+st('')+st('',True)
    return struct.pack('<I',len(b)+4)+b

class FixtureServer:
    def __init__(self):
        self.devices=[fixture(),fixture('Mouse',3,1,typ=6,serial='MOUSE')];self.writes=[]
        self.sock=socket.socket();self.sock.bind(('127.0.0.1',0));self.sock.listen();self.port=self.sock.getsockname()[1]
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        conn,_=self.sock.accept()
        def exact(n):
            b=b''
            while len(b)<n:
                c=conn.recv(n-len(b))
                if not c:raise EOFError
                b+=c
            return b
        def reply(dev,typ,data):
            raw=struct.pack('<4sIII',b'ORGB',dev,typ,len(data))+data
            # Deliberately fragmented headers exercise TCP stream correctness.
            conn.sendall(raw[:3]);conn.sendall(raw[3:11]);conn.sendall(raw[11:])
        try:
            while True:
                _,dev,typ,n=struct.unpack('<4sIII',exact(16));data=exact(n)
                if typ==40:reply(0,40,struct.pack('<I',6))
                elif typ in (50,52):reply(dev,10,struct.pack('<II',typ,0))
                elif typ==0:reply(0,0,struct.pack('<III',2,27,91))
                elif typ==1:
                    d=self.devices[0 if dev==27 else 1];reply(dev,1,packet_data(d))
                elif typ in (1050,1100):self.writes.append((dev,typ,data));reply(dev,10,struct.pack('<II',typ,0))
        except (EOFError,OSError):pass
        finally:conn.close();self.sock.close()

class LayoutTests(unittest.TestCase):
    def test_full_tkl_compact_use_their_own_matrix(self):
        for w,h in [(22,6),(18,6),(14,5)]:
            d=fixture(width=w,height=h);l=bridge_layout(d);self.assertTrue(l.spatial);self.assertEqual((l.width,l.height),(w,h))
            p=new_profile();p['effect']='Audio';levels=np.zeros((2,6));levels[0]=1
            c=render_layout(p,0,levels,l)
            self.assertTrue(any(sum(c[k.id])>0 for k in l.keys if k.x+k.w/2<l.width/2))
            self.assertTrue(all(sum(c[k.id])==0 for k in l.keys if k.x+k.w/2>=l.width/2))
    def test_zone_missing_geometry_is_mirrored(self):
        d=fixture(width=5,height=1,matrix=False);l=bridge_layout(d);self.assertFalse(l.spatial)
        p=new_profile();p['effect']='Audio';lv=np.zeros((2,6));lv[1,4]=1
        colors=render_layout(p,0,lv,l);self.assertEqual(len(set(colors.values())),1);self.assertGreater(sum(next(iter(colors.values()))),0)
    def test_padding_is_not_a_key(self):
        d=fixture(width=2,height=1);d.leds+=[''];d.colors+=[(0,0,0)];d.zones[0].count=3;d.signature=signature(d)
        l=bridge_layout(d);self.assertTrue(l.spatial);self.assertEqual(len(l.keys),2);self.assertEqual(len(l.led_ids),3)
    def test_mapping_uses_positions_not_order(self):
        d=fixture(width=2,height=1,matrix=False);l=bridge_layout(d)
        values={l.led_ids[0]:[9,0],l.led_ids[1]:[0,0]};validate_mapping(values,l)
        mapped=bridge_layout(d,values);self.assertEqual(mapped.keys[0].x,9)
        with self.assertRaises(ValueError):validate_mapping({k:[0,0] for k in l.led_ids},l)
    def test_old_profiles_and_device_paint_are_separate(self):
        p=new_profile();p.pop('device_overrides');p['overrides']={'W':'#ffffff'};q=validate_profile(p)
        l=bridge_layout(fixture());painted(q,l)[l.keys[0].id]='#ff0000'
        self.assertEqual(painted(q,DIRECT_LAYOUT),{'W':'#ffffff'})
        with tempfile.TemporaryDirectory() as temp:
            store=ProfileStore(temp);store.commit(q);again=ProfileStore(temp).get()
            self.assertEqual(again['device_overrides'],q['device_overrides'])
            self.assertEqual(again['overrides'],p['overrides'])

class ProtocolTests(unittest.TestCase):
    def test_real_format_parser_and_malformed_packet(self):
        d=fixture();raw=packet_data(d);got=parse_controller(raw,27)
        self.assertEqual(got.identity,d.identity);self.assertEqual(got.signature,d.signature)
        for raw in [raw[:-1],raw[:12]]:
            with self.assertRaises(BridgeError):parse_controller(raw,27)
    def test_stable_identity_and_stale_layout(self):
        original=fixture();moved=copy.deepcopy(original);moved.id=900
        self.assertEqual(resolve([fixture('Mouse',typ=6),moved],original).id,900)
        with self.assertRaises(BridgeError):resolve([moved,moved],original)
        with self.assertRaises(BridgeError):resolve([fixture(serial='OTHER')],original)
        moved.signature='changed'
        with self.assertRaises(BridgeError):resolve([moved],original)
    def test_selected_keyboard_only_with_fragmented_tcp(self):
        server=FixtureServer();sdk=SDK(server.port).connect()
        try:
            devices=sdk.devices();chosen=resolve(devices,server.devices[0]);sdk.custom(chosen.id);sdk.write(chosen.id,[(20,30,40)]*len(chosen.leds))
        finally:sdk.close()
        server.thread.join(2);self.assertEqual([x[:2] for x in server.writes],[(27,1100),(27,1050)])
    def test_non_keyboard_never_resolves(self):
        mouse=fixture(typ=6)
        with self.assertRaises(BridgeError):resolve([mouse],mouse)
    def test_catalog_is_exact_and_scoped(self):
        c=catalog();self.assertGreater(len(c['models']),100)
        self.assertTrue(all(m['detector'] in c['detectors'] and len(m['vid'])==4 and len(m['pid'])==4 for m in c['models']))
        for name in ['Corsair DRAM','Gigabyte RGB Fusion 2 SMBus','Patriot Viper Steel','Logitech HID++ 2.0']:
            self.assertIn(name,c['detectors'])

if __name__=='__main__':unittest.main()
