
import cv2
import numpy as np
from PIL import ImageGrab
import bettercam
import time
import os

def analyze(name, img):
    if img is None:
        print(f"[{name}] Capture returned None")
        return
    
    # Convert if needed
    if len(img.shape) == 3 and img.shape[2] == 3:
        pass # assume BGR or RGB
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = np.mean(gray)
    max_val = np.max(gray)
    min_val = np.min(gray)
    
    # Histogram analysis for high values
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    high_vals = hist[250:]
    print(f"[{name}] Size: {img.shape}, Mean: {mean_val:.2f}, Max: {max_val}, Min: {min_val}")
    print(f"[{name}] Histogram [250-255]: {high_vals.flatten().astype(int)}")

    
    timestamp = int(time.time())
    fname = f"debug_images/diag_{name}_{timestamp}.png"
    cv2.imwrite(fname, img)
    print(f"[{name}] Saved to {fname}")

def main():
    if not os.path.exists("debug_images"):
        os.makedirs("debug_images")

    print("--- Starting Diagnosis ---")
    
    # 1. PIL
    print("Testing PIL...")
    try:
        pil_img = ImageGrab.grab()
        img_np = np.array(pil_img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        analyze("PIL", img_bgr)
    except Exception as e:
        print(f"PIL Failed: {e}")

    # 2. BetterCam
    print("Testing BetterCam...")
    try:
        camera = bettercam.create(device_idx=0, output_idx=0)
        time.sleep(1) # Warmup
        frame = camera.grab()
        if frame is not None:
             img_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
             analyze("BetterCam", img_bgr)
        else:
             print("BetterCam grabbed None")
        camera.stop()
    except Exception as e:
        print(f"BetterCam Failed: {e}")

if __name__ == "__main__":
    main()
