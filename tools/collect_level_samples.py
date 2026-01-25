import cv2
import numpy as np
import time
import os
import json
from PIL import ImageGrab
import datetime

def collect_samples():
    # Load config to get level region
    config_path = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\data\config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    
    reg = config.get("level_region")
    if not reg:
        print("Error: level_region not found in config.json")
        return

    # Create output directory
    output_dir = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\level_tuning"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Starting collection in 3 seconds...")
    print(f"Target region: {reg}")
    time.sleep(3)
    
    left = reg.get('left', 0)
    top = reg.get('top', 0)
    width = reg.get('width', 50)
    height = reg.get('height', 30)
    
    for i in range(120):
        print(f"Capturing sample {i+1}/120...")
        
        # Capture using PIL (same as VisionEngine)
        try:
            img_pil = ImageGrab.grab(bbox=(left, top, left + width, top + height), all_screens=True)
            img_np = np.array(img_pil)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = os.path.join(output_dir, f"level_{ts}.png")
            cv2.imwrite(filename, img_bgr)
            
        except Exception as e:
            print(f"Failed to capture sample {i}: {e}")
            
        time.sleep(1)
    
    print(f"Done! Collected 120 samples in {output_dir}")

if __name__ == "__main__":
    collect_samples()
