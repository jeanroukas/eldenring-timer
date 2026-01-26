import sys
import os
import time
import threading

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.vision_engine import VisionEngine

def mock_callback(*args):
    # args: text, width, center_offset, word_data, brightness, score
    text = args[0]
    if text:
        print(f"CALLBACK: '{text}'")

def verify_threading():
    print("TEST: Initializing VisionEngine...")
    config = {
        "monitor_region": {"left": 0, "top": 0, "width": 100, "height": 100},
        "level_region": {"left": 0, "top": 0, "width": 50, "height": 30},
        "runes_region": {"left": 0, "top": 0, "width": 100, "height": 30},
        "debug_mode": True,
        "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    }
    
    engine = VisionEngine(config)
    
    print("TEST: Starting monitoring...")
    engine.start_monitoring(mock_callback)
    
    # Check threads
    print(f"TEST: Main Thread Alive: {engine.thread.is_alive()}")
    print(f"TEST: Secondary Thread Alive: {engine.secondary_thread.is_alive()}")
    
    time.sleep(1.0)
    
    print("TEST: Main Thread Tesseract: ", engine.tess_api_main is not None)
    print("TEST: Secondary Thread Tesseract: ", engine.tess_api_secondary is not None)

    print("TEST: Running for 3 seconds...")
    time.sleep(3)
    
    print("TEST: Stopping...")
    engine.stop()
    time.sleep(1)
    
    if not engine.thread.is_alive() and not engine.secondary_thread.is_alive():
        print("TEST PASSED: Threads stopped.")
    else:
        print("TEST FAILED: Threads still running.")

if __name__ == "__main__":
    verify_threading()
