from PIL import ImageGrab
import cv2
import numpy as np
import ctypes

def test_black_screen():
    print("Diagnostic: Testing PIL Capture...")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        ctypes.windll.user32.SetProcessDPIAware()

    # Capture a 1000x1000 area at 0,0
    # On multi-monitor, we use negative offsets if needed
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(76)
    vy = user32.GetSystemMetrics(77)
    
    # Let's just capture the whole virtual screen once
    print("Capturing full virtual screen...")
    full = ImageGrab.grab(all_screens=True)
    full_np = np.array(full)
    
    # Check if image is all zeros
    if np.any(full_np > 0):
        print("Success: Full screen is NOT black.")
        # Save a thumbnail
        small = cv2.resize(cv2.cvtColor(full_np, cv2.COLOR_RGB2BGR), (0,0), fx=0.1, fy=0.1)
        cv2.imwrite("diagnostic_full.png", small)
        print("Saved diagnostic_full.png (thumbnail)")
    else:
        print("Failure: Full screen IS black. Hardware acceleration or DRM is active.")

if __name__ == "__main__":
    test_black_screen()
