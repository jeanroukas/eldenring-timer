import sys
import argparse
import ctypes
from PyQt6.QtWidgets import QApplication
from src.service_container import ServiceContainer
from src.services.base_service import IConfigService, IVisionService, IOverlayService, IStateService, IDatabaseService
from src.services.config_service import ConfigService
from src.services.vision_service import VisionService
from src.services.overlay_service import OverlayService
from src.services.state_service import StateService
from src.services.database_service import DatabaseService
from src.region_selector import RegionSelector
from src.ui.settings_window import SettingsWindow

# Set DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) 
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        print("Could not set DPI awareness")

class Launcher:
    def __init__(self):
        # Singleton Check
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\EldenRingNightreignTimerMutex"
        self.mutex = kernel32.CreateMutexW(None, False, mutex_name)
        if kernel32.GetLastError() == 183:
            print("Another instance is already running. Exiting.")
            sys.exit(0)

        # Qt Application
        self.app = QApplication(sys.argv)
        
        self.container = ServiceContainer()
        self.setup_services()
        
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

        # 5. State
        self.state_service = StateService(self.config_service, self.vision_service, self.overlay_service, self.db_service)
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
        self.settings = SettingsWindow(self.config_service, self.db_service)
        self.settings.btn_select_region.clicked.connect(self.select_region)
        self.settings.show()

    def select_region(self):
        # We need a Tkinter root still for RegionSelector as it's built on Tkinter
        # FOR NOW: We keep it as is, or migrate it.
        # Calling RegionSelector might block or need a root.
        import tkinter as tk
        temp_root = tk.Tk()
        temp_root.withdraw()
        RegionSelector(lambda r: self.on_region_selected(r, temp_root))
        temp_root.mainloop()

    def on_region_selected(self, region, temp_root):
        self.config_service.set("monitor_region", region)
        self.vision_service.set_region(region)
        print(f"Region saved: {region}")
        temp_root.destroy()

    def start_application(self):
        print("Starting Services...")
        self.container.initialize_all()

if __name__ == "__main__":
    launcher = Launcher()
    launcher.run()
