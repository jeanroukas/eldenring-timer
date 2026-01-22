# NOTE: Always analyze and implement project tracking.md
import tkinter as tk
from src.config import load_config, save_config
from src.region_selector import RegionSelector
from src.vision_engine import VisionEngine
from src.overlay import Overlay
from src.pattern_manager import PatternManager
import threading
import time
import winsound
import os

try:
    import keyboard
except ImportError:
    keyboard = None
    print("Warning: 'keyboard' module not found. Global hotkeys disabled.")

import argparse
import subprocess
import ctypes
from ctypes import wintypes
import sys
import datetime

import re

# Set DPI Awareness for Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        print("Could not set DPI awareness")

class App:
    def __init__(self):
        # 0. Singleton Check (Mutex)
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\EldenRingNightreignTimerMutex"
        self.mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        
        if last_error == 183:
            print("Another instance is already running. Exiting.")
            sys.exit(0)

        self.config = load_config()
        self.root = tk.Tk()
        
        # Parse Arguments
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", action="store_true", help="Open configuration window")
        args = parser.parse_args()
        
        self.vision = None
        self.overlay = None
        
        # State
        self.is_hibernating = True 
        self.game_process = "nightreign.exe"
        
        # Buffering Logic State
        self.trigger_buffer = [] # List of (timestamp, trigger_type)
        self.buffer_window = 2.5 # Seconds to keep history
        self.triggered_recently = False 
        
        # Fast Mode State
        self.fast_mode_active = False
        self.fast_mode_end_time = 0
        self.last_beep_time = 0
        self.last_fast_mode_trigger = 0  # Timestamp du dernier trigger de fast mode
        self.last_jour_detection = 0  # Timestamp de la dernière détection de "JOUR"
        
        # Pattern Manager
        self.pattern_manager = PatternManager()
        
        # Last detected raw text for feedback
        self.last_raw_text = ""
        self.current_matched_pattern = "" 
        
        # Day 3 State Machine
        self.day3_seq_step = 0 
        self.black_screen_start = 0
        self.in_black_screen = False
        
        # Victory detection state
        self.victory_check_active = False
        self.last_victory_check = 0
        self.victory_check_interval = 0.5  # Check every 0.5 seconds when in boss phase 

        if args.config:
            self.setup_ui()
        else:
            self.setup_service()

        # Keyboard Hooks
        if keyboard:
            try:
                # AZERTY Keys: & (1), é (2), ( (5)
                # We use the character names directly
                keyboard.add_hotkey('&', lambda: self.handle_manual_feedback("DAY 1"))
                keyboard.add_hotkey('é', lambda: self.handle_manual_feedback("DAY 2"))
                keyboard.add_hotkey('"', lambda: self.handle_manual_feedback("DAY 3"))
                keyboard.add_hotkey('(', self.handle_false_positive)
                print("Global hotkeys '&', 'é', '\"', '(' registered.")
            except Exception as e:
                print(f"Failed to register hotkeys: {e}")

    def setup_ui(self):
        self.root.title("Nightreign Timer Controller")
        self.root.geometry("300x150")
        
        tk.Button(self.root, text="Select Region", command=self.select_region).pack(pady=10)
        tk.Button(self.root, text="Start Overlay", command=self.start_overlay).pack(pady=10)
        self.debug_var = tk.BooleanVar(value=self.config.get("debug_mode", False))
        self.save_images_var = tk.BooleanVar(value=self.config.get("save_debug_images", False))
        self.hdr_mode_var = tk.BooleanVar(value=self.config.get("hdr_mode", False))
        self.save_raw_samples_var = tk.BooleanVar(value=self.config.get("save_raw_samples", True))
        
        tk.Checkbutton(self.root, text="Debug Mode (Logs)", variable=self.debug_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="Save Debug Images", variable=self.save_images_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="HDR Mode (High Compatibility)", variable=self.hdr_mode_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="Collect Training Data (Raw)", variable=self.save_raw_samples_var, command=self.update_config).pack()

    def select_region(self):
        self.root.withdraw() # Hide main window
        RegionSelector(self.on_region_selected)

    def on_region_selected(self, region):
        self.config["monitor_region"] = region
        save_config(self.config)
        
        if self.vision:
            self.vision.update_region(region)
            
        self.root.deiconify() # Show main window again
        print(f"Region saved: {region}")

    def setup_service(self):
        self.root.withdraw() # Start hidden
        
        with open("monitor.log", "a") as f: f.write("Service started\n")
        self.check_process_loop()

    def check_process_loop(self):
        game_running = self.check_process(self.game_process)
        
        if game_running and self.is_hibernating:
            with open("monitor.log", "a") as f: f.write(f"[{time.ctime()}] Game detected. Waking up...\n")
            self.wake_up()
        elif not game_running and not self.is_hibernating:
             with open("monitor.log", "a") as f: f.write(f"[{time.ctime()}] Game lost. Hibernating...\n")
             self.hibernate()
            
        self.root.after(5000, self.check_process_loop)

    def check_process(self, process_name):
        try:
            cmd = 'tasklist'
            output = subprocess.check_output(cmd, shell=True).decode(errors='ignore')
            return process_name.lower() in output.lower()
        except Exception as e:
            with open("monitor.log", "a") as f: f.write(f"Process check failed: {e}\n")
            return False

    def wake_up(self):
        print("Elden Ring detected! Waking up...")
        self.is_hibernating = False
        if not self.overlay:
            self.start_overlay()
        else:
             self.overlay.show()
             if self.vision: self.vision.resume()

    def hibernate(self):
        print("Elden Ring closed. Hibernating...")
        self.is_hibernating = True
        if self.overlay:
            self.overlay.hide()
        if self.vision:
            self.vision.pause()

    def update_config(self):
        self.config["debug_mode"] = self.debug_var.get()
        self.config["save_debug_images"] = self.save_images_var.get()
        self.config["hdr_mode"] = self.hdr_mode_var.get()
        self.config["save_raw_samples"] = self.save_raw_samples_var.get()
        save_config(self.config)
        
        if self.vision:
             self.vision.update_config(self.config)
             
        print(f"Config Updated: Debug={self.config['debug_mode']}, SaveImages={self.config['save_debug_images']}, HDR={self.config['hdr_mode']}")

    def start_overlay(self):
        if self.root.state() == "normal":
             self.root.withdraw()
        
        overlay_window = tk.Toplevel(self.root)
        self.overlay = Overlay(overlay_window)
        
        self.vision = VisionEngine(self.config)
        self.vision.start_monitoring(self.on_ocr_result)
        
        overlay_window.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_ocr_result(self, text, width, offset, word_data, brightness=0):
        self.root.after(0, self.process_ocr_trigger, text, width, offset, word_data, brightness)

    def process_ocr_trigger(self, text, width, offset, word_data, brightness=0):
        now = time.time()
        self.last_raw_text = text # Store for manual feedback
        
        # 1. Clean Buffer (Handles [timestamp, trigger_type, score])
        self.trigger_buffer = [item for item in self.trigger_buffer if now - item[0] <= self.buffer_window]
        
        detected_trigger = None
        
        # Vérifier la désactivation du fast mode même sans texte (pour réactivité)
        if self.fast_mode_active:
            time_since_last_jour = now - self.last_jour_detection if self.last_jour_detection > 0 else float('inf')
            time_since_last_trigger = now - self.last_fast_mode_trigger
            
            # Si on n'a pas détecté "JOUR" depuis plus de 3 secondes, désactiver immédiatement
            if time_since_last_jour > 3.0:
                print("DEBUG: Disabling Fast Mode (no JOUR detected for 3s)")
                self.fast_mode_active = False
                self.vision.set_scan_delay(0.08)
            # Sinon, vérifier le timeout normal
            elif now > self.fast_mode_end_time and time_since_last_trigger > 2.0:
                print("DEBUG: Disabling Fast Mode (timeout)")
                self.fast_mode_active = False
                self.vision.set_scan_delay(0.08)
        
        if text:
            normalized = text.strip().upper()
            
            # --- Fast Mode & Audio Warning Logic ---
            # Activer le fast mode dès qu'on détecte des indices précurseurs de "jour"
            # pour augmenter le nombre de captures et améliorer la détection
            
            should_fast_mode = False
            
            # 1. Vérifier si "JOUR" est présent dans le texte normalisé
            if "JOUR" in normalized:
                should_fast_mode = True
                self.last_jour_detection = now  # Mettre à jour la dernière détection de JOUR
            
            # 2. Vérifier dans les mots détectés (word_data) si un mot contient "JOUR"
            if not should_fast_mode and word_data:
                for w in word_data:
                    word_text = w.get("text", "").upper()
                    if "JOUR" in word_text:
                        should_fast_mode = True
                        self.last_jour_detection = now  # Mettre à jour la dernière détection de JOUR
                        break
            
            # 3. Vérifier les variantes partielles de "JOUR" dans le texte normalisé
            if not should_fast_mode:
                # Only trigger on 3+ chars to avoid noise like "JO" in random garbage
                # "JOU", "OUR" are safer. "UR" is risky.
                fast_triggers = ["JOU", "OUR"] 
                if any(x in normalized for x in fast_triggers):
                    should_fast_mode = True
            
            # 4. Vérifier si le texte correspond à un pattern connu contenant "JOUR"
            if not should_fast_mode:
                if len(normalized) >= 3:
                     for pat in self.pattern_manager.patterns.keys():
                         if "JOUR" in pat.upper() or normalized in pat:
                             should_fast_mode = True
                             break
            
            # 5. Détection précoce : lettres isolées "J", "O", "U" dans un contexte approprié
            # (largeur de texte suggérant un banner, position centrée)
            if not should_fast_mode and len(normalized) >= 1:
                # Si on détecte "J", "O", ou "U" isolé avec une largeur importante (suggère un banner)
                if width > 800:  # Les banners "JOUR" ont généralement une largeur importante
                    if normalized in ["J", "O", "U", "I", "II", "III"]:
                        should_fast_mode = True

            if should_fast_mode:
                 if self.overlay: self.overlay.show_recording(True)
                 self.last_fast_mode_trigger = now  # Mettre à jour le timestamp du dernier trigger
                 
                 if not self.fast_mode_active:
                     print("DEBUG: Enabling Fast Mode (20 FPS)")
                     self.fast_mode_active = True
                     self.vision.set_scan_delay(0.05)
                     
                     # Beep (Warning)
                     if now - self.last_beep_time > 2.0: # Rate limit beeps
                         try:
                             winsound.MessageBeep(winsound.MB_ICONWARNING)
                         except: pass
                         self.last_beep_time = now
                  
                 # Étendre la durée du fast mode à 10 secondes et le maintenir actif
                 self.fast_mode_end_time = now + 10.0
            
            # --- Pattern Matching ---
            # 1. EVALUATE using PatternManager with Granular Geometry
            target_day, score = self.pattern_manager.evaluate(normalized, text_width=width, center_offset=offset, word_data=word_data)
            
            if target_day and score >= 65:
                detected_trigger = target_day
                self.current_matched_pattern = normalized
                if self.config.get("debug_mode"):
                    print(f"Match: {normalized} -> {target_day} (Score: {score:.1f}, w={width}, off={offset:.1f})")
                
                # Maintenir le fast mode actif quand on détecte un trigger
                if not self.fast_mode_active:
                    print("DEBUG: Enabling Fast Mode (trigger detected)")
                    self.fast_mode_active = True
                    self.vision.set_scan_delay(0.05)
                self.last_fast_mode_trigger = now
                # Prolonger davantage pour DAY 3 (banner plus long)
                if detected_trigger == "DAY 3":
                    self.fast_mode_end_time = now + 15.0  # 15 secondes pour DAY 3
                    self.last_jour_detection = now  # Mettre à jour aussi pour éviter désactivation prématurée
                else:
                    self.fast_mode_end_time = now + 10.0

        if detected_trigger:
            self.trigger_buffer.append((now, detected_trigger, score))
        
        # --- Buffer Analysis ---
        if not self.trigger_buffer and not self.fast_mode_active:
            # Allow pass-through if we are in Day 3 - Preparation (Index 10) to check for black screens
            if not (self.overlay and self.overlay.current_phase_index == 10):
                if self.overlay: self.overlay.show_recording(False)
                return

        # Show recording icon if we have something in buffer OR fast mode is active
        if self.overlay: self.overlay.show_recording(True)

        # --- Score-Weighted Temporal Clustering Decision ---
        day_scores = {"DAY 1": 0.0, "DAY 2": 0.0, "DAY 3": 0.0}
        day_counts = {"DAY 1": 0, "DAY 2": 0, "DAY 3": 0}
        
        for item in self.trigger_buffer:
            if len(item) == 3:
                t, val, s = item
                day_scores[val] += s
                day_counts[val] += 1
        
        final_decision = None
        
        # Day 3 / Day 2 / Day 1 Priority with strict requirements
        # DAY 3 : 2 détections suffisent (le banner est plus long donc moins de captures)
        if day_counts["DAY 3"] >= 2 and day_scores["DAY 3"] > 100:
            final_decision = "DAY 3"
        elif day_counts["DAY 2"] >= 2 and day_scores["DAY 2"] > 180:
            final_decision = "DAY 2"
        elif day_counts["DAY 1"] >= 2 and day_scores["DAY 1"] > day_scores["DAY 3"]:
            final_decision = "DAY 1"
        
        if final_decision and not self.triggered_recently:
             print(f"DEBUG: TEMPORAL CONSENSUS -> {final_decision}")
             if self.overlay:
                if final_decision == "DAY 1": self.overlay.trigger_day_1()
                elif final_decision == "DAY 2": self.overlay.trigger_day_2()
                elif final_decision == "DAY 3": self.overlay.trigger_day_3()
             
             self.trigger_buffer = [] 
             self.triggered_recently = True
             self.root.after(4000, lambda: setattr(self, 'triggered_recently', False))

        # --- Day 3 Black Screen Sequence Logic ---
        if self.overlay:
             if self.overlay and self.overlay.current_phase_index == 10:
                # We are in Day 3 - Preparation
                # Looking for:
                # 1. Black Screen (~0.5s)
                # 2. Gap (Game/Loading)
                # 3. Black Screen (~1.0s) -> TRIGGER
                
                is_black = (brightness < 15)
                
                if is_black:
                    if not self.in_black_screen:
                        self.in_black_screen = True
                        self.black_screen_start = now
                        if self.config.get("debug_mode"):
                            print(f"DEBUG: Black Screen Started at {now}")
                else:
                    if self.in_black_screen:
                        # Black screen ended
                        duration = now - self.black_screen_start
                        self.in_black_screen = False
                        
                        if self.config.get("debug_mode"):
                            print(f"DEBUG: Black Screen Ended. Duration: {duration:.2f}s (Step: {self.day3_seq_step})")

                        # Step 1: Detect ~0.5s (Range 0.3 - 0.8)
                        if 0.3 <= duration <= 1.5: # Generous upper bound to catch the first one
                            if self.day3_seq_step == 0:
                                self.day3_seq_step = 1
                                if self.config.get("debug_mode"):
                                    print("DEBUG: Day 3 Sequence - Saw Screen 1")
                            elif self.day3_seq_step == 1:
                                pass
                                
                        # Step 2: Detect ~1.0s (Range > 0.8)
                        if duration >= 0.8:
                            if self.day3_seq_step == 1:
                                # This is likely the second screen
                                if self.config.get("debug_mode"):
                                    print("DEBUG: Day 3 Sequence - Saw Screen 2 (TRIGGER BOSS)")
                                self.overlay.trigger_final_boss()
                                self.day3_seq_step = 0
                            elif self.day3_seq_step == 0:
                                 pass
        
        # --- Victory Detection for Day 3 Final Boss (Phase 11) ---
        if self.overlay and self.overlay.current_phase_index == 11:
            # We are in Day 3 - Final Boss phase
            # Check for victory periodically
            if not self.victory_check_active:
                self.victory_check_active = True
                self.last_victory_check = now
                if self.config.get("debug_mode"):
                    print("DEBUG: Starting victory detection for Day 3 Final Boss")
                # Start periodic victory checks (async)
                self.root.after(int(self.victory_check_interval * 1000), self.check_victory_periodic)
        else:
            # Not in boss phase, stop victory checking
            if self.victory_check_active:
                self.victory_check_active = False
                if self.config.get("debug_mode"):
                    print("DEBUG: Stopping victory detection")

    def check_victory_periodic(self):
        """Periodically checks for victory text in the victory region."""
        if not self.vision or not self.victory_check_active:
            if self.config.get("debug_mode"):
                print("DEBUG Victory: check_victory_periodic called but vision=None or not active")
            return
        
        # Check if we're still in boss phase
        if not self.overlay or self.overlay.current_phase_index != 11:
            if self.config.get("debug_mode"):
                print(f"DEBUG Victory: Not in boss phase (phase_index={self.overlay.current_phase_index if self.overlay else 'None'})")
            self.victory_check_active = False
            return
        
        self.last_victory_check = time.time()
        
        # Check if victory region is configured
        if not self.config.get("victory_region"):
            if self.config.get("debug_mode"):
                print("DEBUG Victory: Victory region not configured, skipping victory check")
            # Schedule next check anyway
            self.root.after(int(self.victory_check_interval * 1000), self.check_victory_periodic)
            return
        
        if self.config.get("debug_mode"):
            print("DEBUG Victory: Starting victory scan...")
        
        # Scan victory region
        text, score = self.vision.scan_victory_region()
        
        if text and score >= 60:  # Lower threshold to match vision_engine
            # Victory detected!
            print(f"VICTORY DETECTED: '{text}' (Score: {score:.1f})")
            if self.overlay:
                self.overlay.stop_timer()
                # Play victory sound
                try:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except:
                    pass
            self.victory_check_active = False  # Stop checking after victory
        else:
            if self.config.get("debug_mode"):
                if text:
                    print(f"DEBUG Victory: Text found '{text}' but score {score:.1f} < 65")
                else:
                    print("DEBUG Victory: No text detected in victory region")
            # Schedule next check
            self.root.after(int(self.victory_check_interval * 1000), self.check_victory_periodic)

    def handle_manual_feedback(self, correct_target):
        """
        Called when user presses F5 or F6 (now & or é).
        scans ocr_log.txt for recent entries and teaches them as 'correct_target'.
        """
        print(f"Manual Feedback Received: {correct_target}")
        
        # 1. Trigger the action immediately for responsiveness
        if self.overlay and not self.triggered_recently:
            if correct_target == "DAY 1": self.overlay.trigger_day_1()
            elif correct_target == "DAY 2": self.overlay.trigger_day_2()
            elif correct_target == "DAY 3": self.overlay.trigger_day_3()
            self.triggered_recently = True
            self.root.after(5000, lambda: setattr(self, 'triggered_recently', False))

        # 2. Learn from history
        # We read the last ~20 lines of log
        try:
            if not os.path.exists("ocr_log.txt"): return
            
            with open("ocr_log.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()[-20:]
            
            # Filter lines from the last 5 seconds
            active_lines = []
            now = datetime.datetime.now()
            
            for line in lines:
                # format: [HH:MM:SS] TEXT
                try:
                    parts = line.split("] ", 1)
                    if len(parts) < 2: continue
                    ts_str = parts[0].strip("[")
                    text = parts[1].strip()
                    if not text: continue
                    
                    # Parsing time is tricky without date, assume today
                    line_time = datetime.datetime.strptime(ts_str, "%H:%M:%S").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                    
                    # Handle midnight crossover if needed (ignored for simplicity)
                    if (now - line_time).total_seconds() < 5:
                        active_lines.append(text)
                except: continue
                
            # Learn the most frequent non-empty text
            if active_lines:
                from collections import Counter
                # Exclude purely empty strings if any
                c = Counter(active_lines)
                most_common = c.most_common(1)
                if most_common:
                    text_to_learn = most_common[0][0]
                    print(f"Learning '{text_to_learn}' as {correct_target}")
                    self.pattern_manager.learn(text_to_learn, correct_target)
                    winsound.Beep(1000, 200) # Confirmation beep
                    
        except Exception as e:
            print(f"Error in manual feedback: {e}")

    def handle_false_positive(self):
        """
        Called when user presses F7 (now '(').
        Stops timer, learns to punish the text that triggered it.
        """
        print("Manual Feedback: False Positive")
        
        # 1. Stop/Reset Timer
        if self.overlay:
            # We assume we just want to go back to "Waiting"
            self.overlay.reset_timer()
        
        # 2. Punish
        target_to_punish = self.current_matched_pattern
        if target_to_punish:
             print(f"Punishing '{target_to_punish}'")
             self.pattern_manager.punish(target_to_punish)
             winsound.Beep(500, 500) # Sad beep

    def on_close(self):
        if self.vision:
            self.vision.stop()
        self.root.destroy()
        import sys
        sys.exit()

if __name__ == "__main__":
    app = App()
    app.root.mainloop()
