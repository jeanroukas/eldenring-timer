import json
import os
from typing import Any, Callable
from src.services.base_service import IConfigService

class ConfigService(IConfigService):
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config = {}
        self._observers = []

    def initialize(self) -> bool:
        self.load()
        return True

    def add_observer(self, callback: Callable[[], None]) -> None:
        self._observers.append(callback)

    def _notify_observers(self) -> None:
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                print(f"ConfigService: Error notifying observer: {e}")

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
            self._notify_observers()
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        # Auto-save could be optional, but for now we'll save on set for safety or rely on explicit save
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
