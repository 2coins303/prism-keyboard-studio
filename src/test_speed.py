"""Regression coverage for preserving slow looks and extending only the upper range."""
import os,math,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from app import Studio,STYLE
from model import MAX_SPEED,new_profile,validate_profile,ProfileStore,animation_rate
from verification_speed import check_old_frames,check_maximum_pace

class SpeedRange(unittest.TestCase):
    def test_original_low_range_and_saved_pace_are_exactly_preserved(self):
        for speed in (0,1,10,45,75,99,100):self.assertEqual(animation_rate(speed),.12+speed/45)
        self.assertEqual(check_old_frames(),93)

    def test_every_animation_runs_ten_times_faster_at_the_new_maximum(self):
        self.assertEqual(check_maximum_pace(),26)
        self.assertTrue(all(animation_rate(s+1)>animation_rate(s) for s in range(MAX_SPEED)))

    def test_high_speed_round_trip_drafts_and_range_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ProfileStore(directory);p=store.get();p['speed']=100;store.commit(p)
            self.assertEqual(ProfileStore(directory).get()['speed'],100)
            p['speed']=MAX_SPEED;store.drafts[p['id']]=p;store.save()
            reopened=ProfileStore(directory);self.assertFalse(reopened.warning)
            self.assertEqual(reopened.drafts[p['id']]['speed'],MAX_SPEED)
            store.commit(p);path=Path(directory)/'fast.json';store.export_file(path,p)
            self.assertEqual(store.import_file(path)['speed'],MAX_SPEED)
            for bad in (-1,1001,True,float('nan'),float('inf'),'1000'):
                p['speed']=bad
                with self.assertRaises(ValueError):validate_profile(p)
            p['speed']=MAX_SPEED;p['brightness']=101
            with self.assertRaises(ValueError):validate_profile(p)

class SpeedUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)

    def test_exact_entry_quick_speeds_preserve_phase_and_disable_when_irrelevant(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                w.show();w.use_pattern('Rain');self.app.processEvents();w.timer.stop()
                w.phase=213.125;position=w.phase*animation_rate(w.p['speed'])
                entry=w.speed_value;entry.setFocus()
                QTest.keyClick(entry,Qt.Key_A,Qt.ControlModifier);QTest.keyClicks(entry,'1000');QTest.keyClick(entry,Qt.Key_Return)
                self.assertEqual(w.p['speed'],MAX_SPEED);self.assertEqual(w.speed.value(),MAX_SPEED)
                self.assertTrue(math.isclose(position,w.phase*animation_rate(w.p['speed'])))
                for value in (100,250,500,1000):
                    w.speed_control.quick_buttons[value].click()
                    self.assertEqual(w.p['speed'],value);self.assertEqual(entry.value(),value)
                    self.assertTrue(math.isclose(position,w.phase*animation_rate(w.p['speed'])))
                for name in ('Solid','Audio','Checkerboard'):
                    w.use_pattern(name)
                    self.assertFalse(w.speed.isEnabled());self.assertFalse(w.speed_value.isEnabled())
                    self.assertTrue(all(not b.isEnabled() for b in w.speed_control.quick_buttons.values()))
                w.use_pattern('Galaxy');self.assertTrue(w.speed.isEnabled());self.assertEqual(w.p['speed'],MAX_SPEED)
            finally:w.close();self.app.processEvents()

if __name__=='__main__':unittest.main()
