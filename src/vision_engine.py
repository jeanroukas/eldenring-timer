# NOTE: Always analyze and implement project tracking.md
import cv2
import numpy as np
import pytesseract
import time
import os
import threading
import unicodedata
from fuzzywuzzy import fuzz
import ctypes
from ctypes import wintypes
from enum import IntEnum

import datetime
import json
import bettercam
import mss
import mss.tools
from PIL import Image
import re
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from src.utils.tesseract_api import TesseractAPI
from src.logger import logger

import re
try:
    import xxhash
except ImportError:
    xxhash = None

try:
    import psutil
except ImportError:
    psutil = None

class OCRPass(IntEnum):
    OTSU = 0
    ADAPTIVE = 1
    INVERTED = 2
    FIXED = 3

class VisionEngine:
    # Optimized String Constants
    VALID_SHORT = frozenset(["1", "2", "3", "I", "II", "III", "IV", "V"])
    RELEVANT_CHARS = frozenset(["J", "O", "U", "I", "1", "2", "3", "V", "F"])
    BANNED_SIGNALS = frozenset(["OT", "S", "K", "SS", "OT."])

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debug_mode = config.get("debug_mode", False)
        self.running = False
        self.paused = False
        self.region = config.get("monitor_region", {})
        self.level_region = config.get("level_region", {})
        self.level_region = config.get("level_region", {})
        self.runes_region = config.get("runes_region", {})
        self.runes_icon_region = config.get("runes_icon_region", {})
        self.scan_delay = 0.2 # Default delay (Standard 5 FPS)
        
        self.last_raw_frame = None
        self.last_frame_timestamp = 0.0
        self.region_override = None
        self.secondary_running = False
        
        # Debug / Inspector State
        self.last_ocr_text = ""
        self.last_ocr_conf = 0.0
        self.last_brightness = 0.0
        self.suppress_ocr_until = 0
        self.consecutive_garbage_frames = 0
        self.is_low_power_mode = False

        # Adaptive FPS State
        self.last_activity_time = time.time()
        self.adaptive_fps_enabled = True
        self.base_scan_delay = 0.033 # 30 FPS target
        self.power_save_delay = 0.2  # 5 FPS
        
        # Parallel OCR Pool
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.tess_pool_main = []
        
        # Initial parameter sync
        self.update_from_config()

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
            "JQURII": "JOUR II",
            "JQUR II": "JOUR II",
            "JQURIH": "JOUR II",
            "JOUR IT": "JOUR II",
            "JOURII": "JOUR II",
            "JOUR I I": "JOUR II",
            "JOURITI": "JOUR II",
            "JQU_RII": "JOUR II",
            "JOURIII": "JOUR III",
            "JQURIII": "JOUR III",
            "JOUR1": "JOUR I",
            "JOUR2": "JOUR II",
            "JOUR3": "JOUR III",
            "JQUR I": "JOUR I",
            "JOUR I T": "JOUR I",
            "J OURIT": "JOUR I"
        }
        
        # Performance Tracking / Fast Mode
        self.last_successful_pass = None
        
        # Smart Filter Stats
        self.total_scans = 0
        self.skipped_scans = 0
        
        # High Performance Tesseract API (DLL)
        self.tess_api_main = None      # For Day Detection (A-Z, 0-9)
        self.tess_api_secondary = None # For Stats (0-9 ONLY) - Very Fast
        self._init_tess_api()

        # Define OCR passes configuration
        self.ocr_passes = {
            "standard": [
                # Pass 1: Gamma 0.6 + Otsu (Robust for general lighting)
                {"type": OCRPass.OTSU, "val": 0, "scale": 1.0, "gamma": 0.6},
                # Pass 2: Gamma 0.6 + Fixed 220 (Optimized for bright text)
                {"type": OCRPass.FIXED, "val": 220, "scale": 1.0, "gamma": 0.6},
                # Pass 3: Inverted (Fallback for black-on-white glitching)
                {"type": OCRPass.INVERTED, "val": 0, "scale": 1.0, "gamma": 0.6}
            ],
            "aggressive": [
                {"type": OCRPass.OTSU, "val": 0, "scale": 1.5, "gamma": 0.6},
                {"type": OCRPass.ADAPTIVE, "val": 0, "scale": 1.5, "gamma": 0.6},
                {"type": OCRPass.FIXED, "val": 200, "scale": 1.5, "gamma": 0.6}
            ]
        }
        
        # Thread Safety Lock for Fallback Pytesseract ONLY
        # (Tesseract DLL instances are now thread-local/safe by design)
        self.ocr_lock = threading.Lock()
        
        # Cooldown / Optimization Logic
        self.suppress_ocr_until = 0  # Timestamp to resume OCR
        self.consecutive_garbage_frames = 0
        self.is_low_power_mode = False
        
        # Thread-local storage for camera instances
        self._thread_local = threading.local()
        
        # Pre-calculate Gamma Table for 0.6 (Used in Levels/Runes)
        self.gamma_table_06 = self._build_gamma_table(0.6)
        self._gamma_cache = {0.6: self.gamma_table_06, 1.0: None}

        # Icon Matching
        self.icon_template = None
        self._load_icon_template()

        # Char Select Matching
        self.char_template = None
        self.char_callback = None
        self._load_char_template()

    def _load_char_template(self):
        try:
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "templates", "char_select_template.png")
            if os.path.exists(template_path):
                self.char_template = cv2.imread(template_path, cv2.IMREAD_COLOR) # Color matching for menu?
                if self.char_template is None:
                     # Fallback to grayscale if color failed or intended
                     self.char_template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                
                if self.config.get("debug_mode"):
                    print(f"VISION: Loaded Character Template from {template_path}")
            else:
                if self.config.get("debug_mode"):
                    print(f"VISION: Character Template not found at {template_path}. Char detection disabled.")
        except Exception as e:
            print(f"Error loading char template: {e}")


    def _load_icon_template(self):
        try:
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "rune_icon_template.png")
            if os.path.exists(template_path):
                self.icon_template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                if self.config.get("debug_mode"):
                    print(f"VISION: Loaded Rune Icon Template from {template_path}")
            else:
                if self.config.get("debug_mode"):
                    print("VISION: Rune Icon Template not found. Icon detection disabled.")
        except Exception as e:
            print(f"Error loading icon template: {e}")

    def detect_rune_icon(self, img_bgr):
        """
        Checks if the Rune Icon is present in the "runes_icon_region".
        Returns (True/False, confidence).
        """
        if self.icon_template is None:
            return True, 1.0 # Default to True if no template (don't block)
        
        reg = self.runes_icon_region
        if not reg or reg.get("width", 0) == 0:
            return True, 1.0 # No region defined

        # Extract Region
        mon = self.config.get("monitor_region", {})
        left = reg.get("left", 0) - mon.get("left", 0)
        top = reg.get("top", 0) - mon.get("top", 0)
        w = reg.get("width", 50)
        h = reg.get("height", 50)
        
        if img_bgr is None: return False, 0.0
        
        fh, fw = img_bgr.shape[:2]
        if left < 0 or top < 0 or (left+w) > fw or (top+h) > fh:
            return False, 0.0
            
        roi = img_bgr[top:top+h, left:left+w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Match
        res = cv2.matchTemplate(gray, self.icon_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        
        return max_val > 0.5, max_val


    @property
    def camera(self):
        """Thread-safe BetterCam instance."""
        if not hasattr(self._thread_local, 'camera'):
            try:
                # BetterCam works best with a dedicated instance per thread or shared?
                # Usually one instance is fine, but Desktop Duplication can be picky.
                self._thread_local.camera = bettercam.create()
            except Exception as e:
                logger.error(f"Failed to create BetterCam: {e}")
                self._thread_local.camera = None
        return self._thread_local.camera

    @property
    def sct(self):
        """Thread-safe mss instance."""
        if not hasattr(self._thread_local, 'sct'):
            self._thread_local.sct = mss.mss()
        return self._thread_local.sct

    def _build_gamma_table(self, gamma):
        if gamma == 1.0: return None
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
        return table

    def _init_tess_api(self):
        """Initializes the Direct DLL API instances."""
        try:
            exe_path = self.config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            base_path = os.path.dirname(exe_path)
            dll_path = os.path.join(base_path, "libtesseract-5.dll")
            tessdata_path = os.path.join(base_path, "tessdata")
            
            if os.path.exists(dll_path):
                # Allowlist for Day Detection
                allowlist_main = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
                
                # Path to manual words file
                words_file = os.path.join(self.project_root, "data", "ocr_words.txt")
                
                # Tesseract Variables to restrict vocabulary
                tess_vars = {
                    "load_system_dawg": "0",
                    "load_freq_dawg": "0",
                    "user_words_file": words_file
                }
                
                # Create a pool of engines for parallel passes
                # Using 'eng' instead of 'fra' because we don't need accents and 
                # we want to avoid French dictionary bias (confusing II for IL/le).
                self.tess_pool_main = [
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=7, variables=tess_vars),
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=7, variables=tess_vars),
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=7, variables=tess_vars)
                ]
                # Keep reference for legacy code
                self.tess_api_main = self.tess_pool_main[0]
                
                # 2. Secondary Engine: Stats (Digits ONLY)
                allowlist_stats = "0123456789"
                self.tess_api_secondary = TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_stats, psm=7)
                
                if self.config.get("debug_mode"):
                    print(f"VISION: High-performance Parallel Tesseract API loaded (3 workers).")
            else:
                if self.config.get("debug_mode"):
                    print(f"VISION: libtesseract-5.dll not found at {dll_path}.")
                # CRITICAL: Do not fallback to pytesseract for main loop. It's too slow.
                raise FileNotFoundError(f"Tesseract DLL not found. Pytesseract fallback DISABLED for performance.")

        except Exception as e:
            if self.config.get("debug_mode"):
                print(f"VISION: Failed to load Tesseract DLL: {e}.")
            # We must fail hard here or the user will get 2 FPS.
            print("CRITICAL ERROR: High-Performance OCR failed to load.")
            self.tess_api_main = None
            self.tess_api_secondary = None

        self.last_level_scan_time = 0
        self.last_runes_scan_time = 0
        self.level_callback = None
        self.runes_callback = None

    def set_level_callback(self, callback):
        self.level_callback = callback

    def set_runes_callback(self, callback):
        self.runes_callback = callback
        
    def set_char_callback(self, callback):
        self.char_callback = callback


    def update_config(self, new_config):
        """Updates configuration."""
        self.config = new_config

    def get_monitors(self):
        """Returns a list of all monitors with their global coordinates."""
        try:
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

    def update_from_config(self) -> None:
        """Refreshes parameters that can be changed at runtime."""
        self.debug_mode = self.config.get("debug_mode", False)
        
        # Configure Tesseract path
        tesseract_cmd = self.config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if os.path.exists(tesseract_cmd):
             pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
    def _init_camera(self, region=None):
        """Initializes Capture (MSS). No special init needed usually."""
        pass

    def set_scan_delay(self, delay):
        self.scan_delay = delay

    def update_region(self, region):
        """Updates the capture region and re-initializes the camera."""
        self.region = region
        self.config["monitor_region"] = region
        self._init_camera()

    def update_level_region(self, region):
        """Updates the level OCR region."""
        self.level_region = region
        self.config["level_region"] = region
        # No need to re-init camera as this uses simple crop from ImageGrab or separate logic

    def update_runes_region(self, region):
        """Updates the runes OCR region."""
        self.runes_region = region
        self.config["runes_region"] = region

    def update_runes_icon_region(self, region):
        """Updates the runes icon region."""
        self.runes_icon_region = region
        self.config["runes_icon_region"] = region


    def set_region_override(self, region):
        """Sets a temporary override region for scanning (e.g. for Victory check). Pass None to clear."""
        self.region_override = region

    def scan_victory_region(self, frame=None):
        """
        Scans the victory region specifically for "résultat" detection.
        Returns (text, score) or (None, 0) if nothing detected.
        """
        victory_region = self.config.get("victory_region")
        if not victory_region:
            return None, 0
        
        try:
            # Use provided frame (likely cropped from main loop) or capture new one
            if frame is not None:
                img = frame
            else:
                # Temporarily override region to capture ONLY the victory area
                old_override = getattr(self, 'region_override', None)
                self.region_override = victory_region
                try:
                    img = self.capture_screen()
                finally:
                    self.region_override = old_override
            
            if img is None: return None, 0
            
            # Use otsu preprocessing
            processed = self.preprocess_image(img, pass_type="otsu")
            if processed is None: return None, 0
            
            # OCR with PSM 7
            with self.ocr_lock:
                data = pytesseract.image_to_data(processed, config='--psm 7', output_type=pytesseract.Output.DICT)
            
            valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
            raw_text = " ".join([data['text'][i] for i in valid_indices]).strip()
            text = self.clean_text(raw_text)
            
            if not text: return None, 0
            
            # Check if it matches VICTORY pattern
            # Normalize: remove accents and convert to uppercase
            normalized = text.strip().upper()
            # Remove accents for matching (é -> E, à -> A, etc.)
            normalized_no_accents = ''.join(c for c in unicodedata.normalize('NFD', normalized) 
                                            if unicodedata.category(c) != 'Mn')
            
            if self.debug_mode:
                print(f"DEBUG Victory: normalized='{normalized}', no_accents='{normalized_no_accents}'")
            
            # Victory patterns (without accents)
            victory_patterns_base = ["RESULTAT", "RESULTIT", "RESULT", "RECOMPE"]
            
            # Always use fuzzy matching (more reliable)
            best_score = 0
            best_pattern = None
            for pattern in victory_patterns_base:
                score = fuzz.ratio(normalized_no_accents, pattern)
                if score > best_score:
                    best_score = score
                    best_pattern = pattern
            
            if self.debug_mode:
                print(f"DEBUG Victory: Best fuzzy match '{best_pattern}' score={best_score:.1f} (normalized='{normalized_no_accents}')")
            
            # Lower threshold for victory detection (60 instead of 65)
            # because "RÉSULTAT" vs "RESULTAT" should match (score=100)
            if best_score >= 60:
                if self.debug_mode:
                    print(f"VICTORY detected (fuzzy): '{text}' (Score: {best_score:.1f})")
                return text, best_score
            else:
                if self.debug_mode:
                    print(f"DEBUG Victory: Best fuzzy score {best_score:.1f} < 60, not enough")
            
            if self.debug_mode:
                print("DEBUG Victory: No victory pattern detected")
            return None, 0
        finally:
            # Restore old override
            self.region_override = old_override

    def start_monitoring(self, callback):
        if self.running: return
        self.running = True
        
        # Start Main Loop (Fast, Day Detection)
        self.thread = threading.Thread(target=self._loop, args=(callback,))
        self.thread.daemon = True
        self.thread.start()

        # Start Secondary Loop (Slow, Level/Runes)
        self.secondary_running = True
        self.secondary_thread = threading.Thread(target=self._secondary_loop)
        self.secondary_thread.daemon = True
        self.secondary_thread.start()

    def stop(self):
        self.running = False
        self.secondary_running = False

    def pause(self):
        self.paused = True
        print("Vision Engine: Paused")

    def resume(self):
        self.paused = False
        print("Vision Engine: Resumed")
        
    def capture_screen(self) -> np.ndarray:
        """Captures the current region using BetterCam."""
        try:
            reg = self.region_override if self.region_override else self.region
            if not reg: return None
            
            # BetterCam Region: [left, top, right, bottom]
            left = int(reg.get("left", 0))
            top = int(reg.get("top", 0))
            right = left + int(reg.get("width", 100))
            bottom = top + int(reg.get("height", 100))
            
            region = (left, top, right, bottom)
            
            # Use BetterCam
            if self.camera:
                img = self.camera.grab(region=region)
                if img is not None:
                     # BetterCam returns RGB or BGR? 
                     # Usually RGB. OpenCV wants BGR.
                     return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Fallback to MSS
            monitor = {
                "top": top,
                "left": left,
                "width": right - left,
                "height": bottom - top
            }
            sct_img = self.sct.grab(monitor)
            return cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Vision Engine: Capture failed: {e}")
            return None


    def adjust_gamma(self, image, gamma=1.0):
        if gamma == 1.0: return image
        
        # Check cache
        if gamma in self._gamma_cache:
            table = self._gamma_cache[gamma]
        else:
            # Build and cache
            table = self._build_gamma_table(gamma)
            self._gamma_cache[gamma] = table
            
        return cv2.LUT(image, table)

    def is_worth_ocr(self, img: np.ndarray) -> bool:
        """
        Fast check to see if the image contains enough bright pixels.
        """
        if img is None: return False
        
        # Convert to grayscale for faster processing if BGR
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        # Optimization: We look for white-ish pixels. 
        max_val = np.max(gray)
        # Lowered to 70 for robustness with photos/darker setups
        if max_val < 70: 
            return False
            
        return True

    def preprocess_image(self, img: np.ndarray, pass_type: OCRPass = OCRPass.OTSU, 
                         custom_val: int = 0, scale: float = 1.0, 
                         gamma: float = 1.0, input_gray: np.ndarray = None) -> np.ndarray:
        if img is None and input_gray is None: return None
        
        # Dynamic Scaling
        # Optimization: If no scaling needed and input_gray provided, skip resize
        if scale == 1.0 and input_gray is not None:
            gray = input_gray
        else:
            if img is not None:
                h, w = img.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                # Use INTER_LINEAR for speed
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                # Convert to gray
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            elif input_gray is not None:
                # Scale the gray input directly
                h, w = input_gray.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                gray = cv2.resize(input_gray, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                return None

        # Gamma Correction
        if gamma != 1.0:
            gray = self.adjust_gamma(gray, gamma)

        if pass_type == OCRPass.OTSU:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        elif pass_type == OCRPass.FIXED:
            val = custom_val if custom_val > 0 else 230
            _, thresh = cv2.threshold(gray, val, 255, cv2.THRESH_BINARY_INV)
        elif pass_type == OCRPass.ADAPTIVE:
             thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY_INV, 25, 2)
        elif pass_type == OCRPass.INVERTED:
             gray = cv2.bitwise_not(gray)
             _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Morphological Closing
        kernel = np.ones((2,2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return thresh

    def is_relevant(self, text: str) -> bool:
        """Checks if text is relevant for saving."""
        if not text: return False
        t = text.upper()
        
        if len(t) < 3 and t not in self.VALID_SHORT:
            return False

        if t in self.BANNED_SIGNALS: return False

        if any(c in t for c in self.RELEVANT_CHARS):
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

    def _process_numeric_region(self, region_config, callback, process_name="Numeric"):
        """
        Generic helper for Level/Runes OCR using the Unified Capture if available.
        """
        if not region_config: return
        
        try:
            reg = region_config
            left = reg.get('left', 0)
            top = reg.get('top', 0)
            width = reg.get('width', 50)
            height = reg.get('height', 30)
            
            if width <= 0 or height <= 0: return

            img = None
            
            # Unified Capture Logic
            if self.last_raw_frame is not None and (time.time() - self.last_frame_timestamp < 0.2):
                mon_reg = self.config.get("monitor_region", {})
                rel_x = left - mon_reg.get('left', 0)
                rel_y = top - mon_reg.get('top', 0)
                fh, fw = self.last_raw_frame.shape[:2]
                
                if rel_x >= 0 and rel_y >= 0 and (rel_x + width) <= fw and (rel_y + height) <= fh:
                     img = self.last_raw_frame[rel_y:rel_y+height, rel_x:rel_x+width]
                else:
                     # Fallback capture
                     monitor = {"top": top, "left": left, "width": width, "height": height}
                     img = cv2.cvtColor(np.array(self.sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
            else:
                 # Standard capture
                 monitor = {"top": top, "left": left, "width": width, "height": height}
                 img = cv2.cvtColor(np.array(self.sct.grab(monitor)), cv2.COLOR_BGRA2BGR)

            if img is None: return

            # Preprocess (Gamma 0.6 -> Otsu -> Scale 2.0)
            scale = 2.0
            # Use INTER_LINEAR for speed (Phase 1/2 overlap)
            img_resized = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # Use optimized Gamma LUT
            gray = self.adjust_gamma(gray, gamma=0.6)
            
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            if self.tess_api_secondary:
                # Use Stats Instance
                text, conf = self.tess_api_secondary.get_text(thresh)
                
                if text:
                    # Log RAW text seen if debug mode + sparse logging
                    if self.config.get("debug_mode") and self.frame_count % 60 == 0:
                         logger.info(f"OCR RAW ({process_name}): '{text}' Conf: {conf}")

                if text and text.isdigit():
                    val = int(text)
                    if callback:
                        callback(val, conf) # Pass Confidence!
            else:
                # Fallback removed
                pass

        except Exception as e:
            if self.config.get("debug_mode"):
                print(f"{process_name} Processing Failed: {e}")

    def _process_level_ocr(self):
        """Captures and processes the Level region."""
        self._process_numeric_region(self.level_region, self.level_callback, "Level")

    def _process_runes_ocr(self):
        """Captures and processes the Runes region."""
        # GATE: Check Icon First
        if self.last_raw_frame is not None:
             is_icon_present, conf = self.detect_rune_icon(self.last_raw_frame)
             if not is_icon_present:
                 if self.config.get("debug_mode") and self.frame_count % 60 == 0:
                     logger.info(f"Runes OCR Paused: Icon Missing ({conf:.2f})")
                 return # Skip OCR if icon is missing (Map, Menu, etc.)

        self._process_numeric_region(self.runes_region, self.runes_callback, "Runes")

    def detect_char_screen(self, img_bgr):
        """
        Checks if the Character Select Screen is present.
        Returns (True/False, confidence).
        """
        if self.char_template is None:
            return False, 0.0
            
        reg = self.config.get("char_region", {})
        if not reg or reg.get("width", 0) == 0:
            return False, 0.0
            
        # Extract Region
        mon = self.config.get("monitor_region", {})
        left = reg.get("left", 0) - mon.get("left", 0)
        top = reg.get("top", 0) - mon.get("top", 0)
        w = reg.get("width", 50)
        h = reg.get("height", 50)
        
        if img_bgr is None: return False, 0.0
        
        fh, fw = img_bgr.shape[:2]
        if left < 0 or top < 0 or (left+w) > fw or (top+h) > fh:
            return False, 0.0
            
        roi = img_bgr[top:top+h, left:left+w]
        
        # Use simple diff or template matching?
        # Since config region matches template exactly (captured from it),
        # matchTemplate should be perfect at (0,0) of ROI relative to template? 
        # Actually template IS the ROI.
        # But we captured template from screen.
        # Let's use matchTemplate of template AGAINST roi.
        
        # Determine Color or Gray
        if len(self.char_template.shape) == 3:
             # Color match
             res = cv2.matchTemplate(roi, self.char_template, cv2.TM_CCOEFF_NORMED)
        else:
             gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
             res = cv2.matchTemplate(gray, self.char_template, cv2.TM_CCOEFF_NORMED)
             
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return max_val > 0.8, max_val

    def _process_char_detection(self):
         if self.last_raw_frame is not None:
             # 1. Single Fast Check
             found, conf = self.detect_char_screen(self.last_raw_frame)
             
             if found:
                 # 2. Burst Confirmation (User Request: "5 fois de suite rapidement")
                 # We need to capture fresh frames for this.
                 if self.config.get("debug_mode"): print(f"Char Screen Candidate ({conf:.2f}). Verifying...")
                 
                 confirm_count = 0
                 reg = self.config.get("char_region", {})
                 
                 for _ in range(5):
                     # Capture fresh small region
                     frame = self.capture_screen() # Captures override or full monitor?
                     # capture_screen respects region_override. We should set it temporarily or just use detect_char_screen on full frame?
                     # detect_char_screen takes full frame and crops.
                     # efficient way: override region to char_region, capture, match.
                     
                     # Simpler: Just capture full frame 5 times (overhead 5x 50ms = 250ms, acceptable)
                     # Or rely on loop? No, loop is slow (200ms). Burst must be fast.
                     
                     if frame is None: continue
                     f_found, f_conf = self.detect_char_screen(frame)
                     if f_found: confirm_count += 1
                     # Sleep tiny bit?
                     # time.sleep(0.05) 
                 
                 # Consensus: 4/5 or 3/5? User said "5 fois de suite". Let's say 4/5.
                 if confirm_count >= 4:
                     if self.config.get("debug_mode"): print(f"Char Screen CONFIRMED ({confirm_count}/5).")
                     self.char_callback(True, conf)
                 else:
                     if self.config.get("debug_mode"): print(f"Char Screen REJECTED ({confirm_count}/5).")



    def request_runes_burst(self) -> List[int]:
        """
        Performs 5 high-speed scans of the runes region to find a consensus.
        """
        results = []
        if not self.runes_region: return results
        
        reg = self.runes_region
        left, top = reg.get('left', 0), reg.get('top', 0)
        width, height = reg.get('width', 150), reg.get('height', 40)
        monitor = {"top": top, "left": left, "width": width, "height": height}

        for _ in range(5):
            try:
                # Capture Optimized (MSS)
                sct_img = self.sct.grab(monitor)
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Preprocess (Fast path using numeric helper logic essence)
                scaled = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
                gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
                gamma_adj = self.adjust_gamma(gray, gamma=0.6)
                _, thresh = cv2.threshold(gamma_adj, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                
                if self.tess_api_secondary:
                    text, _ = self.tess_api_secondary.get_text(thresh)
                    if text and text.isdigit():
                        results.append(int(text))
            except Exception as e:
                if self.config.get("debug_mode"): 
                    print(f"Burst scan error: {e}")
            
            # Removed sleep for burst speed
            
        return results

    def _ocr_pass_worker(self, engine: TesseractAPI, img: np.ndarray, gray_preview: np.ndarray, p_config: Dict[str, Any]):
        """Runs a single OCR pass on a background thread."""
        try:
            processed = self.preprocess_image(img, pass_type=p_config["type"], 
                                              custom_val=p_config["val"], 
                                              scale=p_config["scale"],
                                              gamma=p_config.get("gamma", 1.0),
                                              input_gray=gray_preview if p_config["scale"] == 1.0 else None)
            if processed is None: return None

            # --- SAFETY CHECK: Prevent Tesseract "Image too small" errors ---
            coords = cv2.findNonZero(processed)
            if coords is None: return None
            _, _, w, h = cv2.boundingRect(coords)
            # Filter out noise (dots/lines < 10px wide) which causes Tesseract to complain
            if w < 10 or h < 8: return None 
            # ----------------------------------------------------------------

            text, avg_conf = engine.get_text(processed)
            cleaned = self.clean_text(text)
            cleaned = self.CORRECTION_MAP.get(cleaned, cleaned)
            
            if not cleaned: return None
            
            return {
                "text": cleaned,
                "conf": avg_conf,
                "width": processed.shape[1]
            }
        except Exception as e:
            if self.debug_mode: print(f"OCR Pass Worker Error: {e}")
            return None

    def _perform_full_ocr_cycle(self, img: np.ndarray, gray_preview: np.ndarray):
        """Internal helper for a complete OCR run (all passes in PARALLEL)."""
        best_text = ""
        best_conf = 0.0
        best_width = 0
        found_valid_text = False
        
        # Optimization: Only scan if it's worth it
        if not self.is_worth_ocr(gray_preview):
             return "", 0.0, 0, False

        # --- ADAPTIVE LOGIC (Data-Driven from Fine-Tuning) ---
        # Analyze brightness to choose the best strategy
        mean_brightness = np.mean(gray_preview)
        
        passes = []
        if mean_brightness < 70:
            # DARK IMAGE: Use Otsu + Gamma 0.4
            passes.append({"type": OCRPass.OTSU, "val": 0, "scale": 1.0, "gamma": 0.4})
        else:
            # BRIGHT/NORMAL IMAGE: Use Fixed 240 + Gamma 0.3
            passes.append({"type": OCRPass.FIXED, "val": 240, "scale": 1.0, "gamma": 0.3})
            
        # Dispatch to ThreadPool
        futures = []
        for i, p_config in enumerate(passes):
            # Use one of the pool engines
            engine = self.tess_pool_main[i % len(self.tess_pool_main)]
            futures.append(self.executor.submit(self._ocr_pass_worker, engine, img, gray_preview, p_config))
            
        # Collect results
        for future in futures:
            res = future.result()
            if res:
                if len(res["text"]) > 2: found_valid_text = True
                
                if res["conf"] > best_conf:
                    best_conf = res["conf"]
                    best_text = res["text"]
                    best_width = res["width"]
                    
        return best_text, best_conf, best_width, found_valid_text

    def _day_burst(self, callback, brightness):
        """Takes 4 additional high-speed samples to confirm a detection."""
        if self.debug_mode:
            print("VISION: Starting Day Burst confirmation...")
            
        for _ in range(3): # Take 3 more samples (total 4 with the original one)
            try:
                img = self.capture_screen()
                if img is None: continue
                
                self.last_raw_frame = img
                self.last_frame_timestamp = time.time()
                
                gray_preview = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                text, conf, width, _ = self._perform_full_ocr_cycle(img, gray_preview)
                
                if text:
                    # Execute callback immediately for consensus
                    callback(text, width, 0, {}, brightness, conf)
            except:
                pass

    def _loop(self, callback):
        print(f"Vision Engine: Monitoring started with Multi-Instance Strategy. Debug Mode: {self.config.get('debug_mode')}")
        
        while self.running:
            try:
                loop_start = time.perf_counter()
                
                # 1. Cooldown Check (Global Pause)
                if time.time() < self.suppress_ocr_until:
                    time.sleep(1.0) 
                    continue
                
                # 2. Capture
                img = self.capture_screen()
                if img is None:
                    time.sleep(0.1)
                    continue
                
                self.last_raw_frame = img
                
                self.last_frame_timestamp = time.time()
                
                # 3. Preprocess
                h, w = img.shape[:2]
                gray_preview = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                brightness = np.mean(gray_preview)
                
                if brightness < 15: # Too dark for OCR, but relevant for Black Screen detection
                    self.consecutive_garbage_frames = 0
                    # Fire callback with empty text to report brightness to StateLogic
                    callback("", 0, 0, {}, brightness, 0)
                    time.sleep(0.1)
                    continue

                if self.is_low_power_mode:
                    pass

                # Store debug vars once
                dm = self.debug_mode
                
                # Run OCR checks
                best_text, best_conf, best_width, found_valid_text = self._perform_full_ocr_cycle(img, gray_preview)
                best_center_offset = 0 # Not supported in DLL mode currently
                best_word_data = {}    # Not supported in DLL mode currently
                
                # --- NOISE THROTTLE LOGIC ---
                self.frame_count += 1
                
                if not found_valid_text:
                    self.consecutive_garbage_frames += 1
                else:
                    self.consecutive_garbage_frames = 0
                    self.is_low_power_mode = False

                if self.config.get("debug_mode") and (best_text or self.frame_count % 30 == 0):
                    # Show Day RAW if anything seen, or periodic heartbeat
                    log_text = best_text if best_text else "EMPTY"
                    if log_text != getattr(self, '_last_logged_day_text', '') or self.frame_count % 60 == 0:
                        logger.info(f"OCR RAW (Day): '{log_text}' Conf: {best_conf:.1f}")
                        self._last_logged_day_text = log_text

                if self.consecutive_garbage_frames > 5:
                    self.is_low_power_mode = True
                else:
                    # Burst if Day detected
                    if "JOUR" in best_text or "RESULTAT" in best_text:
                        self._day_burst(callback, brightness)
                        
                    # Store for Debug Inspector
                    self.last_ocr_text = best_text
                    self.last_ocr_conf = best_conf
                    self.last_brightness = brightness
                    
                    # Standard Callback
                    callback(best_text, best_width, best_center_offset, best_word_data, brightness, best_conf)
                
                # Adaptive FPS Logic
                now_ts = time.time()
                activity_detected = found_valid_text
                
                # Check for brightness change (simple motion/scene change detection)
                if hasattr(self, 'last_brightness_val'):
                    if abs(brightness - self.last_brightness_val) > 2.0: # ~1% change threshold
                        activity_detected = True
                self.last_brightness_val = brightness

                if activity_detected:
                    self.last_activity_time = now_ts
                    self.is_low_power_mode = False
                
                # If no activity for 10s, enter Power Save
                if now_ts - self.last_activity_time > 10.0:
                    self.is_low_power_mode = True
                
                # Update Scan Delay
                current_delay = self.power_save_delay if self.is_low_power_mode else self.base_scan_delay
                self.scan_delay = current_delay

                elapsed = time.perf_counter() - loop_start
                self.last_loop_end = time.perf_counter()

                # Sleep to maintain FPS
                remaining_delay = max(0, self.scan_delay - elapsed)
                time.sleep(remaining_delay if remaining_delay > 0 else 0.001)

            except Exception as e:
                print(f"Vision error: {e}")
                time.sleep(1)

    def _secondary_loop(self):
        """
        Secondary Thread Loop: Handles lower-priority, 1Hz OCR tasks (Level, Runes).
        This runs independently to avoid stalling the main 'Day' detection loop.
        """
        print(f"Vision Engine: Secondary Worker started (Level/Runes).")
        
        while self.secondary_running:
            try:
                loop_start = time.time()
                
                # 1. Level OCR
                if self.level_region:
                    try:
                        self._process_level_ocr()
                    except Exception as e:
                        if self.config.get("debug_mode"):
                            print(f"Level OCR (Thread) Error: {e}")

                # 2. Runes & Icon Check
                is_icon_visible = False
                if self.runes_region and self.last_raw_frame is not None:
                     # Check Icon Visibility first
                     is_icon_visible, _ = self.detect_rune_icon(self.last_raw_frame)
                     
                     if is_icon_visible:
                         # ICON VISIBLE: Game Interface Active -> Check Runes
                         try:
                             self._process_numeric_region(self.runes_region, self.runes_callback, "Runes")
                         except Exception as e:
                             if self.config.get("debug_mode"): print(f"Runes OCR Error: {e}")
                     else:
                         # ICON MISSING: Potential Menu/Char Select -> Check Char Detect
                         # 3. Char Select Detection (Only if Icon Missing)
                         if self.char_template is not None and self.char_callback:
                            try:
                                self._process_char_detection()
                            except Exception as e:
                                 if self.config.get("debug_mode"): print(f"Char Detect Error: {e}")



                # Maintain approx 5Hz frequency (User Request: "ne s'actualise pas assez vite")
                elapsed = time.time() - loop_start
                sleep_time = max(0.01, 0.2 - elapsed) # 200ms cycle
                time.sleep(sleep_time)

            except Exception as e:
                print(f"Secondary Vision Loop Crash: {e}")
                time.sleep(1)

    def log_debug(self, message: str) -> None:
        """Allow other services to log via unified logger"""
        logger.debug(message)

    def trigger_cooldown(self, seconds=60):
        """
        Called by StateService when a Day/Event is confirmed.
        Stops the main OCR engine for 'seconds' to save CPU.
        """
        self.suppress_ocr_until = time.time() + seconds
        if self.debug_mode:
            print(f"VISION: Cooldown triggered for {seconds}s.")

    def save_labeled_sample(self, label: str):
        """
        Saves the last captured frame as a labeled sample for ML training.
        """
        if self.last_raw_frame is None: return
        
        # Avoid saving if frame is too old (> 1.0s)
        if time.time() - self.last_frame_timestamp > 1.0:
            return

        try:
            # Sanitize label
            safe_label = "".join(c for c in label if c.isalnum() or c in " -_").strip()
            if not safe_label: safe_label = "UNKNOWN"
            
            # Directory: samples/LABEL/
            label_dir = os.path.join(self.project_root, "samples", safe_label)
            os.makedirs(label_dir, exist_ok=True)
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = os.path.join(label_dir, f"{ts}.png")
            
            cv2.imwrite(filename, self.last_raw_frame)
            print(f"Saved labeled sample: {filename}")
            
        except Exception as e:
            print(f"Failed to save labeled sample: {e}")

    def get_debug_state(self) -> Dict[str, Any]:
        """Returns internal state for the Debug Inspector UI."""
        now = time.time()
        cooldown_rem = max(0, self.suppress_ocr_until - now)
        
        return {
            "cooldown_remaining": cooldown_rem,
            "is_cooling_down": cooldown_rem > 0,
            "is_low_power_mode": self.is_low_power_mode,
            "consecutive_garbage": self.consecutive_garbage_frames,
            "last_brightness": self.last_brightness,
            "last_text": self.last_ocr_text,
            "last_conf": self.last_ocr_conf,
            "scan_delay": self.scan_delay,
            "tess_main_active": self.tess_api_main is not None,
            "tess_secondary_active": self.tess_api_secondary is not None
        }
