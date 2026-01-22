import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "monitor_region": {"top": 0, "left": 0, "width": 100, "height": 50},
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "debug_mode": False,
    "ocr_target_height": 160
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print("Config saved.")
    except Exception as e:
        print(f"Error saving config: {e}")
