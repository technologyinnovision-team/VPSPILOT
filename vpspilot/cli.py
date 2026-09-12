"""
Command Line Interface for VPSPilot
Entry point for starting, stopping, configuring, and installing VPSPilot as a system service.
"""

import sys
import os
import argparse
import signal
import time
import subprocess
import getpass
from pathlib import Path
from aiohttp import web

from vpspilot import __version__
from vpspilot.config import (
    init_config,
    load_config,
    update_password,
    get_pid_file,
    get_log_file,
    get_config_file,
    DEFAULT_PORT,
    DEFAULT_HOST
)
from vpspilot.server import create_app

BANNER = rf"""
 __      _______   _____ _____ _____ _      ____ _______ 
 \ \    / /  __ \ / ____|  __ \_   _| |    / __ \__   __|
  \ \  / /| |__) | (___ | |__) || | | |   | |  | | | |   
   \ \/ / |  ___/ \___ \|  ___/ | | | |   | |  | | | |   
    \  /  | |     ____) | |    _| |_| |___| |__| | | |   
     \/   |_|    |_____/|_|   |_____|______\____/  |_|   
          The Autonomous VPS Command Center (v{__version__})
"""

def print_banner(host: str, port: int, temp_password: str | None = None):
    print(BANNER)
    display_host = "localhost" if host == "127.0.0.1" else host
    print(f" [+] VPSPilot Web Dashboard: http://{display_host}:{port}")
    if host == "0.0.0.0":
        # Print detected local IP addresses
        try:
            import socket
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            print(f" [+] Primary LAN Address:    http://{ip}:{port}")
        except Exception:
            pass

    cfg = load_config()
    username = cfg.get("admin_username", "admin")
    print(f" [+] Default Admin User:     {username}")

    if temp_password:
        print(f"\n [!] >>> INITIAL ADMIN PASSWORD: {temp_password} <<<")
        print(" [!] Please save this password or change it inside the dashboard / via CLI.\n")
    else:
        print(" [+] Authentication:         Password configured.\n")

def run_server(host: str, port: int):
    app = create_app()
    web.run_app(app, host=host, port=port, print=False)

def start_daemon(host: str, port: int):
    pid_file = get_pid_file()
    log_file = get_log_file()

    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.kill(old_pid, 0)
            print(f"[-] VPSPilot is already running with PID {old_pid}")
            return
        except (OSError, ValueError):
            pid_file.unlink(missing_ok=True)

    print(f"[+] Starting VPSPilot daemon on {host}:{port}...")
    # Launch subprocess in detached mode
    cmd = [sys.executable, "-m", "vpspilot.cli", "start", "--host", host, "--port", str(port), "--foreground"]
    with open(log_file, "a", encoding="utf-8") as out:
        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=out,
            start_new_session=True
        )
    pid_file.write_text(str(proc.pid))
    print(f"[+] VPSPilot daemon started with PID {proc.pid}")
    print(f"[+] Logs streaming to: {log_file}")
    print(f"[+] Access URL: http://{host}:{port}")

