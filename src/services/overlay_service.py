from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from abc import ABCMeta
from typing import Callable, Optional
from src.services.base_service import IOverlayService, IConfigService
from src.ui.qt_overlay import ModernOverlay, RunCountOverlay
from src.service_container import ServiceContainer

class OverlayMeta(type(QObject), ABCMeta):
    pass

class OverlayService(QObject, IOverlayService, metaclass=OverlayMeta):
    # Signal to marshall calls to the main thread
    _schedule_signal = pyqtSignal(int, object) # delay, callback

    def __init__(self):
        super().__init__()
        self.overlay: Optional[ModernOverlay] = None
        self.run_counter_overlay: Optional[RunCountOverlay] = None
        self.is_recording = False
        
        # Connect signal to slot (will execute in Main Thread)
        self._schedule_signal.connect(self._execute_schedule, Qt.ConnectionType.QueuedConnection)

    def initialize(self) -> bool:
        self.create_overlay()
        return True

    def shutdown(self) -> None:
        if self.overlay:
            self.overlay.close()
        if self.run_counter_overlay:
            self.run_counter_overlay.close()

    def create_overlay(self):
        config_service = ServiceContainer().resolve(IConfigService)

        # Timer Overlay
        if not self.overlay:
            self.overlay = ModernOverlay()
            self.overlay.is_recording = self.is_recording
            
            # Restore position
            x = config_service.get("timer_pos_x")
            y = config_service.get("timer_pos_y")
            if x is not None and y is not None:
                self.overlay.move(x, y)

            self.overlay.position_changed.connect(self._on_timer_moved)
            self.overlay.show()

        # Run Counter Overlay
        if not self.run_counter_overlay:
            self.run_counter_overlay = RunCountOverlay()
            
            # Restore position
            rx = config_service.get("run_counter_pos_x")
            ry = config_service.get("run_counter_pos_y")
            if rx is not None and ry is not None:
                self.run_counter_overlay.move(rx, ry)
            
            self.run_counter_overlay.position_changed.connect(self._on_run_counter_moved)
            self.run_counter_overlay.show()

    def _on_timer_moved(self, x: int, y: int):
        try:
            config_service = ServiceContainer().resolve(IConfigService)
            config_service.set("timer_pos_x", x)
            config_service.set("timer_pos_y", y)
        except:
            pass # Handle potential service resolution issues during shutdown

    def _on_run_counter_moved(self, x: int, y: int):
        try:
            config_service = ServiceContainer().resolve(IConfigService)
            config_service.set("run_counter_pos_x", x)
            config_service.set("run_counter_pos_y", y)
        except:
            pass

    def show(self) -> None:
        if not self.overlay:
            self.create_overlay()
        self.overlay.show()
        if self.run_counter_overlay:
            self.run_counter_overlay.show()

    def hide(self) -> None:
        if self.overlay:
            self.overlay.hide()
        if self.run_counter_overlay:
            self.run_counter_overlay.hide()
    
    def update_timer(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_text(text)

    def update_status(self, text: str) -> None:
        if self.overlay:
            self.overlay.set_text(text)
    
    def update_run_count(self, count: int) -> None:
        if self.run_counter_overlay:
            self.run_counter_overlay.set_run_count(count)

    def show_recording(self, show: bool):
        self.is_recording = show
        if self.overlay:
            self.overlay.is_recording = show
            self.overlay.update()

    def set_click_through(self, enabled: bool) -> None:
        # Qt 6.x supports this via setWindowFlags or setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if self.overlay:
            self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if self.run_counter_overlay:
            self.run_counter_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

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
