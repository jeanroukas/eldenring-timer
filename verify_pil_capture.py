
import json
import cv2
import numpy as np
from PIL import ImageGrab
import os
import time

def test_capture():
    print("Loading config...")
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    reg = config.get("monitor_region", {})
    print(f"Config Region: {reg}")

    print("Attempting PIL Capture (all_screens=True)...")
    try:
        start_time = time.time()
        full_img = ImageGrab.grab(all_screens=True)
        print(f"Full Image Size: {full_img.size} captured in {time.time() - start_time:.4f}s")
        
        # Crop logic
        left = reg.get('left', 0)
        top = reg.get('top', 0)
        width = reg.get('width', 100)
        height = reg.get('height', 100)
        
        box = (left, top, left + width, top + height)
        print(f"Cropping to box: {box}")
        
        cropped = full_img.crop(box)
        img_np = np.array(cropped)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        if not os.path.exists("debug_images"):
            os.makedirs("debug_images")
            
        filename = f"debug_images/manual_pil_test_{int(time.time())}.png"
        cv2.imwrite(filename, img_bgr)
        print(f"Saved capture to {filename}")
        
        avg_brightness = np.mean(img_bgr)
        print(f"Average Brightness: {avg_brightness:.2f}")
        
    except Exception as e:
        print(f"PIL Capture Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_capture()
