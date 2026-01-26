import threading
import queue
import pyttsx3
import asyncio
import tempfile
import os
import winsound
import pythoncom
from winsdk.windows.media.speechsynthesis import SpeechSynthesizer
from winsdk.windows.storage.streams import DataReader
from src.services.base_service import IAudioService, IConfigService
from src.logger import logger

class AudioService(IAudioService):
    def __init__(self, config_service: IConfigService):
        self.config = config_service
        self.queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.enabled = self.config.get("audio_enabled", True)
        self.available_devices = []
        self.available_voices = []
        self.devices_ready_event = threading.Event()

    def initialize(self) -> bool:
        logger.info("AudioService: Initializing...")
        self.running = True
        self.config.add_observer(self.on_config_changed)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        return True

    def on_config_changed(self):
        self.enabled = self.config.get("audio_enabled", True)
        self.target_volume = self.config.get("audio_volume", 50) / 100.0
        self.target_rate = int(self.config.get("audio_rate", 165))
        self.target_device_id = self.config.get("audio_device_id", "")
        self.target_voice_id = self.config.get("audio_voice_id", "")

    def get_devices(self):
        """Returns list of (id, description) tuples. Blocks until worker has loaded them."""
        if not self.devices_ready_event.wait(timeout=5.0):
            logger.warning("AudioService: Timeout waiting for device list")
            return []
        return self.available_devices

    def get_voices(self):
        """Returns list of (id, name) tuples."""
        if not self.devices_ready_event.wait(timeout=5.0):
             return []
        return self.available_voices
        
    def set_device(self, device_id: str):
        self.config.set("audio_device_id", device_id)
        self.target_device_id = device_id

    def set_voice(self, voice_id: str):
        self.config.set("audio_voice_id", voice_id)
        self.target_voice_id = voice_id

    def shutdown(self) -> None:
        logger.info("AudioService: Shutting down...")
        self.running = False
        self.queue.put(None) # Sentinel
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
            
        # Cleanup temp files
        if hasattr(self, '_temp_files'):
            for f in self._temp_files:
                try: os.remove(f)
                except: pass
            self._temp_files = []

    def announce(self, text: str) -> None:
        if not self.enabled:
            return
        
        self.queue.put(text)
        logger.debug(f"AudioService: Enqueued '{text}' (Queue size: {self.queue.qsize()})")

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.config.set("audio_enabled", enabled)
        logger.info(f"AudioService: Audio {'enabled' if enabled else 'disabled'}")

    async def _enumerate_winrt_voices(self, target_list, seen_ids):
        try:
            synthesizer = SpeechSynthesizer()
            voices = SpeechSynthesizer.all_voices
            for voice in voices:
                if "fr" in voice.language.lower():
                    # Prefix ID to distinguish provider
                    v_id = "WINRT:" + voice.id 
                    if v_id not in seen_ids:
                        name = voice.display_name + " (Naturelle)"
                        target_list.append((v_id, name))
                        seen_ids.add(v_id)
        except Exception as e:
             logger.error(f"AudioService: WinRT enumeration error: {e}")

    async def _speak_winrt(self, text, voice_id_raw, rate, volume):
        # Remove prefix
        voice_id = voice_id_raw.replace("WINRT:", "")
        
        synthesizer = SpeechSynthesizer()
        
        # Find Voice
        voices = SpeechSynthesizer.all_voices
        selected_voice = None
        for v in voices:
            if v.id == voice_id:
                selected_voice = v
                break
        
        if selected_voice:
            synthesizer.voice = selected_voice
            
        # Options
        winrt_rate = rate / 165.0
        synthesizer.options.speaking_rate = max(0.5, min(6.0, winrt_rate))
        synthesizer.options.audio_volume = max(0.0, min(1.0, volume))
        
        try:
            stream = await synthesizer.synthesize_text_to_stream_async(text)
            
            # Read stream to bytes
            size = stream.size
            if size == 0: return

            reader = DataReader(stream.get_input_stream_at(0))
            await reader.load_async(size)
            
            # winsdk DataReader.read_bytes expects a buffer
            audio_buffer = bytearray(size)
            reader.read_bytes(audio_buffer)
            
            # Save to temp
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            
            with open(path, "wb") as f:
                f.write(audio_buffer)
                
            # Play Async to prevent blocking the worker thread (which might hold GIL/IO)
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            
            # Defer cleanup (keep last few files or clean on shutdown)
            # We add to a cleanup list
            if not hasattr(self, '_temp_files'): self._temp_files = []
            self._temp_files.append(path)
            
            # Cleanup old files (> 10)
            if len(self._temp_files) > 10:
                oldest = self._temp_files.pop(0)
                try: os.remove(oldest)
                except: pass
            
        except Exception as e:
            logger.error(f"AudioService: WinRT Speak Error: {e}")
            
        except Exception as e:
            logger.error(f"AudioService: WinRT Speak Error: {e}")


    def _worker(self):
        # Initialize COM for this thread (Required for SAPI5/pyttsx3)
        pythoncom.CoInitialize()
        try:
            # Clear list to start fresh
            self.available_voices = []
            
            # 1. Device Enumeration (Once at startup)
            try:
                # Temp engine for enumeration
                temp_engine = pyttsx3.init()
                try:
                    driver = temp_engine.proxy._driver
                    if hasattr(driver, '_tts'):
                        outputs = driver._tts.GetAudioOutputs()
                        for i in range(outputs.Count):
                            item = outputs.Item(i)
                            desc = item.GetDescription()
                            dev_id = item.Id
                            self.available_devices.append((dev_id, desc))
                except Exception as e:
                    logger.error(f"AudioService: Error enumerating devices: {e}")
                
                # Enumerate SAPI5 Voices (Filtered)
                sapi_voices = []
                seen_ids = set()
                try:
                    voices = temp_engine.getProperty('voices')
                    for v in voices:
                        # Filter for French
                        if "french" in v.name.lower() or "français" in v.name.lower() or "hortense" in v.name.lower():
                            if v.id not in seen_ids:
                                sapi_voices.append((v.id, v.name))
                                seen_ids.add(v.id)
                except Exception as e:
                    logger.error(f"AudioService: Error enumerating voices: {e}")
                    
                del temp_engine
                
                # Enumerate WinRT Voices
                winrt_voices = []
                try:
                    # Pass seen_ids to check against SAPI too (though keys differ) or just for WinRT dupes
                    asyncio.run(self._enumerate_winrt_voices(winrt_voices, seen_ids))
                except Exception as e:
                     logger.error(f"AudioService: Failed to run WinRT enumeration: {e}")

                # SORTING: Natural Voices FIRST
                self.available_voices = winrt_voices + sapi_voices
                
            except Exception as e:
                 logger.error(f"AudioService: Error in startup enumeration: {e}")
                 
            self.devices_ready_event.set()
            logger.info(f"AudioService: Worker thread ready. {len(self.available_voices)} voices found.")

            while self.running:
                try:
                    task = self.queue.get(timeout=0.5) # Check run flag periodically
                    if task is None:
                        break
                    
                    # Speak with fresh engine
                    try:
                        logger.debug(f"AudioService: Speaking '{task}'...")
                        
                        # 1. Determine Provider
                        target_voice = self.config.get("audio_voice_id", "")
                        
                        rate = int(self.config.get("audio_rate", 165))
                        volume = self.config.get("audio_volume", 50) / 100.0
                        
                        if target_voice.startswith("WINRT:"):
                            # Use WinRT
                            try:
                                asyncio.run(self._speak_winrt(task, target_voice, rate, volume))
                            except Exception as e:
                                 logger.error(f"AudioService: Asyncio run failed: {e}")
                        else:
                            # Use SAPI5 (Legacy)
                            engine = pyttsx3.init()
                            
                            # Setup Voice
                            selected_voice = None
                            if target_voice and not target_voice.startswith("WINRT:"):
                                selected_voice = target_voice
                            else:
                                # Auto-select French from SAPI pool if WinRT failed or not selected
                                voices = engine.getProperty('voices')
                                for v in voices:
                                    if "Hortense" in v.name:
                                        selected_voice = v.id
                                        break
                                if not selected_voice:
                                    for v in voices:
                                        if "french" in v.name.lower() or "français" in v.name.lower():
                                            selected_voice = v.id
                                            break
                                            
                            if selected_voice:
                                try:
                                    engine.setProperty('voice', selected_voice)
                                except: pass

                            # Setup Properties
                            engine.setProperty('rate', rate)
                            engine.setProperty('volume', volume)
                            
                            # Setup Device check
                            device_id = self.config.get("audio_device_id", "")
                            if device_id:
                                 try:
                                     driver = engine.proxy._driver
                                     # ... existing device logic
                                     if hasattr(driver, '_tts'):
                                         outputs = driver._tts.GetAudioOutputs()
                                         for i in range(outputs.Count):
                                             if outputs.Item(i).Id == device_id:
                                                 driver._tts.AudioOutput = outputs.Item(i)
                                                 break
                                 except: pass

                            engine.say(task)
                            engine.runAndWait()
                            del engine
                        
                        logger.debug(f"AudioService: Finished speaking '{task}'")
                    except Exception as e:
                        logger.error(f"AudioService: Error speaking '{task}': {e}")
                    
                    self.queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"AudioService: Worker loop error: {e}")
                    
        finally:
            pythoncom.CoUninitialize()
