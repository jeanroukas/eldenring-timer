# NOTE: Always analyze and implement project tracking.md
import cv2
import numpy as np
import pytesseract
import bettercam
import time
import os
import threading
try:
    from windows_capture import WindowsCapture
except ImportError:
    WindowsCapture = None

import datetime
import json

import re
try:
    import xxhash
except ImportError:
    xxhash = None

try:
    import psutil
except ImportError:
    psutil = None

class VisionEngine:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.paused = False
        self.region = config.get("monitor_region", {})
        self.scan_delay = 0.08 # Default delay (réduit pour plus d'échantillons)
        
        self.camera = None
        self.wgc_instance = None
        self.wgc_control = None
        self.last_wgc_frame = None
        self.wgc_lock = threading.Lock()
        
        self._init_camera()

        # Configure Tesseract path
        tesseract_cmd = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if os.path.exists(tesseract_cmd):
             pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            print(f"Warning: Tesseract not found at {tesseract_cmd}. OCR may fail.")

        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if self.config.get("debug_mode"):
            os.makedirs(os.path.join(self.project_root, "debug_images"), exist_ok=True)
            
        # Ensure raw samples directory exists
        self.raw_samples_dir = os.path.join(self.project_root, "samples", "raw")
        os.makedirs(self.raw_samples_dir, exist_ok=True)
        self.last_raw_save_time = 0
        self.frame_count = 0

        # Precompile regex for cleaning text
        self.re_start = re.compile(r'[A-Z0-9].*[A-Z0-9]')
        self.re_single = re.compile(r'[A-Z0-9]')
        
        # Common OCR Misreadings Map
        self.CORRECTION_MAP = {
            "JOURIL": "JOUR II",
            "JOURTI": "JOUR II",
            "JOUBRII": "JOUR II",
            "JOBRIL": "JOUR II",
            "JOUBIIL": "JOUR II",
            "JOURTL": "JOUR II",
            "JOURTE": "JOUR II",
            "JOERII": "JOUR II",
            "JOUMT": "JOUR II",
            "JAURAL": "JOUR II", 
            "JOURIII": "JOUR III", # Sometimes OK, sometimes noisy
            "JOUR1": "JOUR I",
            "JOUR2": "JOUR II",
            "JOUR3": "JOUR III",
            "JOU": "JOUR I" # Aggressive fix for short capture?
        }

    def update_config(self, new_config):
        """Updates configuration and re-initializes engine if capture mode changed."""
        old_hdr = self.config.get("hdr_mode", False)
        self.config = new_config
        if self.config.get("hdr_mode", False) != old_hdr:
            print(f"Vision Engine: HDR Mode switched to {self.config.get('hdr_mode')}. Re-initializing...")
            self._init_camera()

    def get_monitors(self):
        """Returns a list of all monitors with their global coordinates."""
        try:
            import ctypes
            from ctypes import wintypes
            # Try to be DPI aware for correct coordinates
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except:
                ctypes.windll.user32.SetProcessDPIAware()

            screens = []
            def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                rect = lprcMonitor.contents
                screens.append({
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top
                })
                return True

            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
            ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_proc), 0)
            return screens
        except Exception as e:
            print(f"Vision Engine: Failed to get monitors: {e}")
            return []

    def _init_camera(self):
        """Initializes or re-initializes BetterCam with current region and correct monitor."""
        try:
            if self.camera:
                try: self.camera.stop()
                except: pass
                self.camera = None
            
            if self.wgc_control:
                try: self.wgc_control.stop()
                except: pass
                self.wgc_control = None
                self.wgc_instance = None
            
            region = self.config.get("monitor_region", {})
            if not region:
                self.camera = None
                return

            if self.config.get("hdr_mode"):
                if not WindowsCapture:
                    print("Vision Engine: windows-capture library missing. HDR mode unavailable.")
                    return
                
                # 1. Find monitor index for WGC
                monitors = self.get_monitors()
                global_left = region.get('left', 0)
                global_top = region.get('top', 0)
                
                monit_idx = 0
                for i, m in enumerate(monitors):
                    if (m['left'] <= global_left < m['right']) and (m['top'] <= global_top < m['bottom']):
                        monit_idx = i
                        break
                
                # WGC monitor_index is 1-based
                wgc_idx = monit_idx + 1
                
                print(f"Vision Engine: Using WGC (HDR Mode) on Monitor {wgc_idx}")
                
                self.wgc_instance = WindowsCapture(monitor_index=wgc_idx)
                
                @self.wgc_instance.event
                def on_frame_arrived(frame, control):
                    with self.wgc_lock:
                        # frame.frame_buffer is the numpy array (BGRA)
                        self.last_wgc_frame = frame.frame_buffer.copy()

                @self.wgc_instance.event
                def on_closed():
                    print("Vision Engine: WGC Capture closed.")

                self.wgc_control = self.wgc_instance.start_free_threaded()
                return

            # 1. Find which monitor this region (top-left) belongs to
            monit_idx = 0
            monitors = self.get_monitors()
            
            global_left = region.get('left', 0)
            global_top = region.get('top', 0)
            
            found_monitor = None
            for i, m in enumerate(monitors):
                if (m['left'] <= global_left < m['right']) and (m['top'] <= global_top < m['bottom']):
                    monit_idx = i
                    found_monitor = m
                    break
            
            if not found_monitor:
                print(f"Vision Engine: Could not find monitor for region at ({global_left}, {global_top}). Defaulting to 0.")
                found_monitor = monitors[0] if monitors else {"left": 0, "top": 0}

            # 2. Convert GLOBAL coordinates to LOCAL monitor coordinates
            # mss used global, bettercam uses local to the specific output.
            local_left = global_left - found_monitor['left']
            local_top = global_top - found_monitor['top']
            local_right = local_left + region.get('width', 100)
            local_bottom = local_top + region.get('height', 100)
            
            # 3. Initialize BetterCam on the specific monitor (output_idx)
            # BetterCam output_idx matches EnumDisplayMonitors order usually
            self.camera = bettercam.create(device_idx=0, output_idx=monit_idx, region=(local_left, local_top, local_right, local_bottom))
            print(f"Vision Engine: BetterCam initialized on Monitor {monit_idx} at local region ({local_left}, {local_top}, {local_right}, {local_bottom})")
            
        except Exception as e:
            print(f"Vision Engine: Failed to initialize BetterCam: {e}")
            self.camera = None

    def set_scan_delay(self, delay):
        self.scan_delay = delay

    def update_region(self, region):
        """Updates the capture region and re-initializes the camera."""
        self.region = region
        self.config["monitor_region"] = region
        self._init_camera()

    def set_region_override(self, region):
        """Sets a temporary override region for scanning (e.g. for Victory check). Pass None to clear."""
        self.region_override = region

    def scan_victory_region(self):
        """
        Scans the victory region specifically for "résultat" detection.
        Returns (text, score) or (None, 0) if nothing detected.
        Uses otsu preprocessing as determined by testing.
        """
        victory_region = self.config.get("victory_region")
        if not victory_region:
            if self.config.get("debug_mode"):
                print("DEBUG Victory: victory_region not configured")
            return None, 0
        
        if self.config.get("debug_mode"):
            print(f"DEBUG Victory: Scanning region {victory_region}")
        
        # Temporarily override region
        old_override = getattr(self, 'region_override', None)
        self.region_override = victory_region
        
        try:
            img = self.capture_screen()
            if img is None:
                if self.config.get("debug_mode"):
                    print("DEBUG Victory: Failed to capture image")
                return None, 0
            
            if self.config.get("debug_mode"):
                print(f"DEBUG Victory: Image captured: {img.shape[1]}x{img.shape[0]}")
            
            # Use otsu preprocessing (determined to be the best)
            processed = self.preprocess_image(img, pass_type="otsu")
            if processed is None:
                if self.config.get("debug_mode"):
                    print("DEBUG Victory: Failed to preprocess image")
                return None, 0
            
            # OCR with PSM 7 (single text line)
            data = pytesseract.image_to_data(processed, config='--psm 7', output_type=pytesseract.Output.DICT)
            
            valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
            raw_text = " ".join([data['text'][i] for i in valid_indices]).strip()
            text = self.clean_text(raw_text)
            
            if self.config.get("debug_mode"):
                print(f"DEBUG Victory: OCR raw='{raw_text}', cleaned='{text}'")
            
            if text:
                # Check if it matches VICTORY pattern
                # Normalize: remove accents and convert to uppercase
                normalized = text.strip().upper()
                # Remove accents for matching (é -> E, à -> A, etc.)
                import unicodedata
                normalized_no_accents = ''.join(c for c in unicodedata.normalize('NFD', normalized) 
                                                if unicodedata.category(c) != 'Mn')
                
                if self.config.get("debug_mode"):
                    print(f"DEBUG Victory: normalized='{normalized}', no_accents='{normalized_no_accents}'")
                
                # Victory patterns (without accents)
                victory_patterns_base = ["RESULTAT", "RESULTIT", "RESULT", "RECOMPE"]
                
                # Always use fuzzy matching (more reliable)
                from fuzzywuzzy import fuzz
                best_score = 0
                best_pattern = None
                for pattern in victory_patterns_base:
                    score = fuzz.ratio(normalized_no_accents, pattern)
                    if score > best_score:
                        best_score = score
                        best_pattern = pattern
                
                if self.config.get("debug_mode"):
                    print(f"DEBUG Victory: Best fuzzy match '{best_pattern}' score={best_score:.1f} (normalized='{normalized_no_accents}')")
                
                # Lower threshold for victory detection (60 instead of 65)
                # because "RÉSULTAT" vs "RESULTAT" should match (score=100)
                if best_score >= 60:
                    if self.config.get("debug_mode"):
                        print(f"VICTORY detected (fuzzy): '{text}' (Score: {best_score:.1f})")
                    return text, best_score
                else:
                    if self.config.get("debug_mode"):
                        print(f"DEBUG Victory: Best fuzzy score {best_score:.1f} < 60, not enough")
            
            if self.config.get("debug_mode"):
                print("DEBUG Victory: No victory pattern detected")
            return None, 0
        finally:
            # Restore old override
            self.region_override = old_override

    def start_monitoring(self, callback):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, args=(callback,))
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.camera:
            try: self.camera.stop()
            except: pass
        if self.wgc_control:
            try: self.wgc_control.stop()
            except: pass

    def pause(self):
        self.paused = True
        print("Vision Engine: Paused")

    def resume(self):
        self.paused = False
        print("Vision Engine: Resumed")
        
    def capture_screen(self):
        """Captures the current region using the active engine."""
        try:
            # Check for override, otherwise use config region
            reg = getattr(self, 'region_override', None)
            if not reg:
                reg = self.config.get("monitor_region", {})
            
            if not reg: return None

            if self.config.get("hdr_mode"):
                # Use WGC frame buffer
                with self.wgc_lock:
                    if self.last_wgc_frame is None: return None
                    full_frame = self.last_wgc_frame.copy()
                
                # Find monitor relative coordinates to crop
                monitors = self.get_monitors()
                global_left = reg.get('left', 0)
                global_top = reg.get('top', 0)
                
                found_monitor = None
                for m in monitors:
                    if (m['left'] <= global_left < m['right']) and (m['top'] <= global_top < m['bottom']):
                        found_monitor = m
                        break
                
                if not found_monitor:
                    found_monitor = monitors[0] if monitors else {"left":0, "top":0}

                # Local coordinates for crop
                lx = global_left - found_monitor['left']
                ly = global_top - found_monitor['top']
                lw = reg.get('width', 100)
                lh = reg.get('height', 100)
                
                # Crop BGRA and convert to BGR (with safety bounds)
                fh, fw = full_frame.shape[:2]
                ly_end = min(max(0, ly + lh), fh)
                lx_end = min(max(0, lx + lw), fw)
                ly_start = min(max(0, ly), fh)
                lx_start = min(max(0, lx), fw)
                
                cropped = full_frame[ly_start:ly_end, lx_start:lx_end]
                
                if cropped.size == 0:
                    return None
                    
                return cv2.cvtColor(cropped, cv2.COLOR_BGRA2BGR)
            
            if self.camera:
                # Check if we need to re-init camera for new region (Only if region changed and we are not in HDR/WGC mode)
                # This causes a slight lag frame but is necessary for BetterCam dynamic region
                current_cam_region = getattr(self, 'current_cam_region', None)
                if current_cam_region != reg:
                     print(f"Vision Engine: Switching BetterCam region to {reg}")
                     self.region = reg # Update internal tracking
                     # We need to re-init BetterCam with this new region.
                     # But we can't call _init_camera directly easily as it uses self.config.
                     # Let's temporarily patch self.config["monitor_region"] for _init_camera or modify _init_camera to accept arg.
                     # Modifying _init_camera is cleaner but requires looking at lines 85+.
                     # For now, let's just hack it:
                     old_conf_reg = self.config.get("monitor_region")
                     self.config["monitor_region"] = reg
                     self._init_camera()
                     self.config["monitor_region"] = old_conf_reg # Restore
                     self.current_cam_region = reg

                frame = self.camera.grab()
                if frame is not None:
                    # bettercam returns RGB, OpenCV usually wants BGR
                    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return None
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def adjust_gamma(self, image, gamma=1.0):
        if gamma == 1.0: return image
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)

    def preprocess_image(self, img, pass_type="otsu", custom_val=0, scale=1.0):
        if img is None: return None
        
        # Dynamic Scaling
        h, w = img.shape[:2]
        # Target height based on analysis (Scale 1.5x of original usually optimal)
        # But here we use explicit scale if provided
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Convert to gray
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Gamma (Fixed 1.0 generally fine, analysis showed 0.8-1.2 var)
        # Lets keep it simple or param? Analysis said 1.0 or 0.8. 
        # We'll stick to 1.0 for now unless dynamic requires it
        gamma = 1.0
        if gamma != 1.0:
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
            gray = cv2.LUT(gray, table)

        if pass_type == "otsu":
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        elif pass_type == "fixed" or pass_type == "dynamic":
            # Use provided value or default
            val = custom_val if custom_val > 0 else 230
            _, thresh = cv2.threshold(gray, val, 255, cv2.THRESH_BINARY_INV)
        elif pass_type == "adaptive":
             # Adaptive Gaussian
             thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY_INV, 25, 2)
        elif pass_type == "inverted":
             # Invert image first, then Otsu
             gray = cv2.bitwise_not(gray)
             _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Morphological Closing
        kernel = np.ones((2,2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return thresh

    def is_relevant(self, text):
        """Checks if text is relevant for saving (avoids saving 'OT', 'K', 'S' etc)."""
        if not text: return False
        t = text.upper()
        
        # Valid short tokens (Day numbers, etc)
        valid_short = ["1", "2", "3", "I", "II", "III", "IV", "V"] 
        if len(t) < 3 and t not in valid_short:
            return False

        # Must contain at least one characteristic letter or be a valid day indicator
        # "J" (Jour), "O" (Jour/One), "U" (Jour), "R" (Jour), "I" (1/2/3), "V" (Victory)
        relevant_chars = ["J", "O", "U", "I", "1", "2", "3", "V", "F"] 
        
        # Check for banned signals explicitly
        if t in ["OT", "S", "K", "SS", "OT."]: return False

        if any(c in t for c in relevant_chars):
            return True
        return False
        
    def clean_text(self, text):
        """
        Strips non-alphanumeric characters from the START and END of the text.
        Preserves internal spaces and letters (e.g., "~ JOUR I," -> "JOUR I").
        """
        if not text: return ""
        # Regex to find the first and last alphanumeric character
        match = self.re_start.search(text.upper())
        if match:
            return match.group(0)
        # If no internal match, try single alphanumeric
        match = self.re_single.search(text.upper())
        if match:
            return match.group(0)
        return ""

    def _loop(self, callback):
        print(f"Vision Engine: Monitoring started with 2-Pass Strategy (optimized). Debug Mode: {self.config.get('debug_mode')}")
        
        while self.running:
            try:
                if self.paused:
                    time.sleep(1)
                    continue

                self.frame_count += 1
                loop_start = time.perf_counter()
                
                img = self.capture_screen()
                if img is None:
                    time.sleep(0.1)
                    continue
                
                brightness = 0
                if img is not None:
                     brightness = np.mean(img)

                # Dynamic OCR Logic
                # Derived from Phase 2 Analysis: Threshold = 230 + (Brightness * 0.1)
                # Scale 1.5x was consistently best.
                
                # Calculate optimal threshold
                target_thresh = 230 + (brightness * 0.1)
                target_thresh = min(254, max(200, int(target_thresh))) # Clamp to valid range
                
                # We will try the calculated Optimal first, then fallbacks for edge cases
                # Strategy:
                # 1. Dynamic Fixed: Fast, 85% success rate.
                # 2. Adaptive: Slower, handles extreme brightness gradients.
                # 3. Inverted: Handles rare bloom/inversion cases.
                passes = [
                    {"type": "dynamic", "val": target_thresh, "scale": 1.5},
                    {"type": "adaptive", "val": 0, "scale": 1.5},
                    {"type": "inverted", "val": 0, "scale": 1.5} 
                ]
                
                best_text = ""
                best_width = 0
                best_center_offset = 0
                best_word_data = []
                best_pass = "none"
                
                # Run passes
                for p_config in passes:
                    processed = self.preprocess_image(img, pass_type=p_config["type"], 
                                                      custom_val=p_config["val"], 
                                                      scale=p_config["scale"])
                    if processed is None: continue

                    custom_config = r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7'
                    
                    try:
                        data = pytesseract.image_to_data(processed, config=custom_config, output_type=pytesseract.Output.DICT)
                    except: continue
                    
                    # Calculate Confidence Score
                    conf_list = [int(c) for c in data['conf'] if c != -1]
                    avg_conf = np.mean(conf_list) if conf_list else 0
                    
                    # Quality Filter: Reject very low confidence (<40)
                    if avg_conf < 40 and p_config["type"] == "dynamic":
                         continue

                    valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
                    raw_text = " ".join([data['text'][i] for i in valid_indices]).strip()
                    text = self.clean_text(raw_text)
                    
                    # Apply corrections immediately
                    text = self.CORRECTION_MAP.get(text, text)
                    
                    if text:
                        # Heuristic: Prefer High Confidence > Longer Text
                        # Previous logic favored length, but confidence is key now
                        if avg_conf > (getattr(self, 'best_conf', 0) + 10) or (len(text) > len(best_text) and avg_conf > 50):
                            self.best_conf = avg_conf # Store for next comparison
                            best_text = text
                            best_pass = p_config["type"]
                            
                            # Geometry calculation
                            if valid_indices:
                                left = min([data['left'][i] for i in valid_indices])
                                right = max([data['left'][i] + data['width'][i] for i in valid_indices])
                                best_width = right - left
                                best_center_offset = abs((left + best_width / 2) - (processed.shape[1] / 2))
                                
                                best_word_data = []
                                for i in valid_indices:
                                     best_word_data.append({
                                         "text": data['text'][i].upper(),
                                         "left": data['left'][i],
                                         "width": data['width'][i],
                                         "conf": data['conf'][i]
                                     })
                                
                                text_center = left + (best_width / 2)
                                img_center = processed.shape[1] / 2
                                best_center_offset = abs(text_center - img_center)
                        
                        # Early Exit: If we found a very high confidence result (>85), 
                        # stop trying other passes to save CPU and latency.
                        if getattr(self, 'best_conf', 0) > 85:
                            break

                # Save RAW samples + Metadata on Detection
                should_save = False
                is_panic_save = False
                
                # 1. Normal Relevant Text
                if best_text and self.is_relevant(best_text):
                    should_save = True
                
                # 2. Bias Fix: High Brightness (>240) - likely burned, missed by OCR
                # Save these to collect "hard" samples
                if brightness > 240:
                    should_save = True
                    if not best_text: is_panic_save = True

                # 3. Bias Fix: Random Background (1% chance) - capture true negatives
                import random
                if random.random() < 0.01:
                    should_save = True
                    if not best_text: is_panic_save = True

                if should_save and self.config.get("save_raw_samples", True):
                    # Ratelimit: Max 2 per second to avoid flooding
                    now = time.time()
                    if (now - self.last_raw_save_time > 0.5):
                        self.last_raw_save_time = now
                        try:
                            # Sanitize text for filename
                            if best_text:
                                safe_text = "".join(c for c in best_text if c.isalnum())
                            else:
                                safe_text = "NO_TEXT"
                            
                            # Prefix panic saves for easy ID
                            if is_panic_save:
                                safe_text = "PANIC_" + safe_text

                            ts_full = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
                            
                            # Filename: raw_TIMESTAMP_TEXT_bBRIGHTNESS.png
                            base_name = f"raw_{ts_full}_{safe_text}_b{int(brightness)}"
                            raw_filename = f"{base_name}.png"
                            json_filename = f"{base_name}.json"
                            
                            raw_path = os.path.join(self.raw_samples_dir, raw_filename)
                            json_path = os.path.join(self.raw_samples_dir, json_filename)
                            
                            # Save Image
                            cv2.imwrite(raw_path, img)
                            
                            # Calculate Inference Time
                            inference_time_ms = (time.perf_counter() - loop_start) * 1000
                            
                            # Calculate Image Hash (for deduplication)
                            img_hash = ""
                            if xxhash is not None:
                                img_hash = xxhash.xxh64(img).hexdigest()
                            
                            # Get System Stats (CPU/RAM)
                            sys_stats = {"cpu": None, "ram": None}
                            if psutil is not None:
                                try:
                                    # CPU percent (non-blocking)
                                    sys_stats["cpu"] = psutil.cpu_percent(interval=None)
                                    sys_stats["ram"] = psutil.virtual_memory().percent
                                except: pass

                            # Save Metadata
                            metadata = {
                                "timestamp": ts_full,
                                "detected_text": best_text,
                                "safe_text": safe_text,
                                "brightness": brightness,
                                "image_width": img.shape[1],
                                "image_height": img.shape[0],
                                "image_hash": img_hash,
                                "inference_time_ms": round(inference_time_ms, 2),
                                "system_stats": sys_stats,
                                "ocr_pass_used": best_pass,
                                "ocr_width": best_width,
                                "ocr_center_offset": best_center_offset,
                                "word_data": best_word_data,
                                "config_region": self.region,
                                "passes_attempted": passes,
                                "verification": {
                                    "is_correct": None, # Placeholder for manual labeling
                                    "actual_text": None,
                                    "comments": None
                                }
                            }
                            
                            with open(json_path, "w", encoding="utf-8") as f:
                                json.dump(metadata, f, indent=2)
                                
                        except Exception as e:
                            print(f"Failed to save raw sample/metadata: {e}")

                if self.config.get("debug_mode"):
                    if best_text:
                         # Log result
                         ts = datetime.datetime.now().strftime("%H:%M:%S")
                         log_msg = f"[{ts}] OCR: '{best_text}' (Filter: {self.is_relevant(best_text)}, Save: {self.config.get('save_raw_samples')}) Br:{brightness:.1f}\n"
                         print(log_msg.strip())
                         try:
                             with open(os.path.join(self.project_root, "ocr_log.txt"), "a", encoding='utf-8') as f:
                                 f.write(log_msg)
                         except: pass
                    elif self.frame_count % 50 == 0:
                         # Heartbeat
                         print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Heartbeat - Brightness: {brightness:.1f}")
                
                # Callback now expects (text, width, center_offset, word_data, brightness)
                callback(best_text, best_width, best_center_offset, best_word_data, brightness)
                
                # Dynamic Delay
                elapsed = time.perf_counter() - loop_start
                remaining_delay = max(0, self.scan_delay - elapsed)
                time.sleep(remaining_delay if remaining_delay > 0 else 0.001)

            except Exception as e:
                print(f"Vision error: {e}")
                time.sleep(1)
