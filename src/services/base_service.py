from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable

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
    def add_observer(self, callback: Callable[[str, Dict], None]) -> None:
        """Register a callback for OCR results."""
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

class IStateService(IService):
    """Interface for game state management."""
    @abstractmethod
    def get_current_state(self) -> str:
        pass

    @abstractmethod
    def handle_trigger(self, trigger_text: str) -> None:
        pass
