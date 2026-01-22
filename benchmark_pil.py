from PIL import ImageGrab
import time
import ctypes

def benchmark_pil_region():
    # Set DPI awareness
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        ctypes.windll.user32.SetProcessDPIAware()

    # Small region (typical for OCR)
    # top, left, width, height format from user
    region = {"top": 100, "left": 100, "width": 400, "height": 100}
    
    # PIL bbox is (left, top, right, bottom)
    bbox = (region["left"], region["top"], region["left"] + region["width"], region["top"] + region["height"])
    
    print(f"Benchmarking PIL ImageGrab on region: {bbox}")
    
    times = []
    for _ in range(20):
        start = time.perf_counter()
        img = ImageGrab.grab(bbox=bbox)
        times.append(time.perf_counter() - start)
    
    avg_time = sum(times) / len(times)
    fps = 1.0 / avg_time
    print(f"Average capture time: {avg_time:.4f}s ({fps:.2f} FPS)")

if __name__ == "__main__":
    benchmark_pil_region()
