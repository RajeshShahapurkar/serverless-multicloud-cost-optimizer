from datetime import date, timedelta
from typing import Any

import boto3

from .base import CloudProvider


class AWSProvider(CloudProvider):
    name = "aws"

    def test_connection(self, credentials: dict[str, Any]) -> bool:
        return bool(
            credentials.get("access_key_id")
            and credentials.get("secret_access_key")
        )

    def collect_resources(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        # Resource inventory will be added after AWS account connection is enabled.
        return []

    def collect_costs(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        access_key_id = credentials.get("access_key_id")
        secret_access_key = credentials.get("secret_access_key")
        session_token = credentials.get("session_token")
        days = int(credentials.get("days", 30))

        if not access_key_id or not secret_access_key:
            raise ValueError("AWS credentials are required for cost collection")
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")

        end = date.today()
        start = end - timedelta(days=days)

        client = boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
        )

        response = client.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        records: list[dict[str, Any]] = []
        for result in response.get("ResultsByTime", []):
            period_start = result.get("TimePeriod", {}).get("Start")
            period_end = result.get("TimePeriod", {}).get("End")
            for group in result.get("Groups", []):
                service_name = group.get("Keys", ["Unknown service"])[0]
                metric = group.get("Metrics", {}).get("UnblendedCost", {})
                try:
                    amount = float(metric.get("Amount", 0))
                except (TypeError, ValueError):
                    amount = 0.0

                if amount == 0:
                    continue

                records.append(
                    {
                        "provider": "aws",
                        "amount": amount,
                        "currency": metric.get("Unit", "USD"),
                        "service_name": service_name,
                        "period_start": period_start,
                        "period_end": period_end,
                        "metadata": {
                            "metric": "UnblendedCost",
                            "granularity": "DAILY",
                        },
                    }
                )

        return records
