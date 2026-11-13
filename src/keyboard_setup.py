"""In-app keyboard setup and exact-variant compatibility catalog."""
import html,json
from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QLineEdit,
    QTabWidget,QWidget,QTextBrowser,QListWidget,QSpinBox,QMessageBox,QTableWidget,QTableWidgetItem,
    QHeaderView,QDoubleSpinBox,QDialogButtonBox,QFileDialog)
from bridge import SDK,supports_direct
from managed_bridge import catalog
from layouts import validate_mapping
from model import atomic_json

class Job(QThread):
    finishedWork=Signal(object,str)
    def __init__(self,fn,parent):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.finishedWork.emit(self.fn(),'')
        except Exception as e:self.finishedWork.emit(None,str(e))

class KeyboardSetup(QDialog):
    def __init__(self,studio):
        super().__init__(studio);self.studio=studio;self.job=None;self.devices=[];self.models=catalog()['models']
        self.setWindowTitle('Prism · choose your keyboard');self.resize(920,680)
        outer=QVBoxLayout(self);tabs=QTabWidget();outer.addWidget(tabs)
        page=QWidget();l=QVBoxLayout(page);tabs.addTab(page,'Connect a keyboard')
        title=QLabel('Choose your keyboard');title.setStyleSheet('font-size:23px;font-weight:700;');l.addWidget(title)
        text=QLabel('Close other lighting apps first.');text.setWordWrap(True);l.addWidget(text)
        self.direct_btn=QPushButton('Use Huntsman V3 Pro');self.direct_btn.setToolTip('Connect the full-size Huntsman V3 Pro directly by USB.');self.direct_btn.clicked.connect(self.direct);l.addWidget(self.direct_btn)
        self.search=QLineEdit();self.search.setPlaceholderText('Search keyboards');l.addWidget(self.search)
        self.models_box=QComboBox();l.addWidget(self.models_box);self.search.textChanged.connect(self.filter_models);self.filter_models()
        self.model_note=QLabel();self.model_note.setWordWrap(True);l.addWidget(self.model_note);self.models_box.currentIndexChanged.connect(self.describe_model);self.describe_model()
        self.start_btn=QPushButton('Connect keyboard');self.start_btn.setObjectName('primary');self.start_btn.clicked.connect(self.start_bridge);l.addWidget(self.start_btn)
        self.state=QLabel('Ready to connect');self.state.setWordWrap(True);l.addWidget(self.state)
        self.list=QListWidget();l.addWidget(self.list,1)
        self.use=QPushButton('Use selected keyboard');self.use.setEnabled(False);self.use.clicked.connect(self.select);l.addWidget(self.use)
        advanced=QWidget();advanced_layout=QVBoxLayout(advanced)
        advanced_note=QLabel('Use an existing OpenRGB server on this PC.');advanced_note.setWordWrap(True);advanced_layout.addWidget(advanced_note)
        adv=QHBoxLayout();adv.addWidget(QLabel('Port'));self.port=QSpinBox();self.port.setRange(1024,65535);self.port.setValue(studio.bridge_port or 6742);adv.addWidget(self.port)
        self.existing=QPushButton('Connect');self.existing.clicked.connect(self.connect_existing);adv.addWidget(self.existing);advanced_layout.addLayout(adv);advanced_layout.addStretch()
        guide=QTextBrowser();guide.setOpenExternalLinks(True)
        guide.setHtml('''<h2>Keyboard support</h2><p>Check the exact USB variant in the catalog. Similar names, wireless versions and Bluetooth are not automatically supported.</p>
        <p>Huntsman V3 Pro 1532:02A6 was tested here. Other listed models have upstream OpenRGB 1.1 support and still need physical verification.</p>
        <h3>Connection</h3><p>Prism’s bundled OpenRGB helper runs locally for the selected keyboard and closes with Prism. It installs no drivers, firmware, services or startup entries. Low-level motherboard modules are omitted.</p>
        <p>Already running OpenRGB 1.1 or later? Start its SDK server on 127.0.0.1, then use Advanced. Prism leaves that server’s settings unchanged and does not stop it.</p>
        <h3>Layouts</h3><p>Use Adjust layout to correct key positions. Zones have less detail. Without physical coordinates, audio is mirrored. Painted colors are saved per device and layout; patterns and palettes follow your saved look.</p>
        <p>Unlisted variants and firmware-dependent QMK boards are not promised. Prism never flashes keyboards.</p>
        <p><a href="https://openrgb.org/releases.html">Official OpenRGB release</a> · <a href="https://openrgb.org/devices_1.1.html">Upstream support reference</a></p>''')
        tabs.addTab(guide,'Setup & limits')
        table=QWidget();tl=QVBoxLayout(table);tabs.addTab(table,f'{len(self.models)} USB variants')
        find=QLineEdit();find.setPlaceholderText('Search model, USB ID, or capability');tl.addWidget(find)
        grid=QTableWidget(len(self.models),5);grid.setHorizontalHeaderLabels(['Exact model','USB ID','Connection','Lighting','Evidence']);grid.setEditTriggers(QTableWidget.NoEditTriggers);grid.setWordWrap(True);grid.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);grid.setColumnWidth(0,290);grid.setColumnWidth(1,95);grid.setColumnWidth(2,160);grid.setColumnWidth(3,230);grid.setColumnWidth(4,240);tl.addWidget(grid)
        for row,m in enumerate(self.models):
            for col,value in enumerate([m['name'],m['vid']+':'+m['pid'],m['connection'],m['capability'],m['evidence']]):grid.setItem(row,col,QTableWidgetItem(value))
        grid.resizeRowsToContents()
        def filter_table(text):
            for i,m in enumerate(self.models):grid.setRowHidden(i,text.casefold() not in json.dumps(m).casefold())
        find.textChanged.connect(filter_table)
        tabs.addTab(advanced,'Advanced')
        self.done_btn=QPushButton('Done');self.done_btn.clicked.connect(self.accept);outer.addWidget(self.done_btn)
    def filter_models(self):
        query=self.search.text().casefold();self.models_box.clear()
        seen=set()
        for m in self.models:
            if query in (m['name']+' '+m['vid']+':'+m['pid']).casefold() and m['detector'] not in seen:
                self.models_box.addItem(m['name'],m);seen.add(m['detector'])
    def describe_model(self):
        m=self.models_box.currentData()
        if hasattr(self,'model_note'):
            self.model_note.setText(m['capability'].replace(' (layout supplied by bridge)','') if m else 'No exact variant found.')
            self.model_note.setToolTip(m['evidence'] if m else '')
    def busy(self,fn):
        for w in [self.start_btn,self.existing,self.done_btn,self.direct_btn,self.models_box,self.search,self.port]:w.setEnabled(False)
        self.use.setEnabled(False);self.state.setText('Starting connection…');self.list.clear()
        self.job=Job(fn,self);self.job.finishedWork.connect(self.result);self.job.start()
    def start_bridge(self):
        m=self.models_box.currentData()
        if not m:return
        self.studio.stop_connection()
        self.busy(lambda:self.studio.bridge.start(m))
    def connect_existing(self):
        self.studio.stop_connection();port=self.port.value()
        def work():
            sdk=SDK(port).connect()
            try:return sdk.devices()
            finally:sdk.close()
        self.studio.bridge_port=port;self.busy(work)
    def result(self,devices,error):
        if self.job:self.job.wait(2000)
        for w in [self.start_btn,self.existing,self.done_btn,self.direct_btn,self.models_box,self.search,self.port]:w.setEnabled(True)
        if error:self.state.setText(error);return
        if self.studio.bridge.process:self.studio.bridge_port=self.studio.bridge.port
        self.devices=[d for d in devices if d.type==5]
        for d in self.devices:
            note='direct colors available' if supports_direct(d) else 'no direct lighting mode'
            self.list.addItem(f'{d.name} · {len(d.leds)} lighting addresses · {note}')
        self.state.setText('Choose the keyboard to control.' if self.devices else 'No supported keyboard detected yet. Check its cable and exact USB variant, then start again.')
        if self.devices:self.list.setCurrentRow(0);self.use.setEnabled(True)
        if len(self.devices)==1 and self.devices[0].identity and supports_direct(self.devices[0]):self.select()
    def select(self):
        i=self.list.currentRow()
        if i<0:return
        d=self.devices[i]
        if not d.identity or sum(x.identity==d.identity for x in self.devices)!=1:
            self.state.setText('This keyboard has no unique identity. Connect one identical unit at a time.');return
        if not supports_direct(d):self.state.setText('This model cannot stream Prism effects through this bridge.');return
        self.studio.select_bridge(d);self.accept()
    def direct(self):
        try:self.studio.select_direct();self.accept()
        except Exception as e:self.state.setText(str(e))
    def reject(self):
        if self.job and self.job.isRunning():return
        super().reject()

