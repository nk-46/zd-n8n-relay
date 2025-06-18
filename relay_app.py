import os
from dotenv import load_dotenv
import httpx
import traceback
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.responses import JSONResponse
import socket
import dns.resolver
import secrets

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
# Shared secret, set via environment
RELAY_TOKEN = os.getenv("RELAY_TOKEN")
# Basic auth credentials
WEBHOOK_USERNAME = os.getenv("WEBHOOK_USERNAME", "admin")
WEBHOOK_PASSWORD = os.getenv("WEBHOOK_PASSWORD", "changeme")

# Debug print (remove this after testing)
"""print("Loaded RELAY_TOKEN:", RELAY_TOKEN)
print("Loaded WEBHOOK_USERNAME:", WEBHOOK_USERNAME)"""

# Your internal n8n webhook URL, e.g. http://10.0.0.5:5678/webhook/zendesk
N8N_ENDPOINT = os.getenv("N8N_ENDPOINT")

# Basic auth dependency
security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic authentication credentials"""
    is_username_correct = secrets.compare_digest(credentials.username, WEBHOOK_USERNAME)
    is_password_correct = secrets.compare_digest(credentials.password, WEBHOOK_PASSWORD)
    
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

@app.get("/test-connection")
async def test_connection():
    """Test endpoint to diagnose n8n connectivity issues"""
    results = {
        "n8n_endpoint": N8N_ENDPOINT,
        "tests": {}
    }
    
    # Test 1: DNS Resolution
    try:
        domain = N8N_ENDPOINT.split("://")[1].split("/")[0]
        answers = dns.resolver.resolve(domain, 'A')
        results["tests"]["dns"] = {
            "success": True,
            "ips": [str(rdata) for rdata in answers]
        }
    except Exception as e:
        results["tests"]["dns"] = {
            "success": False,
            "error": str(e)
        }

    # Test 2: TCP Connection
    try:
        domain = N8N_ENDPOINT.split("://")[1].split("/")[0]
        port = 443 if N8N_ENDPOINT.startswith("https") else 80
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((domain, port))
        sock.close()
        results["tests"]["tcp"] = {
            "success": result == 0,
            "error": f"Connection failed with code {result}" if result != 0 else None
        }
    except Exception as e:
        results["tests"]["tcp"] = {
            "success": False,
            "error": str(e)
        }

    # Test 3: HTTP Request
    try:
        async with httpx.AsyncClient(verify=True, timeout=5.0) as client:
            resp = await client.get(N8N_ENDPOINT)
            results["tests"]["http"] = {
                "success": True,
                "status_code": resp.status_code,
                "headers": dict(resp.headers)
            }
    except Exception as e:
        results["tests"]["http"] = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

    return results

@app.post("/zendesk-webhook")
async def relay(request: Request, x_relay_token: str = Header(None), credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    # 1. Validate secret header
    if x_relay_token != RELAY_TOKEN:
        raise HTTPException(
            status_code=403, 
            detail=f"Invalid relay token. Expected: {repr(RELAY_TOKEN)}, Got: {repr(x_relay_token)}"
        )

    # 2. Read incoming JSON
    payload = await request.json()

    # 3. Log payload
    print("Relaying Zendesk payload:", payload)
    print("N8N_ENDPOINT:", N8N_ENDPOINT)

    # 4. Forward to internal n8n
    try:
        async with httpx.AsyncClient(verify=True, timeout=30.0) as client:
            print(f"Attempting to forward to n8n at: {N8N_ENDPOINT}")
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "n8n-relay/1.0"
                }
                
                resp = await client.post(
                    N8N_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                print(f"n8n response status: {resp.status_code}")
                print(f"n8n response body: {resp.text}")
                
                if resp.status_code >= 400:
                    return JSONResponse(
                        status_code=502,
                        content={
                            "error": "n8n relay failed",
                            "details": resp.text,
                            "status_code": resp.status_code
                        },
                    )
            except httpx.ConnectTimeout as e:
                print(f"Connection timeout: {str(e)}")
                print(f"Connection timeout details: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=504,
                    content={
                        "error": "Connection timeout to n8n",
                        "details": str(e),
                        "type": "timeout_error"
                    },
                )
            except httpx.ConnectError as e:
                print(f"Connection error: {str(e)}")
                print(f"Connection error details: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=502,
                    content={
                        "error": "Failed to connect to n8n",
                        "details": str(e),
                        "type": "connection_error"
                    },
                )
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                print(f"Full traceback: {traceback.format_exc()}")
                return JSONResponse(
                    status_code=502,
                    content={
                        "error": "Unexpected error when forwarding to n8n",
                        "details": str(e),
                        "type": type(e).__name__
                    },
                )
    except Exception as e:
        print(f"Client error: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=502,
            content={
                "error": "Failed to create HTTP client",
                "details": str(e),
                "type": type(e).__name__
            },
        )

    return {"status": "ok"}

@app.get("/debug-ip")
async def debug_ip(request: Request):
    """Debug endpoint to show client IP address"""
    client_ip = request.client.host
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")
    
    return {
        "client_ip": client_ip,
        "x_forwarded_for": forwarded_for,
        "x_real_ip": real_ip,
        "all_headers": dict(request.headers)
    }