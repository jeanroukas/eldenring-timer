import os
import glob
import json

RAW_DIR = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"

def is_relevant(text):
    """Checks if text is relevant for saving (avoids saving 'OT', 'K', 'S' etc)."""
    if not text: return False
    t = text.upper()
    
    # Valid short tokens (Day numbers, etc)
    valid_short = ["1", "2", "3", "I", "II", "III", "IV", "V"] 
    if len(t) < 3 and t not in valid_short:
        return False

    # Must contain at least one characteristic letter or be a valid day indicator
    # "J" (Jour), "O" (Jour/One), "U" (Jour), "R" (Jour), "I" (1/2/3), "V" (Victory)
    relevant_chars = ["J", "O", "U", "I", "1", "2", "3", "V", "F"] 
    
    # Check for banned signals explicitly
    if t in ["OT", "S", "K", "SS", "OT."]: return False

    if any(c in t for c in relevant_chars):
        return True
    return False

def cleanup():
    print(f"Scanning {RAW_DIR}...")
    json_files = glob.glob(os.path.join(RAW_DIR, "*.json"))
    print(f"Found {len(json_files)} metadata files.")
    
    count_deleted = 0
    count_kept = 0
    
    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            text = data.get('detected_text', '')
            
            if not is_relevant(text):
                print(f"Deleting irrelevant sample: '{text}' ({os.path.basename(json_path)})")
                
                # Construct png path
                png_path = json_path.replace('.json', '.png')
                
                # Remove json
                os.remove(json_path)
                
                # Remove png if exists
                if os.path.exists(png_path):
                    os.remove(png_path)
                
                count_deleted += 1
            else:
                count_kept += 1
                
        except Exception as e:
            print(f"Error processing {json_path}: {e}")

    print(f"Cleanup complete. Deleted: {count_deleted}, Kept: {count_kept}")

if __name__ == "__main__":
    cleanup()
