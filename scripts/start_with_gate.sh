#!/usr/bin/env bash
# scripts/start_with_gate.sh
# 作用：启动 uvicorn -> 本机健康门禁 -> 通过则常驻，失败则退出1

set -euo pipefail

PORT="${PORT:-8000}"
BASE_URL_LOCAL="http://127.0.0.1:${PORT}"

# 1) 后台启动 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 2 --timeout-keep-alive 15 &
APP_PID=$!

# 2) 配置并运行健康门禁（对本机回环地址做检查，跳过 CDN/网络抖动）
export BASE_URL="${BASE_URL_LOCAL}"
export SLOW_SERVER_MS="${SLOW_SERVER_MS:-300}"   # x-response-time-ms 门槛
export PASS_COUNT="${PASS_COUNT:-3}"             # 连续通过次数
export MAX_TRIES="${MAX_TRIES:-60}"              # 最大重试
export SLEEP_SECS="${SLEEP_SECS:-2}"

if /app/scripts/health_gate.sh; then
  echo "Health gate passed. Keeping server running (pid=${APP_PID})"
  # 3) 健康通过，阻塞等待 uvicorn（容器主进程保持存活）
  wait "${APP_PID}"
else
  echo "Health gate FAILED. Killing server (pid=${APP_PID})"
  kill -TERM "${APP_PID}" || true
  wait "${APP_PID}" || true
  exit 1
fi