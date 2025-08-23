#!/usr/bin/env bash
set -euo pipefail
export PORT="${PORT:-8080}"
export HOST="0.0.0.0"

UVICORN_CMD="uvicorn app.main:app --host ${HOST} --port ${PORT}"
echo "[start] ${UVICORN_CMD}"
exec ${UVICORN_CMD}
