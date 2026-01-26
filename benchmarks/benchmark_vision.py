
import sys
import os
import time
import cv2
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision_engine import VisionEngine
from src.logger import logger

# Mock config
MOCK_CONFIG = {
    "monitor_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    "level_region": {"left": 100, "top": 100, "width": 50, "height": 30},
    "runes_region": {"left": 200, "top": 100, "width": 150, "height": 40},
    "debug_mode": False,
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe"
}

def mock_callback(*args):
    pass

def benchmark():
    print("Initializing VisionEngine...")
    engine = VisionEngine(MOCK_CONFIG)
    
    # Warmup
    print("Warming up...")
    for _ in range(5):
        engine.capture_screen()
        
    print("\nStarting Benchmark (50 frames)...")
    
    start_time = time.time()
    frame_count = 50
    
    capture_times = []
    process_times = []
    
    for i in range(frame_count):
        t0 = time.perf_counter()
        img = engine.capture_screen()
        t1 = time.perf_counter()
        
        if img is not None:
            # Simulate basic processing path
            engine.is_worth_ocr(img)
            engine.preprocess_image(img, pass_type="otsu")
            # We don't run full loop logic to avoid threading chaos, 
            # but we simulate the heavy lifting components.
            
            # Day OCR Simulation (Main)
            if engine.tess_api_main:
                # Create a dummy processed image for OCR
                h, w = img.shape[:2]
                # Resize small to simulate actual ROI or scaled image
                small = cv2.resize(img, (w//4, h//4))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                engine.tess_api_main.get_text(gray)
                
        t2 = time.perf_counter()
        
        capture_times.append(t1 - t0)
        process_times.append(t2 - t1)
        
    total_time = time.time() - start_time
    fps = frame_count / total_time
    
    print(f"\nResults:")
    print(f"Total Time: {total_time:.4f}s")
    print(f"FPS: {fps:.2f}")
    print(f"Avg Capture Time: {np.mean(capture_times)*1000:.2f}ms")
    print(f"Avg Process Time: {np.mean(process_times)*1000:.2f}ms")

if __name__ == "__main__":
    benchmark()
