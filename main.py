import tkinter as tk
import argparse
import sys
import ctypes
from src.service_container import ServiceContainer
from src.services.base_service import IConfigService, IVisionService, IOverlayService, IStateService
from src.services.config_service import ConfigService
from src.services.vision_service import VisionService
from src.services.overlay_service import OverlayService
from src.services.state_service import StateService
from src.region_selector import RegionSelector

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

        self.root = tk.Tk()
        self.root.withdraw()

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
        self.overlay_service = OverlayService(self.root)
        self.container.register(IOverlayService, self.overlay_service)

        # 4. State
        self.state_service = StateService(self.config_service, self.vision_service, self.overlay_service)
        self.container.register(IStateService, self.state_service)

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", action="store_true", help="Open configuration window")
        args = parser.parse_args()

        if args.config:
            self.show_config_ui()
        else:
            self.start_application()

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.container.shutdown_all()

    def show_config_ui(self):
        self.root.title("Nightreign Timer Controller")
        self.root.geometry("300x200")
        self.root.deiconify()
        
        # Load config to vars
        self.config_service.initialize() # Load config
        
        tk.Button(self.root, text="Select Region", command=self.select_region).pack(pady=10)
        
        self.debug_var = tk.BooleanVar(value=self.config_service.get("debug_mode", False))
        self.save_images_var = tk.BooleanVar(value=self.config_service.get("save_debug_images", False))
        self.hdr_mode_var = tk.BooleanVar(value=self.config_service.get("hdr_mode", False))
        self.save_raw_samples_var = tk.BooleanVar(value=self.config_service.get("save_raw_samples", True))
        
        tk.Checkbutton(self.root, text="Debug Mode (Logs)", variable=self.debug_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="Save Debug Images", variable=self.save_images_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="HDR Mode (High Compatibility)", variable=self.hdr_mode_var, command=self.update_config).pack()
        tk.Checkbutton(self.root, text="Collect Training Data (Raw)", variable=self.save_raw_samples_var, command=self.update_config).pack()

        tk.Button(self.root, text="Start Overlay", command=self.start_application_from_ui).pack(pady=10)

    def select_region(self):
        self.root.withdraw()
        RegionSelector(self.on_region_selected)

    def on_region_selected(self, region):
        self.config_service.set("monitor_region", region)
        self.vision_service.set_region(region) # Might not be initialized yet but method handles it
        print(f"Region saved: {region}")
        self.root.deiconify()

    def update_config(self):
        self.config_service.set("debug_mode", self.debug_var.get())
        self.config_service.set("save_debug_images", self.save_images_var.get())
        self.config_service.set("hdr_mode", self.hdr_mode_var.get())
        self.config_service.set("save_raw_samples", self.save_raw_samples_var.get())
        # ConfigService auto-saves on set

    def start_application_from_ui(self):
        self.root.withdraw()
        self.start_application()

    def start_application(self):
        # If we came from config UI, ConfigService is already "initialized" (loaded).
        # ServiceContainer.initialize_all() will call initialize() on all.
        # ConfigService.initialize() re-loads, which is fine.
        print("Starting Services...")
        self.container.initialize_all()

if __name__ == "__main__":
    launcher = Launcher()
    launcher.run()
