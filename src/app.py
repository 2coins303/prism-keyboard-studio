"""Native Windows UI for Prism Keyboard Studio. GPL-2.0-or-later."""
from __future__ import annotations
import copy
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time

import numpy as np
from PySide6.QtCore import Qt, QTimer, QRectF, Signal, QSize, QLockFile, QStandardPaths
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QLinearGradient, QIcon, QPixmap, QKeySequence, QShortcut, QFontDatabase
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,
    QLabel,QPushButton,QComboBox,QSlider,QFrame,QListWidget,QListWidgetItem,QTabWidget,QColorDialog,
    QInputDialog,QMessageBox,QFileDialog,QCheckBox,QScrollArea,QDialog,QTextBrowser,QSizePolicy,QLayout,QStackedWidget,QMenu)

from model import *
from device import DeviceWorker
from audio_engine import AudioCapture
from layouts import DIRECT_LAYOUT,bridge_layout,render_layout,painted,validate_mapping
from bridge import OpenRGBKeyboard,static_only
from managed_bridge import ManagedBridge
from keyboard_setup import KeyboardSetup,MappingDialog
from patterns import PATTERNS,DIRECTIONAL
from pattern_browser import PatternBrowser
from brightness_control import BrightnessControl
from speed_control import SpeedControl

STYLE = '''
QWidget { background:#10101b; color:#eeedfa; font-family:'Segoe UI'; font-size:13px; }
QMainWindow { background:#10101b; }
QLabel { background:transparent; }
QLabel#muted { color:#aaa8c5; }
QLabel#eyebrow { color:#bca4ff; font-size:11px; font-weight:700; letter-spacing:2px; }
QLabel#title { font-size:28px; font-weight:750; }
QLabel#section { font-size:16px; font-weight:700; }
QFrame#sidebar { background:#151421; border-right:1px solid #302b45; }
QFrame#card { background:#1d1a2d; border:1px solid #443554; border-radius:24px; }
QFrame#card QLabel { background:transparent; border:0; }
QPushButton { border:2px solid #665181; background:#392b50; border-radius:22px; padding:10px 18px; min-height:20px; font-weight:600; }
QPushButton:hover { border-color:#c69aff; background:#51406e; }
QPushButton:pressed { background:#67428a; }
QPushButton:focus { border-color:#edd4ff; }
QPushButton:disabled { color:#80798f; border-color:#383143; background:#211d2b; }
QPushButton:checked { border-color:#e6bbff; background:#7845a5; color:white; }
QPushButton#primary { color:white; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #8c43e8,stop:1 #c4389e); border-color:#d09aff; padding:12px 22px; border-radius:24px; font-size:14px; font-weight:700; }
QPushButton#primary:hover { background:#a947d5; border-color:#f1caff; }
QPushButton#primary:pressed { background:#7735ac; }
QPushButton#preset { background:#563379; border-color:#9d70cc; font-size:14px; font-weight:700; }
QPushButton#preset:hover { background:#75499e; border-color:#e6b8ff; }
QPushButton#preset:disabled { color:#80798f; border-color:#383143; background:#211d2b; }
QPushButton#quiet { background:#292339; border-color:#514260; color:#ded4ed; }
QPushButton#quiet:hover { background:#443354; border-color:#ba91df; }
QPushButton#small { padding:8px 14px; border-radius:20px; font-size:12px; }
QPushButton#nav { text-align:left; padding:14px 18px; font-size:16px; background:#211c30; border-color:#342b46; border-radius:26px; }
QPushButton#nav:checked { color:white; background:#7444a5; border-color:#c98fff; }
QPushButton#nav:hover { background:#503466; }
QMenu { background:#211b30; border:1px solid #635077; padding:6px; }
QMenu::item { padding:8px 20px; }
QMenu::item:selected { background:#54366f; }
QListWidget { background:transparent; border:0; outline:0; }
QListWidget::item { border:1px solid transparent; border-radius:18px; padding:13px 12px; margin-bottom:5px; }
QListWidget::item:selected { background:#35244e; border:1px solid #8f54ce; color:white; }
QListWidget::item:hover { background:#252238; }
QComboBox { border:1px solid #665078; border-radius:16px; padding:9px 14px; background:#242033; min-height:20px; }
QComboBox::drop-down { border:0; width:23px; }
QComboBox QAbstractItemView { background:#252039; border:1px solid #72608d; selection-background-color:#674390; }
QLineEdit { border:1px solid #6a4a91; border-radius:18px; padding:11px 14px; background:#221c31; }
QSpinBox { border:1px solid #6a4a91; border-radius:14px; padding:9px; background:#221c31; }
QSpinBox QLineEdit { border:0; padding:0; background:transparent; }
QSlider::groove:horizontal { height:8px; background:#373146; border-radius:4px; }
QSlider::sub-page:horizontal { background:#bc80ff; border-radius:4px; }
QSlider::handle:horizontal { background:#f4dfff; border:2px solid #b36aff; width:20px; height:20px; margin:-8px 0; border-radius:12px; }
QTabWidget::pane { border:1px solid #383147; background:#191826; border-radius:20px; }
QTabBar::tab { color:#c9bddb; background:#272035; border:2px solid #4a385e; border-radius:18px; padding:10px 22px; margin-right:8px; }
QTabBar::tab:selected { color:white; border-color:#d29aff; background:#72439c; }
QTabBar::tab:hover { background:#513469; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#181522; width:9px; }
QScrollBar::handle:vertical { background:#55416c; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QCheckBox { spacing:8px; background:transparent; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #74608e; border-radius:5px; background:#211b30; }
QCheckBox::indicator:checked { background:#ac62ef; border:2px solid #dfafff; }
QToolTip { background:#2d2340; color:white; border:1px solid #8d64bf; padding:7px; }
QTextBrowser { background:#191522; border:0; padding:8px; }
QDialog { background:#171321; }
'''

def label(text,kind=None):
    w=QLabel(text)
    if kind: w.setObjectName(kind)
    return w

def button(text,slot=None,kind=None):
    w=QPushButton(text)
    w.setCursor(Qt.PointingHandCursor)
    if slot: w.clicked.connect(slot)
    if kind: w.setObjectName(kind)
    return w

def row(*items,spacing=10):
    box=QHBoxLayout(); box.setSpacing(spacing); box.setContentsMargins(0,0,0,0)
    for item in items:
        if item is None: box.addStretch()
        elif isinstance(item,QWidget): box.addWidget(item)
        else: box.addLayout(item)
    return box

