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
        # If called from main thread (init), direct call is best.
        # If called from background, simple schedule.
        self.schedule(0, lambda: self._safe_show())

    def _safe_show(self):
        try:
            if not self.unified_overlay:
                self.create_overlay()
            if self.unified_overlay:
                self.unified_overlay.show()
        except RuntimeError:
            self.create_overlay()
            self.unified_overlay.show()

    def hide(self) -> None:
        self.schedule(0, lambda: self.unified_overlay.hide() if self.unified_overlay else None)

    def toggle(self) -> None:
        self.schedule(0, self._safe_toggle)

    def _safe_toggle(self):
        if not self.unified_overlay:
            self.create_overlay()
            self.unified_overlay.show()
        else:
            if self.unified_overlay.isVisible():
                self.unified_overlay.hide()
            else:
                self.unified_overlay.show()
    
    def update_timer(self, text: str) -> None:
        self.schedule(0, lambda: self.unified_overlay.set_timer_text(text) if self.unified_overlay else None)

    def update_status(self, text: str) -> None:
        self.schedule(0, lambda: self.unified_overlay.set_timer_text(text) if self.unified_overlay else None)
    
    def update_run_stats(self, stats: dict) -> None:
        # Clone stats if needed? Dicts are passed by reference, but usually stats is a new dict from StateService
        self.schedule(0, lambda: self.unified_overlay.set_stats(stats) if self.unified_overlay else None)

    def show_recording(self, show: bool):
        self.is_recording = show
        def _u():
            if self.unified_overlay:
                self.unified_overlay.is_recording = show
                self.unified_overlay.update()
        self.schedule(0, _u)

    def set_click_through(self, enabled: bool) -> None:
        def _u():
            if self.unified_overlay:
                self.unified_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self.schedule(0, _u)

    def set_ocr_score(self, score: float) -> None:
        self.schedule(0, lambda: self.unified_overlay.set_score(score) if self.unified_overlay else None)

    def schedule(self, delay_ms: int, callback: Callable) -> None:
        """Schedule a callback on the UI thread."""
        self._schedule_signal.emit(delay_ms, callback)

    def _execute_schedule(self, delay_ms, callback):
        def safe_callback():
            try:
                callback()
            except RuntimeError:
                # pass silently or re-create?
                pass
            except Exception as e:
                print(f"Overlay Error: {e}")

        if delay_ms == 0:
            safe_callback()
        else:
            QTimer.singleShot(delay_ms, safe_callback)