class MappingDialog(QDialog):
    def __init__(self,studio):
        super().__init__(studio);self.studio=studio;self.setWindowTitle('Prism · physical key positions');self.resize(680,620)
        l=QVBoxLayout(self);t=QLabel('Set each light’s column and row. Start at 0, top left.');l.addWidget(t)
        self.grid=QTableWidget(len(studio.layout.keys),3);self.grid.setHorizontalHeaderLabels(['Lighting address','Column','Row']);self.grid.setColumnWidth(0,370);l.addWidget(self.grid)
        for i,k in enumerate(studio.layout.keys):
            item=QTableWidgetItem(k.label);item.setFlags(item.flags()&~Qt.ItemIsEditable);item.setData(Qt.UserRole,k.id);self.grid.setItem(i,0,item)
            for col,val in [(1,k.x),(2,k.y)]:
                s=QDoubleSpinBox();s.setRange(0,100);s.setSingleStep(.25);s.setValue(val);self.grid.setCellWidget(i,col,s)
        row=QHBoxLayout();save=QPushButton('Save layout');save.setObjectName('primary');save.clicked.connect(self.save);row.addWidget(save);reset=QPushButton('Reset layout');reset.setToolTip('Restore the layout supplied by the connection.');reset.clicked.connect(self.reset);row.addWidget(reset);l.addLayout(row)
    def save(self):
        try:
            values={self.grid.item(i,0).data(Qt.UserRole):[self.grid.cellWidget(i,1).value(),self.grid.cellWidget(i,2).value()] for i in range(self.grid.rowCount())}
            self.studio.save_mapping(values);self.accept()
        except Exception as e:QMessageBox.warning(self,'Check positions',str(e))
    def reset(self):self.studio.save_mapping(None);self.accept()
