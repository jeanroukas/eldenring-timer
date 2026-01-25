import sys
import argparse
import ctypes
from PyQt6.QtWidgets import QApplication
from src.service_container import ServiceContainer
from src.services.base_service import IConfigService, IVisionService, IOverlayService, IStateService, IDatabaseService, ITrayService, IAudioService
from src.services.config_service import ConfigService
from src.services.vision_service import VisionService
from src.services.overlay_service import OverlayService
from src.services.state_service import StateService
from src.services.database_service import DatabaseService
from src.services.tray_service import TrayService
from src.services.audio_service import AudioService
from src.ui.region_selector import RegionSelector
from src.ui.settings_window import SettingsWindow

# Set DPI Awareness
try:
    # Try Per-Monitor V2 (Context -4)
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    try:
        # Fallback to Per-Monitor (2)
        ctypes.windll.shcore.SetProcessDpiAwareness(2) 
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            print("Could not set DPI awareness")

import psutil
import os

class Launcher:
    def __init__(self):
        # Singleton Check
        self.mutex_name = "Global\\EldenRingNightreignTimerMutex_V2"
        self.kernel32 = ctypes.windll.kernel32
        
        self.mutex = self.kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = self.kernel32.GetLastError()
        
        if last_error == 183: # ERROR_ALREADY_EXISTS
            # Another instance is running
            if not self.ask_kill_existing():
                sys.exit(0)
            
            # If we are here, user said YES and we tried to kill logic.
            # Convert to "Restart" flow: Release old mutex handle and try again
            try: self.kernel32.CloseHandle(self.mutex)
            except: pass
            
            import time
            time.sleep(1.0) # Give more time for OS cleanup
            
            self.mutex = self.kernel32.CreateMutexW(None, False, self.mutex_name)
            if self.kernel32.GetLastError() == 183:
                 ctypes.windll.user32.MessageBoxW(0, "Unable to start: Previous instance is still holding the lock.", "Error", 0)
                 sys.exit(0)

        # Qt Application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.container = ServiceContainer()
        self.setup_services()

    def ask_kill_existing(self):
        MB_YESNO = 0x04
        MB_ICONQUESTION = 0x20
        IDYES = 6
        
        result = ctypes.windll.user32.MessageBoxW(0, 
            "An instance of Elden Ring Timer is already running.\nDo you want to terminate it and restart?", 
            "Instance Running", 
            MB_YESNO | MB_ICONQUESTION)
            
        if result == IDYES:
            self.kill_existing_instances()
            return True
        return False
                
    def kill_existing_instances(self):
        current_pid = os.getpid()
        killed = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check for python processes running main.py
                if proc.info['pid'] == current_pid:
                    continue
                    
                cmdline = proc.info.get('cmdline', [])
                if not cmdline: continue
                
                # Heuristic: matches 'main.py' or our exe name
                is_target = False
                if 'python' in proc.info['name'].lower():
                     if any('main.py' in arg for arg in cmdline):
                         is_target = True
                elif 'eldenringtimer' in proc.info['name'].lower():
                     is_target = True
                     
                if is_target:
                    print(f"Killing process {proc.info['pid']}")
                    proc.kill()
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if not killed:
             print("Could not find process to kill, but mutex was held.")
        
    def setup_services(self):
        # 1. Config
        self.config_service = ConfigService()
        self.container.register(IConfigService, self.config_service)

        # 2. Vision
        self.vision_service = VisionService(self.config_service)
        self.container.register(IVisionService, self.vision_service)

        # 3. Overlay
        # Note: OverlayService now doesn't need root window like Tkinter did,
        # but it owns the ModernOverlay.
        self.overlay_service = OverlayService()
        self.container.register(IOverlayService, self.overlay_service)

        # 4. Database
        self.db_service = DatabaseService()
        self.container.register(IDatabaseService, self.db_service)

        # 5. Audio
        self.audio_service = AudioService(self.config_service)
        self.container.register(IAudioService, self.audio_service)

        # 6. Tray (System Icon)
        self.tray_service = TrayService(self)
        self.container.register(ITrayService, self.tray_service)

        # 7. State
        self.state_service = StateService(self.config_service, self.vision_service, self.overlay_service, self.db_service, self.audio_service, self.tray_service)
        self.container.register(IStateService, self.state_service)

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", action="store_true", help="Open configuration window")
        args = parser.parse_args()

        if args.config:
            self.show_config_ui()
        else:
            self.start_application()

        # Run Qt Event Loop
        sys.exit(self.app.exec())

    def show_config_ui(self):
        self.config_service.initialize() # Load config
        self.db_service.initialize() # Load DB for stats
        self.settings = SettingsWindow(self.config_service, self.db_service, self.audio_service)
        self.settings.btn_select_region.clicked.connect(self.select_region)
        self.settings.btn_select_level_region.clicked.connect(self.select_level_region)
        self.settings.btn_select_runes_region.clicked.connect(self.select_runes_region)
        self.settings.show()

    def select_region(self):
        # Modern properties of PyQt Region Selector
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.on_region_selected)
        self.selector.show()

    def select_level_region(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.on_level_region_selected)
        self.selector.show()

    def select_runes_region(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.on_runes_region_selected)
        self.selector.show()
        
    def on_region_selected(self, region):
        self.config_service.set("monitor_region", region)
        self.vision_service.set_region(region)
        print(f"Region saved: {region}")
        # Bring settings back to front if needed
        self.settings.raise_()

    def on_level_region_selected(self, region):
        self.config_service.set("level_region", region)
        self.vision_service.set_level_region(region)
        print(f"Level Region saved: {region}")
        self.settings.raise_()
        # Bring settings back to front if needed
        self.settings.raise_()

    def on_runes_region_selected(self, region):
        self.config_service.set("runes_region", region)
        self.vision_service.set_runes_region(region)
        print(f"Runes Region saved: {region}")
        self.settings.raise_()

    def start_application(self):
        print("Starting Services...")
        self.container.initialize_all()

if __name__ == "__main__":
    launcher = Launcher()
    launcher.run()
