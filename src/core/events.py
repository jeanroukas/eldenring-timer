from typing import List, Dict, Any, Callable, Type
from dataclasses import dataclass, field
import time
from src.logger import logger

# --- EVENT BUS ---
class EventBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._listeners = {}
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_listeners'):
            self._listeners: Dict[Type, List[Callable]] = {}

    def subscribe(self, event_type: Type, callback: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
        logger.debug(f"EventBus: Subscribed to {event_type.__name__}")

    def publish(self, event: Any):
        event_type = type(event)
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"EventBus Error processing {event_type.__name__}: {e}")

# Global Accessor
bus = EventBus()

# --- EVENTS (Flattened to avoid inheritance issues) ---

@dataclass
class LevelDetectedEvent:
    level: int
    confidence: float
    timestamp: float = field(default_factory=time.time)

@dataclass
class RunesDetectedEvent:
    runes: int
    confidence: float
    timestamp: float = field(default_factory=time.time)

@dataclass
class MenuDetectedEvent:
    is_open: bool
    timestamp: float = field(default_factory=time.time)

@dataclass
class PhaseChangeEvent:
    new_phase_index: int
    phase_name: str
    manual: bool = False
    timestamp: float = field(default_factory=time.time)

@dataclass
class DeathEvent:
    old_level: int
    new_level: int
    runes_lost: int
    total_loss: int
    timestamp: float = field(default_factory=time.time)

@dataclass
class VictoryEvent:
    boss_name: str
    duration: float
    timestamp: float = field(default_factory=time.time)

@dataclass
class EarlyGameDetectedEvent:
    """Emitted when Level 1 is detected without rune icon (early game start)"""
    level: int
    timestamp: float = field(default_factory=time.time)
