import cv2
import numpy as np
import os
import sys
import pytesseract
import json
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess_image(img, pass_type="otsu", custom_val=0, scale=1.0, gamma=1.0):
    if img is None: return None
    
    # Dynamic Scaling
    h, w = img.shape[:2]
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Convert to gray
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if gamma != 1.0:
        gray = adjust_gamma(gray, gamma)

    if pass_type == "otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif pass_type == "fixed":
        _, thresh = cv2.threshold(gray, custom_val, 255, cv2.THRESH_BINARY_INV)
    elif pass_type == "adaptive":
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY_INV, 25, 2)
    elif pass_type == "inverted":
        gray = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return thresh

def run_ocr(img, psm=7):
    config = f'--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    try:
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
        valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
        text = " ".join([data['text'][i] for i in valid_indices]).strip()
        conf_list = [int(c) for c in data['conf'] if c != -1]
        avg_conf = np.mean(conf_list) if conf_list else 0
        return text.upper(), avg_conf
    except Exception as e:
        return f"ERROR: {e}", 0

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(root, "samples", "raw")
    
    # Set tesseract path (common locations)
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Users\lprad\AppData\Local\Tesseract-OCR\tesseract.exe"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

    if not os.path.exists(samples_dir):
        print(f"Directory not found: {samples_dir}")
        return

    images = [f for f in os.listdir(samples_dir) if f.endswith(".png")]
    if not images:
        print(f"No PNG images found in {samples_dir}")
        return

    # Tuning Grid
    gammas = [0.5, 0.8, 1.0, 1.2, 1.5]
    scales = [1.0, 1.5, 2.0]
    psms = [7, 6]
    methods = ["otsu", "adaptive", "fixed_230", "fixed_200", "fixed_250"]

    results = []

    print(f"Starting Grid Search on {len(images)} images...")
    
    for img_name in images:
        img_path = os.path.join(samples_dir, img_name)
        img = cv2.imread(img_path)
        if img is None: continue
        
        print(f"\nAnalyzing: {img_name}")
        
        for g in gammas:
            for s in scales:
                for psm in psms:
                    for m in methods:
                        m_type = m.split('_')[0]
                        m_val = int(m.split('_')[1]) if '_' in m else 0
                        
                        processed = preprocess_image(img, pass_type=m_type, custom_val=m_val, scale=s, gamma=g)
                        text, conf = run_ocr(processed, psm=psm)
                        
                        if text:
                            res = {
                                "image": img_name,
                                "gamma": g,
                                "scale": s,
                                "psm": psm,
                                "method": m,
                                "text": text,
                                "conf": round(conf, 2)
                            }
                            results.append(res)
                            if conf > 60:
                                print(f"  [GOOD] G:{g} S:{s} PSM:{psm} M:{m} -> '{text}' ({conf}%)")

    # Sort results by confidence
    results.sort(key=lambda x: x['conf'], reverse=True)
    
    output_file = os.path.join(root, "samples", "ocr_tuning_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDone! Best results saved to {output_file}")
    
    # Show Top 10
    print("\nTop 10 Overall:")
    for i, r in enumerate(results[:10]):
        print(f"{i+1}. {r['image']} | {r['text']} ({r['conf']}%) | G:{r['gamma']} S:{r['scale']} PSM:{r['psm']} M:{r['method']}")

if __name__ == "__main__":
    main()
