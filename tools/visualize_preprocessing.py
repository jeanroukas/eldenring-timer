import cv2
import numpy as np
import os
import sys

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

    if pass_type == "otsu" or pass_type == "simple_otsu":
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    elif pass_type == "fixed" or pass_type == "dynamic":
        val = custom_val if custom_val > 0 else 230
        _, thresh = cv2.threshold(gray, val, 255, cv2.THRESH_BINARY_INV)
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

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(root, "samples", "raw")
    output_dir = os.path.join(root, "samples", "debug_processing")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(samples_dir):
        print(f"Directory not found: {samples_dir}")
        return

    images = [f for f in os.listdir(samples_dir) if f.endswith(".png")]
    if not images:
        print(f"No PNG images found in {samples_dir}")
        return

    print(f"Found {len(images)} images. Processing...")

    for img_name in images:
        img_path = os.path.join(samples_dir, img_name)
        img = cv2.imread(img_path)
        if img is None: continue

        brightness = np.mean(img)
        target_thresh = 230 + (brightness * 0.1)
        target_thresh = min(254, max(200, int(target_thresh)))

        passes = [
            {"type": "simple_otsu", "val": 0, "scale": 1.0, "gamma": 1.0},
            {"type": "dynamic", "val": target_thresh, "scale": 1.5, "gamma": 1.0},
            {"type": "adaptive", "val": 0, "scale": 1.5, "gamma": 1.0},
            {"type": "inverted", "val": 0, "scale": 1.5, "gamma": 1.0}
        ]

        for p in passes:
            processed = preprocess_image(img, pass_type=p["type"], custom_val=p["val"], scale=p["scale"], gamma=p["gamma"])
            out_name = f"{os.path.splitext(img_name)[0]}_pass_{p['type']}.png"
            cv2.imwrite(os.path.join(output_dir, out_name), processed)
            print(f"Saved: {out_name}")

if __name__ == "__main__":
    main()
