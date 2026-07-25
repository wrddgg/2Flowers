#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_MODULE="${APP_MODULE:-app.main:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/uvicorn.log}"
PID_FILE="${PID_FILE:-$ROOT_DIR/uvicorn.pid}"
RUN_MODE="${RUN_MODE:-background}"
INSTALL_ONLY="${INSTALL_ONLY:-0}"
FORCE_RESTART="${FORCE_RESTART:-0}"

echo "==> 项目目录: $ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "未找到 Python 可执行文件: $PYTHON_BIN"
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "==> 创建虚拟环境"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "==> 安装依赖"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"

if [ "$INSTALL_ONLY" = "1" ]; then
  echo "==> 依赖安装完成，已跳过启动"
  exit 0
fi

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE")"
  if kill -0 "$EXISTING_PID" >/dev/null 2>&1; then
    if [ "$FORCE_RESTART" = "1" ]; then
      echo "==> 停止旧进程: $EXISTING_PID"
      kill "$EXISTING_PID"
      rm -f "$PID_FILE"
    else
      echo "检测到服务已在运行，PID=$EXISTING_PID"
      echo "如需重启，请执行: FORCE_RESTART=1 ./deploy.sh"
      exit 0
    fi
  else
    rm -f "$PID_FILE"
  fi
fi

echo "==> 启动服务 http://$HOST:$PORT"
if [ "$RUN_MODE" = "foreground" ]; then
  exec "$VENV_DIR/bin/python" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" --app-dir "$ROOT_DIR"
fi

nohup "$VENV_DIR/bin/python" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT" --app-dir "$ROOT_DIR" >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "==> 服务已后台启动"
echo "    PID: $(cat "$PID_FILE")"
echo "    日志: $LOG_FILE"
