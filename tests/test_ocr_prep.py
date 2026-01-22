import unittest
import os
import shutil
import cv2
import numpy as np
import time
from src.vision_engine import VisionEngine

class MockConfig:
    def get(self, key, default=None):
        if key == "monitor_region": return {"top": 0, "left": 0, "width": 100, "height": 100}
        return default

class TestOCRMLPrep(unittest.TestCase):
    def setUp(self):
        self.config = MockConfig()
        self.engine = VisionEngine(self.config)
        self.test_samples_dir = os.path.join(self.engine.project_root, "samples")
        
        # Clean samples dir for test
        if os.path.exists(self.test_samples_dir):
            shutil.rmtree(self.test_samples_dir)

    def tearDown(self):
        if self.engine:
            self.engine.stop()

    def test_save_labeled_sample(self):
        # 1. Mock a frame
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        self.engine.last_raw_frame = dummy_frame
        self.engine.last_frame_timestamp = time.time()
        
        # 2. Save
        self.engine.save_labeled_sample("TEST_LABEL")
        
        # 3. Verify
        label_dir = os.path.join(self.test_samples_dir, "TEST_LABEL")
        self.assertTrue(os.path.exists(label_dir))
        files = os.listdir(label_dir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith(".png"))

    def test_save_labeled_sample_expired(self):
        # 1. Mock an OLD frame
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        self.engine.last_raw_frame = dummy_frame
        self.engine.last_frame_timestamp = time.time() - 2.0 # 2 seconds ago
        
        # 2. Save
        self.engine.save_labeled_sample("SHOULD_NOT_EXIST")
        
        # 3. Verify
        label_dir = os.path.join(self.test_samples_dir, "SHOULD_NOT_EXIST")
        self.assertFalse(os.path.exists(label_dir))

if __name__ == '__main__':
    unittest.main()
