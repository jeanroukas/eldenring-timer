import cv2
import numpy as np
import pytesseract
import os
import time
import json
from itertools import product

# Configure Tesseract path if needed (will try default first)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def adjust_gamma(image, gamma=1.0):
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess(img, method="otsu", gamma=1.0, scale=2.0):
    # 1. Resize
    h, w = img.shape[:2]
    img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    
    # 2. Gray
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. Gamma
    if gamma != 1.0:
        gray = adjust_gamma(gray, gamma)
    
    # 4. Threshold
    if method == "otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif method == "fixed_200":
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    elif method == "fixed_150":
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    elif method == "adaptive":
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    else:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
    return thresh

def tune():
    samples_dir = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\level_tuning"
    if not os.path.exists(samples_dir):
        print(f"Error: Samples directory not found: {samples_dir}")
        return

    files = [f for f in os.listdir(samples_dir) if f.endswith('.png')]
    if not files:
        print("No samples found.")
        return

    # Define search space
    gammas = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
    methods = ["otsu", "fixed_200", "fixed_150", "adaptive"]
    scales = [1.5, 2.0, 2.5]
    
    combinations = list(product(gammas, methods, scales))
    results = []

    print(f"Analyzing {len(files)} samples with {len(combinations)} combinations...")

    for gamma, method, scale in combinations:
        success_count = 0
        total_digits = 0
        
        for f in files:
            img = cv2.imread(os.path.join(samples_dir, f))
            processed = preprocess(img, method=method, gamma=gamma, scale=scale)
            
            # OCR Digits only
            config = r'--psm 7 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(processed, config=config).strip()
            
            if text and text.isdigit():
                success_count += 1
                total_digits += len(text)
        
        results.append({
            "gamma": gamma,
            "method": method,
            "scale": scale,
            "success_rate": success_count / len(files),
            "avg_digits": total_digits / success_count if success_count > 0 else 0
        })
        print(f"Tested: Gamma={gamma}, Method={method}, Scale={scale} -> Success: {success_count}/{len(files)}")

    # Sort by success rate and avg digits (longer strings usually mean better level detection)
    results.sort(key=lambda x: (x["success_rate"], x["avg_digits"]), reverse=True)

    best = results[0]
    print("\n--- BEST CONFIGURATION ---")
    print(f"Gamma: {best['gamma']}")
    print(f"Method: {best['method']}")
    print(f"Scale: {best['scale']}")
    print(f"Success Rate: {best['success_rate']:.2%}")
    
    # Save best config
    with open("level_ocr_best_config.json", "w") as f:
        json.dump(best, f, indent=4)

if __name__ == "__main__":
    tune()
