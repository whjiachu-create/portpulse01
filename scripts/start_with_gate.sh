#!/usr/bin/env bash
# 启动应用 + 本地门禁（通过后继续运行，不通过则退出让 Railway 回滚）
set -euo pipefail

PORT="${PORT:-8000}"
APP_CMD=(uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 2 --timeout-keep-alive 15)

# 1) 先把应用启动到后台
"${APP_CMD[@]}" &
APP_PID=$!

# 2) 跑健康门禁，针对容器本地 127.0.0.1:${PORT}
export BASE_URL="http://127.0.0.1:${PORT}"
export SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # 服务端阈值（x-response-time-ms）
export PASS_COUNT="${PASS_COUNT:-3}"             # 需要连续通过次数
export MAX_TRIES="${MAX_TRIES:-120}"             # 最多尝试（默认 2 分钟，配合 SLEEP_SECS=1）
export SLEEP_SECS="${SLEEP_SECS:-1}"

bash /app/scripts/health_gate.sh || {
  echo "health gate failed; stopping app..."
  kill -TERM "${APP_PID}" || true
  wait "${APP_PID}" || true
  exit 1
}

# 3) 门禁通过后，继续等待前台进程（保持容器存活）
wait "${APP_PID}"
