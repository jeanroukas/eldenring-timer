import cv2
import numpy as np
import pytesseract
import os

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def verify():
    image_path = "debug_images/debug_raw_060130.png"
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load {image_path}")
        return

    # Winning Params: (1.5, 0, 'otsu', 2, 'close_2x2', 0.8)
    scale = 1.5
    gamma = 0.8
    
    # 1. Resize
    h, w = img.shape[:2]
    new_h = int(h * scale)
    new_w = int(w * scale)
    proc = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    # 2. Convert to Gray & Gamma
    gray = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
    if gamma != 1.0:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

    # 3. Threshold (Otsu)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 4. Morph (Close 2x2)
    kernel = np.ones((2,2), np.uint8)
    final = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # 5. OCR
    text = pytesseract.image_to_string(final, config='--psm 7').strip()
    print(f"OCR Result: '{text}'")
    
    # Save image
    cv2.imwrite("debug_proc_winner.png", final)

if __name__ == "__main__":
    verify()
