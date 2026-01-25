import json
import os
import sys
from PIL import ImageGrab
from datetime import datetime

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.services.config_service import ConfigService

def main():
    print("Initializing Config Service...")
    c = ConfigService()
    c.initialize()
    
    # 1. Get Regions
    monitor_region = c.get("monitor_region")
    level_region = c.get("level_region")
    
    print(f"\n[CONFIG] Monitor Region: {monitor_region}")
    print(f"[CONFIG] Level Region: {level_region}")
    
    # 2. Capture Full Screen (for reference coordinate check)
    # Note: ImageGrab.grab(all_screens=True) works on recent Pillow versions
    try:
        full = ImageGrab.grab(all_screens=True)
        print(f"\n[CAPTURE] Virtual Screen Size: {full.size}")
        full.save("debug_full_screen.png")
        print(" Saved 'debug_full_screen.png'")
    except Exception as e:
        print(f" Failed to capture full screen: {e}")
        return

    # 3. Extract Regions
    # Note: Pillow crop is relative to the image size. 
    # If all_screens=True, (0,0) is top-left of the virtual desktop (which might be negative in OS coords?)
    # Wait, ImageGrab.grab(all_screens=True) aligns (0,0) to top-left of combined rect.
    # BUT our `monitor_region` is likely in Windows Virtual Desktop coordinates (which can be negative).
    # We need to offset them to the image coordinates if Top/Left < 0.
    
    # Assuming ImageGrab.grab(bbox=None, all_screens=True) returns image starting at Virtual Top-Left?
    # Let's check region capture specifically.
    
    if monitor_region:
        save_region_snapshot(monitor_region, "debug_monitor_region.png")
        
    if level_region:
        save_region_snapshot(level_region, "debug_level_region.png")
        
    print("\nPlease inspect the generated .png files to verify what the OCR sees.")


try:
    import pytesseract
    # Try to find tesseract binary if not in path
    tess_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    ]
    for p in tess_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
except ImportError:
    pytesseract = None

def save_region_snapshot(region, filename):
    try:
        x = region.get('left')
        y = region.get('top')
        w = region.get('width')
        h = region.get('height')
        
        if x is None or y is None or w is None or h is None:
            print(f" Invalid region data for {filename}")
            return

        print(f" Capturing {filename} at ({x}, {y}, {w}x{h})...")
        
        # ImageGrab expects (left, top, right, bottom)
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        img.save(filename)
        print(f" Saved {filename}")
        
        # Try OCR
        if pytesseract:
            print(f"   Running OCR on {filename}...")
            # Pre-processing similar to engine
            import cv2
            import numpy as np
            img_np = np.array(img)
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Text Only
            text = pytesseract.image_to_string(thresh, config='--psm 7').strip()
            print(f"   [OCR RESULT] '{text}'")
            
            # Digits Only (for Level)
            digits = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()
            print(f"   [DIGITS ONLY] '{digits}'")
            
    except Exception as e:
        print(f" FAILED to save/ocr {filename}: {e}")

if __name__ == "__main__":
    main()
