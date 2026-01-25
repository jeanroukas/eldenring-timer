import pyttsx3
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_run_audio():
    print("Initializing TTS...")
    engine = pyttsx3.init()
    
    # Try to match the app's voice selection logic
    voices = engine.getProperty('voices')
    selected_voice = None
    for v in voices:
        if "Hortense" in v.name:
            selected_voice = v.id
            break
    if not selected_voice:
        for v in voices:
            if "French" in v.name or "Français" in v.name:
                selected_voice = v.id
                break
    
    if selected_voice:
        engine.setProperty('voice', selected_voice)
        print(f"Using voice: {selected_voice}")
    
    engine.setProperty('rate', 165)
    engine.setProperty('volume', 0.5) # Default 50%

    phrases = [
        "La zone se refermera dans 4 minutes 30 secondes",
        "Fermeture de la zone dans 2 minutes",
        "Fermeture de la zone dans 1 minute",
        "Dans 30 secondes",
        "5 secondes",
        "La zone se referme",
        "Victoire !"
    ]

    print("Playing sample run phrases...")
    for phrase in phrases:
        print(f"Speaking: {phrase}")
        engine.say(phrase)
        engine.runAndWait()
        time.sleep(1)

if __name__ == "__main__":
    test_run_audio()
