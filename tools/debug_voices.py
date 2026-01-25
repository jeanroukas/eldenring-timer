import asyncio
import pyttsx3
import winsound
import tempfile
import os
import logging
from winsdk.windows.media.speechsynthesis import SpeechSynthesizer
from winsdk.windows.storage.streams import DataReader

# Configure Logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("VoiceDebug")

def list_sapi_voices():
    logger.info("--- SAPI5 Voices ---")
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for v in voices:
        logger.info(f"SAPI: {v.name} | ID: {v.id}")
    del engine

async def list_winrt_voices():
    logger.info("--- WinRT Voices ---")
    try:
        voices = SpeechSynthesizer.all_voices
        for v in voices:
            logger.info(f"WinRT: {v.display_name} | ID: {v.id} | Lang: {v.language}")
            
        # Try speaking with the first French voice
        french_voice = None
        for v in voices:
            if "fr" in v.language.lower():
                french_voice = v
                break
        
        if french_voice:
            logger.info(f"Attempting to speak with: {french_voice.display_name}")
            await test_winrt_speak(french_voice)
        else:
            logger.warning("No French WinRT voice found.")
            
    except Exception as e:
        logger.error(f"WinRT Error: {e}")

async def test_winrt_speak(voice):
    try:
        synthesizer = SpeechSynthesizer()
        synthesizer.voice = voice
        text = "Ceci est un test de voix naturelle."
        
        logger.info("Synthesizing...")
        stream = await synthesizer.synthesize_text_to_stream_async(text)
        
        logger.info(f"Stream generated. Size: {stream.size}")
        
        if stream.size == 0:
            logger.error("Stream size is 0!")
            return

        reader = DataReader(stream.get_input_stream_at(0))
        await reader.load_async(stream.size)
        audio_bytes = reader.read_bytes(stream.size)
        
        logger.info(f"Read {len(audio_bytes)} bytes.")
        
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        with open(path, "wb") as f:
            f.write(bytearray(audio_bytes))
            
        logger.info(f"Saved to {path}. Playing...")
        winsound.PlaySound(path, winsound.SND_FILENAME)
        logger.info("Playback complete.")
        
        os.remove(path)
        
    except Exception as e:
        logger.error(f"Speak Error: {e}", exc_info=True)

if __name__ == "__main__":
    list_sapi_voices()
    asyncio.run(list_winrt_voices())
