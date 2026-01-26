import cv2
import numpy as np
import os
import json
import time
import sys

# Import project DLL wrapper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.tesseract_api import TesseractAPI

DLL_PATH = r"C:\Program Files\Tesseract-OCR\libtesseract-5.dll"
TESSDATA_PATH = r"C:\Program Files\Tesseract-OCR\tessdata"

def adjust_gamma(image, gamma=1.0):
    if abs(gamma - 1.0) < 0.01: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def analyze_dataset(directory):
    if not os.path.exists(DLL_PATH):
        print(f"Error: DLL not found at {DLL_PATH}")
        return

    # Use PSM 7 for single line detection
    tess = TesseractAPI(DLL_PATH, TESSDATA_PATH, lang="fra", psm=7)
    
    files = [f for f in os.listdir(directory) if f.lower().endswith(".png")]
    print(f"Analyzind {len(files)} images for correlation...")

    # PARAMETER GRID
    # Start with Gamma 2.4 and Threshold 240 as pivot
    gammas = [1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0]
    thresholds = [230, 235, 240, 243, 245, 248, 250, 252]

    correlations = []

    start_time = time.time()
    for idx, filename in enumerate(files):
        img_path = os.path.join(directory, filename)
        img = cv2.imread(img_path)
        if img is None: continue

        # Calculations as requested
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        min_v = int(np.min(gray))
        max_v = int(np.max(gray))
        mean_v = float(np.mean(gray))

        # Target label
        target = "EMPTY"
        if "JOURIII" in filename: target = "JOURIII"
        elif "JOURII" in filename: target = "JOURII"
        elif "JOURI" in filename: target = "JOURI"

        best_config = {"conf": -1}

        # Search for best settings for THIS specific image profile
        for g in gammas:
            g_img = adjust_gamma(gray, g)
            for t in thresholds:
                _, thresh = cv2.threshold(g_img, t, 255, cv2.THRESH_BINARY_INV)
                
                # --- PROTECTION: Ensure image isn't too small/empty for Tesseract ---
                coords = cv2.findNonZero(thresh)
                if coords is None: continue
                
                x, y, w, h = cv2.boundingRect(coords)
                # Tesseract PSM 7 needs a minimum horizontal width (usually 3+).
                # To be safe and silent, we ONLY pass images that actually look like text (w > 20)
                # and we add generous padding.
                if w < 20 or h < 8: continue 

                # Crop to text and Add Padding (helps Tesseract enormously and prevents scale errors)
                cropped = thresh[y:y+h, x:x+w]
                padded = cv2.copyMakeBorder(cropped, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=0)
                
                # Upscale if still small
                if padded.shape[1] < 100:
                    padded = cv2.resize(padded, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)

                text, conf = tess.get_text(padded)
                text_clean = text.upper().replace(" ", "").strip()

                is_valid = False
                if target != "EMPTY":
                    if target in text_clean or "JOUR" in text_clean:
                        is_valid = True
                else:
                    if not text_clean or len(text_clean) < 3:
                        is_valid = True

                if is_valid and conf > best_config["conf"]:
                    best_config = {
                        "gamma": g,
                        "threshold": t,
                        "conf": conf,
                        "text": text_clean
                    }
                    if conf > 90: break # Found high quality setting
            if best_config["conf"] > 90: break

        correlations.append({
            "image": filename,
            "stats": {"min": min_v, "max": max_v, "mean": mean_v},
            "best_params": best_config if best_config["conf"] > 0 else None,
            "target": target
        })

        if idx % 50 == 0:
            print(f"Progress: {idx}/{len(files)}...")

    # Result grouping by Mean Brightness
    print("\n--- CORRELATION SUMMARY ---")
    print(f"{'Mean':<8} | {'Min':<5} | {'Max':<5} | {'Target':<10} | {'Best G':<6} | {'Best T':<6} | {'Conf'}")
    print("-" * 70)
    
    for c in sorted(correlations, key=lambda x: x["stats"]["mean"]):
        p = c["best_params"]
        if p:
            print(f"{c['stats']['mean']:<8.1f} | {c['stats']['min']:<5} | {c['stats']['max']:<5} | {c['target']:<10} | {p['gamma']:<6} | {p['threshold']:<6} | {p['conf']}%")

    with open("debug_images/ocr_correlations.json", "w") as f:
        json.dump(correlations, f, indent=4)

if __name__ == "__main__":
    run_dataset_path = "debug_images/fine tune"
    analyze_dataset(run_dataset_path)
