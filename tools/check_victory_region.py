import sys
import os
import json
import cv2
import numpy as np
import pytesseract
from PIL import ImageGrab
import time
import unicodedata
from fuzzywuzzy import fuzz

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found.")
        sys.exit(1)

def capture_region(region):
    try:
        # Convert region to PIL bbox (left, top, right, bottom)
        left = region.get("left", 0)
        top = region.get("top", 0)
        width = region.get("width", 100)
        height = region.get("height", 100)
        
        # NOTE: PIL ImageGrab.grab(bbox=...) captures from the primary screen coordinate system.
        # If the region is configured for a specific monitor in VisionEngine, we might need to adjust.
        # But usually ImageGrab takes global coordinates if all monitors are mapped to a virtual desktop.
        
        bbox = (left, top, left + width, top + height)
        print(f"Capturing region: {bbox}")
        
        img = ImageGrab.grab(bbox=bbox)
        
        # Convert to OpenCV BGR
        img_np = np.array(img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        return img_bgr
    except Exception as e:
        print(f"Capture failed: {e}")
        return None

def adjust_gamma(image, gamma=1.0):
    if gamma == 1.0: return image
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def preprocess_otsunet(img):
    # Mimic VisionEngine.preprocess_image with 'otsu'
    if img is None: return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return thresh

def check_victory():
    config = load_config()
    victory_region = config.get("victory_region")
    
    if not victory_region:
        print("Error: 'victory_region' not defined in config.json")
        return

    # Check for Tesseract config
    tesseract_cmd = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    else:
        print(f"Warning: Tesseract cmd '{tesseract_cmd}' not found.")

    print("--- Starting Detection Test ---")
    img = capture_region(victory_region)
    
    if img is None:
        print("Failed to capture image.")
        return

    # Save debug image
    os.makedirs("debug_images", exist_ok=True)
    debug_path = "debug_images/victory_region_debug.png"
    cv2.imwrite(debug_path, img)
    print(f"Debug image saved to: {debug_path}")
    print("Please check this image to verify it covers the 'RESULTAT' text.")

    # Preprocess
    processed = preprocess_otsunet(img)
    cv2.imwrite("debug_images/victory_region_processed.png", processed)
    
    # OCR
    print("Running OCR...")
    try:
        data = pytesseract.image_to_data(processed, config='--psm 7', output_type=pytesseract.Output.DICT)
        valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
        raw_text = " ".join([data['text'][i] for i in valid_indices]).strip()
        
        print(f"Raw OCR Output: '{raw_text}'")
        
        # Clean and Normalize
        text = raw_text # In engine we use clean_text which strips non-alphanumeric from edges
        normalized = text.strip().upper()
        # Remove accents
        normalized_no_accents = ''.join(c for c in unicodedata.normalize('NFD', normalized) 
                                        if unicodedata.category(c) != 'Mn')
        
        print(f"Normalized: '{normalized_no_accents}'")
        
        # Fuzzy Match
        victory_patterns_base = ["RESULTAT", "RESULTIT", "RESULT", "RECOMPE"]
        best_score = 0
        best_pattern = None
        for pattern in victory_patterns_base:
            score = fuzz.ratio(normalized_no_accents, pattern)
            if score > best_score:
                best_score = score
                best_pattern = pattern
        
        print(f"Best Match: '{best_pattern}' | Score: {best_score}")
        
        if best_score >= 60:
            print(">>> VICTORY DETECTED! <<<")
        else:
            print(">>> No Victory Detected (Score < 60) <<<")

    except Exception as e:
        print(f"OCR Failed: {e}")

if __name__ == "__main__":
    check_victory()
