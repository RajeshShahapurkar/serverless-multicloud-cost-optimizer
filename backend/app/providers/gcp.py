from typing import Any
from .base import CloudProvider

class GCPProvider(CloudProvider):
    name="gcp"
    def test_connection(self, credentials: dict[str,Any])->bool: return False
    def collect_resources(self, credentials: dict[str,Any])->list[dict[str,Any]]: return []
    def collect_costs(self, credentials: dict[str,Any])->list[dict[str,Any]]: return []
