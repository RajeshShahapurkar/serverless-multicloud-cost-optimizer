from abc import ABC, abstractmethod
from typing import Any

class CloudProvider(ABC):
    name: str

    @abstractmethod
    def authorization_url(self, state: str, redirect_uri: str) -> str:
        """Return the provider's OAuth authorization URL."""
        ...

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an OAuth authorization code for server-side tokens."""
        ...

    @abstractmethod
    def collect_resources(self, access_token: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def collect_costs(self, access_token: str) -> list[dict[str, Any]]:
        ...
