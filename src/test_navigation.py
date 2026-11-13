"""Real user paths through the preset-first layout, without desktop interaction."""
import os,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QPoint,QTimer,QEventLoop
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app import Studio,STYLE
from model import PALETTES,ProfileStore
from test_bridge import fixture

def settle():
    loop=QEventLoop();QTimer.singleShot(160,loop.quit);loop.exec()

class PresetNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)

    def test_launch_choose_customize_return_and_saved_look(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                w.show();settle();w.timer.stop()
                self.assertEqual(w.pages.currentWidget(),w.library)
                self.assertTrue(w.presets_nav.isChecked())
                self.assertEqual(len(w.library.cards),31)
                w.brightness_value.setValue(42)
                w.library.search.setText('ocean')
                name,card,choose=w.library.cards[0];self.assertEqual(name,'Ocean waves')
                choose.click();self.assertEqual(w.pages.currentWidget(),w.main_scroll)
                self.assertEqual(w.p['effect'],'Ocean waves');self.assertEqual(w.p['brightness'],42)
                self.assertEqual(w.p['palette'],PALETTES['Deep ocean'])
                w.presets_nav.click();self.assertEqual(w.pages.currentWidget(),w.library)
                self.assertEqual(w.library.search.text(),'ocean')
                QTest.keyClick(w.library.search,Qt.Key_Escape)
                self.assertTrue(w.library.isVisible())
                w.library.theme_buttons['Cyber mint'].click()
                self.assertEqual(w.p['effect'],'Gradient');self.assertEqual(w.p['palette'],PALETTES['Cyber mint'])
                self.assertEqual(w.p['brightness'],42);self.assertEqual(w.pages.currentWidget(),w.main_scroll)
                w.save_profile();self.assertEqual(ProfileStore(directory).get()['brightness'],42)
                w.presets_nav.click()
                item=w.profiles.currentItem()
                QTest.mouseClick(w.profiles.viewport(),Qt.LeftButton,pos=w.profiles.visualItemRect(item).center())
                self.assertEqual(w.pages.currentWidget(),w.main_scroll)
                self.assertEqual({a.text() for a in w.profile_menu.actions()}, {'Rename','Duplicate','Restore saved look','Import','Export','Delete'})
            finally:w.close();self.app.processEvents()

    def test_small_window_and_static_keyboard_keep_presets_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                w.resize(1100,740);w.show();settle();w.timer.stop()
                self.assertEqual(w.library.columns,2)
                self.assertEqual(w.library.scroll.horizontalScrollBar().maximum(),0)
                for widget in (w.presets_nav,w.brightness_control,w.apply_btn):
                    self.assertTrue(widget.isVisible())
                    self.assertTrue(w.rect().contains(widget.rect().translated(widget.mapTo(w,QPoint(0,0)))))
                d=fixture();d.modes[0].flags=512;w.select_bridge(d);w.show_presets();settle()
                self.assertFalse(next(b for n,_,b in w.library.cards if n=='Fire').isEnabled())
                self.assertTrue(next(b for n,_,b in w.library.cards if n=='Checkerboard').isEnabled())
                w.library.choose('Checkerboard');self.assertEqual(w.pages.currentWidget(),w.main_scroll)
                self.assertEqual(w.p['effect'],'Checkerboard');self.assertTrue(w.brightness.isEnabled())
            finally:w.close();self.app.processEvents()

if __name__=='__main__':unittest.main()
