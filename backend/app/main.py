import os
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .gcp_oauth import GCP_SCOPES, build_authorization_url, exchange_code, encrypt_tokens, list_billing_accounts
from .security import verify_state

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
                "Prefer": "return=representation",
            },
            json=json,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Database operation failed")
    return r.json() if r.content else {}

class ConnectResponse(BaseModel):
    provider: str
    status: str
    authorization_url: str

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

    try:
        accounts = await list_billing_accounts(tokens["access_token"])
    except httpx.HTTPStatusError as exc:
        logger.exception("GCP Cloud Billing API failed with HTTP %s", exc.response.status_code)
        return RedirectResponse(frontend + f"/dashboard?cloud_error=gcp_billing_api_{exc.response.status_code}")
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
        "error_message": None,
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
