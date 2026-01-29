from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from abc import ABCMeta
from typing import Callable, Optional
from src.services.base_service import IOverlayService, IConfigService
from src.ui.qt_overlay import UnifiedOverlay
from src.ui.level_indicator import LevelIndicatorOverlay
from src.ui.missing_runes_overlay import MissingRunesOverlay
from src.ui.transaction_history_widget import TransactionHistoryWidget
from src.service_container import ServiceContainer

class OverlayMeta(type(QObject), ABCMeta):
    pass

class OverlayService(QObject, IOverlayService, metaclass=OverlayMeta):
    # Signal to marshall calls to the main thread
    _schedule_signal = pyqtSignal(int, object) # delay, callback

    def __init__(self):
        super().__init__()
        self.unified_overlay: Optional[UnifiedOverlay] = None
        self.level_indicator: Optional[LevelIndicatorOverlay] = None
        self.missing_runes_overlay: Optional[MissingRunesOverlay] = None
        self.transaction_widget: Optional[TransactionHistoryWidget] = None
        self.is_recording = False
        
        # Connect signal to slot (will execute in Main Thread)
        self._schedule_signal.connect(self._execute_schedule, Qt.ConnectionType.QueuedConnection)

    def initialize(self) -> bool:
        self.create_overlay()
        return True

    def shutdown(self) -> None:
        if self.unified_overlay:
            self.unified_overlay.close()
        if self.level_indicator:
            self.level_indicator.close()
        if self.missing_runes_overlay:
            self.missing_runes_overlay.close()

    def create_overlay(self):
        config_service = ServiceContainer().resolve(IConfigService)

        if not self.unified_overlay:
            self.unified_overlay = UnifiedOverlay()
            
            # Restore position
            x = config_service.get("unified_pos_x")
            y = config_service.get("unified_pos_y")
            print(f"[DEBUG] Restoring position from config: x={x}, y={y}")
            if x is not None and y is not None:
                self.unified_overlay.move(x, y)
                print(f"[DEBUG] Position restored to: ({x}, {y})")
            else:
                # Default position if none saved
                self.unified_overlay.move(20, 20)
                print(f"[DEBUG] Using default position: (20, 20)")

            self.unified_overlay.position_changed.connect(self._on_overlay_moved)
            self.unified_overlay.show()
            
        if not self.level_indicator:
            self.level_indicator = LevelIndicatorOverlay()
            self.level_indicator.show()
        
        if not self.missing_runes_overlay:
            self.missing_runes_overlay = MissingRunesOverlay()
            self.missing_runes_overlay.show()

    def _on_overlay_moved(self, x: int, y: int):
        try:
            print(f"[DEBUG] _on_overlay_moved called: ({x}, {y})")
            config_service = ServiceContainer().resolve(IConfigService)
            config_service.set("unified_pos_x", x)
            config_service.set("unified_pos_y", y)
            print(f"[DEBUG] Position saved to config: ({x}, {y})")
        except Exception as e:
            print(f"[DEBUG] Error saving position: {e}") 

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
        
        # Update transaction history widget
        if "transaction_history" in stats:
            def _u_transaction():
                # Create widget if not exists and has transactions
                if self.transaction_widget is None and len(stats["transaction_history"]) > 0:
                    config = ServiceContainer().resolve(IConfigService)
                    self.transaction_widget = TransactionHistoryWidget(None, config)
                    self.transaction_widget.show()
                
                # Update widget with new transactions
                if self.transaction_widget:
                    self.transaction_widget.update_transactions(stats["transaction_history"])
            
            self.schedule(0, _u_transaction)
        
        # Update Circle Indicator if applicable
        if "level" in stats and "potential_level" in stats:
            def _u_indicator():
                if self.level_indicator:
                    config = ServiceContainer().resolve(IConfigService)
                    region = config.get("level_region", [0, 0, 100, 100])
                    self.level_indicator.set_data(stats["level"], stats["potential_level"], region)
            self.schedule(0, _u_indicator)
        
        # Update Missing Runes Overlay
        if "missing_runes" in stats and "is_max_level" in stats:
            def _u_missing():
                if self.missing_runes_overlay:
                    from src.services.rune_data import RuneData
                    config = ServiceContainer().resolve(IConfigService)
                    region = config.get("level_region", [0, 0, 100, 100])
                    
                    # Calculate level cost for blink effect
                    current_level = stats.get("level", 1)
                    next_level = current_level + 1
                    current_total = RuneData.get_total_runes_for_level(current_level) or 0
                    next_total = RuneData.get_total_runes_for_level(next_level) or 0
                    level_cost = next_total - current_total
                    
                    self.missing_runes_overlay.set_data(
                        stats["missing_runes"], 
                        stats["is_max_level"], 
                        region, 
                        level_cost
                    )
            self.schedule(0, _u_missing)

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
