"""Regression: changing window size must not squeeze text inside padded buttons."""
import os,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from app import Studio,STYLE
from verification_resize import exercise_resize

class ResizeRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet(STYLE)
        # Offscreen Windows tests must explicitly load the installed app font,
        # just as the packaged verification entry point does.
        for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
            font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
            if font.exists():QFontDatabase.addApplicationFont(str(font))

    def test_all_tabs_preserve_button_text_when_window_shape_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            window=Studio(directory,offline=True)
            try:
                cases=exercise_resize(window)
                self.assertEqual(len(cases),18)
                paint=next(c for c in cases if c['width']==1346 and c['height']==740 and c['tab']=='Paint keys')
                self.assertTrue(any(b['text']=='Paint selected' for b in paint['buttons']))
            finally:window.close();self.app.processEvents()

    def test_color_picker_buttons_are_readable_for_light_and_dark_swatches(self):
        from verification_color_picker import exercise_color_pickers
        with tempfile.TemporaryDirectory() as directory:
            window=Studio(directory,offline=True)
            try:
                window.show();window.timer.stop()
                cases=exercise_color_pickers(window)
                self.assertEqual(len(cases),12)
            finally:window.close();self.app.processEvents()

if __name__=='__main__':unittest.main()
