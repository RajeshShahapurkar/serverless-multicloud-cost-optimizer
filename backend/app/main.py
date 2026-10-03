import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .providers.aws import AWSProvider
from .gcp_oauth import GCP_SCOPES, build_authorization_url, exchange_code, encrypt_tokens, list_billing_accounts, refresh_access_token, list_projects, list_compute_instances
from .gcp_inventory import search_all_resources, normalize_asset, list_compute_cpu_utilization
from .security import verify_state, decrypt_secret, encrypt_secret

app = FastAPI(title="Multi-Cloud Cost Optimizer API", version="0.3.0")
logger = logging.getLogger("multicloud.gcp")

def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(status_code=503, detail="Server configuration missing: " + name)
    return value

async def get_supabase_user(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            env("SUPABASE_URL") + "/auth/v1/user",
            headers={"apikey": env("SUPABASE_PUBLISHABLE_KEY"), "Authorization": "Bearer " + token},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid application session")
    return r.json()

async def db(method: str, path: str, json: dict[str, Any] | None = None) -> Any:
    key = env("SUPABASE_SERVICE_ROLE_KEY")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.request(
            method,
            env("SUPABASE_URL") + "/rest/v1/" + path,
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "return=representation,resolution=merge-duplicates",
            },
            json=json,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Database operation failed")
    return r.json() if r.content else {}

class SyncResponse(BaseModel):
    provider: str
    projects: int
    resources: int
    warnings: list[str] = []

class ConnectResponse(BaseModel):
    provider: str
    status: str
    authorization_url: str

class BillingStatusResponse(BaseModel):
    provider: str
    status: str
    billing_accounts: int
    message: str

class CostSummaryResponse(BaseModel):
    days: int
    total_records: int
    totals_by_currency: dict[str, float]
    by_provider: list[dict[str, Any]]
    by_service: list[dict[str, Any]]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/collection/status")
def collection_status():
    return {"providers": {
        p: {"status": "oauth_ready" if p == "gcp" else "oauth_pending_configuration"}
        for p in ("aws", "azure", "gcp")
    }}

@app.post("/api/providers/gcp/connect", response_model=ConnectResponse)
async def begin_gcp(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")
    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    url = build_authorization_url(
        env("GOOGLE_CLIENT_ID"), env("OAUTH_STATE_SECRET"), user["id"], env("GOOGLE_REDIRECT_URI")
    )
    return ConnectResponse(provider="gcp", status="authorization_required", authorization_url=url)

@app.get("/api/providers/gcp/callback")
async def gcp_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if error or not code or not state:
        return RedirectResponse(frontend + "/dashboard?cloud_error=gcp_authorization_denied")
    try:
        user_id = verify_state(env("OAUTH_STATE_SECRET"), state)["user_id"]
    except Exception:
        logger.exception("GCP OAuth state validation failed")
        return RedirectResponse(frontend + "/dashboard?cloud_error=gcp_state_invalid")

    try:
        tokens = await exchange_code(
            env("GOOGLE_CLIENT_ID"), env("GOOGLE_CLIENT_SECRET"), code, env("GOOGLE_REDIRECT_URI")
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("GCP OAuth token exchange failed with HTTP %s", exc.response.status_code)
        return RedirectResponse(frontend + f"/dashboard?cloud_error=gcp_token_exchange_{exc.response.status_code}")
    except Exception:
        logger.exception("GCP OAuth token exchange failed")
        return RedirectResponse(frontend + "/dashboard?cloud_error=gcp_token_exchange_failed")

    billing_warning = None
    try:
        billing_result = await list_billing_accounts(tokens["access_token"])
        if billing_result["status"] == "available":
            accounts = billing_result["billing_accounts"]
        else:
            accounts = []
            billing_warning = billing_result.get(
                "message",
                "Google Cloud Billing access is currently unavailable.",
            )
    except Exception:
        logger.exception("GCP Cloud Billing API request failed")
        return RedirectResponse(frontend + "/dashboard?cloud_error=gcp_billing_api_failed")
    account = accounts[0] if accounts else {}
    data = {
        "display_name": account.get("displayName") or "Google Cloud",
        "status": "connected",
        "auth_method": "oauth",
        "account_identifier": account.get("name"),
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        "error_message": billing_warning,
    }

    existing = await db("GET", f"cloud_accounts?user_id=eq.{user_id}&provider=eq.gcp&select=id")
    if existing:
        account_id = existing[0]["id"]
        await db("PATCH", f"cloud_accounts?id=eq.{account_id}", data)
    else:
        created = await db("POST", "cloud_accounts", {
            "user_id": user_id, "provider": "gcp", **data
        })
        account_id = created[0]["id"]

    encrypted = encrypt_tokens(env("TOKEN_ENCRYPTION_KEY"), tokens)
    token_data = {
        "cloud_account_id": account_id,
        "user_id": user_id,
        "provider": "gcp",
        "access_token_ciphertext": encrypted["access_token_ciphertext"],
        "refresh_token_ciphertext": encrypted["refresh_token_ciphertext"],
        "token_expires_at": datetime.fromtimestamp(encrypted["token_expires_at"], tz=timezone.utc).isoformat() if encrypted["token_expires_at"] else None,
        "scopes": GCP_SCOPES,
    }
    existing_token = await db(
        "GET", f"provider_tokens?cloud_account_id=eq.{account_id}&select=id"
    )
    if existing_token:
        await db("PATCH", f"provider_tokens?id=eq.{existing_token[0]['id']}", token_data)
    else:
        await db("POST", "provider_tokens", token_data)

    return RedirectResponse(frontend + "/dashboard?cloud_connected=gcp")


@app.get("/api/providers/gcp/billing-status", response_model=BillingStatusResponse)
async def gcp_billing_status(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    rows = await db(
        "GET",
        f"cloud_accounts?user_id=eq.{user['id']}&provider=eq.gcp&select=id,status",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="GCP account is not connected")

    account_id = rows[0]["id"]
    token_rows = await db(
        "GET",
        f"provider_tokens?cloud_account_id=eq.{account_id}&user_id=eq.{user['id']}&provider=eq.gcp&select=id,access_token_ciphertext,refresh_token_ciphertext",
    )
    if not token_rows:
        raise HTTPException(status_code=404, detail="GCP credentials are not available")

    token_row = token_rows[0]
    encryption_key = env("TOKEN_ENCRYPTION_KEY")
    access_token = decrypt_secret(encryption_key, token_row["access_token_ciphertext"])
    refresh_cipher = token_row.get("refresh_token_ciphertext")

    result = await list_billing_accounts(access_token)

    if result["status"] == "unauthorized" and refresh_cipher:
        try:
            refresh_token = decrypt_secret(encryption_key, refresh_cipher)
            refreshed = await refresh_access_token(
                env("GOOGLE_CLIENT_ID"),
                env("GOOGLE_CLIENT_SECRET"),
                refresh_token,
            )
            access_token = refreshed["access_token"]
            encrypted = encrypt_tokens(
                encryption_key,
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": refreshed.get("expires_in", 3600),
                },
            )
            await db(
                "PATCH",
                f"provider_tokens?id=eq.{token_row['id']}",
                {
                    "access_token_ciphertext": encrypted["access_token_ciphertext"],
                    "token_expires_at": (
                        datetime.fromtimestamp(
                            encrypted["token_expires_at"],
                            tz=timezone.utc,
                        ).isoformat()
                        if encrypted["token_expires_at"]
                        else None
                    ),
                    "scopes": GCP_SCOPES,
                },
            )
            result = await list_billing_accounts(access_token)
        except Exception:
            logger.exception("GCP token refresh failed during billing status check")
            return BillingStatusResponse(
                provider="gcp",
                status="unauthorized",
                billing_accounts=0,
                message="Google Cloud authentication needs to be reconnected.",
            )

    return BillingStatusResponse(
        provider="gcp",
        status=result["status"],
        billing_accounts=len(result.get("billing_accounts", [])),
        message=result.get("message", "Google Cloud Billing status checked."),
    )

class AWSConnectStartResponse(BaseModel):
    provider: str
    status: str
    external_id: str
    trusted_principal_arn: str
    instructions: str


class AWSConnectCompleteRequest(BaseModel):
    role_arn: str
    region: str = "us-east-1"


@app.post("/api/providers/aws/connect/start", response_model=AWSConnectStartResponse)
async def start_aws_connection(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    external_id = __import__("secrets").token_urlsafe(32)

    sts = __import__("boto3").client("sts", region_name="us-east-1")
    try:
        identity = sts.get_caller_identity()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AWS backend credentials are not configured. Configure the AWS SDK credential chain for the backend first.",
        )

    principal = os.getenv("AWS_APP_PRINCIPAL_ARN") or identity.get("Arn", "")
    if ":assumed-role/" in principal:
        parts = principal.split(":assumed-role/", 1)
        role_name = parts[1].split("/", 1)[0]
        principal = f"{parts[0]}:role/{role_name}"

    rows = await db(
        "GET",
        f"cloud_accounts?user_id=eq.{user['id']}&provider=eq.aws&select=id",
    )
    data = {
        "display_name": "Amazon Web Services",
        "status": "pending",
        "auth_method": "iam_role",
        "account_identifier": None,
        "region": "us-east-1",
        "error_message": "Create the AWS IAM role using the supplied trust principal and external ID, then complete the connection.",
    }
    if rows:
        account_id = rows[0]["id"]
        await db("PATCH", f"cloud_accounts?id=eq.{account_id}", data)
    else:
        created = await db("POST", "cloud_accounts", {"user_id": user["id"], "provider": "aws", **data})
        account_id = created[0]["id"]

    await db(
        "POST",
        "provider_tokens",
        {
            "cloud_account_id": account_id,
            "user_id": user["id"],
            "provider": "aws",
            "access_token_ciphertext": None,
            "refresh_token_ciphertext": None,
            "role_arn_ciphertext": None,
            "external_id_ciphertext": encrypt_secret(env("TOKEN_ENCRYPTION_KEY"), external_id),
            "scopes": ["sts:AssumeRole", "ce:GetCostAndUsage"],
        },
    )

    return AWSConnectStartResponse(
        provider="aws",
        status="setup_required",
        external_id=external_id,
        trusted_principal_arn=principal,
        instructions="Create an IAM role in the AWS account you want to connect. Trust the supplied principal, require the supplied external ID, and grant read-only permissions for the resources and Cost Explorer data you want to collect.",
    )


@app.post("/api/providers/aws/connect/complete")
async def complete_aws_connection(
    payload: AWSConnectCompleteRequest,
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    rows = await db(
        "GET",
        f"cloud_accounts?user_id=eq.{user['id']}&provider=eq.aws&select=id",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="AWS connection setup has not been started")

    account_id = rows[0]["id"]
    token_rows = await db(
        "GET",
        f"provider_tokens?cloud_account_id=eq.{account_id}&user_id=eq.{user['id']}&provider=eq.aws&select=id,external_id_ciphertext",
    )
    if not token_rows or not token_rows[0].get("external_id_ciphertext"):
        raise HTTPException(status_code=404, detail="AWS connection setup token is missing")

    external_id = decrypt_secret(env("TOKEN_ENCRYPTION_KEY"), token_rows[0]["external_id_ciphertext"])
    provider = AWSProvider()
    try:
        temporary = provider.assume_role(
            payload.role_arn,
            external_id,
            f"smco-{user['id'][:8]}",
        )
        session = __import__("boto3").Session(
            aws_access_key_id=temporary["access_key_id"],
            aws_secret_access_key=temporary["secret_access_key"],
            aws_session_token=temporary["session_token"],
            region_name=payload.region,
        )
        identity = session.client("sts").get_caller_identity()
    except Exception as exc:
        logger.exception("AWS role assumption failed")
        raise HTTPException(status_code=400, detail=f"AWS role assumption failed: {exc}")

    await db(
        "PATCH",
        f"provider_tokens?id=eq.{token_rows[0]['id']}",
        {
            "role_arn_ciphertext": encrypt_secret(env("TOKEN_ENCRYPTION_KEY"), payload.role_arn),
            "scopes": ["sts:AssumeRole", "ce:GetCostAndUsage"],
        },
    )
    await db(
        "PATCH",
        f"cloud_accounts?id=eq.{account_id}",
        {
            "status": "connected",
            "auth_method": "iam_role",
            "account_identifier": identity.get("Account"),
            "region": payload.region,
            "error_message": None,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "provider": "aws",
        "status": "connected",
        "account_identifier": identity.get("Account"),
        "role_arn": payload.role_arn,
    }


@app.post("/api/providers/aws/sync")
async def sync_aws(
    authorization: str | None = Header(default=None),
    days: int = 30,
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    rows = await db("GET", f"cloud_accounts?user_id=eq.{user['id']}&provider=eq.aws&select=id,region")
    if not rows:
        raise HTTPException(status_code=404, detail="AWS account is not connected")
    account_id = rows[0]["id"]
    token_rows = await db("GET", f"provider_tokens?cloud_account_id=eq.{account_id}&user_id=eq.{user['id']}&provider=eq.aws&select=id,role_arn_ciphertext,external_id_ciphertext")
    if not token_rows or not token_rows[0].get("role_arn_ciphertext"):
        raise HTTPException(status_code=404, detail="AWS role credentials are not configured")

    token = token_rows[0]
    encryption_key = env("TOKEN_ENCRYPTION_KEY")
    role_arn = decrypt_secret(encryption_key, token["role_arn_ciphertext"])
    external_id = decrypt_secret(encryption_key, token["external_id_ciphertext"])
    provider = AWSProvider()

    try:
        temporary = provider.assume_role(role_arn, external_id, f"smco-sync-{user['id'][:8]}")
        temporary["region"] = rows[0].get("region") or "us-east-1"
        temporary["days"] = days
        costs = provider.collect_costs(temporary)
        resources = provider.collect_resources(temporary)
    except Exception as exc:
        logger.exception("AWS synchronization failed")
        await db("PATCH", f"cloud_accounts?id=eq.{account_id}", {"status": "error", "error_message": str(exc)})
        raise HTTPException(status_code=502, detail=f"AWS synchronization failed: {exc}")

    for resource in resources:
        resource_id = resource.get("resource_id")
        if not resource_id:
            continue
        await db("POST", "cloud_resources?on_conflict=cloud_account_id,resource_id", {
            "user_id": user["id"],
            "cloud_account_id": account_id,
            "provider": "aws",
            **resource,
        })

    for cost in costs:
        await db("POST", "cost_records", {
            "user_id": user["id"],
            "cloud_account_id": account_id,
            **cost,
        })

    await db("PATCH", f"cloud_accounts?id=eq.{account_id}", {
        "status": "connected",
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    })

    return {
        "provider": "aws",
        "status": "synced",
        "resources": len(resources),
        "cost_records": len(costs),
        "days": days,
    }


@app.get("/api/costs/summary", response_model=CostSummaryResponse)
async def cost_summary(
    authorization: str | None = Header(default=None),
    days: int = 30,
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    rows = await db(
        "GET",
        f"cost_records?user_id=eq.{user['id']}&period_end=gte.{cutoff}"
        "&select=provider,amount,currency,service_name,period_start,period_end"
        "&order=period_end.desc",
    )

    totals_by_currency: dict[str, float] = {}
    provider_totals: dict[tuple[str, str], dict[str, Any]] = {}
    service_totals: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        provider = row.get("provider") or "unknown"
        currency = row.get("currency") or "USD"
        service = row.get("service_name") or "Unknown service"
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            continue

        totals_by_currency[currency] = totals_by_currency.get(currency, 0.0) + amount

        provider_key = (provider, currency)
        provider_item = provider_totals.setdefault(
            provider_key,
            {"provider": provider, "currency": currency, "amount": 0.0, "records": 0},
        )
        provider_item["amount"] += amount
        provider_item["records"] += 1

        service_key = (service, currency)
        service_item = service_totals.setdefault(
            service_key,
            {"service_name": service, "currency": currency, "amount": 0.0, "records": 0},
        )
        service_item["amount"] += amount
        service_item["records"] += 1

    return CostSummaryResponse(
        days=days,
        total_records=len(rows),
        totals_by_currency={k: round(v, 2) for k, v in totals_by_currency.items()},
        by_provider=sorted(
            [
                {**item, "amount": round(item["amount"], 2)}
                for item in provider_totals.values()
            ],
            key=lambda item: item["amount"],
            reverse=True,
        ),
        by_service=sorted(
            [
                {**item, "amount": round(item["amount"], 2)}
                for item in service_totals.values()
            ],
            key=lambda item: item["amount"],
            reverse=True,
        ),
    )



@app.get("/api/providers/gcp/recommendations")
async def gcp_recommendations(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")

    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    accounts = await db(
        "GET",
        f"cloud_accounts?user_id=eq.{user['id']}&provider=eq.gcp&select=id",
    )
    if not accounts:
        raise HTTPException(status_code=404, detail="GCP account is not connected")

    account_id = accounts[0]["id"]
    resources = await db(
        "GET",
        f"cloud_resources?user_id=eq.{user['id']}&cloud_account_id=eq.{account_id}&provider=eq.gcp&select=id,resource_id,resource_type,resource_name,region,status,metadata&order=resource_type,resource_name",
    )

    metrics = await db(
        "GET",
        f"usage_metrics?user_id=eq.{user['id']}&select=cloud_resource_id,metric_name,metric_value,unit,recorded_at&order=recorded_at.desc",
    )

    latest_cpu: dict[str, float] = {}
    for metric in metrics:
        if metric.get("metric_name") != "cpu_utilization":
            continue
        resource_id = metric.get("cloud_resource_id")
        if resource_id and resource_id not in latest_cpu:
            latest_cpu[resource_id] = float(metric.get("metric_value") or 0)

    recommendations = []
    for resource in resources:
        resource_type = resource.get("resource_type", "")
        status = (resource.get("status") or "").upper()
        cpu = latest_cpu.get(resource["id"])

        if resource_type == "compute_instance" and status == "TERMINATED":
            recommendations.append({
                "resource_id": resource["resource_id"],
                "resource_name": resource.get("resource_name"),
                "resource_type": resource_type,
                "severity": "medium",
                "rule": "STOPPED_COMPUTE_INSTANCE",
                "title": "Stopped VM should be reviewed",
                "reason": "The VM is stopped and may still have attached disks or other billable resources.",
                "metric_value": None,
                "unit": None,
            })
        elif resource_type == "compute_instance" and cpu is not None and cpu < 0.05:
            recommendations.append({
                "resource_id": resource["resource_id"],
                "resource_name": resource.get("resource_name"),
                "resource_type": resource_type,
                "severity": "high",
                "rule": "POTENTIAL_IDLE_VM",
                "title": "Potential idle VM",
                "reason": "Average CPU utilization observed over the latest monitoring window is below 5%. Review before keeping the VM running.",
                "metric_value": round(cpu, 4),
                "unit": "ratio",
            })
        elif resource_type == "compute_instance" and cpu is not None and cpu < 0.20:
            recommendations.append({
                "resource_id": resource["resource_id"],
                "resource_name": resource.get("resource_name"),
                "resource_type": resource_type,
                "severity": "low",
                "rule": "UNDERUTILIZED_VM",
                "title": "Potentially underutilized VM",
                "reason": "Average CPU utilization is below 20%. Consider reviewing the machine size and workload requirements.",
                "metric_value": round(cpu, 4),
                "unit": "ratio",
            })

    return {
        "provider": "gcp",
        "resource_count": len(resources),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "rules": [
            "Stopped Compute Engine VMs are flagged for review.",
            "Compute Engine VMs with average CPU below 5% are flagged as potentially idle.",
            "Compute Engine VMs with average CPU below 20% are flagged as potentially underutilized.",
        ],
    }


@app.post("/api/providers/gcp/sync", response_model=SyncResponse)
async def sync_gcp(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing application session")
    user = await get_supabase_user(authorization.removeprefix("Bearer ").strip())
    rows = await db("GET", f"cloud_accounts?user_id=eq.{user["id"]}&provider=eq.gcp&select=id,status")
    if not rows:
        raise HTTPException(status_code=404, detail="GCP account is not connected")
    account_id = rows[0]["id"]
    token_rows = await db("GET", f"provider_tokens?cloud_account_id=eq.{account_id}&user_id=eq.{user["id"]}&provider=eq.gcp&select=id,access_token_ciphertext,refresh_token_ciphertext")
    if not token_rows:
        raise HTTPException(status_code=404, detail="GCP credentials are not available")
    token_row = token_rows[0]
    access_token = decrypt_secret(env("TOKEN_ENCRYPTION_KEY"), token_row["access_token_ciphertext"])
    refresh_cipher = token_row.get("refresh_token_ciphertext")
    try:
        projects = await list_projects(access_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 401 or not refresh_cipher:
            raise HTTPException(status_code=502, detail=f"GCP project discovery failed with HTTP {exc.response.status_code}")
        refresh_token = decrypt_secret(env("TOKEN_ENCRYPTION_KEY"), refresh_cipher)
        try:
            refreshed = await refresh_access_token(env("GOOGLE_CLIENT_ID"), env("GOOGLE_CLIENT_SECRET"), refresh_token)
            access_token = refreshed["access_token"]
            encrypted = encrypt_tokens(env("TOKEN_ENCRYPTION_KEY"), {"access_token": access_token, "refresh_token": refresh_token, "expires_in": refreshed.get("expires_in", 3600)})
            await db("PATCH", f"provider_tokens?id=eq.{token_row["id"]}", {"access_token_ciphertext": encrypted["access_token_ciphertext"], "token_expires_at": datetime.fromtimestamp(encrypted["token_expires_at"], tz=timezone.utc).isoformat(), "scopes": GCP_SCOPES})
            projects = await list_projects(access_token)
        except Exception:
            logger.exception("GCP token refresh failed during sync")
            raise HTTPException(status_code=502, detail="GCP authentication refresh failed")
    warnings = []
    resource_count = 0
    inventory_resource_count = 0
    monitoring_metric_count = 0

    for project in projects:
        project_id = project.get("projectId")
        if not project_id:
            continue
        await db("POST", "cloud_resources?on_conflict=cloud_account_id,resource_id", {
            "user_id": user["id"], "cloud_account_id": account_id, "provider": "gcp",
            "resource_id": f"gcp:project:{project_id}", "resource_type": "project",
            "resource_name": project.get("displayName") or project_id, "status": project.get("state"),
            "metadata": {"project_id": project_id, "project_name": project.get("name"), "lifecycle_state": project.get("state")},
        })
        resource_count += 1
        try:
            instances = await list_compute_instances(access_token, project_id)
            for instance in instances:
                name = instance.get("name") or str(instance.get("id", ""))
                if not name:
                    continue
                zone = instance.get("zone", "").split("/")[-1]
                resource_id = f"gcp:compute:instance:{project_id}:{zone}:{name}"
                await db("POST", "cloud_resources?on_conflict=cloud_account_id,resource_id", {
                    "user_id": user["id"], "cloud_account_id": account_id, "provider": "gcp",
                    "resource_id": resource_id, "resource_type": "compute_instance", "resource_name": name,
                    "region": zone.rsplit("-", 1)[0] if "-" in zone else zone, "status": instance.get("status"),
                    "metadata": {"project_id": project_id, "zone": zone, "machine_type": instance.get("machineType", "").split("/")[-1], "instance_id": str(instance.get("id", "")), "labels": instance.get("labels", {})},
                })
                resource_count += 1
        except httpx.HTTPStatusError as exc:
            warnings.append(f"{project_id}: Compute API returned HTTP {exc.response.status_code}")
        except Exception:
            warnings.append(f"{project_id}: Compute discovery failed")

        try:
            assets = await search_all_resources(access_token, project_id)
            for asset in assets:
                normalized = normalize_asset(asset, project_id)
                if not normalized:
                    continue
                await db("POST", "cloud_resources?on_conflict=cloud_account_id,resource_id", {
                    "user_id": user["id"],
                    "cloud_account_id": account_id,
                    "provider": "gcp",
                    **normalized,
                })
                inventory_resource_count += 1
        except httpx.HTTPStatusError as exc:
            warnings.append(f"{project_id}: Cloud Asset Inventory returned HTTP {exc.response.status_code}")
        except Exception:
            warnings.append(f"{project_id}: Cloud Asset Inventory discovery failed")

        try:
            metric_series = await list_compute_cpu_utilization(access_token, project_id, days=7)
            resource_rows = await db(
                "GET",
                f"cloud_resources?cloud_account_id=eq.{account_id}&provider=eq.gcp&resource_type=eq.compute_instance&select=id,resource_name,metadata",
            )
            by_instance_id = {}
            by_name = {}
            for row in resource_rows:
                metadata = row.get("metadata") or {}
                if metadata.get("instance_id"):
                    by_instance_id[str(metadata["instance_id"])] = row
                if row.get("resource_name"):
                    by_name[row["resource_name"]] = row

            for metric in metric_series.values():
                resource = by_instance_id.get(str(metric.get("instance_id"))) or by_name.get(metric.get("instance_name"))
                if not resource:
                    continue
                await db("POST", "usage_metrics", {
                    "user_id": user["id"],
                    "cloud_resource_id": resource["id"],
                    "metric_name": metric["metric_name"],
                    "metric_value": metric["metric_value"],
                    "unit": metric["unit"],
                    "recorded_at": metric["recorded_at"],
                })
                monitoring_metric_count += 1
        except httpx.HTTPStatusError as exc:
            warnings.append(f"{project_id}: Cloud Monitoring returned HTTP {exc.response.status_code}")
        except Exception:
            warnings.append(f"{project_id}: Cloud Monitoring collection failed")
    await db("PATCH", f"cloud_accounts?id=eq.{account_id}", {"status": "connected", "last_synced_at": datetime.now(timezone.utc).isoformat(), "error_message": "; ".join(warnings) if warnings else None})
    return SyncResponse(
        provider="gcp",
        projects=len(projects),
        resources=resource_count + inventory_resource_count,
        warnings=warnings,
    )
