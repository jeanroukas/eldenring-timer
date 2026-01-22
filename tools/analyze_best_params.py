import cv2
import pytesseract
import os
import glob
import json
import numpy as np
import argparse
import random
import csv

# Config
RAW_DIR = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def load_samples(limit=None):
    files = glob.glob(os.path.join(RAW_DIR, "*.json"))
    samples = []
    
    # Filter only labeled ones
    labeled_files = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                if data.get('manual_label') in ["0", "1", "2", "3"]:
                    labeled_files.append((f, data))
        except: pass

    if limit and limit < len(labeled_files):
        labeled_files = random.sample(labeled_files, limit)
    
    for f, data in labeled_files:
        img_path = f.replace('.json', '.png')
        if os.path.exists(img_path):
            samples.append({
                "id": os.path.basename(f),
                "img_path": img_path,
                "label": data.get('manual_label'),
                "brightness": data.get('brightness', 128)
            })
    return samples

def generate_param_grid(size=20, mode="explore"):
    grid = []
    
    if mode == "refine":
        # Phase 2: Refinement Grid (Deterministic-ish)
        # Winning traits from Phase 1: Scale 1.5+, High Thresholds
        gammas = [0.8, 1.0, 1.2]
        scales = [1.5, 2.0]
        thresholds = [240, 245, 250, 253, 254, 255]
        
        # Generator all combinations (small space: 3*2*6 = 36 combos)
        # We ignore 'size' here to be thorough
        for g in gammas:
            for s in scales:
                for t in thresholds:
                    grid.append({
                        "gamma": g,
                        "type": "fixed",
                        "thresh_val": t,
                        "scale": s
                    })
        return grid

    # Phase 1: Exploration (Random)
    gammas = [0.8, 1.0, 1.2, 1.5, 2.0]
    thresh_types = ["otsu", "fixed", "adaptive", "inverted"]
    fixed_vals = [200, 220, 230, 240, 250, 254]
    
    for _ in range(size):
        p = {
            "gamma": random.choice(gammas),
            "type": random.choice(thresh_types),
            "thresh_val": random.choice(fixed_vals) if "fixed" else 0,
            "scale": random.choice([1.0, 1.5, 2.0])
        }
        if p["type"] == "fixed":
            p["thresh_val"] = random.choice(fixed_vals)
            
        grid.append(p)
        
    return grid

def preprocess(img, params):
    # Scale
    if params["scale"] != 1.0:
        h, w = img.shape[:2]
        img = cv2.resize(img, (int(w*params["scale"]), int(h*params["scale"])))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Gamma
    if params["gamma"] != 1.0:
        invGamma = 1.0 / params["gamma"]
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

    # Invert?
    if params["type"] == "inverted":
        gray = cv2.bitwise_not(gray)
        # Treated as OTSU usually for inverted text
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Thresholds
    elif params["type"] == "otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif params["type"] == "fixed":
        _, thresh = cv2.threshold(gray, params["thresh_val"], 255, cv2.THRESH_BINARY_INV)
    elif params["type"] == "adaptive":
         thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 2)
    else:
        # Default fallback
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
         
    # Morph
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return thresh

def is_correct(text, label):
    t = text.upper()
    # Normalize 'JOURIL' mapping here strictly for analysis? 
    # Or test RAW engine capability? 
    # Let's test RAW capability to find best optical params, 
    # but allow minor fuzzy matches if strictly needed.
    
    if label == "1":
        return "1" in t or "I" in t
    if label == "2":
        return "2" in t or "II" in t or "IL" in t # Accept 'IL' as good enough signal if we use mapping
    if label == "3":
        return "3" in t or "III" in t
    if label == "0":
        return len(t) < 2 # Empty or garbage
        
    return False

def analyze():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--grid", type=int, default=20)
    parser.add_argument("--mode", type=str, default="explore", choices=["explore", "refine"])
    args = parser.parse_args()
    
    print(f"--- Analysis Phase: {args.mode.upper()} ---")
    print(f"Samples: {args.samples} | Grid: {args.grid if args.mode == 'explore' else 'Full Refinement'}")
    
    samples = load_samples(args.samples)
    print(f"Loaded {len(samples)} samples.")
    
    param_grid = generate_param_grid(args.grid, args.mode)
    
    # Store results: [ {brightness, best_conf, best_params...} ]
    results = []
    
    print("Running analysis... (this may take a moment)")
    
    for s in samples:
        img = cv2.imread(s["img_path"])
        if img is None: continue
        
        best_run = None
        best_conf = -1
        
        for p in param_grid:
            try:
                processed = preprocess(img, p)
                
                # Get confidence data
                data = pytesseract.image_to_data(processed, config='--psm 7', output_type=pytesseract.Output.DICT)
                
                # Extract text and average confidence
                conf_list = [int(c) for c in data['conf'] if c != '-1']
                avg_conf = np.mean(conf_list) if conf_list else 0
                
                text_list = [t for t in data['text'] if t.strip()]
                text = " ".join(text_list)
                
                if is_correct(text, s["label"]):
                    # We want the HIGHEST confidence result
                    if avg_conf > best_conf:
                        best_conf = avg_conf
                        best_run = {
                            "text": text,
                            "conf": avg_conf,
                            "params": p
                        }
            except: pass
            
        # Log result for this image
        res = {
            "image": s["id"],
            "brightness": s["brightness"],
            "label": s["label"],
            "success": best_run is not None,
            "best_params": best_run["params"] if best_run else None,
            "conf": best_run["conf"] if best_run else 0
        }
        results.append(res)
        
        status = "OK" if res["success"] else "FAIL"
        p_str = str(res["best_params"]) if res["success"] else "None"
        print(f"[{status}] Br:{s['brightness']:.1f} | Lbl:{s['label']} -> {p_str} (Conf: {res['conf']:.1f})")

    # Summary
    success_count = sum(1 for r in results if r["success"])
    print(f"\nTotal Success Rate: {success_count}/{len(samples)} ({success_count/len(samples)*100:.1f}%)")
    
    # Correlate Brightness to Threshold (if fixed)
    print("\n--- Correlation: Brightness vs Best Threshold (Fixed) ---")
    for r in results:
        if r["success"] and r["best_params"]["type"] == "fixed":
            print(f"Br: {r['brightness']:.1f} -> Thresh: {r['best_params']['thresh_val']}")

if __name__ == "__main__":
    analyze()
