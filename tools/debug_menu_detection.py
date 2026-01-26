import json
import os
import cv2
import numpy as np
import mss

def debug_menu_detection():
    # Load config
    config_path = "data/config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Load template
    template_path = "data/templates/main_menu_template.png"
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    
    if template is None:
        print(f"ERROR: Could not load template from {template_path}")
        return
    
    print(f"Template shape: {template.shape}")
    
    # Get regions
    menu_region = config.get("menu_region", {})
    monitor_region = config.get("monitor_region", {})
    
    print(f"\nMonitor region: {monitor_region}")
    print(f"Menu region (absolute): {menu_region}")
    
    # Calculate relative coordinates
    left = menu_region.get("left", 0) - monitor_region.get("left", 0)
    top = menu_region.get("top", 0) - monitor_region.get("top", 0)
    w = menu_region.get("width", 50)
    h = menu_region.get("height", 50)
    
    print(f"Menu region (relative): left={left}, top={top}, w={w}, h={h}")
    
    # Capture screen
    with mss.mss() as sct:
        monitor = {
            "top": monitor_region.get("top", 0),
            "left": monitor_region.get("left", 0),
            "width": monitor_region.get("width", 1920),
            "height": monitor_region.get("height", 1080)
        }
        
        print(f"\nCapturing monitor: {monitor}")
        
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        print(f"Captured image shape: {img_bgr.shape}")
        
        # Check if ROI is valid
        fh, fw = img_bgr.shape[:2]
        if left < 0 or top < 0 or (left+w) > fw or (top+h) > fh:
            print(f"\nERROR: ROI out of bounds!")
            print(f"Image size: {fw}x{fh}")
            print(f"ROI: [{left}:{left+w}, {top}:{top+h}]")
            return
        
        # Extract ROI
        roi = img_bgr[top:top+h, left:left+w]
        print(f"ROI shape: {roi.shape}")
        
        # Save ROI for inspection
        cv2.imwrite("debug_roi.png", roi)
        print(f"\nSaved current ROI to debug_roi.png")
        
        # Try template matching
        res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        print(f"\nTemplate matching result:")
        print(f"  Max confidence: {max_val:.4f}")
        print(f"  Max location: {max_loc}")
        print(f"  Threshold: 0.8")
        print(f"  Would detect: {max_val > 0.8}")
        
        # Try with lower threshold
        for threshold in [0.7, 0.6, 0.5, 0.4, 0.3]:
            if max_val > threshold:
                print(f"  Would detect with threshold {threshold}: YES")
                break

if __name__ == "__main__":
    debug_menu_detection()
