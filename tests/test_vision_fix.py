
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.config_service import ConfigService
from src.vision_engine import VisionEngine

class TestVisionFix(unittest.TestCase):
    def setUp(self):
        self.config_service = ConfigService("test_config.json")
        self.config_service.set("monitor_region", {"top": 0, "left": 0, "width": 100, "height": 100})
        self.config_service.set("debug_mode", True)
        
    def tearDown(self):
        if os.path.exists("test_config.json"):
            os.remove("test_config.json")

    def test_config_dictionary_access(self):
        """Test that ConfigService behaves like a dictionary."""
        self.assertEqual(self.config_service["monitor_region"]["width"], 100)
        self.assertTrue("debug_mode" in self.config_service)
        
        self.config_service["new_key"] = "value"
        self.assertEqual(self.config_service.get("new_key"), "value")

    def test_vision_engine_init(self):
        """Test that VisionEngine initializes without error using ConfigService."""
        engine = VisionEngine(self.config_service)
        self.assertIsNotNone(engine)
        self.assertEqual(engine.config, self.config_service)

    def test_vision_engine_update_region(self):
        """Test that update_region works without crashing."""
        engine = VisionEngine(self.config_service)
        new_region = {"top": 10, "left": 10, "width": 200, "height": 200}
        
        # This triggers _init_camera internally
        try:
            engine.update_region(new_region)
        except Exception as e:
            self.fail(f"update_region raised exception: {e}")
            
        self.assertEqual(self.config_service["monitor_region"], new_region)

if __name__ == '__main__':
    unittest.main()
