import sys
import os
import time
import cv2

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from vision_engine import VisionEngine

def main():
    print("Starting Live Vision Debugger...")
    
    config = {
        "monitor_region": {
            "top": 1093,
            "left": 1500,
            "width": 832,
            "height": 224
        },
        "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        "debug_mode": True,
        "save_raw_samples": True, # Force save
        "hdr_mode": True
    }
    
    engine = VisionEngine(config)
    
    print("Engine initialized. Starting scan loop (Press Ctrl+C to stop)...")
    
    try:
        while True:
            img = engine.capture_screen()
            if img is None:
                print("Capture failed (None)")
                time.sleep(0.5)
                continue
                
            # Manually run the pipeline steps to debug
            brightness = engine.calc_brightness(img) if hasattr(engine, 'calc_brightness') else 0
            if not hasattr(engine, 'calc_brightness'):
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                brightness = float(gray.mean())
                
            print(f"Brightness: {brightness:.2f}")

            # Mimic process logic
            passes = ["fixed", "otsu"]
            if brightness > 220:
                print(" -> High Brightness Detected! Switching to [otsu, high_fixed]")
                passes = ["otsu", "high_fixed"]
            
            for p_type in passes:
                processed = engine.preprocess_image(img, pass_type=p_type)
                
                # Run OCR
                custom_config = r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7'
                import pytesseract
                try:
                    text = pytesseract.image_to_string(processed, config=custom_config).strip()
                    clean = engine.clean_text(text)
                    relevant = engine.is_relevant(clean)
                    print(f"   Pass [{p_type}]: Raw='{text}' | Clean='{clean}' | Relevant={relevant}")
                except Exception as e:
                    print(f"   Pass [{p_type}]: Error {e}")

            time.sleep(1.0) # Slow loop
            
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    main()
