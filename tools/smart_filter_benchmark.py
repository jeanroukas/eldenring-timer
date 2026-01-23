import cv2
import numpy as np
import os
import sys
import time
import json
import pytesseract

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision_engine import VisionEngine

# Discovery of Tesseract path
possible_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\lprad\AppData\Local\Tesseract-OCR\tesseract.exe"
]
for p in possible_paths:
    if os.path.exists(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

class BenchVisionEngine(VisionEngine):
    def __init__(self, config):
        super().__init__(config)
        self.scan_delay = 0
        self.current_img = None
        
    def capture_screen(self):
        return self.current_img.copy()

def run_bench(engine, img, duration=5):
    engine.current_img = img
    count = 0
    start = time.perf_counter()
    end_time = start + duration
    
    # Simulate the loop logic (simplified)
    while time.perf_counter() < end_time:
        # 1. Capture/Copy
        test_img = engine.capture_screen()
        
        # 2. Smart Filter
        if not engine.is_worth_ocr(test_img):
            count += 1
            continue
            
        # 3. Simulate one OCR pass (the cost)
        processed = engine.preprocess_image(test_img, pass_type="otsu", scale=1.0)
        try:
            pytesseract.image_to_string(processed, config="--psm 7")
        except: pass
        
        count += 1
        
    total_time = time.perf_counter() - start
    return count / total_time

def main():
    print("Starting Smart Filter Benchmark...")
    
    # Create test images
    dark_img = np.zeros((100, 300, 3), dtype=np.uint8) # Pur noir
    light_img = np.ones((100, 300, 3), dtype=np.uint8) * 200 # Blanc (SDR)
    
    engine = BenchVisionEngine({"debug_mode": False})
    
    print("\n[1/2] Benchmarking DARK frame (Filter should SKIP OCR)...")
    dark_fps = run_bench(engine, dark_img, duration=5)
    
    print("[2/2] Benchmarking LIGHT frame (Filter should ALLOW OCR)...")
    light_fps = run_bench(engine, light_img, duration=5)
    
    print("\n" + "="*45)
    print(f"{'Condition':<20} | {'Throughput (FPS)':<20}")
    print("-" * 45)
    print(f"{'Ecran Sombre':<20} | {dark_fps:<20.2f}")
    print(f"{'Ecran avec Texte':<20} | {light_fps:<20.2f}")
    print("=" * 45)
    print(f"Gain de performance : x{dark_fps/light_fps:.1f}")

if __name__ == "__main__":
    main()
