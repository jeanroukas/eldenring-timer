import cv2
import pytesseract
import os
import glob
import json
import numpy as np

# Config
RAW_DIR = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def load_samples():
    files = glob.glob(os.path.join(RAW_DIR, "*.json"))
    samples = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                label = data.get('manual_label')
                # Only use samples that have a manual label 0, 1, 2, 3
                if label in ["0", "1", "2", "3"]:
                    img_path = f.replace('.json', '.png')
                    if os.path.exists(img_path):
                        samples.append({
                            "img_path": img_path,
                            "label": label,
                            "brightness": data.get('brightness', 128)
                        })
        except: pass
    return samples

def preprocess(img, brightness, p_type="otsu", gamma=1.0, thresh_val=230):
    # Resize
    h, w = img.shape[:2]
    target_h = 100 # Tuning target
    scale = target_h / h
    img = cv2.resize(img, (int(w*scale), target_h))
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Gamma
    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

    # Threshold
    if p_type == "otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif p_type == "fixed":
        _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
    elif p_type == "adaptive":
         thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 2)
         
    # Morph
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return thresh

def clean_text(text):
    import re
    # Match engine logic
    match = re.search(r'[A-Z0-9].*[A-Z0-9]', text.upper())
    if match: return match.group(0)
    match = re.search(r'[A-Z0-9]', text.upper())
    if match: return match.group(0)
    return ""

def score_text(text, label):
    # Heuristic scoring
    t = text.upper()
    if label == "1":
        return 1 if t in ["JOUR I", "JOURI", "JOUR 1"] else 0
    if label == "2":
        return 1 if t in ["JOUR II", "JOURII", "JOUR 11", "JOUR 2"] else 0
    if label == "3":
        return 1 if t in ["JOUR III", "JOURIII", "JOUR 3"] else 0
    if label == "0":
        # Should be empty or irrelevant
        # If we detect JOUR I/II here it's a fail
        if "JOUR" in t: return 0
        return 1
    return 0

def run_tuning():
    samples = load_samples()
    print(f"Loaded {len(samples)} valid samples for tuning.")
    
    # Grid Search
    gammas = [1.0, 1.2, 1.5]
    thresholds = [200, 220, 230, 240, 250] 
    modes = ["otsu", "fixed"]
    
    results = []
    
    for mode in modes:
        ts_list = thresholds if mode == "fixed" else [0]
        for t_val in ts_list:
            for g in gammas:
                config_name = f"{mode}_t{t_val}_g{g}"
                
                score_sum = 0
                sample_count = 0
                
                # Evaluation
                for s in samples:
                    # Only evaluate relevant brightness for fixed threshold logic?
                    # No, let's see which one is universally best or best per bucket
                    
                    img = cv2.imread(s['img_path'])
                    if img is None: continue
                    
                    processed = preprocess(img, s['brightness'], mode, g, t_val)
                    
                    # OCR
                    custom_config = r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7'
                    data = pytesseract.image_to_string(processed, config=custom_config)
                    text = clean_text(data)
                    
                    # Simple accuracy check
                    # We accept common partials for now to measure "clarity"
                    # But strict scoring for "Success"
                    if score_text(text, s['label']):
                        score_sum += 1
                    
                    sample_count += 1
                
                acc = (score_sum / sample_count) * 100 if sample_count > 0 else 0
                print(f"Config {config_name}: Acc={acc:.1f}%")
                results.append((config_name, acc))
    
    # Sort
    results.sort(key=lambda x: x[1], reverse=True)
    print("\n=== TOP 5 CONFIGS ===")
    for r in results[:5]:
        print(f"{r[0]}: {r[1]:.1f}%")

if __name__ == "__main__":
    run_tuning()
