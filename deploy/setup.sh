#!/usr/bin/env bash
# One-time Hetzner server setup — run as root on a fresh Ubuntu 24.04 VPS.
# After this script, complete the manual steps printed at the end.
set -euo pipefail

echo "=== Market Dashboard — Hetzner setup ==="

# ── 1. System packages ─────────────────────────────────────────────────────
apt-get update -q
apt-get install -y --no-install-recommends curl git unzip ca-certificates gnupg

# ── 2. Docker ──────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
else
  echo "Docker already installed: $(docker --version)"
fi

# ── 3. Service user ────────────────────────────────────────────────────────
if ! id market &>/dev/null; then
  echo "Creating 'market' service user..."
  useradd -m -s /bin/bash market
  usermod -aG docker market
else
  echo "User 'market' already exists"
fi

# ── 4. Clone repo ──────────────────────────────────────────────────────────
if [ ! -d /home/market/app ]; then
  echo "Cloning repo..."
  su - market -c "git clone https://github.com/cutout-z/claude-code-projects.git /home/market/app"
else
  echo "Repo already cloned — pulling latest..."
  su - market -c "cd /home/market/app && git pull"
fi

# ── 5. Make scripts executable ─────────────────────────────────────────────
chmod +x /home/market/app/market-dashboard/deploy/start.sh

# ── 6. Protected secrets directory ─────────────────────────────────────────
mkdir -p /etc/market-dashboard
chmod 700 /etc/market-dashboard

# ── 7. Install systemd service ─────────────────────────────────────────────
cp /home/market/app/market-dashboard/deploy/market-dashboard.service \
   /etc/systemd/system/market-dashboard.service
systemctl daemon-reload
systemctl enable market-dashboard

# ── 8. Build Docker image ──────────────────────────────────────────────────
echo "Building Docker image..."
cd /home/market/app/market-dashboard
docker compose build

echo ""
echo "=========================================================="
echo "  Setup complete. One manual step remains:"
echo "=========================================================="
echo ""
echo "  STEP A — Create the server-only environment file:"
echo ""
echo "    install -d -m 700 /etc/market-dashboard"
echo "    nano /etc/market-dashboard/env"
echo ""
echo "  Put these lines in it:"
echo "    FRED_API_KEY=PASTE_FRED_KEY_HERE"
echo "    FMP_API_KEY=PASTE_FMP_KEY_HERE"
echo ""
echo "  Then protect it:"
echo "    chmod 600 /etc/market-dashboard/env"
echo "    chown root:root /etc/market-dashboard/env"
echo ""
echo "  Then start the service:"
echo "    systemctl start market-dashboard"
echo "    journalctl -u market-dashboard -f"
echo ""
echo "  Access the dashboard via SSH tunnel from your Mac:"
echo "    ssh -L 8060:localhost:8060 root@YOUR_SERVER_IP"
echo "  Then open: http://localhost:8060"
echo "=========================================================="
