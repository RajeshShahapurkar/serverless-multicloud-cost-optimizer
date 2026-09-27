from fastapi import FastAPI

app = FastAPI(title="Multi-Cloud Cost Optimizer API", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/collection/status")
def collection_status():
    return {"providers": {
        "aws": "adapter_pending_credentials",
        "gcp": "adapter_pending_credentials",
        "azure": "adapter_pending_credentials"
    }}
