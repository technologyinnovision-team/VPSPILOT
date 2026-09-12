# ⚡ VPSPilot: Precision VPS Management Deck & Web Command Center

[![PyPI Version](https://img.shields.io/pypi/v/vpspilot.svg?color=blue)](https://pypi.org/project/vpspilot/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**VPSPilot** is an autonomous, production-grade Python package and web dashboard engineered specifically for Linux Virtual Private Servers (VPS). It equips VPS owners and sysadmins with an online command center for host configuration, real-time hardware telemetry, full-duplex interactive web terminal, and complete systemd service management.

When installed, VPSPilot is designed to **always run** in the background as an automated persistent systemd daemon that starts on server boot and auto-restarts on any failure.

---

## 🌟 Key Capabilities

- 🔄 **Always Running Daemon**: Registers directly with systemd (`Restart=always`, `RestartSec=3`, `WantedBy=multi-user.target`) to guarantee uninterrupted 24/7 background operation across reboots.
- 📊 **Real-Time Telemetry**: Live per-core CPU utilization, RAM usage, swap space, mounted filesystem quotas, and live RX/TX network transfer rates.
- 💻 **Interactive Web Terminal**: Full-featured web shell powered by `xterm.js` and `/dev/pts` pseudo-terminals with resize detection (`TIOCSWINSZ`), ANSI colors, and shortcut toolbar (Ctrl+C, Ctrl+D, Clear, Reconnect).
- ⚙️ **All Services Manager**: Real-time listing of all systemd units with state filters (`active`, `inactive`, `failed`), one-click controls (Start, Stop, Restart), and an integrated Journalctl log inspector modal.
- 🛠️ **VPS Configuration Deck**:
  - Hostname changer (`hostnamectl`)
  - Timezone selector (`timedatectl`)
  - DNS resolvers viewer (`/etc/resolv.conf`)
  - SSH daemon security inspection (Port, Root Login, Password Auth)
  - Firewall manager (UFW rules: Allow/Deny, rule removal, enable/disable toggle)
  - System maintenance (package update status, cache cleanup, safe Reboot/Poweroff)
- 🗂️ **Process Explorer**: Live running processes list sorted by CPU% or Memory% with instant `SIGTERM` / `SIGKILL` signals.
- 🔒 **Enterprise-Grade Security**: PBKDF2-HMAC-SHA256 password hashing, secure session tokens, rate-limited login defense, and strict permission enforcement (`0600` on credentials).
- 📦 **Offline-Ready & Zero CDN Dependency**: `xterm.js` and vendor assets are bundled inside the Python package, ensuring the terminal functions flawlessly on isolated or restricted networks.

---

## 🚀 One-Line Automated Install (Always Runs on Boot)

Run this single command on your Linux VPS as root:

```bash
curl -sSL https://raw.githubusercontent.com/technologyinnovision-team/VPSPILOT/main/install.sh | sudo bash
```

The automated installer will:
1. Install Python 3 and pip dependencies.
2. Install `vpspilot`.
3. Configure and activate the persistent systemd service (`systemctl enable --now vpspilot.service`).
4. Output your access URL (`http://<YOUR-VPS-IP>:8888`) and initial administrative password.

---

## 📦 PyPI Package Installation

Once published on PyPI, install via pip:

```bash
# Install globally
pip install vpspilot

# Activate the always-running persistent system service
sudo vpspilot install-service
```

---

## 🖥️ Command Line Usage

Once installed, the global `vpspilot` executable is available from any terminal:

```bash
# View live status of VPSPilot service
sudo systemctl status vpspilot
# Or via CLI
vpspilot status

# Check or change admin password
vpspilot set-password

# View configuration
vpspilot config show

# Start manually in foreground
vpspilot start --port 8888

# Start manually in background daemon mode
vpspilot start --port 8888 --daemon

# Stop or restart daemon
vpspilot stop
vpspilot restart

# Install / Uninstall systemd service
sudo vpspilot install-service
sudo vpspilot uninstall-service
```

---

## 🌐 Web Dashboard Access

Open your browser and navigate to:
```
http://<YOUR-VPS-IP>:8888
```

---

## 📦 Publishing to PyPI

To publish a new release to PyPI:

### Option A: Using Twine (CLI)
```bash
# 1. Build distribution
python3 -m build

# 2. Check build artifacts
twine check dist/*

# 3. Upload to PyPI (requires PyPI API Token)
twine upload dist/*
```

### Option B: Automatic via GitHub Actions
Add your PyPI API token as a secret named `PYPI_API_TOKEN` in your GitHub Repository settings (`Settings -> Secrets and variables -> Actions`).
Then push a git tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```
The included GitHub Action (`.github/workflows/publish-pypi.yml`) will automatically build and publish the release to PyPI.

---

## 🏗️ Architecture

```
Client Browser (SPA)
  │
  ├── REST API (/api/*)  ──> aiohttp Web Server
  ├── Telemetry WS (/ws/metrics) ──> psutil + /proc Kernel Telemetry
  └── Web Terminal WS (/ws/terminal) ──> Python PTY Bridge (pty.openpty)
                                              │
                                              └── /dev/pts (bash/zsh login shell)
```

---

## 📄 License
Apache-2.0. Technology Innovision Team.
