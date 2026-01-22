import mss
import cv2
import numpy as np
import time
import os
import json
import keyboard
import threading
from datetime import datetime

# Load configuration for region
try:
    with open("config.json", "r") as f:
        config = json.load(f)
        region = config.get("monitor_region")
except Exception as e:
    print(f"Error loading config.json: {e}")
    region = {"top": 0, "left": 0, "width": 800, "height": 600} # Default fallback

if not region:
    print("Region not found in config.json. Please check your configuration.")
    exit(1)

OUTPUT_DIR = "debug_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=== Elden Ring Nightreign - Data Collector ===")
print(f"Region: {region}")
print("Usage:")
print("  Press 'S' to start a 3-second capture burst (approx 10-15 images).")
print("  Press 'Q' to quit.")
print("==============================================")

def capture_burst():
    print("\n[STARTED] Capturing burst for 3 seconds...")
    start_time = time.time()
    count = 0
    
    with mss.mss() as sct:
        while time.time() - start_time < 3.0:
            # Capture
            img = np.array(sct.grab(region))
            
            # Save
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = os.path.join(OUTPUT_DIR, f"sample_{ts}.png")
            
            # Save as PNG
            # mss returns BGRA, opencv handles it fine for saving png
            cv2.imwrite(filename, img)
            
            count += 1
            time.sleep(0.2) # Approx 5 fps
            
    print(f"[FINISHED] Burst complete. Saved {count} images to {OUTPUT_DIR}")

def main():
    while True:
        try:
            if keyboard.is_pressed('q'):
                print("Exiting...")
                break
            
            if keyboard.is_pressed('s'):
                capture_burst()
                # Debounce to prevent multiple triggers
                time.sleep(1)
                print("Ready for next capture.")
                
            time.sleep(0.05)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