class ColorButton(QPushButton):
    chosen=Signal(str)
    def __init__(self,color,title='Choose a color'):
        super().__init__(); self.color=color; self.title=title; self.setCursor(Qt.PointingHandCursor)
        self.setObjectName('colorSwatch')
        self.setFixedSize(56,40); self.setAccessibleName(title); self.refresh(); self.clicked.connect(self.choose)
    def refresh(self):
        # The color dialog is our child: unqualified button rules would also
        # recolor and shrink its OK, Cancel and custom-color controls.
        self.setStyleSheet(f'QPushButton#colorSwatch {{background:{self.color};border:2px solid #d7b7ee;border-radius:18px;padding:0;min-height:36px;}} QPushButton#colorSwatch:hover {{border-color:white;}}')
        self.setToolTip(f'{self.title} · {self.color.upper()}')
    def set_color(self,color): self.color=color; self.refresh()
    def choose(self):
        c=QColorDialog.getColor(QColor(self.color),self,self.title,QColorDialog.DontUseNativeDialog)
        if c.isValid(): self.set_color(c.name()); self.chosen.emit(c.name())

class KeyboardCanvas(QWidget):
    selectionChanged=Signal()
    paintRequested=Signal(str,bool)
    def __init__(self):
        super().__init__(); self.layout_info=DIRECT_LAYOUT; self.colors={k.id:(80,30,130) for k in KEYS}; self.selected=set()
        self.rects={}; self.paint_mode=False; self.dragging=False; self.visited=set(); self.audio=False
        self.setMinimumHeight(245); self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.setMouseTracking(True); self.setAccessibleName('Full-size Huntsman V3 Pro keyboard lighting canvas')
        self.setToolTip('Click a key to select it. Ctrl-click adds keys. Drag to select a group. Turn on Paint mode to brush colors.')
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        outer=QRectF(1,1,self.width()-2,self.height()-2)
        gradient=QLinearGradient(0,0,self.width(),self.height()); gradient.setColorAt(0,QColor('#242039')); gradient.setColorAt(1,QColor('#131a2c'))
        p.setBrush(gradient); p.setPen(QPen(QColor('#514166'),1)); p.drawRoundedRect(outer,17,17)
        layout=self.layout_info; width=layout.width; height=layout.height
        u=min((self.width()-44)/width,(self.height()-68)/height)
        ox=(self.width()-width*u)/2; oy=(self.height()-height*u)/2+8
        self.rects={}
        for k in self.layout_info.keys:
            r=QRectF(ox+k.x*u+2,oy+k.y*u+2,k.w*u-5,k.h*u-5); self.rects[k.id]=r
            c=QColor(*self.colors.get(k.id,(30,30,50)))
            glow=QColor(c); glow.setAlpha(50)
            p.setPen(QPen(glow,4)); p.setBrush(QColor('#151420')); p.drawRoundedRect(r,4,4)
            fill=QColor(int(c.red()*.24)+15,int(c.green()*.21)+15,int(c.blue()*.25)+19)
            p.setBrush(fill); p.setPen(QPen(QColor('#ffffff') if k.id in self.selected else c,2 if k.id in self.selected else 1))
            p.drawRoundedRect(r,4,4)
            p.setPen(Qt.NoPen); p.setBrush(c); p.drawRoundedRect(QRectF(r.x()+4,r.bottom()-5,r.width()-8,2),1,1)
            p.setPen(QColor('#ffffff') if k.id in self.selected else QColor('#eee7ff'))
            f=QFont('Segoe UI'); f.setPixelSize(max(9,int(u*.24))); f.setWeight(QFont.DemiBold); p.setFont(f)
            p.drawText(r,Qt.AlignCenter,k.label)
        p.setFont(QFont('Segoe UI',8)); p.setPen(QColor('#ac9ec6'))
        p.drawText(QRectF(20,9,self.width()-40,16),Qt.AlignLeft,self.layout_info.name.upper())
        if self.audio and self.layout_info.spatial:
            p.setPen(QPen(QColor('#c085ef'),1,Qt.DashLine)); split=ox+width/2*u
            p.drawLine(int(split),int(oy-5),int(split),int(oy+height*u+5))
            p.setPen(QColor('#cbb0e7')); p.drawText(QRectF(0,self.height()-21,self.width()/2,15),Qt.AlignCenter,'LEFT CHANNEL  •  bass → air')
            p.drawText(QRectF(self.width()/2,self.height()-21,self.width()/2,15),Qt.AlignCenter,'RIGHT CHANNEL  •  bass → air')
        else:
            p.setPen(QColor('#ac9ec6')); p.drawText(QRectF(0,self.height()-21,self.width(),15),Qt.AlignCenter,'Click or drag to select')
    def hit(self,pos): return next((k for k,r in self.rects.items() if r.contains(pos)),None)
    def mousePressEvent(self,e):
        if e.button()!=Qt.LeftButton: return
        k=self.hit(e.position()); self.dragging=True; self.visited=set()
        if not k: return
        if self.paint_mode:
            self.paintRequested.emit(k,True); self.visited.add(k)
        else:
            multi=bool(e.modifiers()&(Qt.ControlModifier|Qt.ShiftModifier))
            if not multi: self.selected={k}
            elif k in self.selected: self.selected.remove(k)
            else: self.selected.add(k)
            self.visited.add(k); self.selectionChanged.emit(); self.update()
    def mouseMoveEvent(self,e):
        k=self.hit(e.position()); self.setCursor(Qt.CrossCursor if k else Qt.ArrowCursor)
        if k: self.setToolTip(f'{next(x.label for x in self.layout_info.keys if x.id==k)} · {k} · '+('Paint with your brush color' if self.paint_mode else 'Click to select; Ctrl-click to add'))
        if self.dragging and k and k not in self.visited:
            self.visited.add(k)
            if self.paint_mode: self.paintRequested.emit(k,False)
            else: self.selected.add(k); self.selectionChanged.emit(); self.update()
    def mouseReleaseEvent(self,e): self.dragging=False; self.visited=set()

class Spectrum(QWidget):
    def __init__(self):
        super().__init__(); self.levels=np.zeros((2,6)); self.colors=list(BAND_COLORS); self.meters=np.zeros(2)
        self.setMinimumHeight(60); self.setMaximumHeight(80)
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); w=self.width()/2
        for channel in range(2):
            p.setPen(QColor('#cbbbe2')); p.drawText(QRectF(channel*w,0,23,self.height()),Qt.AlignVCenter,'L' if channel==0 else 'R')
            bw=(w-36)/6
            for i in range(6):
                r=QRectF(channel*w+26+i*bw,6,bw-7,self.height()-12)
                p.setPen(Qt.NoPen); p.setBrush(QColor('#2b233a')); p.drawRoundedRect(r,4,4)
                height=max(1,r.height()*self.levels[channel,i]); p.setBrush(QColor(self.colors[i]))
                p.drawRoundedRect(QRectF(r.x(),r.bottom()-height,r.width(),height),4,4)

