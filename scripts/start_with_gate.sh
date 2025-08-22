#!/usr/bin/env bash
# scripts/start_with_gate.sh
set -euo pipefail

PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"
APP_CMD="uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}"

# 这些参数传给 health_gate.sh
SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # 服务器侧阈值（更严格）
PASS_COUNT="${PASS_COUNT:-3}"             # 需连续通过的次数
MAX_TRIES="${MAX_TRIES:-60}"              # 最多尝试次数
SLEEP_SECS="${SLEEP_SECS:-2}"

echo "▶️ Starting app in background: ${APP_CMD}"
${APP_CMD} &
APP_PID=$!

# 粗略探活：给应用一点启动时间（最多等 30s）
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "⛳ Run health gate against http://127.0.0.1:${PORT}"
if BASE_URL="http://127.0.0.1:${PORT}" \
     SLOW_SERVER_MS="${SLOW_SERVER_MS}" \
     PASS_COUNT="${PASS_COUNT}" \
     MAX_TRIES="${MAX_TRIES}" \
     SLEEP_SECS="${SLEEP_SECS}" \
     bash /app/scripts/health_gate.sh
then
  echo "✅ Gate passed, keeping app running (pid=${APP_PID})"
  wait "${APP_PID}"
else
  echo "❌ Health gate failed; stopping app (pid=${APP_PID})..."
  kill -TERM "${APP_PID}" || true
  sleep 2
  kill -KILL "${APP_PID}" || true
  exit 1
fi