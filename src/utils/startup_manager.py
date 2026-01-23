"""Windows startup registry manager for Elden Ring Timer."""
import winreg
import os
import sys


class StartupManager:
    """Manages Windows startup registry entries."""
    
    APP_NAME = "EldenRingTimer"
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    @staticmethod
    def is_enabled():
        """Check if app is set to run at startup.
        
        Returns:
            bool: True if app is in startup registry, False otherwise.
        """
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                StartupManager.REG_PATH, 
                                0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, StartupManager.APP_NAME)
            winreg.CloseKey(key)
            return value is not None
        except WindowsError:
            return False
    
    @staticmethod
    def enable():
        """Add app to Windows startup.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Get executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                exe_path = sys.executable
            else:
                # Running from script - use pythonw + main.py
                python_path = sys.executable.replace("python.exe", "pythonw.exe")
                # Get main.py path (3 levels up from this file)
                main_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                    "main.py"
                )
                exe_path = f'"{python_path}" "{main_path}"'
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                StartupManager.REG_PATH,
                                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, StartupManager.APP_NAME, 0, 
                             winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            print(f"Startup: Enabled at path: {exe_path}")
            return True
        except Exception as e:
            print(f"Startup: Failed to enable: {e}")
            return False
    
    @staticmethod
    def disable():
        """Remove app from Windows startup.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                StartupManager.REG_PATH,
                                0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, StartupManager.APP_NAME)
            winreg.CloseKey(key)
            print("Startup: Disabled")
            return True
        except WindowsError:
            # Already not in startup
            return True
        except Exception as e:
            print(f"Startup: Failed to disable: {e}")
            return False
