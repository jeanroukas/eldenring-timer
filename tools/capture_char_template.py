
import json
import os
import cv2
import numpy as np
import mss
import time

def capture_template():
    # Load config
    config_path = "data/config.json"
    if not os.path.exists(config_path):
        print("Config file not found.")
        return
        
    with open(config_path, "r") as f:
        config = json.load(f)
        
    region = config.get("char_region")
    if not region:
        print("Error: char_region not found in config.json")
        return

    # Create templates dir
    os.makedirs("data/templates", exist_ok=True)
    
    # Coordinates from PyQt (Global)
    left = int(region["left"])
    top = int(region["top"])
    width = int(region["width"])
    height = int(region["height"])
    
    print(f"Capturing region: {region}")
    
    with mss.mss() as sct:
        # MSS handles global coordinates via the dictionary
        monitor = {
            "top": top,
            "left": left,
            "width": width,
            "height": height
        }
        
        try:
            # Capture
            sct_img = sct.grab(monitor)
            
            # Convert to numpy/opencv
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Save
            save_path = "data/templates/char_select_template.png"
            cv2.imwrite(save_path, img)
            print(f"Successfully saved template to {save_path}")
            
        except Exception as e:
            print(f"Capture failed: {e}")
            print("Ensure coordinates are within virtual screen bounds.")

if __name__ == "__main__":
    time.sleep(1) # Give a second
    capture_template()
