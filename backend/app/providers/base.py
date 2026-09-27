from abc import ABC, abstractmethod
from typing import Any

class CloudProvider(ABC):
    name: str

    @abstractmethod
    def test_connection(self, credentials: dict[str, Any]) -> bool: ...

    @abstractmethod
    def collect_resources(self, credentials: dict[str, Any]) -> list[dict[str, Any]]: ...

    @abstractmethod
    def collect_costs(self, credentials: dict[str, Any]) -> list[dict[str, Any]]: ...