class Studio(QMainWindow):
    def __init__(self,data_dir,offline=False):
        super().__init__(); self.data_dir=Path(data_dir); self.offline=offline
        self.layout=DIRECT_LAYOUT; self.selected_device=None; self.bridge_port=None
        self.bridge=ManagedBridge(data_dir); self.mappings={}
        try:self.mappings=json.loads((self.data_dir/'layouts.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        if not isinstance(self.mappings,dict):self.mappings={}
        old_library=self.data_dir/'profiles.json'; backup=self.data_dir/'profiles.before-v2.5.json'
        if old_library.exists() and not backup.exists():backup.write_bytes(old_library.read_bytes())
        self.store=ProfileStore(data_dir); self.p=self.store.drafts.get(self.store.last,self.store.get())
        self.undo_stack=[]; self.redo_stack=[]; self.loading=True; self.active=False; self.paused=False
        self.capture=AudioCapture(); self.analyzer=AudioAnalyzer(); self.worker=None if offline else DeviceWorker()
        self.start_time=time.monotonic(); self.last_tick=self.start_time; self.phase=0.; self.test_until=0.; self.frame_counter=0
        self.audio_status='Choose an audio source.'
        self.last_status=''; self.initial_warning=self.store.warning
        self.setWindowTitle(APP_NAME+" · "+VERSION); self.resize(1360,900); self.setMinimumSize(1100,740)
        self.setWindowIcon(self.make_icon())
        central=QWidget(); self.setCentralWidget(central); outer=QHBoxLayout(central); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        outer.addWidget(self.build_sidebar())
        main=QWidget(); ml=QVBoxLayout(main); ml.setContentsMargins(24,12,24,16); ml.setSpacing(12)
        self.subheading=label('Customize','title')
        ml.addLayout(row(self.subheading,None,button('Change preset',self.show_presets,'small')))
        self.keyboard_btn=button('Huntsman V3 Pro · Change',self.show_keyboards,'quiet')
        self.keyboard_btn.setToolTip('Choose or connect a keyboard')
        self.map_btn=button('Adjust layout',self.adjust_layout,'quiet'); self.map_btn.setEnabled(False)
        self.map_btn.setVisible(False)
        self.layout_note=label(self.layout.note,'muted');self.layout_note.setVisible(False)
        self.canvas=KeyboardCanvas(); self.canvas.selectionChanged.connect(self.selection_changed); self.canvas.paintRequested.connect(self.brush_key)
        ml.addWidget(self.canvas,4)
        self.tabs=QTabWidget(); self.tabs.addTab(self.build_lighting(),'Colors and motion'); self.tabs.addTab(self.build_paint(),'Paint keys'); self.tabs.addTab(self.build_audio(),'Audio')
        # An explicit smaller minimum overrides the tabs' content-derived minimum
        # and compresses padded button text. Let Qt measure the pages; the outer
        # scroll area handles short windows without shrinking their controls.
        ml.addWidget(self.tabs,3)
        self.status_label=label('Preview · '+self.p['effect'] if offline else 'Connecting…'); self.status_label.setWordWrap(True)
        self.status_detail=label('','muted'); self.status_detail.setWordWrap(True); self.status_detail.hide()
        statusbox=QVBoxLayout(); statusbox.setSpacing(3); statusbox.addWidget(self.status_label); statusbox.addWidget(self.status_detail)
        self.apply_btn=button('Apply to keyboard',self.apply,'primary'); self.pause_btn=button('Pause',self.pause); self.pause_btn.setEnabled(False)
        self.apply_btn.setToolTip('Send this look to your keyboard. Edits then apply live. Keep Prism open for animations.')
        self.pause_btn.setToolTip('Pause lighting updates and audio capture. The keyboard may keep its last colors.')
        bottom=QHBoxLayout(); bottom.addLayout(statusbox,1); bottom.addWidget(self.pause_btn); bottom.addWidget(self.apply_btn)
        # Preserve room for the canvas and controls on shorter displays.
        # The main area scrolls instead of allowing widgets to overlap.
        ml.setSizeConstraint(QLayout.SetMinimumSize)
        self.main_scroll=QScrollArea();self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setWidget(main)
        workspace=QWidget();workspace_layout=QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0,0,0,0);workspace_layout.setSpacing(0)
        header=QWidget();header_layout=QHBoxLayout(header);header_layout.setContentsMargins(24,14,24,8)
        header_layout.addWidget(self.keyboard_btn)
        header_layout.addStretch();header_layout.addWidget(self.map_btn);workspace_layout.addWidget(header)
        self.pages=QStackedWidget()
        self.library=PatternBrowser(self,embedded=True)
        self.pages.addWidget(self.library);self.pages.addWidget(self.main_scroll)
        workspace_layout.addWidget(self.pages,1)
        self.controls_footer=QFrame();footer=QVBoxLayout(self.controls_footer)
        footer.setContentsMargins(24,12,24,16);footer.setSpacing(8)
        self.brightness_control=BrightnessControl(self.p['brightness'])
        self.brightness=self.brightness_control.slider;self.brightness_value=self.brightness_control.percentage
        self.brightness_control.valueChanged.connect(lambda value:self.set_value('brightness',value))
        footer.addWidget(self.brightness_control)
        footer.addLayout(bottom);workspace_layout.addWidget(self.controls_footer)
        outer.addWidget(workspace,1)
        self.debounce=QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(650); self.debounce.timeout.connect(self.persist_draft)
        self.reload_profiles(); self.load_controls(); self.loading=False;self.show_presets()
        self.refresh_audio()
        if self.worker: self.worker.start()
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(42)
        QShortcut(QKeySequence.Save,self,activated=self.save_profile)
        QShortcut(QKeySequence.Undo,self,activated=self.undo)
        QShortcut(QKeySequence.Redo,self,activated=self.redo)
        if self.initial_warning: QTimer.singleShot(400,lambda:QMessageBox.warning(self,'Profile recovery',self.initial_warning))

    @property
    def paint_colors(self): return painted(self.p,self.layout)

    def show_keyboards(self): KeyboardSetup(self).exec()

    def stop_connection(self):
        self.release()
        if self.worker:self.worker.shutdown();self.worker=None

    def set_layout(self,layout):
        self.layout=layout;self.canvas.layout_info=layout;self.canvas.selected.clear()
        self.canvas.setAccessibleName(layout.name+' lighting canvas');self.keyboard_btn.setText(layout.name+' · Change')
        self.layout_note.setText(layout.note);self.map_btn.setEnabled(self.selected_device is not None)
        self.map_btn.setVisible(self.selected_device is not None);self.keyboard_btn.setToolTip('Choose or connect a keyboard. '+layout.note)
        self.undo_stack.clear();self.redo_stack.clear();self.selection_changed();self.canvas.update();self.update_labels()

    def select_direct(self):
        self.stop_connection();self.bridge.stop();self.selected_device=None;self.bridge_port=None
        self.set_layout(DIRECT_LAYOUT)
        if not self.offline:self.worker=DeviceWorker();self.worker.start()

    def select_bridge(self,device):
        self.stop_connection();self.selected_device=device
        base=bridge_layout(device);mapping=self.mappings.get(base.identity)
        if mapping:
            try:validate_mapping(mapping,base)
            except (ValueError,TypeError,AttributeError):mapping=None
        self.set_layout(bridge_layout(device,mapping))
        if static_only(device):self.layout_note.setText('Per-key static colors · hardware saves automatically · Apply each change · no audio/animation')
        if not self.offline:
            self.worker=DeviceWorker(lambda:OpenRGBKeyboard(device,self.bridge_port));self.worker.start()

    def adjust_layout(self):
        if self.selected_device:MappingDialog(self).exec()

    def save_mapping(self,values):
        base=bridge_layout(self.selected_device)
        if values is None:self.mappings.pop(base.identity,None)
        else:self.mappings[base.identity]=validate_mapping(values,base)
        atomic_json(self.data_dir/'layouts.json',self.mappings)
        self.set_layout(bridge_layout(self.selected_device,self.mappings.get(base.identity)))

    @staticmethod
    def make_icon():
        pix=QPixmap(128,128); pix.fill(Qt.transparent); p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
        g=QLinearGradient(0,0,128,128); g.setColorAt(0,QColor('#6e3eff')); g.setColorAt(.5,QColor('#c243d5')); g.setColorAt(1,QColor('#26d9ff'))
        p.setBrush(g); p.setPen(Qt.NoPen); p.drawRoundedRect(QRectF(4,4,120,120),28,28)
        p.setPen(QPen(QColor('white'),5)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(QRectF(23,37,82,55),8,8)
        for y in [49,62]:
            for x in [35,49,63,77,91]: p.drawPoint(x,y)
        p.drawLine(42,79,84,79); p.end(); return QIcon(pix)

    def build_sidebar(self):
        w=QFrame(); w.setObjectName('sidebar'); w.setFixedWidth(228); l=QVBoxLayout(w); l.setContentsMargins(16,22,16,18); l.setSpacing(10)
        brand=label('P R I S M'); brand.setStyleSheet('font-size:27px;font-weight:800;color:#edc2ff;'); l.addWidget(brand)
        l.addSpacing(22)
        self.presets_nav=button('Presets',self.show_presets,'nav');self.presets_nav.setCheckable(True);l.addWidget(self.presets_nav)
        self.customize_nav=button('Customize',self.show_editor,'nav');self.customize_nav.setCheckable(True);l.addWidget(self.customize_nav)
        l.addSpacing(20);l.addWidget(label('Saved looks','section'))
        self.profiles=QListWidget(); self.profiles.setAccessibleName('Saved looks'); self.profiles.currentItemChanged.connect(self.switch_profile)
        self.profiles.itemClicked.connect(lambda item:self.show_editor())
        l.addWidget(self.profiles,1)
        self.dirty_label=label('Saved','muted'); self.dirty_label.setWordWrap(True); l.addWidget(self.dirty_label)
        self.dirty_label.setToolTip('Drafts stay on this PC. Save look updates the saved version.')
        l.addWidget(button('Save look',self.save_profile,'primary'))
        more=button('More…',None,'quiet');self.profile_menu=QMenu(more)
        for title,action in [('Rename',self.rename),('Duplicate',self.duplicate),('Restore saved look',self.restore_saved),('Import',self.import_profile),('Export',self.export_profile),('Delete',self.delete)]:
            self.profile_menu.addAction(title,action)
        more.setMenu(self.profile_menu);l.addLayout(row(button('+ New',self.new_profile,'quiet'),more))
        l.addSpacing(12);l.addWidget(button('Help',self.show_help,'quiet'))
        return w

    def slider_row(self,name,low,high,callback):
        lab=label(name); lab.setMinimumWidth(82); val=label(''); val.setMinimumWidth(45)
        s=QSlider(Qt.Horizontal); s.setRange(low,high); s.setAccessibleName(name); s.valueChanged.connect(callback)
        return row(lab,s,val),s,val

    def build_lighting(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(18,18,18,18); l.setSpacing(16)
        self.effect=QComboBox(); self.effect.addItems(EFFECTS); self.effect.setAccessibleName('Lighting effect'); self.effect.currentTextChanged.connect(self.effect_changed)
        self.direction=QComboBox(); self.direction.addItems(['Right','Left','Down','Up']); self.direction.currentTextChanged.connect(lambda v:self.set_value('direction',v))
        l.addLayout(row(label('Pattern'),self.effect,None,label('Direction'),self.direction))
        colors=row(label('Colors'))
        self.palette_buttons=[]
        for i,c in enumerate(self.p['palette']):
            b=ColorButton(c,f'Palette color {i+1}'); b.chosen.connect(lambda c,i=i:self.palette_change(i,c)); self.palette_buttons.append(b); colors.addWidget(b)
        colors.addStretch(); l.addLayout(colors)
        self.speed_control=SpeedControl(self.p['speed'])
        self.speed=self.speed_control.slider;self.speed_value=self.speed_control.percentage
        self.speed_control.valueChanged.connect(lambda value:self.set_value('speed',value));l.addWidget(self.speed_control)
        l.addStretch()
        return w

    def build_paint(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(18,16,18,16); l.setSpacing(13)
        self.brush=ColorButton('#2fe8ff','Brush color')
        self.paint_toggle=button('Brush mode',kind='small'); self.paint_toggle.setCheckable(True)
        self.paint_toggle.setToolTip('Turn on to paint keys by clicking or dragging. Turn off to select keys.')
        self.paint_toggle.toggled.connect(lambda b:setattr(self.canvas,'paint_mode',b))
        l.addLayout(row(label('Brush'),self.brush,self.paint_toggle,None,button('Undo',self.undo,'small'),button('Redo',self.redo,'small')))
        self.selection_label=label('No keys selected','muted'); l.addWidget(self.selection_label)
        groups=row()
        for name in ['All','WASD','Arrows','Function','Numpad','Left half','Right half']:
            groups.addWidget(button(name,lambda checked=False,n=name:self.select_group(n),'small'))
        groups.addStretch(); l.addLayout(groups)
        reset=button('Reset selected',self.clear_selected); reset.setToolTip('Remove painted colors from selected keys so they follow the pattern again.')
        l.addLayout(row(button('Paint selected',self.paint_selected,'primary'),reset,button('Deselect',self.clear_selection,'quiet'),None))
        clear=button('Clear all paint',self.clear_overrides,'quiet'); clear.setToolTip('Remove every painted color from this keyboard. The pattern stays in place.')
        l.addLayout(row(clear,None)); l.addStretch()
        return w

    def build_audio(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(18,14,18,12); l.setSpacing(9)
        self.source_combo=QComboBox(); self.source_combo.setMinimumWidth(250); self.source_combo.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.source_combo.setAccessibleName('Audio input or playback source'); self.source_combo.currentIndexChanged.connect(self.source_changed)
        self.audio_start=button('Listen',self.toggle_audio,'primary')
        self.audio_start.setToolTip('Start or stop live audio analysis. Nothing is recorded or uploaded.')
        l.addLayout(row(self.source_combo,button('Refresh',self.refresh_audio,'small'),self.audio_start))
        self.audio_text=label(self.audio_status,'muted'); self.audio_text.setWordWrap(True); l.addWidget(self.audio_text)
        self.spectrum=Spectrum(); l.addWidget(self.spectrum)
        bands=row(spacing=18); self.band_buttons=[]
        for i,(lo,hi,name) in enumerate(BANDS):
            col=QVBoxLayout(); col.setSpacing(4); b=ColorButton(self.p['audio']['colors'][i],f'{name} color · {lo}–{hi} Hz')
            b.chosen.connect(lambda c,i=i:self.band_change(i,c)); self.band_buttons.append(b)
            col.addWidget(b); col.addWidget(label(name)); bands.addLayout(col)
        bands.addStretch(); l.addLayout(bands)
        gainrow,self.gain,self.gain_value=self.slider_row('Sensitivity',-12,36,lambda v:self.audio_value('gain',v))
        smoothrow,self.smoothing,self.smoothing_value=self.slider_row('Smoothing',0,95,lambda v:self.audio_value('smoothing',v))
        tune=row(gainrow,smoothrow,spacing=28); l.addLayout(tune)
        self.channel_mode=QComboBox(); self.channel_mode.addItems(['Auto','Mono mirror']); self.channel_mode.currentTextChanged.connect(lambda v:self.audio_value('channel_mode',v))
        self.channel_mode.setToolTip('Auto keeps stereo channels separate and mirrors mono sources. Mono mirror combines both channels.')
        test=button('Test L / R',self.audio_test,'small'); test.setToolTip('Preview left, right, then both sides. No sound is played or captured.')
        l.addLayout(row(label('Channels'),self.channel_mode,test,None))
        return w

    def error(self,title,e): QMessageBox.warning(self,title,str(e))
    def checkpoint(self):
        self.undo_stack.append(copy.deepcopy(self.p)); self.undo_stack=self.undo_stack[-60:]; self.redo_stack.clear()
    def changed(self):
        if self.loading: return
        self.dirty_label.setText('Unsaved changes')
        self.debounce.start(); self.update_labels()
    def set_value(self,k,v):
        if self.loading: return
        if self.p[k]!=v:
            if k=='speed':
                # Preserve the current animation position while changing its pace.
                self.phase*=animation_rate(self.p['speed'])/animation_rate(v)
            self.p[k]=v; self.changed()
    def effect_changed(self,text):
        if self.loading: return
        self.p['effect']=text
        if text!='Audio': self.stop_audio()
        elif self.active and not self.paused: self.start_audio()
        self.changed()
    def show_patterns(self): self.show_presets()

    def show_presets(self):
        self.library.refresh_state();self.pages.setCurrentIndex(0)
        self.presets_nav.setChecked(True);self.customize_nav.setChecked(False)
        self.profiles.clearSelection()

    def show_editor(self):
        self.library.preview_timer.stop();self.pages.setCurrentIndex(1)
        self.presets_nav.setChecked(False);self.customize_nav.setChecked(True)
        if self.profiles.currentItem():self.profiles.currentItem().setSelected(True)

    def use_pattern(self,name,keep_colors=False):
        if name not in PATTERNS:return
        if self.selected_device and static_only(self.selected_device) and name in ANIMATED:return
        self.checkpoint();self.p['effect']=name
        if not keep_colors:self.p['palette']=list(PALETTES[PATTERNS[name]['palette']])
        if name=='Rain':self.p['direction']='Down'
        if name!='Audio':self.stop_audio()
        elif self.active and not self.paused:self.start_audio()
        self.load_controls();self.changed()
        self.tabs.setCurrentIndex(2 if name=='Audio' else 0)
        self.show_editor()

    def palette_change(self,i,c): self.checkpoint(); self.p['palette'][i]=c; self.changed()
    def band_change(self,i,c): self.checkpoint(); self.p['audio']['colors'][i]=c; self.changed()
    def audio_value(self,k,v):
        if self.loading: return
        self.p['audio'][k]=v; self.changed()
    def update_labels(self):
        self.speed_control.setValue(self.p['speed']); self.brightness_control.setValue(self.p['brightness'])
        self.gain_value.setText(f"{int(self.p['audio']['gain']):+d} dB"); self.smoothing_value.setText(f"{int(self.p['audio']['smoothing'])}%")
        animated=self.p['effect'] in ANIMATED and self.p['effect']!='Audio'; self.speed_control.setEnabled(animated)
        self.direction.setEnabled(self.layout.spatial and self.p['effect'] in DIRECTIONAL)
        limited=bool(self.selected_device and static_only(self.selected_device))
        self.tabs.setTabEnabled(2,not limited)
        self.tabs.setTabText(1,'Paint keys' if self.layout.spatial else 'Paint lights')
        for i,effect in enumerate(EFFECTS):self.effect.model().item(i).setEnabled(not limited or effect not in ANIMATED)
        self.canvas.audio=self.p['effect']=='Audio'
        info=PATTERNS[self.p['effect']]
        for b in self.palette_buttons:b.setEnabled(info['uses_palette'])
        self.effect.setToolTip(info['description']+' Painted keys keep their own colors.')
        if hasattr(self,'library'):
            self.library.limited=limited
            if self.pages.currentIndex()==0:self.library.preview_timer.start()
    def load_controls(self):
        old=self.loading; self.loading=True
        self.effect.setCurrentText(self.p['effect']); self.direction.setCurrentText(self.p['direction'])
        self.speed_control.setValue(self.p['speed']); self.brightness_control.setValue(self.p['brightness'])
        for i,b in enumerate(self.palette_buttons): b.set_color(self.p['palette'][i])
        for i,b in enumerate(self.band_buttons): b.set_color(self.p['audio']['colors'][i])
        self.gain.setValue(int(self.p['audio']['gain'])); self.smoothing.setValue(int(self.p['audio']['smoothing']))
        self.channel_mode.setCurrentText(self.p['audio']['channel_mode'])
        idx=self.source_combo.findData(self.p['audio']['source'])
        if idx<0 and not self.p['audio']['source'] and self.source_combo.count():
            idx=0; self.p['audio']['source']=self.source_combo.itemData(0)
        self.source_combo.setCurrentIndex(idx)
        self.loading=old; self.update_labels(); self.selection_changed()
        self.dirty_label.setText('Unsaved changes' if self.p!=self.store.get(self.p['id']) else 'Saved')
    def persist_draft(self):
        if self.loading: return
        try:
            if self.p==self.store.get(self.p['id']): self.store.drafts.pop(self.p['id'],None)
            else: self.store.drafts[self.p['id']]=copy.deepcopy(self.p)
            self.store.last=self.p['id']; self.store.save()
        except Exception as e: self.error('Could not keep the draft',e)
    def reload_profiles(self):
        self.profiles.blockSignals(True); self.profiles.clear()
        for p in self.store.profiles:
            item=QListWidgetItem(p['name']); item.setData(Qt.UserRole,p['id']); item.setToolTip(p['effect']); self.profiles.addItem(item)
            if p['id']==self.p['id']: self.profiles.setCurrentItem(item)
        self.profiles.blockSignals(False)
    def switch_profile(self,item,previous):
        if self.loading or not item: return
        self.persist_draft(); self.stop_audio(); self.store.last=item.data(Qt.UserRole)
        self.p=copy.deepcopy(self.store.drafts.get(self.store.last,self.store.get())); self.undo_stack=[]; self.redo_stack=[]
        self.load_controls(); self.store.save()
        self.show_editor()
        if self.p['effect']=='Audio':
            self.tabs.setCurrentIndex(2)
            if self.active and not self.paused: self.start_audio()
    def save_profile(self):
        try: self.store.commit(self.p); self.dirty_label.setText('Saved'); self.reload_profiles()
        except Exception as e: self.error('Could not save profile',e)
    def add_profile(self,p):
        self.persist_draft()
        try:
            self.store.commit(p); self.stop_audio(); self.p=p; self.reload_profiles(); self.load_controls();self.show_editor()
            if self.active and not self.paused and p['effect']=='Audio': self.start_audio()
        except Exception as e: self.error('Could not add profile',e)
    def new_profile(self):
        name,ok=QInputDialog.getText(self,'New profile','Give your look a name:')
        if ok and name.strip(): self.add_profile(new_profile(name.strip()[:60]))
    def duplicate(self):
        p=copy.deepcopy(self.p); p['id']=uuid.uuid4().hex; p['name']=(p['name'][:53]+' copy'); self.add_profile(p)
    def rename(self):
        name,ok=QInputDialog.getText(self,'Rename profile','Profile name:',text=self.p['name'])
        if ok and name.strip(): self.p['name']=name.strip()[:60]; self.save_profile()
    def delete(self):
        if len(self.store.profiles)<=1: return self.error('Keep one profile','Create another profile before deleting your last one.')
        if QMessageBox.question(self,'Delete profile',f'Delete “{self.p["name"]}” and its local draft?')!=QMessageBox.Yes: return
        self.debounce.stop(); self.store.profiles=[p for p in self.store.profiles if p['id']!=self.p['id']]
        self.store.drafts.pop(self.p['id'],None); self.store.last=self.store.profiles[0]['id']; self.p=self.store.get(); self.store.save()
        self.stop_audio(); self.reload_profiles(); self.load_controls()
        if self.active and not self.paused and self.p['effect']=='Audio': self.start_audio()
    def import_profile(self):
        path,_=QFileDialog.getOpenFileName(self,'Import Prism profile','','Prism profile (*.json)')
        if not path: return
        self.persist_draft()
        try:
            p=self.store.import_file(path); self.stop_audio(); self.p=p; self.reload_profiles(); self.load_controls();self.show_editor()
            if self.active and not self.paused and p['effect']=='Audio': self.start_audio()
        except Exception as e: self.error('Could not import profile',e)
    def export_profile(self):
        safe=''.join(c for c in self.p['name'] if c.isalnum() or c in ' -_') or 'Prism profile'
        path,_=QFileDialog.getSaveFileName(self,'Export Prism profile',safe+'.prism.json','Prism profile (*.json)')
        if path:
            try: self.store.export_file(path,self.p)
            except Exception as e: self.error('Could not export profile',e)
    def restore_saved(self):
        self.checkpoint(); self.stop_audio(); self.p=self.store.get(self.p['id']); self.load_controls(); self.persist_draft()
        if self.active and not self.paused and self.p['effect']=='Audio': self.start_audio()
    def preset(self,name):
        self.checkpoint(); self.stop_audio(); self.p['palette']=PALETTES[name].copy(); self.p['effect']='Gradient'; self.load_controls(); self.changed();self.show_editor()
    def selection_changed(self): self.selection_label.setText(f'{len(self.canvas.selected)} selected · {len(self.paint_colors)} painted')
    def select_group(self,name):
        self.canvas.selected={k.id for k in self.layout.keys if name=='All' or (name=='WASD' and k.label in ('W','A','S','D')) or k.group==name or (self.layout.spatial and name=='Left half' and k.x+k.w/2<self.layout.width/2) or (self.layout.spatial and name=='Right half' and k.x+k.w/2>=self.layout.width/2)}
        self.canvas.update(); self.selection_changed()
    def clear_selection(self): self.canvas.selected.clear(); self.canvas.update(); self.selection_changed()
    def paint_selected(self):
        if not self.canvas.selected: return self.error('Select some keys','Click keys on the keyboard or choose a group such as WASD.')
        self.checkpoint()
        for k in self.canvas.selected: self.paint_colors[k]=self.brush.color
        self.changed(); self.selection_changed()
    def brush_key(self,k,first):
        if first: self.checkpoint()
        self.paint_colors[k]=self.brush.color; self.changed(); self.selection_changed()
    def clear_selected(self):
        self.checkpoint()
        for k in self.canvas.selected: self.paint_colors.pop(k,None)
        self.changed(); self.selection_changed()
    def clear_overrides(self): self.checkpoint(); self.paint_colors.clear(); self.changed(); self.selection_changed()
    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.p)); self.stop_audio(); self.p=self.undo_stack.pop(); self.load_controls(); self.changed()
            if self.active and not self.paused and self.p['effect']=='Audio': self.start_audio()
    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.p)); self.stop_audio(); self.p=self.redo_stack.pop(); self.load_controls(); self.changed()
            if self.active and not self.paused and self.p['effect']=='Audio': self.start_audio()

    def refresh_audio(self):
        running=self.capture.stream is not None; self.stop_audio(); saved=self.p['audio']['source']
        try:
            sources=self.capture.refresh(); self.source_combo.blockSignals(True); self.source_combo.clear()
            for s in sources:
                prefix='PC audio' if s['loopback'] else 'Microphone'; suffix=' · mono' if s['channels']==1 else ' · 2 ch'
                self.source_combo.addItem(f'{prefix}  ·  {s["name"]}{suffix}',s['id'])
            index=self.source_combo.findData(saved)
            if index<0 and not saved and sources: index=0; self.p['audio']['source']=sources[0]['id']
            self.source_combo.setCurrentIndex(index); self.source_combo.blockSignals(False)
            self.audio_status='Ready to listen' if index>=0 else 'Saved source unavailable. Choose a connected microphone or playback source.'
            if running and index>=0: self.start_audio()
        except Exception as e:
            self.source_combo.blockSignals(False); self.audio_status=f'Audio devices could not be opened: {e}'
        self.update_audio_text()
    def update_audio_text(self):
        text=self.audio_status
        if text=='Mono input · mirrored to both halves':text='Listening · Mono'
        elif text=='2-channel input · left and right analyzed separately':text='Listening · Stereo'
        elif text.endswith(' · mono mirror selected') and text.startswith(('Mono input','2-channel input')) and 'buffer recovered' not in text:text='Listening · Mono mirror'
        self.audio_text.setText(text); self.audio_text.setToolTip(self.audio_status)

    def source_changed(self,index):
        if self.loading or index<0: return
        running=self.capture.stream is not None; self.stop_audio(); self.p['audio']['source']=self.source_combo.itemData(index); self.changed()
        if running: self.start_audio()
        else: self.audio_status='Ready to listen'
    def start_audio(self):
        if self.capture.stream is not None: return True
        if not self.p['audio']['source']:
            self.audio_status='Choose a microphone or PC audio source first.'; return False
        try:
            self.analyzer.reset(); self.capture.start(self.p['audio']['source']); self.audio_start.setText('Stop listening'); return True
        except Exception as e:
            self.audio_status=f'Cannot listen to this source: {e}. Use Refresh, then select a source.'
            self.audio_start.setText('Listen'); self.update_audio_text(); return False
    def stop_audio(self):
        try: self.capture.stop()
        except Exception: logging.exception('Could not stop audio')
        self.analyzer.reset(); self.test_until=0
        if hasattr(self,'audio_start'): self.audio_start.setText('Listen')
        self.audio_status='Audio stopped'
    def toggle_audio(self):
        if self.capture.stream: self.stop_audio()
        else:
            self.p['effect']='Audio'; self.load_controls(); self.changed(); self.start_audio()
    def audio_test(self):
        self.stop_audio(); self.p['effect']='Audio'; self.load_controls(); self.changed(); self.test_until=time.monotonic()+6
        self.audio_status='Testing · Left → Right → Both'
    def apply(self):
        if self.offline: return self.error('Preview session','This test session has hardware access disabled.')
        if not self.worker: return self.show_keyboards()
        if self.selected_device and static_only(self.selected_device) and self.p['effect'] in ANIMATED: return self.error('Static lighting only','This keyboard automatically saves colors. Choose a static pattern from the library; animations and audio streaming are unavailable.')
        if self.p['effect']=='Audio' and not self.start_audio(): self.tabs.setCurrentIndex(2); return
        self.active=True; self.paused=False; self.worker.enable(True); self.apply_btn.setText('Reapply look'); self.pause_btn.setText('Pause'); self.pause_btn.setEnabled(True)
    def pause(self):
        if not self.active: return
        self.paused=not self.paused; self.worker.enable(not self.paused); self.pause_btn.setText('Resume' if self.paused else 'Pause')
        if self.paused: self.stop_audio()
        elif self.p['effect']=='Audio': self.start_audio()
    def release(self,rainbow=False):
        self.active=False; self.paused=False; self.stop_audio(); self.apply_btn.setText('Apply to keyboard'); self.pause_btn.setEnabled(False); self.pause_btn.setText('Pause')
        if self.worker: self.worker.request('rainbow' if rainbow else 'release')

    def tick(self):
        now=time.monotonic(); dt=min(.2,now-self.last_tick); self.last_tick=now
        if not self.paused: self.phase+=dt
        levels=np.zeros((2,6))
        if self.test_until>now:
            segment=int((6-(self.test_until-now))//2)
            if segment in (0,2): levels[0,0]=.95
            if segment in (1,2): levels[1,4]=.95
        elif self.p['effect']=='Audio' and self.capture.stream is not None:
            samples,self.audio_status=self.capture.read()
            if samples is not None:
                a=self.p['audio']; levels=self.analyzer.analyze(samples,self.capture.rate,a['gain'],a['smoothing'],a['channel_mode']=='Mono mirror',dt)
                if a['channel_mode']=='Mono mirror': self.audio_status+=' · mono mirror selected'
            else:
                self.analyzer.reset(); self.audio_start.setText('Listen')
        elif self.test_until:
            self.test_until=0; self.audio_status='Test finished'
        colors=render_layout(self.p,self.phase,levels,self.layout)
        self.canvas.colors=colors; self.canvas.update()
        self.spectrum.levels=levels; self.spectrum.colors=self.p['audio']['colors']; self.spectrum.update()
        self.update_audio_text()
        if self.active and not self.paused and self.worker: self.worker.submit(tuple(colors.get(k,(0,0,0)) for k in self.layout.led_ids) if self.selected_device else matrix_frame(colors))
        self.frame_counter+=1
        if self.frame_counter%8==0:
            s=self.worker.status() if self.worker else dict(state='Preview',message='Hardware disabled for this preview.',frames=0,acks=0,firmware='')
            state=s['state']; message=s['message']
            if self.paused: title='Paused'
            elif state=='Live' and self.active: title='Live'
            elif state=='Ready': title='Connected'
            elif state=='Unavailable': title='Reconnecting…'
            else: title=state
            self.status_label.setText(title+' · '+self.p['effect'])
            self.status_label.setToolTip(message)
            self.status_label.setStyleSheet('color:'+('#6bf3bc' if state in ('Live','Ready') else '#f2ba79')+';font-weight:700;')
            detail=message if state=='Unavailable' else ('Press Apply for each change.' if self.selected_device and static_only(self.selected_device) else '')
            self.status_detail.setText(detail); self.status_detail.setVisible(bool(detail))

    def show_help(self):
        d=QDialog(self); d.setWindowTitle('Prism · help & connection'); d.resize(690,650); l=QVBoxLayout(d)
        t=QTextBrowser(); t.setOpenExternalLinks(True)
        s=self.worker.status() if self.worker else {}
        import html
        t.setHtml(f'''<h2>Quick start</h2>
        <p><b>Presets → Use preset → Apply to keyboard.</b><br>Customize colors, speed, keys or audio. <b>Save look</b> keeps your changes.</p>
        <p>Edits apply live after Apply. Keep Prism open for animations. <b>Pause</b> stops lighting updates and audio. <b>More → Restore saved look</b> discards your draft.</p>
        <h3>Paint & audio</h3>
        <p>Select keys, then <b>Paint selected</b>, or turn on <b>Brush mode</b> and drag. Painted keys keep their colors over the pattern. <b>Reset selected</b> returns them to the pattern.</p>
        <p>For music, choose <b>PC audio → Listen → Apply</b>. Mono is mirrored; stereo uses left and right halves. Only the first two channels are analyzed. Hover over colors for frequency ranges. Audio is never recorded or uploaded.</p>
        <h3>Connection</h3><p><b>{html.escape(s.get('state','Preview'))}</b>: {html.escape(s.get('message',''))}<br>
        Accepted commands: {s.get('acks',0)} · Frames: {s.get('frames',0)}</p>
        <p>If colors flicker, close other lighting apps, then Retry. Accepted commands do not verify the physical lights. Prism does not stop other apps.</p>
        <p><b>Release</b> stops updates and restores the initial brightness (direct USB) or initial colors (bridge). <b>Rainbow & release</b> requests a cycling effect. Neither reconstructs an earlier animated effect.</p>
        <p>Prism controls lighting only. For actuation, Rapid Trigger and key assignments, see the <a href="https://dl.razerzone.com/master-guides/RazerSynapse3/HUNTSMANV3PRO-00000678-en.pdf">keyboard guide</a>.</p>
        <p><small>Prism {VERSION} · GPL-2.0-or-later · OpenRazer / openrazer-win, Qt for Python, NumPy, PyAudioWPatch. Independent of Razer.</small></p>''')
        l.addWidget(t)
        l.addLayout(row(button('Retry connection',lambda:self.worker.request('retry') if self.worker else None),button('Release keyboard',lambda:self.release()),button('Rainbow & release',lambda:self.release(True))))
        l.addLayout(row(button('Save diagnostics',self.save_diagnostics,'quiet'),None,button('Done',d.accept,'primary'))); d.exec()
    def save_diagnostics(self):
        path,_=QFileDialog.getSaveFileName(self,'Save local diagnostics','Prism diagnostics.json','JSON (*.json)')
        if path:
            value=dict(app=APP_NAME,version=VERSION,keyboard=self.layout.name,status=self.worker.status() if self.worker else {},audio_status=self.audio_status)
            try: atomic_json(path,value)
            except Exception as e: self.error('Could not save diagnostics',e)
    def closeEvent(self,event):
        self.timer.stop(); self.debounce.stop(); self.persist_draft()
        try: self.capture.close()
        except Exception: logging.exception('Audio cleanup failed')
        if self.worker: self.worker.shutdown()
        self.bridge.stop()
        event.accept()

def package_check(app,report_path):
    """Noninteractive runtime check. USB writes require explicit --check-live."""
    import tempfile
    report_path=Path(report_path).resolve(); report_path.parent.mkdir(parents=True,exist_ok=True)
    report=dict(app=APP_NAME,version=VERSION,frozen=bool(getattr(sys,'frozen',False)))
    with tempfile.TemporaryDirectory(prefix='prism-check-',dir=report_path.parent) as temporary:
        live='--check-live' in sys.argv
        window=Studio(temporary,offline=not live)
        try:
            window.show(); app.processEvents()
            window.select_group('WASD'); window.paint_selected()
            assert all(k in window.p['overrides'] for k in 'WASD')
            window.undo(); assert not window.p['overrides']
            window.redo(); assert len(window.p['overrides'])==4
            window.save_profile(); saved=ProfileStore(temporary).get()
            assert len(saved['overrides'])==4
            file=Path(temporary)/'export.json'; window.store.export_file(file,window.p)
            imported=window.store.import_file(file); assert imported['id']!=window.p['id']
            report.update(ui_constructed=True,profile_save_and_import=True,paint_undo_redo=True,
                          audio_sources=len(window.capture.sources),matrix_bytes=len(matrix_frame(render_colors(window.p,0))))
            if live:
                def run_for(seconds):
                    until=time.monotonic()+seconds
                    while time.monotonic()<until: app.processEvents(); time.sleep(.012)
                window.p['overrides']={}; window.p['effect']='Rainbow wave'; window.load_controls(); window.apply(); run_for(2.5)
                first=window.worker.status(); assert first['state']=='Live' and first['frames']>=10,first
                window.pause(); run_for(.2); assert window.worker.status()['state']=='Paused'
                window.p['effect']='Audio'; window.load_controls(); window.apply(); run_for(2.5)
                second=window.worker.status(); assert second['state']=='Live' and second['frames']>=first['frames']+10,second
                assert window.capture.last_callback>0,'No live audio callback'
                window.preset('Neon nights'); run_for(.3); window.pause(); run_for(.2)
                assert window.capture.stream is None
                report['packaged_live_pipeline']=dict(result='PASS',animation_frames=first['frames'],
                    frames_after_audio=second['frames'],acks=second['acks'],pause_verified=True,audio_stopped=True)
            else:
                from device import Huntsman
                dev=Huntsman()
                try:
                    dev.connect(); report['keyboard_read_only']=dict(connected=True,firmware=dev.firmware,interface=dev.interface,acks=dev.acks)
                except Exception as e: report['keyboard_read_only']=dict(connected=False,error=str(e))
                finally: dev.close()
            report['result']='PASS'
        except Exception as e: report.update(result='FAIL',error=str(e))
        finally: window.close(); app.processEvents()
    atomic_json(report_path,report)
    return 0 if report.get('result')=='PASS' else 1

def main():
    bridge_check='--check-bridge' in sys.argv
    pattern_check='--check-patterns' in sys.argv
    resize_check='--check-resize' in sys.argv
    speed_check='--check-speed' in sys.argv
    checking='--check-package' in sys.argv or bridge_check or pattern_check or resize_check or speed_check
    if checking: os.environ['QT_QPA_PLATFORM']='offscreen'
    QApplication.setApplicationName(APP_NAME); QApplication.setOrganizationName('Prism Local')
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    if checking:
        for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
            font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
            if font.exists():QFontDatabase.addApplicationFont(str(font))
    if speed_check:
        from verification_speed import check_speed
        return check_speed(app,Studio,sys.argv[sys.argv.index('--check-speed')+1])
    if resize_check:
        from verification_resize import check_resize
        return check_resize(app,Studio,sys.argv[sys.argv.index('--check-resize')+1])
    if bridge_check:
        from verification_v2 import check_bridge
        return check_bridge(app,Studio,sys.argv[sys.argv.index('--check-bridge')+1])
    if pattern_check:
        from verification_patterns import check_patterns
        return check_patterns(app,Studio,sys.argv[sys.argv.index('--check-patterns')+1])
    if checking: return package_check(app,sys.argv[sys.argv.index('--check-package')+1])
    if sys.platform=='win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Prism.KeyboardStudio.1')
    directory=Path(os.environ.get('PRISM_DATA_DIR',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'PrismKeyboardStudio')))
    directory.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(directory/'studio.log',maxBytes=256000,backupCount=2,encoding='utf-8')
    logging.basicConfig(level=logging.WARNING,handlers=[handler],format='%(asctime)s %(levelname)s %(message)s')
    lock=QLockFile(str(directory/'studio.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None,APP_NAME,f'Prism is already open. Close its current window, then reopen this shortcut to use version {VERSION}.'); return 0
    try:
        window=Studio(directory,offline='--preview-only' in sys.argv); window.show()
        if '--icon' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--icon')+1]); window.make_icon().pixmap(128,128).save(str(out))
        return app.exec()
    except Exception as e:
        logging.exception('Startup failed'); QMessageBox.critical(None,'Prism could not start',str(e)); return 1
    finally: lock.unlock()

if __name__=='__main__': sys.exit(main())
