from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from abc import ABCMeta
from typing import Callable, Optional
from src.services.base_service import IOverlayService
from src.ui.qt_overlay import ModernOverlay

class OverlayMeta(type(QObject), ABCMeta):
    pass

class OverlayService(QObject, IOverlayService, metaclass=OverlayMeta):
    # Signal to marshall calls to the main thread
    _schedule_signal = pyqtSignal(int, object) # delay, callback

    def __init__(self):
        super().__init__()
        self.overlay: Optional[ModernOverlay] = None
        self.is_recording = False
        
        # Connect signal to slot (will execute in Main Thread)
        self._schedule_signal.connect(self._execute_schedule, Qt.ConnectionType.QueuedConnection)

    def initialize(self) -> bool:
        self.create_overlay()
        # self.overlay.hide() # REMOVED: Start visible by default
        return True

    def shutdown(self) -> None:
        if self.overlay:
            self.overlay.close()

    def create_overlay(self):
        if self.overlay: return
        self.overlay = ModernOverlay()
        self.overlay.is_recording = self.is_recording
        self.overlay.show()

    def show(self) -> None:
        if not self.overlay:
            self.create_overlay()
        self.overlay.show()

    def hide(self) -> None:
        if self.overlay:
            self.overlay.hide()
    
    def update_timer(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_text(text)

    def update_status(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_text(text)

    def show_recording(self, show: bool):
        self.is_recording = show
        if self.overlay:
            self.overlay.is_recording = show
            self.overlay.update()

    def set_click_through(self, enabled: bool) -> None:
        # Qt 6.x supports this via setWindowFlags or setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if self.overlay:
            self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

    def set_ocr_score(self, score: float) -> None:
        if self.overlay:
            self.overlay.set_score(score)

    def schedule(self, delay_ms: int, callback: Callable) -> None:
        """Schedule a callback on the UI thread."""
        self._schedule_signal.emit(delay_ms, callback)

    def _execute_schedule(self, delay_ms, callback):
        if delay_ms == 0:
            callback()
        else:
            QTimer.singleShot(delay_ms, callback)
