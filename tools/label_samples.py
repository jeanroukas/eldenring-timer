import cv2
import json
import glob
import os
import sys

# Configuration
RAW_DIR = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
WINDOW_NAME = "Labeler (Press: &='1', post='2', \"='3', a='0'/Skip, ESC=Quit)"

def load_samples():
    print(f"DEBUG: Looking for JSONs in {RAW_DIR}")
    json_patterns = os.path.join(RAW_DIR, "*.json")
    files = glob.glob(json_patterns)
    print(f"DEBUG: Glob found {len(files)} files")
    # Sort by timestamp to label in order
    files.sort()
    return files

def main():
    if not os.path.exists(RAW_DIR):
        print(f"Directory not found: {RAW_DIR}")
        return

    files = load_samples()
    if not files:
        print("ERROR: No .json files found! Check directory path.")
        input("Press Enter to exit...")
        return

    print(f"Found {len(files)} samples. Opening window...")
    
    count = 0
    skipped_already_labeled = 0
    
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 800, 300)

    for json_path in files:
        # Load JSON first to check if already labeled
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            continue

        if "manual_label" in data:
            # Skip already labeled ones
            skipped_already_labeled += 1
            continue 


        png_path = json_path.replace('.json', '.png')
        if not os.path.exists(png_path):
            print(f"Image missing for {json_path}")
            continue

        img = cv2.imread(png_path)
        if img is None:
            print(f"Could not load image: {png_path}")
            continue

        # Draw info on image (visual feedback)
        display_img = img.copy()
        
        # Add text info
        ocr_text = data.get('detected_text', 'N/A')
        curr_label = data.get('manual_label', 'None')
        
        info_str = f"OCR: {ocr_text} | Label: {curr_label} | File: {count+1}/{len(files)}"
        cv2.putText(display_img, info_str, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_img, "KEYS: &=1, \u00e9=2, \"=3, \u00e0=0 (False Positive), SPACE=Skip", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow(WINDOW_NAME, display_img)
        
        print(f"[{count+1}/{len(files)}] {os.path.basename(png_path)} | OCR: {ocr_text} | Current: {curr_label}")

        valid_response = False
        while not valid_response:
            key = cv2.waitKey(0)
            
            # Map AZERTY keys (codes may vary by system, trying standard chars first)
            # Python's ord() can be used for comparison
            
            # '&' -> 1
            if key == ord('&') or key == ord('1'): 
                label = "1"
                valid_response = True
            # 'é' -> 2
            elif key == ord('\u00e9') or key == ord('2'): 
                label = "2"
                valid_response = True
            # '"' -> 3
            elif key == ord('"') or key == ord('3'): 
                label = "3"
                valid_response = True
            # 'à' -> 0 (False Positive)
            elif key == ord('\u00e0') or key == ord('0'): 
                label = "0"
                valid_response = True
            # ESC
            elif key == 27:
                print("Exiting...")
                cv2.destroyAllWindows()
                return
            # Space to skip
            elif key == 32:
                print("Skipping...")
                valid_response = True
                label = None
            else:
                print(f"Unknown key: {key}")

        if label is not None:
            data['manual_label'] = label
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f" -> Labeled as: {label}")
        
        count += 1

    cv2.destroyAllWindows()
    print("Labeling session finished.")

if __name__ == "__main__":
    main()
