import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

# Mocking some behaviors for headless testing if needed
# But here we just want to see if imports and basic init work

try:
    from main import Launcher
    print("Launcher import successful")
    
    # We can't run the full Launcher.run() because of the mainloop
    # but we can check setup_services
    
    app = QApplication(sys.argv)
    launcher = Launcher()
    launcher.setup_services()
    print("Services setup successful")
    
    # Check if container has all services
    from src.services.base_service import IConfigService, IVisionService, IOverlayService, IStateService
    
    services = [IConfigService, IVisionService, IOverlayService, IStateService]
    for s in services:
        try:
            instance = launcher.container.resolve(s)
            print(f"Service {s.__name__} resolved successfully: {type(instance).__name__}")
        except Exception as e:
            print(f"Failed to resolve {s.__name__}: {e}")
            sys.exit(1)
            
    print("Smoke test passed!")
    sys.exit(0)
    
except Exception as e:
    print(f"Smoke test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
