#!/usr/bin/env bash
# Pi Print Server — install script
# Run as a regular user (the script calls sudo where needed).
# Tested on Raspberry Pi OS Lite (32-bit, Bullseye / Bookworm).

set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-pi}"

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Root check ─────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  error "Please run with sudo: sudo bash install.sh"
fi

echo ""
echo "======================================"
echo "  Pi Print Server — Setup"
echo "======================================"
echo ""

# ── 1. Static IP ───────────────────────────────────────────────────────────
info "Step 1: Static IP configuration"
echo ""
read -rp "  Network interface (wlan0 / eth0) [wlan0]: " IFACE
IFACE="${IFACE:-wlan0}"

read -rp "  Static IP address (e.g. 192.168.1.100): " STATIC_IP
[ -z "$STATIC_IP" ] && error "IP address cannot be empty."

read -rp "  Router/gateway IP (e.g. 192.168.1.1): " GATEWAY
[ -z "$GATEWAY" ] && error "Gateway cannot be empty."

read -rp "  DNS server [1.1.1.1]: " DNS
DNS="${DNS:-1.1.1.1}"

DHCPCD_CONF="/etc/dhcpcd.conf"

if grep -q "interface ${IFACE}" "$DHCPCD_CONF" 2>/dev/null; then
  warn "Static IP block for ${IFACE} already exists in ${DHCPCD_CONF} — skipping."
else
  cat >> "$DHCPCD_CONF" <<EOF

# Added by pi-printer install.sh
interface ${IFACE}
static ip_address=${STATIC_IP}/24
static routers=${GATEWAY}
static domain_name_servers=${DNS}
EOF
  info "Static IP written to ${DHCPCD_CONF}."
  systemctl restart dhcpcd || warn "Could not restart dhcpcd — reboot to apply IP change."
fi

# ── 2. Install system packages ─────────────────────────────────────────────
info "Step 2: Installing system packages (CUPS, Python 3, venv)…"
apt-get update -qq
apt-get install -y cups cups-bsd python3 python3-venv python3-pip

# ── 3. CUPS permissions ────────────────────────────────────────────────────
info "Step 3: Configuring CUPS"
usermod -aG lp      "$SERVICE_USER"
usermod -aG lpadmin "$SERVICE_USER"
cupsctl --remote-any
systemctl enable cups
systemctl start cups
info "CUPS is running. Add your printer at: http://${STATIC_IP}:631"

# ── 4. Python virtual environment ──────────────────────────────────────────
info "Step 4: Setting up Python virtual environment…"
VENV_DIR="${INSTALL_DIR}/venv"

sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"
info "Dependencies installed in ${VENV_DIR}"

# ── 5. Uploads directory ───────────────────────────────────────────────────
info "Step 5: Creating uploads directory…"
UPLOADS_DIR="${INSTALL_DIR}/uploads"
mkdir -p "$UPLOADS_DIR"
chown "$SERVICE_USER":"$SERVICE_USER" "$UPLOADS_DIR"

# ── 6. Log directory ───────────────────────────────────────────────────────
info "Step 6: Creating log directory…"
LOG_DIR="/var/log/pi-printer"
mkdir -p "$LOG_DIR"
chown "$SERVICE_USER":"$SERVICE_USER" "$LOG_DIR"

# ── 7. systemd service ─────────────────────────────────────────────────────
info "Step 7: Installing systemd service…"

# Write the service file with the actual install path baked in
cat > /etc/systemd/system/pi-printer.service <<EOF
[Unit]
Description=Pi Print Server
After=network.target cups.service
Requires=cups.service

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/gunicorn \\
    --workers 1 \\
    --bind 0.0.0.0:5000 \\
    --timeout 60 \\
    --access-logfile ${LOG_DIR}/access.log \\
    --error-logfile ${LOG_DIR}/error.log \\
    app:app
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pi-printer
systemctl start pi-printer

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "======================================"
echo -e "  ${GREEN}Setup complete!${NC}"
echo "======================================"
echo ""
echo "  Service status : sudo systemctl status pi-printer"
echo "  Live logs      : journalctl -u pi-printer -f"
echo ""
echo "  Next steps:"
echo "    1. Open http://${STATIC_IP}:631 and add your USB printer in CUPS"
echo "    2. Open http://${STATIC_IP}:5000 to use the print server"
echo ""
info "Reboot recommended if IP address was changed."
echo ""
