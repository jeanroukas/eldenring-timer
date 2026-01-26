import json
import os
import cv2
import numpy as np
import mss

def test_menu_detection_global():
    """
    Test menu detection using GLOBAL coordinates (not relative to monitor_region).
    This is how capture_menu_template.py works, so detection should work the same way.
    """
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
    
    print(f"Template loaded: {template.shape}")
    
    # Get menu region (GLOBAL coordinates)
    menu_region = config.get("menu_region", {})
    print(f"\nMenu region (GLOBAL): {menu_region}")
    
    # Capture using GLOBAL coordinates (like capture_menu_template.py does)
    with mss.mss() as sct:
        monitor = {
            "top": menu_region["top"],
            "left": menu_region["left"],
            "width": menu_region["width"],
            "height": menu_region["height"]
        }
        
        print(f"Capturing: {monitor}")
        
        try:
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            roi = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            print(f"Captured ROI shape: {roi.shape}")
            
            # Save for inspection
            cv2.imwrite("debug_current_menu.png", roi)
            print(f"Saved current capture to debug_current_menu.png")
            
            # Template matching
            res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            print(f"\nTemplate matching:")
            print(f"  Confidence: {max_val:.4f}")
            print(f"  Threshold: 0.8")
            print(f"  Would detect: {max_val > 0.8}")
            
            # Try different thresholds
            print(f"\nThreshold analysis:")
            for threshold in [0.9, 0.8, 0.7, 0.6, 0.5]:
                status = "✓ YES" if max_val > threshold else "✗ NO"
                print(f"  {threshold}: {status}")
                
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_menu_detection_global()
