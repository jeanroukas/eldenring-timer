import cv2
import numpy as np
from windows_capture import WindowsCapture
import time

def test_capture():
    print("Testing WindowsCapture (WGC)...")
    
    # Simple monitor indices (usually 0, 1, 2)
    # The user has 3 monitors.
    # Monitor 0 is primary (3840x2160)
    
    frame_captured = None
    
    capture = WindowsCapture(monitor_index=0)
    
    @capture.event
    def on_frame_arrived(frame, control):
        nonlocal frame_captured
        print(f"Frame arrived: {frame.width}x{frame.height}")
        # frame.frame_buffer is the numpy array
        frame_captured = frame.frame_buffer.copy()
        control.stop()

    @capture.event
    def on_closed():
        print("Capture session closed.")

    print("Starting capture session (waiting for frame)...")
    # start() is blocking until control.stop() is called or window closed
    capture.start()
    
    if frame_captured is not None:
        # BGRA to BGR for saving
        # frame_buffer is usually BGRA according to source
        bgr = cv2.cvtColor(frame_captured, cv2.COLOR_BGRA2BGR)
        cv2.imwrite("wgc_debug_raw.png", bgr)
        print("Saved wgc_debug_raw.png")
        
        # Test adaptive thresholding
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 
            11, 2
        )
        cv2.imwrite("wgc_debug_proc.png", thresh)
        print("Saved wgc_debug_proc.png")
    else:
        print("No frame captured.")

if __name__ == "__main__":
    try:
        test_capture()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
