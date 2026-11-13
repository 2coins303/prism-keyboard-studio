"""Brightness behavior across every pattern, layout, and editing surface."""
import os,tempfile,unittest
from types import SimpleNamespace as N
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PySide6.QtCore import QPoint,Qt
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtTest import QTest
from app import Studio,STYLE
from pattern_browser import PatternBrowser
from model import EFFECTS,ProfileStore,new_profile
from layouts import DIRECT_LAYOUT,bridge_layout,render_layout,painted
from test_bridge import fixture


class BrightnessRendering(unittest.TestCase):
    def test_all_patterns_scale_and_switch_off_every_led_including_paint(self):
        layouts=[DIRECT_LAYOUT,bridge_layout(fixture(width=14,height=5)),bridge_layout(fixture(width=5,height=1,matrix=False))]
        levels=np.ones((2,6))
        for layout in layouts:
            for name in EFFECTS:
                p=new_profile(effect=name);painted(p,layout)[layout.keys[0].id]='#ffffff'
                p['brightness']=100;full=np.array(list(render_layout(p,3.7,levels,layout).values()))
                p['brightness']=37;dim=np.array(list(render_layout(p,3.7,levels,layout).values()))
                self.assertTrue((np.abs(dim-np.floor(full*.37))<=1).all(),(layout.name,name))
                self.assertTrue((dim<=full).all());self.assertTrue(dim.any())
                p['brightness']=0;off=render_layout(p,3.7,levels,layout)
                self.assertEqual(set(off.values()),{(0,0,0)},(layout.name,name))


class BrightnessUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)

    def test_visible_across_all_tabs_patterns_and_scroll_positions(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                w.show();w.resize(1100,740);w.timer.stop();self.app.processEvents()
                w.brightness_value.setValue(37)
                for name in EFFECTS:
                    w.use_pattern(name)
                    for tab in range(3):
                        w.tabs.setCurrentIndex(tab);self.app.processEvents()
                        for scroll_to in (0,w.main_scroll.verticalScrollBar().maximum()):
                            w.main_scroll.verticalScrollBar().setValue(scroll_to)
                            self.assertTrue(w.brightness.isVisible() and w.brightness.isEnabled(),name)
                            origin=w.brightness_control.mapTo(w,QPoint(0,0))
                            self.assertTrue(w.rect().contains(w.brightness_control.rect().translated(origin)))
                            self.assertEqual(w.p['brightness'],37)
                self.assertEqual(w.brightness.value(),37)
                w.save_profile();self.assertEqual(ProfileStore(directory).get()['brightness'],37)
            finally:w.close();self.app.processEvents()

    def test_gallery_numeric_and_slider_changes_sync_and_dim_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                dialog=PatternBrowser(w);dialog.show();self.app.processEvents();dialog.search.setText('Solid')
                percentage=dialog.brightness_control.percentage
                self.assertGreater(percentage.findChild(QLineEdit).width(),30)
                percentage.setFocus();QTest.keyClick(percentage,Qt.Key_A,Qt.ControlModifier)
                QTest.keyClicks(percentage,'25');QTest.keyClick(percentage,Qt.Key_Return)
                self.assertEqual(w.p['brightness'],25);self.assertEqual(w.brightness.value(),25)
                self.assertEqual(w.brightness_value.value(),25)
                dialog.brightness_control.slider.setValue(0);dialog.rebuild()
                self.assertEqual(w.brightness.value(),0)
                self.assertEqual(next(iter(dialog.pixmaps.values())).toImage().pixelColor(8,8).getRgb()[:3],(0,0,0))
                dialog.brightness_control.percentage.setValue(61);dialog.choose('Fire')
                self.assertEqual(w.p['brightness'],61)
                w.persist_draft();self.assertEqual(ProfileStore(directory).drafts[w.p['id']]['brightness'],61)
            finally:w.close();self.app.processEvents()

    def test_static_only_device_keeps_brightness_control(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                d=fixture();d.modes[0].flags=512;w.select_bridge(d);w.use_pattern('Checkerboard')
                self.assertTrue(w.brightness.isEnabled());w.brightness_value.setValue(0)
                self.assertEqual(set(render_layout(w.p,0,None,w.layout).values()),{(0,0,0)})
                self.assertFalse(w.active)  # Adjustment never starts a hardware write on its own.
                self.assertFalse(w.tabs.isTabEnabled(2))
            finally:w.close();self.app.processEvents()

    def test_live_submission_contains_adjusted_brightness(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True);frames=[]
            try:
                w.timer.stop();w.worker=N(submit=frames.append,shutdown=lambda:None)
                w.active=True;w.use_pattern('Solid');w.p['palette'][0]='#ffffff';w.p['overrides']={'W':'#ffffff'}
                w.brightness_value.setValue(40);w.tick()
                self.assertEqual(set(frames[-1]),{0,102})  # Empty matrix cells stay black.
                w.brightness.setValue(0);w.tick();self.assertEqual(frames[-1],bytes(396))
            finally:w.close();self.app.processEvents()

if __name__=='__main__':unittest.main()
