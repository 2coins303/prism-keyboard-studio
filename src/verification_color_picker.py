"""Exercise real color-picker dialogs without screen sampling or device access."""
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QColorDialog, QDialogButtonBox, QPushButton, QStyleOptionButton


def contrast(first, second):
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


def exercise_color_pickers(window, output_dir=None):
    from verification_resize import capture, readable_buttons, settle
    app = QApplication.instance()
    cases = []
    window.show_editor()
    swatches = [('palette', 0, window.palette_buttons[2]), ('brush', 1, window.brush), ('audio', 2, window.band_buttons[0])]
    for kind, tab, swatch in swatches:
        window.tabs.setCurrentIndex(tab)
        settle(60)
        original = swatch.color
        try:
            for color in ('#fff6dc', '#ffffff', '#000000', '#20dfff'):
                swatch.set_color(color)
                errors = []

                def inspect():
                    dialog = app.activeModalWidget()
                    try:
                        assert isinstance(dialog, QColorDialog)
                        settle(20)
                        buttons = readable_buttons(dialog)
                        ratios = []
                        for button in dialog.findChildren(QPushButton):
                            if not button.isVisible() or not button.isEnabled():
                                continue
                            option = QStyleOptionButton(); button.initStyleOption(option)
                            ratio = contrast(option.palette.color(QPalette.ButtonText), option.palette.color(QPalette.Button))
                            assert ratio >= 4.5, f'{button.text()}: insufficient contrast ({ratio:.2f}:1) with {color}'
                            ratios.append(ratio)
                        assert len(buttons) >= 4 and len(ratios) >= 4
                        box = dialog.findChild(QDialogButtonBox)
                        assert box.button(QDialogButtonBox.Ok).isVisible()
                        assert box.button(QDialogButtonBox.Cancel).isVisible()
                        if output_dir and kind == 'palette' and color == '#fff6dc':
                            capture(dialog, output_dir/'Color picker readable buttons.png')
                        cases.append(dict(swatch=kind, color=color, minimum_contrast=round(min(ratios), 2), buttons=buttons))
                        # Cancel must discard edits, as in normal use.
                        dialog.setCurrentColor(QColor('#123456'))
                        box.button(QDialogButtonBox.Cancel).click()
                    except Exception as error:
                        errors.append(error)
                    finally:
                        if isinstance(dialog, QColorDialog) and dialog.isVisible():
                            dialog.reject()

                QTimer.singleShot(50, inspect)
                swatch.choose()
                if errors:
                    raise errors[0]
                assert swatch.color == color, 'Cancel changed the swatch color'
        finally:
            swatch.set_color(original)
    return cases
