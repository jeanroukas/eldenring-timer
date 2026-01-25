from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from abc import ABCMeta
from typing import Callable, Optional
from src.services.base_service import IOverlayService, IConfigService
from src.ui.qt_overlay import UnifiedOverlay
from src.service_container import ServiceContainer

class OverlayMeta(type(QObject), ABCMeta):
    pass

class OverlayService(QObject, IOverlayService, metaclass=OverlayMeta):
    # Signal to marshall calls to the main thread
    _schedule_signal = pyqtSignal(int, object) # delay, callback

    def __init__(self):
        super().__init__()
        self.unified_overlay: Optional[UnifiedOverlay] = None
        self.is_recording = False
        
        # Connect signal to slot (will execute in Main Thread)
        self._schedule_signal.connect(self._execute_schedule, Qt.ConnectionType.QueuedConnection)

    def initialize(self) -> bool:
        self.create_overlay()
        return True

    def shutdown(self) -> None:
        if self.unified_overlay:
            self.unified_overlay.close()

    def create_overlay(self):
        config_service = ServiceContainer().resolve(IConfigService)

        if not self.unified_overlay:
            self.unified_overlay = UnifiedOverlay()
            
            # Restore position
            x = config_service.get("unified_pos_x")
            y = config_service.get("unified_pos_y")
            if x is not None and y is not None:
                self.unified_overlay.move(x, y)

            self.unified_overlay.position_changed.connect(self._on_overlay_moved)
            self.unified_overlay.show()

    def _on_overlay_moved(self, x: int, y: int):
        try:
            config_service = ServiceContainer().resolve(IConfigService)
            config_service.set("unified_pos_x", x)
            config_service.set("unified_pos_y", y)
        except:
            pass 

    def show(self) -> None:
        if not self.unified_overlay:
            self.create_overlay()
        self.unified_overlay.show()

    def hide(self) -> None:
        if self.unified_overlay:
            self.unified_overlay.hide()
    
    def update_timer(self, text: str) -> None:
        if self.unified_overlay:
            self.unified_overlay.set_timer_text(text)

    def update_status(self, text: str) -> None:
        # Map generic status updates to timer text if appropriate, or ignore
        if self.unified_overlay:
            self.unified_overlay.set_timer_text(text)
    
    def update_run_stats(self, stats: dict) -> None:
        if self.unified_overlay:
            self.unified_overlay.set_stats(stats)

    def show_recording(self, show: bool):
        self.is_recording = show
        if self.unified_overlay:
            self.unified_overlay.is_recording = show
            self.unified_overlay.update()

    def set_click_through(self, enabled: bool) -> None:
        if self.unified_overlay:
            self.unified_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

    def set_ocr_score(self, score: float) -> None:
        if self.unified_overlay:
            self.unified_overlay.set_score(score)

    def schedule(self, delay_ms: int, callback: Callable) -> None:
        """Schedule a callback on the UI thread."""
        self._schedule_signal.emit(delay_ms, callback)

    def _execute_schedule(self, delay_ms, callback):
        if delay_ms == 0:
            callback()
        else:
            QTimer.singleShot(delay_ms, callback)
