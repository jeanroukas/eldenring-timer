from PIL import ImageGrab
import cv2
import numpy as np
import time

def test_pil_capture():
    print("Testing PIL ImageGrab...")
    
    # Set DPI awareness for PIL
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        ctypes.windll.user32.SetProcessDPIAware()

    start = time.perf_counter()
    # Capture all screens or just primary
    img = ImageGrab.grab(all_screens=True)
    end = time.perf_counter()
    print(f"PIL Capture took {end-start:.4f}s")
    
    # Convert to OpenCV BGR
    img_np = np.array(img)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    
    cv2.imwrite("pil_debug_raw.png", img_bgr)
    print("Saved pil_debug_raw.png")
    
    # Test adaptive thresholding
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 
        11, 2
    )
    cv2.imwrite("pil_debug_proc.png", thresh)
    print("Saved pil_debug_proc.png")

if __name__ == "__main__":
    test_pil_capture()
