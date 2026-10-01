from typing import Any
from .base import CloudProvider

class GCPProvider(CloudProvider):
    name = "gcp"

    def test_connection(self, credentials: dict[str, Any]) -> bool:
        return bool(credentials.get("access_token"))

    def collect_resources(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def collect_costs(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        # GCP cost collection is intentionally empty until the account has
        # billing access or a supported billing-export source.
        return []
