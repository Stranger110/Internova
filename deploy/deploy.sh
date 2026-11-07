#!/usr/bin/env bash
# High-Availability Deployment Script for Linux Server
# Supports Ubuntu, Debian, CentOS, AlmaLinux, Rocky, Fedora
set -e

echo "=========================================================="
echo "         INTERNOVA SATELLITE GROUND STATION - HA          "
echo "=========================================================="

APP_DIR="/opt/satellite-dashboard"

# 1. Check prerequisites (Docker compose v2 or legacy v1)
if command -v docker &> /dev/null && (docker compose version &> /dev/null || command -v docker-compose &> /dev/null); then
    echo "[+] Docker detected. Deploying INTERNOVA container..."
    cd "$(dirname "$0")/.."
    if docker compose version &> /dev/null; then
        docker compose up -d --build
    else
        docker-compose up -d --build
    fi
    echo "[✓] Container deployed and running with healthcheck at http://localhost:8000"
    exit 0
fi

# 2. Bare-Metal Linux installation fallback
echo "[+] Docker not detected. Setting up bare-metal systemd service..."

# Install python3 and virtualenv if needed
if command -v apt-get &> /dev/null; then
    apt-get update -y
    apt-get install -y python3 python3-pip python3-venv curl
elif command -v dnf &> /dev/null; then
    dnf install -y python3 python3-pip curl
fi

# Create directory
mkdir -p "$APP_DIR"
cp -r "$(dirname "$0")/../backend" "$APP_DIR/"
cp -r "$(dirname "$0")/../frontend" "$APP_DIR/"

# Setup Python Virtual Environment
cd "$APP_DIR/backend"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Install systemd service
cat << 'EOF' > /etc/systemd/system/satellite-dashboard.service
[Unit]
Description=High-Availability Satellite Ground Station Dashboard Daemon
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/satellite-dashboard/backend
ExecStart=/opt/satellite-dashboard/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3s
Environment=PYTHONUNBUFFERED=1
Environment=NODE_ID=linux-sat-node-systemd
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable satellite-dashboard
systemctl restart satellite-dashboard

echo "=========================================================="
echo "[✓] Deployment successful!"
echo "    Dashboard running at: http://<your-server-ip>:8000"
echo "    Healthcheck endpoint: http://<your-server-ip>:8000/healthz"
echo "    Status: systemctl status satellite-dashboard"
echo "=========================================================="
