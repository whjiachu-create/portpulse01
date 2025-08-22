#!/usr/bin/env bash
# scripts/start_with_gate.sh  (safe warmup, never kill app)
set -euo pipefail

PORT="${PORT:-8080}"
BASE_URL="http://127.0.0.1:${PORT}"

echo "▶️ Launching app on ${BASE_URL} ..."
# 先把 Uvicorn 跑起来（后台）
uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 &
APP_PID=$!
sleep 1

echo "⛳ Warmup against ${BASE_URL} (server<${SLOW_SERVER_MS:-300}ms, ${PASS_COUNT:-1} pass)"
# 仅用于预热；失败也不退出进程
BASE_URL="${BASE_URL}" PASS_COUNT="${PASS_COUNT:-1}" MAX_TRIES="${MAX_TRIES:-30}" SLEEP_SECS="${SLEEP_SECS:-2}" \
  bash /app/scripts/health_gate.sh || echo "⚠️ Warmup failed; continue serving..."

# 以前台方式“守住”应用
wait "${APP_PID}"