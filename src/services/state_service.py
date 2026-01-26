import time
import datetime
import winsound
import subprocess
import threading
import os
import sys
import json
from collections import deque
import time
import math
from typing import Dict, Any, List, Optional
from src.services.base_service import IStateService, IConfigService, IVisionService, IOverlayService, IDatabaseService, IAudioService, ITrayService
from src.pattern_manager import PatternManager
try:
    import keyboard
except ImportError:
    keyboard = None
import psutil
from src.services.rune_data import RuneData
from src.services.game_logic import NightreignLogic
from src.logger import logger

class StateService(IStateService):
    def __init__(self, config: IConfigService, vision: IVisionService, overlay: IOverlayService, db: IDatabaseService, audio: IAudioService, tray: ITrayService):
        self.config = config
        self.vision = vision
        self.overlay = overlay
        self.db = db
        self.audio = audio
        self.tray = tray
        
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
        self.current_phase_index = -1
        self.start_time: Optional[float] = None
        self.boss3_start_time: Optional[float] = None
        self.day1_detection_time: Optional[float] = None
        self.timer_frozen = False
        
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
        
        # Menu Detection State
        self.is_in_menu = False
        self._was_in_menu = False  # Track previous state for exit detection

    def initialize(self) -> bool:
        logger.info("StateService: Initializing...")
        self.running = True
        
        # Retroactive Death State
        self.last_silent_level_drop = None
        self.low_value_persistence = 0
        
        # Subscribe to config changes
        self.config.add_observer(self.on_config_changed)
        
        # Start Vision Capture Loop
        self.vision.start_capture()
        self.vision.add_observer(self.on_ocr_result)
        self.vision.add_level_observer(self.on_level_detected)
        self.vision.add_runes_observer(self.on_runes_detected)
        self.vision.set_menu_callback(self.on_menu_screen_detected)

        self.current_run_level = 1
        self.pending_level = None
        self.level_consensus_count = 0
        
        # Rune History & RPS (40s Window)
        self.current_runes = 0
        self.last_runes_reading = 0
        self.rune_gains_history = deque([0] * 40, maxlen=40) # 40 seconds
        self.smoothed_rps = 0.0
        self.pending_rps_gain = 0
        self.last_rps_update = time.time()
        self.rps_paused = False
        
        # Advanced Rune & Death Stats
        self.spent_at_merchants = 0
        self.death_count = 0
        self.recovery_count = 0 # New: Track recoveries
        self.death_history = [] 
        self.total_death_loss = 0
        self.lost_runes_pending = 0 
        self.graph_events = [] 
        self.permanent_loss = 0 
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
        self.NR_TOTAL_REQ = 550000 # Farming + Bosses
        self.NR_BOSS_DROPS = 50000 + 100000 
        self.NR_FARMING_GOAL = 400000 # Adjusted for Lvl 14 at 40m
        self.NR_DAY_DURATION = 1200 # 20 mins per day
        self.NR_TOTAL_TIME = 2400 # 40 mins farming time
        self.NR_SNOWBALL = 1.7
        
        # Transaction History (for correction)
        self.recent_spending_history = [] # List of (timestamp, amount)

        # Graph Logging
        self.graph_log_file = ""
        self.graph_log_data = []
        self.last_graph_save = 0
        self.graph_start_time = 0 # Timestamp when graph history started

        # --- FULL-RUN HISTORY (User Request) ---
        self.run_accumulated_history = [] # Corrected/Cleaned History
        self.run_accumulated_raw = []     # Raw/Dirty History (For diff visualization)
        self.day_transition_markers = [] # List of (index, day_name)
        
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
                keyboard.add_hotkey('ctrl+shift+&', lambda: self.handle_manual_feedback("DAY 1"))
                keyboard.add_hotkey('ctrl+shift+é', lambda: self.handle_manual_feedback("DAY 2"))
                keyboard.add_hotkey('ctrl+shift+"', lambda: self.handle_manual_feedback("DAY 3"))
                keyboard.add_hotkey('ctrl+shift+(', self.handle_false_positive)
                keyboard.add_hotkey('ctrl+shift+b', self.skip_to_boss)
                keyboard.add_hotkey('ctrl+shift+r', self.restart_application)
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
        self.current_phase = phase_name
        self.session_log = []
        self.log_dir = os.path.join(os.getcwd(), "data", "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # New Naming Convention: Run_[Count]_[Phase]_[YYYYMMDD]_[HHMMSS].json
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_filename = f"Run_{self.session_count}_{phase_name}_{ts}.json"
        
        # Dedicated Graph Log
        phase_clean = phase_name.replace(" ", "_").replace("-", "")
        self.graph_log_filename = f"Run_{self.session_count}_{phase_clean}_{ts}_GRAPH.json"
        self.graph_log_file = os.path.join(self.log_dir, self.graph_log_filename)
        self.graph_log_data = []
        self.last_graph_save = time.time()
        
        self.log_session_event("SESSION_STARTED", {
            "run_count": self.session_count,
            "phase": phase_name,
            "level": getattr(self, 'current_run_level', 1)
        })

    def log_session_event(self, event_type: str, data: dict = None):
        event = {
            "timestamp": time.time(),
            "time_str": datetime.datetime.now().strftime("%H:%M:%S"),
            "event": event_type,
            "data": data or {}
        }
        self.session_log.append(event)
        if self.config.get("debug_mode"):
            logger.info(f"[SESSION LOG] {event_type}: {data}")
        # Save on every event for robustness
        self.save_session_log()

    def save_session_log(self):
        try:
            filepath = os.path.join(self.log_dir, self.session_filename)
            # ... full_data update ... (omitted for brevity, keep existing logic if editing entire function)
            # Actually we just want to save the session file, keeping existing logic
            
            full_data = {
                "session_summary": {
                    "session_id": self.session_count,
                    "phase": self.current_phase,
                    "total_death_loss": self.total_death_loss,
                    "death_count": self.death_count,
                    "recovery_count": self.recovery_count,
                    "spent_at_merchants": self.spent_at_merchants,
                    "current_level": self.current_run_level,
                    "death_history": self.death_history
                },
                "events": self.session_log
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save session log: {e}")

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
            self.update_timer_task()
            
            time.sleep(0.2)

    def check_system_resources(self):
        if psutil is None: return
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.log_session_event("SYSTEM_RESOURCE_STATS", {"cpu": cpu, "ram": ram})
        except: pass

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
        if self.timer_frozen or self.is_hibernating:
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
                if self.current_runes >= old_runes_val * 0.98:
                    self.pending_spending_event = None
                    if self.config.get("debug_mode"):
                        logger.info(f"Ghost Spending Cancelled: Runes returned to {self.current_runes} (from drop to {old_runes_val-spent_val})")
                    
                    # --- RETROACTIVE GRAPH REPAIR (User: "supprimer et redessiner") ---
                    # The graph recorded a dip during the pending state. Fix it by flattening the last ~5-10s.
                    # We overwrite the "Corrected" history with the current (restored) value.
                    # The "Raw" history remains untouched (showing the dip).
                    try:
                        restored_val = self.last_valid_total_runes # Should be high again
                        history_len = len(self.run_accumulated_history)
                        # Go back 60 seconds (Deep Repair for user request)
                        start_idx = max(0, history_len - 60)
                        for i in range(start_idx, history_len):
                            # Only pull UP, never pull down (in case we had real gains mixed in?)
                            # Actually, just flattening is safer for a ghost cancel.
                            if self.run_accumulated_history[i] < restored_val:
                                self.run_accumulated_history[i] = restored_val
                    except Exception as e:
                        logger.error(f"Graph Repair Error: {e}")

                elif now - event_time >= 10.0:
                    # Still no level up captured? Must be a real purchase.
                    # STRICT Validation: Must be a multiple of 100 (User Request)
                    if spent_val % 100 == 0:
                        self.spent_at_merchants += spent_val
                        self.log_session_event("SPENDING", {"spent": spent_val, "total_spent": self.spent_at_merchants, "current": self.current_runes})
                        self.recent_spending_history.append((time.time(), spent_val))
                    else:
                        # REJECT LOGIC
                        if self.config.get("debug_mode"):
                            logger.info(f"Spending Rejected (Non-standard amount): {spent_val} (Old: {old_runes_val} -> New: {self.current_runes}). Assuming OCR Error.")
                        
                        # We must revert the "current_runes" to "old_runes_val" internally?
                        # No, if we reject the spending, we just assume the drop was an error.
                        # However, 'self.current_runes' is constantly updated by OCR.
                        # IF the OCR stabilizes on this new weird value, we might have an issue.
                        # But typically, if it's 6499 instead of 6500, it might flicker back and forth.
                        # For now, by NOT adding it to 'spent_at_merchants', we effectively treat it as missing wealth (Death/Loss) or just ignore it in the graph math?
                        
                        # Wait, if we ignore it, 'current_runes' is still low.
                        # So 'Effective Wealth' (Current + Spent) will DROP. 
                        # This looks like a DIP in the graph.
                        # If we want to "refouler" (reject), we imply we don't believe the NEW Reading.
                        pass
                        
                    self.pending_spending_event = None

            # --- Process _ignore_next_rune_gain Grace Period ---
            if self._ignore_next_rune_gain_grace_period:
                event_time = self._ignore_next_rune_gain_grace_period
                if now - event_time >= 5.0: # 5-second grace period
                    self._ignore_next_rune_gain = False
                    self._ignore_next_rune_gain_grace_period = None
            
            if self.start_time is not None and self.current_phase_index >= 0:
                phase = self.phases[self.current_phase_index]
                elapsed = time.time() - self.start_time
                
                if phase["duration"] > 0:
                    remaining = max(0, phase["duration"] - elapsed)
                    remaining_int = int(remaining)
                    
                    # Phase Auto Advance
                    if remaining == 0:
                        self.current_phase_index += 1
                        self.start_time = time.time()
                        self._check_rps_pause()
                        return

                    # --- RPS & GRAPH UPDATE (1Hz) ---
                    if time.time() - self.last_rps_update >= 1.0:
                        self.last_rps_update = time.time()
                        
                        if not self.rps_paused:
                            self.rune_gains_history.append(self.pending_rps_gain)
                            self.pending_rps_gain = 0
                            
                            # --- FULL-RUN GRAPH UPDATE ---
                            spent_on_levels = RuneData.get_total_runes_for_level(self.current_run_level) or 0
                            
                            # STRATEGY: Effective Wealth (Holes for Merchant Spending/Permanent Loss)
                            # We only count what is AVAILABLE for leveling.
                            current_calc = spent_on_levels + self.current_runes + self.lost_runes_pending
                            
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
                                     if self.current_runes >= level_cost * 0.2:
                                          current_calc -= level_cost
                                else:
                                     self._level_up_pending_sync = None

                            # --- GLITCH CLAMP ---
                            # If total jumps unreasonably high (e.g. > last + level_cost/2) without a boss event,
                            # clamp it to prevent graph scale ruin.
                            delta = current_calc - self.last_valid_total_runes
                            if delta > 0 and self.current_phase_index >= 0:
                                # If delta is huge (> 50k or > 50% level cost) and NO Boss kill recently...
                                # We could clamp upward spikes, but we MUST allow downward regressions (holes).
                                pass

                                # STRATEGY: GRAPH RATCHET (Via NightreignLogic)
                                # Enforce Monotonicity using central rules
                                
                                # Check if we have valid reasons to drop
                                is_valid_drop_reason = (self.pending_spending_event is not None)
                                # Note: Death resets are handled by graph reset or event, but here we just check if
                                # the current calc is allowed to be lower.
                                
                                # Validate using Logic Class
                                total_accumulated = NightreignLogic.validate_graph_monotonicity(
                                    current_calc, 
                                    self.last_valid_total_runes,
                                    is_death=False, # Death handled separately
                                    is_spending=is_valid_drop_reason
                                )
                                
                                if total_accumulated != current_calc and not is_valid_drop_reason:
                                     # Logic clamped it. It was a glitch.
                                     # Keep last valid
                                     self.last_valid_total_runes = total_accumulated
                                else:
                                     self.last_valid_total_runes = total_accumulated

                                # FORCE 1 for first 15s (User request: "tricher sur le graph")
                                
                                # FORCE 1 for first 15s (User request: "tricher sur le graph")
                                # We use the length of history as the time index (approx 1s per tick)
                                if len(self.run_accumulated_history) < 15:
                                     total_accumulated = 1
                                
                                # FORCE FREEZE at Boss 3 (Final Boss) - Phase Index 11+
                                # User request: "le graff s'arrete au debut du boss 3"
                                elif self.current_phase_index >= 11:
                                     total_accumulated = self.last_valid_total_runes
                                
                                else:
                                     total_accumulated = self.last_valid_total_runes
                            
                            # Raw calculation: Current Runes + Pending + Spent (Current snapshot, no retroactive fixes)
                            # We want this to be the "Naive" view.
                            # If we use self.spent_at_merchants, it is 'corrected' by reverts.
                            # But 'raw' means "what we saw". Ideally we'd store a separate 'raw_spent'.
                            # For simplicity, we'll store the 'current_calc' BEFORE it was potentially clamped/adjusted?
                            # Actually `current_calc` line 390 is good.
                            
                            self.run_accumulated_history.append(total_accumulated)
                            
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
                                    "curr": self.current_runes,
                                    "pend": self.lost_runes_pending,
                                    "perm": self.permanent_loss,
                                    "uncertain": self.runes_uncertain,
                                    "trust_idx": getattr(self, "last_trust_score", 100.0) # LOG TRUST IDX
                                }
                            }
                            self.graph_log_data.append(graph_entry)
                            
                            if time.time() - self.last_graph_save >= 5.0:
                                self.save_graph_log()
                                self.last_graph_save = time.time()

                        self.smoothed_rps = sum(self.rune_gains_history) / 40.0
                    
                    self.update_runes_display(self.current_run_level)
                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    timer_str = f"{mins:02}:{secs:02}"
                    
                    # Audio Announcements
                    if remaining_int != self.last_announcement_second:
                        is_storm = "Storm" in phase["name"]
                        if is_storm:
                            if remaining_int == 120: self.audio.announce("Fermeture de la zone dans 2 minutes")
                            elif remaining_int == 60: self.audio.announce("Fermeture de la zone dans 1 minute")
                            elif remaining_int == 30: self.audio.announce("Dans 30 secondes")
                            elif remaining_int == 5: self.audio.announce("5 secondes")
                            elif remaining_int == 0: self.audio.announce("La zone se referme")
                        self.last_announcement_second = remaining_int
                    
                    # Check for Phase Start Announcement
                    if self.current_phase_index != self.last_announced_phase:
                        # Skip announcement for the very first phase (Day 1 - Storm) to avoid spam on startup
                        if "Storm" in phase["name"] and self.current_phase_index != 0:
                             d_min = phase["duration"] // 60
                             d_sec = phase["duration"] % 60
                             msg = "La zone se refermera dans "
                             if d_min > 0: msg += f"{d_min} minutes "
                             if d_sec > 0: msg += f"{d_sec} secondes"
                             self.audio.announce(msg)
                        self.last_announced_phase = self.current_phase_index
                else:
                    # Stopwatch
                    mins = int(elapsed // 60)
                    secs = int(elapsed % 60)
                    timer_str = f"{mins:02}:{secs:02}"
                    
                # prefix = ""
                # if self.fast_mode_active: prefix += "🔴 "
                
                next_idx = self.current_phase_index + 1
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
                     self.current_run_level = 1
                     self.current_runes = 0
                     self.last_display_level = 1
                     self.last_display_runes = 0
                     
                 # Update previous state for next iteration
                 self._was_in_menu = is_currently_in_menu
                     
                 # Force stats update to show "Waiting" in Phase Name area
                 self.update_runes_display(self.current_run_level)
                 
        except Exception as e:
            logger.error(f"CRASH IN UPDATE_TIMER_TASK: {e}")
            import traceback
            logger.error(traceback.format_exc())


    def shutdown(self) -> None:
        self.running = False

    def schedule(self, delay_ms: int, callback):
        self.overlay.schedule(delay_ms, callback)

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
        logger.info(f"StateService: Config updated. Auto-Hibernate: {self.config.get('auto_hibernate', True)}")
        # Removed aggressive check to prevent crash on startup / threading issues
        pass

    # --- OCR & State Logic ---
    def on_ocr_result(self, text, width, offset, word_data, brightness=0, score=0):
        self.schedule(0, lambda: self.process_ocr_trigger(text, width, offset, word_data, brightness, score))

    def is_stats_stable(self, seconds=1.0) -> bool:
        """Returns True if Level and Runes have been unchanged for the given duration."""
        return (time.time() - self.last_stat_change_time) > seconds

    def process_ocr_trigger(self, text, width, offset, word_data, brightness=0, score=0):
        # Update overlay score display immediately
        if score > 0:
            self.overlay.set_ocr_score(score)
        
        now = time.time()
        
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
            fuzzy_day_idx = NightreignLogic.map_fuzzy_day_trigger(normalized, self.current_phase_index)
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
            if self.config.get("debug_mode") and (target_day or score > 40):
                logger.debug(f"Eval '{normalized}' -> {target_day} (Score: {score})")
            
            if target_day and score >= 55:
                detected_trigger = target_day
                self.current_matched_pattern = normalized
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
             if self.current_phase_index not in [9, 10]: 
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
        elif day_counts["DAY 2"] >= 2 and day_scores["DAY 2"] > 180:
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
                 if self.current_phase_index in [9, 10]:
                     # Single Pulse Fade (0.3s - 3.0s)
                     if 0.3 <= duration <= 3.0:
                         if self.current_phase_index == 9:
                             self.vision.log_debug(f">>> FADE SUCCESS: Boss 2 -> Day 3 Prep (Dur: {duration:.2f}s)")
                             self.trigger_day_3()
                         elif self.current_phase_index == 10:
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
        if self.current_phase_index == 11 and not self.victory_check_active and not self.victory_detected:
             self.victory_check_active = True
             self.schedule(int(self.victory_check_interval * 1000), self.check_victory_loop)

    def on_menu_screen_detected(self, found, confidence):
        """
        Callback when Main Menu screen is detected.
        Shows menu indicator and optionally triggers reset.
        """
        if not found: 
            return
        
        logger.info(f"MAIN MENU DETECTED ({confidence:.2f})")
        
        # Always set menu indicator
        self.is_in_menu = True
        self.overlay.update_timer("🏠 Menu")
        
        # Only reset if we're in an active run (not already in Waiting state)
        if self.current_phase_index == -1: 
            logger.info("Already in Waiting state, skipping reset")
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
        self.current_phase_index = -1
        self.Trigger(-1) # -1 = Waiting/Ready
        
        # Clear Data
        self.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.graph_events = []
        self.death_count = 0
        self.recovery_count = 0
        self.current_runes = 0
        self.current_run_level = 1
        
        # Force UI Update
        self.overlay.set_stats(self._get_stats_dict())
        
        logger.info("Run reset complete")

    def on_level_detected(self, level: int, confidence: float = 100.0):
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
            
        # Check against dynamic requirement
        if self.level_consensus_count >= required_consensus:
            # Only update if changed (or first time after init)
            if level != self.current_run_level:
                old_level = self.current_run_level
                
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
                if level > old_level + 3:
                     # If we have seen this "impossible" value consistently for ~5 seconds (10 reads at 0.5s interval),
                     # we assume the system is desynced and force a correction.
                     if self.level_consensus_count < 10:
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
                     # Check for Force Correction (Desync)
                     if self.level_consensus_count < 10:
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
                # Delegated to NightreignLogic for consistent rules
                
                curr_runes = self.current_runes if hasattr(self, 'current_runes') else 0
                
                # Pass timestamp of last confirmed black screen
                last_black_screen = getattr(self, 'last_black_screen_end', 0)
                is_stat_death = NightreignLogic.is_death_confirmed(old_level, level, curr_runes, last_black_screen, time.time())
                
                if is_stat_death:
                     logger.warning(f"DEATH CONFIRMED (Stat Based): Level {old_level}->{level} (-1) & Runes {curr_runes} (<50).")
                elif level < old_level:
                     # If Logic says NO, but level dropped, it's an OCR error/correction.
                     logger.warning(f"IGNORED Level Drop {old_level}->{level}: Rejected by NightreignLogic (Runes: {curr_runes}).")
                     return

                if level < old_level and not is_stat_death:
                     # This is just a Correction (e.g. 8 -> 7) or non-death drop.
                     # Do NOT trigger death. Do NOT revert spending.
                     # Update level silently.
                     self.current_run_level = level
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
                        history_len = len(self.run_accumulated_history)
                        for i in range(max(0, history_len - 300), history_len):
                            self.run_accumulated_history[i] -= reverted_amount
                            if self.run_accumulated_history[i] < 0: self.run_accumulated_history[i] = 0
                    
                    self.recent_spending_history = valid_history

                    # --- DEATH CALCULATION ---
                    lost_level_cost = RuneData._LEVEL_COSTS.get(old_level, 0)
                    death_runes = self.last_runes_reading 
                    total_loss = death_runes + lost_level_cost + reverted_amount
                    
                    self.death_count += 1
                    self.total_death_loss += total_loss
                    self.lost_runes_pending = total_loss # New bloodstain created
                    
                    death_event = {
                            "death_num": self.death_count,
                            "old_level": old_level,
                            "new_level": level,
                            "runes_at_death": death_runes,
                            "level_cost_lost": lost_level_cost,
                            "total_loss": total_loss
                        }
                    self.death_history.append(death_event)
                    self.log_session_event("DEATH", death_event)
                    self._ignore_next_rune_drop = True 
                    self.graph_events.append({"t": time.time(), "type": "DEATH"})
                
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
                        history_len = len(self.run_accumulated_history)
                        for i in range(max(0, history_len - 300), history_len):
                            self.run_accumulated_history[i] -= reverted_amount
                            if self.run_accumulated_history[i] < 0: self.run_accumulated_history[i] = 0
                        
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
                
                if self.config.get("debug_mode"):
                    logger.info(f"Level Changed (Consensus): {old_level} -> {level}")
                
                self.current_run_level = level
                self.last_stat_change_time = time.time()
                self.schedule(0, lambda: self.update_runes_display(level))
                self.level_consensus_count = 0 

    def on_runes_detected(self, runes: int, confidence: float = 100.0):
        if not hasattr(self, 'current_runes'):
            self.current_runes = 0
            self.last_runes_reading = 0

        # --- DATA CLEANING (Anti-Noise) ---
        # 1. CHANGE GATE: PROCESS LOGIC ONLY IF VALUE DIFFERS FROM CURRENT CONFIRMED STATE
        # Hallucination Guard (Anti-Noise)
        # We use a persistence counter to allow real "0" readings (Death) to pass through eventually.
        if self.current_runes > 100 and runes < 10 and not self.in_black_screen:
            self.low_value_persistence = getattr(self, 'low_value_persistence', 0) + 1
            if self.low_value_persistence < 5: # Hold for 1s (approx 5 frames)
                if self.config.get("debug_mode"):
                    logger.debug(f"Ignored Hallucination (Value: {runes}). Persistence: {self.low_value_persistence}/5")
                return
            else:
                 if self.config.get("debug_mode"): logger.info(f"Hallucination Filter Bypassed: Sustained Low Value ({runes})")
        else:
            self.low_value_persistence = 0

        if runes != self.current_runes:
            
            # --- TRUST SYSTEM: LOW CONFIDENCE REJECTION ---
            if confidence < 70.0:
                 if self.config.get("debug_mode") and not self.runes_uncertain:
                      logger.info(f"Runes Low Confidence ({confidence:.1f}%): {runes}. Setting UNCERTAINTY.")
                 self.runes_uncertain = True
                 self.runes_uncertain_since = time.time()
                 if confidence < 50.0: return # Junk reading

            # --- BURST VALIDATION (Mandatory for Level/Runes) ---
            burst_results = self.vision.request_runes_burst()
            if not burst_results: return
            
            from collections import Counter
            counts = Counter(burst_results)
            most_common, frequency = counts.most_common(1)[0]
            
            # Require Consensus (3/5)
            if frequency < 3:
                 if self.config.get("debug_mode"):
                     logger.debug(f"Burst Inconclusive for {runes}. Results: {burst_results}")
                 return
            
            # Normalize to the consensus value
            runes = most_common

            # Re-check change gate after normalization
            if runes == self.current_runes: pass 
            else:
                # --- GAIN/STABILITY VERIFICATION (2-STEP) ---
                if not hasattr(self, 'gain_verification_candidate'):
                     self.gain_verification_candidate = -1
                
                if runes != self.gain_verification_candidate:
                     # Check for Digit-Shift Spike (e.g., 15k -> 65k)
                     is_suspicious = False
                     s_curr = str(max(0, self.current_runes))
                     s_new = str(runes)
                     if len(s_curr) == len(s_new) and len(s_new) >= 5:
                         diff_digits = sum(1 for c1, c2 in zip(s_curr, s_new) if c1 != c2)
                         if diff_digits == 1 and abs(runes - self.current_runes) >= 10000:
                             is_suspicious = True

                     # Start tracking the new candidate immediately
                     old_candidate = self.gain_verification_candidate
                     self.gain_verification_candidate = runes
                     self.spike_persistence = 1 if is_suspicious else 0
                     
                     if self.config.get("debug_mode"):
                          logger.debug(f"Gain Candidate: {runes} (Waiting for confirmation)")
                     return 

                # If same as candidate, check for suspicious persistence
                if hasattr(self, 'spike_persistence') and self.spike_persistence > 0:
                     self.spike_persistence += 1
                     if self.spike_persistence < 3: # Require 3 hits for suspicious
                         if self.config.get("debug_mode"):
                             logger.info(f"SUSPICIOUS Digit-Shift: {self.current_runes} -> {runes}. Holding for consensus ({self.spike_persistence}/3)")
                         return

                # If we are here, BURST passed AND 2/3-STEP verification passed.
                self.gain_verification_candidate = -1 
                self.spike_persistence = 0
                
                if self.config.get("debug_mode"):
                     logger.info(f"Runes Confirmed: {self.current_runes} -> {runes} (Conf: {confidence:.0f}%)")

                # --- IGNORE NEXT GAIN (After Level Up) ---
                if self._ignore_next_rune_gain and runes > self.current_runes:
                    self._ignore_next_rune_gain = False
                    self._ignore_next_rune_gain_grace_period = None
                    if self.config.get("debug_mode"):
                        logger.info(f"Ignored post-leveling gain: +{runes - self.current_runes}")
                    self.current_runes = runes 
                    self.last_runes_reading = runes
                    return

                diff = runes - self.last_runes_reading
                
                # --- CLEAR SYNC GUARD EARLY ---
                if self._level_up_pending_sync and diff < 0:
                    _, level_cost = self._level_up_pending_sync
                    if abs(diff) >= level_cost * 0.8:
                        self._level_up_pending_sync = None
                        if self.config.get("debug_mode"): logger.info("Level-Up Guard cleared (Spending detected)")

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
                             pass # Fall through to update? No, we want to reject it from "Current Runes" too?
                             # If we update current_runes to 7174, the graph will clamp it (Ratchet).
                             # But the UI will show 7174.
                             # User didn't complain about UI, only Graph.
                             # But let's be safe.
                        
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
                        # Delta Match (Standard)
                        if abs(gain - self.lost_runes_pending) <= 100: # Relaxed tolerance
                            is_recovery = True
                        # Absolute Match (Fallback for "12k glitch -> 34k")
                        # Checks if we are back to within 10% or 2000 runes of the lost amount.
                        # This handles cases where the "Drop" was misread (e.g. reading 12k instead of 0), so the Delta is wrong,
                        # but the "Recovery" restores the full previous amount.
                        elif abs(runes - self.lost_runes_pending) < max(2000, self.lost_runes_pending * 0.1):
                             is_recovery = True
                             if self.config.get("debug_mode"): logger.info(f"Recovery via Absolute Match: {runes} vs {self.lost_runes_pending}")

                    if is_recovery:
                        self.recovery_count += 1 
                        self.log_session_event("RUNE_RECOVERY", {"recovered": self.lost_runes_pending})
                        self.graph_events.append({"t": time.time(), "type": "RECOVERY"})
                        self.lost_runes_pending = 0 
                        gain = 0 
                    
                    if gain > 0: self.pending_rps_gain += gain

                # COMMIT UPDATES
                self.current_runes = runes
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
        self.schedule(0, lambda: self.update_runes_display(self.current_run_level))

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
        current_runes = getattr(self, 'current_runes', 0)
        
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
        if self.current_phase_index >= 0:
             p_name = self.phases[self.current_phase_index]["name"]
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
            "run_history": self.run_accumulated_history,
            "run_history_raw": self.run_accumulated_raw,
            "transitions": self.day_transition_markers,
            "death_count": self.death_count,
            "recovery_count": self.recovery_count,
            "phase_name": p_name,
            "spent_at_merchants": self.spent_at_merchants,
            "graph_events": self.graph_events,
            "graph_start_time": getattr(self, "graph_start_time", 0),
            "rps": self.smoothed_rps,
            "grade": self.calculate_efficiency_grade(),
            "time_to_level": self.calculate_time_to_level(missing),
            "delta_runes": self.last_calculated_delta,
            "nr_config": {
                "snowball": self.NR_SNOWBALL,
                "goal": self.NR_FARMING_GOAL,
                "duration": self.NR_TOTAL_TIME
            }
        }
        
        self.overlay.update_run_stats(stats)

    # --- ANALYTICS ENGINE ---

    def get_ideal_runes_at_time(self, t_seconds: float) -> float:
        """
        Returns the ideal rune count at time t (Farming Steps).
        Revised for 14m Phases (840s).
        """
        
        # Day 1 Duration: ~840s (14 mins)
        t_day1_end = 840.0
        
        if t_seconds < t_day1_end:
            # Segment 1: Day 1
            # Expo curve to 180,881 (Level 9.5)
            ratio = t_seconds / t_day1_end
            if ratio < 0: ratio = 0
            base_runes = 180881 * (ratio ** 1.2)
            return base_runes
        else:
            # Segment 2: Day 2 (After Boss 1)
            # Baseline: Ideal(Day1_End) + 50,000 (Boss 1 Drop)
            day1_val = 180881 
            boss1_drop = 50000
            start_val = day1_val + boss1_drop # 230,881
            
            # Target End: Level 14 (~437k) at 28m (1680s)
            target_val = 437578
            
            t_day2 = t_seconds - t_day1_end
            t_day2_duration = 840.0 # 14 mins for Day 2
            
            ratio = t_day2 / t_day2_duration
            if ratio > 1.0: ratio = 1.0
            
            # Growth from start to target
            growth_needed = target_val - start_val
            current_growth = growth_needed * (ratio ** 1.2)
            
            return start_val + current_growth

    def calculate_efficiency_grade(self) -> str:
        if self.start_time is None: 
            self.last_calculated_delta = 0
            return "C"

        # Calculate Elapsed Farming Time
        # Only count time if timer is running (paused during bosses)
        # Simplify: Use Wall Time - Start Time for now, assuming Pauses are handled 
        # via 'elapsed' passed from update_timer_task? 
        # Actually StateService doesn't track "paused duration" well globally yet.
        # But we pause graph updates during boss. Can we use len(run_history) as seconds?
        # Yes, run_history is approx seconds of active farming.
        farming_time = len(self.run_accumulated_history)
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
        """Sequence Guard: Apply penalties to unlikely state transitions."""
        # Phase mappings:
        # Day 1: 0-4 (Boss 1 is index 4)
        # Day 2: 5-9 (Boss 2 is index 9)
        # Day 3: 10-11
        
        now = time.time()
        
        # 1. Reverse Transitions (Always Penalty)
        if target_day == "DAY 1":
            if self.current_phase_index >= 5:
                return -35
            
            # --- STRICT RUNE LOCKOUT ---
            # If we already have runes (past the very initial drop), block auto-reset.
            # We use 20 as a safe threshold for OCR jitter.
            if self.current_runes > 20:
                if self.config.get("debug_mode"):
                    logger.debug(f"Reset Lockout: Runes detected ({self.current_runes}). Large penalty applied.")
                return -100
                
            # --- FINAL BOSS LOCKOUT ---
            if self.current_phase_index >= 11:
                return -120
        
        if target_day == "DAY 2" and self.current_phase_index >= 10:
            return -35
            
        # 2. Skips (Always Penalty)
        if target_day == "DAY 3" and self.current_phase_index < 5:
            return -40
            
        # 3. Premature Forward Transitions (NEW)
        # Day 1 -> Day 2: Should only happen after Boss 1 (Phase 4) or if enough time has passed
        if target_day == "DAY 2" and self.current_phase_index < 4:
            # We enforce a 12 min (720s) minimum for Day 1 -> Day 2 OCR trigger if not in Boss phase
            if elapsed_in_run < 720:
                return -100 # Extreme penalty to block OCR misreads
            else:
                return -30 # Soft penalty even if late, Boss 1 detection is preferred
                
        # Day 2 -> Day 3: Should only happen after Boss 2 (Phase 9)
        if target_day == "DAY 3" and 4 < self.current_phase_index < 9:
            return -100 # Extreme penalty to block OCR misreads
            
        return 0

    def handle_trigger(self, trigger_text: str) -> bool:
        if not self.is_transition_allowed(trigger_text):
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
        
    def is_transition_allowed(self, target_day: str) -> bool:
        """
        STRICT STATE MACHINE (User Request):
        - Day 1: Only if Reset/Startup. blocked if deep in run (Level > 5 or Runes > 100).
        - Day 2: Only if Phase is Boss 1 (Index 4).
        - Day 3: Only if Phase is Boss 2 (Index 9).
        """
        if target_day == "DAY 1":
            # Block accidental Day 1 resets if we are seemingly deep in a run
            # Exception: Manual Trigger or Startup
            if self.current_run_level > 5 or getattr(self, 'current_runes', 0) > 200:
                logger.warning(f"BLOCKED Transition to DAY 1: Level {self.current_run_level} > 5 or Runes {self.current_runes} > 200.")
                return False
            return True
            
        elif target_day == "DAY 2":
            # Must be in Boss 1 Phase (Index 4)
            # Or if we want to allow Late Detection (e.g. forgot to split), maybe?
            # User said: "jour 2 uniquement si on est au boos jour 1"
            if self.current_phase_index == 4: # Boss 1
                 return True
            else:
                 logger.warning(f"BLOCKED Transition to DAY 2: Current Phase {self.current_phase_index} is not Boss 1 (4).")
                 return False

        elif target_day == "DAY 3":
            # Must be in Boss 2 Phase (Index 9)
            if self.current_phase_index == 9: # Boss 2
                 return True
            else:
                 logger.warning(f"BLOCKED Transition to DAY 3: Current Phase {self.current_phase_index} is not Boss 2 (9).")
                 return False
                 
        return False

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
        self.timer_frozen = False
        self.current_phase_index = index
        self.start_time = time.time()
        self.last_phase_change_time = time.time() # Added to track delay
        self._check_rps_pause()
        
        # Start of Run clears Menu State
        if index != -1:
            self.is_in_menu = False

    def _check_rps_pause(self):
        if self.current_phase_index < 0: return
        phase_name = self.phases[self.current_phase_index]["name"]
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
        # "JOUR I" detection implies a reset. We aggressively clear all state.
        self.timer_frozen = True  # Just freeze, don't announce
        self.start_new_session("Storm")
        
        # --- AGGRESSIVE RESET (Anti-Death/Anti-Leak) ---
        self.current_run_level = 1
        self.current_runes = 0
        self.last_runes_reading = 0
        self.last_valid_total_runes = 0
        self.last_display_level = 1
        self.last_display_runes = 0
        
        # Reset Timer & Global State
        self.start_time = time.time()
        self.boss3_start_time = None
        self.day1_detection_time = time.time()
        
        # Reset RPS & Smoothing
        self.rune_gains_history = deque([0] * 40, maxlen=40)
        self.smoothed_rps = 0.0
        self.pending_rps_gain = 0
        self.rps_paused = False
        
        # Reset Graphics & Markers
        self.run_accumulated_history = []
        self.run_accumulated_raw = []
        self.graph_events = []
        self.graph_log_data = []
        self.graph_start_time = time.time() 
        self.day_transition_markers = []
        self.last_calculated_delta = 0
        
        # Reset Statistics
        self.permanent_loss = 0
        self.death_count = 0
        self.recovery_count = 0
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
        
        if not self.day1_detection_time: self.day1_detection_time = time.time()
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
        marker_idx = len(self.run_accumulated_history)
        self.day_transition_markers.append((marker_idx, "DAY 1"))
        return True

    def trigger_day_2(self):
        if self.current_phase_index != 5:
            self.Trigger(5)
            # Record marker for graph
            marker_idx = len(self.run_accumulated_history)
            self.day_transition_markers.append((marker_idx, "DAY 2"))

    def trigger_day_3(self):
        if self.current_phase_index < 10:
            self.Trigger(10)
            # Record marker for graph
            marker_idx = len(self.run_accumulated_history)
            self.day_transition_markers.append((marker_idx, "DAY 3"))
            self.boss3_start_time = time.time()

    def trigger_final_boss(self):
        if self.current_phase_index != 11:
            self.Trigger(11)
            # The instruction moved boss3_start_time to trigger_day_3, so this line is removed.
            # self.boss3_start_time = time.time() 

    def skip_to_boss(self):
        """Skip to the boss of the current day for testing."""
        logger.info(f"Manual skip requested. Current phase: {self.current_phase_index}")
        if self.current_phase_index < 4:
            msg = "SKIP: Skipping to Boss 1"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.Trigger(4)
        elif self.current_phase_index < 9:
            msg = "SKIP: Skipping to Boss 2"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.Trigger(9)
        elif self.current_phase_index == 9:
            msg = "SKIP: Skipping to Day 3 Preparation"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.trigger_day_3()
        else:
            msg = "SKIP: Skipping to Final Boss"
            logger.info(msg)
            self.vision.log_debug(msg)
            self.trigger_final_boss()

    def get_current_state(self) -> str:
        if self.current_phase_index == -1: return "Waiting"
        return self.phases[self.current_phase_index]["name"]

    # --- Timer Loop ---

    def update_overlay_now(self):
        # Force update logic for immediate feedback
        pass # loop will catch up in 100ms

    # --- Victory ---
    def check_victory_loop(self):
        if not self.running: return
        if self.current_phase_index != 11:
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
        else:
             self.schedule(int(self.victory_check_interval * 1000), self.check_victory_loop)

    def stop_timer_victory(self):
        self.timer_frozen = True
        
        total_time = 0
        boss3_time = 0
        now = time.time()
        
        if self.day1_detection_time: total_time = now - self.day1_detection_time
        elif self.start_time: total_time = now - self.start_time # Approximation
        
        if self.boss3_start_time: boss3_time = now - self.boss3_start_time
        
        fmt = lambda s: f"{int(s//60):02}:{int(s%60):02}"
        final_text = f"{fmt(total_time)}"
        
        self.overlay.update_timer(final_text)
        self.audio.announce("Victoire !")

    # --- Manual Feedback ---
    def handle_manual_feedback(self, correct_target: str):
        logger.info(f"Manual Feedback requested: {correct_target}")
        
        # Guard: Prevent accidental Day 2 trigger if too early in Day 1 run
        if correct_target == "DAY 2":
            elapsed_in_run = len(self.run_accumulated_history)
            # If less than 8 minutes (480s) have passed, we ignore the hotkey unless in Boss 1
            if self.current_phase_index < 4 and elapsed_in_run < 480:
                logger.warning(f"Manual DAY 2 ignored: Run too short ({elapsed_in_run}s < 480s) and not in Boss phase.")
                try: winsound.Beep(300, 200) # Low error beep
                except: pass
                return

        if not self.triggered_recently:
            logger.info(f"Manual Feedback Applied: {correct_target}")
            self.handle_trigger(correct_target)
            self.triggered_recently = True
            self.schedule(5000, lambda: setattr(self, 'triggered_recently', False))
            
            # Save a sample to help debug what was happening
            if self.config.get("save_raw_samples", True) or self.config.get("debug_mode", False):
                self.vision.save_labeled_sample(f"MANUAL_{correct_target}")
        else:
             logger.warning(f"Manual Feedback {correct_target} ignored: Triggered too recently.")

    def handle_false_positive(self):
        logger.info("Manual Feedback: False Positive")
        self.timer_frozen = False
        self.current_phase_index = -1
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
            
        phase_name = "Unknown"
        if 0 <= self.current_phase_index < len(self.phases):
            phase_name = self.phases[self.current_phase_index]["name"]
            
        return {
            "phase": phase_name,
            "phase_index": self.current_phase_index,
            "session_count": self.session_count,
            "runes": self.current_runes,
            "level": self.current_run_level,
            "spent_merchants": self.spent_at_merchants,
            "death_count": self.death_count,
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
        
        self.death_count += 1
        self.total_death_loss += total_loss
        self.lost_runes_pending = total_loss
        
        death_event = {
                "death_num": self.death_count,
                "old_level": old_level,
                "new_level": level,
                "runes_at_death": death_runes,
                "level_cost_lost": lost_level_cost,
                "total_loss": total_loss,
                "retroactive": True
            }
        self.death_history.append(death_event)
        self.log_session_event("DEATH", death_event)
        self.graph_events.append({"t": time.time(), "type": "DEATH"})
        
        # 3. Graph Repair (Similar to standard death)
        # We need to subtract the loss from 'last_valid_total_runes' 
        # But wait, 'last_valid_total_runes' might have already updated? 
        # No, 'on_runes_detected' calls this BEFORE committing the drop to 'current_runes' state usually?
        # Actually it's inside the "SPENDING" block.
        # So 'last_valid_total_runes' considers the runes as "Available". 
        
        # We must ignore the next rune drop? No, we just processed it.
        self._ignore_next_rune_drop = True 


