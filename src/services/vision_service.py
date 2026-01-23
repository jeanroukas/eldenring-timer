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

    def scan_victory_region(self):
        if self.engine:
            return self.engine.scan_victory_region()
        return None, 0

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

    def _multicast_callback(self, text, width, offset, word_data, brightness=0, score=0):
        for observer in self.observers:
            observer(text, width, offset, word_data, brightness, score)
            
    def update_config(self):
         if self.engine:
             pass
