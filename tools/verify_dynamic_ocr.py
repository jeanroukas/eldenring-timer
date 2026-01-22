import sys
import os
import cv2
import json
import glob
import time
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from vision_engine import VisionEngine

def verify_engine():
    print("=== FINAL VERIFICATION: VisionEngine Integration ===")
    
    # Init Engine (mock config)
    config = {
        "monitor_region": {"top": 0, "left": 0, "width": 100, "height": 100},
        "debug_mode": False,
        "save_raw_samples": False
    }
    engine = VisionEngine(config)
    
    # Load Samples
    raw_dir = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
    files = glob.glob(os.path.join(raw_dir, "*.json"))
    
    success = 0
    total = 0
    
    print(f"Testing {len(files)} samples against the LIVE Engine logic...")
    
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            label = data.get('manual_label')
            if label not in ["0", "1", "2", "3"]: continue
            
            img_path = f_path.replace('.json', '.png')
            if not os.path.exists(img_path): continue
            
            img = cv2.imread(img_path)
            if img is None: continue
            
            # --- RUN ENGINE LOGIC MANUALLY ---
            # We bypass the loop but use the internal methods
            
            brightness = np.mean(img)
            
            # 1. Calc Dynamic Threshold
            # Logic replicated from _loop or we can extract it to a method?
            # It's inside _loop currently. Let's replicate the CALLS exactly as they appear in _loop
            # to verify the python code is valid and logic holds.
            
            target_thresh = 230 + (brightness * 0.1)
            target_thresh = min(254, max(200, int(target_thresh)))
            
            passes = [
                {"type": "dynamic", "val": target_thresh, "scale": 1.5},
                {"type": "adaptive", "val": 0, "scale": 1.5},
                {"type": "inverted", "val": 0, "scale": 1.5} 
            ]
            
            best_text = ""
            best_conf = 0
            engine.best_conf = 0 # reset
            
            for p_config in passes:
                processed = engine.preprocess_image(img, pass_type=p_config["type"], 
                                                  custom_val=p_config["val"], 
                                                  scale=p_config["scale"])
                if processed is None: continue
                
                # We need pytesseract here like the engine does
                import pytesseract
                custom_config = r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 --psm 7'
                data_ocr = pytesseract.image_to_data(processed, config=custom_config, output_type=pytesseract.Output.DICT)
                
                conf_list = [int(c) for c in data_ocr['conf'] if c != -1]
                avg_conf = np.mean(conf_list) if conf_list else 0
                
                if avg_conf < 40 and p_config["type"] == "dynamic": continue
                
                valid_indices = [i for i, t in enumerate(data_ocr['text']) if t.strip()]
                raw_text = " ".join([data_ocr['text'][i] for i in valid_indices]).strip()
                text = engine.clean_text(raw_text)
                text = engine.CORRECTION_MAP.get(text, text)
                
                # RELEVANCE FILTER
                if not engine.is_relevant(text): continue
                
                if text:
                     if avg_conf > (engine.best_conf + 10) or (len(text) > len(best_text) and avg_conf > 50):
                        engine.best_conf = avg_conf
                        best_text = text
                        best_conf = avg_conf
                
                if engine.best_conf > 85: break # Early exit
            
            # CHECK RESULT
            is_ok = False
            if label == "0": is_ok = (not best_text)
            elif label == "1": is_ok = ("1" in best_text or "I" in best_text)
            elif label == "2": is_ok = ("2" in best_text or "II" in best_text)
            elif label == "3": is_ok = ("3" in best_text or "III" in best_text)
            
            if is_ok: success += 1
            total += 1
            
            status = "PASS" if is_ok else "FAIL"
            # print(f"[{status}] Lbl:{label} vs Det:'{best_text}' (Conf:{best_conf:.1f}, Br:{brightness:.1f})")
            
        except Exception as e:
            print(f"Error on {f_path}: {e}")

    print("-" * 30)
    print(f"Final Accuracy: {success}/{total} ({success/total*100:.1f}%)")
    print("-" * 30)

if __name__ == "__main__":
    verify_engine()
