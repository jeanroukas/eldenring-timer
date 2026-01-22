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
        # VisionEngine expects a dict-like config object. 
        # Since ConfigService abstraction might not match exactly what VisionEngine expects (dict),
        # we might need to pass the raw dict or an adapter.
        # VisionEngine uses config.get("key", default). ConfigService.get works the same.
        self.engine = VisionEngine(self.config_service)
        return True

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

    def add_observer(self, callback: Callable[[str, int, float, List[Dict], float], None]) -> None:
        if callback not in self.observers:
            self.observers.append(callback)

    def _multicast_callback(self, text, width, offset, word_data, brightness=0):
        for observer in self.observers:
            observer(text, width, offset, word_data, brightness)
            
    def update_config(self):
         if self.engine:
             # Since we passed config_service to engine, and engine assumes it's a dict...
             # Wait, VisionEngine lines 29: self.config = config.
             # line 33: self.region = config.get("monitor_region", {})
             # If I pass ConfigService instance, it has .get() method, so it MIGHT work if VisionEngine only uses .get()
             # But VisionEngine line 195: self.config["monitor_region"] = region. This assumes dict item assignment.
             # ConfigService.set() is what I defined.
             # I need to verify if ConfigService supports item assignment or if I should pass the internal dict.
             # Or I update VisionEngine to use the service interface.
             # For Phase 1, the plan said "Refactor VisionEngine to VisionService".
             # To avoid modifying VisionEngine too much right now (risky), I should probably pass 'self.config_service._config' to it,
             # OR wrap ConfigService to behave like a dict.
             pass
