import ctypes
from ctypes import wintypes
from PIL import ImageGrab
import cv2
import numpy as np

def get_virtual_screen_origin():
    user32 = ctypes.windll.user32
    # SM_XVIRTUALSCREEN = 76
    # SM_YVIRTUALSCREEN = 77
    # SM_CXVIRTUALSCREEN = 78
    # SM_CYVIRTUALSCREEN = 79
    vx = user32.GetSystemMetrics(76)
    vy = user32.GetSystemMetrics(77)
    vw = user32.GetSystemMetrics(78)
    vh = user32.GetSystemMetrics(79)
    return vx, vy, vw, vh

if __name__ == "__main__":
    vx, vy, vw, vh = get_virtual_screen_origin()
    print(f"Virtual Screen Origin: ({vx}, {vy}) Size: {vw}x{vh}")
    
    # Capture the whole thing to see
    img = ImageGrab.grab(all_screens=True)
    print(f"PIL Image size: {img.size}")
    
    # If the user's region is at (0,0) globally, it's at (-vx, -vy) in PIL
    # Let's try to capture a 500x500 box at global 0,0
    left = 0 - vx
    top = 0 - vy
    bbox = (left, top, left + 500, top + 500)
    print(f"Attempting to capture global (0,0) with PIL bbox: {bbox}")
    
    try:
        sub_img = ImageGrab.grab(bbox=bbox, all_screens=True)
        sub_img.save("pil_test_origin.png")
        print("Saved pil_test_origin.png")
    except Exception as e:
        print(f"Error: {e}")
