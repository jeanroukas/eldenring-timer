import cv2
import numpy as np
import os
import sys

def analyze_pixels(image_path):
    if not os.path.exists(image_path):
        return

    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    h_orig, w_orig = img.shape[:2]
    print(f"Image Size: {w_orig}x{h_orig}")
    print(f"Mean Brightness: {np.mean(gray):.2f}")
    print(f"Max Brightness: {np.max(gray)}")
    print(f"Min Brightness: {np.min(gray)}")
    
    # Try to find yellow-ish pixels (JOUR banner is golden)
    # HSV Yellow range: approx 20-35 hue
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([20, 50, 50])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    yellow_pixel_count = np.sum(mask_yellow > 0)
    print(f"Yellow Pixels Found: {yellow_pixel_count}")
    
    cv2.imwrite("debug_images/Day_Region_YellowMask.png", mask_yellow)
    
    # Check if there's enough contrast
    # A standard banner should have some pixels > 200 brightness
    bright_pixels = np.sum(gray > 200)
    print(f"Bright Pixels (>200): {bright_pixels}")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "debug_images/Day_Region.png"
    analyze_pixels(path)
