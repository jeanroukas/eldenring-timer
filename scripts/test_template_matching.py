import cv2
import numpy as np
import os
import sys

def run_template_matching_test(directory):
    print("--- Template Matching Test ---")
    
    # 1. Pick a "Golden Sample" (Template)
    # This file was identified as a clear "JOUR II" in previous successful OCR runs
    template_filename = "raw_20260123_040758_634_JOURII_b92.png" 
    template_path = os.path.join(directory, template_filename)
    
    if not os.path.exists(template_path):
        print(f"Error: Template {template_filename} not found!")
        # Fallback to first png if specific one missing (for portability)
        files = [f for f in os.listdir(directory) if f.endswith(".png")]
        if not files: return
        template_path = os.path.join(directory, files[0])
        print(f"Fallback Template: {files[0]}")

    # Load and Preprocess Template
    # We use EDGE DETECTION (Canny) or THRESHOLD for matching to be robust to brightness
    template_img = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    
    # Crop the template to just the "JOUR" part if possible, or use the whole thing?
    # These raw images are usually "JOUR II" fully framed.
    # Let's use the whole thing for now, assuming "JOUR II" is the common case we want to catch.
    # But wait, "JOUR I" won't match "JOUR II" template well.
    # Ideally we want a "JOUR" template.
    
    # Let's try to construct a "JOUR" only template by cropping
    h, w = template_img.shape
    # Assuming "JOUR II" is centered or left aligned. "JOUR" is likely the first 60-70%.
    # Let's crop 0 to 70% of width for a "JOUR" generic template?
    # Or just use the full "JOUR II" and see what happens.
    
    # Preprocessing (Otsu) to normalize
    _, template_thresh = cv2.threshold(template_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Resize template to ensure we match at same scale (images should be same scale)
    
    files = [f for f in os.listdir(directory) if f.lower().endswith(".png")]
    print(f"Template: {template_filename}")
    print(f"Testing on {len(files)} images...")
    
    matches = []
    
    for filename in files:
        img_path = os.path.join(directory, filename)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None: continue
        
        # Preprocess Target
        _, img_thresh = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Match
        # We need to handle size difference. 
        # If template is larger than image, matchTemplate fails.
        th, tw = template_thresh.shape
        ih, iw = img_thresh.shape
        
        if th > ih or tw > iw:
             # Scale down template or skip?
             # For this test, skip if incompatible
             continue
             
        res = cv2.matchTemplate(img_thresh, template_thresh, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # Ground Truth check
        is_jour_ii = "JOURII" in filename or "JOUR II" in filename
        
        matches.append({
             "file": filename,
             "score": max_val,
             "is_target": is_jour_ii
        })
        
    # Stats
    # Sort by score
    matches.sort(key=lambda x: x["score"], reverse=True)
    
    print("\nTop 10 Matches:")
    for m in matches[:10]:
        print(f"{m['score']:.2f} | {m['file']} ({'TARGET' if m['is_target'] else 'other'})")
        
    print("\nBottom 5 Matches (of those that should match):")
    targets = [m for m in matches if m["is_target"]]
    for m in targets[-5:]:
        print(f"{m['score']:.2f} | {m['file']}")
        
    # Analyze separation
    avg_target = np.mean([m['score'] for m in targets]) if targets else 0
    non_targets = [m for m in matches if not m["is_target"]]
    avg_non_target = np.mean([m['score'] for m in non_targets]) if non_targets else 0
    
    print(f"\nAvg Score for 'JOUR II': {avg_target:.2f}")
    print(f"Avg Score for Others:    {avg_non_target:.2f}")

if __name__ == "__main__":
    target_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_images", "fine tune")
    run_template_matching_test(target_dir)
