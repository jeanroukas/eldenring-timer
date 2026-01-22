import sys
import os
import re

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.pattern_manager import PatternManager

def clean_text_simulated(text):
    """ Simulated from vision_engine.py """
    if not text: return ""
    # Strip timestamp if present: [HH:MM:SS] TEXT
    if text.startswith("[") and "]" in text:
        text = text.split("]", 1)[1].strip()
    
    match = re.search(r'[A-Z0-9].*[A-Z0-9]', text.upper())
    if match:
        return match.group(0)
    match = re.search(r'[A-Z0-9]', text.upper())
    if match:
        return match.group(0)
    return ""

def run_log_analysis():
    log_path = "ocr_log.txt"
    if not os.path.exists(log_path):
        print(f"Log file {log_path} not found.")
        return

    pm = PatternManager()
    
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    results = []
    stats = {"DAY 1": 0, "DAY 2": 0, "NONE": 0}
    
    print(f"--- Analyzing {len(lines)} log entries ---\n")
    
    noise_successes = []
    typo_successes = []
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        cleaned = clean_text_simulated(line)
        if not cleaned: 
            stats["NONE"] += 1
            continue
            
        target, score = pm.evaluate(cleaned)
        
        if target:
            stats[target] += 1
            # Check if cleaning actually removed symbols
            if re.search(r'[^A-Z0-9 ]', line.split("]",1)[-1] if "]" in line else line):
                noise_successes.append((line, cleaned, target, score))
            
            # Check for typos (score < 100 or specific typo strings)
            if score < 50: # fuzzy range
                typo_successes.append((line, cleaned, target, score))
                
            results.append({
                "raw": line,
                "cleaned": cleaned,
                "target": target,
                "score": score
            })
        else:
            stats["NONE"] += 1

    print("\n--- Detection Summary ---")
    print(f"Total Lines: {len(lines)}")
    print(f"Day 1 Detected: {stats['DAY 1']}")
    print(f"Day 2 Detected: {stats['DAY 2']}")
    print(f"Rejected Source: {stats['NONE']}")
    
    print("\n--- Noise Cleaning Successes (Raw -> Cleaned -> Result) ---")
    for raw, cl, tar, sc in noise_successes[:15]:
        print(f"'{raw}' -> '{cl}' -> {tar}")

    print("\n--- Typo/Fuzzy Successes ---")
    for raw, cl, tar, sc in typo_successes[:15]:
        print(f"'{raw}' -> '{cl}' -> {tar} (Score: {sc:.1f})")


if __name__ == "__main__":
    run_log_analysis()
