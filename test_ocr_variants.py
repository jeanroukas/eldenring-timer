import cv2
import numpy as np
import pytesseract
import os

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def test_on_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load {image_path}")
        return

    # Resize to 160 height if needed
    h, w = img.shape[:2]
    target_h = 160
    scale = target_h / h
    new_w = int(w * scale)
    img_resized = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    
    # Try different gammas
    for gamma in [0.8, 1.0, 1.2]:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        gray_gamma = cv2.LUT(gray, table)

        variants = []
        
        # 1. Current (Adaptive 31)
        thresh1 = cv2.adaptiveThreshold(gray_gamma, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 2)
        variants.append(("Adaptive_31", thresh1))
        
        # 2. Large Adaptive (101)
        thresh2 = cv2.adaptiveThreshold(gray_gamma, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 101, 2)
        variants.append(("Adaptive_101", thresh2))

        # 3. Very Large Adaptive (201)
        thresh3 = cv2.adaptiveThreshold(gray_gamma, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 201, 2)
        variants.append(("Adaptive_201", thresh3))

        # 4. Otsu
        _, thresh4 = cv2.threshold(gray_gamma, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants.append(("Otsu", thresh4))

        # 5. Fixed High Threshold
        _, thresh5 = cv2.threshold(gray_gamma, 180, 255, cv2.THRESH_BINARY_INV)
        variants.append(("Fixed_180", thresh5))

        print(f"\n--- Gamma {gamma} ---")
        for name, proc in variants:
            # Add a bit of dilation to some to see
            # proc_dilated = cv2.dilate(proc, np.ones((2,2), np.uint8), iterations=1)
            
            text = pytesseract.image_to_string(proc, config='--psm 7').strip()
            print(f"{name}: '{text}'")
            
            # Save for inspection
            cv2.imwrite(f"test_out_{name}_g{gamma}.png", proc)

if __name__ == "__main__":
    test_on_image("debug_images/debug_raw_060130.png")
