import asyncio
from winsdk.windows.media.speechsynthesis import SpeechSynthesizer

async def list_winrt_voices():
    print("Enumerating WinRT (Windows 10/11) Voices...")
    try:
        synthesizer = SpeechSynthesizer()
        voices = SpeechSynthesizer.all_voices
        
        print(f"Count: {len(voices)}")
        for voice in voices:
            print(f"Name: {voice.display_name}")
            print(f"Language: {voice.language}")
            print(f"ID: {voice.id}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_winrt_voices())
