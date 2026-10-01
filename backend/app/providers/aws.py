from datetime import date, timedelta
from typing import Any

import boto3

from .base import CloudProvider


class AWSProvider(CloudProvider):
    name = "aws"

    def assume_role(self, role_arn: str, external_id: str, session_name: str) -> dict[str, Any]:
        if not role_arn or not external_id:
            raise ValueError("AWS role ARN and external ID are required")

        sts = boto3.client("sts", region_name="us-east-1")
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name[:64],
            ExternalId=external_id,
            DurationSeconds=3600,
        )
        credentials = response["Credentials"]
        return {
            "access_key_id": credentials["AccessKeyId"],
            "secret_access_key": credentials["SecretAccessKey"],
            "session_token": credentials["SessionToken"],
            "expiration": credentials["Expiration"],
        }

    def test_connection(self, credentials: dict[str, Any]) -> bool:
        return bool(
            credentials.get("access_key_id")
            and credentials.get("secret_access_key")
            and credentials.get("session_token")
        )

    def collect_resources(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.test_connection(credentials):
            raise ValueError("Temporary AWS credentials are required")

        region = credentials.get("region") or "us-east-1"
        session = boto3.Session(
            aws_access_key_id=credentials["access_key_id"],
            aws_secret_access_key=credentials["secret_access_key"],
            aws_session_token=credentials["session_token"],
            region_name=region,
        )
        ec2 = session.client("ec2")
        response = ec2.describe_instances()

        resources: list[dict[str, Any]] = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = {t["Key"]: t["Value"] for t in instance.get("Tags", []) if "Key" in t}
                resources.append(
                    {
                        "resource_id": instance.get("InstanceId"),
                        "resource_type": "ec2_instance",
                        "resource_name": tags.get("Name") or instance.get("InstanceId"),
                        "region": region,
                        "status": instance.get("State", {}).get("Name"),
                        "metadata": {
                            "instance_type": instance.get("InstanceType"),
                            "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                            "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
                            "tags": tags,
                        },
                    }
                )
        return resources

    def collect_costs(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.test_connection(credentials):
            raise ValueError("Temporary AWS credentials are required")

        days = int(credentials.get("days", 30))
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")

        end = date.today()
        start = end - timedelta(days=days)
        session = boto3.Session(
            aws_access_key_id=credentials["access_key_id"],
            aws_secret_access_key=credentials["secret_access_key"],
            aws_session_token=credentials["session_token"],
            region_name="us-east-1",
        )
        client = session.client("ce")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
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
                        "metadata": {"metric": "UnblendedCost", "granularity": "DAILY"},
                    }
                )
        return records
