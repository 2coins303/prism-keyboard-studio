"""Isolated source/frozen pattern-library checks. No hardware connection or writes."""
import copy,sys,tempfile,time,traceback
from pathlib import Path
import numpy as np
from PySide6.QtCore import QPoint,QTimer,QEventLoop
from PySide6.QtWidgets import QLineEdit
from PySide6.QtGui import QPixmap
from model import APP_NAME,VERSION,EFFECTS,ANIMATED,PALETTES,ProfileStore,atomic_json,render_colors,matrix_frame
from patterns import PATTERNS
from pattern_browser import PatternBrowser

def settle():
    # Let layout/show and deferred deletion events finish before visual checks.
    loop=QEventLoop();QTimer.singleShot(200,loop.quit);loop.exec()

def capture(widget,path):
    # Explicitly repaint all children after rapid automated page switches.
    pixmap=QPixmap(widget.size());widget.render(pixmap)
    return pixmap.save(str(path))

def check_patterns(app,Studio,report_path):
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(app=APP_NAME,version=VERSION,frozen=bool(getattr(sys,'frozen',False)),hardware_access=False)
    with tempfile.TemporaryDirectory(prefix='prism-pattern-check-',dir=report_path.parent) as temporary:
        w=Studio(temporary,offline=True)
        try:
            w.show();settle();w.timer.stop()
            assert w.pages.currentWidget()==w.library and w.presets_nav.isChecked()
            assert len(w.library.cards)==31 and len(w.library.theme_buttons)==4
            assert capture(w,report_path.parent/'Prism 2.3 presets.png')
            next(b for n,_,b in w.library.cards if n=='Fire').click()
            assert w.pages.currentWidget()==w.main_scroll and w.p['effect']=='Fire'
            w.presets_nav.click();assert w.pages.currentWidget()==w.library
            w.library.theme_buttons['Neon nights'].click()
            assert w.pages.currentWidget()==w.main_scroll and w.p['palette']==PALETTES['Neon nights']
            samples={};benchmarks={}
            for name in EFFECTS:
                w.use_pattern(name);app.processEvents()
                assert w.p['effect']==name
                w.brightness_value.setValue(0)
                assert not any(matrix_frame(render_colors(w.p,3.3,np.ones((2,6)))))
                w.brightness.setValue(37)
                assert w.p['brightness']==37 and w.brightness_value.value()==37
                start=time.perf_counter()
                frames=[render_colors(w.p,t,np.ones((2,6))*.75) for t in (0,.8,3.3,12.7)]
                benchmarks[name]=round((time.perf_counter()-start)*250,3)
                assert all(len(matrix_frame(c))==396 for c in frames)
                if name in ANIMATED and name!='Audio':assert frames[0]!=frames[-1],name
                samples[name]=len(set(frames[2].values()))
                file=Path(temporary)/'export.json';w.store.export_file(file,w.p)
                assert w.store.import_file(file)['effect']==name
            w.brightness.setValue(85);w.use_pattern('Aurora');w.tick();app.processEvents()
            settle();assert capture(w,report_path.parent/'Prism 2.3 customize.png')
            gallery=PatternBrowser(w);gallery.show();settle()
            assert len(gallery.cards)==31
            gallery.brightness_control.percentage.setValue(64);settle()
            assert w.p['brightness']==64 and w.brightness.value()==64 and w.brightness_value.value()==64
            assert gallery.cards[0][1].height()>180
            assert gallery.brightness_control.percentage.findChild(QLineEdit).width()>30
            assert capture(gallery,report_path.parent/'Prism 2.3 preset dialog.png')
            gallery.search.setText('ocean');assert [n for n,_,_ in gallery.cards]==['Ocean waves']
            old=copy.deepcopy(w.p);gallery.keep_colors.setChecked(True);gallery.choose('Ocean waves')
            assert w.p['palette']==old['palette'];w.undo();assert w.p==old
            w.redo();assert w.p['effect']=='Ocean waves'
            w.save_profile();assert ProfileStore(temporary).get()['effect']=='Ocean waves'
            # Verify the actual minimum supported window size remains usable.
            w.resize(1100,740);w.tick();settle()
            assert capture(w,report_path.parent/'Prism 2.3 compact customize.png')
            scroll=w.main_scroll.verticalScrollBar();assert scroll.maximum()>0
            scroll.setValue(scroll.maximum());app.processEvents()
            assert capture(w,report_path.parent/'Prism 2.3 compact controls.png')
            for tab in range(3):
                w.tabs.setCurrentIndex(tab);settle()
                origin=w.brightness_control.mapTo(w,QPoint(0,0))
                assert w.rect().contains(w.brightness_control.rect().translated(origin))
                assert w.brightness.isVisible() and w.brightness.isEnabled()
            assert capture(w,report_path.parent/'Prism 2.3 audio brightness.png')
            w.presets_nav.click();settle()
            assert w.library.columns==2
            assert w.library.scroll.horizontalScrollBar().maximum()==0
            assert capture(w,report_path.parent/'Prism 2.3 compact presets.png')
            report.update(result='PASS',patterns=len(EFFECTS),rendered_unique_colors=samples,
                          milliseconds_per_frame=benchmarks,search_and_selection=True,
                          kept_custom_palette=True,undo_redo=True,all_pattern_exports=True,saved_profile=True,
                          brightness_all_patterns=True,brightness_all_tabs_visible=True,gallery_brightness_sync=True,zero_percent_all_leds_off=True,
                          opens_to_presets=True,one_click_customize=True,color_presets_visible=True,responsive_preset_grid=True)
        except Exception:
            report.update(result='FAIL',error=traceback.format_exc())
        finally:w.close();app.processEvents()
    atomic_json(report_path,report)
    return 0 if report.get('result')=='PASS' else 1
