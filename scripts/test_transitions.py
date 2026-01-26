import sys
import os
import time
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.state_service import StateService

def test_transition_guards():
    print("Testing Transition Guards...")
    
    # Mock dependencies
    config = MagicMock()
    db = MagicMock()
    vision = MagicMock()
    overlay = MagicMock()
    audio = MagicMock()
    pattern = MagicMock()
    
    state = StateService(config, db, vision, overlay, audio, pattern)
    
    # Case 1: Early Day 1 -> Day 2 (Should be blocked)
    state.current_phase_index = 0 # Storm
    state.run_accumulated_history = [0] * 100 # 100 seconds elapsed
    penalty = state.get_transition_penalty("DAY 2")
    print(f"Day 1 (100s) -> Day 2 penalty: {penalty} (Expected: -100)")
    assert penalty == -100
    
    # Case 2: Late Day 1 -> Day 2 (Should be soft penalty)
    state.run_accumulated_history = [0] * 800 # 800 seconds elapsed (13.3 mins)
    penalty = state.get_transition_penalty("DAY 2")
    print(f"Day 1 (800s) -> Day 2 penalty: {penalty} (Expected: -30)")
    assert penalty == -30
    
    # Case 3: Boss 1 -> Day 2 (Should be allowed/no extra penalty)
    state.current_phase_index = 4 # Boss 1
    penalty = state.get_transition_penalty("DAY 2")
    print(f"Boss 1 -> Day 2 penalty: {penalty} (Expected: 0)")
    assert penalty == 0
    
    # Case 4: Day 1 -> Day 3 (Skip, should be blocked)
    state.current_phase_index = 0
    penalty = state.get_transition_penalty("DAY 3")
    print(f"Day 1 -> Day 3 penalty: {penalty} (Expected: -40)")
    assert penalty == -40
    
    # Case 5: Day 2 -> Day 3 (Before Boss 2, should be blocked)
    state.current_phase_index = 5 # Day 2 Storm
    penalty = state.get_transition_penalty("DAY 3")
    print(f"Day 2 -> Day 3 penalty: {penalty} (Expected: -100)")
    assert penalty == -100
    
    # Case 6: Boss 2 -> Day 3 (Allowed)
    state.current_phase_index = 9 # Boss 2
    penalty = state.get_transition_penalty("DAY 3")
    print(f"Boss 2 -> Day 3 penalty: {penalty} (Expected: 0)")
    assert penalty == 0

def test_hotkey_guards():
    print("\nTesting Hotkey Guards...")
    
    # Mock dependencies
    config = MagicMock()
    config.get.return_value = False
    db = MagicMock()
    vision = MagicMock()
    overlay = MagicMock()
    audio = MagicMock()
    pattern = MagicMock()
    
    state = StateService(config, db, vision, overlay, audio, pattern)
    state.handle_trigger = MagicMock()
    
    # Case 7: Early Manual Day 2 (Should be ignored)
    state.current_phase_index = 0
    state.run_accumulated_history = [0] * 100
    state.handle_manual_feedback("DAY 2")
    print(f"Early Manual Day 2 triggered: {state.handle_trigger.called} (Expected: False)")
    assert not state.handle_trigger.called
    
    # Case 8: Late Manual Day 2 (Should be allowed)
    state.run_accumulated_history = [0] * 500 # > 8 mins
    state.handle_manual_feedback("DAY 2")
    print(f"Late Manual Day 2 triggered: {state.handle_trigger.called} (Expected: True)")
    assert state.handle_trigger.called

if __name__ == "__main__":
    try:
        test_transition_guards()
        test_hotkey_guards()
        print("\nAll tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
