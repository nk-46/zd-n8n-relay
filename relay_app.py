import os
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
# Shared secrets, set via environment
RELAY_TOKEN = os.getenv("RELAY_TOKEN")
API_KEY = os.getenv("API_KEY")  # Add this to your .env file

# Your internal n8n webhook URL, e.g. http://10.0.0.5:5678/webhook/zendesk
N8N_ENDPOINT = os.getenv("N8N_ENDPOINT")

# API Key security scheme
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return api_key_header

@app.post("/zendesk-webhook")
async def relay(
    request: Request, 
    x_relay_token: str = Header(None),
    api_key: str = Depends(get_api_key)  # This adds API key requirement
):
    # 1. Validate secret header
    if x_relay_token != RELAY_TOKEN:
        raise HTTPException(
            status_code=403, 
            detail=f"Invalid relay token. Expected: {repr(RELAY_TOKEN)}, Got: {repr(x_relay_token)}"
        )

    # 2. Read incoming JSON
    payload = await request.json()

    # 3. Optionally, log or inspect payload here
    print("Relaying Zendesk payload:", payload)

    # 4. Forward to internal n8n
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            N8N_ENDPOINT,
            json=payload,
            timeout=10.0,
        )
    if resp.status_code >= 400:
        return JSONResponse(
            status_code=502,
            content={"error": "n8n relay failed", "details": resp.text},
        )

    return {"status": "ok"}
