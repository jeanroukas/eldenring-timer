import asyncio
import sys
import os

# Adjust path to find src
sys.path.append(os.getcwd())

try:
    from src.windows_capture import WindowsCapture
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def main():
    wc = WindowsCapture(monitor_index=0)
    print("Starting WGC...")
    wc.start()
    
    import time
    time.sleep(3)
    
    print("Checking frame...")
    frame = wc.get_latest_frame()
    if frame is None:
        print("Frame is None!")
    else:
        print(f"Frame received! Shape: {frame.shape}")
        
    print("Stopping...")
    wc.stop()
    print("Done.")

if __name__ == "__main__":
    main()
