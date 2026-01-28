import time
import datetime
from collections import deque
from typing import List, Dict, Any, Optional, Tuple

class GameSession:
    """
    Represents a single run/session of the game.
    Encapsulates all volatile state that should be reset when a new run starts.
    NASA-grade Stats Freeze Gate: Level/Runes updates are blocked when stats_frozen=True
    """
    
    def __init__(self, session_id: int = -1):
        self.id = session_id
        self.start_time = time.time()
        self.phase_index = -1
        
        # Identity
        self.run_name = ""
        
        # Time tracking
        self.boss3_start_time: Optional[float] = None
        self.day1_detection_time: Optional[float] = None
        self.timer_frozen = False
        
        # Stats Freeze Control (NASA-grade gate pattern)
        self._stats_frozen = False
        
        # Stats (Current State) - Private backing fields
        self._current_run_level = 1
        self._current_runes = 0
        self.last_runes_reading = 0
        self.last_valid_total_runes = 0
        self.display_level = 1
        self.display_runes = 0
        
        # Accumulators
        self.permanent_loss = 0
        self.death_count = 0
        self.recovery_count = 0
        self.total_death_loss = 0
        self.lost_runes_pending = 0
        self.spent_at_merchants = 0
        
        # History Logs
        self.recent_spending_history: List[Tuple[float, int]] = []
        self.death_history: List[Dict[str, Any]] = []
        self.run_accumulated_history: List[int] = [] # The "Green Curve"
        self.run_accumulated_raw: List[int] = [] # Raw data
        self.graph_events: List[Dict[str, Any]] = []
        self.graph_log_data: List[Dict[str, Any]] = []
        self.day_transition_markers: List[Tuple[int, str]] = []
        
        # RPS / Smoothing
        self.rune_gains_history: deque = deque([0] * 40, maxlen=40)
        self.smoothed_rps = 0.0
        self.pending_rps_gain = 0
        self.rps_paused = False
        
        # Transient Detection State (Debouncing/Logic guards)
        self.pending_spending_event: Optional[Dict[str, Any]] = None
        self._level_up_pending_sync: Optional[Tuple[float, int]] = None
        self._ignore_next_rune_gain = False
        self._ignore_next_rune_drop = False
        self._ignore_next_rune_gain_grace_period: Optional[float] = None
        self.gain_verification_candidate = -1
        self.low_value_persistence = 0
        self.last_silent_level_drop: Optional[float] = None
        self.runes_uncertain = False
        self.runes_uncertain_since = 0
        
        # Victory State
        self.victory_detected = False
        self.victory_check_active = False
        
        # Level Detection internals
        self.pending_level_reading = 1
        self.level_consensus_count = 0
        
        # Analysis
        self.last_calculated_delta = 0
        
        # Timestamps
        self.last_stat_change_time = time.time()
        self.graph_start_time = time.time()
    
    # NASA-grade Property Gates for Stats
    @property
    def stats_frozen(self) -> bool:
        return self._stats_frozen
    
    @stats_frozen.setter
    def stats_frozen(self, value: bool):
        self._stats_frozen = value
    
    @property
    def current_run_level(self) -> int:
        return self._current_run_level
    
    @current_run_level.setter
    def current_run_level(self, value: int):
        if not self._stats_frozen:
            self._current_run_level = value
        # Silently ignore if frozen
    
    @property
    def current_runes(self) -> int:
        return self._current_runes
    
    @current_runes.setter
    def current_runes(self, value: int):
        if not self._stats_frozen:
            self._current_runes = value
        # Silently ignore if frozen
        
    def to_dict(self):
        """Debug dump"""
        return {
            "id": self.id,
            "lvl": self.current_run_level,
            "runes": self.current_runes,
            "phase": self.phase_index
        }
