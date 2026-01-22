import cv2
import numpy as np
import pytesseract
import os
import glob
from src.pattern_manager import PatternManager

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def preprocess_adaptive(img, block_size=101, c=2, gamma=1.0):
    if img is None: return None
    h, w = img.shape[:2]
    target_h = 300
    scale = target_h / h
    new_w = int(w * scale)
    img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, c)
    return thresh

def preprocess_otsu(img, gamma=1.0):
    if img is None: return None
    h, w = img.shape[:2]
    target_h = 300
    scale = target_h / h
    new_w = int(w * scale)
    img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return thresh

def preprocess_fixed(img, thresh_val=200, gamma=1.0):
    if img is None: return None
    h, w = img.shape[:2]
    target_h = 300
    scale = target_h / h
    new_w = int(w * scale)
    img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)
    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
    return thresh

def main():
    debug_dir = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\debug_images"
    raw_images = glob.glob(os.path.join(debug_dir, "debug_raw_*.png"))
    pm = PatternManager()
    
    print("--- Testing 3-Pass Strategy + Geometry ---")
    for img_path in sorted(raw_images):
        base_name = os.path.basename(img_path)
        img = cv2.imread(img_path)
        
        # Pass 1: Otsu
        proc1 = preprocess_otsu(img, gamma=1.0)
        data1 = pytesseract.image_to_data(proc1, output_type=pytesseract.Output.DICT, config='--psm 7')
        text1 = " ".join([w for w in data1['text'] if w.strip()]).strip()
        x1 = min([data1['left'][i] for i, t in enumerate(data1['text']) if t.strip()]) if text1 else 0
        w1 = sum([data1['width'][i] for i, t in enumerate(data1['text']) if t.strip()]) if text1 else 0
        target1, score1 = pm.evaluate(text1)
        
        # Pass 2: Fixed 200
        proc2 = preprocess_fixed(img, thresh_val=200, gamma=1.2)
        data2 = pytesseract.image_to_data(proc2, output_type=pytesseract.Output.DICT, config='--psm 7')
        text2 = " ".join([w for w in data2['text'] if w.strip()]).strip()
        x2 = min([data2['left'][i] for i, t in enumerate(data2['text']) if t.strip()]) if text2 else 0
        w2 = sum([data2['width'][i] for i, t in enumerate(data2['text']) if t.strip()]) if text2 else 0
        target2, score2 = pm.evaluate(text2)

        # Pass 3: Adaptive
        proc3 = preprocess_adaptive(img, block_size=101, gamma=1.0)
        data3 = pytesseract.image_to_data(proc3, output_type=pytesseract.Output.DICT, config='--psm 7')
        text3 = " ".join([w for w in data3['text'] if w.strip()]).strip()
        x3 = min([data3['left'][i] for i, t in enumerate(data3['text']) if t.strip()]) if text3 else 0
        w3 = sum([data3['width'][i] for i, t in enumerate(data3['text']) if t.strip()]) if text3 else 0
        target3, score3 = pm.evaluate(text3)
        
        result = "MISS"
        if target1 and score1 >= 40:
            result = f"HIT (Otsu): {target1} | '{text1}' | x={x1}, w={w1}"
        elif target2 and score2 >= 40:
            result = f"HIT (Fixed 200): {target2} | '{text2}' | x={x2}, w={w2}"
        elif target3 and score3 >= 40:
            result = f"HIT (Adaptive): {target3} | '{text3}' | x={x3}, w={w3}"
        else:
            result = f"MISS | O:'{text1}'(x={x1},w={w1}) | F:'{text2}'(x={x2},w={w2}) | A:'{text3}'(x={x3},w={w3})"
        
        print(f"[{base_name}] {result}")

if __name__ == "__main__":
    main()
