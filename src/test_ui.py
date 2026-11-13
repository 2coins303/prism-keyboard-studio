import os,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from app import Studio,STYLE
from keyboard_setup import KeyboardSetup,MappingDialog
from test_bridge import fixture

class UIFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyleSheet(STYLE)
    def test_setup_filters_closes_and_keeps_device_paint_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            w=Studio(directory,offline=True)
            try:
                dialog=KeyboardSetup(w);dialog.search.setText('Blackwidow V4');self.assertGreater(dialog.models_box.count(),0)
                dialog.show();self.app.processEvents();dialog.close();self.app.processEvents()
                w.select_bridge(fixture('Compact fixture',14,5));w.canvas.selected={w.layout.keys[0].id};w.paint_selected()
                self.assertEqual(len(w.paint_colors),1);self.assertEqual(w.p['overrides'],{})
                w.undo();self.assertEqual(w.paint_colors,{})
                w.redo();self.assertEqual(len(w.paint_colors),1)
                m=MappingDialog(w);m.show();self.app.processEvents();m.close()
                w.select_direct();self.assertEqual(w.paint_colors,{})
                limited=fixture('Static-only fixture');limited.modes[0].flags=512
                w.select_bridge(limited);self.assertFalse(w.tabs.isTabEnabled(2))
                self.assertFalse(w.effect.model().item(6).isEnabled())
                w.select_direct();self.assertTrue(w.tabs.isTabEnabled(2))
            finally:w.close()

if __name__=='__main__':unittest.main()
