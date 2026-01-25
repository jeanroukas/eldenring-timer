import random
import time
from src.services.config_service import ConfigService
from src.services.audio_service import AudioService
from src.logger import logger
import logging

# Configure logger to print to console
logging.basicConfig(level=logging.DEBUG)

def monkey_test_audio():
    print("Starting Monkey Test for AudioService...")
    
    # Setup
    config = ConfigService()
    config.initialize()
    audio = AudioService(config)
    audio.initialize()
    
    print("Wait for init...")
    time.sleep(2)
    
    phrases = ["Test 1", "Test 2", "Longer phrase for testing blockage", "Rapid fire"]
    
    # Rapid fire test
    print("Injecting 10 phrases rapidly...")
    for i in range(10):
        p = f"Message {i}"
        print(f"Injecting: {p}")
        audio.announce(p)
        time.sleep(0.1) # vary this to simulate rapid clicks
        
    print("Waiting for completion...")
    time.sleep(10)
    
    print("Shutting down...")
    audio.shutdown()

if __name__ == "__main__":
    monkey_test_audio()
