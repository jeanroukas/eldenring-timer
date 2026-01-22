import cv2
import glob
import os
import numpy as np

def analyze_bounds():
    images = glob.glob("debug_images/*.png")
    if not images:
        print("No images found.")
        return

    min_x, min_y = 99999, 99999
    max_x, max_y = 0, 0

    print(f"Analyzing {len(images)} images...")

    for img_path in images:
        img = cv2.imread(img_path)
        if img is None: continue
        
        # Convert to gray
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Gamma Correction (Crucial for HDR)
        invGamma = 1.0 / 0.5
        table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

        # Threshold to find bright text 
        _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Filter noise (Text is likely larger than 50x50)
            if w < 50 or h < 50: continue
            
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

    print(f"Global Bounding Box across all samples:")
    print(f"X: {min_x} to {max_x} (Width: {max_x - min_x})")
    print(f"Y: {min_y} to {max_y} (Height: {max_y - min_y})")
    
    if images:
        debug_img = cv2.imread(images[0])
        
        # Redraw logic to visualize what is being picked up
        # Re-run threshold on first image to draw contours
        gray = cv2.cvtColor(debug_img, cv2.COLOR_BGR2GRAY)
        invGamma = 1.0 / 0.5
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
             x, y, w, h = cv2.boundingRect(cnt)
             if w >= 30 and h >= 30:
                 cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)

        cv2.rectangle(debug_img, (min_x, min_y), (max_x, max_y), (0, 0, 255), 2)
        cv2.imwrite("debug_images/region_debug.png", debug_img)
        print("Saved debug_images/region_debug.png")

if __name__ == "__main__":
    analyze_bounds()
