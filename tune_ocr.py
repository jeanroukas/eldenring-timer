import cv2
import numpy as np
import pytesseract
import os
import glob

tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_cmd):
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def verify_winning_settings(folder_path):
    images = glob.glob(os.path.join(folder_path, "*.png"))
    print(f"Verifying H:80 T:245 G:0.5 on {len(images)} images in {folder_path}")

    # Optimal Settings (Found via optimization)
    target_h = 80
    thresh_val = 245
    gamma_val = 0.5
    
    for img_path in images:
        print(f"\n=== {os.path.basename(img_path)} ===")
        img = cv2.imread(img_path)
        if img is None: continue

        h, w = img.shape[:2]
        scale = target_h / h
        new_w = int(w * scale)
        resized = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA)
        
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        # Gamma
        gray = adjust_gamma(gray, gamma_val)
        
        _, thresh_img = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
        
        # New Optimal is 'Normal' (Not Inverted)
        configs = [
            ('Winning (G:0.5 T:245 Inv:False)', thresh_img),
        ]
        
        for name, proc_img in configs:
            config = '--psm 7' 
            text = pytesseract.image_to_string(proc_img, config=config).strip()
            clean = text.replace('\n', ' ')
            print(f"Result [{name}]: '{clean}'")

if __name__ == "__main__":
    verify_winning_settings("debug_images")
