import cv2
import numpy as np
import os
import sys
import time
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision_engine import VisionEngine

class BenchVisionEngine(VisionEngine):
    """VisionEngine specialized for benchmarking."""
    def __init__(self, config, benchmark_img):
        # Disable logging for pure throughput test
        config["debug_mode"] = False
        config["save_raw_samples"] = False
        super().__init__(config)
        self.benchmark_img = benchmark_img
        self.scan_delay = 0 
        
    def capture_screen(self):
        return self.benchmark_img.copy()

def run_benchmark(engine, duration=10):
    count = 0
    start = time.perf_counter()
    end_time = start + duration
    
    # Run the real _loop logic but in a controlled way
    def mock_callback(text, width, offset, word_data, brightness):
        pass

    # We manually pull the logic from _loop into a benchmark loop
    while time.perf_counter() < end_time:
        # This mirrors the core of _loop
        img = engine.capture_screen()
        brightness = np.mean(img)
        
        # Use the engine's real processing logic
        target_thresh = 230 + (brightness * 0.1)
        target_thresh = min(254, max(200, int(target_thresh)))

        all_passes = [
            {"type": "simple_otsu", "val": 0, "scale": 1.0, "gamma": 1.0, "id": "otsu"},
            {"type": "dynamic", "val": target_thresh, "scale": 1.0, "gamma": 1.0, "id": "dyn_1.0"},
            {"type": "dynamic", "val": target_thresh, "scale": 1.2, "gamma": 0.8, "id": "dyn_0.8"},
            {"type": "fixed", "val": 250, "scale": 1.2, "gamma": 0.8, "id": "fixed_250"},
            {"type": "adaptive", "val": 0, "scale": 1.0, "gamma": 1.0, "id": "adaptive"}
        ]
        
        prioritized_passes = []
        if engine.last_successful_pass:
            matching = [p for p in all_passes if p["id"] == engine.last_successful_pass["id"]]
            if matching: prioritized_passes.append(matching[0])
        
        others = [p for p in all_passes if p not in prioritized_passes]
        if brightness > 180:
            others.sort(key=lambda x: (x.get("gamma") == 0.8 or x["type"] == "fixed"), reverse=True)
        else:
            others.sort(key=lambda x: (x["type"] == "simple_otsu" or (x.get("gamma") == 1.0 and x["type"] == "dynamic")), reverse=True)
        prioritized_passes.extend(others)

        best_conf = 0
        for p_config in prioritized_passes:
            processed = engine.preprocess_image(img, pass_type=p_config["type"], 
                                              custom_val=p_config["val"], 
                                              scale=p_config["scale"],
                                              gamma=p_config.get("gamma", 1.0))
            if processed is None: continue
            
            # THE CORE: DLL or Pytesseract
            if engine.tess_api:
                text, avg_conf = engine.tess_api.get_text(processed)
            else:
                # Mock pytesseract overhead for comparison if DLL failed to load
                avg_conf = 0 
                
            if avg_conf > 70:
                engine.last_successful_pass = p_config
                if avg_conf > 85:
                    break # Early Exit
            
        count += 1
    
    total_time = time.perf_counter() - start
    return count, total_time

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(root, "samples", "raw")
    
    sample_files = [f for f in os.listdir(samples_dir) if f.endswith(".png") and "JOUR" in f]
    if not sample_files:
        sample_files = [f for f in os.listdir(samples_dir) if f.endswith(".png")]
        
    if not sample_files:
        print("Error: No samples found.")
        return
    
    bench_img = cv2.imread(os.path.join(samples_dir, sample_files[0]))
    print(f"Using sample for benchmark: {sample_files[0]}")

    print("\n[BENCHMARK] Testing Direct API Integration...")
    
    config = {
        "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        "debug_mode": True # For init messages
    }
    
    engine = BenchVisionEngine(config, bench_img)
    
    if not engine.tess_api:
        print("CRITICAL: DLL API not loaded during benchmark init.")
        return

    # Warmup
    print("Warmer cycle...")
    run_benchmark(engine, duration=2)
    
    print("Running 10s benchmark...")
    count, duration = run_benchmark(engine, duration=10)
    fps = count / duration

    print("\n" + "="*45)
    print(f"{'Engine Mode':<20} | {'Throughput (FPS)':<20}")
    print("-" * 45)
    print(f"{'Direct DLL API':<20} | {fps:<20.2f}")
    print("=" * 45)
    print(f"Target: 10.00 FPS")
    if fps > 10:
        print(f"Goal ACHIEVED! Speedup over pytesseract: ~x{fps / 2.0:.1f}")

if __name__ == "__main__":
    main()
