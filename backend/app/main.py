from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Multi-Cloud Cost Optimizer API", version="0.2.0")

SUPPORTED_PROVIDERS = {"aws", "gcp", "azure"}

class ConnectResponse(BaseModel):
    provider: str
    status: str
    message: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/collection/status")
def collection_status():
    return {
        "providers": {
            provider: {
                "status": "oauth_pending_configuration",
                "message": "Provider OAuth credentials must be configured server-side."
            }
            for provider in sorted(SUPPORTED_PROVIDERS)
        }
    }

@app.get("/api/providers")
def providers():
    return {
        "providers": [
            {"id": "aws", "name": "AWS", "authorization": "oauth"},
            {"id": "gcp", "name": "Google Cloud", "authorization": "oauth"},
            {"id": "azure", "name": "Microsoft Azure", "authorization": "oauth"},
        ]
    }

@app.post("/api/providers/{provider}/connect", response_model=ConnectResponse)
def begin_provider_connection(provider: str):
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    return ConnectResponse(
        provider=provider,
        status="oauth_pending_configuration",
        message=f"{provider.upper()} OAuth is the connection path; configure the provider OAuth application server-side before enabling the redirect."
    )
