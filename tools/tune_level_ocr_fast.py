import cv2
import numpy as np
import os
import time
import json
from itertools import product
import sys

# Add src to path to import TesseractAPI
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.tesseract_api import TesseractAPI

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess(img, method="otsu", gamma=1.0, scale=2.0):
    h, w = img.shape[:2]
    img_resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    
    if gamma != 1.0:
        gray = adjust_gamma(gray, gamma)
    
    if method == "otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif method == "fixed_200":
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    elif method == "fixed_230":
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
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

    # Tesseract DLL setup
    dll_path = r"C:\Program Files\Tesseract-OCR\libtesseract-5.dll"
    tessdata_path = r"C:\Program Files\Tesseract-OCR\tessdata"
    
    try:
        tess = TesseractAPI(dll_path, tessdata_path, lang="fra")
        # Ensure whitelist for digits only
        tess.lib.TessBaseAPISetVariable(tess.handle, b"tessedit_char_whitelist", b"0123456789")
    except Exception as e:
        print(f"Error initializing Tesseract DLL: {e}")
        return

    # Search space
    gammas = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    methods = ["otsu", "fixed_200", "fixed_230"]
    scales = [1.5, 2.0, 2.5]
    
    combinations = list(product(gammas, methods, scales))
    results = []

    print(f"Fast Tuning with DLL: Analyzing {len(files)} samples with {len(combinations)} combinations...")
    start_time = time.time()

    for gamma, method, scale in combinations:
        success_count = 0
        total_digits = 0
        
        for f in files:
            img = cv2.imread(os.path.join(samples_dir, f))
            processed = preprocess(img, method=method, gamma=gamma, scale=scale)
            
            # Use DLL API
            text, conf = tess.get_text(processed)
            text = text.strip()
            
            if text and text.isdigit():
                success_count += 1
                total_digits += len(text)
        
        rate = success_count / len(files)
        results.append({
            "gamma": gamma,
            "method": method,
            "scale": scale,
            "success_rate": rate,
            "avg_digits": total_digits / success_count if success_count > 0 else 0
        })
        # print(f"G={gamma}, M={method}, S={scale} -> {success_count}/{len(files)}")

    duration = time.time() - start_time
    print(f"Tuning finished in {duration:.1f} seconds.")

    # Sort results
    results.sort(key=lambda x: (x["success_rate"], x["avg_digits"]), reverse=True)

    best = results[0]
    print("\n--- BEST CONFIGURATION (DLL) ---")
    print(f"Gamma: {best['gamma']}")
    print(f"Method: {best['method']}")
    print(f"Scale: {best['scale']}")
    print(f"Success Rate: {best['success_rate']:.2%}")
    
    with open("level_ocr_best_config.json", "w") as f:
        json.dump(best, f, indent=4)
    
    print("\nTop 5 results:")
    for i in range(min(5, len(results))):
        r = results[i]
        print(f"{i+1}. G={r['gamma']}, M={r['method']}, S={r['scale']} -> {r['success_rate']:.1%}")

if __name__ == "__main__":
    tune()
