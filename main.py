import sys
import json
import logging
import ctypes
from PyQt6.QtWidgets import QApplication, QFrame, QStyleOption, QStyle,QHBoxLayout, QLabel, QToolTip, QGraphicsOpacityEffect
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap, QPainter, QCursor, QFontMetrics
from PyQt6.QtCore import Qt, QTimer, QRect, QPropertyAnimation, QUrl, QObject, QEvent, QPoint
from ctypes import windll

############### SETTINGS ####################
DOCK_ICON_SIZE = 48
ANIMATION_SPEED = 200
HIDE_TASKBAR = False  # Hide Windows taskbar when Dock is running. Taskbar must have enabled Auto Hide option. Only primary taskbar will be hidden.
logging.basicConfig(filename='log.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
#############################################

class TooltipEventFilter(QObject):
    def __init__(self, parent, tooltip_text):
        super().__init__(parent)
        self.tooltip_text = tooltip_text

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            global_pos = obj.mapToGlobal(QPoint(0, 0))
            font_metrics = QFontMetrics(obj.font())
            tooltip_width = font_metrics.horizontalAdvance(self.tooltip_text)
            icon_height = obj.height()
            x = global_pos.x() + (DOCK_ICON_SIZE - tooltip_width - 20) // 2
            y = global_pos.y() - 8 - icon_height
            QToolTip.showText(QPoint(x, y), self.tooltip_text, obj)
        elif event.type() == QEvent.Type.Leave:
            QToolTip.hideText()
        return False

class FloatingDock(QFrame):
    def __init__(self, config):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QFrame {
               background-color: rgba(30, 33, 49, 0.85);
               border: 1px solid #41434c;
               border-radius: 16px;
               padding: 6px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                padding: 6px;
                border-radius: 8px;
            }
            QLabel:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QToolTip {
                font-size: 13px;
                border-radius: 3px;
                border: 1px solid #41434c;
                background-color: rgb(30, 33, 49);
                color: white;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for label_name, label_info in config.items():
            icon_label = QLabel(self)
            icon_path = label_info["icon"]
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(DOCK_ICON_SIZE, DOCK_ICON_SIZE)
            icon_label.setPixmap(pixmap)
            action_type = label_info["type"]
            if action_type == "open_app":
                action = lambda exec=label_info["exec"]: self.open_app(exec)
            elif action_type == "open_url":
                action = lambda url=label_info["url"]: self.open_website(url)
            else:
                action = lambda: None
            icon_label.mousePressEvent = lambda event, action=action: self.on_icon_click(event, action)
            tooltip_filter = TooltipEventFilter(icon_label, label_name)
            icon_label.installEventFilter(tooltip_filter)
            layout.addWidget(icon_label)

        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.toggle_visibility)
        self.timer.start(400)
        self.is_visible = False
        # TOTAL_HEIGHT  =QFrame(padding top+bottom) + QLabel(padding top+bottom) + QFrame (border top+bottom) 6+6+6+6+1+1
        TOTAL_HEIGHT = DOCK_ICON_SIZE + 46 
        desktop_geometry = QApplication.primaryScreen().availableGeometry()
        self.hidden_pos = QPoint((desktop_geometry.width() - self.width()) // 2, desktop_geometry.height() - 1)
        self.visible_pos = QPoint((desktop_geometry.width() - self.width()) // 2, desktop_geometry.height() - TOTAL_HEIGHT)

        self.slide_up_animation = QPropertyAnimation(self, b"pos")
        self.slide_up_animation.setDuration(ANIMATION_SPEED)
        self.slide_up_animation.setStartValue(self.hidden_pos)
        self.slide_up_animation.setEndValue(self.visible_pos)

        self.slide_down_animation = QPropertyAnimation(self, b"pos")
        self.slide_down_animation.setDuration(ANIMATION_SPEED)
        self.slide_down_animation.setStartValue(self.visible_pos)
        self.slide_down_animation.setEndValue(self.hidden_pos)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(ANIMATION_SPEED)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

    def toggle_visibility(self):
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(cursor_pos):
            if not self.is_visible:
                self.slide_up_animation.start()
                self.opacity_animation.setStartValue(0)
                self.opacity_animation.setEndValue(1)
                self.opacity_animation.start()
                self.show()
                self.is_visible = True
        else:
            if self.is_visible:
                self.slide_down_animation.start()
                self.opacity_animation.setStartValue(1)
                self.opacity_animation.setEndValue(0)
                self.opacity_animation.start()
                self.is_visible = False

    def on_icon_click(self, event, action):
        if event.button() == Qt.MouseButton.LeftButton:
            action()

    def open_app(self, exec):
        try:
            import subprocess
            subprocess.Popen(exec)
        except Exception as e:
            logging.error(f"Error executing: {e}")

    def open_website(self, url):
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            logging.error(f"Error opening website: {e}")

def hide_taskbar():
    taskbar = ctypes.windll.user32.FindWindowA(b'Shell_TrayWnd', None)
    ctypes.windll.user32.ShowWindow(taskbar, 0)

def show_taskbar():
    taskbar = ctypes.windll.user32.FindWindowA(b'Shell_TrayWnd', None)
    ctypes.windll.user32.ShowWindow(taskbar, 9)

def app_config():
    with open("config.json", "r") as config_file:
        return json.load(config_file)

def main():
    if HIDE_TASKBAR:
        hide_taskbar()
    else:
        show_taskbar()

    config = app_config()
    app = QApplication(sys.argv)
    widget = FloatingDock(config)
    widget.show()
    widget.raise_()
    widget.activateWindow()
    desktop_geometry = app.primaryScreen().availableGeometry()
    widget.move(widget.hidden_pos)
    widget.hide()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()