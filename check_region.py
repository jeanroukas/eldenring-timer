
import json
from PIL import ImageGrab
import ctypes

# DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# Get Screen Size
img = ImageGrab.grab(all_screens=True)
width, height = img.size
print(f"Current Screen Size: {width}x{height}")

# Load Config
try:
    with open("config.json", "r") as f:
        config = json.load(f)
        region = config.get("monitor_region", {})
        print(f"Config Region: {region}")
        
        # Check Bounds
        r_top = region.get("top", 0)
        r_left = region.get("left", 0)
        r_w = region.get("width", 0)
        r_h = region.get("height", 0)
        
        if r_top + r_h > height:
            print("WARNING: Region BOTTOM is OFF SCREEN!")
        if r_left + r_w > width:
            print("WARNING: Region RIGHT is OFF SCREEN!")
            
        # Calculate timer.py equivalent
        t_top = int(height * 0.5)
        t_bottom = int(height * 0.65)
        t_left = int(width * 0.35)
        t_right = int(width * 0.65)
        
        print(f"Timer.py Equivalent Region: Top={t_top}, Left={t_left}, W={t_right-t_left}, H={t_bottom-t_top}")
        
except Exception as e:
    print(f"Error: {e}")
