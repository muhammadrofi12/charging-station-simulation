#!/bin/bash
set -e

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "Penggunaan: bash scripts/setup_ssl.sh <nama-domain-anda>"
    echo "Contoh    : bash scripts/setup_ssl.sh spklu.example.com"
    exit 1
fi

echo "========================================================"
echo "🔒 SETUP HTTPS & DOMAIN UNTUK: $DOMAIN 🔒"
echo "========================================================"

# 1. Update charging-station service to run on internal port 8000
echo "[1/4] Mengatur aplikasi berjalan di port internal 8000..."
SERVICE_FILE="/etc/systemd/system/charging-station.service"
if [ -f "$SERVICE_FILE" ]; then
    sed -i 's/--port 80/--port 8000/g' "$SERVICE_FILE"
    sed -i 's/Environment="PORT=80"/Environment="PORT=8000"/g' "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl restart charging-station
fi

# 2. Install Caddy Web Server
echo "[2/4] Menginstal Caddy Web Server..."
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

# 3. Configure Caddyfile
echo "[3/4] Mengonfigurasi SSL Let's Encrypt untuk $DOMAIN..."
cat <<EOF > /etc/caddy/Caddyfile
$DOMAIN {
    reverse_proxy 127.0.0.1:8000
}
EOF

# 4. Restart Caddy
echo "[4/4] Mengaktifkan HTTPS..."
systemctl daemon-reload
systemctl enable caddy
systemctl restart caddy

# Open Firewall ports 80 and 443
ufw allow 80/tcp || true
ufw allow 443/tcp || true

echo "========================================================"
echo "🎉 HTTPS BERHASIL DIAKTIFKAN! 🎉"
echo "========================================================"
echo "Domain Anda sekarang sudah memiliki sertifikat SSL resmi (🔒):"
echo ""
echo " [💻] Layar Kiosk : https://$DOMAIN/kiosk"
echo " [📱] Layar Driver: https://$DOMAIN/driver"
echo "========================================================"
