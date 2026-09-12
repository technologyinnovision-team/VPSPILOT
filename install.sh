#!/usr/bin/env bash
# ==============================================================================
# VPSPilot - Autonomous VPS Command Center & Web Dashboard
# One-Line Auto-Installer & Persistent Service Setup
# ==============================================================================
set -e

# ANSI Color Codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
cat << "EOF"
 __      _______   _____ _____ _____ _      ____ _______ 
 \ \    / /  __ \ / ____|  __ \_   _| |    / __ \__   __|
  \ \  / /| |__) | (___ | |__) || | | |   | |  | | | |   
   \ \/ / |  ___/ \___ \|  ___/ | | | |   | |  | | | |   
    \  /  | |     ____) | |    _| |_| |___| |__| | | |   
     \/   |_|    |_____/|_|   |_____|______\____/  |_|   
EOF
echo -e "       ${BLUE}VPSPilot Automated Persistent Installer${NC}\n"

# 1. Check Root Privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[-] Error: This installer must be run as root.${NC}"
  echo -e "    Please run: sudo bash $0"
  exit 1
fi

echo -e "${GREEN}[+]${NC} Verifying system requirements..."

# 2. Package Manager & Python Detection
if ! command -v python3 &>/dev/null; then
  echo -e "${YELLOW}[!] python3 not found. Installing python3 and pip...${NC}"
  if command -v apt-get &>/dev/null; then
    apt-get update -y && apt-get install -y python3 python3-pip python3-venv curl
  elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip curl
  elif command -v yum &>/dev/null; then
    yum install -y python3 python3-pip curl
  elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm python python-pip curl
  else
    echo -e "${RED}[-] Unsupported package manager. Please install python3 and pip manually.${NC}"
    exit 1
  fi
fi

# 3. Install VPSPilot
echo -e "${GREEN}[+]${NC} Installing VPSPilot package..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
  # Local source installation
  echo -e "    Installing from local source at $SCRIPT_DIR..."
  python3 -m pip install --break-system-packages "$SCRIPT_DIR" || python3 -m pip install "$SCRIPT_DIR"
else
  # Remote installation via PyPI
  echo -e "    Installing latest release from PyPI..."
  python3 -m pip install --break-system-packages --upgrade vpspilot || python3 -m pip install --upgrade vpspilot
fi

# Locate vpspilot binary
VPSPILOT_BIN="$(which vpspilot || echo "")"
if [ -z "$VPSPILOT_BIN" ]; then
  if [ -f "/usr/local/bin/vpspilot" ]; then
    VPSPILOT_BIN="/usr/local/bin/vpspilot"
  elif [ -f "$HOME/.local/bin/vpspilot" ]; then
    VPSPILOT_BIN="$HOME/.local/bin/vpspilot"
  else
    VPSPILOT_BIN="$(command -v python3) -m vpspilot.cli"
  fi
fi

echo -e "${GREEN}[+]${NC} VPSPilot executable resolved: ${VPSPILOT_BIN}"

# 4. Initialize Configuration & Credentials
echo -e "${GREEN}[+]${NC} Initializing configuration in /etc/vpspilot..."
mkdir -p /etc/vpspilot
chmod 700 /etc/vpspilot

# Run config init to generate password if not present
python3 -c '
from vpspilot.config import init_config
cfg, generated_pwd = init_config()
if generated_pwd:
    print(f"__VPSPILOT_GEN_PWD__:{generated_pwd}")
' > /tmp/vpspilot_init.out 2>&1 || true

INIT_PWD=$(grep "__VPSPILOT_GEN_PWD__:" /tmp/vpspilot_init.out | cut -d':' -f2 || true)
rm -f /tmp/vpspilot_init.out

# 5. Create Systemd Service (Always Running & Auto-restart)
echo -e "${GREEN}[+]${NC} Configuring persistent systemd daemon..."

cat << EOF > /etc/systemd/system/vpspilot.service
[Unit]
Description=VPSPilot - The Autonomous VPS Command Center
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/
ExecStart=${VPSPILOT_BIN} start --host 0.0.0.0 --port 8888 --foreground
Restart=always
RestartSec=3
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chmod 644 /etc/systemd/system/vpspilot.service

# 6. Enable and Start the Service Immediately
echo -e "${GREEN}[+]${NC} Enabling and starting vpspilot.service..."
systemctl daemon-reload
systemctl enable --now vpspilot.service
systemctl restart vpspilot.service

# 7. Check Service Health
sleep 1
if systemctl is-active --quiet vpspilot.service; then
  echo -e "${GREEN}[+] VPSPilot service is ACTIVE and ALWAYS RUNNING!${NC}\n"
else
  echo -e "${YELLOW}[!] Notice: Service started, checking journalctl...${NC}"
  journalctl -u vpspilot.service -n 10 --no-pager
fi

# 8. Print Connection Details
PORT=8888
PRIMARY_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR-SERVER-IP")

echo -e "=================================================================="
echo -e "${GREEN}🚀 VPSPilot is now actively running in the background!${NC}"
echo -e "   It will automatically launch on server boot and auto-restart."
echo -e "=================================================================="
echo -e " 🌐 Web Dashboard:    ${CYAN}http://${PRIMARY_IP}:${PORT}${NC}"
echo -e " 🌐 Local Address:    ${CYAN}http://localhost:${PORT}${NC}"
echo -e " 👤 Default User:     ${YELLOW}admin${NC}"

if [ -n "$INIT_PWD" ]; then
  echo -e " 🔑 Admin Password:   ${YELLOW}${INIT_PWD}${NC}"
  echo -e "    ${RED}Please save this password securely!${NC}"
else
  echo -e " 🔑 Admin Password:   (Already configured in /etc/vpspilot/config.json)"
fi
echo -e "=================================================================="
echo -e " Useful commands:"
echo -e "   systemctl status vpspilot   # Check status"
echo -e "   systemctl restart vpspilot  # Restart daemon"
echo -e "   journalctl -u vpspilot -f   # View live logs"
echo -e "   vpspilot set-password       # Change password"
echo -e "==================================================================\n"
