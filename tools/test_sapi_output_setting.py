import pyttsx3
import comtypes.client

def test_set_output():
    engine = pyttsx3.init()
    
    # Access internal driver
    # engine.proxy is the Engine instance
    # engine.proxy._driver is the SAPI5Driver instance
    driver = engine.proxy._driver
    print(f"Driver type: {type(driver)}")
    print(f"Driver dir: {dir(driver)}")
    
    if hasattr(driver, '_tts'):
        tts = driver._tts
        print("Found _tts object.")
        
        # List outputs
        outputs = tts.GetAudioOutputs()
        print(f"Outputs count: {outputs.Count}")
        
        # Try waiting
        # engine.say("Testing default output")
        # engine.runAndWait()
        
        # Try setting output to index 1 (if exists)
        if outputs.Count > 0:
            new_out = outputs.Item(0) # Just re-setting 0 for safety, or 1 if you want to test
            print(f"Setting output to: {new_out.GetDescription()}")
            tts.AudioOutput = new_out
            
            engine.say("Testing specific output")
            engine.runAndWait()
            print("Speaking finished.")
    else:
        print("_tts not found on driver.")

if __name__ == "__main__":
    test_set_output()
