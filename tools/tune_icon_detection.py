import cv2
import numpy as np
import glob
import os
import shutil

def tune_icon():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    samples_dir = os.path.join(base_dir, "samples", "icon_raw")
    data_dir = os.path.join(base_dir, "data")
    
    files = sorted(glob.glob(os.path.join(samples_dir, "*.png")))
    if not files:
        print("No samples found.")
        return

    print(f"Loaded {len(files)} samples.")
    
    # 1. Finding a good template
    # Strategy: The icon is consistent. We look for a frame that matches many others well.
    # We'll take a few random candidates and test them against the set.
    
    candidates = files[::len(files)//10][:10] # Take ~10 candidates spread out
    if not candidates: candidates = files[:1]
    
    best_candidate = None
    best_score_separation = 0
    best_threshold = 0.0
    
    print("Analyzing candidates for template...")
    
    for cand_path in candidates:
        template = cv2.imread(cand_path, cv2.IMREAD_GRAYSCALE)
        
        # Apply slight preprocessing to focus on edges/contrast
        # Rune icon is Golden. In grayscale it's bright.
        # Let's try simple thresholding? Or just raw grayscale matching.
        # Raw grayscale is usually robust enough for exact UI elements.
        
        scores = []
        for f_path in files:
            img = cv2.imread(f_path, cv2.IMREAD_GRAYSCALE)
            res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            scores.append(max_val)
            
        scores = np.array(scores)
        
        # Analyze distribution
        # We expect two clusters: High Matches (Icon Present) and Low Matches (Icon Absent)
        # Or just High Matches if user didn't hide it enough.
        
        avg = np.mean(scores)
        std = np.std(scores)
        
        # Simple Clustering (K-Means/Otsu-like logic) on scalar?
        # Let's try to find a split.
        hist, bin_edges = np.histogram(scores, bins=20, range=(0,1))
        
        # We want a candidate that produces a lot of HIGH scores (>0.8) and some LOW scores (<0.6)
        # If everything is >0.9, maybe the icon was never hidden, or the candidate is too generic (black screen?)
        # If everything is <0.5, the candidate is garbage.
        
        high_matches = scores[scores > 0.8]
        low_matches = scores[scores < 0.6]
        
        if len(high_matches) > len(files) * 0.1: # At least 10% valid matches
             separation = np.mean(high_matches) - (np.mean(low_matches) if len(low_matches) > 0 else 0)
             
             if separation > best_score_separation:
                 best_score_separation = separation
                 best_candidate = cand_path
                 
                 # Determine threshold
                 if len(low_matches) > 0:
                     best_threshold = (np.min(high_matches) + np.max(low_matches)) / 2
                 else:
                     best_threshold = 0.75 # Default fallback
                     
    if best_candidate:
        print(f"Best Template Found: {os.path.basename(best_candidate)}")
        print(f"Estimated Threshold: {best_threshold:.2f}")
        
        # Save Template
        template_save_path = os.path.join(data_dir, "rune_icon_template.png")
        shutil.copy2(best_candidate, template_save_path)
        print(f"Saved template to {template_save_path}")
        
        # Save Config Recommendation (Optional - just print for now)
        print("Recommended Configuration:")
        print(f"  Threshold: {best_threshold:.2f}")
    else:
        print("Could not determine a good template. Maybe the icon was never visible or never hidden?")

if __name__ == "__main__":
    tune_icon()
