from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QObject
from src.services.base_service import ITrayService
from abc import ABCMeta
import sys

class TrayMeta(type(QObject), ABCMeta):
    pass

class TrayService(QObject, ITrayService, metaclass=TrayMeta):
    def __init__(self, launcher):
        super().__init__()
        self.launcher = launcher
        self.tray_icon = None
        self.menu = None

    def initialize(self) -> bool:
        # Create the tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Create a simple icon programmatically
        icon = self._create_icon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Elden Ring Nightreign Timer")
        
        # Create Context Menu
        self.menu = QMenu()
        
        # Settings Action
        action_settings = self.menu.addAction("Settings")
        action_settings.triggered.connect(self.launcher.show_config_ui)
        
        self.menu.addSeparator()
        
        # Quit Action
        action_quit = self.menu.addAction("Quit")
        action_quit.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        return True

    def shutdown(self) -> None:
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None

    def set_tooltip(self, text: str) -> None:
        if self.tray_icon:
            self.tray_icon.setToolTip(text)

    def show_message(self, title: str, message: str) -> None:
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def quit_app(self):
        self.shutdown()
        QApplication.quit()
        sys.exit(0)

    def _create_icon(self) -> QIcon:
        """Creates a simple 64x64 icon with 'ER' text."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Circle Background
        painter.setBrush(QColor("#1a1a1a")) # Dark Gray
        painter.setPen(QColor("#c6a664"))   # Gold
        painter.drawEllipse(2, 2, 60, 60)
        
        # Draw Text
        painter.setPen(QColor("#c6a664"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(20)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "ER")
        
        painter.end()
        return QIcon(pixmap)
