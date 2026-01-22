from src.pattern_manager import PatternManager
import os
import json

def test_pattern_manager():
    # 1. Setup - use a temporary file for testing
    test_json = "test_patterns.json"
    if os.path.exists(test_json):
        os.remove(test_json)
        
    pm = PatternManager(filepath=test_json)
    
    print("--- Testing Pattern Manager ---")
    
    # 2. Test Exact Matches
    tests = [
        ("JOUR 1", "DAY 1", 900, [{"text": "JOUR", "left": 100}, {"text": "1", "left": 210}]),
        ("JOUR I", "DAY 1", 900, [{"text": "JOUR", "left": 100}, {"text": "I", "left": 210}]),
        ("JOUR 2", "DAY 2", 950, [{"text": "JOUR", "left": 100}, {"text": "2", "left": 210}]),
        ("JOUR II", "DAY 2", 950, [{"text": "JOUR", "left": 100}, {"text": "II", "left": 210}]),
        ("JOUR 3", "DAY 3", 1300, [{"text": "JOUR", "left": 100}, {"text": "3", "left": 500}]),
        ("JOUR III", "DAY 3", 1300, [{"text": "JOUR", "left": 100}, {"text": "III", "left": 500}]),
    ]
    
    for input_text, expected_target, width, w_data in tests:
        target, score = pm.evaluate(input_text, text_width=width, word_data=w_data)
        print(f"Input: '{input_text}' (w={width}) -> Target: {target} (Score: {score})")
        assert target == expected_target, f"Failed: Expected {expected_target} for {input_text}, got {target}"

    # 3. Test Fuzzy Matches
    fuzzy_tests = [
        ("JOWR II", "DAY 2", 950, [{"text": "JOWR", "left": 100}, {"text": "II", "left": 210}]),
        ("JOURI", "DAY 1", 900, [{"text": "JOURI", "left": 100}]),
    ]
    
    for input_text, expected_target, width, w_data in fuzzy_tests:
        target, score = pm.evaluate(input_text, text_width=width, word_data=w_data)
        print(f"Fuzzy Input: '{input_text}' (w={width}) -> Target: {target} (Score: {score})")
        assert target == expected_target, f"Failed Fuzzy: Expected {expected_target} for {input_text}, got {target}"

    # 4. Test Learning
    print("\nTesting Learning...")
    pm.learn("NEW JOUR PATTERN", "DAY 3")
    target, score = pm.evaluate("NEW JOUR PATTERN", text_width=1300)
    print(f"Learned Input: 'NEW JOUR PATTERN' -> Target: {target} (Score: {score})")
    assert target == "DAY 3"
    
    # Check stats
    print(f"Stats: {pm.stats}")
    assert pm.stats.get("day3_count") == 1
    
    # Check JSON content
    with open(test_json, 'r') as f:
        data = json.load(f)
        assert "NEW JOUR PATTERN" in data["patterns"]
        assert data["patterns"]["NEW JOUR PATTERN"]["target"] == "DAY 3"
        print("JSON content verification passed.")

    print("\n--- All Tests Passed! ---")
    
    # Cleanup
    if os.path.exists(test_json):
        os.remove(test_json)

if __name__ == "__main__":
    try:
        test_pattern_manager()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
