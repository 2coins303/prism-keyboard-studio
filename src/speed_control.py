"""Extended animation speed with precise entry and quick choices."""
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSlider,QSpinBox,QPushButton
from model import MAX_SPEED

class SpeedControl(QWidget):
    valueChanged=Signal(int)

    def __init__(self,value=45,parent=None):
        super().__init__(parent)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        top=QHBoxLayout();top.setSpacing(10)
        title=QLabel('Speed');title.setMinimumWidth(82);top.addWidget(title)
        self.slider=QSlider(Qt.Horizontal);self.slider.setRange(0,MAX_SPEED);self.slider.setPageStep(50)
        self.slider.setAccessibleName('Animation speed');top.addWidget(self.slider,1)
        self.percentage=QSpinBox();self.percentage.setRange(0,MAX_SPEED);self.percentage.setSuffix('%')
        self.percentage.setAlignment(Qt.AlignCenter);self.percentage.setMinimumWidth(100);self.percentage.setKeyboardTracking(False)
        self.percentage.setAccessibleName('Animation speed percentage');top.addWidget(self.percentage)
        title.setBuddy(self.slider);layout.addLayout(top)
        quick=QHBoxLayout();quick.setSpacing(8);quick_label=QLabel('Quick');quick_label.setMinimumWidth(82);quick.addWidget(quick_label)
        self.quick_buttons={}
        for amount in (100,250,500,1000):
            button=QPushButton(f'{amount}%');button.setObjectName('small');button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False,v=amount:self.changed(v))
            quick.addWidget(button);self.quick_buttons[amount]=button
        quick.addStretch();layout.addLayout(quick)
        self.setToolTip('The original 0–100% speeds are unchanged. 1000% runs ten times faster than 100%.')
        self.setValue(value);self.slider.valueChanged.connect(self.changed);self.percentage.valueChanged.connect(self.changed)

    def setValue(self,value):
        value=int(value)
        for control in (self.slider,self.percentage):
            blocked=control.blockSignals(True);control.setValue(value);control.blockSignals(blocked)
        for amount,button in self.quick_buttons.items():button.setChecked(value==amount)

    def changed(self,value):
        self.setValue(value);self.valueChanged.emit(value)
