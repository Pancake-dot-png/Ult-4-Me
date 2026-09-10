"""
Transparent overlay — shows score, detection delay, and matched regions
on top of the Overwatch game window.

Ported from Underwatch-Ultimate's overlay.py.
Uses Config and Vision classes instead of global config dict.
"""

from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt

from config import Config, REGIONS
from vision import Vision

try:
    from win32gui import GetWindowText, GetForegroundWindow
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class Overlay(QWidget):
    def __init__(self, config: Config, vision: Vision):
        super().__init__(parent=None)
        self.config = config
        self.vision = vision

        self.setWindowTitle("overlay")
        flags = (
            Qt.WindowType.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._init_elements()
        self._update_geometry()
        self.show()
        self.update_display()

    # ── Setup ────────────────────────────────────────────────────────────

    def _init_elements(self):
        # Border showing detection area
        self.corners = QLabel("", self)
        self.corners.setStyleSheet("border: 1px solid magenta;")

        # Score display
        self.score_label = QLabel("Score:", self)
        self.score_label.setStyleSheet("color: rgb(200, 0, 200); font: bold 18px;")

        # Detection delay display
        self.ping_label = QLabel("Detection Delay:", self)
        self.ping_label.setStyleSheet("color: rgb(200, 0, 200); font: bold 12px;")

        # Region boxes + labels
        self.region_widgets = {}
        for region_name in REGIONS:
            rect_widget = QLabel("", self)
            rect_widget.setStyleSheet("color: red; border: 1px solid red;")

            label_widget = QLabel(region_name, self)
            label_widget.setStyleSheet("color: red; font: bold 14px;")

            if "Popup" in region_name:
                label_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                label_widget.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

            self.region_widgets[region_name] = {"rect": rect_widget, "label": label_widget}

    def _update_geometry(self):
        det_rect = self.vision.get_detection_rect()
        if not det_rect:
            return

        self.setGeometry(
            det_rect["left"], det_rect["top"],
            det_rect["width"], det_rect["height"],
        )

        self.corners.setGeometry(0, 0, det_rect["width"], det_rect["height"])

        # Score label position (bottom-left area)
        scale = self.vision._scale
        self.score_label.setGeometry(
            int(170 * scale), int(1000 * scale),
            int(250 * scale), int(20 * scale),
        )
        self.ping_label.setGeometry(
            int(170 * scale), int(1020 * scale),
            int(250 * scale), int(20 * scale),
        )

        # Position region boxes
        region_state = self.vision.get_region_state()
        for name, widgets in self.region_widgets.items():
            rs = region_state.get(name)
            if not rs:
                continue
            sr = rs["scaled"]
            widgets["rect"].setGeometry(sr["x"] - 1, sr["y"] - 1, sr["w"] + 2, sr["h"] + 2)

            if "Popup" in name:
                widgets["label"].setGeometry(sr["x"] - 200, sr["y"], 195, sr["h"])
            else:
                widgets["label"].setGeometry(sr["x"], sr["y"] - 100, 200, 100)

    # ── Update (called each frame) ───────────────────────────────────────

    def update_display(self):
        if self.vision.resolution_changed:
            self._update_geometry()

        show = self._should_show()
        self._set_visible(show)
        if not show:
            return

        self._update_regions()
        self.score_label.setText(f"Score: {self.vision.get_score():.0f}")
        self.ping_label.setText(f"Detection Delay: {self.vision.detection_ping * 1000:4.0f} MS")

    def _should_show(self):
        mode = self.config.get("show_overlay_mode", 0)
        if mode == 0:
            return False
        if mode == 1:
            return True
        if mode == 2 and HAS_WIN32:
            return GetWindowText(GetForegroundWindow()) == "Overwatch"
        return False

    def _set_visible(self, visible):
        if visible:
            self.corners.show()
            self.score_label.show()
            self.ping_label.show()
        else:
            self.corners.hide()
            self.score_label.hide()
            self.ping_label.hide()
            for widgets in self.region_widgets.values():
                widgets["rect"].hide()
                widgets["label"].setText("")

    def _update_regions(self):
        region_mode = self.config.get("show_regions_mode", 0)
        overlay_mode = self.config.get("show_overlay_mode", 0)
        region_state = self.vision.get_region_state()

        if region_mode == 0 or overlay_mode == 0:
            for widgets in self.region_widgets.values():
                widgets["rect"].hide()
                widgets["label"].hide()
                widgets["label"].setText("")

        elif region_mode == 1:
            for name, widgets in self.region_widgets.items():
                widgets["rect"].show()
                widgets["label"].show()
                widgets["label"].setText(name)

        elif region_mode == 2:
            for name, widgets in self.region_widgets.items():
                rs = region_state.get(name, {})
                matches = rs.get("matches", [])
                if not matches:
                    widgets["rect"].hide()
                    widgets["label"].hide()
                    widgets["label"].setText("")
                else:
                    widgets["label"].setText("\n".join(matches))
                    widgets["label"].show()
                    widgets["rect"].show()
