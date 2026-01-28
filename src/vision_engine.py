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
        
        self.debug_callback = None # New Debug Callback
        
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
        
        # Adjustable OCR Parameters (Tuner)
        # Adjustable OCR Parameters (Tuner)
        # Split into Runes / Level
        # Load from config or use defaults
        default_params = {
            "Runes": { "scale": 1.0, "gamma": 1.9, "thresh": 255, "dilate": 0, "psm": 7, "mode": "Digits", "padding": 20 },
            "Level": { "scale": 4.0, "gamma": 0.6, "thresh": 160, "dilate": 1, "psm": 7, "mode": "Digits", "padding": 20 }
        }
        self.ocr_params = self.config.get("ocr_params", default_params)
        
        # Whitelist mapping
        self.ocr_whitelists = {
            "Digits": "0123456789",
            "Alphanumeric": "", # Empty = everything
            "Uppercase": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "Custom": "0123456789JOUR I,"
        }

        # Ensure deep merge / structure integrity if config is partial
        for key in default_params:
            if key not in self.ocr_params:
                self.ocr_params[key] = default_params[key]

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
        
        # Configure pytesseract path for fallback/numeric modes
        pytesseract.pytesseract.tesseract_cmd = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        
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

        # Optimize State
        self.is_in_menu_state = False
        self.last_menu_check_time = 0  # Throttle for burst confirmation
        
        # Char Select / Menu Matching
        self.menu_template = None
        self.char_callback = None # Keep callback name generic or rename? Renaming to menu_callback for consistency.
        self._load_menu_template()
        self.day_ocr_enabled = True
        self.last_day_ocr_status = True # For logging

    def _load_menu_template(self):
        try:
            # Using same template name for now or new one? User said "refaire une capture".
            # I will assume new capture will save to 'main_menu_template.png'.
            template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates", "main_menu_template.png")
            if os.path.exists(template_path):
                self.menu_template = cv2.imread(template_path, cv2.IMREAD_COLOR) 
                if self.menu_template is None:
                     self.menu_template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                
                if self.config.get("debug_mode"):
                    print(f"VISION: Loaded Menu Template from {template_path}")
            else:
                if self.config.get("debug_mode"):
                    print(f"VISION: Menu Template not found at {template_path}. Menu detection disabled.")
        except Exception as e:
            print(f"Error loading menu template: {e}")


    def _load_icon_template(self):
        try:
            template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates", "rune_icon_template.png")
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
        left = reg.get("left", 0)
        top = reg.get("top", 0)
        w = reg.get("width", 50)
        h = reg.get("height", 50)
        
        # Calculate relative coordinates
        rel_x = left - mon.get("left", 0)
        rel_y = top - mon.get("top", 0)
        
        roi = None
        
        # Unified Capture Logic (Fast path)
        if img_bgr is not None:
            fh, fw = img_bgr.shape[:2]
            if rel_x >= 0 and rel_y >= 0 and (rel_x + w) <= fw and (rel_y + h) <= fh:
                 roi = img_bgr[rel_y:rel_y+h, rel_x:rel_x+w]
        
        # Fallback Capture Logic (If outside monitor region or img_bgr is None)
        if roi is None:
            try:
                monitor = {"top": top, "left": left, "width": w, "height": h}
                sct_img = self.sct.grab(monitor)
                roi = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
            except Exception as e:
                # if self.config.get("debug_mode"): logger.debug(f"Icon Fallback Capture failed: {e}")
                return False, 0.0

        if roi is None: return False, 0.0
        
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
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=6, variables=tess_vars),
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=6, variables=tess_vars),
                    TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_main, psm=6, variables=tess_vars)
                ]                # self.tess_pool_main = []
                # Keep reference for legacy code
                if self.tess_pool_main:
                    self.tess_api_main = self.tess_pool_main[0]
                else:
                    self.tess_api_main = None
                
                # 2. Secondary Engine: Stats (Digits ONLY)
                # STRICT Allowlist to prevent "II" or "|" errors. Digits 0-9 only.
                allowlist_diag = "0123456789"
                self.tess_api_secondary = TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist_diag, psm=6)
                # self.tess_api_secondary = None
                
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
        
    def set_menu_callback(self, callback):
        self.menu_callback = callback
        self.debug_image_callback = None


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

    def set_debug_callback(self, callback):
        """Sets the callback for real-time debug UI updates."""
        self.debug_callback = callback
        
    def set_debug_image_callback(self, callback):
        """Sets the callback for real-time binary image preview."""
        self.debug_image_callback = callback
        
    def set_ocr_param(self, category: str, key: str, value: float):
        """Updates internal OCR parameters dynamically for a specific category."""
        if category in self.ocr_params and key in self.ocr_params[category]:
            # Type safety
            if key in ["thresh", "dilate", "padding"]:
                self.ocr_params[category][key] = int(value)
            else:
                self.ocr_params[category][key] = float(value)
            
            if self.debug_mode:
                print(f"VISION TUNER ({category}): Set {key} = {self.ocr_params[category][key]}")

    def update_from_config(self):
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
        
    def set_day_ocr_enabled(self, enabled: bool):
        self.day_ocr_enabled = enabled
        if self.debug_mode:
            logger.info(f"Vision Engine: Day OCR {'ENABLED' if enabled else 'DISABLED'}")
        
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
            # if self.camera:
            #     img = self.camera.grab(region=region)
            #     if img is not None:
            #          # BetterCam returns RGB or BGR? 
            #          # Usually RGB. OpenCV wants BGR.
            #          return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
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

            # Preprocess (Gamma 0.6 -> Grayscale -> Scale 4.0)
            # Use Dynamic Parameters based on Process Name (Runes vs Level)
            params = self.ocr_params.get(process_name, self.ocr_params["Level"])
            
            scale = params.get("scale", 4.0)
            gamma = params.get("gamma", 0.6)
            thresh_val = params.get("thresh", 160)
            dilate_iter = params.get("dilate", 1)
            padding = params.get("padding", 20)

            img_resized = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # Use optimized Gamma LUT
            gray = self.adjust_gamma(gray, gamma=gamma)
            
            # Fixed 160 threshold for clean black-on-white text
            _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
            
            # Simple fallback to OTSU ONLY if the image is mostly empty/white
            if np.mean(thresh) > 252:
                 _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # --- MORPHOLOGICAL EROSION (Thicken Text) ---
            if dilate_iter > 0:
                kernel = np.ones((2,2), np.uint8)
                thresh = cv2.dilate(thresh, kernel, iterations=dilate_iter)

            # Padding is essential for single digit recognition

            # Padding is essential for single digit recognition
            if padding > 0:
                thresh = cv2.copyMakeBorder(thresh, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=255) # White padding for Black-on-White text
            
            # Ensure contiguous for C API
            thresh = np.ascontiguousarray(thresh)
            
            text = ""
            conf = 0.0
            
            # --- DEBUG IMAGE CALLBACK (Moved after OCR to get Confidence) ---
            # We need to run OCR first.

            if self.tess_api_secondary:
                # Apply Dynamic Parameters (PSM, Mode)
                psm = params.get("psm", 7)
                mode_name = params.get("mode", "Digits")
                whitelist = self.ocr_whitelists.get(mode_name, "")
                
                # Update Tesseract Variables dynamically
                self.tess_api_secondary.lib.TessBaseAPISetVariable(self.tess_api_secondary.handle, b"tessedit_pageseg_mode", str(psm).encode('utf-8'))
                self.tess_api_secondary.lib.TessBaseAPISetVariable(self.tess_api_secondary.handle, b"tessedit_char_whitelist", whitelist.encode('utf-8'))

                # Use High-Performance DLL Instance
                text, conf = self.tess_api_secondary.get_text(thresh)
                
                if self.debug_image_callback:
                    self.debug_image_callback(process_name, thresh, conf)
                
                if process_name == "Level" and self.config.get("debug_mode"):
                    current_sec = int(time.time())
                    if current_sec % 2 == 0:  # Every 2 seconds
                        logger.info(f"DLL OCR RAW ({process_name}): text='{text}' Conf: {conf}")
                        debug_path = os.path.join(self.project_root, f"debug_{process_name.lower()}_dll.png")
                        cv2.imwrite(debug_path, thresh)

                if text:
                    # Translation for common Elden Ring font misreadings (digits)
                    # Note: With Allowlist "0123456789", letters like 'I', 'l', '|' won't appear,
                    # but maybe mapped to '1' or dropped. 
                    # We keep replacements just in case some slip through or allowlist isn't perfect partial match.
                    text = text.replace('|', '1').replace('I', '1').replace('l', '1').replace('[', '1').replace(']', '1').replace('!', '1')
                    
                    # Log RAW text seen if debug mode + sparse logging
                    if self.config.get("debug_mode") and self.frame_count % 60 == 0:
                         logger.info(f"OCR RAW ({process_name}): '{text}' Conf: {conf}")

                # --- UNIFIED DEBUG CALLBACK (Post-Clean) ---
                if self.debug_callback:
                    # Provide the text EXACTLY as we logic sees it
                    self.debug_callback(process_name, text, conf)

                # Extract first numeric sequence
                numeric_match = re.search(r'\d+', text)
                if numeric_match:
                    val = int(numeric_match.group())
                    if callback:
                        callback(val, conf) # Pass Confidence!
                else:
                    if process_name == "Level" and self.config.get("debug_mode"):
                        current_sec = int(time.time())
                        if current_sec % 2 == 0:
                            logger.info(f"Level DLL OCR FAILED: text='{text}'")
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

    def detect_menu_screen(self, img_bgr=None):
        """
        Checks if the Main Menu Screen is present.
        Uses GLOBAL coordinates (not relative to monitor_region) for multi-monitor support.
        Returns (True/False, confidence).
        """
        if self.menu_template is None:
            return False, 0.0
            
        reg = self.config.get("menu_region", {})
        if not reg or reg.get("width", 0) == 0:
            return False, 0.0
        
        # IMPORTANT: Use GLOBAL coordinates directly (like capture_menu_template.py)
        # This fixes multi-monitor setups where menu_region is on a different screen
        try:
            with mss.mss() as sct:
                monitor = {
                    "top": reg.get("top", 0),
                    "left": reg.get("left", 0),
                    "width": reg.get("width", 50),
                    "height": reg.get("height", 50)
                }
                
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                roi = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Template matching
                if len(self.menu_template.shape) == 3:
                    # Color match
                    res = cv2.matchTemplate(roi, self.menu_template, cv2.TM_CCOEFF_NORMED)
                else:
                    # Grayscale match
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    res = cv2.matchTemplate(gray, self.menu_template, cv2.TM_CCOEFF_NORMED)
                    
                _, max_val, _, _ = cv2.minMaxLoc(res)
                return max_val > 0.8, max_val
                
        except Exception as e:
            if self.config.get("debug_mode"):
                logger.error(f"Menu detection error: {e}")
            return False, 0.0

    def _process_menu_detection(self):
         try:
             # 1. Single Fast Check using global coordinates
             found, conf = self.detect_menu_screen()
             
             if self.config.get("debug_mode"):
                 logger.info(f"Menu Burst Check Starting (initial conf: {conf:.2f})")
             
             if found:
                 # 2. Burst Confirmation (5 frames)
                 confirm_count = 0
                 
                 for i in range(5):
                     try:
                         found_burst, conf_burst = self.detect_menu_screen()
                         if found_burst: 
                            confirm_count += 1
                         if self.config.get("debug_mode"):
                             logger.info(f"  Burst {i+1}/5: {found_burst} (conf: {conf_burst:.2f})")
                     except Exception as e:
                         if self.config.get("debug_mode"):
                             logger.error(f"  Burst {i+1}/5 ERROR: {e}")
                     
                     # Tiny sleep to allow screen update
                     time.sleep(0.02)
                 
                 # Consensus: 4/5
                 if confirm_count >= 4:
                     logger.info(f"Menu Screen CONFIRMED ({confirm_count}/5)")
                     try:
                         self.menu_callback(True, conf)
                         logger.info("Menu callback executed successfully")
                     except Exception as e:
                         logger.error(f"Menu callback ERROR: {e}")
                 else:
                     logger.info(f"Menu Screen REJECTED ({confirm_count}/5)")
             else:
                 if self.config.get("debug_mode"):
                     logger.info(f"Menu initial check failed (conf: {conf:.2f})")
         except Exception as e:
             logger.error(f"_process_menu_detection CRASH: {e}")
             import traceback
             logger.error(traceback.format_exc())



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

    def _ocr_pass_worker_pyt(self, img: np.ndarray, gray_preview: np.ndarray, p_config: Dict[str, Any]):
        """Runs a single OCR pass using Pytesseract on another thread."""
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
            x, y, w, h = cv2.boundingRect(coords)
            
            pil_img = Image.fromarray(processed)
            text = pytesseract.image_to_string(pil_img, config='--psm 6').strip()
            # Pytesseract doesn't provide confidence easily in image_to_string
            # We assign a default good confidence if text found
            return {"text": text, "conf": 75 if text else 0, "width": w}
        except Exception as e:
            if self.config.get("debug_mode"):
                print(f"Pyt-Worker Error: {e}")
            return None
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
            # BRIGHT/NORMAL IMAGE: Soft thresholds for Cyan/Blue text
            passes.append({"type": OCRPass.FIXED, "val": 180, "scale": 1.0, "gamma": 0.5})
            passes.append({"type": OCRPass.FIXED, "val": 150, "scale": 1.0, "gamma": 0.7})
            
            # SPECIAL: Red channel extraction for Cyan/Blue banners
            passes.append({"type": "RED", "val": 160, "scale": 1.0, "gamma": 0.6})
            
        # Dispatch to ThreadPool
        futures = []
        # Collect results
        for idx, p_config in enumerate(passes):
            try:
                if p_config.get("type") == "RED":
                    # Extract red channel (BGR format)
                    chan = img[:, :, 2]
                    
                    # MAGICAL FIX: 3x Scale for stylized banner font
                    scale = 3.0
                    h, w = chan.shape[:2]
                    process_img = cv2.resize(chan, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
                    
                    process_img = self.adjust_gamma(process_img, gamma=1.0)
                    _, process_img = cv2.threshold(process_img, 120, 255, cv2.THRESH_BINARY_INV)
                    
                    # Pad extensively
                    pad = 50
                    process_img = cv2.copyMakeBorder(process_img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
                    
                    if self.config.get("debug_mode") and self.frame_count % 30 == 0:
                        cv2.imwrite(os.path.join(self.project_root, "debug_red_pass.png"), process_img)
                    
                    # Convert to PIL for pytesseract
                    pil_img = Image.fromarray(process_img)
                    text = pytesseract.image_to_string(pil_img, config='--psm 6').strip()
                    conf = 85 if text else 0 
                    width = w * scale # Approximate width for pattern manager
                else:
                    # Standard worker via executor
                    res = self._ocr_pass_worker_pyt(img, gray_preview, p_config)
                    if not res: continue
                    text, conf, width = res["text"], res["conf"], res.get("width", 0)
                
                if self.config.get("debug_mode") and text:
                     p_type = p_config.get("type", "UNKNOWN")
                     logger.info(f"  > Pass {idx} ({p_type}): '{text}' (Conf: {conf})")

                if text:
                    if len(text) > 2: found_valid_text = True
                    
                    if conf > best_conf:
                        best_text = text
                        best_conf = conf
                        best_width = width
            except Exception as e:
                if self.config.get("debug_mode"):
                    logger.error(f"OCR Cycle Error in pass {idx}: {e}")
                    
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
                # OPTIMIZATION: If Main Menu is detected by secondary thread, SKIP Day OCR loop.
                if self.is_in_menu_state:
                    time.sleep(0.5)
                    continue

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

                # DEBUG: Save Day Region capture
                if self.config.get("debug_mode"):
                    current_sec = int(time.time())
                    if current_sec % 5 == 0:
                         debug_day_path = os.path.join(self.project_root, "debug_day_region.png")
                         cv2.imwrite(debug_day_path, img)

                if self.is_low_power_mode:
                    pass

                # Store debug vars once
                dm = self.debug_mode
                
                best_text, best_conf, best_width, found_valid_text = "", 0.0, 0, False
                if self.day_ocr_enabled:
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
                    
                    if self.debug_callback:
                         self.debug_callback("Zone", best_text, best_conf)

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
                # Local counter for this thread (initialized via modulo logic or simple time check)
                # We'll just rely on time.time() for 10s logs actually? Or just int(time.time())
                current_sec = int(time.time())
                
                # 1. Runes & Icon Check (PRIORITY: Determine Menu State first)
                is_icon_visible = False
                if self.runes_region and self.last_raw_frame is not None:
                     # Check Icon Visibility first
                     is_icon_visible, icon_conf = self.detect_rune_icon(self.last_raw_frame)
                     
                     if is_icon_visible:
                         if current_sec % 5 == 0: logger.info(f"DEBUG: Icon Visible (Conf: {icon_conf:.2f}) -> Skipped Menu")
                         # ICON VISIBLE: Game Interface Active -> Not Menu
                         self.is_in_menu_state = False
                         try:
                             self._process_numeric_region(self.runes_region, self.runes_callback, "Runes")
                         except Exception as e:
                             if self.config.get("debug_mode"): print(f"Runes OCR Error: {e}")
                     else:
                         if current_sec % 5 == 0: logger.info("DEBUG: Icon Missing -> Checking Menu...")
                         # ICON MISSING: Potential Menu/Char Select -> Check Char Detect
                         # 2. Main Menu Detection (Only if Icon Missing)
                         if self.menu_template is not None and self.menu_callback:
                            try:
                                # We check menu detection logic
                                # Note: _process_menu_detection handles the burst and callback
                                # We just need to capture the state for optimization
                                found_menu, menu_conf = self.detect_menu_screen()
                                if current_sec % 5 == 0: logger.info(f"DEBUG: Menu Check: {found_menu} (Conf: {menu_conf:.2f})")
                                
                                if found_menu:
                                     # Throttle: Only run burst check every 2 seconds
                                     now = time.time()
                                     if now - self.last_menu_check_time > 2.0:
                                         self.last_menu_check_time = now
                                         self._process_menu_detection() 
                                     
                                     self.is_in_menu_state = True
                                else:
                                     self.is_in_menu_state = False
                            except Exception as e:
                                 if self.config.get("debug_mode"): print(f"Menu Detect Error: {e}")
                                 self.is_in_menu_state = False

                # 2. Level OCR (Only if NOT in Menu OR if waiting for early game)
                # CRITICAL: In early game (JOUR I displayed), icon is missing but we MUST detect Level 1
                # So we force Level OCR even without icon if icon is missing (potential early game)
                should_scan_level = (not self.is_in_menu_state) or (not is_icon_visible)
                
                if should_scan_level and self.level_region:
                    if current_sec % 5 == 0: logger.info(f"DEBUG: Scanning Level (menu={self.is_in_menu_state}, icon={is_icon_visible})")
                    try:
                        self._process_level_ocr()
                    except Exception as e:
                        if self.config.get("debug_mode"):
                            print(f"Level OCR (Thread) Error: {e}")



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

    def capture_training_sample(self, category: str):
        """
        Saves the current *cropped* region (Level or Runes) for training.
        """
        try:
            # Determine which region to grab
            reg = None
            if category.lower() == "level":
                reg = self.level_region
            elif category.lower() == "runes":
                reg = self.runes_region
            elif category.lower() == "day":
                # Day region isn't a specific crop usually, it's the whole monitor region
                # But we can save the whole monitor region or a crop if needed.
                # For training "JOUR I", we likely want the whole captured frame?
                # Actually, the user wants "0-9, J, O..." from specifically the Runes/Level/Day areas.
                # Let's save the RAW capture of the RUNES/LEVEL region.
                pass
                
            if not reg: 
                # If no specific region, save the last raw frame (Monitor Region)
                if self.last_raw_frame is not None:
                     self._save_image_sample("Day_Full", self.last_raw_frame)
                return

            # Capture crop
            # Logic similar to _process_numeric_region
            if self.last_raw_frame is not None:
                mon_reg = self.config.get("monitor_region", {})
                left = reg.get('left', 0)
                top = reg.get('top', 0)
                width = reg.get('width', 50)
                height = reg.get('height', 30)
                
                rel_x = left - mon_reg.get('left', 0)
                rel_y = top - mon_reg.get('top', 0)
                fh, fw = self.last_raw_frame.shape[:2]
                
                if rel_x >= 0 and rel_y >= 0 and (rel_x + width) <= fw and (rel_y + height) <= fh:
                     crop = self.last_raw_frame[rel_y:rel_y+height, rel_x:rel_x+width]
                     self._save_image_sample(category, crop)
        except Exception as e:
            print(f"Failed to capture training sample: {e}")

    def _save_image_sample(self, category, img):
        if img is None: return
        try:
            training_dir = os.path.join(self.project_root, "samples_training", category)
            os.makedirs(training_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = os.path.join(training_dir, f"{ts}.png")
            cv2.imwrite(filename, img)
            print(f"Use for Training: Saved {filename}")
        except Exception as e:
            print(f"Error saving sample: {e}")
            
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
