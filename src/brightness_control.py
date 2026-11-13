"""Shared keyboard brightness control. GPL-2.0-or-later."""
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QSlider,QSpinBox

class BrightnessControl(QWidget):
    valueChanged=Signal(int)

    def __init__(self,value=85,parent=None):
        super().__init__(parent)
        layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14)
        title=QLabel('Brightness');layout.addWidget(title)
        self.slider=QSlider(Qt.Horizontal);self.slider.setRange(0,100)
        self.slider.setAccessibleName('Keyboard LED brightness')
        self.slider.setToolTip('Brightness for every pattern, audio effect, and painted key. 0% turns the LEDs off.')
        layout.addWidget(self.slider,1)
        self.percentage=QSpinBox();self.percentage.setRange(0,100);self.percentage.setSuffix('%')
        self.percentage.setAlignment(Qt.AlignCenter)
        self.percentage.setMinimumWidth(84);self.percentage.setKeyboardTracking(False)
        self.percentage.setAccessibleName('Keyboard LED brightness percentage')
        self.percentage.setToolTip('Enter a brightness from 0% to 100%.')
        title.setBuddy(self.slider);layout.addWidget(self.percentage)
        self.setValue(value)
        self.slider.valueChanged.connect(self.changed)
        self.percentage.valueChanged.connect(self.changed)

    def setValue(self,value):
        for control in (self.slider,self.percentage):
            blocked=control.blockSignals(True)
            control.setValue(round(value))
            control.blockSignals(blocked)

    def changed(self,value):
        self.setValue(value);self.valueChanged.emit(value)
