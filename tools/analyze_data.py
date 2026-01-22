import os
import json
import glob
import numpy as np
from collections import Counter
import re
import datetime

# Config
RAW_DIR = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
LOG_FILE = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\ocr_log.txt"

def analyze_samples():
    print("=== SAMPLE ANALYSIS ===")
    files = glob.glob(os.path.join(RAW_DIR, "*.json"))
    print(f"Found {len(files)} JSON samples.")
    
    if not files: return

    brightness_values = []
    labels = []
    detected_texts = []
    panic_saves = 0
    
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            br = data.get('brightness', 0)
            brightness_values.append(br)
            
            det = data.get('detected_text', "")
            detected_texts.append(det)
            
            lbl = data.get('manual_label')
            if lbl:
                labels.append(lbl)
                
            # Check for panic saves (if we just implemented it, likely none yet, but good for future)
            if "PANIC" in os.path.basename(f_path):
                panic_saves += 1
                
        except Exception as e:
            print(f"Error reading {f_path}: {e}")

    avg_br = np.mean(brightness_values) if brightness_values else 0
    print(f"Average Brightness: {avg_br:.2f}")
    print(f" brightness range: {min(brightness_values):.2f} - {max(brightness_values):.2f}")
    print(f"Samples with Manual Labels: {len(labels)}")
    print(f"Panic/Bias-Fix Saves: {panic_saves}")
    
    print("\nTop 10 Detected Texts:")
    print(Counter(detected_texts).most_common(10))
    
    print("\nManual Label Distribution:")
    print(Counter(labels).most_common())

def analyze_logs():
    print("\n=== LOG ANALYSIS ===")
    if not os.path.exists(LOG_FILE):
        print("Log file not found.")
        return

    # Regex to capture text and brightness
    # [17:52:07] OCR: 'SAOURI' (Filter: True, Save: True) Br:245.3
    pattern = re.compile(r"OCR: '([^']*)'.*Br:([\d\.]+)")
    
    texts = []
    brightnesses = []
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        match = pattern.search(line)
        if match:
            text = match.group(1)
            br = float(match.group(2))
            texts.append(text)
            brightnesses.append(br)
            
    print(f"Parsed {len(texts)} OCR entries from log.")
    
    # Common errors for "JOUR II" (heuristic)
    # We look for things that start with J but aren't JOUR I or JOUR II
    suspicious = [t for t in texts if "J" in t and t not in ["JOUR I", "JOUR II", "JOUR III"]]
    print("\nSuspicious 'J' texts (potential Day 2 misreads):")
    print(Counter(suspicious).most_common(20))
    
    # Correlate brightness with specific errors
    # Let's see average brightness of "JOUR II" vs "Jouril"
    
    def get_avg_br(target_text):
        brs = [b for t, b in zip(texts, brightnesses) if t == target_text]
        return np.mean(brs) if brs else 0, len(brs)

    print("\nBrightness Correlation:")
    for txt in ["JOUR I", "JOUR II", "JOURIL", "JOURTI", "JOUR", "I", "II"]:
        avg, count = get_avg_br(txt)
        if count > 0:
            print(f"  '{txt}': Avg Br={avg:.1f} (n={count})")

if __name__ == "__main__":
    analyze_samples()
    analyze_logs()
