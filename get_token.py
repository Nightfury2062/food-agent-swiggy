import base64
import hashlib
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import set_key

BASE = "https://mcp.swiggy.com"
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}/callback"

# 1. Register this script as a client (Dynamic Client Registration)
reg = requests.post(
    f"{BASE}/auth/register",
    json={
        "client_name": "food-agent-dev",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    },
    timeout=30,
)
if not reg.ok:
    raise SystemExit(f"Registration failed: {reg.status_code} {reg.text}")
client_id = reg.json()["client_id"]

# 2. PKCE: a secret verifier and its hash (the challenge)
verifier = secrets.token_urlsafe(48)
challenge = (
    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    .rstrip(b"=")
    .decode()
)
state = secrets.token_urlsafe(16)

auth_url = f"{BASE}/auth/authorize?" + urlencode(
    {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "mcp:tools",
    }
)

# 3. Tiny local server that catches the redirect from Swiggy
result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            result["code"] = params["code"][0]
            result["state"] = params.get("state", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h3>Done! You can close this tab and go back to the terminal.</h3>")

    def log_message(self, *args):
        pass


server = HTTPServer(("localhost", PORT), Handler)
print("Opening browser. Log in with your Swiggy phone number + OTP...")
webbrowser.open(auth_url)

while "code" not in result:
    server.handle_request()

if result["state"] != state:
    raise SystemExit("State mismatch, aborting for safety.")

# 4. Swap the code for an access token
tok = requests.post(
    f"{BASE}/auth/token",
    json={
        "grant_type": "authorization_code",
        "code": result["code"],
        "code_verifier": verifier,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
    },
    timeout=30,
)
if not tok.ok:
    raise SystemExit(f"Token exchange failed: {tok.status_code} {tok.text}")

data = tok.json()
set_key(".env", "SWIGGY_ACCESS_TOKEN", data["access_token"])
print(f"Saved token to .env (valid for about {data.get('expires_in', 0) // 86400} days).")