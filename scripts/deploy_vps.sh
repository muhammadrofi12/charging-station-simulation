#!/bin/bash
set -e

echo "========================================================"
echo "⚡ VOLTX EV CHARGING STATION - AUTOMATIC VPS DEPLOYMENT ⚡"
echo "========================================================"

# 1. Update system packages
echo "[1/6] Mengupdate sistem dan menginstal dependensi..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl ufw

# 2. Setup project directory
INSTALL_DIR="/var/www/charging-station"
echo "[2/6] Mempersiapkan direktori project di $INSTALL_DIR..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Direktori sudah ada, mengambil update terbaru dari Git..."
    cd "$INSTALL_DIR"
    git reset --hard
    git pull origin main
else
    git clone https://github.com/soul222/charging-station.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 3. Setup Python Virtual Environment
echo "[3/6] Membuat Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Setup Systemd Service (Auto-start saat server boot & auto-restart jika crash)
echo "[4/6] Mengonfigurasi Systemd Service (Port 80)..."
SERVICE_FILE="/etc/systemd/system/charging-station.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=VOLTX EV Charging Station Simulator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CLOUD_MODE=true"
Environment="PORT=80"
ExecStart=$INSTALL_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable charging-station
systemctl restart charging-station

# 5. Configure Firewall (UFW)
echo "[5/6] Membuka port 80 (HTTP) dan 22 (SSH)..."
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

# 6. Get Server Public IP
SERVER_IP=$(curl -s -4 ifconfig.me || curl -s -4 api.ipify.org || hostname -I | awk '{print $1}')

echo "========================================================"
echo "🎉 DEPLOYMENT BERHASIL! APLIKASI TELAH AKTIF 24 JAM! 🎉"
echo "========================================================"
echo "Klien dan Anda sekarang bisa membuka:"
echo ""
echo " [💻] Layar Kiosk Laptop : http://$SERVER_IP/kiosk"
echo " [📱] Aplikasi Driver HP : http://$SERVER_IP/driver"
echo ""
echo " Status Service: $(systemctl is-active charging-station)"
echo " Log Aplikasi  : journalctl -u charging-station -f"
echo "========================================================"
