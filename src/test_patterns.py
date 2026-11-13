"""Behavior checks for the expanded pattern library, including the gallery."""
import copy,os,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PySide6.QtWidgets import QApplication
from app import Studio,STYLE
from pattern_browser import PatternBrowser
from patterns import PATTERNS,EXTRA_PATTERNS,STATIC_PATTERNS
from model import EFFECTS,ANIMATED,PALETTES,KEYS,Key,new_profile,render_colors,ProfileStore,validate_profile
from layouts import bridge_layout,render_layout,painted,DIRECT_LAYOUT
from test_bridge import fixture


class PatternRendering(unittest.TestCase):
    def test_every_recipe_is_available_and_round_trips(self):
        self.assertEqual(len(EFFECTS),31);self.assertEqual(len(EXTRA_PATTERNS),24)
        self.assertEqual(set(PATTERNS),set(EFFECTS))
        with tempfile.TemporaryDirectory() as directory:
            store=ProfileStore(directory)
            for name,recipe in PATTERNS.items():
                p=new_profile(name=name,effect=name,palette=PALETTES[recipe['palette']])
                p['overrides']={'W':'#123456'};store.commit(p)
                exported=Path(directory)/'look.json';store.export_file(exported,p)
                restored=store.import_file(exported)
                self.assertEqual(restored['effect'],name)
                self.assertEqual(restored['overrides'],p['overrides'])
            loaded=ProfileStore(directory)
            self.assertFalse(loaded.warning)
            self.assertEqual({p['effect'] for p in loaded.profiles},set(EFFECTS))

    def test_each_new_animation_moves_and_static_patterns_hold(self):
        signatures=set()
        for name in EXTRA_PATTERNS:
            p=new_profile(effect=name)
            frames=[tuple(render_colors(p,t).values()) for t in (0,.8,3.3,12.7)]
            if name in STATIC_PATTERNS:self.assertEqual(len(set(frames)),1,name)
            else:self.assertGreater(len(set(frames)),1,name)
            signatures.add(tuple(frames))
        self.assertEqual(len(signatures),len(EXTRA_PATTERNS))

    def test_new_effects_cover_all_layouts_directions_and_extremes(self):
        layouts=[DIRECT_LAYOUT]+[bridge_layout(fixture(width=w,height=h)) for w,h in [(22,6),(18,6),(14,5),(4,1)]]
        for layout in layouts:
            for name in EXTRA_PATTERNS:
                for direction in ('Right','Left','Up','Down'):
                    p=new_profile(effect=name);p['direction']=direction
                    for speed,bright,t in [(0,0,0),(100,100,98765.432),(1000,100,98765.432)]:
                        p['speed']=speed;p['brightness']=bright
                        colors=render_layout(p,t,None,layout)
                        self.assertEqual(set(colors),{k.id for k in layout.keys})
                        values=np.array(list(colors.values()))
                        self.assertTrue(np.isfinite(values).all())
                        self.assertTrue(((values>=0)&(values<=255)).all())
                        if not bright:self.assertFalse(values.any())

    def test_physical_positions_determine_effects_not_key_order(self):
        keys=[Key('a','',0,0,1,1,0,0),Key('b','',3,2,1,1,2,3)]
        scaled=[Key(k.id,'',k.x*2,k.y*2,2,2,99,99) for k in keys]
        for name in EXTRA_PATTERNS:
            p=new_profile(effect=name)
            a=render_colors(p,4,keys=keys,width=4,height=3)
            b=render_colors(p,4,keys=list(reversed(scaled)),width=8,height=6)
            self.assertEqual(a,b,name)

    def test_unmapped_lights_stay_uniform_and_painted_keys_win(self):
        layouts=[DIRECT_LAYOUT,bridge_layout(fixture(width=14,height=5)),bridge_layout(fixture(width=8,height=1,matrix=False))]
        for layout in layouts:
            for name in EXTRA_PATTERNS:
                p=new_profile(effect=name);p['brightness']=100
                base=render_layout(p,2,None,layout)
                if not layout.spatial:self.assertEqual(len(set(base.values())),1,name)
                key=layout.keys[0].id;painted(p,layout)[key]='#123456'
                self.assertEqual(render_layout(p,9,None,layout)[key],(18,52,86))


class PatternGallery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)

    def test_search_category_selection_keep_colors_and_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                w.p['overrides']={'W':'#123456'};before=copy.deepcopy(w.p)
                dialog=PatternBrowser(w);self.assertEqual(len(dialog.cards),31)
                dialog.search.setText('ocean');self.assertEqual([n for n,_,_ in dialog.cards],['Ocean waves'])
                dialog.search.setText('unmatched pattern');self.assertFalse(dialog.cards)
                dialog.search.clear();dialog.category.setCurrentText('Static')
                self.assertEqual({n for n,_,_ in dialog.cards},STATIC_PATTERNS)
                dialog.choose('Fire');self.assertEqual(w.p['effect'],'Fire')
                self.assertEqual(w.p['palette'],PALETTES['Solar flare'])
                self.assertEqual(w.p['overrides'],before['overrides'])
                w.undo();self.assertEqual(w.p,before)
                w.redo();self.assertEqual(w.p['effect'],'Fire')
                second=PatternBrowser(w);second.keep_colors.setChecked(True)
                second.choose('Rain');self.assertEqual(w.p['palette'],PALETTES['Solar flare'])
                self.assertEqual(w.p['direction'],'Down')
                w.persist_draft();saved=ProfileStore(directory)
                self.assertEqual(saved.drafts[w.p['id']]['effect'],'Rain')
                w.use_pattern('Rainbow spiral');self.assertTrue(all(not b.isEnabled() for b in w.palette_buttons))
                w.use_pattern('Checkerboard');self.assertFalse(w.speed.isEnabled())
            finally:w.close();self.app.processEvents()

    def test_static_only_device_cannot_select_new_animations(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                d=fixture();d.modes[0].flags=512;w.select_bridge(d)
                dialog=PatternBrowser(w)
                for name,card,choose in dialog.cards:self.assertEqual(choose.isEnabled(),name in STATIC_PATTERNS,name)
                before=copy.deepcopy(w.p);dialog.choose('Fire');self.assertEqual(w.p,before)
                dialog.choose('Checkerboard');self.assertEqual(w.p['effect'],'Checkerboard')
                self.assertFalse(w.speed.isEnabled());self.assertFalse(w.tabs.isTabEnabled(2))
            finally:w.close();self.app.processEvents()

if __name__=='__main__':unittest.main()
