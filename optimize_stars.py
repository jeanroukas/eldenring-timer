import cv2
import numpy as np
import pytesseract
import os
import itertools

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def optimize():
    image_path = "debug_images/debug_raw_060130.png"
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load {image_path}")
        return

    # Parameter space
    scales = [1.5, 2.0, 3.0]
    bilaterals = [0, 5, 9] # d parameter (0 = off)
    thresholds = ["otsu", "adaptive_101", "adaptive_201"]
    c_constants = [2, 5, 10]
    morphs = [None, "close_2x2", "close_3x3"]
    gammas = [0.8, 1.0]

    results = []
    
    combinations = list(itertools.product(scales, bilaterals, thresholds, c_constants, morphs, gammas))
    print(f"Testing {len(combinations)} combinations...")

    for scale, d, thresh_type, c, morph, gamma in combinations:
        # 1. Resize
        h, w = img.shape[:2]
        new_h = int(h * scale)
        new_w = int(w * scale)
        proc = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        # 2. Gamma
        gray = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
        if gamma != 1.0:
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            gray = cv2.LUT(gray, table)

        # 3. Bilateral Filter
        if d > 0:
            gray = cv2.bilateralFilter(gray, d, 75, 75)

        # 4. Threshold
        if thresh_type == "otsu":
            _, final = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            block = int(thresh_type.split("_")[1])
            final = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, c)

        # 5. Morph
        if morph == "close_2x2":
            kernel = np.ones((2,2), np.uint8)
            final = cv2.morphologyEx(final, cv2.MORPH_CLOSE, kernel)
        elif morph == "close_3x3":
            kernel = np.ones((3,3), np.uint8)
            final = cv2.morphologyEx(final, cv2.MORPH_CLOSE, kernel)

        # 6. OCR
        # We test both PSM 7 (line) and PSM 8 (word)
        text = pytesseract.image_to_string(final, config='--psm 7').strip()
        
        if "JOUR I" in text.upper():
            score = 100
            if text.upper() == "JOUR I": score = 1000 # Perfect!
            results.append({
                "score": score,
                "text": text,
                "params": (scale, d, thresh_type, c, morph, gamma)
            })

    # Sort results
    results.sort(key=lambda x: x["score"], reverse=True)
    
    print("\n--- TOP RESULTS ---")
    for r in results[:10]:
        print(f"Score: {r['score']} | Text: '{r['text']}' | Params: {r['params']}")

    if results:
        best = results[0]
        print(f"\nWinning Params: {best['params']}")
        # Re-run and save the best image
        # ... (manual verification)

if __name__ == "__main__":
    optimize()
