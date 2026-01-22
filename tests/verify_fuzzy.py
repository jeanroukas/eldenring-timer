import sys
import os
import time

# Mocking Config
sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.pattern_manager import PatternManager

def verify_fuzzy_detection():
    print("--- Verifying Fuzzy OCR Detection (Typos) ---")
    
    # Use fresh file
    if os.path.exists("test_fuzzy.json"):
        os.remove("test_fuzzy.json")
    
    pm = PatternManager("test_fuzzy.json")
    
    # Test Cases: Typos -> Expected Target
    cases = [
        ("JUUR I", "DAY 1"),   # Typo of JOUR I
        ("JOOR IL", "DAY 2"),  # Typo of JOUR IL
        ("JUR II", "DAY 2"),   # Typo of JOUR II (Short)
        ("JOUR I", "DAY 1"),   # Exact (Control)
        ("RANDOM", None)       # Noise (Control)
    ]
    
    for text, expected in cases:
        target, score = pm.evaluate(text)
        print(f"Input: '{text}' -> Target: {target} (Score: {score:.2f})")
        
        if expected:
            if target != expected:
                print(f"FAILED: Expected {expected} for '{text}'")
            else:
                print("PASS")
        else:
            if target is not None and score > 20: 
                print(f"WARNING: '{text}' matched {target} unexpectedly")
            else:
                print("PASS (No Match)")
    
    if os.path.exists("test_fuzzy.json"):
        os.remove("test_fuzzy.json")

if __name__ == "__main__":
    verify_fuzzy_detection()
