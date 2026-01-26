import cv2
import numpy as np
import os
import sys
import time
import csv
import collections
from concurrent.futures import ThreadPoolExecutor

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.tesseract_api import TesseractAPI

# --- Configuration ---
FIXED_THRESHOLD = 240
# Refined search space based on previous run (0.4 was winner)
GAMMAS = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
METHODS = ["FIXED", "OTSU", "ADAPTIVE", "INVERTED"]

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess(gray_img, method, gamma, threshold):
    # 1. Gamma
    g_img = adjust_gamma(gray_img, gamma)
    
    # 2. Method
    if method == "OTSU":
        # Otsu ignores explicit threshold
        _, thresh = cv2.threshold(g_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif method == "FIXED":
        _, thresh = cv2.threshold(g_img, threshold, 255, cv2.THRESH_BINARY_INV)
    elif method == "ADAPTIVE":
        thresh = cv2.adaptiveThreshold(g_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 25, 2)
    elif method == "INVERTED":
        # Inverted Otsu
        inv = cv2.bitwise_not(g_img)
        _, thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        return None
        
    return thresh

def get_image_stats(gray_img):
    return {
        "min": int(np.min(gray_img)),
        "max": int(np.max(gray_img)),
        "mean": float(np.mean(gray_img))
    }

def run_fine_tuning(directory, max_images=1000):
    print(f"--- Advanced Fine Tuning (Threshold={FIXED_THRESHOLD}) ---")
    
    # 1. Setup Resources
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    words_file = os.path.join(project_root, "data", "ocr_words.txt")
    dll_path = r"C:\Program Files\Tesseract-OCR\libtesseract-5.dll"
    tessdata_path = r"C:\Program Files\Tesseract-OCR\tessdata"
    
    if not os.path.exists(words_file):
        print("Words file missing!")
        return

    # Load Words
    allowed_words = set()
    with open(words_file, 'r') as f:
        for line in f:
            w = line.strip().upper()
            if w: allowed_words.add(w)
            
    # Init Tesseract
    tess_vars = {
        "load_system_dawg": "0", 
        "load_freq_dawg": "0", 
        "user_words_file": words_file
    }
    # Allow alphanumeric + space
    allowlist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
    
    try:
        tess = TesseractAPI(dll_path, tessdata_path, lang="eng", allowlist=allowlist, psm=7, variables=tess_vars)
    except Exception as e:
        print(f"Tesseract Init Failed: {e}")
        return

    # 2. Load Files
    files = [f for f in os.listdir(directory) if f.lower().endswith(".png")]
    files = [f for f in files if "JOUR" in f] # Filter for relevant samples
    files = files[:max_images]
    print(f"Processing {len(files)} samples...")

    results = []
    start_time = time.time()

    for i, filename in enumerate(files):
        img_path = os.path.join(directory, filename)
        img = cv2.imread(img_path)
        if img is None: continue
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        stats = get_image_stats(gray)
        
        # Determine Ground Truth
        target = "UNKNOWN"
        if "JOURII" in filename or "JOUR II" in filename: target = "JOUR II"
        elif "JOURIII" in filename: target = "JOUR III"
        elif "JOURI" in filename or "JOUR I" in filename: target = "JOUR I"
        
        # Best result container
        best_run = {"conf": -1, "text": "", "method": "", "gamma": 0, "match": False}
        
        # Grid Search
        for method in METHODS:
            for gamma in GAMMAS:
                thresh_img = preprocess(gray, method, gamma, FIXED_THRESHOLD)
                
                # Safety Checks
                coords = cv2.findNonZero(thresh_img)
                if coords is None: continue
                _,_,w,h = cv2.boundingRect(coords)
                if w < 10 or h < 5: continue
                
                # OCR
                text, conf = tess.get_text(thresh_img)
                clean = text.strip().upper()
                
                # Check Match
                is_match = False
                if target != "UNKNOWN":
                    # Looser matching: check if target substring exists
                    norm_clean = clean.replace(" ", "")
                    norm_target = target.replace(" ", "")
                    if norm_target in norm_clean:
                        is_match = True
                elif clean in allowed_words and conf > 80:
                    is_match = True
                    
                # Update Best
                if is_match:
                    if conf > best_run["conf"]:
                        best_run = {"conf": conf, "text": clean, "method": method, "gamma": gamma, "match": True}
                elif not best_run["match"] and conf > best_run["conf"]:
                     best_run = {"conf": conf, "text": clean, "method": method, "gamma": gamma, "match": False}

        results.append({
            "file": filename,
            "min": stats["min"],
            "max": stats["max"],
            "mean": stats["mean"],
            "best_method": best_run["method"],
            "best_gamma": best_run["gamma"],
            "conf": best_run["conf"],
            "text": best_run["text"],
            "success": best_run["match"]
        })
        
        sys.stdout.write(".")
        sys.stdout.flush()

    print(f"\nDone in {time.time()-start_time:.1f}s")

    # 3. CSV Export
    csv_path = "tuning_advanced.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["file", "min", "max", "mean", "best_method", "best_gamma", "conf", "text", "success"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved to {csv_path}")

    # 4. Correlation Analysis
    print("\n--- Correlation Analysis (Stats -> Best Settings) ---")
    # Group by Mean Brightness
    buckets = {
        "Dark (<70)": [],
        "Mid (70-150)": [],
        "Bright (>150)": []
    }
    
    successful_results = [r for r in results if r["success"]]
    
    for r in successful_results:
        m = r["mean"]
        if m < 70: buckets["Dark (<70)"].append(r)
        elif m <= 150: buckets["Mid (70-150)"].append(r)
        else: buckets["Bright (>150)"].append(r)
        
    for name, items in buckets.items():
        if not items:
            print(f"\n{name}: No samples")
            continue
            
        print(f"\n{name} (N={len(items)}):")
        
        # Stats
        methods = [r["best_method"] for r in items]
        gammas = [r["best_gamma"] for r in items]
        
        top_method = collections.Counter(methods).most_common(1)[0]
        top_gamma = collections.Counter(gammas).most_common(1)[0]
        
        print(f"  Best Method: {top_method[0]} ({top_method[1]} hits)")
        print(f"  Best Gamma:  {top_gamma[0]} ({top_gamma[1]} hits)")


if __name__ == "__main__":
    target_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_images", "fine tune")
    run_fine_tuning(target_dir, max_images=1000)