def stop_daemon():
    pid_file = get_pid_file()
    if not pid_file.exists():
        print("[-] VPSPilot is not running (no PID file found).")
        return

    try:
        pid = int(pid_file.read_text().strip())
        print(f"[+] Stopping VPSPilot (PID {pid})...")
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            print("[!] Process did not exit gracefully, sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
        pid_file.unlink(missing_ok=True)
        print("[+] VPSPilot stopped successfully.")
    except (ProcessLookupError, ValueError):
        pid_file.unlink(missing_ok=True)
        print("[-] Process was not running. Cleared stale PID file.")
    except PermissionError:
        print(f"[-] Permission denied to kill PID {pid}. Try with sudo.")

def check_status():
    pid_file = get_pid_file()
    if not pid_file.exists():
        print("[-] VPSPilot is NOT running.")
        return

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        cfg = load_config()
        port = cfg.get("port", DEFAULT_PORT)
        host = cfg.get("host", DEFAULT_HOST)
        print(f"[+] VPSPilot is RUNNING (PID: {pid})")
        print(f"[+] Dashboard URL: http://{host}:{port}")
    except OSError:
        print(f"[-] Stale PID file found ({pid}), but process is not alive.")
        pid_file.unlink(missing_ok=True)

def cmd_set_password(args):
    if args.password:
        pwd = args.password
    else:
        pwd = getpass.getpass("Enter new VPSPilot admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if pwd != confirm:
            print("[-] Passwords do not match!")
            sys.exit(1)

    if len(pwd) < 6:
        print("[-] Password must be at least 6 characters.")
        sys.exit(1)

    update_password(pwd)
    print("[+] Admin password updated successfully.")

def install_systemd_service():
    if os.geteuid() != 0:
        print("[-] Error: Installing systemd service requires root privileges. Please run with sudo.")
        sys.exit(1)

    # Detect vpspilot executable or fallback to python module
    import shutil
    vpspilot_bin = shutil.which("vpspilot")
    if vpspilot_bin:
        exec_start = f"{vpspilot_bin} start --host 0.0.0.0 --port 8888 --foreground"
    else:
        exec_start = f"{sys.executable} -m vpspilot.cli start --host 0.0.0.0 --port 8888 --foreground"

    service_content = f"""[Unit]
Description=VPSPilot - The Autonomous VPS Command Center
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/
ExecStart={exec_start}
Restart=always
RestartSec=3
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    dest = Path("/etc/systemd/system/vpspilot.service")
    dest.write_text(service_content, encoding="utf-8")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    # Enable and start immediately so it ALWAYS runs
    subprocess.run(["systemctl", "enable", "--now", "vpspilot.service"], check=True)
    subprocess.run(["systemctl", "restart", "vpspilot.service"], check=True)
    print("[+] Successfully installed and started persistent systemd service: /etc/systemd/system/vpspilot.service")
    print("[+] VPSPilot is now ALWAYS RUNNING (auto-starts on boot and restarts on failure)!")
    print("[+] Check live status with: sudo systemctl status vpspilot")

def uninstall_systemd_service():
    if os.geteuid() != 0:
        print("[-] Error: Removing systemd service requires root privileges. Please run with sudo.")
        sys.exit(1)

    dest = Path("/etc/systemd/system/vpspilot.service")
    if dest.exists():
        subprocess.run(["systemctl", "stop", "vpspilot.service"], check=False)
        subprocess.run(["systemctl", "disable", "vpspilot.service"], check=False)
        dest.unlink()
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("[+] Successfully removed /etc/systemd/system/vpspilot.service")
    else:
        print("[-] Service file /etc/systemd/system/vpspilot.service does not exist.")

def main():
    parser = argparse.ArgumentParser(
        prog="vpspilot",
        description="VPSPilot: Autonomous VPS Command Center and Web Dashboard"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Start command
    start_p = subparsers.add_parser("start", help="Start the VPSPilot web dashboard")
    start_p.add_argument("--port", "-p", type=int, default=None, help=f"Port to bind (default: {DEFAULT_PORT})")
    start_p.add_argument("--host", "-H", type=str, default=None, help=f"Host to bind (default: {DEFAULT_HOST})")
    start_p.add_argument("--daemon", "-d", action="store_true", help="Run in background daemon mode")
    start_p.add_argument("--foreground", "-f", action="store_true", help="Run in foreground (internal)")
    start_p.add_argument("--password", type=str, default=None, help="Explicitly set/override initial admin password")

    # Stop command
    subparsers.add_parser("stop", help="Stop the running VPSPilot daemon")

    # Restart command
    restart_p = subparsers.add_parser("restart", help="Restart VPSPilot daemon")
    restart_p.add_argument("--port", "-p", type=int, default=None)
    restart_p.add_argument("--host", "-H", type=str, default=None)

    # Status command
    subparsers.add_parser("status", help="Check status of VPSPilot daemon")

    # Set password command
    pwd_p = subparsers.add_parser("set-password", help="Update the admin password")
    pwd_p.add_argument("password", nargs="?", default=None, help="New password")

    # Config command
    cfg_p = subparsers.add_parser("config", help="View configuration details")
    cfg_p.add_argument("action", choices=["show", "path"], default="show", nargs="?")

    # Systemd commands
    subparsers.add_parser("install-service", help="Install VPSPilot as a persistent systemd service")
    subparsers.add_parser("uninstall-service", help="Uninstall the VPSPilot systemd service")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "start":
        cfg, initial_pwd = init_config(
            default_port=args.port,
            default_host=args.host,
            explicit_password=args.password
        )
        bind_host = args.host or cfg.get("host", DEFAULT_HOST)
        bind_port = args.port or cfg.get("port", DEFAULT_PORT)

        if args.daemon and not args.foreground:
            start_daemon(bind_host, bind_port)
        else:
            print_banner(bind_host, bind_port, initial_pwd)
            # Write PID for foreground as well
            pid_file = get_pid_file()
            pid_file.write_text(str(os.getpid()))
            try:
                run_server(bind_host, bind_port)
            finally:
                pid_file.unlink(missing_ok=True)

    elif args.command == "stop":
        stop_daemon()

    elif args.command == "restart":
        stop_daemon()
        time.sleep(1)
        cfg = load_config()
        host = args.host or cfg.get("host", DEFAULT_HOST)
        port = args.port or cfg.get("port", DEFAULT_PORT)
        start_daemon(host, port)

    elif args.command == "status":
        check_status()

    elif args.command == "set-password":
        cmd_set_password(args)

    elif args.command == "config":
        if args.action == "path":
            print(f"Config path: {get_config_file()}")
        else:
            cfg = dict(load_config())
            if "password_hash" in cfg:
                cfg["password_hash"] = "*** (PBKDF2 SHA256) ***"
            if "password_salt" in cfg:
                cfg["password_salt"] = "***"
            if "secret_key" in cfg:
                cfg["secret_key"] = "***"
            import json
            print(f"Config file: {get_config_file()}")
            print(json.dumps(cfg, indent=2))

    elif args.command == "install-service":
        install_systemd_service()

    elif args.command == "uninstall-service":
        uninstall_systemd_service()

if __name__ == "__main__":
    main()
