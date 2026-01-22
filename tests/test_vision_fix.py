import sys
import os
sys.path.append(os.getcwd())
from src.vision_engine import VisionEngine
from src.config import load_config

print("Testing VisionEngine initialization...")
try:
    config = load_config()
    # Mock region if needed
    if not config.get("monitor_region"):
        config["monitor_region"] = {"top": 0, "left": 0, "width": 100, "height": 100}
        
    ve = VisionEngine(config)
    print("VisionEngine initialized successfully.")
    
    # Test internal method that caused error
    # The error happened in _loop -> pytesseract.image_to_data call which uses the config string
    # We can try to simulate a call if possible, or just check the string construction if it was in __init__? 
    # No, it was in _loop.
    # But the error "No closing quotation" likely comes from shlex.split() or similar inside pytesseract when PARSING the config string.
    
    # The crash happenend during the loop.
    # Let's try to run a purely synthetic OCR call on a dummy image to see if pytesseract accepts the config string.
    import cv2
    import numpy as np
    import pytesseract
    
    dummy_img = np.zeros((100, 300, 3), dtype=np.uint8)
    # create white text
    cv2.putText(dummy_img, "TEST", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    processed = ve.preprocess_image(dummy_img, pass_type="otsu")
    
    # This is the line that failed:
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
    # custom_config = f'--psm 7 -c tessedit_char_whitelist="{whitelist}"' 
    # ^ This was the bug.
    
    # In the fixed code it is:
    custom_config = r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7'
    
    print(f"Testing config: {custom_config}")
    data = pytesseract.image_to_data(processed, config=custom_config, output_type=pytesseract.Output.DICT)
    print("OCR Call successful.")

except Exception as e:
    print(f"Test Failed: {e}")
