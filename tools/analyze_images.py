import cv2
import numpy as np

def analyze_image(path):
    img = cv2.imread(path)
    if img is None:
        print(f"Could not read {path}")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    avg_brightness = np.mean(gray)
    max_val = np.max(gray)
    min_val = np.min(gray)
    white_ratio = np.sum(gray > 250) / gray.size
    black_ratio = np.sum(gray < 5) / gray.size
    
    print(f"Analysis for {path}:")
    print(f" - Avg Brightness: {avg_brightness:.2f}")
    print(f" - Min/Max: {min_val}/{max_val}")
    print(f" - White Ratio (>250): {white_ratio:.2%}")
    print(f" - Black Ratio (<5): {black_ratio:.2%}")

if __name__ == "__main__":
    import os
    for f in ["wgc_mon1_raw.png", "pil_debug_raw.png"]:
        if os.path.exists(f):
            analyze_image(f)
