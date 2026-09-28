import secrets,time
from urllib.parse import urlencode
import httpx
from .security import encrypt_secret,sign_state

GCP_AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth"
GCP_TOKEN_URL="https://oauth2.googleapis.com/token"
GCP_BILLING_URL="https://cloudbilling.googleapis.com/v1/billingAccounts"
GCP_SCOPES=["https://www.googleapis.com/auth/cloud-billing.readonly","https://www.googleapis.com/auth/cloud-platform.read-only"]

def build_authorization_url(client_id,state_secret,user_id,redirect_uri):
    state=sign_state(state_secret,{"user_id":user_id,"iat":time.time(),"nonce":secrets.token_urlsafe(24)})
    params={"client_id":client_id,"redirect_uri":redirect_uri,"response_type":"code","scope":" ".join(GCP_SCOPES),"access_type":"offline","prompt":"consent","state":state}
    return GCP_AUTH_URL+"?"+urlencode(params)

async def exchange_code(client_id,client_secret,code,redirect_uri):
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post(GCP_TOKEN_URL,data={"code":code,"client_id":client_id,"client_secret":client_secret,"redirect_uri":redirect_uri,"grant_type":"authorization_code"})
        r.raise_for_status()
        return r.json()

async def list_billing_accounts(access_token):
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.get(GCP_BILLING_URL,headers={"Authorization":"Bearer "+access_token})
        r.raise_for_status()
        return r.json().get("billingAccounts",[])

def encrypt_tokens(key,token_response):
    return {"access_token_ciphertext":encrypt_secret(key,token_response["access_token"]),
            "refresh_token_ciphertext":encrypt_secret(key,token_response["refresh_token"]) if token_response.get("refresh_token") else None,
            "token_expires_at": time.time() + int(token_response["expires_in"]) if token_response.get("expires_in") else None}


GCP_PROJECTS_URL="https://cloudresourcemanager.googleapis.com/v3/projects"
GCP_COMPUTE_AGGREGATED_URL="https://compute.googleapis.com/compute/v1/projects/{project_id}/aggregated/instances"

async def refresh_access_token(client_id, client_secret, refresh_token):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            GCP_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        return r.json()

async def list_projects(access_token):
    projects = []
    page_token = None
    headers = {"Authorization": "Bearer " + access_token}
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            params = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            r = await client.get(GCP_PROJECTS_URL, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            projects.extend(data.get("projects", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                return projects

async def list_compute_instances(access_token, project_id):
    url = GCP_COMPUTE_AGGREGATED_URL.format(project_id=project_id)
    instances = []
    page_token = None
    headers = {"Authorization": "Bearer " + access_token}
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            params = {"maxResults": 500}
            if page_token:
                params["pageToken"] = page_token
            r = await client.get(url, headers=headers, params=params)
            if r.status_code in (403, 404):
                return []
            r.raise_for_status()
            data = r.json()
            for zone_key, scoped in data.get("items", {}).items():
                for instance in scoped.get("instances", []):
                    instance["_scope"] = zone_key
                    instances.append(instance)
            page_token = data.get("nextPageToken")
            if not page_token:
                return instances
