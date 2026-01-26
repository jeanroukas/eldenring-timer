import mss
import mss.tools
import json
import os
from PIL import Image

def capture_regions():
    config_path = "data/config.json"
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    regions = {
        "Day_Region": config.get("monitor_region"),
        "Level_Region": config.get("level_region"),
        "Runes_Region": config.get("runes_region")
    }

    output_dir = "debug_images"
    os.makedirs(output_dir, exist_ok=True)

    with mss.mss() as sct:
        for name, reg in regions.items():
            if not reg:
                print(f"Skipping {name}: No region defined.")
                continue
            
            # MSS format: {'top': 0, 'left': 0, 'width': 100, 'height': 100}
            try:
                # Capture
                img = sct.grab(reg)
                output_path = os.path.join(output_dir, f"{name}.png")
                mss.tools.to_png(img.rgb, img.size, output=output_path)
                print(f"Saved {name} to {output_path} (Size: {reg['width']}x{reg['height']} at {reg['left']},{reg['top']})")
            except Exception as e:
                print(f"Failed to capture {name}: {e}")

if __name__ == "__main__":
    capture_regions()
