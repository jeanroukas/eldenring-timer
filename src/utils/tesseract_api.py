import ctypes
import os
import cv2
import numpy as np

class TesseractAPI:
    def __init__(self, dll_path, tessdata_path, lang="fra"):
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"Tesseract DLL not found at: {dll_path}")
        
        self.lib = ctypes.CDLL(dll_path)
        
        # Define API signatures
        self.lib.TessBaseAPICreate.restype = ctypes.c_void_p
        
        self.lib.TessBaseAPIInit3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.TessBaseAPIInit3.restype = ctypes.c_int
        
        self.lib.TessBaseAPISetImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        
        self.lib.TessBaseAPIGetUTF8Text.argtypes = [ctypes.c_void_p]
        self.lib.TessBaseAPIGetUTF8Text.restype = ctypes.c_char_p
        
        self.lib.TessBaseAPIDelete.argtypes = [ctypes.c_void_p]
        
        self.lib.TessBaseAPISetVariable.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.TessBaseAPISetVariable.restype = ctypes.c_int
        
        self.lib.TessBaseAPIMeanTextConf.argtypes = [ctypes.c_void_p]
        self.lib.TessBaseAPIMeanTextConf.restype = ctypes.c_int

        self.handle = self.lib.TessBaseAPICreate()
        
        # Initialize
        datapath = tessdata_path.encode('utf-8')
        language = lang.encode('utf-8')
        if self.lib.TessBaseAPIInit3(self.handle, datapath, language) != 0:
            raise RuntimeError("Could not initialize Tesseract API.")
            
        # Optimization: Whitelist characters (based on project needs)
        self.lib.TessBaseAPISetVariable(self.handle, b"tessedit_char_whitelist", b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        # Optimization: PSM 7 (Single daily line)
        self.lib.TessBaseAPISetVariable(self.handle, b"tessedit_pageseg_mode", b"7")

    def get_text(self, image):
        """Processes a grayscale NumPy image and returns (text, confidence)."""
        if image is None: return "", 0
        
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
        h, w = image.shape
        # bytes_per_pixel = 1 for grayscale
        self.lib.TessBaseAPISetImage(self.handle, image.ctypes.data_as(ctypes.c_char_p), w, h, 1, w)
        
        text_ptr = self.lib.TessBaseAPIGetUTF8Text(self.handle)
        if not text_ptr:
            return "", 0
            
        text = ctypes.string_at(text_ptr).decode('utf-8').strip()
        conf = self.lib.TessBaseAPIMeanTextConf(self.handle)
        
        return text, conf

    def __del__(self):
        if hasattr(self, 'handle') and self.handle:
            self.lib.TessBaseAPIDelete(self.handle)
