import cv2
import pytesseract
import numpy as np
import os

# Configure Tesseract Path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def analyze_ocr(image_path):
    img = cv2.imread(image_path)
    img_large = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_large, cv2.COLOR_BGR2GRAY)
    
    # Trial FIXED 230 INV
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
    
    data = pytesseract.image_to_data(thresh, lang="fra", config='--psm 6', output_type=pytesseract.Output.DICT)
    
    print(f"--- Confirmation for {image_path} ---")
    texts = [t for t in data['text'] if t.strip()]
    confs = [float(c) for i, c in enumerate(data['conf']) if data['text'][i].strip()]
    
    if texts:
        print(f"Detected: {' '.join(texts)}")
        print(f"Confidences: {confs}")
        print(f"Mean Conf: {sum(confs)/len(confs):.1f}%")
    else:
        print("Nothing detected.")

if __name__ == "__main__":
    analyze_ocr("debug_images/Day_Region.png")
