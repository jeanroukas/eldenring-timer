from src.services.state_service import StateService
from unittest.mock import MagicMock
import time

def test_boss2_transition_logic():
    print("Testing Boss 2 -> Day 3 Transition Logic (Threshold < 3)...")
    
    # Mock dependencies
    mock_config = MagicMock()
    mock_config.get.return_value = True 
    mock_vision = MagicMock()
    mock_overlay = MagicMock()
    mock_db = MagicMock()
    
    # Initialize Service
    service = StateService(mock_config, mock_vision, mock_overlay, mock_db)
    service.current_phase_index = 9 
    service.start_time = time.time()
    
    # CASE 1: Brightness 4.0 (Should FAIL detection with threshold 3)
    print("\n--- Simulating Frame (Brightness=4.0) ---")
    service.process_ocr_trigger(text="", width=0, offset=0, word_data=[], brightness=4.0)
    if service.in_black_screen:
        print("FAILURE: Black screen detected at 4.0 (Should be ignored)")
    else:
        print("SUCCESS: Black screen correctly ignored at 4.0")

    # CASE 2: Brightness 2.0 (Should PASS detection with threshold 3)
    print("\n--- Simulating Frame (Brightness=2.0) ---")
    service.process_ocr_trigger(text="", width=0, offset=0, word_data=[], brightness=2.0)
    if service.in_black_screen:
        print("SUCCESS: Black screen detected at 2.0")
    else:
        print("FAILURE: Black screen NOT detected at 2.0")

    # CASE 3: End Black Screen
    if service.in_black_screen:
        print("\n--- Simulating Frame (Brightness=50) ---")
        time.sleep(0.5) 
        service.process_ocr_trigger(text="", width=0, offset=0, word_data=[], brightness=50.0)
        
        if not service.in_black_screen:
             print("SUCCESS: Black screen ended.")
        else:
             print("FAILURE: Black screen stuck.")

if __name__ == "__main__":
    test_boss2_transition_logic()
