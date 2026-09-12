"""
Async aiohttp Server and API router for VPSPilot
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from aiohttp import web, WSMsgType

from vpspilot.config import load_config, update_password, verify_password
from vpspilot.system.auth import (
    authenticate_user,
    validate_session,
    destroy_session,
    get_token_from_request,
    auth_middleware,
    SESSIONS
)
from vpspilot.system.metrics import get_telemetry_snapshot
from vpspilot.system.services import (
    list_services,
    control_service,
    get_service_logs,
    get_service_details
)
from vpspilot.system.terminal import handle_terminal_ws
from vpspilot.system.processes import list_processes, signal_process
from vpspilot.system.vps_config import (
    get_vps_configuration,
    set_hostname,
    set_timezone,
    add_ufw_rule,
    delete_ufw_rule,
    toggle_ufw,
    system_power_action
)

logger = logging.getLogger("vpspilot.server")
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# --- Authentication Handlers ---

async def handle_login(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON format"}, status=400)

    username = data.get("username", "").strip()
    password = data.get("password", "")
    client_ip = request.remote or "127.0.0.1"

    token = authenticate_user(username, password, client_ip)
    if not token:
        return web.json_response({"success": False, "error": "Invalid username or password"}, status=401)

    response = web.json_response({"success": True, "token": token, "username": username})
    response.set_cookie(
        "vpspilot_session",
        token,
        max_age=86400,
        httponly=True,
        samesite="Lax",
        path="/"
    )
    return response

async def handle_logout(request: web.Request) -> web.Response:
    token = get_token_from_request(request)
    if token:
        destroy_session(token)
    response = web.json_response({"success": True, "message": "Logged out successfully"})
    response.del_cookie("vpspilot_session", path="/")
    return response

async def handle_auth_status(request: web.Request) -> web.Response:
    token = get_token_from_request(request)
    is_valid = validate_session(token)
    username = SESSIONS[token]["username"] if is_valid else None
    return web.json_response({
        "authenticated": is_valid,
        "username": username
    })

async def handle_change_password(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    curr_pwd = data.get("current_password", "")
    new_pwd = data.get("new_password", "")

    if len(new_pwd) < 6:
        return web.json_response({"success": False, "error": "New password must be at least 6 characters"}, status=400)

    cfg = load_config()
    stored_hash = cfg.get("password_hash")
    stored_salt = cfg.get("password_salt")

    if not verify_password(curr_pwd, stored_hash, stored_salt):
        return web.json_response({"success": False, "error": "Current password is incorrect"}, status=403)

    update_password(new_pwd)
    return web.json_response({"success": True, "message": "Password updated successfully"})

# --- Telemetry & Metrics Handlers ---

async def handle_get_metrics(request: web.Request) -> web.Response:
    snapshot = get_telemetry_snapshot()
    return web.json_response(snapshot)

async def handle_metrics_ws(request: web.Request) -> web.WebSocketResponse:
    token = get_token_from_request(request)
    if not validate_session(token):
        return web.json_response({"error": "Unauthorized"}, status=401)

    ws = web.WebSocketResponse(heartbeat=15.0)
    await ws.prepare(request)

    try:
        while not ws.closed:
            snapshot = get_telemetry_snapshot()
            await ws.send_str(json.dumps(snapshot))
            await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Metrics WebSocket disconnected: {e}")
    finally:
        if not ws.closed:
            await ws.close()

    return ws

# --- Services Handlers ---

async def handle_list_services(request: web.Request) -> web.Response:
    services = list_services()
    return web.json_response({"success": True, "count": len(services), "services": services})

async def handle_control_service(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    service_name = data.get("service", "")
    action = data.get("action", "")
    result = control_service(service_name, action)
    status_code = 200 if result.get("success") else 400
    return web.json_response(result, status=status_code)

async def handle_service_logs(request: web.Request) -> web.Response:
    service_name = request.query.get("service", "")
    lines = int(request.query.get("lines", 100))
    result = get_service_logs(service_name, lines)
    return web.json_response(result)

async def handle_service_details(request: web.Request) -> web.Response:
    service_name = request.query.get("service", "")
    result = get_service_details(service_name)
    return web.json_response(result)

# --- Processes Handlers ---

async def handle_list_processes(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 100))
    sort_by = request.query.get("sort", "cpu_percent")
    procs = list_processes(limit=limit, sort_by=sort_by)
    return web.json_response({"success": True, "processes": procs})

async def handle_signal_process(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    pid = int(data.get("pid", 0))
    sig = data.get("signal", "SIGTERM")
    result = signal_process(pid, sig)
    return web.json_response(result)

# --- VPS Configuration Handlers ---

async def handle_get_config(request: web.Request) -> web.Response:
    cfg = get_vps_configuration()
    return web.json_response({"success": True, "config": cfg})

async def handle_set_hostname(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    hostname = data.get("hostname", "")
    result = set_hostname(hostname)
    return web.json_response(result)

async def handle_set_timezone(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    tz = data.get("timezone", "")
    result = set_timezone(tz)
    return web.json_response(result)

async def handle_add_ufw_rule(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    port_or_service = data.get("port_or_service", "")
    action = data.get("action", "allow")
    result = add_ufw_rule(port_or_service, action)
    return web.json_response(result)

async def handle_delete_ufw_rule(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    rule_id = data.get("rule_id", "")
    result = delete_ufw_rule(rule_id)
    return web.json_response(result)

async def handle_toggle_ufw(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    enable = bool(data.get("enable", False))
    result = toggle_ufw(enable)
    return web.json_response(result)

async def handle_power_action(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)
    action = data.get("action", "")
    result = system_power_action(action)
    return web.json_response(result)

# --- Index & Static Serving ---

async def handle_index(request: web.Request) -> web.FileResponse:
    index_file = STATIC_DIR / "index.html"
    return web.FileResponse(index_file)

def create_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])

    # API routes
    app.router.add_post("/api/auth/login", handle_login)
    app.router.add_post("/api/auth/logout", handle_logout)
    app.router.add_get("/api/auth/status", handle_auth_status)
    app.router.add_post("/api/auth/change-password", handle_change_password)

    app.router.add_get("/api/system/metrics", handle_get_metrics)
    app.router.add_get("/ws/metrics", handle_metrics_ws)

    app.router.add_get("/ws/terminal", handle_terminal_ws)

    app.router.add_get("/api/services/list", handle_list_services)
    app.router.add_post("/api/services/control", handle_control_service)
    app.router.add_get("/api/services/logs", handle_service_logs)
    app.router.add_get("/api/services/details", handle_service_details)

    app.router.add_get("/api/processes/list", handle_list_processes)
    app.router.add_post("/api/processes/signal", handle_signal_process)

    app.router.add_get("/api/config/get", handle_get_config)
    app.router.add_post("/api/config/hostname", handle_set_hostname)
    app.router.add_post("/api/config/timezone", handle_set_timezone)
    app.router.add_post("/api/config/firewall/rule", handle_add_ufw_rule)
    app.router.add_delete("/api/config/firewall/rule", handle_delete_ufw_rule)
    app.router.add_post("/api/config/firewall/toggle", handle_toggle_ufw)
    app.router.add_post("/api/config/power", handle_power_action)

    # Static assets and index
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")
    app.router.add_get("/", handle_index)

    return app
