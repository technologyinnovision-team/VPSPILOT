"""
Systemd Services Manager for VPSPilot
Allows listing, inspecting, filtering, starting, stopping, restarting,
and retrieving real-time journal logs for system services.
"""

import subprocess
import json
import re
import shlex
from typing import Optional

ALLOWED_ACTIONS = {"start", "stop", "restart", "reload", "enable", "disable"}

def sanitize_service_name(name: str) -> str:
    """Sanitizes service name to prevent command injection."""
    name = name.strip()
    if not re.match(r'^[a-zA-Z0-9_@\.\-]+$', name):
        raise ValueError("Invalid service name format")
    if not name.endswith('.service'):
        name = f"{name}.service"
    return name

def list_services() -> list[dict]:
    """
    Returns list of all system services with their status.
    Attempts JSON output first, then falls back to plain table parsing.
    """
    try:
        # Try modern systemctl with JSON output
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--output=json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            raw_units = json.loads(result.stdout)
            services = []
            for u in raw_units:
                unit_name = u.get("unit", "")
                if not unit_name:
                    continue
                services.append({
                    "name": unit_name,
                    "clean_name": unit_name.removesuffix(".service"),
                    "load": u.get("load", "unknown"),
                    "active": u.get("active", "unknown"),
                    "sub": u.get("sub", "unknown"),
                    "description": u.get("description", "")
                })
            return services
    except Exception:
        pass

    # Fallback to plain text parsing
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        lines = result.stdout.splitlines()
        services = []
        for line in lines:
            line = line.strip()
            if not line or "LOAD" in line or line.startswith("●") or line.startswith("UNIT"):
                continue
            parts = line.split(None, 4)
            if len(parts) >= 4 and parts[0].endswith(".service"):
                unit_name = parts[0]
                description = parts[4] if len(parts) > 4 else ""
                services.append({
                    "name": unit_name,
                    "clean_name": unit_name.removesuffix(".service"),
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": description
                })
        return services
    except Exception as e:
        return [{"error": str(e)}]

def control_service(service_name: str, action: str) -> dict:
    """
    Executes a service action: start, stop, restart, reload, enable, disable.
    """
    if action not in ALLOWED_ACTIONS:
        return {"success": False, "error": f"Action '{action}' not permitted. Allowed: {sorted(list(ALLOWED_ACTIONS))}"}

    try:
        clean_name = sanitize_service_name(service_name)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    cmd = ["systemctl", action, clean_name]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0:
            return {
                "success": True,
                "service": clean_name,
                "action": action,
                "message": f"Successfully performed {action} on {clean_name}"
            }
        else:
            return {
                "success": False,
                "service": clean_name,
                "action": action,
                "error": res.stderr.strip() or f"Command failed with exit code {res.returncode}"
            }
    except Exception as e:
        return {"success": False, "service": clean_name, "action": action, "error": str(e)}

def get_service_logs(service_name: str, lines: int = 100) -> dict:
    """Retrieves recent journal logs for the specified service."""
    try:
        clean_name = sanitize_service_name(service_name)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    lines = max(10, min(lines, 1000))
    cmd = ["journalctl", "-u", clean_name, "-n", str(lines), "--no-pager"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return {
            "success": True,
            "service": clean_name,
            "logs": res.stdout,
            "error_output": res.stderr if res.returncode != 0 else ""
        }
    except Exception as e:
        return {"success": False, "service": clean_name, "error": str(e)}

def get_service_details(service_name: str) -> dict:
    """Returns detailed status output and enablement status of a service."""
    try:
        clean_name = sanitize_service_name(service_name)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    status_cmd = ["systemctl", "status", clean_name, "--no-pager"]
    enabled_cmd = ["systemctl", "is-enabled", clean_name]

    res_status = subprocess.run(status_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    res_enabled = subprocess.run(enabled_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

    return {
        "success": True,
        "service": clean_name,
        "is_enabled": res_enabled.stdout.strip() == "enabled",
        "raw_status": res_status.stdout
    }
