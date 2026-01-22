import cv2
import numpy as np

def main():
    print("Click on the 'Key Debugger' window and press keys.")
    print("Press ESC to exit.")
    
    img = np.zeros((200, 400, 3), dtype=np.uint8)
    cv2.putText(img, "Press keys to see codes", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow("Key Debugger", img)

    while True:
        key = cv2.waitKey(0)
        print(f"Key pressed: {key} (Hex: {hex(key)})")
        
        # Redraw to show last key
        display = img.copy()
        cv2.putText(display, f"Last: {key}", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Key Debugger", display)

        if key == 27: # ESC
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
