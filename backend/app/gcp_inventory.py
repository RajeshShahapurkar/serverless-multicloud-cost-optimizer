from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

GCP_ASSET_SEARCH_URL = "https://cloudasset.googleapis.com/v1/projects/{project_id}:searchAllResources"
GCP_MONITORING_TIMESERIES_URL = "https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"

ASSET_RESOURCE_TYPES = {
    "compute.googleapis.com/Instance": "compute_instance",
    "compute.googleapis.com/Disk": "compute_disk",
    "compute.googleapis.com/Address": "compute_address",
    "compute.googleapis.com/Network": "compute_network",
    "compute.googleapis.com/Subnetwork": "compute_subnetwork",
    "run.googleapis.com/Service": "cloud_run_service",
    "run.googleapis.com/Job": "cloud_run_job",
    "sqladmin.googleapis.com/Instance": "cloud_sql_instance",
    "storage.googleapis.com/Bucket": "storage_bucket",
    "cloudfunctions.googleapis.com/Function": "cloud_function",
    "appengine.googleapis.com/Application": "app_engine_application",
    "appengine.googleapis.com/Service": "app_engine_service",
    "container.googleapis.com/Cluster": "gke_cluster",
    "artifactregistry.googleapis.com/Repository": "artifact_registry_repository",
}

READ_MASK = "name,assetType,location,labels,state,versionedResources"


def normalize_asset(asset: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    name = asset.get("name")
    asset_type = asset.get("assetType")
    if not name or not asset_type:
        return None

    resource_type = ASSET_RESOURCE_TYPES.get(
        asset_type,
        asset_type.split("/")[-1].lower(),
    )
    resource_name = name.rstrip("/").split("/")[-1] or name
    location = asset.get("location")
    metadata = {
        "project_id": project_id,
        "asset_name": name,
        "asset_type": asset_type,
        "labels": asset.get("labels") or {},
        "state": asset.get("state"),
    }

    versioned = asset.get("versionedResources") or []
    if versioned:
        metadata["versioned_resources"] = versioned[:3]

    return {
        "resource_id": f"gcp:asset:{name}",
        "resource_type": resource_type,
        "resource_name": resource_name,
        "region": location,
        "status": asset.get("state"),
        "metadata": metadata,
    }


async def search_all_resources(
    access_token: str,
    project_id: str,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    resources: list[dict[str, Any]] = []
    page_token: str | None = None

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, Any] = {
                "pageSize": min(page_size, 500),
                "readMask": READ_MASK,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await client.get(
                GCP_ASSET_SEARCH_URL.format(project_id=project_id),
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            resources.extend(data.get("results", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return resources


async def list_compute_cpu_utilization(
    access_token: str,
    project_id: str,
    days: int = 7,
) -> dict[str, dict[str, Any]]:
    days = max(1, min(days, 30))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "filter": (
            'metric.type="compute.googleapis.com/instance/cpu/utilization" '
            'AND resource.type="gce_instance"'
        ),
        "interval.startTime": start.isoformat().replace("+00:00", "Z"),
        "interval.endTime": end.isoformat().replace("+00:00", "Z"),
        "view": "FULL",
        "pageSize": 1000,
        "aggregation.alignmentPeriod": "3600s",
        "aggregation.perSeriesAligner": "ALIGN_MEAN",
    }

    results: dict[str, dict[str, Any]] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            GCP_MONITORING_TIMESERIES_URL.format(project_id=project_id),
            headers=headers,
            params=params,
        )

        # Cloud Monitoring is optional for projects without billing.
        # Resource inventory synchronization should continue normally.
        if response.status_code == 403:
            return {}

        response.raise_for_status()

        for series in response.json().get("timeSeries", []):
            resource_labels = (series.get("resource") or {}).get("labels") or {}
            metric_labels = (series.get("metric") or {}).get("labels") or {}
            instance_id = resource_labels.get("instance_id")
            instance_name = metric_labels.get("instance_name")
            values: list[float] = []

            for point in series.get("points", []):
                value = (point.get("value") or {}).get("doubleValue")
                if value is not None:
                    values.append(float(value))

            if not values:
                continue

            sample = {
                "metric_name": "cpu_utilization",
                "metric_value": sum(values) / len(values),
                "unit": "ratio",
                "recorded_at": end.isoformat(),
                "period_days": days,
                "sample_count": len(values),
                "instance_id": instance_id,
                "instance_name": instance_name,
                "zone": resource_labels.get("zone"),
            }

            if instance_id:
                results[instance_id] = sample
            if instance_name:
                results[instance_name] = sample

    return results