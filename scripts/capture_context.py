import mss
import mss.tools
from PIL import Image

def capture_context():
    with mss.mss() as sct:
        # Capture Monitor 1
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        output_path = "debug_images/Context_Full.png"
        mss.tools.to_png(img.rgb, img.size, output=output_path)
        print(f"Full context saved to {output_path}")

if __name__ == "__main__":
    capture_context()
