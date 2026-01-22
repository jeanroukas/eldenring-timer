import cv2
import numpy as np
import pytesseract
import os
import glob

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def preprocess_adaptive(img, block_size=101, c=2, gamma=1.0):
    if img is None: return None
    
    # Resize
    h, w = img.shape[:2]
    target_h = 300
    if h != target_h:
        scale = target_h / h
        new_w = int(w * scale)
        img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

    # Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, block_size, c)
    
    # Morphological Closing
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return thresh

def preprocess_fixed(img, thresh_val=200, gamma=1.0):
    if img is None: return None
    
    # Resize
    h, w = img.shape[:2]
    target_h = 300
    if h != target_h:
        scale = target_h / h
        new_w = int(w * scale)
        img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

    # Fixed Thresholding (assuming white text on dark/variable background)
    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
    
    # Morphological Closing
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return thresh

def main():
    debug_dir = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\debug_images"
    raw_images = glob.glob(os.path.join(debug_dir, "debug_raw_*.png"))
    
    if not raw_images:
        print("No raw debug images found.")
        return

    print(f"Testing OCR on {len(raw_images)} images...")
    
    results_dir = "tuning_results"
    os.makedirs(results_dir, exist_ok=True)

    for img_path in raw_images:
        base_name = os.path.basename(img_path).replace("debug_raw_", "").replace(".png", "")
        img = cv2.imread(img_path)
        
        # Variants to test
        variants = [
            ("Adaptive_251_g1.2", lambda i: preprocess_adaptive(i, 251, 2, 1.2)),
            ("Adaptive_151_g1.2", lambda i: preprocess_adaptive(i, 151, 2, 1.2)),
            ("Adaptive_151_g1.0", lambda i: preprocess_adaptive(i, 151, 2, 1.0)),
            ("Adaptive_101_g1.0", lambda i: preprocess_adaptive(i, 101, 2, 1.0)),
            ("Fixed_180_g1.0", lambda i: preprocess_fixed(i, 180, 1.0)),
            ("Fixed_200_g1.2", lambda i: preprocess_fixed(i, 200, 1.2)),
            ("Otsu_g1.0", lambda i: cv2.threshold(cv2.cvtColor(i, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]),
            ("Otsu_g1.2", lambda i: cv2.threshold(cv2.LUT(cv2.cvtColor(i, cv2.COLOR_BGR2GRAY), np.array([((j / 255.0) ** (1/1.2)) * 255 for j in range(256)]).astype("uint8")), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]),
        ]

        for suffix, func in variants:
            processed = func(img)
            text = pytesseract.image_to_string(processed, config='--psm 7').strip()
            print(f"[{base_name}] {suffix}: '{text}'")
            
            # Save processed image for inspection
            cv2.imwrite(os.path.join(results_dir, f"test_{base_name}_{suffix}.png"), processed)

if __name__ == "__main__":
    main()
