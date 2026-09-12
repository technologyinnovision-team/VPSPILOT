"""
Authentication and Session Security for VPSPilot
"""

import time
import secrets
from typing import Optional
from aiohttp import web
from vpspilot.config import load_config, verify_password

# In-memory session store: token -> {"username": str, "expires": float, "ip": str}
SESSIONS: dict[str, dict] = {}
# Rate limiting tracking: ip -> [timestamps]
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
MAX_ATTEMPTS = 10
ATTEMPT_WINDOW = 60 # 60 seconds

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = LOGIN_ATTEMPTS.get(ip, [])
    # Filter attempts within window
    valid_attempts = [t for t in attempts if now - t < ATTEMPT_WINDOW]
    LOGIN_ATTEMPTS[ip] = valid_attempts
    return len(valid_attempts) >= MAX_ATTEMPTS

def record_attempt(ip: str):
    now = time.time()
    if ip not in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[ip] = []
    LOGIN_ATTEMPTS[ip].append(now)

def create_session(username: str, ip: str, ttl: int = 86400) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "username": username,
        "expires": time.time() + ttl,
        "ip": ip,
        "created_at": time.time()
    }
    return token

def validate_session(token: Optional[str]) -> bool:
    if not token or token not in SESSIONS:
        return False
    session = SESSIONS[token]
    if time.time() > session["expires"]:
        del SESSIONS[token]
        return False
    return True

def destroy_session(token: str):
    if token in SESSIONS:
        del SESSIONS[token]

def cleanup_expired_sessions():
    now = time.time()
    expired = [t for t, s in SESSIONS.items() if now > s["expires"]]
    for t in expired:
        del SESSIONS[t]

def authenticate_user(username: str, password: str, client_ip: str) -> Optional[str]:
    """Validates username/password. Returns token if successful, None otherwise."""
    if is_rate_limited(client_ip):
        return None

    cfg = load_config()
    configured_user = cfg.get("admin_username", "admin")
    stored_hash = cfg.get("password_hash")
    stored_salt = cfg.get("password_salt")

    if not stored_hash or not stored_salt:
        return None

    if username != configured_user:
        record_attempt(client_ip)
        return None

    if not verify_password(password, stored_hash, stored_salt):
        record_attempt(client_ip)
        return None

    # Success, create session
    token = create_session(username, client_ip, cfg.get("session_timeout", 86400))
    return token

def get_token_from_request(request: web.Request) -> Optional[str]:
    # 1. Cookie
    token = request.cookies.get("vpspilot_session")
    if token:
        return token
    # 2. Authorization header: Bearer <token>
    auth_hdr = request.headers.get("Authorization")
    if auth_hdr and auth_hdr.startswith("Bearer "):
        return auth_hdr[7:].strip()
    # 3. Query param (useful for WebSocket handshake: ?token=...)
    return request.query.get("token")

@web.middleware
async def auth_middleware(request: web.Request, handler):
    # Exclude public routes
    path = request.path
    if (
        path in ("/api/auth/login", "/api/auth/status")
        or path.startswith("/static/")
        or path == "/favicon.ico"
        or (path == "/" and not request.cookies.get("vpspilot_session"))
    ):
        return await handler(request)

    token = get_token_from_request(request)
    if not validate_session(token):
        if path.startswith("/api/") or path.startswith("/ws/"):
            return web.json_response({"error": "Unauthorized", "authenticated": False}, status=401)
        # If user browses HTML page without session, redirect or render login
        # We handle SPA client-side login check
        return await handler(request)

    request["user"] = SESSIONS[token]["username"]
    return await handler(request)
