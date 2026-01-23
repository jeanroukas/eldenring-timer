
try:
    import dxcam
    print("dxcam: AVAILABLE")
except ImportError:
    print("dxcam: MISSING")

try:
    import mss
    print("mss: AVAILABLE")
except ImportError:
    print("mss: MISSING")
