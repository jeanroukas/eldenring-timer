import pytesseract
import cv2
import numpy as np
from PIL import Image
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

path = r'c:\Users\lprad\Documents\Python Scripts\Elden ring timer\debug_day_region.png'
img = cv2.imread(path)
red = img[:, :, 2] # Red channel

for scale in [2.0, 3.0, 4.0]:
    resized = cv2.resize(red, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(resized, 120, 255, cv2.THRESH_BINARY_INV)
    
    # Padding
    pad = 50
    final = cv2.copyMakeBorder(thresh, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    
    text = pytesseract.image_to_string(Image.fromarray(final), config='--psm 6').strip()
    print(f"RED Scale {scale}: '{text}'")
