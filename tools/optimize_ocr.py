import cv2
import pytesseract
import os
import glob
import numpy as np

# Configuration
# Configuration
INPUT_DIR = os.path.join("samples", "raw")
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Parameters to search
TARGET_HEIGHTS = [150] # Standardize on 150
THRESHOLDS = [-1, 180, 200, 230] # -1 for Otsu, plus fixed candidates
INVERT_OPTIONS = [True, False]
GAMMAS = [1.0] # Default gamma

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess(img, target_h, threshold, invert, gamma):
    # Resize
    h, w = img.shape[:2]
    scale = target_h / h
    new_w = int(w * scale)
    resized = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA)
    
    # Gray
    if len(resized.shape) == 3:
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    else:
        gray = resized

    # Gamma
    gray = adjust_gamma(gray, gamma)

    # Threshold
    if threshold == -1:
        # Otsu
        _, thresh_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, thresh_img = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    # Invert
    if invert:
        thresh_img = cv2.bitwise_not(thresh_img)
        
    return thresh_img

def run_optimization():
    images = glob.glob(os.path.join(INPUT_DIR, "*.png"))
    
    import random
    random.seed(42) # For reproducibility
    
    # Use all images or a larger subset
    if len(images) > 10: 
        images = random.sample(images, 10)
    
    print(f"Loaded {len(images)} images for optimization.")
    
    results = {} # key: (h, t, inv, g), value: list of texts

    total_combinations = len(TARGET_HEIGHTS) * len(THRESHOLDS) * len(INVERT_OPTIONS) * len(GAMMAS)
    print(f"Testing {total_combinations} combinations per image...")

    for i, img_path in enumerate(images):
        print(f"Processing image {i+1}/{len(images)}: {os.path.basename(img_path)}")
        original_img = cv2.imread(img_path)
        if original_img is None: continue
        
        for h in TARGET_HEIGHTS:
            for t in THRESHOLDS:
                for inv in INVERT_OPTIONS:
                    for g in GAMMAS:
                        processed = preprocess(original_img, h, t, inv, g)
                        
                        # OCR
                        config = '--psm 7'
                        try:
                            text = pytesseract.image_to_string(processed, config=config).strip()
                            clean_text = text.replace('\n', ' ').strip()
                        except:
                            clean_text = ""
                        
                        key = (h, t, inv, g)
                        if key not in results:
                            results[key] = []
                        results[key].append(clean_text)

    # Scoring (Heuristic) - Updated for French
    # "JOUR 1", "JOUR 2", "TEMPETE", "APAISEMENT"? 
    
    keywords = ["JOUR", "JOURNEE", "1", "2", "I", "II", "TEMPETE"] 
    
    scores = {}
    
    for key, texts in results.items():
        score = 0
        valid_reads = 0
        
        for text in texts:
            upper_text = text.upper()
            
            # Simple scoring
            if "JOUR" in upper_text: score += 10
            elif "IOUR" in upper_text: score += 5 # Partial typo
            
            if "TEMPETE" in upper_text: score += 10
            
            # Numerals
            if "JOUR 1" in upper_text or "JOUR I" in upper_text: score += 5
            if "JOUR 2" in upper_text or "JOUR II" in upper_text: score += 5
            
            # Bonus for clean length (e.g. "JOUR I" is 6 chars)
            if 4 <= len(upper_text) <= 10:
                 valid_reads += 1
            
        scores[key] = score + valid_reads # Tie breaker

    # Find winner
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    
    print("\n\n=== TOP 5 CONFIGURATIONS ===")
    for k in sorted_keys[:5]:
        h, t, inv, g = k
        print(f"Score: {scores[k]} | Height: {h}, Thresh: {t}, Invert: {inv}, Gamma: {g}")
        # Sample output for this config
        print(f"  Sample Texts: {results[k][:5]}") # Print first 5 texts
        
    best = sorted_keys[0]
    print(f"\nWINNER: Height: {best[0]}, Thresh: {best[1]}, Invert: {best[2]}, Gamma: {best[3]}")
    
    # Save the winner processing for the first image as debug
    if len(images) > 0:
        first_img = cv2.imread(images[0])
        best_proc = preprocess(first_img, best[0], best[1], best[2], best[3])
        cv2.imwrite("debug_images/winner_preview.png", best_proc)
        print("Saved 'debug_images/winner_preview.png' for verification.")

if __name__ == "__main__":
    run_optimization()
