"""
VPS Host Configuration Engine for VPSPilot
Handles Hostname, Timezone, SSH, Firewall (UFW/iptables), DNS, and System Power.
"""

import subprocess
import os
import re
import socket
from pathlib import Path

def get_hostname() -> str:
    try:
        res = subprocess.run(["hostnamectl", "--static"], stdout=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return socket.gethostname()

def set_hostname(new_name: str) -> dict:
    new_name = new_name.strip()
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', new_name):
        return {"success": False, "error": "Invalid hostname. Must be alphanumeric and up to 63 characters."}
    try:
        res = subprocess.run(["hostnamectl", "set-hostname", new_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0:
            return {"success": True, "hostname": new_name}
        return {"success": False, "error": res.stderr.strip() or "Failed to set hostname"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_timezone() -> str:
    try:
        res = subprocess.run(["timedatectl", "show", "--property=Timezone", "--value"], stdout=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    tz_file = Path("/etc/timezone")
    if tz_file.exists():
        return tz_file.read_text(encoding="utf-8").strip()
    return "UTC"

def list_common_timezones() -> list[str]:
    return [
        "UTC",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Toronto",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Amsterdam",
        "Europe/Madrid",
        "Europe/Rome",
        "Asia/Dubai",
        "Asia/Karachi",
        "Asia/Kolkata",
        "Asia/Singapore",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Australia/Sydney",
        "Pacific/Auckland"
    ]

def set_timezone(tz: str) -> dict:
    tz = tz.strip()
    try:
        res = subprocess.run(["timedatectl", "set-timezone", tz], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode == 0:
            return {"success": True, "timezone": tz}
        return {"success": False, "error": res.stderr.strip() or "Failed to set timezone"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_dns_resolvers() -> list[str]:
    resolvers = []
    resolv_conf = Path("/etc/resolv.conf")
    if resolv_conf.exists():
        try:
            for line in resolv_conf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) > 1:
                        resolvers.append(parts[1])
        except Exception:
            pass
    return resolvers

def get_ssh_config() -> dict:
    """Inspects SSH server configuration."""
    config_paths = ["/etc/ssh/sshd_config", "/etc/ssh/sshd_config.d/"]
    settings = {
        "installed": False,
        "active": False,
        "port": "22",
        "permit_root_login": "unknown",
        "password_auth": "unknown",
        "pubkey_auth": "unknown"
    }

    # Check if ssh service is running
    try:
        chk = subprocess.run(["systemctl", "is-active", "ssh"], stdout=subprocess.PIPE, text=True, check=False)
        if chk.stdout.strip() == "active":
            settings["active"] = True
            settings["installed"] = True
        else:
            chk2 = subprocess.run(["systemctl", "is-active", "sshd"], stdout=subprocess.PIPE, text=True, check=False)
            if chk2.stdout.strip() == "active":
                settings["active"] = True
                settings["installed"] = True
    except Exception:
        pass

    sshd_cfg = Path("/etc/ssh/sshd_config")
    if sshd_cfg.exists():
        settings["installed"] = True
        try:
            for line in sshd_cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    key, val = parts[0].lower(), parts[1].strip()
                    if key == "port":
                        settings["port"] = val
                    elif key == "permitrootlogin":
                        settings["permit_root_login"] = val
                    elif key == "passwordauthentication":
                        settings["password_auth"] = val
                    elif key == "pubkeyauthentication":
                        settings["pubkey_auth"] = val
        except Exception:
            pass

    return settings

def get_firewall_status() -> dict:
    """Queries firewall (UFW or iptables) status and rules."""
    has_ufw = False
    try:
        chk = subprocess.run(["which", "ufw"], stdout=subprocess.PIPE, text=True, check=False)
        has_ufw = chk.returncode == 0
    except Exception:
        pass

    if has_ufw:
        try:
            res = subprocess.run(["ufw", "status", "numbered"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            output = res.stdout
            is_active = "Status: active" in output
            rules = []
            for line in output.splitlines():
                line = line.strip()
                match = re.match(r'^\[\s*(\d+)\]\s+(.*?)\s+(ALLOW|DENY|REJECT)\s+(IN|OUT)?\s*(.*)$', line, re.IGNORECASE)
                if match:
                    rules.append({
                        "id": match.group(1),
                        "to": match.group(2).strip(),
                        "action": match.group(3).upper(),
                        "direction": match.group(4) or "IN",
                        "from": match.group(5).strip() or "Anywhere"
                    })
            return {
                "backend": "ufw",
                "available": True,
                "active": is_active,
                "rules": rules,
                "raw": output
            }
        except Exception as e:
            return {"backend": "ufw", "available": True, "active": False, "rules": [], "error": str(e)}

    # Fallback to iptables check
    try:
        res = subprocess.run(["iptables", "-L", "-n", "--line-numbers"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return {
            "backend": "iptables",
            "available": res.returncode == 0,
            "active": res.returncode == 0 and "Chain" in res.stdout,
            "rules": [],
            "raw": res.stdout[:2000] if res.returncode == 0 else res.stderr
        }
    except Exception:
        return {"backend": "none", "available": False, "active": False, "rules": []}

def add_ufw_rule(port_or_service: str, action: str = "allow") -> dict:
    port_or_service = port_or_service.strip()
    action = action.strip().lower()
    if action not in ("allow", "deny", "reject"):
        return {"success": False, "error": "Invalid action. Use allow or deny."}
    if not re.match(r'^[a-zA-Z0-9_\-\/]+$', port_or_service):
        return {"success": False, "error": "Invalid port or service specification."}

    cmd = ["ufw", action, port_or_service]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return {
            "success": res.returncode == 0,
            "message": res.stdout.strip(),
            "error": res.stderr.strip() if res.returncode != 0 else ""
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_ufw_rule(rule_id: str) -> dict:
    rule_id = str(rule_id).strip()
    if not rule_id.isdigit():
        return {"success": False, "error": "Rule ID must be a number."}
    cmd = ["ufw", "--force", "delete", rule_id]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return {
            "success": res.returncode == 0,
            "message": res.stdout.strip(),
            "error": res.stderr.strip() if res.returncode != 0 else ""
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def toggle_ufw(enable: bool) -> dict:
    action = "enable" if enable else "disable"
    cmd = ["ufw", "--force", action]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return {
            "success": res.returncode == 0,
            "active": enable,
            "message": res.stdout.strip()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_package_updates() -> dict:
    """Checks for pending system packages updates."""
    # Check if apt is available
    if Path("/usr/bin/apt").exists():
        try:
            res = subprocess.run(
                ["apt", "list", "--upgradable"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            upgradable = []
            for line in res.stdout.splitlines():
                if "/" in line and not line.startswith("Listing..."):
                    upgradable.append(line.strip())
            return {
                "manager": "apt",
                "upgradable_count": len(upgradable),
                "packages": upgradable[:50]
            }
        except Exception as e:
            return {"manager": "apt", "error": str(e), "upgradable_count": 0}

    return {"manager": "generic", "upgradable_count": 0, "packages": []}

def system_power_action(action: str) -> dict:
    """Executes a system reboot or poweroff."""
    if action not in ("reboot", "poweroff"):
        return {"success": False, "error": "Invalid action. Choose reboot or poweroff."}
    try:
        # Asynchronously schedule reboot so web request can finish returning
        subprocess.Popen(["systemctl", action])
        return {"success": True, "action": action, "message": f"System {action} initiated."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_vps_configuration() -> dict:
    """Aggregates all VPS configuration items into a single status object."""
    return {
        "hostname": get_hostname(),
        "timezone": get_timezone(),
        "available_timezones": list_common_timezones(),
        "dns_resolvers": get_dns_resolvers(),
        "ssh": get_ssh_config(),
        "firewall": get_firewall_status(),
        "updates": check_package_updates()
    }
