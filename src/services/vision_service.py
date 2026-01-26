from typing import Any, Dict, Callable, List, Optional
from src.services.base_service import IVisionService, IConfigService
from src.vision_engine import VisionEngine

class VisionService(IVisionService):
    def __init__(self, config_service: IConfigService):
        self.config_service = config_service
        self.engine: Optional[VisionEngine] = None
        self.observers: List[Callable[[str, int, float, List[Dict], float], None]] = []

    def initialize(self) -> bool:
        # We assume ConfigService is already initialized
        self.engine = VisionEngine(self.config_service)
        # self.engine = None # DEBUG: Disabled to test crash
        
        # Subscribe to config changes
        self.config_service.add_observer(self.on_config_changed)
        
        return True

    def on_config_changed(self):
        if self.engine:
            self.engine.update_from_config()

    def shutdown(self) -> None:
        self.stop_capture()

    def start_capture(self) -> None:
        if self.engine:
            self.engine.start_monitoring(self._multicast_callback)

    def stop_capture(self) -> None:
        if self.engine:
            self.engine.stop()

    def pause_capture(self) -> None:
        if self.engine:
            self.engine.pause()
            
    def resume_capture(self) -> None:
        if self.engine:
            self.engine.resume()

    def set_region(self, region: Dict) -> None:
        if self.engine:
            self.engine.update_region(region)

    def set_level_region(self, region: Dict) -> None:
        if self.engine:
            self.engine.update_level_region(region)

    def set_runes_region(self, region: Dict) -> None:
        if self.engine:
            self.engine.update_runes_region(region)

    def set_runes_icon_region(self, region: Dict) -> None:
        if self.engine:
            self.engine.update_runes_icon_region(region)

    def scan_victory_region(self):
        if self.engine:
            return self.engine.scan_victory_region()
        return None, 0

    def request_runes_burst(self) -> List[int]:
        if self.engine:
            return self.engine.request_runes_burst()
        return []

    def set_scan_delay(self, delay: float) -> None:
        if self.engine:
            self.engine.set_scan_delay(delay)

    def save_labeled_sample(self, label: str) -> None:
        if self.engine:
            self.engine.save_labeled_sample(label)

    def log_debug(self, message: str) -> None:
        if self.engine:
            self.engine.log_debug(message)

    def add_observer(self, callback: Callable[[str, int, float, List[Dict], float, float], None]) -> None:
        if callback not in self.observers:
            self.observers.append(callback)

    def add_level_observer(self, callback: Callable[[int], None]) -> None:
        """Adds an observer for level changes."""
        if not hasattr(self, 'level_observers'):
            self.level_observers = []
        if callback not in self.level_observers:
            self.level_observers.append(callback)

    def add_runes_observer(self, callback: Callable[[int], None]) -> None:
        """Adds an observer for runes changes."""
        if not hasattr(self, 'runes_observers'):
            self.runes_observers = []
        if callback not in self.runes_observers:
            self.runes_observers.append(callback)

    def _multicast_callback(self, text, width, offset, word_data, brightness=0, score=0):
        for observer in self.observers:
            observer(text, width, offset, word_data, brightness, score)

    def _level_multicast_callback(self, level: int, confidence: float = 100.0):
        if hasattr(self, 'level_observers'):
            for observer in self.level_observers:
                observer(level, confidence)

    def _runes_multicast_callback(self, runes: int, confidence: float = 100.0):
        if hasattr(self, 'runes_observers'):
            for observer in self.runes_observers:
                observer(runes, confidence)
            
    def start_capture(self) -> None:
        if self.engine:
            self.engine.set_level_callback(self._level_multicast_callback)
            self.engine.set_runes_callback(self._runes_multicast_callback)
            self.engine.start_monitoring(self._multicast_callback)

    def update_config(self):
         if self.engine:
             pass
