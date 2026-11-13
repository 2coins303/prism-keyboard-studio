"""Searchable pattern gallery with rendered lighting previews. GPL-2.0-or-later."""
from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QPixmap,QPainter,QColor
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QWidget,QLabel,
    QLineEdit,QComboBox,QCheckBox,QScrollArea,QFrame,QPushButton)
import numpy as np
from patterns import PATTERNS,EXTRA_PATTERNS
from model import EFFECTS,ANIMATED,PALETTES,Key,new_profile,render_colors
from bridge import static_only
from brightness_control import BrightnessControl

def thumbnail(effect,palette,brightness=100):
    keys=[Key(str(i),'',i%18,i//18,1,1,i//18,i%18) for i in range(90)]
    p=new_profile(effect=effect,palette=palette);p['brightness']=brightness
    if effect=='Rain':p['direction']='Down'
    levels=np.array([[.8,.4,.9,.6,.35,.7],[.3,.7,.5,.9,.6,.4]])
    colors=render_colors(p,3.75,levels,keys,18,5)
    pix=QPixmap(270,78);pix.fill(QColor('#11101c'));painter=QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen)
    for k in keys:
        painter.setBrush(QColor(*colors[k.id]));painter.drawRoundedRect(QRectF(3+k.x*14.7,4+k.y*14.1,11.7,10.7),2,2)
    painter.end();return pix

class PatternBrowser(QDialog):
    def __init__(self,studio,embedded=False):
        super().__init__(studio);self.studio=studio;self.embedded=embedded;self.cards=[];self.pixmaps={};self.columns=3
        if embedded:self.setWindowFlags(Qt.Widget)
        self.preview_brightness=None
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self.rebuild)
        self.limited=bool(studio.selected_device and static_only(studio.selected_device))
        self.setWindowTitle('Prism · presets');self.resize(1030,770)
        outer=QVBoxLayout(self);outer.setContentsMargins(22,20,22,18);outer.setSpacing(14)
        title=QLabel('Presets');title.setStyleSheet('font-size:29px;font-weight:750;color:#eed7ff;');outer.addWidget(title)
        controls=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Search presets');self.search.setAccessibleName('Search presets');controls.addWidget(self.search,1)
        self.category=QComboBox();self.category.addItem('All presets');self.category.addItems(sorted({p['category'] for p in PATTERNS.values()}));controls.addWidget(self.category)
        outer.addLayout(controls)
        themes=QHBoxLayout();themes.setSpacing(8);themes.addWidget(QLabel('Colors'))
        self.theme_buttons={}
        for name in ('Neon nights','Cyber mint','Solar flare','Arctic'):
            b=QPushButton(name);b.setObjectName('small');b.setCursor(Qt.PointingHandCursor);b.setAutoDefault(False)
            palette=PALETTES[name]
            b.setStyleSheet(f'QPushButton {{ background:#30243f; color:#f5eaff;border:2px solid {palette[0]};padding:9px 14px;border-radius:21px; }} QPushButton:hover {{ background:#513568;border-color:{palette[1]}; }}')
            b.setToolTip('Apply the '+name+' color palette')
            b.clicked.connect(lambda checked=False,n=name:self.choose_theme(n));themes.addWidget(b);self.theme_buttons[name]=b
        themes.addStretch();outer.addLayout(themes)
        opts=QHBoxLayout();self.keep_colors=QPushButton('Keep my colors');self.keep_colors.setObjectName('small');self.keep_colors.setCheckable(True);self.keep_colors.setAutoDefault(False)
        self.keep_colors.setCursor(Qt.PointingHandCursor);self.keep_colors.setToolTip('Turn on to keep your current colors when choosing a pattern.')
        opts.addWidget(self.keep_colors);opts.addStretch();self.count=QLabel();opts.addWidget(self.count);outer.addLayout(opts)
        if not embedded:
            self.brightness_control=BrightnessControl(studio.p['brightness'])
            self.brightness_control.valueChanged.connect(self.change_brightness);outer.addWidget(self.brightness_control)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.panel=QWidget();self.grid=QGridLayout(self.panel);self.grid.setSpacing(12);self.scroll.setWidget(self.panel);outer.addWidget(self.scroll,1)
        self.notice=QLabel();self.notice.setWordWrap(True);self.notice.setStyleSheet('color:#b9adcc;');outer.addWidget(self.notice)
        if not embedded:
            close=QPushButton('Done');close.setAutoDefault(False);close.clicked.connect(self.reject);outer.addWidget(close)
        self.search.textChanged.connect(self.rebuild);self.category.currentTextChanged.connect(self.rebuild);self.keep_colors.toggled.connect(self.rebuild);self.rebuild()
    def refresh_state(self):
        self.limited=bool(self.studio.selected_device and static_only(self.studio.selected_device))
        if not self.embedded:self.brightness_control.setValue(self.studio.p['brightness'])
        self.rebuild()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'scroll'):
            columns=max(1,min(3,(self.width()-60)//300))
            if columns!=self.columns:self.columns=columns;self.preview_timer.start(0)
    def rebuild(self):
        self.preview_timer.stop()
        self.notice.setText('Static presets only on this keyboard.' if self.limited else '')
        self.notice.setVisible(self.limited)
        brightness=self.studio.p['brightness']
        if brightness!=self.preview_brightness:self.pixmaps.clear();self.preview_brightness=brightness
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        self.cards=[];query=self.search.text().strip().casefold();category=self.category.currentText()
        featured=['Aurora','Fire','Ocean waves','Rain','Rainbow spiral','Comet']
        order=featured+[n for n in EXTRA_PATTERNS if n not in featured]+[n for n in EFFECTS if n not in EXTRA_PATTERNS]
        selected=[n for n in order if (category=='All presets' or PATTERNS[n]['category']==category) and query in (n+' '+PATTERNS[n]['description']).casefold()]
        self.count.setText(f'{len(selected)} presets')
        for index,name in enumerate(selected):
            info=PATTERNS[name];card=QFrame();card.setObjectName('card');box=QVBoxLayout(card);box.setContentsMargins(12,12,12,12);box.setSpacing(7)
            pal=tuple(self.studio.p['palette'] if self.keep_colors.isChecked() else PALETTES[info['palette']])
            key=(name,pal)
            if key not in self.pixmaps:self.pixmaps[key]=thumbnail(name,list(pal),brightness)
            visual=QLabel();visual.setPixmap(self.pixmaps[key]);visual.setAlignment(Qt.AlignCenter);box.addWidget(visual)
            title=QLabel(name);title.setStyleSheet('font-size:16px;font-weight:700;color:#f0dfff;');box.addWidget(title)
            card.setToolTip(info['description']);card.setAccessibleDescription(info['description'])
            available=not self.limited or name not in ANIMATED
            choose=QPushButton('Use preset' if available else 'Static only');choose.setEnabled(available);choose.setAutoDefault(False)
            choose.setCursor(Qt.PointingHandCursor);choose.setAccessibleName('Use '+name+' preset');choose.setToolTip(info['description']+' Painted colors stay in place.')
            choose.setObjectName('primary' if name==self.studio.p['effect'] else 'preset');choose.clicked.connect(lambda checked=False,n=name:self.choose(n));box.addWidget(choose)
            self.grid.addWidget(card,index//self.columns,index%self.columns);self.cards.append((name,card,choose))
        if not selected:
            empty=QLabel('No presets match. Try another name or choose All presets.');self.grid.addWidget(empty,0,0,1,self.columns)
        for col in range(3):self.grid.setColumnStretch(col,1 if col<self.columns else 0)
    def change_brightness(self,value):
        self.studio.set_value('brightness',value)
        # Update the keyboard immediately, then refresh thumbnails after dragging.
        self.preview_timer.start()
    def done(self,result):
        if self.embedded:return
        self.preview_timer.stop();super().done(result)
    def keyPressEvent(self,event):
        if self.embedded:QWidget.keyPressEvent(self,event)
        else:super().keyPressEvent(event)
    def choose(self,name):
        if self.limited and name in ANIMATED:return
        self.studio.use_pattern(name,self.keep_colors.isChecked())
        if not self.embedded:self.accept()
    def choose_theme(self,name):
        self.studio.preset(name)
        if not self.embedded:self.accept()
