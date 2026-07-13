#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
OPEN_BROWSER="${OPEN_BROWSER:-true}"

PIDS=""

cleanup() {
  for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup INT TERM EXIT

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed, so the frontend cannot be started."
  echo "Backend and MCP will still start."
fi

cd "$ROOT_DIR"

"$ROOT_DIR/.venv/bin/python" -m uvicorn src.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
PIDS="$PIDS $!"

"$ROOT_DIR/.venv/bin/python" -m src.mcp.server &
PIDS="$PIDS $!"

if command -v npm >/dev/null 2>&1; then
  (
    cd "$ROOT_DIR/frontend"
    npm run dev:ui -- --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT"
  ) &
  PIDS="$PIDS $!"
fi

if [ "$OPEN_BROWSER" = "true" ] && command -v open >/dev/null 2>&1; then
  (
    i=0
    while [ "$i" -lt 60 ]; do
      if nc -z "$FRONTEND_HOST" "$FRONTEND_PORT" >/dev/null 2>&1; then
        open "http://$FRONTEND_HOST:$FRONTEND_PORT"
        exit 0
      fi
      i=$((i + 1))
      sleep 1
    done
    exit 0
  ) &
fi

echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "MCP:      running in the same launcher session"

wait
