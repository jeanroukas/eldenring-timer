from typing import Dict, Type, TypeVar, Optional
from src.services.base_service import IService

T = TypeVar('T', bound=IService)

class ServiceContainer:
    _instance = None
    _services: Dict[Type[IService], IService] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceContainer, cls).__new__(cls)
        return cls._instance

    def register(self, interface: Type[T], implementation: T) -> None:
        """Register a service implementation for an interface."""
        self._services[interface] = implementation
        # Simple Dependency Injection for property setters if needed
        # but for now we rely on constructor injection manually in main.py


    def resolve(self, interface: Type[T]) -> T:
        """Resolve a service by its interface."""
        if interface not in self._services:
            raise KeyError(f"Service {interface.__name__} not registered")
        return self._services[interface]

    def initialize_all(self) -> None:
        """Initialize all registered services."""
        for service in self._services.values():
            service.initialize()

    def shutdown_all(self) -> None:
        """Shutdown all registered services."""
        for service in self._services.values():
            service.shutdown()
