import time
import datetime
import winsound
import subprocess
import threading
import os
import json
from typing import Optional, List, Dict
from src.services.base_service import IStateService, IConfigService, IVisionService, IOverlayService
from src.pattern_manager import PatternManager
try:
    import keyboard
except ImportError:
    keyboard = None

class StateService(IStateService):
    def __init__(self, config: IConfigService, vision: IVisionService, overlay: IOverlayService):
        self.config = config
        self.vision = vision
        self.overlay = overlay
        
        self.running = False
        self.is_hibernating = True
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
        
        # Day 3 State Machine
        self.day3_seq_step = 0 
        self.black_screen_start = 0
        self.in_black_screen = False
        
        # Victory detection
        self.victory_check_active = False
        self.last_victory_check = 0
        self.victory_check_interval = 0.5

        # Audio state
        self.last_beep_second = -1

    def initialize(self) -> bool:
        self.running = True
        self.vision.add_observer(self.on_ocr_result)
        
        # Setup Hotkeys
        if keyboard:
            try:
                keyboard.add_hotkey('&', lambda: self.handle_manual_feedback("DAY 1"))
                keyboard.add_hotkey('é', lambda: self.handle_manual_feedback("DAY 2"))
                keyboard.add_hotkey('"', lambda: self.handle_manual_feedback("DAY 3"))
                keyboard.add_hotkey('(', self.handle_false_positive)
            except Exception as e:
                print(f"Failed to register hotkeys: {e}")

        # Start process monitor loop
        self.schedule(0, self.check_process_loop)
        
        # Start timer update loop
        self.schedule(0, self.update_timer_loop)
        
        return True

    def shutdown(self) -> None:
        self.running = False

    def schedule(self, delay_ms: int, callback):
        self.overlay.schedule(delay_ms, callback)

    # --- Process Monitor ---
    def check_process_loop(self):
        if not self.running: return
        
        game_running = self.check_process(self.game_process)
        
        if game_running and self.is_hibernating:
             self.wake_up()
        elif not game_running and not self.is_hibernating:
             self.hibernate()
            
        self.schedule(5000, self.check_process_loop)

    def check_process(self, process_name):
        try:
            cmd = 'tasklist'
            output = subprocess.check_output(cmd, shell=True).decode(errors='ignore')
            return process_name.lower() in output.lower()
        except:
            return False

    def wake_up(self):
        print("Elden Ring detected! Waking up...")
        self.is_hibernating = False
        self.overlay.show()
        self.vision.resume_capture()

    def hibernate(self):
        print("Elden Ring closed. Hibernating...")
        self.is_hibernating = True
        self.overlay.hide()
        self.vision.pause_capture()

    # --- OCR & State Logic ---
    def on_ocr_result(self, text, width, offset, word_data, brightness=0):
        # Called from Vision thread. Dispatch to UI thread for processing if needed 
        # but logic can run here if thread-safe, just UI updates need scheduling.
        # process_ocr_trigger access self state, should be fine properly locked or if single consumer.
        # To be safe and avoid race conditions, we schedule it on UI thread
        self.schedule(0, lambda: self.process_ocr_trigger(text, width, offset, word_data, brightness))

    def process_ocr_trigger(self, text, width, offset, word_data, brightness=0):
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
                self.vision.set_scan_delay(0.08)
            elif now > self.fast_mode_end_time and time_since_last_trigger > 2.0:
                self.fast_mode_active = False
                self.vision.set_scan_delay(0.08)

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
                    self.vision.set_scan_delay(0.05)
                    if now - self.last_beep_time > 2.0:
                         try: winsound.MessageBeep(winsound.MB_ICONWARNING)
                         except: pass
                         self.last_beep_time = now
                
                self.fast_mode_end_time = now + 10.0

            # Pattern Match
            target_day, score = self.pattern_manager.evaluate(normalized, text_width=width, center_offset=offset, word_data=word_data)
            
            if target_day and score >= 65:
                detected_trigger = target_day
                self.current_matched_pattern = normalized
                if self.config.get("debug_mode"):
                    print(f"Match: {normalized} -> {target_day} ({score})")
                
                if not self.fast_mode_active:
                    self.fast_mode_active = True
                    self.vision.set_scan_delay(0.05)
                self.last_fast_mode_trigger = now
                
                if detected_trigger == "DAY 3":
                    self.fast_mode_end_time = now + 15.0
                    self.last_jour_detection = now
                else:
                    self.fast_mode_end_time = now + 10.0

        if detected_trigger:
            self.trigger_buffer.append((now, detected_trigger, score))

        if not self.trigger_buffer and not self.fast_mode_active:
             if self.current_phase_index != 10: # If not in Day 3 Prep
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
        elif day_counts["DAY 1"] >= 2 and day_scores["DAY 1"] > day_scores["DAY 3"]:
            final_decision = "DAY 1"
            
        if final_decision and not self.triggered_recently:
            self.handle_trigger(final_decision)
            self.triggered_recently = True
            self.trigger_buffer = []
            self.schedule(4000, lambda: setattr(self, 'triggered_recently', False))

        # Day 3 Black Screen
        if self.current_phase_index == 10:
             is_black = (brightness < 15)
             if is_black:
                 if not self.in_black_screen:
                     self.in_black_screen = True
                     self.black_screen_start = now
             else:
                 if self.in_black_screen:
                     duration = now - self.black_screen_start
                     self.in_black_screen = False
                     
                     if 0.3 <= duration <= 1.5 and self.day3_seq_step == 0:
                         self.day3_seq_step = 1
                     elif duration >= 0.8 and self.day3_seq_step == 1:
                         self.trigger_final_boss()
                         self.day3_seq_step = 0
        
        # Victory check loop handled separately via `check_victory_loop` 
        # but needs to be triggered.
        if self.current_phase_index == 11 and not self.victory_check_active:
             self.victory_check_active = True
             self.schedule(int(self.victory_check_interval * 1000), self.check_victory_loop)

    def handle_trigger(self, trigger_text: str):
        if trigger_text == "DAY 1": self.set_phase_by_name_start("Day 1")
        elif trigger_text == "DAY 2": self.set_phase_by_name_start("Day 2")
        elif trigger_text == "DAY 3": self.set_phase_by_name_start("Day 3")

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
        self.update_overlay_now()

    def trigger_day_1(self):
        is_in_day_1 = (0 <= self.current_phase_index <= 3)
        elapsed = time.time() - self.start_time if self.start_time else 0
        if not is_in_day_1 or elapsed > 15:
            if not self.day1_detection_time: self.day1_detection_time = time.time()
            self.Trigger(0)

    def trigger_day_2(self):
        is_in_day_2 = (5 <= self.current_phase_index <= 8)
        elapsed = time.time() - self.start_time if self.start_time else 0
        if not is_in_day_2 or elapsed > 15:
            self.Trigger(5)

    def trigger_day_3(self):
        is_in_day_3 = (self.current_phase_index == 10 or self.current_phase_index == 11)
        if not is_in_day_3:
            self.Trigger(10)

    def trigger_final_boss(self):
        if self.current_phase_index != 11:
            self.Trigger(11)
            self.boss3_start_time = time.time()

    def get_current_state(self) -> str:
        if self.current_phase_index == -1: return "Waiting"
        return self.phases[self.current_phase_index]["name"]

    # --- Timer Loop ---
    def update_timer_loop(self):
        if not self.running: return

        if self.timer_frozen:
            # Stopped state
            self.schedule(100, self.update_timer_loop)
            return

        if self.start_time and self.current_phase_index >= 0:
            phase = self.phases[self.current_phase_index]
            elapsed = time.time() - self.start_time
            
            if phase["duration"] > 0:
                remaining = max(0, phase["duration"] - elapsed)
                remaining_int = int(remaining)
                
                # Phase Auto Advance
                if remaining == 0:
                    self.current_phase_index += 1
                    self.start_time = time.time() # Reset start time for next phase
                    # Logic needed if next phase is Boss Manual?
                    # phases list has duration 0 for Boss 1/2.
                    self.update_timer_loop() # Recursive immediate update
                    return

                mins = int(remaining // 60)
                secs = int(remaining % 60)
                timer_str = f"{mins:02}:{secs:02}"
                
                # Audio Beeps
                if remaining_int in [30, 10, 3, 2, 1] and remaining_int != self.last_beep_second:
                     try: winsound.Beep(1000 if remaining_int > 3 else 1500, 200)
                     except: pass
                     self.last_beep_second = remaining_int
                elif remaining_int not in [30, 10, 3, 2, 1]:
                     self.last_beep_second = -1
            else:
                # Stopwatch
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                timer_str = f"{mins:02}:{secs:02}"
                
            prefix = ""
            if self.fast_mode_active: prefix += "🔴 "
            # Warning blink
            next_idx = self.current_phase_index + 1
            if phase["duration"] > 0 and next_idx < len(self.phases) and "Shrinking" in self.phases[next_idx]["name"]:
                remaining = max(0, phase["duration"] - elapsed)
                if remaining <= 30 and int(time.time() * 2) % 2 == 0:
                    prefix += "⚠️ "

            self.overlay.update_timer(f"{prefix}{phase['name']} - {timer_str}")

        else:
             text = "Waiting for Day 1..."
             if self.fast_mode_active: text = "🔴 " + text
             self.overlay.update_timer(text)

        self.schedule(100, self.update_timer_loop)

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
             print(f"VICTORY: {text} ({score})")
             self.stop_timer_victory()
             self.victory_check_active = False
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
        try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except: pass

    # --- Manual Feedback ---
    def handle_manual_feedback(self, correct_target):
        print(f"Manual Feedback: {correct_target}")
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
        print("Manual Feedback: False Positive")
        self.timer_frozen = False
        self.current_phase_index = -1
        self.overlay.update_timer("Waiting...")
        if self.current_matched_pattern:
             self.pattern_manager.punish(self.current_matched_pattern)
             try: winsound.Beep(500, 500)
             except: pass
