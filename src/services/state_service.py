import time
import datetime
import winsound
import threading
import os
import sys
import json
from collections import deque
from typing import Dict, Any, List, Optional
try:
    import keyboard
except ImportError:
    keyboard = None
import psutil
import subprocess

from src.services.base_service import IStateService, IConfigService, IVisionService, IOverlayService, IDatabaseService, IAudioService, ITrayService
from src.pattern_manager import PatternManager
from src.services.rune_data import RuneData
from src.core.session import GameSession
from src.core.game_rules import GameRules
from src.core.ticket_manager import TicketManager
from src.core.events import bus, LevelDetectedEvent, RunesDetectedEvent, MenuDetectedEvent, PhaseChangeEvent, EarlyGameDetectedEvent
from src.logger import logger

class StateService(IStateService):
    def __init__(self, config: IConfigService, vision: IVisionService, overlay: IOverlayService, db: IDatabaseService, audio: IAudioService, tray: ITrayService):
        self.config = config
        self.vision = vision
        self.overlay = overlay
        self.db = db
        self.audio = audio
        self.tray = tray
        
        # Session State
        self.session: Optional[GameSession] = GameSession()
        self.current_session_id = -1
        
        self.running = False
        self.is_hibernating = False # Default to visible (safer)
        # Reverted per user: nightreign.exe
        self.game_process = "nightreign.exe" 
        

        
        # Game State
        self.phases = [
            {"name": "Day 1 - Storm", "duration": 270},       # 4:30
            {"name": "Day 1 - Shrinking", "duration": 180},   # 3:00
            {"name": "Day 1 - Storm 2", "duration": 210},     # 3:30
            {"name": "Day 1 - Shrinking 2", "duration": 180}, # 3:00
            {"name": "Boss 1", "duration": 0},                # Manual
            {"name": "Day 2 - Storm", "duration": 270},
            {"name": "Day 2 - Shrinking", "duration": 180},
            {"name": "Day 2 - Storm 2", "duration": 210},
            {"name": "Day 2 - Shrinking 2", "duration": 180},
            {"name": "Boss 2", "duration": 0},
            {"name": "Day 3 - Preparation", "duration": 0},
            {"name": "Day 3 - Final Boss", "duration": 0}
        ]
        self.session.phase_index = -1
        self.session.start_time: Optional[float] = None
        self.session.boss3_start_time: Optional[float] = None
        self.session.day1_detection_time: Optional[float] = None
        self.session.timer_frozen = False
        
        # Buffering Logic
        self.trigger_buffer = [] 
        self.buffer_window = 2.5 
        self.triggered_recently = False 
        
        # Fast Mode State
        self.fast_mode_active = False
        self.fast_mode_end_time = 0
        self.last_beep_time = 0
        self.last_fast_mode_trigger = 0 
        self.last_jour_detection = 0 
        
        # Pattern Manager
        self.pattern_manager = PatternManager()
        self.current_matched_pattern = ""
        
        # Day 3 Transitions
        self.black_screen_start = 0
        self.in_black_screen = False
        self.last_phase_change_time = 0
        
        # Victory detection
        self.victory_check_active = False
        self.last_victory_check = 0
        self.victory_check_interval = 0.5
        self.victory_detected = False

        # Audio state
        self.last_beep_second = -1

        # Debugging
        self.last_brightness_log = 0
        
        # Audio Logic State
        self.last_announced_phase = -1
        self.last_announcement_second = -1
        
        # Stat Stability Tracking
        self.last_stat_change_time = 0
        
        # Spending Delay Logic
        self.pending_spending_event = None
        
        # Persistence & Smoothing
        self.last_valid_total_runes = 0
        self.last_display_level = 1
        self.last_display_level = 1
        self.last_display_runes = 0
        
        # Rune Validation State
        self.gain_verification_candidate = -1
        self.spike_persistence = 0
        self.runes_uncertain = False
        self.runes_uncertain_since = 0
        self.pre_run_spam_limit = 0
        
        # Menu Detection State
        self.is_in_menu = False
        self._was_in_menu = False  # Track previous state for exit detection
        self._menu_first_detected = 0  # Timestamp of first menu detection
        self._menu_validated = False  # True after 3s of continuous detection
        
        # Early Game Detection State
        self.waiting_for_day1 = False  # True when Level 1 detected, waiting for JOUR I
        
        self.tuner_callback = None
        self.logic_paused = False # Flag to pause logic during OCR Tuning
        
        # --- NIGHTREIGN CONSTANTS (Configurable) ---
        self._load_nr_constants()

    def initialize(self) -> bool:
        logger.info("StateService: Initializing...")
        logger.update_context("phase", "Waiting")
        logger.update_context("session_id", "init")
        
        self.running = True
        
        # Retroactive Death State
        self.last_silent_level_drop = None
        self.low_value_persistence = 0
        
        # Subscribe to config changes
        self.config.add_observer(self.on_config_changed)
        
        # Start Vision Capture Loop
        self.vision.start_capture()
        
        # Initial Day OCR state
        self._update_day_ocr_state()
        
        # HYBRID ARCHITECTURE: 
        # 1. StateService Acts as the "Bridge" transforming Vision Callbacks -> Events
        # 2. StateService ALSO listens to events (Self-Loop for logic isolation)
        
        # Direct Callbacks (Legacy/Bridge)
        self.vision.add_observer(self.on_ocr_result)
        self.vision.add_tuning_observer(self.on_tuning_status) # Subscription for Pause Logic
        self.vision.add_level_observer(lambda lvl, conf: bus.publish(LevelDetectedEvent(lvl, conf)))
        self.vision.add_runes_observer(lambda runes, conf: bus.publish(RunesDetectedEvent(runes, conf)))
        self.vision.set_menu_callback(lambda is_open: bus.publish(MenuDetectedEvent(is_open)))

        # Event Subscriptions
        bus.subscribe(LevelDetectedEvent, self._handle_level_event)
        bus.subscribe(RunesDetectedEvent, self._handle_runes_event)
        bus.subscribe(MenuDetectedEvent, self._handle_menu_event)

        self.session.current_run_level = 1
        self.pending_level = None
        self.level_consensus_count = 0
        self.level_burst_buffer = []  # New: For burst validation (4/5 majority)
        
        # LED States for OCR Validation Feedback
        # States: 'idle' (gray), 'burst' (orange), 'validated' (green), 'rejected' (red)
        self.level_led_state = 'idle'
        self.runes_led_state = 'idle'
        
        # Rune History & RPS (40s Window)
        self.session.current_runes = 0
        self.last_runes_reading = 0
        self.rune_gains_history = deque([0] * 40, maxlen=40) # 40 seconds
        self.smoothed_rps = 0.0
        self.pending_rps_gain = 0
        self.last_rps_update = time.time()
        self.rps_paused = False
        
        # Advanced Rune & Death Stats
        self.spent_at_merchants = 0
        self.session.death_count = 0
        self.session.recovery_count = 0 # New: Track recoveries
        self.death_history = [] 
        self.total_death_loss = 0
        self.lost_runes_pending = 0 
        self.session.graph_events = [] 
        self.permanent_loss = 0 
        
        # Transaction Ticket System
        self.ticket_manager = TicketManager(config)
        self._ignore_next_rune_drop = False
        self._ignore_next_rune_gain = False
        self._ignore_next_rune_gain_grace_period = None
        self._level_up_pending_sync = None # (timestamp, level_cost)
        self.last_calculated_delta = 0 # Store for UI
        self.last_potential_level_log = 0 # Throttling for debug log
        
        # --- RUNE UNCERTAINTY (Anti-Glitch) ---
        self.runes_uncertain = False
        self.runes_uncertain_since = 0
        self.last_stable_runes_val = 0
        self.last_stable_runes_time = time.time()
        
        # --- NIGHTREIGN ANALYTICS CONSTANTS ---
        self.NR_TOTAL_REQ = 512936 # Lvl 1->15 (Exact)
        self.NR_BOSS_DROPS = 50000 + 50000 # Boss 1 + Boss 2
        self.NR_FARMING_GOAL = 412936 # Farming Only (Target - Bosses)
        self.NR_DAY_DURATION = 840 # 14 mins per day (270+180+210+180)
        self.NR_TOTAL_TIME = 1680 # 28 mins farming time (2 days)
        self.NR_SNOWBALL_D1 = 1.35
        self.NR_SNOWBALL_D2 = 1.15
        
        # Transaction History (for correction)
        self.recent_spending_history = [] # List of (timestamp, amount)

        # Graph Logging
        self.graph_log_file = ""
        self.graph_log_data = []
        self.last_graph_save = 0
        self.last_graph_log_time = 0
        self.graph_start_time = 0 # Timestamp when graph history started

        # --- FULL-RUN HISTORY (User Request) ---
        self.session.run_accumulated_history = [] # Corrected/Cleaned History
        self.run_accumulated_raw = []     # Raw/Dirty History (For diff visualization)
        self.session.day_transition_markers = [] # List of (index, day_name)
        
        # Debug / Inspector State
        self.recent_warnings = deque(maxlen=20)
        
        # Session Management
        self.session_count = self.config.get("session_count", 0)
        self.current_phase = "INIT"
        self.start_new_session("STARTUP")
        
        self.update_runes_display(1)

        # Initialize Audio
        # REMOVED: AudioService is initialized by the container. Double-init caused thread duplication/COM issues.
        # self.audio.initialize() 
        
        logger.info("StateService: Registering hotkeys...")
        # Setup Hotkeys
        if keyboard:
            try:
                # Debug Wrapper to catch errors and log key presses
                def _bind(key, func, name):
                    def _wrapper():
                        logger.info(f"HOTKEY PRESSED: {key} ({name})")
                        try:
                            func()
                            logger.info(f"HOTKEY EXECUTED: {key}")
                        except Exception as e:
                            logger.error(f"HOTKEY ERROR {key}: {e}", exc_info=True)
                            try: winsound.Beep(200, 200)
                            except: pass
                    keyboard.add_hotkey(key, _wrapper)
                    logger.info(f"Bound {key} -> {name}")

                # -- STANDARD F-KEYS MAPPING --
                _bind('f4', self.reset_to_initial_state, "FULL_RESET")
                _bind('f5', lambda: self.handle_manual_feedback("DAY 1", force=True), "RESET")
                _bind('f6', lambda: self.handle_manual_feedback("DAY 2", force=True), "FORCE_D2")
                _bind('f7', lambda: self.handle_manual_feedback("DAY 3", force=True), "FORCE_D3")
                
                # F8: Boss Skip / Correction
                _bind('f8', self.skip_to_boss, "BOSS_SKIP")
                
                _bind('f9', self.on_f9_pressed, "OPEN_TUNER")
                # F9 Backup (just in case)
                _bind('shift+f9', self.on_f9_pressed, "OPEN_TUNER_BACKUP")

                # F10: Quit (Must be scheduled on Main Thread to avoid crash)
                _bind('f10', lambda: self.overlay.schedule(0, self.tray.quit_app) if self.tray else os._exit(0), "QUIT")
                
            except Exception as e:
                logger.error(f"Failed to register hotkeys: {e}")

        logger.info("StateService: Starting background loop...")
        # Start background thread for loops
        self.thread = threading.Thread(target=self._run_loops, daemon=True)
        self.thread.start()
        
        logger.info("StateService: Initialization Complete.")
        return True

    def start_new_session(self, phase_name: str):
        self.session_count += 1
        self.config.set("session_count", self.session_count)
        
        # --- LOG CONTEXT UPDATE ---
        logger.update_context("session_id", self.session_count)
        logger.update_context("phase", phase_name)
        
        self.current_phase = phase_name
        self.session_log = []
        
        # Clear History for New Session
        self.session.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.session.graph_events = []
        self.session.ui_transitions = []
        self.spent_at_merchants = 0
        self.session.death_count = 0
        self.session.recovery_count = 0
        
        self.log_dir = os.path.join(os.getcwd(), "data", "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # New Naming Convention: Run_[Count]_[Phase]_[YYYYMMDD]_[HHMMSS].json
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.session_filename = f"Run_{self.session_count}_{phase_name}_{ts}.json"
        
        # Dedicated Graph Log
        phase_clean = phase_name.replace(" ", "_").replace("-", "")
        self.graph_log_filename = f"Run_{self.session_count}_{phase_clean}_{ts}_GRAPH.json"
        self.graph_log_file = os.path.join(self.log_dir, self.graph_log_filename)
        self.graph_log_data = []
        self.last_graph_save = time.time()
        self.graph_start_time = time.time() # Fix: Mark start of graph for marker calculation
        
        self.log_session_event("SESSION_STARTED", {
            "run_count": self.session_count,
            "phase": phase_name,
            "level": getattr(self, 'current_run_level', 1)
        })

    def reset_to_initial_state(self):
        """
        F4 Hotkey: Reset to initial state (like after finishing a run).
        Clears all run data and returns to waiting state.
        """
        logger.info("F4 PRESSED: Resetting to initial state...")
        
        # Reset session state
        self.session.phase_index = -1
        self.session.start_time = None
        self.session.boss3_start_time = None
        self.session.day1_detection_time = None
        self.session.timer_frozen = False
        self.session.current_run_level = 1
        self.session.current_run_runes = 0
        self.session.total_runes_earned = 0
        self.session.total_runes_spent = 0
        self.session.death_count = 0
        self.session.recovery_count = 0
        self.session.lost_runes_pending = 0
        self.spent_at_merchants = 0
        
        # Clear History
        self.session.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.session.graph_events = []
        self.session.day_transition_markers = []
        self.session.ui_transitions = []
        
        # Reset phase tracking
        self.current_phase = "Waiting"
        self.last_phase_change_time = time.time()
        
        # Reset detection states
        self.waiting_for_day1 = False
        self.is_in_menu = False
        self._was_in_menu = False
        self._menu_first_detected = 0
        self._menu_validated = False
        self.victory_detected = False
        self.victory_check_active = False
        
        # Reset rune tracking
        self.last_valid_total_runes = 0
        self.last_display_level = 1
        self.last_display_runes = 0
        self.gain_verification_candidate = -1
        self.spike_persistence = 0
        self.runes_uncertain = False
        
        # Reset graph data
        self.graph_log_data = []
        
        # Update UI to initial state
        self.overlay.update_timer("00:00")
        self.overlay.update_run_stats({
            "level": 1,
            "potential_level": 1,
            "current_runes": 0,
            "total_runes": 0,
            "next_level": 2,
            "needed_runes": 0,
            "missing_runes": 0,
            "is_max_level": False,
            "run_history": [],
            "run_history_raw": [],
            "transitions": [],
            "death_count": 0,
            "recovery_count": 0,
            "phase_name": "Waiting",
            "spent_at_merchants": 0,
            "graph_events": [],
            "rps": 0,
            "grade": "C",
            "delta_runes": 0,
            "time_to_level": "---",
            "graph_start_time": 0
        })
        
        # Reset OCR Sensors (Re-enable Day OCR)
        self._last_day_ocr_state = None # Force update
        self._update_day_ocr_state()
        
        # Ensure logic is unpaused
        self.logic_paused = False
        
        # Reset ui_transitions for graph
        self.session.ui_transitions = []
        
        logger.info("Reset complete. Day OCR sensor re-enabled.")
        
        logger.info("Reset complete. Waiting for new run...")
        try:
            winsound.Beep(800, 100)  # Confirmation beep
        except:
            pass


    def log_session_event(self, event_type: str, data: dict = None):
        """
        Unified Logging:
        1. Writes to JSONL (Telemetry Stream) for analysis/replay.
        2. Writes to SQLite (Persistence) for stats.
        3. Writes to Legacy JSON (Backup) - Optional, can be deprecated.
        """
        event = {
            "timestamp": time.time(),
            "time_str": datetime.datetime.now().strftime("%H:%M:%S"),
            "event_type": event_type,
            "data": data or {}
        }
        
        # 1. Telemetry Stream (The "NASA" Way)
        logger.info(f"GAME EVENT: {event_type}", extra={"data": event, "type": "GAME_EVENT"})
        
        # 2. Add to internal memory (legacy support)
        self.session_log.append(event)
        
        # 3. Persist to DB
        if self.current_session_id != -1:
            self.db.log_event(self.current_session_id, event_type, json.dumps(data))
            
        # Save on every event for robustness
        self.save_session_log()

    def save_session_log(self):
        # Legacy File Save - DISABLED (Redundant with app.jsonl and stats.db)
        return
        
        """
        try:
            filepath = os.path.join(self.log_dir, self.session_filename)
            # ... full_data update ... (omitted for brevity, keep existing logic if editing entire function)
            # Actually we just want to save the session file, keeping existing logic
            
            full_data = {
                "session_summary": {
                    "session_id": self.session_count,
                    "phase": self.current_phase,
                    "total_death_loss": self.total_death_loss,
                    "death_count": self.session.death_count,
                    "recovery_count": self.session.recovery_count,
                    "spent_at_merchants": self.spent_at_merchants,
                    "current_level": self.session.current_run_level,
                    "death_history": self.death_history
                },
                "events": self.session_log
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save session log: {e}")
        """

    def save_graph_log(self):
        try:
            if self.graph_log_file and self.graph_log_data:
                with open(self.graph_log_file, "w", encoding="utf-8") as f:
                    # No indent for compactness, it's a raw data dump
                    json.dump(self.graph_log_data, f)
        except Exception as e:
            logger.error(f"Failed to save graph log: {e}")

    def _run_loops(self):
        last_process_check = 0
        last_sys_check = 0
        while self.running:
            now = time.time()
            
            # 1. Process Check (every 5s)
            if now - last_process_check >= 5.0:
                self.check_process_task()
                last_process_check = now

            # 2. System Resource Check (every 10s)
            if now - last_sys_check >= 10.0:
                self.check_system_resources()
                last_sys_check = now
            
            # 3. Update Timer (every 200ms)
            try:
                self.update_timer_task()
            except Exception as e:
                logger.error(f"CRASH IN update_timer_task: {e}", exc_info=True)
                time.sleep(1.0) # Prevent tight loop spam
            
            time.sleep(0.2)

    def check_system_resources(self):
        """
        Monitors system resources and logs heartbeat to detect crashes.
        Runs every 10 seconds via _run_loops.
        """
        if psutil is None: return
        try:
            # Get system stats
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            
            # Get process memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Calculate uptime
            uptime = 0
            if self.session.start_time:
                uptime = int(time.time() - self.session.start_time)
            
            # Log system stats with memory
            self.log_session_event("SYSTEM_RESOURCE_STATS", {
                "cpu": cpu, 
                "ram": ram,
                "process_memory_mb": round(memory_mb, 1)
            })
            
            # Heartbeat logging every 60 seconds (6 cycles of 10s)
            if not hasattr(self, '_heartbeat_counter'):
                self._heartbeat_counter = 0
            
            self._heartbeat_counter += 1
            if self._heartbeat_counter >= 6:  # 60 seconds
                logger.info(
                    f"HEARTBEAT: Session {self.session_count}, "
                    f"Phase: {self.current_phase}, "
                    f"Uptime: {uptime}s, "
                    f"Memory: {memory_mb:.1f}MB"
                )
                self._heartbeat_counter = 0
                
        except Exception as e:
            logger.error(f"check_system_resources error: {e}", exc_info=True)

    def check_process_task(self):
        try:
            game_running = self.check_process(self.game_process)
            
            # "auto_hibernate" being True means we should hide when game closes.
            # "auto_hibernate" being False means we "Always Show" (Force Active).
            force_show = not self.config.get("auto_hibernate", True)
            
            # The logic: We should be active/awake if the Game is Running OR if Force Show is enabled.
            should_be_awake = game_running or force_show

            if should_be_awake:
                 if self.is_hibernating:
                     self.wake_up()
            else:
                 if not self.is_hibernating:
                     self.hibernate()
        except Exception as e:
            logger.error(f"StateService: check_process_task error: {e}")

    def update_timer_task(self):
        if self.session.timer_frozen or self.is_hibernating:
            return

        # if self.paused:
        #    return

        try:
            now = time.time()
            
            # --- Process Pending Spending Events (Grace Period) ---
            if self.pending_spending_event:
                event_time, spent_val, old_runes_val = self.pending_spending_event
                
                # --- GHOST CANCELLATION ---
                # If runes return to their previous high level, it was an OCR flicker
                if self.session.current_runes >= old_runes_val * 0.98:
                    self.pending_spending_event = None
                    if self.config.get("debug_mode"):
                        logger.info(f"Ghost Spending Cancelled: Runes returned to {self.session.current_runes} (from drop to {old_runes_val-spent_val})")
                    
                    # --- RETROACTIVE GRAPH REPAIR (User: "supprimer et redessiner") ---
                    # The graph recorded a dip during the pending state. Fix it by flattening the last ~5-10s.
                    # We overwrite the "Corrected" history with the current (restored) value.
                    # The "Raw" history remains untouched (showing the dip).
                    try:
                        restored_val = self.last_valid_total_runes # Should be high again
                        history_len = len(self.session.run_accumulated_history)
                        # Go back 60 seconds (Deep Repair for user request)
                        start_idx = max(0, history_len - 60)
                        for i in range(start_idx, history_len):
                            # Only pull UP, never pull down (in case we had real gains mixed in?)
                            # Actually, just flattening is safer for a ghost cancel.
                            if self.session.run_accumulated_history[i] < restored_val:
                                self.session.run_accumulated_history[i] = restored_val
                    except Exception as e:
                        logger.error(f"Graph Repair Error: {e}")

                elif now - event_time >= 10.0:
                    # Still no level up captured? Must be a real purchase.
                    # TICKET SYSTEM: Create ticket instead of immediate decision
                    ticket = self.ticket_manager.create_ticket(
                        amount=spent_val,
                        old_runes=old_runes_val,
                        new_runes=self.session.current_runes
                    )
                    
                    # Ticket will be resolved automatically by TicketManager
                    # based on evidence (level change, multiple of 100, etc.)
                    
                    self.pending_spending_event = None
                    
                # Clear old pending event if it exists
                if self.pending_spending_event and (now - self.pending_spending_event[0]) > 30:
                    self.pending_spending_event = None

            # --- TICKET SYSTEM: Periodic Resolution ---
            # Check pending tickets and resolve based on evidence
            self.ticket_manager.check_pending_tickets()
            
            # Apply validated tickets to game state
            for ticket in self.ticket_manager.get_validated_tickets():
                if ticket.resolution == "MERCHANT":
                    # Apply merchant spending
                    self.spent_at_merchants += ticket.amount
                    self.log_session_event("SPENDING", {"spent": ticket.amount, "total_spent": self.spent_at_merchants, "current": self.session.current_runes})
                    self.recent_spending_history.append((time.time(), ticket.amount))
                    
                    # GRAPH DECREASE: Subtract spending from accumulated history
                    for i in range(len(self.session.run_accumulated_history)):
                        self.session.run_accumulated_history[i] -= ticket.amount
                        if self.session.run_accumulated_history[i] < 0:
                            self.session.run_accumulated_history[i] = 0
                    
                    # Add spending event marker
                    self.session.graph_events.append({"t": len(self.session.run_accumulated_history), "type": "SPENDING", "amount": ticket.amount})
                    
                    if self.config.get("debug_mode"):
                        logger.info(f"TICKET_APPLIED: {ticket.id} | MERCHANT spending -{ticket.amount}. Total spent: {self.spent_at_merchants}")
                
                elif ticket.resolution == "LEVEL_UP":
                    # Level-up: No graph decrease (already handled by level change logic)
                    if self.config.get("debug_mode"):
                        logger.info(f"TICKET_APPLIED: {ticket.id} | LEVEL_UP (no graph change)")
                
                # Mark ticket as applied
                self.ticket_manager.mark_applied(ticket.id)
            
            # Cleanup old tickets (every 5 minutes)
            if int(time.time()) % 300 == 0:
                self.ticket_manager.cleanup_old_tickets()
            
            # --- Process _ignore_next_rune_gain Grace Period ---
            if self._ignore_next_rune_gain_grace_period:
                event_time = self._ignore_next_rune_gain_grace_period
                if now - event_time >= 5.0: # 5-second grace period
                    self._ignore_next_rune_gain = False
                    self._ignore_next_rune_gain_grace_period = None
            
            if self.session.start_time is not None and self.session.phase_index >= 0:
                phase = self.phases[self.session.phase_index]
                elapsed = time.time() - self.session.start_time
                
                if phase["duration"] > 0:
                    remaining = max(0, phase["duration"] - elapsed)
                    remaining_int = int(remaining)
                    
                    # NOTE: Auto-advance is now handled later (line ~771) via Trigger()
                    # This ensures SHRINK events are properly created when leaving shrinking phases

                    # --- RPS & GRAPH UPDATE (1Hz) ---
                    if time.time() - self.last_rps_update >= 1.0:
                        self.last_rps_update = time.time()
                        
                        if not self.rps_paused:
                            self.rune_gains_history.append(self.pending_rps_gain)
                            self.pending_rps_gain = 0
                            
                            # --- FULL-RUN GRAPH UPDATE ---
                            spent_on_levels = RuneData.get_total_runes_for_level(self.session.current_run_level) or 0
                            
                            # STRATEGY: Effective Wealth (Holes for Merchant Spending/Permanent Loss)
                            # We only count what is AVAILABLE for leveling.
                            current_calc = spent_on_levels + self.session.current_runes + self.lost_runes_pending
                            
                            # For Session Logs, we also calculate the Total Lifetime Wealth (generated total)
                            total_lifetime_wealth = current_calc + self.spent_at_merchants + self.permanent_loss
                            
                                # --- LEVEL-UP SYNC GUARD (Anti-Peak) ---
                            if self._level_up_pending_sync:
                                sync_time, level_cost = self._level_up_pending_sync
                                # Increased guard window to 12s for slow OCR updates
                                if now - sync_time < 12.0:
                                     # If Runes are still "High" (indicative of pre-spend state), mask the cost.
                                     # We assume if current > 20% of cost, we might still be seeing old value.
                                     # (Unless user literally farmed back 20% in 5 seconds? Unlikely inside menu).
                                     if self.session.current_runes >= level_cost * 0.2:
                                          current_calc -= level_cost
                                else:
                                     self._level_up_pending_sync = None

                            # --- GLITCH CLAMP ---
                            # If total jumps unreasonably high (e.g. > last + level_cost/2) without a boss event,
                            # clamp it to prevent graph scale ruin.
                            delta = current_calc - self.last_valid_total_runes
                            
                            # Initialize total_accumulated to prevent UnboundLocalError
                            total_accumulated = self.last_valid_total_runes
                            
                            if delta > 0 and self.session.phase_index >= 0:
                                # If delta is huge (> 50k or > 50% level cost) and NO Boss kill recently...
                                # We could clamp upward spikes, but we MUST allow downward regressions (holes).
                                pass

                                # STRATEGY: GRAPH RATCHET (Via GameRules)
                                # Enforce Monotonicity using central rules
                                
                                # Check if we have valid reasons to drop
                                is_valid_drop_reason = (self.pending_spending_event is not None)
                                
                                # Check if a death just occurred (within last 5 seconds)
                                is_recent_death = False
                                if self.session.graph_events:
                                    for evt in reversed(self.session.graph_events[-10:]):  # Check last 10 events
                                        if evt.get("type") == "DEATH":
                                            time_since_death = now - evt.get("t", 0)
                                            if time_since_death < 5.0:  # Death within last 5 seconds
                                                is_recent_death = True
                                                break
                                
                                # Validate using Logic Class
                                total_accumulated = GameRules.validate_graph_monotonicity(
                                    current_calc, 
                                    self.last_valid_total_runes,
                                    is_death=is_recent_death,  # Now properly detects deaths
                                    is_spending=is_valid_drop_reason
                                )
                                
                                if total_accumulated != current_calc and not is_valid_drop_reason:
                                     # Logic clamped it. It was a glitch.
                                     # Keep last valid
                                     self.last_valid_total_runes = total_accumulated
                                else:
                                     self.last_valid_total_runes = total_accumulated
                            
                            # FORCE 1 for first 15s (User request: "tricher sur le graph")
                            # We use the length of history as the time index (approx 1s per tick)
                            if len(self.session.run_accumulated_history) < 15:
                                 total_accumulated = 1
                            
                            # FORCE FREEZE at Boss 3 (Final Boss) - Phase Index 11+
                            # User request: "le graff s'arrete au debut du boss 3"
                            elif self.session.phase_index >= 11:
                                 total_accumulated = self.last_valid_total_runes
                            
                            # Raw calculation: Current Runes + Pending + Spent (Current snapshot, no retroactive fixes)
                            # We want this to be the "Naive" view.
                            # If we use self.spent_at_merchants, it is 'corrected' by reverts.
                            # But 'raw' means "what we saw". Ideally we'd store a separate 'raw_spent'.
                            # For simplicity, we'll store the 'current_calc' BEFORE it was potentially clamped/adjusted?
                            # Actually `current_calc` line 390 is good.
                            
                            self.session.run_accumulated_history.append(total_accumulated)
                            
                            # Raw history: We want it to be immutable.
                            self.run_accumulated_raw.append(current_calc)
                            

                            # --- GRAPH LOGGING ---
                            graph_entry = {
                                "t": float(f"{time.time():.2f}"),
                                "fmt": datetime.datetime.now().strftime("%H:%M:%S"),
                                "raw": current_calc, # Effective
                                "brute": total_lifetime_wealth, # Brute Total
                                "display": total_accumulated,
                                "comps": {
                                    "lvl_cost": spent_on_levels,
                                    "merch": self.spent_at_merchants,
                                    "curr": self.session.current_runes,
                                    "pend": self.lost_runes_pending,
                                    "perm": self.permanent_loss,
                                    "uncertain": self.runes_uncertain,
                                    "trust_idx": getattr(self, "last_trust_score", 100.0) # LOG TRUST IDX
                                }
                            }
                            self.graph_log_data.append(graph_entry)
                            
                            # Log every 1s
                            if time.time() - self.last_graph_log_time >= 1.0:
                                # logger.info(f"GRAPH DATA: {json.dumps(graph_entry)}")
                                self.last_graph_log_time = time.time()

                            if time.time() - self.last_graph_save >= 5.0:
                                self.save_graph_log()
                                self.last_graph_save = time.time()

                        self.smoothed_rps = sum(self.rune_gains_history) / 40.0
                    
                    self.update_runes_display(self.session.current_run_level)
                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    timer_str = f"{mins:02}:{secs:02}"
                    
                    # AUTO-ADVANCE: When timer expires, move to next phase
                    phase_just_changed = False
                    if remaining <= 0 and phase["duration"] > 0:
                        next_idx = self.session.phase_index + 1
                        if next_idx < len(self.phases):
                            logger.info(f"Timer expired. Auto-advancing from phase {self.session.phase_index} to {next_idx}")
                            self.Trigger(next_idx)
                            logger.info(f"✅ Trigger() completed. New phase_index={self.session.phase_index}")
                            # Reset timer for new phase
                            self.session.start_time = time.time()
                            phase_just_changed = True
                            # CRITICAL: Reload phase variable after Trigger() changed phase_index
                            phase = self.phases[self.session.phase_index]
                            elapsed = time.time() - self.session.start_time
                            remaining = max(0, phase["duration"] - elapsed)
                            remaining_int = int(remaining)
                            logger.info(f"✅ Phase reloaded: {phase['name']}, duration={phase['duration']}s, remaining={remaining:.1f}s")
                    
                    # Audio Announcements (only if NOT auto-advancing)
                    if not phase_just_changed and remaining_int != self.last_announcement_second:
                        is_storm = "Storm" in phase["name"]
                        if is_storm:
                            if remaining_int == 120: self.audio.announce("Fermeture de la zone dans 2 minutes")
                            elif remaining_int == 60: self.audio.announce("Fermeture de la zone dans 1 minute")
                            elif remaining_int == 30: self.audio.announce("Dans 30 secondes")
                            elif remaining_int == 5: self.audio.announce("5 secondes")
                            # Note: remaining_int == 0 case removed - handled by phase transition
                        self.last_announcement_second = remaining_int
                    
                    # Check for Phase Start Announcement
                    if self.session.phase_index != self.last_announced_phase:
                        logger.info(f"🔊 Phase start announcement check: phase={phase['name']}, is_storm={'Storm' in phase['name']}, phase_idx={self.session.phase_index}")
                        # Skip announcement for the very first phase (Day 1 - Storm) to avoid spam on startup
                        if "Storm" in phase["name"] and self.session.phase_index != 0:
                             d_min = phase["duration"] // 60
                             d_sec = phase["duration"] % 60
                             msg = "La zone se refermera dans "
                             if d_min > 0: msg += f"{d_min} minutes "
                             if d_sec > 0: msg += f"{d_sec} secondes"
                             logger.info(f"🔊 Announcing: {msg}")
                             self.audio.announce(msg)
                        self.last_announced_phase = self.session.phase_index
                        logger.info(f"✅ Phase start announcement complete")
                else:
                    # Stopwatch
                    mins = int(elapsed // 60)
                    secs = int(elapsed % 60)
                    timer_str = f"{mins:02}:{secs:02}"
                    
                # prefix = ""
                # if self.fast_mode_active: prefix += "🔴 "
                
                next_idx = self.session.phase_index + 1
                if phase["duration"] > 0 and next_idx < len(self.phases) and "Shrinking" in self.phases[next_idx]["name"]:
                    remaining = max(0, phase["duration"] - elapsed)
                    if remaining <= 30 and int(time.time() * 2) % 2 == 0:
                        pass # prefix += "⚠️ " # User likely doesn't want this either if they hate icons? 
                        # Actually user only complained about the record icon. I'll keep the warning or remove it?
                        # "il y a toujours le logo record... il a sa place colonne de droite."
                        # The warning is different. I'll just remove the Record one.
                        
                self.overlay.update_timer(f"{timer_str}")

            else:
                 # Detect menu exit (transition from Menu to Game)
                 is_currently_in_menu = getattr(self, "is_in_menu", False)
                 was_previously_in_menu = getattr(self, "_was_in_menu", False)
                 
                 if is_currently_in_menu:
                      self.overlay.update_timer("🏠 Menu")
                 else:
                      self.overlay.update_timer("00:00")
                      
                 # Detect transition: Menu (True) -> Game (False)
                 if was_previously_in_menu and not is_currently_in_menu:
                     logger.info("Menu exit detected - Resetting stats for fresh start")
                     self.session.current_run_level = 1
                     self.session.current_runes = 0
                     self.last_display_level = 1
                     self.last_display_runes = 0
                     
                 # Update previous state for next iteration
                 self._was_in_menu = is_currently_in_menu
                     
                 # Force stats update to show "Waiting" in Phase Name area
                 self.update_runes_display(self.session.current_run_level)
                 
        except Exception as e:
            logger.error(f"CRASH IN UPDATE_TIMER_TASK: {e}")
            import traceback
            logger.error(traceback.format_exc())


    def shutdown(self) -> None:
        self.running = False

    def schedule(self, delay_ms: int, callback):
        self.overlay.schedule(delay_ms, callback)
    
    def _update_debug_led(self, zone_name: str, text: str, confidence: float, burst_state: str):
        """Update Debug Overlay LED with burst state."""
        if hasattr(self, 'debug_overlay') and self.debug_overlay:
            # Update via signal (thread-safe)
            self.debug_overlay.update_signal.emit(zone_name, text, confidence)
            # Update burst state directly on widget (if exists)
            if zone_name in self.debug_overlay.widgets:
                widget = self.debug_overlay.widgets[zone_name]
                widget.burst_state = burst_state
                widget.update()

    # --- Process Monitor ---

    def check_process(self, process_name):
        # print(f"DEBUG: check_process({process_name})")
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            return False
        except Exception as e:
            logger.error(f"StateService: Process check error: {e}")
            return False

    def wake_up(self):
        logger.info("STATE: Waking up (Game detected or Auto-Hibernate disabled)...")
        self.is_hibernating = False
        self.overlay.show()
        self.vision.resume_capture()
        if self.tray:
            self.tray.set_hibernation_mode(False)

    def hibernate(self):
        logger.info("STATE: Hibernating (Game closed and Auto-Hibernate enabled)...")
        self.is_hibernating = True
        self.overlay.hide()
        self.vision.pause_capture()
        if self.tray:
            self.tray.set_hibernation_mode(True)

    def on_config_changed(self, config_key=None):
        if config_key is None or config_key == "nightreign":
            self._load_nr_constants()
            
    def _load_nr_constants(self):
        nr = self.config.get("nightreign", {})
        self.NR_SNOWBALL_D1 = nr.get("snowball_d1", 1.35)
        self.NR_SNOWBALL_D2 = nr.get("snowball_d2", 1.15)
        self.NR_FARMING_GOAL = nr.get("farming_goal", 337578)
        self.NR_DAY_DURATION = nr.get("day_duration", 840)
        self.NR_TOTAL_TIME = nr.get("total_time", 1680)
        self.NR_IDEAL_TARGET = RuneData.get_total_runes_for_level(nr.get("target_level", 14)) or 437578
        self.NR_BOSS_DROPS = 50000 # Fixed for now
        logger.info(f"StateService: NR Constants loaded (D1:{self.NR_SNOWBALL_D1}, D2:{self.NR_SNOWBALL_D2}, Goal:{self.NR_FARMING_GOAL})")
        logger.info(f"StateService: Config updated. Auto-Hibernate: {self.config.get('auto_hibernate', True)}")
        # Removed aggressive check to prevent crash on startup / threading issues
        pass

    # --- OCR & State Logic ---
    def on_tuning_status(self, is_active: bool):
        self.logic_paused = is_active
        if is_active:
             logger.info("StateService: Logic PAUSED (Tuner Active)")
        else:
             logger.info("StateService: Logic RESUMED")
             # Restore proper OCR state (in case Tuner forced it open)
             self._update_day_ocr_state()

    def on_ocr_result(self, text, width, offset, word_data, brightness=0, score=0):
        if self.logic_paused: return
        self.schedule(0, lambda: self.process_ocr_trigger(text, width, offset, word_data, brightness, score))

    def is_stats_stable(self, seconds=1.0) -> bool:
        """Returns True if Level and Runes have been unchanged for the given duration."""
        return (time.time() - self.last_stat_change_time) > seconds

    def _update_day_ocr_state(self):
        """
        Dynamically enables/disables the Day OCR Scanning to save resources.
        User Rules:
        1. Stop after Day 1 confirmed until Boss 1.
        2. Stop after Day 2 confirmed until end of run.
        """
        phase = self.session.phase_index
        
        # ENABLED only when waiting for Day 1 (-1) or Boss 1 (4)
        should_enable = (phase == -1 or phase == 4)
        
        # Re-enable if Victory detected (to wait for next run)
        if getattr(self, 'victory_detected', False):
            should_enable = True

        if getattr(self, '_last_day_ocr_state', None) != should_enable:
            self.vision.set_day_ocr_enabled(should_enable)
            self._last_day_ocr_state = should_enable

    def process_ocr_trigger(self, text, width, offset, word_data, brightness=0, score=0):
        # Update overlay score display immediately
        if score > 0:
            self.overlay.set_ocr_score(score)
        
        now = time.time()
        
        # --- BLACK SCREEN TRACKING ---
        if brightness < 20: 
            self.last_black_screen_end = now
            # If we are in a black screen, we don't need to process OCR triggers usually
            # But we continue just in case
        
        # 1. Clean Buffer
        self.trigger_buffer = [item for item in self.trigger_buffer if now - item[0] <= self.buffer_window]
        
        detected_trigger = None
        
        # Fast Mode Logic checks
        if self.fast_mode_active:
            time_since_last_jour = now - self.last_jour_detection if self.last_jour_detection > 0 else float('inf')
            time_since_last_trigger = now - self.last_fast_mode_trigger
            
            if time_since_last_jour > 3.0:
                self.fast_mode_active = False
                self.vision.set_scan_delay(0.2) # Standard 5 FPS
            elif now > self.fast_mode_end_time and time_since_last_trigger > 2.0:
                self.fast_mode_active = False
                self.vision.set_scan_delay(0.2) # Standard 5 FPS

        should_fast_mode = False
        
        if text:
            normalized = text.strip().upper()
            
            # Fast Mode Triggers
            if "JOUR" in normalized:
                should_fast_mode = True
                self.last_jour_detection = now
            elif word_data:
                for w in word_data:
                    if "JOUR" in w.get("text", "").upper():
                        should_fast_mode = True
                        self.last_jour_detection = now
                        break
            
            if not should_fast_mode:
                if any(x in normalized for x in ["JOU", "OUR"]):
                    should_fast_mode = True
            
            if not should_fast_mode and len(normalized) >= 3:
                for pat in self.pattern_manager.patterns.keys():
                    if "JOUR" in pat.upper() or normalized in pat:
                         should_fast_mode = True
                         break
            
            if not should_fast_mode and len(normalized) >= 1 and width > 800:
                 if normalized in ["J", "O", "U", "I", "II", "III"]:
                      should_fast_mode = True

            if should_fast_mode:
                self.overlay.show_recording(True)
                self.last_fast_mode_trigger = now
                if not self.fast_mode_active:
                    self.fast_mode_active = True
                    self.vision.set_scan_delay(0.066) # Fast 15 FPS
                    if now - self.last_beep_time > 2.0:
                         try: winsound.MessageBeep(winsound.MB_ICONWARNING)
                         except: pass
                         self.last_beep_time = now
                
                self.fast_mode_end_time = now + 10.0

            self.fast_mode_end_time = now + 10.0

            # --- FUZZY DAY LOGIC (User Request) ---
            # If we are in specific Boss Phases, allow ANY "JOUR" detection to trigger next day.
            fuzzy_day_idx = GameRules.map_fuzzy_day_trigger(normalized, self.session.phase_index)
            if fuzzy_day_idx:
                 target_day = f"DAY {fuzzy_day_idx}"
                 score = 100.0
                 logger.info(f"Fuzzy Trigger Promotion: '{normalized}' -> {target_day} (Phase Prerequisite Met)")
            else:
                 # Standard Pattern Match
                 target_day, score = self.pattern_manager.evaluate(normalized, text_width=width, center_offset=offset, word_data=word_data)
            
            # Apply Soft Guard Penalty
            
            # Apply Soft Guard Penalty
            if target_day:
                penalty = self.get_transition_penalty(target_day)
                score += penalty
                if penalty != 0 and self.config.get("debug_mode"):
                    logger.debug(f"Soft Guard Penalty for {target_day}: {penalty} (Final Score: {score})")

            # DEBUG: Print all evaluations
            if self.config.get("debug_mode") and (target_day or score > 20):
                if self.waiting_for_day1 and "JOUR" in normalized:
                     logger.info(f"WAITING_FOR_D1 Eval: '{normalized}' -> {target_day} (Score: {score})")
                elif target_day or score > 40:
                     logger.debug(f"Eval '{normalized}' -> {target_day} (Score: {score})")
            
            if target_day and score >= 55:
                detected_trigger = target_day
                self.current_matched_pattern = normalized
                if self.waiting_for_day1:
                     logger.info(f"MATCHED Candidate '{normalized}' -> {target_day} (Score: {score})")
                else:
                     logger.info(f"Trigger Candidate '{normalized}' -> {target_day} (Score: {score})")
                
                if not self.fast_mode_active:
                    self.fast_mode_active = True
                    self.vision.set_scan_delay(0.066) # Fast 15 FPS
                self.last_fast_mode_trigger = now
                
                if detected_trigger == "DAY 3":
                    self.fast_mode_end_time = now + 15.0
                    self.last_jour_detection = now
                else:
                    self.fast_mode_end_time = now + 10.0

        if detected_trigger:
            self.trigger_buffer.append((now, detected_trigger, score))
            logger.debug(f"Added to buffer. Buffer size: {len(self.trigger_buffer)}")

        if not self.trigger_buffer and not self.fast_mode_active:
             # Exclude Boss 2 (9) and Day 3 Prep (10) from early exit to allow fade detection
             if self.session.phase_index not in [9, 10]: 
                 self.overlay.show_recording(False)
                 return

        self.overlay.show_recording(True)
        
        # Consensus
        day_scores = {"DAY 1": 0.0, "DAY 2": 0.0, "DAY 3": 0.0}
        day_counts = {"DAY 1": 0, "DAY 2": 0, "DAY 3": 0}
        
        for item in self.trigger_buffer:
            _, val, s = item
            day_scores[val] += s
            day_counts[val] += 1
            
        final_decision = None
        if day_counts["DAY 3"] >= 2 and day_scores["DAY 3"] > 100:
            final_decision = "DAY 3"
        # HARDENED: Day 2 now requires 3 detections (was 2) and score > 240 (was 180)
        # This prevents false positives from low-confidence OCR (e.g., 75% conf "JOUR II")
        elif day_counts["DAY 2"] >= 3 and day_scores["DAY 2"] > 240:
            final_decision = "DAY 2"
        # Day 1 Reset: Require Temporal Persistence and High Score
        else:
            d1_items = [i for i in self.trigger_buffer if i[1] == "DAY 1"]
            if d1_items:
                # 1. Check Duration (Time between first and last detection in buffer)
                first_t = d1_items[0][0]
                last_t = d1_items[-1][0]
                duration = last_t - first_t
                
                # 2. Check Consensus
                if (duration >= 0.8 and day_counts["DAY 1"] >= 3 and day_scores["DAY 1"] > 250):
                    final_decision = "DAY 1"
                # Fallback for very high confidence single hit during initial startup?
                # No, better be safe. Manual Ctrl+Shift+R is the workaround.
                elif day_counts["DAY 1"] >= 1 and day_scores["DAY 1"] >= 300:
                    final_decision = "DAY 1"
                # 3. NASA-GRADE EARLY GAME SYNC: If we are specifically waiting for Day 1
                # we allow a much lower threshold to ensure we don't miss the fast banner.
                elif self.waiting_for_day1 and day_counts["DAY 1"] >= 1 and day_scores["DAY 1"] >= 80:
                    logger.info("🚀 EARLY GAME SYNC: Accept single-hit DAY 1 (waiting_for_day1 active)")
                    final_decision = "DAY 1"
            
        if final_decision and not self.triggered_recently:
            # --- STABILITY VALIDATION (User Request) ---
            # Real Day banners appear while the player is NOT actively leveling or gaining runes.
            # If stats are changing, it's likely an OCR error during gameplay.
            if self.is_stats_stable(1.2):
                if self.handle_trigger(final_decision):
                    logger.info(f"ACTIVATING TRIGGER {final_decision} (Stats Stable)")
                    self.triggered_recently = True
                    self.trigger_buffer = []
                    self.schedule(4000, lambda: setattr(self, 'triggered_recently', False))
                else:
                    # If blocked, clear buffer to avoid immediate retry but don't set triggered_recently long-term
                    self.trigger_buffer = []
            else:
                if self.config.get("debug_mode"):
                    logger.debug(f"FILTERED Trigger {final_decision}: Stats unstable (Changing in last 1.2s)")
                self.add_debug_warning(f"Filtered {final_decision}: Stats unstable")
                # If it's DAY 1, we might want to be more lenient for video scrubbing?
                # For now, stick to the rule to prevent Day 1 resets mid-boss due to noise.

        # Contextual Fade Detection for Day 3
        # --- GLOBAL BLACK SCREEN DETECTION (Runs in all phases for Death Logic) ---
        # Used for "Triple-Lock" Death Validation: Death requires a preceding Black Screen.
        
        # Periodic brightness logging for debugging (every 1s in log file)
        if now - self.last_brightness_log > 1.0:
             # Just log brightness if very dark or very bright to avoid spam
             if brightness < 10 or brightness > 200:
                 self.vision.log_debug(f"Brightness Check: {brightness:.1f}")
             self.last_brightness_log = now

        is_black = (brightness < 3) # Threshold 3 (Strict user request for caves)
        
        if is_black:
             if not self.in_black_screen:
                 self.in_black_screen = True
                 self.black_screen_start = now
                 self.vision.log_debug(f"!!! BLACK SCREEN DETECTED (Br: {brightness:.1f})")
        else:
             if self.in_black_screen:
                 duration = now - self.black_screen_start
                 self.in_black_screen = False
                 self.last_black_screen_end = now # MARK TIMESTAMP for Death Validation
                 self.vision.log_debug(f"DEBUG: BLACK SCREEN ENDED (Dur: {duration:.2f}s, Br: {brightness:.1f})")
                 
                 # Contextual Fade Logic (Day 3 Triggering)
                 if self.session.phase_index in [9, 10]:
                     # Single Pulse Fade (0.3s - 3.0s)
                     if 0.3 <= duration <= 3.0:
                         if self.session.phase_index == 9:
                             self.vision.log_debug(f">>> FADE SUCCESS: Boss 2 -> Day 3 Prep (Dur: {duration:.2f}s)")
                             self.trigger_day_3()
                         elif self.session.phase_index == 10:
                             # Wait 10s after entering Day 3 Prep before allowing Final Boss trigger
                             if now - self.last_phase_change_time > 10.0:
                                 self.vision.log_debug(f">>> FADE SUCCESS: Day 3 Prep -> Final Boss (Dur: {duration:.2f}s)")
                                 self.trigger_final_boss()
                             else:
                                 self.vision.log_debug(f"FADE IGNORED: Too soon after Day 3 Prep start ({now - self.last_phase_change_time:.1f}s)")
                     else:
                         if self.config.get("debug_mode"):
                             self.vision.log_debug(f"FADE REJECTED: Duration {duration:.2f}s out of range (0.3-3.0s)")
        
        # Victory check loop handled separately via `check_victory_loop` 
        # but needs to be triggered.
        if self.session.phase_index == 11 and not self.victory_check_active and not self.victory_detected:
             self.victory_check_active = True
             self.schedule(int(self.victory_check_interval * 1000), self.check_victory_loop)

    def on_menu_screen_detected(self, found, confidence):
        """
        Callback when Main Menu screen is detected.
        Requires 3 seconds of continuous detection before setting menu state.
        """
        now = time.time()
        
        if not found:
            # Menu not detected - reset validation
            self._menu_first_detected = 0
            self._menu_validated = False
            return
        
        logger.info(f"MAIN MENU DETECTED ({confidence:.2f})")
        
        # Start or continue temporal validation
        if self._menu_first_detected == 0:
            self._menu_first_detected = now
            logger.info("Menu detection started - waiting 3s for validation...")
            return
        
        # Check if 3 seconds have passed
        elapsed = now - self._menu_first_detected
        if elapsed < 3.0:
            logger.info(f"Menu validation in progress... ({elapsed:.1f}/3.0s)")
            return
        
        # Validated! Set menu state (only once)
        if not self._menu_validated:
            logger.info("Menu VALIDATED after 3s - Setting menu state")
            self._menu_validated = True
            self.is_in_menu = True
            self.overlay.update_timer("🏠 Menu")
        
        # Only reset if we're in an active run (not already in Waiting state)
        if self.session.phase_index == -1: 
            return

        logger.info("Resetting run...")
        
        # Determine valid session end reason (Victory vs Reset/Death)
        reason = "RESET"
        if self.victory_detected:
            reason = "VICTORY_CONFIRMED"
        
        # End current session if active
        if self.current_session_id != -1:
             self.db.end_session(self.current_session_id, reason)
             self.current_session_id = -1

        # Full Reset Logic
        self.session.phase_index = -1
        self.Trigger(-1) # -1 = Waiting/Ready
        
        # Clear Data
        self.session.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.session.graph_events = []
        self.session.death_count = 0
        self.session.recovery_count = 0
        self.session.current_runes = 0
        self.session.current_run_level = 1
        
        # Force UI Update
        self.overlay.update_run_stats(self._get_stats_dict())
        
        logger.info("Run reset complete")

    def on_level_detected(self, level: int, confidence: float = 100.0):
        # Pause logic if tuner is active
        if self.logic_paused: return
        
        # Valid range check (assuming max level 713)
        if level < 1 or level > 713: return
        
        # Stability / Consensus Mechanism (TRUST SYSTEM):
        # We only accept a level change if we see it consistent over multiple frames.
        # WEIGHTING: High confidence needs less consensus. Low confidence needs more.
        
        required_consensus = 2
        if confidence < 70.0:
            required_consensus = 5 # Low trust -> Verify for longer
        elif confidence < 85.0:
             required_consensus = 3
             
        if level == self.pending_level:
            self.level_consensus_count += 1
        else:
            self.pending_level = level
            self.level_consensus_count = 1
            
        # NASA-grade Early Game Detection: ACTIVATE IMMEDIATELY on first frame 
        # because the banner might appear very quickly (within 100ms).
        if level == 1 and self.session.phase_index == -1 and not self.waiting_for_day1:
            logger.info("🚀 EARLY GAME: Level 1 detected (First Frame) - Activating JOUR I monitoring")
            self.waiting_for_day1 = True
            self.session._current_run_level = 1  # Set BEFORE freezing
            self.session.stats_frozen = True
            # Emit event
            bus.publish(EarlyGameDetectedEvent(level=1))
            
        # Check against dynamic requirement for standard updates
        if self.level_consensus_count >= required_consensus:
            # --- BURST VERIFICATION (Premium Reliability) ---
            # If a change is suspected, we trigger a high-speed burst to confirm.
            if level != self.session.current_run_level:
                # Check for Hidden HUD (Low Confidence / Junk Read)
                is_hud_hidden = (confidence < 40.0) or (level == 0)
                
                if is_hud_hidden:
                    # If HUD is hidden, we keep the PREVIOUS level to ensure
                    # Level-up indicators STAY visible at the last known position.
                    if self.config.get("debug_mode") and self.frame_count % 60 == 0:
                        logger.info(f"Level Change {self.session.current_run_level}→{level} deferred: HUD Hidden (Conf: {confidence:.1f})")
                    return
                    
                # Trigger Burst
                self.level_led_state = 'burst'  # LED: Orange (scanning)
                
                # Update Debug Overlay LED immediately (so user sees orange)
                if self.config.get("debug_mode"):
                    self._update_debug_led("Level", "...", 50, 'burst')
                
                burst = self.vision.request_level_burst()
                if burst:
                    from collections import Counter
                    counts = Counter(burst)
                    most_common, freq = counts.most_common(1)[0]
                    
                    # Changed from 3/5 to 4/5 majority (per user questionnaire)
                    if freq < 4:
                        if self.config.get("debug_mode"):
                            logger.info(f"Level Burst Failed: Inconsistent results {burst} (need 4/5, got {freq}/5). Waiting...")
                        self.level_led_state = 'rejected'  # LED: Red (failed validation)
                        
                        # Update LED and keep red for 500ms
                        if self.config.get("debug_mode"):
                            self._update_debug_led("Level", str(most_common), freq * 20, 'rejected')
                            self.schedule(500, lambda: setattr(self, 'level_led_state', 'idle'))
                        return
                    
                    # Normalize to burst consensus
                    level = most_common
                    self.level_led_state = 'validated'  # LED: Green (consensus reached)
                    
                    # Update Debug Overlay LED and keep green for 300ms
                    if self.config.get("debug_mode"):
                        self._update_debug_led("Level", str(level), freq * 20, 'validated')
                        self.schedule(300, lambda: setattr(self, 'level_led_state', 'idle'))

            # Only update if changed (or first time after init)
            if level != self.session.current_run_level:
                # If run is NOT active, just update UI and exit to prevent logging/side-effects
                if self.session.phase_index == -1:
                    # Bypass freeze for UI sync during pre-run phase
                    self.session._current_run_level = level
                    self.schedule(0, lambda: self.update_runes_display(level))
                    self.level_consensus_count = 0 
                    return

                old_level = self.session.current_run_level
                
                # --- CANCEL PENDING SPENDING ---
                # A level change (up or down) means the rune drop was likely due to leveling or death.
                if self.pending_spending_event:
                    self.pending_spending_event = None
                    if self.config.get("debug_mode"):
                        logger.info("Pending SPENDING cancelled (Level Change detected)")
                
                # --- SANITY CHECK: MAX JUMP (OCR Guard) ---
                # Example: jumping from Level 3 to 30 is impossible in 1 frame.
                # We allow up to +3 levels in one update to handle fast menuing.
                # BUT, if we are desynced (e.g. system thinks Lvl 4, actual is Lvl 9), we MUST allow correction
                # if the new value is stable for a long time.
                
                # CRITICAL FIX: During the first 30 seconds of a session, allow immediate level sync
                # This handles the case where the timer starts at level 1 but the player is already at level 7+
                session_age = time.time() - self.session.start_time
                is_early_session = session_age < 30.0
                
                if level > old_level + 3:
                     # If we're in the first 30 seconds, accept the level immediately (startup sync)
                     if is_early_session:
                         logger.info(f"EARLY SESSION: Accepting level jump {old_level}→{level} (startup sync)")
                     # Otherwise, require sustained consensus
                     elif self.level_consensus_count < 10:
                         logger.warning(f"IGNORED Level Jump {old_level}->{level} (Too large). Waiting for sustained consensus ({self.level_consensus_count}/10).")
                         self.add_debug_warning(f"Ignored Level Jump {old_level}->{level}")
                         return
                     else:
                         logger.warning(f"FORCING LEVEL CORRECTION {old_level}->{level} after sustained consensus.")
                         # Proceed to update...
                
                # --- SANITY CHECK: MAX DROP (User Rule) ---
                # "Impossible dans le jeu de perdre 2 niveau d'un coup"
                # Allowed: Drop of 1 (Correction of recent +1 misread).
                # Rejected: Drop > 1 (e.g. 9 -> 4).
                # Rejected: Drop to 1 (Accidental Reset). Now requires Force Correction (5s).
                if old_level - level > 1:
                     # If we're in the first 30 seconds, accept the level immediately (startup sync)
                     if is_early_session:
                         logger.info(f"EARLY SESSION: Accepting level drop {old_level}→{level} (startup sync)")
                     # Otherwise, require consensus
                     elif self.level_consensus_count < 10:
                         logger.warning(f"IGNORED Massive Level Drop {old_level}->{level} (Impossible > 1 drop). Keeping {old_level}. Waiting for consensus ({self.level_consensus_count}/10).")
                         self.add_debug_warning(f"Ignored Impossible Drop {old_level}->{level}")
                         # Do NOT reset consensus here, keep counting!
                         return
                     else:
                         logger.warning(f"FORCING LEVEL DROP CORRECTION {old_level}->{level} after sustained consensus.")
                         # Proceed...
                
                # --- SET UNCERTAINTY (Level Change) ---
                if level != old_level:
                     self.runes_uncertain = True
                     self.runes_uncertain_since = time.time()
                     if self.config.get("debug_mode"):
                        logger.info("Runes Marked UNCERTAIN (Level Change)")

                # --- DEATH LOGIC (TRIPLE LOCK) ---
                # --- DEATH LOGIC (STRICT STAT BASED) ---
                # Delegated to GameRules for consistent rules
                
                curr_runes = self.session.current_runes
                
                # Pass timestamp of last confirmed black screen
                last_black_screen = getattr(self, 'last_black_screen_end', 0)
                is_stat_death = GameRules.is_death_confirmed(
                    old_level, level, curr_runes, 
                    last_black_screen_time=self.last_black_screen_end
                )
                
                if is_stat_death:
                     logger.warning(f"DEATH CONFIRMED (Stat Based): Level {old_level}->{level} (-1) & Runes {curr_runes} (<50).")
                elif level < old_level:
                     # If Logic says NO, but level dropped, it's an OCR error/correction.
                     logger.warning(f"IGNORED Level Drop {old_level}->{level}: Rejected by GameRules (Runes: {curr_runes}).")
                     return

                if level < old_level and not is_stat_death:
                     # This is just a Correction (e.g. 8 -> 7) or non-death drop.
                     # Do NOT trigger death. Do NOT revert spending.
                     # Update level silently.
                     self.session.current_run_level = level
                     self.schedule(0, lambda: self.update_runes_display(level))
                     return
                     
                if is_stat_death:
                    # --- CONFIRMED DEATH (Flow continues below) ---

                    # --- CONFIRMED DEATH ---
                    # If we have pending runes from a previous death, they are now PERMANENTLY LOST.
                    if self.lost_runes_pending > 0:
                        self.permanent_loss += self.lost_runes_pending
                        self.log_session_event("PERMANENT_LOSS", {"amount": self.lost_runes_pending})
                        self.lost_runes_pending = 0 

                    # --- SPENDING CORRECTION (Anti-Spike for Death) ---
                    # If we misidentified the rune drop as spending in the last few seconds, revert it.
                    reverted_amount = 0
                    valid_history = []
                    for t, amount in self.recent_spending_history:
                        if now - t <= 5.0:
                            reverted_amount += amount
                        else:
                            valid_history.append((t, amount))
                            
                    if reverted_amount > 0:
                        self.spent_at_merchants -= reverted_amount
                        if self.spent_at_merchants < 0: self.spent_at_merchants = 0
                        self.log_session_event("SPENDING_REVERTED", {"amount": reverted_amount, "reason": f"Death/Level Drop {old_level}->{level}"})
                        logger.info(f"Reverted {reverted_amount} spending due to Death detection. Correcting graph...")
                        
                        # --- GRAPH RECONSTRUCTION ---
                        self.last_valid_total_runes -= reverted_amount
                        if self.last_valid_total_runes < 0: self.last_valid_total_runes = 0
                        # Correct "Entire" history (or reasonably deep) as requested
                        # We go back up to 300 seconds (5 mins) which covers any plausible recent spending
                        history_len = len(self.session.run_accumulated_history)
                        for i in range(max(0, history_len - 300), history_len):
                            self.session.run_accumulated_history[i] -= reverted_amount
                            if self.session.run_accumulated_history[i] < 0: self.session.run_accumulated_history[i] = 0
                    
                    self.recent_spending_history = valid_history

                    # --- DEATH CALCULATION ---
                    lost_level_cost = RuneData._LEVEL_COSTS.get(old_level, 0)
                    death_runes = self.last_runes_reading 
                    total_loss = death_runes + lost_level_cost + reverted_amount
                    
                    self.session.death_count += 1
                    self.total_death_loss += total_loss
                    self.lost_runes_pending = total_loss # New bloodstain created
                    
                    death_event = {
                            "death_num": self.session.death_count,
                            "old_level": old_level,
                            "new_level": level,
                            "runes_at_death": death_runes,
                            "level_cost_lost": lost_level_cost,
                            "total_loss": total_loss
                        }
                    self.death_history.append(death_event)
                    self.log_session_event("DEATH", death_event)
                    self._ignore_next_rune_drop = True 
                    self.session.graph_events.append({"t": len(self.session.run_accumulated_history), "type": "DEATH"})
                
                # --- LEVEL UP LOGIC ---
                elif level > old_level:
                    # --- SPENDING CORRECTION (Anti-Spike for Level Up) ---
                    now = time.time()
                    reverted_amount = 0
                    valid_history = []
                    
                    for t, amount in self.recent_spending_history:
                        if now - t <= 5.0:
                            reverted_amount += amount
                        else:
                            valid_history.append((t, amount))
                            
                    if reverted_amount > 0:
                        self.spent_at_merchants -= reverted_amount
                        if self.spent_at_merchants < 0: self.spent_at_merchants = 0
                        self.log_session_event("SPENDING_REVERTED", {"amount": reverted_amount, "reason": f"Level Up {old_level}->{level}"})
                        logger.info(f"Reverted {reverted_amount} spending due to Level Up detection. Correcting graph...")
                        
                        # --- GRAPH RECONSTRUCTION ---
                        self.last_valid_total_runes -= reverted_amount
                        if self.last_valid_total_runes < 0: self.last_valid_total_runes = 0
                        # Correct "Entire" history (or reasonably deep) as requested
                        # We go back up to 300 seconds (5 mins) to catch any lingering spending
                        history_len = len(self.session.run_accumulated_history)
                        for i in range(max(0, history_len - 300), history_len):
                            self.session.run_accumulated_history[i] -= reverted_amount
                            if self.session.run_accumulated_history[i] < 0: self.session.run_accumulated_history[i] = 0
                        
                    self.recent_spending_history = valid_history

                    self.log_session_event("LEVEL_UP", {"old": old_level, "new": level})
                    self._ignore_next_rune_drop = True 
                    
                    # --- IGNORE NEXT GAIN (Post-Leveling) ---
                    self._ignore_next_rune_gain = True
                    self._ignore_next_rune_gain_grace_period = time.time()
                    
                    # --- LEVEL-UP SYNC GUARD (Anti-Peak) ---
                    # Calculate total cost of ALL levels gained in this jump
                    total_jump_cost = 0
                    for l in range(old_level + 1, level + 1):
                        total_jump_cost += RuneData._LEVEL_COSTS.get(l, 0)
                        
                    if total_jump_cost > 0:
                        self._level_up_pending_sync = (time.time(), total_jump_cost)
                        if self.config.get("debug_mode"):
                            logger.info(f"Level-Up Sync Guard Activated (Expected Drop: {total_jump_cost})")
                
                # TICKET SYSTEM: Add level-up evidence to pending tickets
                for ticket in self.ticket_manager.get_active_tickets():
                    level_cost = RuneData._LEVEL_COSTS.get(old_level, 0)
                    # Check if ticket amount matches level cost
                    if abs(ticket.amount - total_jump_cost) < 100:
                        self.ticket_manager.add_evidence(ticket.id, "level_up_detected", True)
                        self.ticket_manager.add_evidence(ticket.id, "level_cost_match", True)
                
                if self.config.get("debug_mode"):
                    logger.info(f"Level Changed (Consensus): {old_level} -> {level}")
                    logger.info(f"DEBUG_LEVEL: Level-up detected. Old: {old_level}, New: {level}, Burst validated")
                
                self.session.current_run_level = level
                self.last_stat_change_time = time.time()
                self.schedule(0, lambda: self.update_runes_display(level))
                self.level_consensus_count = 0 

    def on_runes_detected(self, runes: int, confidence: float = 100.0):
        if self.logic_paused: return
        
        # Update internal state (Always active for UI)
        self.last_runes_reading = runes
        
        # If run is not active, we just update the UI (via current_runes) but NOT history
        if self.session.phase_index == -1:
            # FLICKER GUARD (Pre-Run) - AGGRESSIVE
            # The OCR is extremely unstable during startup (Value -> 0 -> Value).
            # If we drop to 0/low unexpectedly, we just IGNORE it completely if we already have a valid reading.
            # We assume you don't "lose" runes in the loading screen.
            if runes < 10 and self.session._current_runes > 100:
                 return 
            
            # Reset spam limiter on valid read
            if runes > 10: self.pre_run_spam_limit = 0

            # Bypass freeze for UI sync during pre-run phase
            self.session._current_runes = runes
            # Force simple UI update
            self.update_runes_display(self.session.current_run_level)
            return
        
        # --- DATA CLEANING (Anti-Noise) ---
        # 1. CHANGE GATE: PROCESS LOGIC ONLY IF VALUE DIFFERS FROM CURRENT CONFIRMED STATE
        # Hallucination Guard (Anti-Noise)
        # We use a persistence counter to allow real "0" readings (Death) to pass through eventually.
        # FIX: Removed `not self.in_black_screen` check. Even in black screen, we shouldn't drop to 0 instantly.
        # Increased persistence to 10 (approx 2s at 5Hz) to prevent flickering.
        if self.session.current_runes > 100 and runes < 10:
            self.low_value_persistence = getattr(self, 'low_value_persistence', 0) + 1
            if self.low_value_persistence < 15: # Hold for ~2-3s (Robust Debounce)
                return # Block update
            else:
                 if self.config.get("debug_mode"): logger.info(f"Hallucination Filter Bypassed: Sustained Low Value ({runes})")
        else:
            self.low_value_persistence = 0

        if runes != self.session.current_runes:
            
            # --- TRUST SYSTEM: LOW CONFIDENCE REJECTION ---
            if confidence < 70.0:
                 self.runes_uncertain = True
                 self.runes_uncertain_since = time.time()
                 if confidence < 50.0: 
                     return # Junk reading

            # --- BURST VALIDATION (Mandatory for Level/Runes) ---
            self.runes_led_state = 'burst'  # LED: Orange (scanning)
            
            # Update Debug Overlay LED immediately
            if self.config.get("debug_mode"):
                self._update_debug_led("Runes", "...", 50, 'burst')
            
            burst_results = self.vision.request_runes_burst()
            if not burst_results:
                self.runes_led_state = 'rejected'  # LED: Red (no burst data)
                if self.config.get("debug_mode"):
                    self._update_debug_led("Runes", "FAIL", 0, 'rejected')
                    self.schedule(500, lambda: setattr(self, 'runes_led_state', 'idle'))
                return
            
            from collections import Counter
            counts = Counter(burst_results)
            most_common, frequency = counts.most_common(1)[0]
            
            # Require Consensus (3/5)
            if frequency < 3:
                self.runes_led_state = 'rejected'  # LED: Red (failed consensus)
                if self.config.get("debug_mode"):
                    self._update_debug_led("Runes", str(most_common), frequency * 20, 'rejected')
                    self.schedule(500, lambda: setattr(self, 'runes_led_state', 'idle'))
                return
            
            # Normalize to the consensus value
            runes = most_common
            self.runes_led_state = 'validated'  # LED: Green (consensus reached)
            
            # Update Debug Overlay LED and keep green for 300ms
            if self.config.get("debug_mode"):
                self._update_debug_led("Runes", str(runes), frequency * 20, 'validated')
                self.schedule(300, lambda: setattr(self, 'runes_led_state', 'idle'))

            # Re-check change gate after normalization
            if runes == self.session.current_runes: pass 
            else:
                # --- GAIN/STABILITY VERIFICATION (2-STEP) ---
                if runes != self.gain_verification_candidate:
                     # Check for Digit-Shift Spike (e.g., 15k -> 65k)
                     is_suspicious = False
                     s_curr = str(max(0, self.session.current_runes))
                     s_new = str(runes)
                     if len(s_curr) == len(s_new) and len(s_new) >= 5:
                         diff_digits = sum(1 for c1, c2 in zip(s_curr, s_new) if c1 != c2)
                         if diff_digits == 1 and abs(runes - self.session.current_runes) >= 10000:
                             is_suspicious = True

                     # Start tracking the new candidate immediately
                     self.gain_verification_candidate = runes
                     self.spike_persistence = 1 if is_suspicious else 0
                     return 

                # If same as candidate, check for suspicious persistence
                if self.spike_persistence > 0:
                     self.spike_persistence += 1
                     # Reduced from 3 to 2 hits (per user: "digit shift dure une fraction de seconde")
                     if self.spike_persistence < 2:
                         return

                # If we are here, BURST passed AND 2/3-STEP verification passed.
                self.gain_verification_candidate = -1 
                self.spike_persistence = 0
                
                logger.info(f"DEBUG_RUNES: VALIDATED {self.session.current_runes} -> {runes}")

                # --- IGNORE NEXT GAIN (After Level Up) ---
                if self._ignore_next_rune_gain and runes > self.session.current_runes:
                    self._ignore_next_rune_gain = False
                    self._ignore_next_rune_gain_grace_period = None
                    self.session.current_runes = runes 
                    self.last_runes_reading = runes
                    return

                diff = runes - self.last_runes_reading
                
                # --- CLEAR SYNC GUARD EARLY ---
                if self._level_up_pending_sync and diff < 0:
                    _, level_cost = self._level_up_pending_sync
                    if abs(diff) >= level_cost * 0.8:
                        self._level_up_pending_sync = None

                # A. SPENDING (Negative diff)
                if diff < 0:
                    if self._ignore_next_rune_drop:
                        self._ignore_next_rune_drop = False
                    else:
                        if not self.is_stats_stable(1.5): return # Reject unstable drops
                        
                        # --- SUSPICIOUS DROP FILTER (Digit Shift) ---
                        # If drop looks like a digit swap (e.g. 7774 -> 7174), it's highly likely a glitch.
                        # We require EXTRA STABILITY (15s+) or treat it as noise.
                        # Actually, we just flag it as UNCERTAIN and let validity check happen later.
                        is_digit_shift = self._is_digit_shift_drop(self.last_runes_reading, runes)
                        if is_digit_shift:
                             if self.config.get("debug_mode"):
                                 logger.warning(f"SUSPICIOUS DROP DETECTED (Digit Shift): {self.last_runes_reading} -> {runes}. Holding for verification.")
                             self.runes_uncertain = True
                             self.runes_uncertain_since = time.time()
                             # Do NOT register pending spending yet! Wait for it to stabilize for real.
                             # Actually, we rely on `is_stats_stable` which is only 1.5s. 
                             # We should return here to force "longer" stability?
                             # Yes, let's ignore it for now. If it persists for 5s, it will eventually pass.
                             # But `on_runes_detected` updates `current_runes` at the end!
                             # We must BLOCK the update if we suspect it.
                             
                        
                        spent = abs(diff)
                        self.pending_spending_event = (time.time(), spent, self.last_runes_reading)
                        self.runes_uncertain = True
                        self.runes_uncertain_since = time.time()
                        
                        # --- RETROACTIVE DEATH CHECK ---
                        # If we just dropped to near 0, and we recently had a "Silent Level Drop", it was a death.
                        if runes < 100 and hasattr(self, 'last_silent_level_drop'):
                             t_drop, old_lvl, new_lvl = self.last_silent_level_drop
                             # 10s window to link the two events
                             if time.time() - t_drop < 10.0:
                                  logger.warning(f"RETROACTIVE DEATH CONFIRMED: Level Drop {old_lvl}->{new_lvl} followed by Rune Drop to {runes}.")
                                  # Manually trigger death logic
                                  self.handle_retroactive_death(old_lvl, new_lvl, self.last_runes_reading) # Pass the PREVIOUS rune value (the dropped amount)
                                  self.last_silent_level_drop = None # Consumed
                
                # B. GAIN (Positive diff)
                elif diff > 0:
                    gain = diff
                    if gain > 500000:
                        logger.warning(f"OCR Doubt: Massive jump (+{gain})")
                        self.log_session_event("OCR_DOUBT", {"gain": gain, "current": runes})

                    # --- GHOST SPENDING REVERSAL ---
                    # If we just had a large gain that roughly matches a recent spending,
                    # it was likely an OCR error that exceeded the 5s/10s grace period.
                    # Clean up old history first (> 5 mins)
                    now = time.time()
                    self.recent_spending_history = [s for s in self.recent_spending_history if now - s[0] < 300]
                    
                    for i, (ts, amount) in enumerate(self.recent_spending_history):
                        # Use a tolerance of 1% or 200 runes
                        if abs(gain - amount) < max(200, amount * 0.01):
                            self.spent_at_merchants -= amount
                            self.log_session_event("SPENDING_REVERTED", {"amount": amount, "reason": "Ghost Recovery (OCR Correction)"})
                            self.recent_spending_history.pop(i)
                            gain = 0 # Don't count it as a real gain (RPS)
                            if self.config.get("debug_mode"):
                                logger.info(f"Ghost Spending Reverted: +{amount} matched previous spend.")
                            break
                    
                    # RUNE RECOVERY (Manual Target Match or Absolute Return)
                    # 1. Delta Match: Exact gain matches loss (Clean OCR)
                    # 2. Absolute Match: Current runes match pending loss (Glitchy OCR or intermediate gains)
                    is_recovery = False
                    if self.lost_runes_pending > 0:
                        # Delta Match (Standard) - Strict
                        if gain == self.lost_runes_pending: 
                            is_recovery = True
                        # Absolute Match (Fallback for "12k glitch -> 34k")
                        # Checks if we are back to within 10% or 2000 runes of the lost amount.
                        # This handles cases where the "Drop" was misread (e.g. reading 12k instead of 0), so the Delta is wrong,
                        # but the "Recovery" restores the full previous amount.
                        # Strict Match (User Request: "Strictement egale")
                        if runes == self.lost_runes_pending:
                            is_recovery = True
                            if self.config.get("debug_mode"): logger.info(f"Recovery VALIDATED: {runes} == {self.lost_runes_pending}")
                        
                        else:
                             # No fuzzy match allowed per strict rules
                             pass

                    if is_recovery:
                        self.session.recovery_count += 1 
                        self.log_session_event("RUNE_RECOVERY", {"recovered": self.lost_runes_pending})
                        self.session.graph_events.append({"t": len(self.session.run_accumulated_history), "type": "RECOVERY"})
                        if self.config.get("debug_mode"):
                            logger.info(f"DEBUG_RUNES [ACTION]: RECOVERY DETECTED (+{self.lost_runes_pending})")
                        self.lost_runes_pending = 0 
                        gain = 0 
                        # Note: UI will update on next update_timer_task cycle (200ms) 
                    
                    if gain > 0: self.pending_rps_gain += gain

                # COMMIT UPDATES
                if self.config.get("debug_mode"):
                    logger.info(f"DEBUG_RUNES [COMMIT]: {self.session.current_runes} -> {runes}")
                self.session.current_runes = runes
                self.last_runes_reading = runes
                self.last_stat_change_time = time.time() 

        # 3. STABILITY MONITOR (Always runs to clear uncertainty)
        if self.runes_uncertain:
            if runes == self.last_stable_runes_val:
                if time.time() - self.last_stable_runes_time > 2.0:
                    self.runes_uncertain = False
                    if self.config.get("debug_mode"): logger.info("Runes Marked CERTAIN/STABLE.")
            else:
                self.last_stable_runes_val = runes
                self.last_stable_runes_time = time.time()
        else:
             self.last_stable_runes_val = runes
             self.last_stable_runes_time = time.time()

        # Update display every frame
        self.schedule(0, lambda: self.update_runes_display(self.session.current_run_level))

    def _is_digit_shift_drop(self, old_val: int, new_val: int) -> bool:
        """
        Detects if a drop is likely a single digit misread (e.g. 7774 -> 7174).
        """
        s_old = str(old_val)
        s_new = str(new_val)
        if len(s_old) != len(s_new): return False
        
        diff_count = sum(1 for a, b in zip(s_old, s_new) if a != b)
        if diff_count == 1:
             return True
        return False

    def update_runes_display(self, level: int):
        current_runes = getattr(self.session, 'current_runes', 0)
        
        # --- BLINDNESS FILTER (Inventory / Black Screen) ---
        # If OCR sees 0/0, it's likely hidden UI. We hold last valid display values.
        is_blind = (level <= 0 and current_runes <= 0)
        
        if not is_blind:
             self.last_display_level = level
             self.last_display_runes = current_runes
        
        disp_lvl = self.last_display_level
        disp_runes = self.last_display_runes
        
        # Always use monotonicity for total runes display
        total_runes_to_show = self.last_valid_total_runes
        # Calculate Stats for UI
        potential_lvl = RuneData.calculate_potential_level(disp_lvl, disp_runes)
        
        # DEBUG: Log Level Up Calculation (Throttled 5s)
        if potential_lvl > disp_lvl and (time.time() - getattr(self, 'last_potential_level_log', 0) > 5.0):
             cost_next = RuneData.get_runes_for_next_level(disp_lvl)
             logger.info(f"LEVEL UP CHECK: Level {disp_lvl} -> {potential_lvl}. Runes: {disp_runes}. Cost Next: {cost_next}. (Indicator: {'READY' if potential_lvl > disp_lvl else 'NO'})")
             self.last_potential_level_log = time.time()

        # User refinement: Next Level = Potential + 1
        target_level = potential_lvl + 1
        needed = RuneData.get_total_runes_for_level(target_level) or 0
        # Cost to reach from current level
        runes_already_spent = RuneData.get_total_runes_for_level(disp_lvl) or 0
        relative_needed = needed - runes_already_spent
        missing = max(0, relative_needed - disp_runes)
        
        # Define p_name for Stats
        # Define p_name for Stats
        if self.session.phase_index >= 0:
             p_name = self.phases[self.session.phase_index]["name"]
             # Shorten for UI
             if "Shrinking" in p_name: p_name = p_name.replace("Shrinking", "Shrink")
             if "Preparation" in p_name: p_name = p_name.replace("Preparation", "Prep")
             
             if self.config.get("debug_mode"):
                 logger.debug(f"UI UPDATE: Phase Index {self.session.phase_index} -> Name '{p_name}'")
        else:
             p_name = "WAITING"

        # Create structured stats
        stats = {
            "level": disp_lvl,
            "potential_level": potential_lvl,
            "current_runes": disp_runes,
            "total_runes": total_runes_to_show,
            "next_level": target_level,
            "needed_runes": relative_needed,
            "missing_runes": missing,
            "is_max_level": disp_lvl >= 15,
            "run_history": self.session.run_accumulated_history,
            "run_history_raw": self.run_accumulated_raw,
            "transitions": getattr(self.session, 'ui_transitions', []),
            "death_count": self.session.death_count,
            "recovery_count": self.session.recovery_count,
            "phase_name": p_name,
            "spent_at_merchants": self.spent_at_merchants,
            "graph_events": self.session.graph_events,
            "graph_start_time": getattr(self, "graph_start_time", 0),
            "rps": self.smoothed_rps,
            "grade": self.calculate_efficiency_grade(),
            "time_to_level": self.calculate_time_to_level(missing),
            "delta_runes": self.last_calculated_delta,
            "remaining_time": self.NR_TOTAL_TIME - len(self.session.run_accumulated_history), # Assuming run_accumulated_history length is seconds
            "boss_drops": self.NR_BOSS_DROPS,
            "snowball_d1": self.NR_SNOWBALL_D1,
            "snowball_d2": self.NR_SNOWBALL_D2,
            "nr_config": { # Signal that new config is active
                "goal": self.NR_FARMING_GOAL,
                "duration": self.NR_TOTAL_TIME
            }
        }
        
        self.overlay.update_run_stats(stats)

    def get_ideal_runes_at_time(self, t_seconds: float):
        # Piecewise Logic (Phase 4: 14m cycles)
        if t_seconds < self.NR_DAY_DURATION:
            # Day 1: 0 -> 14m
            ratio = t_seconds / self.NR_TOTAL_TIME
            val = self.NR_FARMING_GOAL * (ratio ** self.NR_SNOWBALL_D1)
            return val
        elif t_seconds < self.NR_TOTAL_TIME:
            # Day 2: 14m -> 28m
            # Calculate Day 1 end point (Farming only)
            val_d1_end = self.NR_FARMING_GOAL * ((self.NR_DAY_DURATION / self.NR_TOTAL_TIME) ** self.NR_SNOWBALL_D1)
            start_d2 = val_d1_end + self.NR_BOSS_DROPS
            
            # Growth needed in Day 2 to reach Target (437k)
            rem_farming = self.NR_IDEAL_TARGET - start_d2
            
            # Progress in Day 2
            t_d2 = t_seconds - self.NR_DAY_DURATION
            ratio_d2 = t_d2 / self.NR_DAY_DURATION
            val = start_d2 + rem_farming * (ratio_d2 ** self.NR_SNOWBALL_D2)
            return val
        else:
            # Post Day 2: Flat + Boss 2 Drop
            return self.NR_IDEAL_TARGET + self.NR_BOSS_DROPS

    def calculate_efficiency_grade(self) -> str:
        if self.session.start_time is None: 
            self.last_calculated_delta = 0
            return "C"

        # Calculate Elapsed Farming Time
        # Only count time if timer is running (paused during bosses)
        # Simplify: Use Wall Time - Start Time for now, assuming Pauses are handled 
        # via 'elapsed' passed from update_timer_task? 
        # Actually StateService doesn't track "paused duration" well globally yet.
        # But we pause graph updates during boss. Can we use len(run_history) as seconds?
        # Yes, run_history is approx seconds of active farming.
        farming_time = len(self.session.run_accumulated_history)
        if farming_time < 30: return "A" # Start buffer
        
        current_total = self.last_valid_total_runes
        ideal = self.get_ideal_runes_at_time(farming_time)
        
        delta = current_total - ideal
        self.last_calculated_delta = delta
        
        # Grading based on Delta Percentage relative to Ideal
        # Avoid division by zero
        if ideal < 1000: return "A" 
        
        pct_diff = delta / ideal
        
        if pct_diff >= 0.10: return "S"   # +10% 
        if pct_diff >= 0.0: return "A"    # Ahead
        if pct_diff >= -0.10: return "B"  # -0% to -10%
        if pct_diff >= -0.20: return "C"  # -10% to -20%
        if pct_diff >= -0.30: return "D"  # -20% to -30%
        if pct_diff >= -0.40: return "E"
        return "F"                        # < -40%

    def calculate_time_to_level(self, missing: int) -> str:
        if missing <= 0: return "Ready"
        if self.smoothed_rps < 5: return "---" # Too slow to predict
        
        seconds = missing / self.smoothed_rps
        if seconds > 3600: return "> 1h"
        
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"

    def get_transition_penalty(self, target_day: str) -> int:
        """Sequence Guard: Apply penalties to unlikely state transitions (Delegated to GameRules)."""
        elapsed_in_run = len(self.session.run_accumulated_history)

        current_runes = getattr(self.session, 'current_runes', 0)
        debug_mode = self.config.get("debug_mode", False)

        return GameRules.get_transition_penalty(
            target_day=target_day,
            current_phase_index=self.session.phase_index,
            current_runes=current_runes,
            elapsed_in_run=elapsed_in_run,
            debug_mode=debug_mode
        )

    def handle_trigger(self, trigger_text: str, is_manual: bool = False, force: bool = False) -> bool:
        print(f"DEBUG_TRACE: handle_trigger({trigger_text}, is_manual={is_manual}, force={force})")
        if not force and not self.is_transition_allowed(trigger_text, is_manual=is_manual):
            print(f"DEBUG_TRACE: Transition BLOCKED by Rules (Force={force})")
            return False

        if self.current_session_id == -1:
             self.current_session_id = self.db.create_session()
             logger.info(f"StateService: Started Session {self.current_session_id} (Trigger: {trigger_text})")
             
        result = True
        if trigger_text == "DAY 1": result = self.trigger_day_1()
        elif trigger_text == "DAY 2": self.trigger_day_2()
        elif trigger_text == "DAY 3": self.trigger_day_3()
        
        if result and self.current_session_id != -1:
             self.db.log_event(self.current_session_id, "TRIGGER", trigger_text)

        # Auto-Label Training Data
        if result and self.config.get("save_raw_samples", True):
             self.vision.save_labeled_sample(trigger_text)
        
        return result
        
    def is_transition_allowed(self, target_day: str, is_manual: bool = False) -> bool:
        """
        STRICT STATE MACHINE (Delegated to GameRules).
        """
        elapsed_in_run = len(self.session.run_accumulated_history)

        current_runes = getattr(self.session, 'current_runes', 0)
        last_black_screen = getattr(self, 'last_black_screen_end', 0)
        debug_mode = self.config.get("debug_mode", False)

        return GameRules.is_transition_allowed(
            target_day=target_day,
            current_phase_index=self.session.phase_index,
            current_run_level=self.session.current_run_level,
            current_runes=current_runes,
            elapsed_in_run=elapsed_in_run,
            last_black_screen_time=last_black_screen,
            is_manual=is_manual,
            debug_mode=debug_mode,
            is_startup=getattr(self, 'waiting_for_day1', False)
        )

    def set_phase_by_name_start(self, name_start_str):
        # Logique simplifiée pour mapper Day 1 -> Phase 0, Day 2 -> Phase 5 etc.
        if name_start_str == "Day 1":
             if self.is_transition_allowed("DAY 1"):
                 self.trigger_day_1()
        elif name_start_str == "Day 2":
             if self.is_transition_allowed("DAY 2"):
                self.trigger_day_2()
        elif name_start_str == "Day 3":
             if self.is_transition_allowed("DAY 3"):
                self.trigger_day_3()

    def Trigger(self, index):
        logger.info(f"🔵 DEBUG: Trigger({index}) called. Current phase_index={getattr(self.session, 'phase_index', 'NONE')}")
        if index < -1 or index >= len(self.phases): 
            logger.info(f"🔵 DEBUG: Trigger({index}) rejected - out of bounds")
            return
        
        # --- GRAPH MARKER LOGIC (End Shrink Detection) ---
        # We record the transition WHEN LEAVING a Shrinking Phase
        # Check the CURRENT phase (before updating to the new one)
        current_idx = self.session.phase_index if hasattr(self.session, 'phase_index') else -1
        logger.info(f"🔵 DEBUG: current_idx={current_idx}, checking shrink_map")
        
        shrink_map = {
            1: "End Shrink 1.1", # Leaving Day 1 - Shrinking
            3: "End Shrink 1.2", # Leaving Day 1 - Shrinking 2
            6: "End Shrink 2.1", # Leaving Day 2 - Shrinking
            8: "End Shrink 2.2"  # Leaving Day 2 - Shrinking 2
        }
        
        # If we're currently IN a shrinking phase and about to leave it
        if current_idx in shrink_map:
             logger.info(f"🔵 DEBUG: MATCH! current_idx={current_idx} is in shrink_map, creating event...")
             t_name = shrink_map[current_idx]
             # Log as standard Graph Event (Type: SHRINK)
             # This uses the exact same pipeline as Deaths/Recoveries
             self.session.graph_events.append({
                 "t": len(self.session.run_accumulated_history),
                 "type": "SHRINK",
                 "details": t_name
             })
             # Always log SHRINK events for debugging
             logger.info(f"🔵 SHRINK EVENT CREATED: {t_name} at t={time.time():.1f} (Total events: {len(self.session.graph_events)})")
             if self.config.get("debug_mode"):
                 logger.info(f"Graph Marker Added: {t_name}")
        else:
             logger.info(f"🔵 DEBUG: NO MATCH. current_idx={current_idx} not in shrink_map {list(shrink_map.keys())}")

        self.session.timer_frozen = False
        self.session.phase_index = index
        self.session.start_time = time.time()
        self.last_phase_change_time = time.time() # Added to track delay
        self._update_day_ocr_state()
        self._check_rps_pause()
        
        # --- LOG CONTEXT UPDATE ---
        phase_name = self.phases[index]["name"] if index >= 0 else "Waiting"
        logger.update_context("phase", phase_name)
        logger.info(f"Phase Triggered: {phase_name} (Index: {index})")
        
        # Event Bus
        bus.publish(PhaseChangeEvent(index, phase_name, manual=False))
        
        # Start of Run clears Menu State
        if index != -1:
            self.is_in_menu = False
        
        # Force UI Update to show new phase name immediately
        self.schedule(0, lambda: self.update_runes_display(self.session.current_run_level))

    def _check_rps_pause(self):
        if self.session.phase_index < 0: return
        phase_name = self.phases[self.session.phase_index]["name"]
        # Boss 1, Boss 2, Day 3 - Final Boss
        if "Boss" in phase_name:
            self.rps_paused = True
            if self.config.get("debug_mode"):
                logger.info(f"RPS Paused (Phase: {phase_name})")
        else:
            self.rps_paused = False
            if self.config.get("debug_mode"):
                logger.info(f"RPS Resumed (Phase: {phase_name})")
        self.update_overlay_now()
        
        if self.current_session_id != -1:
             self.db.log_event(self.current_session_id, "PHASE_CHANGE", phase_name)

    def trigger_day_1(self) -> bool:
        # NASA-grade Early Game Detection: JOUR I marks end of initialization
        if self.waiting_for_day1:
            logger.info("✅ JOUR I detected - Initialization complete. Unfreezing stats.")
            self.waiting_for_day1 = False
            self.session.stats_frozen = False
        
        # "JOUR I" detection implies a reset. We aggressively clear all state.
        self.session.timer_frozen = True  # Just freeze, don't announce
        self.start_new_session("Storm")
        
        # --- AGGRESSIVE RESET (Anti-Death/Anti-Leak) ---
        self.session.current_run_level = 1
        self.session.current_runes = 0
        self.last_runes_reading = 0
        self.last_valid_total_runes = 0
        self.last_display_level = 1
        self.last_display_runes = 0
        
        # Reset Timer & Global State
        self.session.start_time = time.time()
        self.session.boss3_start_time = None
        self.session.day1_detection_time = time.time()
        
        # Reset RPS & Smoothing
        self.rune_gains_history = deque([0] * 40, maxlen=40)
        self.smoothed_rps = 0.0
        self.pending_rps_gain = 0
        self.rps_paused = False
        
        # Reset Graphics & Markers
        self.session.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.session.graph_events = []
        self.graph_log_data = []
        self.graph_start_time = 0 
        self.session.day_transition_markers = []
        self.last_calculated_delta = 0
        
        # Reset Statistics
        self.permanent_loss = 0
        self.session.death_count = 0
        self.session.recovery_count = 0
        self.total_death_loss = 0
        self.lost_runes_pending = 0
        self.spent_at_merchants = 0 
        self.recent_spending_history = []
        self.death_history = []
        
        # Reset Audio & Announcements
        self.last_beep_second = -1
        self.last_announced_phase = -1
        self.last_announcement_second = -1
        
        # --- RESET TRANSIENT/PENDING STATES (Anti-Leak) ---
        self.pending_spending_event = None
        self._level_up_pending_sync = None
        self._ignore_next_rune_gain = False
        self._ignore_next_rune_drop = False
        self.gain_verification_candidate = -1
        self.low_value_persistence = 0
        self.last_silent_level_drop = None
        self.runes_uncertain = False
        
        if not self.session.day1_detection_time: self.session.day1_detection_time = time.time()
        self.victory_detected = False # Reset for new run
        self.victory_check_active = False
        self.last_stat_change_time = time.time()
        self.recent_warnings.clear()
        
        # Reset level internals
        self.pending_level = 1
        self.level_consensus_count = 0 
        
        self.Trigger(0)
        
        # Force UI Refresh
        self.schedule(0, lambda: self.update_runes_display(1))
        
        # Record marker for graph
        marker_idx = len(self.session.run_accumulated_history)
        self.session.day_transition_markers.append((marker_idx, "DAY 1"))
        return True

    def trigger_day_2(self):
        if self.session.phase_index != 5:
            self.Trigger(5)
            # Record marker for graph
            marker_idx = len(self.session.run_accumulated_history)
            self.session.day_transition_markers.append((marker_idx, "DAY 2"))

    def trigger_day_3(self):
        if self.session.phase_index != 10:
            self.Trigger(10)
            # Record marker for graph
            marker_idx = len(self.session.run_accumulated_history)
            self.session.day_transition_markers.append((marker_idx, "DAY 3"))
            self.session.boss3_start_time = time.time()

    def trigger_final_boss(self):
        if self.session.phase_index != 11:
            self.Trigger(11)
            # The instruction moved boss3_start_time to trigger_day_3, so this line is removed.
            # self.session.boss3_start_time = time.time() 

    def skip_to_boss(self):
        """Skip to the boss of the current day for testing."""
        logger.info(f"Manual skip requested. Current phase: {self.session.phase_index}")
        if self.session.phase_index < 4:
            msg = "SKIP: Skipping to Boss 1"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.Trigger(4)
        elif self.session.phase_index < 9:
            msg = "SKIP: Skipping to Boss 2"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.Trigger(9)
        elif self.session.phase_index == 9:
            msg = "SKIP: Boss 2 -> Day 3 Preparation"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.trigger_day_3()
        elif self.session.phase_index == 10:
            msg = "SKIP: Day 3 Preparation -> Final Boss"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.trigger_final_boss()
        else:
            msg = "SKIP: Already at Final Boss"
            logger.info(msg)
            self.vision.log_debug(msg)

    def get_current_state(self) -> str:
        if self.session.phase_index == -1: return "Waiting"
        return self.phases[self.session.phase_index]["name"]

    # --- Timer Loop ---

    def update_overlay_now(self):
        # Force update logic for immediate feedback
        pass # loop will catch up in 100ms

    # --- Victory ---
    def check_victory_loop(self):
        if not self.running: return
        if self.session.phase_index != 11:
            self.victory_check_active = False
            return 
            
        # Scan
        # Wait, VisionService returns result via Observer. 
        # But we need specific victory scan method (region override).
        # VisionService has scan_victory_region().
        
        text, score = self.vision.scan_victory_region()
        if text and score >= 60:
             logger.info(f"VICTORY: {text} ({score})")
             self.stop_timer_victory()
             
             if self.current_session_id != -1:
                 self.db.end_session(self.current_session_id, "VICTORY")
                 self.current_session_id = -1
                 
             if self.config.get("save_raw_samples", True):
                 self.vision.save_labeled_sample("VICTORY")

             self.victory_check_active = False
             self.victory_detected = True # Lock victory state until next run
             self._update_day_ocr_state() 
        else:
             self.schedule(int(self.victory_check_interval * 1000), self.check_victory_loop)

    def stop_timer_victory(self):
        self.session.timer_frozen = True
        
        total_time = 0
        boss3_time = 0
        now = time.time()
        
        if self.session.day1_detection_time: total_time = now - self.session.day1_detection_time
        elif self.session.start_time: total_time = now - self.session.start_time # Approximation
        
        if self.session.boss3_start_time: boss3_time = now - self.session.boss3_start_time
        
        fmt = lambda s: f"{int(s//60):02}:{int(s%60):02}"
        final_text = f"{fmt(total_time)}"
        
        self.overlay.update_timer(final_text)
        self.audio.announce("Victoire !")

    # --- Manual Feedback ---
    def handle_manual_feedback(self, correct_target: str, force: bool = False):
        print(f"DEBUG_TRACE: handle_manual_feedback({correct_target}, force={force})")
        logger.info(f"Manual Feedback requested: {correct_target} (Force={force})")
        
        # Guard: Prevent accidental Day 2 trigger if too early in Day 1 run
        # BYPASSED if force=True (Expert Shortcut)
        if not force and correct_target == "DAY 2":
            elapsed_in_run = len(self.session.run_accumulated_history)
            # If less than 8 minutes (480s) have passed, we ignore the hotkey unless in Boss 1
            if self.session.phase_index < 4 and elapsed_in_run < 480:
                logger.warning(f"Manual DAY 2 ignored: Run too short ({elapsed_in_run}s < 480s) and not in Boss phase.")
                try: winsound.Beep(300, 200) # Low error beep
                except: pass
                return

        if not self.triggered_recently:
            logger.info(f"Manual Feedback Applied: {correct_target}")
            self.handle_trigger(correct_target, is_manual=True, force=force)  # Pass force=True
            self.triggered_recently = True
            # Reduce timeout to 1s to allow rapid correction if needed
            self.schedule(1000, lambda: setattr(self, 'triggered_recently', False))
            
            # Save a sample to help debug what was happening
            if self.config.get("save_raw_samples", True) or self.config.get("debug_mode", False):
                self.vision.save_labeled_sample(f"MANUAL_{correct_target}")
        else:
             logger.warning(f"Manual Feedback {correct_target} ignored: Triggered too recently.")

    def handle_false_positive(self):
        logger.info("Manual Feedback: False Positive")
        self.session.timer_frozen = False
        self.session.phase_index = -1
        self._update_day_ocr_state()
        self.triggered_recently = False # Allow immediate re-trigger if needed
        
        # If it was a false positive start, maybe we should delete the session?
        # For now, let's just mark it as ABANDONED/INVALID if it was just started?
        # Simpler: just reset ID
        if self.current_session_id != -1:
             self.db.end_session(self.current_session_id, "ABANDONED")
             self.current_session_id = -1

        self.overlay.update_timer("Waiting...")
        if self.current_matched_pattern:
             self.pattern_manager.punish(self.current_matched_pattern)
             try: winsound.Beep(500, 500)
             except: pass

    def restart_application(self):
        logger.info("RESTART REQUESTED")
        try:
            # Determine path to restart.vbs in project root
            # self is in src.services.state_service -> .../src/services/state_service.py
            # root is .../
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            vbs_path = os.path.join(project_root, "scripts", "restart.vbs")
            
            if os.path.exists(vbs_path):
                logger.info(f"Launching {vbs_path}...")
                subprocess.Popen(["wscript", vbs_path], shell=False, cwd=project_root)
                logger.info("Exiting current process...")
                try:
                    self.vision.stop_capture()
                except: pass
                # Force exit immediately to let the vbs file take over
                os._exit(0) 
            else:
                print(f"Error: {vbs_path} not found.")
                try: winsound.Beep(200, 500)
                except: pass
        except Exception as e:
            logger.error(f"Restart failed: {e}")

    def get_debug_state(self) -> Dict[str, Any]:
        """Returns internal state for the Debug Inspector UI."""
        
        # Get Vision State
        vision_state = {}
        if hasattr(self.vision, "get_debug_state"):
            vision_state = self.vision.get_debug_state()
            
        p_name = "Unknown"
        if 0 <= self.session.phase_index < len(self.phases):
            p_name = self.phases[self.session.phase_index]["name"] if self.session.phase_index >= 0 else "Waiting"
        # Shorten for UI
        if "Shrinking" in p_name: p_name = p_name.replace("Shrinking", "Shrink")
        if "Preparation" in p_name: p_name = p_name.replace("Preparation", "Prep")
        
        if self.config.get("debug_mode"):
             logger.debug(f"UI UPDATE: Phase Index {self.session.phase_index} -> Name '{p_name}'")
        
        return {
            "phase": p_name,
            "phase_index": self.session.phase_index,
            "session_count": self.session_count,
            "runes": self.session.current_runes,
            "level": self.session.current_run_level,
            "spent_merchants": self.spent_at_merchants,
            "death_count": self.session.death_count,
            "pending_loss": self.lost_runes_pending,
            "permanent_loss": self.permanent_loss,
            "black_screen": {
                "active": self.in_black_screen,
                "duration": time.time() - self.black_screen_start if self.in_black_screen else 0
            },
            "buffer_size": len(self.trigger_buffer),
            "level_consensus": self.level_consensus_count,
            "recent_warnings": list(self.recent_warnings),
            "vision": vision_state
        }

    def add_debug_warning(self, msg: str):
        """Adds a message to the debug inspector warning log."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.recent_warnings.append(f"[{ts}] {msg}")

    def handle_retroactive_death(self, old_level, level, death_runes):
        """Handles a death that was detected late (Runes dropped to 0 after Level dropped)."""
        # Reconstruct the Death Event
        
        # 1. Cancel the Pending Spending (since we identified it as death)
        self.pending_spending_event = None
        
        # 2. Calculate Loss
        lost_level_cost = RuneData._LEVEL_COSTS.get(old_level, 0)
        # death_runes passed in is 'self.last_runes_reading' aka the amount BEFORE the drop to 0.
        total_loss = death_runes + lost_level_cost
        
        self.session.death_count += 1
        self.total_death_loss += total_loss
        self.lost_runes_pending = total_loss
        
        death_event = {
                "death_num": self.session.death_count,
                "old_level": old_level,
                "new_level": level,
                "runes_at_death": death_runes,
                "level_cost_lost": lost_level_cost,
                "total_loss": total_loss,
                "retroactive": True
            }
        self.death_history.append(death_event)
        self.log_session_event("DEATH", death_event)
        self.session.graph_events.append({"t": len(self.session.run_accumulated_history), "type": "DEATH"})
        
        # 3. Graph Repair (Similar to standard death)
        # We need to subtract the loss from 'last_valid_total_runes' 
        # But wait, 'last_valid_total_runes' might have already updated? 
        # No, 'on_runes_detected' calls this BEFORE committing the drop to 'current_runes' state usually?
        # Actually it's inside the "SPENDING" block.
        # So 'last_valid_total_runes' considers the runes as "Available". 
        
        # We must ignore the next rune drop? No, we just processed it.
        self._ignore_next_rune_drop = True 

    # --- EVENT BUS HANDLERS ---
    def _handle_level_event(self, event: LevelDetectedEvent):
        if self.logic_paused: return
        self.on_level_detected(event.level, event.confidence)

    def _handle_runes_event(self, event: RunesDetectedEvent):
        if self.logic_paused: return
        self.on_runes_detected(event.runes, event.confidence)

    def _handle_menu_event(self, event: MenuDetectedEvent):
        if self.logic_paused: return
        self.on_menu_screen_detected(event.is_open)

    def on_menu_screen_detected(self, is_visible: bool):
        """
        Handles transition triggered by Menu Screen detection.
        Logic:
        - If Visible: State matches "MENU".
        - If Disappears (Exit Menu): Reset Session to "GAME INIT" (00:00).
          This prepares for the new run.
        """
        if is_visible:
            # User is in Menu
            if self.current_phase != "MENU":
                logger.info("Menu Detected -> Pausing Run Logic")
                self.current_phase = "MENU"
                self.overlay.update_phase("MENU", "00:00")
                
        else:
            # Menu just disappeared -> Starting Game or Loading?
            # User request: "dès qu'elle n'est plus là on remet le chrono à 00:00 et on indique ‘game init’"
            if self.current_phase == "MENU":
                logger.info("Menu Exited -> Resetting to GAME INIT")
                self.reset_to_initial_state()
                # Initialize resets everything, which is what we want for "Game Init"
                self.current_phase = "GAME INIT"
                self.overlay.update_phase("GAME INIT", "00:00")
                # Ensure session count doesn't increment prematurely, 
                # but initialize() resets it? No, initialize is hard reset.
                # Maybe just soft reset?
                self.start_new_session("GAME INIT")
                self.session_start_time = 0 # Hold at 0 until Day 1 triggers
                self.session_active = False # Wait for Day 1 msg

    def on_f9_pressed(self):
        """Handle F9 hotkey to open settings window."""
        logger.info(f"F9 Pressed. Callback registered: {self.tuner_callback is not None}")
        # Audio confirmation (Standard F9 Beep)
        try:
            winsound.Beep(880, 150) # High-pitched beep
        except:
            pass
            
        if self.tuner_callback:
            self.tuner_callback()
        else:
            logger.warning("F9 pressed but tuner_callback is not set.")


