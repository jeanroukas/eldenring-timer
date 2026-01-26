import cv2
import mss
import numpy as np
import time
import os
import json

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "config.json")
    with open(config_path, "r") as f:
        return json.load(f)

def capture_samples():
    config = load_config()
    # Try to load the manually defined icon region first
    icon_region = config.get("runes_icon_region", {})
    
    if icon_region and icon_region.get("width", 0) > 0:
        monitor = {
            "top": int(icon_region["top"]),
            "left": int(icon_region["left"]),
            "width": int(icon_region["width"]),
            "height": int(icon_region["height"])
        }
        print(f"Using defined attributes for Icon Region: {monitor}")
    else:
        print("WARNING: 'runes_icon_region' not found in config. Attempting auto-guess...")
        runes_region = config.get("runes_region", {})
        if not runes_region:
            print("ERROR: Runes region not defined either. Please configure regions in settings.")
            return

        # Define Icon Region based on Runes Region (Fallback)
        icon_width = 50
        icon_height = runes_region["height"]
        icon_left = runes_region["left"] - icon_width - 5 
        icon_top = runes_region["top"]
        
        monitor = {
            "top": int(icon_top),
            "left": int(icon_left),
            "width": int(icon_width),
            "height": int(icon_height)
        }
    
    save_dir = os.path.join(os.path.dirname(__file__), "..", "samples", "icon_raw")
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"Starting Capture in 3 seconds... ROI: {monitor}")
    print("Please perform typical actions: Menu, Map, Running, Standing still...")
    time.sleep(3)
    
    start_time = time.time()
    count = 0
    duration = 120 # 2 minutes
    
    with mss.mss() as sct:
        while time.time() - start_time < duration:
            # Capture
            img = np.array(sct.grab(monitor))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Save
            timestamp = int(time.time() * 1000)
            filename = os.path.join(save_dir, f"icon_{timestamp}.png")
            cv2.imwrite(filename, img)
            
            count += 1
            if count % 10 == 0:
                print(f"Captured {count} frames... ({int(duration - (time.time() - start_time))}s remaining)")
            
            time.sleep(0.1) # 10 FPS capture
            
    print(f"Finished. Captured {count} samples in {save_dir}")

if __name__ == "__main__":
    capture_samples()
