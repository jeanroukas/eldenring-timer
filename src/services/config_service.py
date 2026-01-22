import json
import os
from typing import Any
from src.services.base_service import IConfigService

class ConfigService(IConfigService):
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config = {}

    def initialize(self) -> bool:
        self.load()
        return True

    def shutdown(self) -> None:
        self.save()

    def load(self) -> None:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = {}

    def save(self) -> bool:
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        # Auto-save could be optional, but for now we'll save on set for safety or rely on explicit save
        self.save()
