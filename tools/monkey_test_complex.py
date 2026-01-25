import random
import time
from src.services.config_service import ConfigService
from src.services.audio_service import AudioService
from src.logger import logger
import logging

# Configure logger to print to console
logging.basicConfig(level=logging.DEBUG)

def monkey_test_complex():
    print("Starting Complex Monkey Test...")
    
    # Setup
    config = ConfigService()
    config.initialize()
    audio = AudioService(config)
    audio.initialize()
    
    print("Wait for init...")
    time.sleep(2)
    
    print("1. Speak normal")
    audio.announce("Test Un")
    time.sleep(2)
    
    print("2. Change Volume")
    config.set("audio_volume", 80)
    time.sleep(0.5)
    audio.announce("Volume Changé")
    time.sleep(2)
    
    print("3. Change Rate")
    config.set("audio_rate", 250)
    time.sleep(0.5)
    audio.announce("Vitesse Rapide")
    time.sleep(2)
    
    print("4. Rapid Fire with attribute changes")
    for i in range(5):
        audio.announce(f"Message {i}")
        if i % 2 == 0:
            config.set("audio_volume", 50 + i*5)
        time.sleep(0.2)
        
    print("Waiting for completion...")
    time.sleep(5)
    
    print("Shutting down...")
    audio.shutdown()

if __name__ == "__main__":
    monkey_test_complex()
