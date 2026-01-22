import cv2
import numpy as np
from windows_capture import WindowsCapture
import time

def test_wgc_mon1():
    print("Testing WGC on Monitor 1...")
    frame_captured = None
    
    # Trying index 1 as 0 failed with "must be greater than zero"
    try:
        capture = WindowsCapture(monitor_index=1)
        
        @capture.event
        def on_frame_arrived(frame, control):
            nonlocal frame_captured
            print(f"Frame captured: {frame.width}x{frame.height}")
            frame_captured = frame.frame_buffer.copy()
            control.stop()

        @capture.event
        def on_closed():
            print("Capture closed.")

        capture.start()
    except Exception as e:
        print(f"WGC Error on Index 1: {e}")

    if frame_captured is not None:
        bgr = cv2.cvtColor(frame_captured, cv2.COLOR_BGRA2BGR)
        cv2.imwrite("wgc_mon1_raw.png", bgr)
        print("Saved wgc_mon1_raw.png")
    else:
        print("Failed to capture frame on Monitor 1.")

if __name__ == "__main__":
    test_wgc_mon1()
