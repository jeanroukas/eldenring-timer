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
        self.last_display_runes = 0

    def initialize(self) -> bool:
        logger.info("StateService: Initializing...")
        self.running = True
        
        # Subscribe to config changes
        self.config.add_observer(self.on_config_changed)
        
        # Start Vision Capture Loop
        self.vision.start_capture()
        self.vision.add_observer(self.on_ocr_result)
        self.vision.add_level_observer(self.on_level_detected)
        self.vision.add_runes_observer(self.on_runes_detected)

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
        self.last_calculated_delta = 0 # Store for UI
        
        # --- NIGHTREIGN ANALYTICS CONSTANTS ---
        self.NR_TOTAL_REQ = 513116
        self.NR_BOSS_DROPS = 11000 + 50000 # ~61k guaranteed
        self.NR_FARMING_GOAL = self.NR_TOTAL_REQ - self.NR_BOSS_DROPS # ~452k
        self.NR_DAY_DURATION = 1200 # 20 mins per day
        self.NR_TOTAL_TIME = self.NR_DAY_DURATION * 2 # 40 mins farming time
        self.NR_SNOWBALL = 1.7
        
        # Transaction History (for correction)
        self.recent_spending_history = [] # List of (timestamp, amount)

        # Graph Logging
        self.graph_log_file = ""
        self.graph_log_data = []
        self.last_graph_save = 0
        self.graph_start_time = 0 # Timestamp when graph history started

        # --- FULL-RUN HISTORY (User Request) ---
        self.run_accumulated_history = [] # Total runes per second
        self.day_transition_markers = [] # List of (index, day_name)
        
        # Session Management
        self.session_count = self.config.get("session_count", 0)
        self.current_phase = "INIT"
        self.start_new_session("STARTUP")
        
        self.update_runes_display(1)

        # Initialize Audio
        self.audio.initialize()
        
        # Setup Hotkeys
        if keyboard:
            try:
                keyboard.add_hotkey('&', lambda: self.handle_manual_feedback("DAY 1"))
                keyboard.add_hotkey('é', lambda: self.handle_manual_feedback("DAY 2"))
                keyboard.add_hotkey('"', lambda: self.handle_manual_feedback("DAY 3"))
                keyboard.add_hotkey('(', self.handle_false_positive)
                keyboard.add_hotkey('ctrl+shift+b', self.skip_to_boss)
                keyboard.add_hotkey('ctrl+shift+r', self.restart_application)
            except Exception as e:
                logger.error(f"Failed to register hotkeys: {e}")

        # Start background thread for loops
        self.thread = threading.Thread(target=self._run_loops, daemon=True)
        self.thread.start()
        
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
                event_time, spent_val, current_runes = self.pending_spending_event
                if now - event_time >= 1.5:
                    # Still no level up captured? Must be a real purchase.
                    self.spent_at_merchants += spent_val
                    self.log_session_event("SPENDING", {"spent": spent_val, "total_spent": self.spent_at_merchants, "current": current_runes})
                    self.recent_spending_history.append((time.time(), spent_val))
                    self.pending_spending_event = None

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

                    # --- RPS Per-Second Update ---
                    if time.time() - self.last_rps_update >= 1.0:
                        self.last_rps_update = time.time()
                        if not self.rps_paused:
                            self.rune_gains_history.append(self.pending_rps_gain)
                            self.pending_rps_gain = 0
                        self.smoothed_rps = sum(self.rune_gains_history) / 40.0
                    
                    # --- FULL-RUN GRAPH UPDATE ---
                    if not self.rps_paused:
                        spent_on_levels = RuneData.get_total_runes_for_level(self.current_run_level) or 0
                        current_calc = spent_on_levels + self.spent_at_merchants + self.current_runes + self.lost_runes_pending + self.permanent_loss
                        
                        if current_calc > self.last_valid_total_runes:
                            self.last_valid_total_runes = current_calc
                        
                        # FORCE 0 for first 15s (Falling/Loading)
                        # We use the length of history as the time index (approx 1s per tick)
                        if len(self.run_accumulated_history) < 15:
                             total_accumulated = 0
                        else:
                             total_accumulated = self.last_valid_total_runes
                        
                        self.run_accumulated_history.append(total_accumulated)
                        
                        # --- GRAPH LOGGING ---
                        graph_entry = {
                            "t": float(f"{time.time():.2f}"),
                            "fmt": datetime.datetime.now().strftime("%H:%M:%S"),
                            "raw": current_calc,
                            "display": total_accumulated,
                            "comps": {
                                "lvl_cost": spent_on_levels,
                                "merch": self.spent_at_merchants,
                                "curr": self.current_runes,
                                "pend": self.lost_runes_pending,
                                "perm": self.permanent_loss
                            }
                        }
                        self.graph_log_data.append(graph_entry)
                        
                        if time.time() - self.last_graph_save >= 5.0:
                            self.save_graph_log()
                            self.last_graph_save = time.time()
                    
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
                 self.overlay.update_timer("00:00")
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

            # Pattern Match
            target_day, score = self.pattern_manager.evaluate(normalized, text_width=width, center_offset=offset, word_data=word_data)
            
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
        elif day_counts["DAY 1"] >= 2 and day_scores["DAY 1"] > 100: 
            final_decision = "DAY 1"
            
        if final_decision and not self.triggered_recently:
            # --- STABILITY VALIDATION (User Request) ---
            # Real Day banners appear while the player is NOT actively leveling or gaining runes.
            # If stats are changing, it's likely an OCR error during gameplay.
            if self.is_stats_stable(1.2):
                logger.info(f"ACTIVATING TRIGGER {final_decision} (Stats Stable)")
                self.handle_trigger(final_decision)
                self.triggered_recently = True
                self.trigger_buffer = []
                self.schedule(4000, lambda: setattr(self, 'triggered_recently', False))
            else:
                if self.config.get("debug_mode"):
                    logger.debug(f"FILTERED Trigger {final_decision}: Stats unstable (Changing in last 1.2s)")
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

    def on_level_detected(self, level: int):
        # Valid range check (assuming max level 713)
        if level < 1 or level > 713: return
        
        # Stability / Consensus Mechanism:
        # To avoid misreads (flickering), we only accept a level change if we see it
        # at least twice in a row.
        if level == self.pending_level:
            self.level_consensus_count += 1
        else:
            self.pending_level = level
            self.level_consensus_count = 1
            
        # Exception: Instant update if it's level 1 (reset)
        is_reset = (level == 1)
        
        if self.level_consensus_count >= 2 or is_reset:
            # Only update if changed (or first time after init)
            if level != self.current_run_level:
                old_level = self.current_run_level
                
                # --- CANCEL PENDING SPENDING ---
                # A level change (up or down) means the rune drop was likely due to leveling or death.
                if self.pending_spending_event:
                    self.pending_spending_event = None
                    if self.config.get("debug_mode"):
                        logger.info("Pending SPENDING cancelled (Level Change detected)")
                
                # --- CANCEL PENDING SPENDING ---
                # A level change (up or down) means the rune drop was likely due to leveling or death.
                if self.pending_spending_event:
                    self.pending_spending_event = None
                    if self.config.get("debug_mode"):
                        logger.info("Pending SPENDING cancelled (Level Change detected)")
                
                # --- DEATH LOGIC (TRIPLE LOCK) ---
                if level < old_level:
                    # 1. Check if Runes actually dropped to Zero
                    curr_runes = self.current_runes if hasattr(self, 'current_runes') else 0
                    if curr_runes > 0:
                        logger.warning(f"IGNORED Level Drop {old_level}->{level}: Runes did not drop to 0 (Held: {curr_runes}). Probable OCR misread.")
                        # Do NOT trigger death. Trust the runes over the level number for now.
                        return

                    # 2. Check for recent Black Screen (12s window)
                    now = time.time()
                    time_since_black = now - getattr(self, 'last_black_screen_end', 0)
                    if time_since_black > 12.0:
                         logger.warning(f"IGNORED Level Drop {old_level}->{level}: No recent Black Screen (Last: {time_since_black:.1f}s ago). Noise?")
                         return

                    # --- DOUBLE DEATH CHECK ---
                    # If we have pending runes from a previous death, they are now PERMANENTLY LOST.
                    if self.lost_runes_pending > 0:
                        self.permanent_loss += self.lost_runes_pending
                        self.log_session_event("PERMANENT_LOSS", {"amount": self.lost_runes_pending})
                        self.lost_runes_pending = 0 # Clear pending, moved to permanent

                    # --- SPENDING CORRECTION (Anti-Spike) ---
                    # Check for spending events in the last 60 seconds (likely false positives from level up screen delay)
                    now = time.time()
                    reverted_amount = 0
                    valid_history = []
                    
                    for t, amount in self.recent_spending_history:
                        if now - t <= 60.0:
                            reverted_amount += amount
                        else:
                            valid_history.append((t, amount))
                            
                    if reverted_amount > 0:
                        self.spent_at_merchants -= reverted_amount
                        if self.spent_at_merchants < 0: self.spent_at_merchants = 0
                        self.log_session_event("SPENDING_REVERTED", {"amount": reverted_amount, "reason": f"Level Up {old_level}->{level}"})
                        logger.info(f"Reverted {reverted_amount} spending due to Level Up detection.")
                        
                    self.recent_spending_history = valid_history
                    
                    for t, amount in self.recent_spending_history:
                        if now - t < 10.0:
                            self.spent_at_merchants -= amount
                            reverted_amount += amount
                            if self.config.get("debug_mode"):
                                logger.info(f"Reverted False Spending: {amount} (Time diff: {now-t:.2f}s)")
                        else:
                            valid_history.append((t, amount))
                    
                    self.recent_spending_history = valid_history
                    
                    if reverted_amount > 0:
                         self.log_session_event("SPENDING_CORRECTED", {"reverted": reverted_amount})

                    # --- DEATH CALCULATION ---
                    # Total loss = Runes we had (Snapshot or 0) + Cost of level lost + Reverted Runes (which were actually lost)
                    # Note: death_runes logic might be redundant if we use reverted_amount, but we keep it for safety.
                    lost_level_cost = RuneData._LEVEL_COSTS.get(old_level, 0)
                    death_runes = self.last_runes_reading 
                    
                    # Robust Total: The runes we thought we spent were actually dropped on death.
                    total_loss = death_runes + lost_level_cost + reverted_amount
                    
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
                    self._ignore_next_rune_drop = True # Prevent on_runes_detected from logging "SPENDING"
                    self.graph_events.append({"t": time.time(), "type": "DEATH"})
                
                # --- LEVEL UP LOGIC ---
                elif level > old_level:
                    # --- SPENDING CORRECTION (Anti-Spike for Level Up) ---
                    # Check for spending events in the last 60 seconds (likely false positives from level up screen delay)
                    now = time.time()
                    reverted_amount = 0
                    valid_history = []
                    
                    for t, amount in self.recent_spending_history:
                        if now - t <= 60.0:
                            reverted_amount += amount
                        else:
                            valid_history.append((t, amount))
                            
                    if reverted_amount > 0:
                        self.spent_at_merchants -= reverted_amount
                        if self.spent_at_merchants < 0: self.spent_at_merchants = 0
                        self.log_session_event("SPENDING_REVERTED", {"amount": reverted_amount, "reason": f"Level Up {old_level}->{level}"})
                        logger.info(f"Reverted {reverted_amount} spending due to Level Up detection.")
                        
                    self.recent_spending_history = valid_history

                    self.log_session_event("LEVEL_UP", {"old": old_level, "new": level})
                    self._ignore_next_rune_drop = True # Prevent spending detection for the level cost consumption
                
                if self.config.get("debug_mode"):
                    logger.info(f"Level Changed (Consensus): {old_level} -> {level}")
                
                self.current_run_level = level
                self.last_stat_change_time = time.time() # Mark stat change
                # self._ignore_next_rune_drop is already set in blocks above if needed
                self.schedule(0, lambda: self.update_runes_display(level))
                # Reset consensus once applied
                self.level_consensus_count = 0 

    def on_runes_detected(self, runes: int):
        if not hasattr(self, 'current_runes'):
            self.current_runes = 0
            self.last_runes_reading = 0
            
        if runes != self.current_runes:
            # --- BURST VALIDATION (User Refinement) ---
            # Trigger a sequence of 5 fast scans to confirm the number
            burst_results = self.vision.request_runes_burst()
            if burst_results:
                from collections import Counter
                # Find the most frequent value in the burst (Majority Vote)
                counts = Counter(burst_results)
                valid_runes, freq = counts.most_common(1)[0]
                
                # If the majority view matches our new value, or is a strong consensus
                if freq >= 3:
                    runes = valid_runes
                else:
                    # Inconclusive burst: Skip this update to avoid false readings
                    if self.config.get("debug_mode"):
                        logger.debug(f"Burst inconclusive (reading: {runes}, burst: {burst_results}). Skipping update.")
                    return

            if runes == self.current_runes: return # False alarm filtered by burst
            
            if self.config.get("debug_mode"):
                 logger.info(f"Runes Changed (Confirmed): {self.current_runes} -> {runes}")
            
            # --- MERCHANT SPENDING vs RECOVERY vs GAIN ---
            diff = runes - self.last_runes_reading
            
            # 1. MERCHANT SPENDING / SPENDING (Negative diff, stable level)
            if diff < 0:
                if self._ignore_next_rune_drop:
                    self._ignore_next_rune_drop = False
                    # It was a death/leveling, already handled
                else:
                    spent = abs(diff)
                    # Use a grace period to differentiate from Level Up consumption
                    self.pending_spending_event = (time.time(), spent, runes)
                gain = 0
            
            # 2. POTENTIAL RECOVERY / NEW GAIN
            elif diff > 0:
                gain = diff
                
                # OCR Doubt: Log unrealistic gains
                if gain > 500000:
                    logger.warning(f"OCR Doubt: Massive jump detected (+{gain}). Logged for audit.")
                    self.log_session_event("OCR_DOUBT", {"gain": gain, "current": runes})

                if self.lost_runes_pending > 0:
                    # --- STRICT RECOVERY (User Request: All or Nothing) ---
                    # We only accept a recovery if the gain matches the pending loss EXACTLY.
                    # We allow a tiny tolerance (5 runes) just for last-digit OCR jitter.
                    if abs(gain - self.lost_runes_pending) <= 5:
                        self.recovery_count += 1 # Increment Recovery Count
                        self.log_session_event("RUNE_RECOVERY", {"recovered": gain, "exact_match": True})
                        self.graph_events.append({"t": time.time(), "type": "RECOVERY"})
                        self.lost_runes_pending = 0 
                        gain = 0 
                    else:
                        # If it's not a match, it's just farming or a new gain.
                        # We DO NOT touch lost_runes_pending.
                        pass
                
                # Add real gain to pending RPS
                if gain > 0:
                    self.pending_rps_gain += gain
            else:
                gain = 0

            self.current_runes = runes
            self.last_runes_reading = runes
            self.last_stat_change_time = time.time() # Mark stat change
            
            # Update display
            self.schedule(0, lambda: self.update_runes_display(self.current_run_level))

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
        
        potential_level = RuneData.calculate_potential_level(disp_lvl, disp_runes)
        
        # User refinement: Next Level = Potential + 1
        target_level = potential_level + 1
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
            "potential_level": potential_level,
            "current_runes": disp_runes,
            "total_runes": total_runes_to_show,
            "next_level": target_level,
            "needed_runes": relative_needed,
            "missing_runes": missing,
            "is_max_level": disp_lvl >= 15,
            "run_history": self.run_accumulated_history,
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
        Returns the ideal rune count at time t using the "Stepped Snowball" Curve.
        
        Logic:
        1. Effective Time = t - 15s (Falling/Loading)
        2. Base Farming = 452k * (t_eff / 40min)^1.7
        3. Boss Bonuses = +11k (at 20m) + 50k (at 40m)
        """
        offset = 15.0 # Seconds "in the air"
        
        if t_seconds <= offset: return 0
        
        effective_t = t_seconds - offset
        effective_total_time = self.NR_TOTAL_TIME # 2400s (40m)
        
        # 1. Base Farming (Continuous)
        # Cap ratio at 1.0 to avoid overshooting goal if run goes long
        ratio = effective_t / effective_total_time
        if ratio > 1.0: ratio = 1.0
        
        farming_progress = self.NR_FARMING_GOAL * (ratio ** self.NR_SNOWBALL)
        
        # 2. Boss Steps (Discrete)
        boss_bonus = 0
        day1_end = 1200.0 # 20 mins
        day2_end = 2400.0 # 40 mins
        
        if effective_t > day1_end:
            boss_bonus += 11000 # Boss 1
            
        if effective_t > day2_end:
            boss_bonus += 50000 # Boss 2
            
        return farming_progress + boss_bonus

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
        # Day 1: 0-4
        # Day 2: 5-9
        # Day 3: 10-11
        
        # Reset (Going back to Day 1)
        if target_day == "DAY 1" and self.current_phase_index >= 5:
            return -35
            
        # Skip (Day 1 -> Day 3)
        if target_day == "DAY 3" and self.current_phase_index < 5:
            return -40
            
        # Reverse (Day 3 -> Day 2)
        if target_day == "DAY 2" and self.current_phase_index >= 10:
            return -35
            
        return 0

    def handle_trigger(self, trigger_text: str):
        if self.current_session_id == -1:
             self.current_session_id = self.db.create_session()
             logger.info(f"StateService: Started Session {self.current_session_id} (Trigger: {trigger_text})")
             
        if trigger_text == "DAY 1": self.set_phase_by_name_start("Day 1")
        elif trigger_text == "DAY 2": self.set_phase_by_name_start("Day 2")
        elif trigger_text == "DAY 3": self.set_phase_by_name_start("Day 3")
        
        if self.current_session_id != -1:
             self.db.log_event(self.current_session_id, "TRIGGER", trigger_text)

        # Auto-Label Training Data
        if self.config.get("save_raw_samples", True):
             self.vision.save_labeled_sample(trigger_text)

    def set_phase_by_name_start(self, name_start_str):
        # Logique simplifiée pour mapper Day 1 -> Phase 0, Day 2 -> Phase 5 etc.
        if name_start_str == "Day 1":
             # Logic from old app: if not in Day 1 or elapsed > 15
             self.trigger_day_1()
        elif name_start_str == "Day 2":
             self.trigger_day_2()
        elif name_start_str == "Day 3":
             self.trigger_day_3()

    def Trigger(self, index):
        self.timer_frozen = False
        self.current_phase_index = index
        self.start_time = time.time()
        self.last_phase_change_time = time.time() # Added to track delay
        self._check_rps_pause()

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

    def trigger_day_1(self):
        is_in_day_1 = (0 <= self.current_phase_index <= 3)
        elapsed = time.time() - self.start_time if self.start_time else 0
        if not is_in_day_1 or elapsed > 15:
            # self.stop_timer_victory() # REMOVED: Caused "Victoire" announcement on reset
            self.timer_frozen = True  # Just freeze, don't announce
            self.start_new_session("Storm")
            
            # Reset Graph & History
            self.run_accumulated_history = []
            self.graph_start_time = time.time() # Reset graph time base
            self.day_transition_markers = []
            self.last_valid_total_runes = 0
            self.last_display_level = 1
            self.last_display_runes = 0
            self.permanent_loss = 0
            self.recent_spending_history = []
            
            # Reset RPS for new run
            self.rune_gains_history = deque([0] * 40, maxlen=40)
            self.rps_paused = False
            self.pending_rps_gain = 0
            
            if not self.day1_detection_time: self.day1_detection_time = time.time()
            self.victory_detected = False # Reset for new run
            
            # Reset level to 1 for the new run
            self.pending_level = 1
            self.level_consensus_count = 2 # Force consensus
            self.on_level_detected(1)
            
            self.Trigger(0)
            # Record marker for graph
            marker_idx = len(self.run_accumulated_history)
            self.day_transition_markers.append((marker_idx, "DAY 1"))

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
        final_text = f"Total: {fmt(total_time)} | Boss 3: {fmt(boss3_time)}"
        
        self.overlay.update_timer(final_text)
        self.audio.announce("Victoire !")

    # --- Manual Feedback ---
    def handle_manual_feedback(self, correct_target):
        logger.info(f"Manual Feedback: {correct_target}")
        if not self.triggered_recently:
            self.handle_trigger(correct_target)
            self.triggered_recently = True
            self.schedule(5000, lambda: setattr(self, 'triggered_recently', False))
            
        # Learn part (simplified log reading access?)
        # For strictness, StateService shouldn't read file directly if ConfigService does.
        # But PatternManager learns from memory or needs to update.
        # Let's import the log reading logic or simpler:
        # Just learn from self.last_raw_text if available?
        # App.last_raw_text was stored. I removed it from StateService storage?
        # No, I didn't store it. I should store last seen text.
        pass

    def handle_false_positive(self):
        logger.info("Manual Feedback: False Positive")
        self.timer_frozen = False
        self.timer_frozen = False
        self.current_phase_index = -1
        
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

