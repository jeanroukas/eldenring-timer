from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List
class IService(ABC):
    """Base interface for all services."""
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the service. Returns True if successful."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup resources."""
        pass

class IConfigService(IService):
    """Interface for configuration management."""
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def save(self) -> bool:
        pass

    @abstractmethod
    def add_observer(self, callback: Callable[[], None]) -> None:
        """Register a callback to be notified of config changes."""
        pass

class IVisionService(IService):
    """Interface for vision and OCR operations."""
    @abstractmethod
    def start_capture(self) -> None:
        pass

    @abstractmethod
    def stop_capture(self) -> None:
        pass

    @abstractmethod
    def set_region(self, region: tuple) -> None:
        pass

    @abstractmethod
    def set_level_region(self, region: tuple) -> None:
        pass
        
    @abstractmethod
    def set_runes_region(self, region: tuple) -> None:
        pass
        
    @abstractmethod
    def request_runes_burst(self) -> List[int]:
        """Triggers a high-speed burst of rune scans and returns the results."""
        pass

    @abstractmethod
    def request_level_burst(self) -> List[int]:
        """Triggers a high-speed burst of level scans and returns the results."""
        pass

    @abstractmethod
    def add_observer(self, callback: Callable[[str, Dict], None]) -> None:
        """Register a callback for OCR results."""
        pass

    @abstractmethod
    def save_labeled_sample(self, label: str) -> None:
        """Saves the current frame as a training sample for the given label."""
        pass

    @abstractmethod
    def log_debug(self, message: str) -> None:
        """Logs a message to the OCR debug log."""
        pass

class IOverlayService(IService):
    """Interface for the UI overlay."""
    @abstractmethod
    def show(self) -> None:
        pass

    @abstractmethod
    def hide(self) -> None:
        pass

    @abstractmethod
    def update_timer(self, text: str) -> None:
        pass
    
    @abstractmethod
    def update_status(self, text: str) -> None:
        pass

    @abstractmethod
    def set_click_through(self, enabled: bool) -> None:
        pass

    @abstractmethod
    def set_ocr_score(self, score: float) -> None:
        pass
        
    @abstractmethod
    def update_run_stats(self, stats: Dict[str, Any]) -> None:
        """Updates the run statistics with structured data."""
        pass

class IStateService(IService):
    """Interface for game state management."""
    @abstractmethod
    def get_current_state(self) -> str:
        pass

    @abstractmethod
    def handle_trigger(self, trigger_text: str) -> None:
        pass

class IDatabaseService(IService):
    """Interface for database and analytics."""
    @abstractmethod
    def create_session(self) -> int:
        """Starts a new game session and returns its ID."""
        pass

    @abstractmethod
    def end_session(self, session_id: int, result: str) -> None:
        """Ends a session with a result (VICTORY, DEFEAT, etc)."""
        pass

    @abstractmethod
    def log_event(self, session_id: int, event_type: str, payload: str = None) -> None:
        """Logs a specific event during a session."""
        pass
        
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregated statistics."""
        pass

class ITrayService(IService):
    """Interface for system tray icon and menu."""
    @abstractmethod
    def set_tooltip(self, text: str) -> None:
        pass

    @abstractmethod
    def show_message(self, title: str, message: str) -> None:
        pass


class IAudioService(IService):
    """Interface for text-to-speech and audio feedback."""
    @abstractmethod
    def announce(self, text: str) -> None:
        """Speaks the given text."""
        pass

    @abstractmethod
    def set_enabled(self, enabled: bool) -> None:
        """Enables or disables audio output."""
        pass
