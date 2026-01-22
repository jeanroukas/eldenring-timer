import ctypes
from ctypes import wintypes

# DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()

def get_monitors():
    user32 = ctypes.windll.user32
    screens = []

    def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        screens.append({
            "hMonitor": hMonitor,
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top
        })
        return True

    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_proc), 0)
    return screens

if __name__ == "__main__":
    monitors = get_monitors()
    print("Detected Monitors (Physical Coordinates):")
    for i, m in enumerate(monitors):
        print(f"Monitor {i}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})")

    import bettercam
    print("\nBetterCam Output Info:")
    print(bettercam.output_info())
