import os
import sys
import shutil
import subprocess
from setuptools import setup, find_packages
from setuptools.command.install import install

class CustomInstallCommand(install):
    """Custom installation command that automatically sets up and starts the systemd service when run as root."""
    def run(self):
        super().run()
        # If running on Linux as root with systemd available, auto-install and start the daemon
        if os.name == "posix" and os.geteuid() == 0 and os.path.exists("/run/systemd/system"):
            try:
                vpspilot_bin = shutil.which("vpspilot") or f"{sys.executable} -m vpspilot.cli"
                service_content = f"""[Unit]
Description=VPSPilot - The Autonomous VPS Command Center
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/
ExecStart={vpspilot_bin} start --host 0.0.0.0 --port 8888 --foreground
Restart=always
RestartSec=3
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
                service_path = "/etc/systemd/system/vpspilot.service"
                with open(service_path, "w", encoding="utf-8") as f:
                    f.write(service_content)
                subprocess.run(["systemctl", "daemon-reload"], check=False)
                subprocess.run(["systemctl", "enable", "--now", "vpspilot.service"], check=False)
                print("\n[+] VPSPilot systemd service automatically installed & started! It will always run in the background.\n")
            except Exception as e:
                print(f"\n[!] Note: To enable always-running background service, run: sudo vpspilot install-service ({e})\n")

setup(
    name="vpspilot",
    version="1.0.0",
    description="VPSPilot: The Autonomous Next-Gen VPS Command Center & Online Management Dashboard",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "vpspilot": [
            "static/*",
            "static/css/*",
            "static/js/*",
            "static/vendor/*",
            "templates/*"
        ]
    },
    install_requires=[
        "aiohttp>=3.8.0",
        "psutil>=5.8.0"
    ],
    entry_points={
        "console_scripts": [
            "vpspilot=vpspilot.cli:main"
        ]
    },
    cmdclass={
        "install": CustomInstallCommand
    },
    python_requires=">=3.9"
)
