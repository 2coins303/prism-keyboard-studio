"""Check real styled text rectangles after resizing. No hardware access."""
import sys,os,tempfile,traceback
from pathlib import Path
from PySide6.QtCore import QEventLoop,QTimer,QPoint,Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QPushButton,QStyleOptionButton,QStyle
from model import APP_NAME,VERSION,atomic_json

SIZES=[(1360,900),(1346,740),(1100,740),(1700,740),(1100,1100),(1360,900)]

def settle(milliseconds=60):
    loop=QEventLoop();QTimer.singleShot(milliseconds,loop.quit);loop.exec()

def readable_buttons(window):
    checked=[]
    for button in window.findChildren(QPushButton):
        if not button.text() or not button.isVisible():continue
        option=QStyleOptionButton();button.initStyleOption(option)
        rect=button.style().subElementRect(QStyle.SE_PushButtonContents,option,button)
        text=button.text().replace('&&','\0').replace('&','').replace('\0','&')
        font=button.fontMetrics()
        assert rect.height()>=font.height(),f'{button.text()}: only {rect.height()} px for {font.height()} px text'
        assert rect.width()>=font.horizontalAdvance(text),f'{button.text()}: text is wider than the button content'
        checked.append(dict(text=button.text(),button_height=button.height(),text_height=rect.height(),font_height=font.height()))
    return checked

def capture(window,path):
    pixmap=QPixmap(window.size());pixmap.fill(Qt.transparent);window.render(pixmap)
    assert pixmap.save(str(path))

def exercise_resize(window,output_dir=None):
    window.show();window.show_editor();settle(150);window.timer.stop()
    cases=[]
    for width,height in SIZES:
        window.resize(width,height)
        for tab in range(3):
            window.tabs.setCurrentIndex(tab);settle()
            checks=readable_buttons(window)
            for control in (window.brightness_control,window.apply_btn):
                origin=control.mapTo(window,QPoint(0,0))
                assert control.isVisible() and window.rect().contains(control.rect().translated(origin))
            cases.append(dict(width=width,height=height,tab=window.tabs.tabText(tab),buttons=checks))
            if output_dir and (width,height)==(1346,740) and tab==1:
                window.main_scroll.verticalScrollBar().setValue(window.main_scroll.verticalScrollBar().maximum());settle()
                capture(window,output_dir/'Prism 2.5 compact paint.png')
    if output_dir:
        window.resize(1360,900)
        for tab,name in enumerate(('colors','paint','audio')):
            window.tabs.setCurrentIndex(tab);window.main_scroll.verticalScrollBar().setValue(0);settle(160)
            capture(window,output_dir/f'Prism 2.5 {name}.png')
    window.show_presets();window.resize(1100,740);settle(160)
    readable_buttons(window)
    assert window.library.scroll.horizontalScrollBar().maximum()==0
    if output_dir:
        capture(window,output_dir/'Prism 2.5 compact presets.png')
        window.resize(1360,900);settle(160)
        capture(window,output_dir/'Prism 2.5 presets.png')
    return cases

def check_resize(app,Studio,report_path):
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(app=APP_NAME,version=VERSION,frozen=bool(getattr(sys,'frozen',False)),hardware_access=False,
                display_scale=os.environ.get('QT_SCALE_FACTOR','1'))
    with tempfile.TemporaryDirectory(prefix='prism-resize-',dir=report_path.parent) as directory:
        window=Studio(directory,offline=True)
        try:
            report['cases']=exercise_resize(window,report_path.parent)
            report.update(result='PASS',cases_checked=len(report['cases']),all_button_text_fits=True,brightness_apply_remain_visible=True)
        except Exception:report.update(result='FAIL',error=traceback.format_exc())
        finally:window.close();app.processEvents()
    atomic_json(report_path,report)
    return 0 if report['result']=='PASS' else 1
