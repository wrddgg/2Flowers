#!/bin/bash
# 2Flowers start/restart services on server
set -e

REMOTE_DIR="/opt/2flowers"

echo "=========================================="
echo "  2Flowers start services"
echo "=========================================="

# ---------- Backend systemd service ----------
echo ""
echo "[1/3] Configure backend systemd service..."
cat > /etc/systemd/system/2flowers-backend.service <<'SERVICE_EOF'
[Unit]
Description=2Flowers Backend (FastAPI uvicorn)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/2flowers/backend
EnvironmentFile=-/opt/2flowers/backend/.env
ExecStart=/opt/2flowers/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir .
Restart=always
RestartSec=5
StandardOutput=append:/opt/2flowers/backend/logs/backend.log
StandardError=append:/opt/2flowers/backend/logs/backend.log

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable 2flowers-backend
systemctl restart 2flowers-backend
sleep 3

if systemctl is-active --quiet 2flowers-backend; then
    echo "  [OK] backend running (port 8000)"
else
    echo "  [X] backend failed to start, check: journalctl -u 2flowers-backend -n 50"
    exit 1
fi

# ---------- Frontend build ----------
echo ""
echo "[2/3] Build frontend..."
cd $REMOTE_DIR/front
npm run build 2>&1 | tail -5
if [ -d "dist" ] && [ -f "dist/index.html" ]; then
    echo "  [OK] frontend built -> dist/"
else
    echo "  [X] frontend build failed"
    exit 1
fi

# ---------- Nginx ----------
echo ""
echo "[3/3] Restart nginx..."
nginx -t
systemctl restart nginx
echo "  [OK] nginx running (port 80)"

echo ""
echo "=========================================="
echo "  All services started!"
echo "=========================================="
echo "  Frontend: http://$(curl -s ifconfig.me 2>/dev/null || echo '<server-ip>')"
echo "  Backend:  http://127.0.0.1:8000/docs"
echo ""
echo "  Backend status: systemctl status 2flowers-backend"
echo "  Backend logs:   journalctl -u 2flowers-backend -f"
echo "=========================================="
