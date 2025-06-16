import os
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from starlette.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
# Shared secret, set via environment
RELAY_TOKEN = os.getenv("RELAY_TOKEN")
# Debug print (remove this after testing)
print("Loaded RELAY_TOKEN:", RELAY_TOKEN)

# Your internal n8n webhook URL, e.g. http://10.0.0.5:5678/webhook/zendesk
N8N_ENDPOINT = os.getenv("N8N_ENDPOINT")

@app.post("/zendesk-webhook")
async def relay(request: Request, x_relay_token: str = Header(None)):

    
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