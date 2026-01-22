import sys
import os
import cv2


# Add src to path to import VisionEngine
sys.path.append(os.path.join(os.getcwd(), 'src'))
from vision_engine import VisionEngine

def verify_fix():
    print("--- Verifying Fix with VisionEngine Class ---")
    
    # Mock Config
    cfg = {
        "monitor_region": {"top": 0, "left": 0, "width": 100, "height": 100},
        "debug_mode": False
    }
    
    engine = VisionEngine(cfg)
    
    test_files = [
        "debug_images/debug_manual_01.png", # JOUR II
        "debug_images/debug_raw_235030.png" # DAY II (reads as DAY I or PAY 1 currently)
    ]
    
    for fpath in test_files:
        if not os.path.exists(fpath):
            continue
            
        print(f"\nProcessing: {fpath}")
        img = cv2.imread(fpath)
        
        # 1. Preprocess
        processed = engine.preprocess_image(img)
        
        # 2. OCR (Simulating the loop)
        import pytesseract
        text = pytesseract.image_to_string(processed, config='--psm 7').strip()
        print(f"Raw OCR: '{text}'")
        
        # 3. Clean
        final = engine.clean_text(text)
        print(f"Final Result: '{final}'")

if __name__ == "__main__":
    verify_fix()
