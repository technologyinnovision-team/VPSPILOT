# ⚡ VPSPilot: Precision VPS Management Deck & Web Command Center

**VPSPilot** is an autonomous, production-grade Python package and web dashboard engineered specifically for Linux Virtual Private Servers (VPS). It equips VPS owners and sysadmins with an online command center for host configuration, real-time hardware telemetry, full-duplex interactive web terminal, and complete systemd service management.

---

## 🌟 Key Capabilities

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

## 🚀 Installation

### Global Install via pip
```bash
pip install --break-system-packages .
```

Or install in development/editable mode:
```bash
pip install --break-system-packages -e .
```

---

## 🖥️ Command Line Usage

Once installed, the global `vpspilot` executable is available anywhere:

```bash
# Start VPSPilot in foreground
vpspilot start --port 8888

# Start VPSPilot as a background daemon
vpspilot start --port 8888 --daemon

# Check daemon status
vpspilot status

# Stop daemon
vpspilot stop

# Restart daemon
vpspilot restart

# Change admin password
vpspilot set-password

# View current configuration
vpspilot config show

# Install as an automated systemd service (boots on server start)
sudo vpspilot install-service

# Uninstall systemd service
sudo vpspilot uninstall-service
```

---

## 🌐 Web Dashboard Access

After launching, open your browser and navigate to:
```
http://<YOUR-VPS-IP>:8888
```

On first launch, an initial administrative password is automatically generated and printed to the terminal console if one has not been specified.

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
Apache-2.0 / MIT. Crafted with precision for Linux VPS systems.
