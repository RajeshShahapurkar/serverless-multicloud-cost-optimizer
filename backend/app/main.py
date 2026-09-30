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

from .gcp_oauth import GCP_SCOPES, build_authorization_url, exchange_code, encrypt_tokens, list_billing_accounts, refresh_access_token, list_projects, list_compute_instances
from .security import verify_state, decrypt_secret

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
        "&select=provider,amount,currency,service_name&period_start&period_end"
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
    await db("PATCH", f"cloud_accounts?id=eq.{account_id}", {"status": "connected", "last_synced_at": datetime.now(timezone.utc).isoformat(), "error_message": "; ".join(warnings) if warnings else None})
    return SyncResponse(provider="gcp", projects=len(projects), resources=resource_count, warnings=warnings)
