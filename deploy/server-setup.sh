#!/bin/bash
# 2Flowers remote environment setup (run once on server)
set -e

REMOTE_DIR="/opt/2flowers"

echo "=========================================="
echo "  2Flowers remote environment setup"
echo "=========================================="

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"; exit 1
fi
echo "OS: $OS"

# Install dependencies
echo ""
echo "[1/5] Install system dependencies..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update -y
    apt-get install -y python3.11 python3.11-venv python3-pip nginx curl
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "alinux" ]; then
    yum install -y python3.11 python3.11-pip nginx curl || {
        yum install -y python3 python3-pip nginx curl
    }
else
    echo "Unsupported OS: $OS"; exit 1
fi
echo "  [OK] system deps"

# Install Node.js 22
echo ""
echo "[2/5] Install Node.js 22..."
if ! command -v node &> /dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
    curl -fsSL https://rpm.nodesource.com/setup_22.x | bash - 2>/dev/null || \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        apt-get install -y nodejs
    else
        yum install -y nodejs
    fi
fi
echo "  [OK] Node.js $(node -v), npm $(npm -v)"

# Python venv + backend deps
echo ""
echo "[3/5] Setup Python venv and backend dependencies..."
cd $REMOTE_DIR/backend
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv || python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  [OK] backend deps installed"

# Create runtime dirs
mkdir -p $REMOTE_DIR/backend/uploads/generated
mkdir -p $REMOTE_DIR/backend/uploads/results
mkdir -p $REMOTE_DIR/backend/logs
echo "  [OK] runtime dirs created"

# Frontend deps
echo ""
echo "[4/5] Install frontend dependencies..."
cd $REMOTE_DIR/front
npm install --no-audit --no-fund 2>&1 | tail -3
echo "  [OK] frontend deps installed"

# Nginx config
echo ""
echo "[5/5] Configure nginx..."
cat > /etc/nginx/conf.d/2flowers.conf <<'NGINX_EOF'
server {
    listen 80;
    server_name _;

    # Gzip
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # 2Flowers app under /2flowers sub-path
    # Backend API proxy (strip /2flowers prefix)
    location /2flowers/api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Backend returns absolute paths like /uploads/... and /library/...
    # Proxy them at root level (old flower-tutorial service is stopped, no conflict)
    location /uploads/ {
        proxy_pass http://127.0.0.1:8000/uploads/;
        proxy_set_header Host $host;
        proxy_read_timeout 120s;
    }

    location /library/ {
        proxy_pass http://127.0.0.1:8000/library/;
        proxy_set_header Host $host;
    }

    # Frontend static + SPA fallback
    location /2flowers/ {
        alias /opt/2flowers/front/dist/;
        index index.html;
        try_files $uri $uri/ /2flowers/index.html;
    }

    # Redirect root to app
    location = / {
        return 302 /2flowers/;
    }
}
NGINX_EOF

# Remove default config if exists
rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

nginx -t
systemctl enable nginx
echo "  [OK] nginx configured"

echo ""
echo "=========================================="
echo "  Environment setup complete!"
echo "=========================================="
