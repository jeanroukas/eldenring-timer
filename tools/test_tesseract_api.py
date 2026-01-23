import cv2
import numpy as np
import os
import sys
import time
import ctypes

# Path to Tesseract DLL
dll_path = r"C:\Program Files\Tesseract-OCR\libtesseract-5.dll"
tessdata_path = r"C:\Program Files\Tesseract-OCR\tessdata"

if not os.path.exists(dll_path):
    print(f"DLL not found at {dll_path}")
    exit(1)

# Load library
try:
    tess = ctypes.CDLL(dll_path)
except Exception as e:
    print(f"Failed to load DLL: {e}")
    exit(1)

# Define return types and argtypes
tess.TessBaseAPICreate.restype = ctypes.c_void_p
tess.TessBaseAPIInit3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
tess.TessBaseAPIInit3.restype = ctypes.c_int

tess.TessBaseAPISetImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]

tess.TessBaseAPIGetUTF8Text.argtypes = [ctypes.c_void_p]
tess.TessBaseAPIGetUTF8Text.restype = ctypes.c_char_p

tess.TessBaseAPIDelete.argtypes = [ctypes.c_void_p]

# Create API handle
handle = tess.TessBaseAPICreate()

# Initialize
# Note: lang must be bytes
lang = b"fra"
datapath = tessdata_path.encode('utf-8')
if tess.TessBaseAPIInit3(handle, datapath, lang) != 0:
    print("Could not initialize tesseract.")
    exit(1)

# Load a sample image
sample_path = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\samples\raw"
sample_files = [f for f in os.listdir(sample_path) if f.endswith(".png")]
if not sample_files:
    print("No sample images found.")
    exit(1)

img = cv2.imread(os.path.join(sample_path, sample_files[0]))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
height, width = gray.shape

# Run Benchmark
print(f"Starting Direct API Benchmark on {sample_files[0]}...")
start = time.time()
iterations = 100

for i in range(iterations):
    # Set image
    tess.TessBaseAPISetImage(handle, gray.ctypes.data_as(ctypes.c_char_p), width, height, 1, width)
    # Get Text
    text_ptr = tess.TessBaseAPIGetUTF8Text(handle)
    # (Optional) convert to string if needed, but for benchmark just calling it is enough
    # result = ctypes.string_at(text_ptr).decode('utf-8')

end = time.time()
print(f"Direct API: {iterations / (end - start):.2f} FPS")

# Cleanup
tess.TessBaseAPIDelete(handle)
