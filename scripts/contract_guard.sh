#!/usr/bin/env bash
set -euo pipefail

# ---- prepare env (CI 内可独立运行) ----
python3 -m venv .guardvenv
source .guardvenv/bin/activate
pip install -q -r requirements.txt
# jq 交给 workflow 装；若本地手动跑可取消下一行注释
# sudo apt-get update -y && sudo apt-get install -y jq

BASE="http://127.0.0.1:8080"

# ---- start uvicorn ----
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 >/tmp/uv.log 2>&1 & PID=$!
trap 'kill $PID 2>/dev/null || true; deactivate || true' EXIT

# 等待 /v1/sources 就绪（若 HEAD/GET 任一 200 即通过）
ok=0
for i in {1..60}; do
  sc=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/v1/sources" || true)
  [ "$sc" = "200" ] && ok=1 && break
  sc=$(curl -sI -o /dev/null -w '%{http_code}' "$BASE/v1/sources" || true)
  [ "$sc" = "200" ] && ok=1 && break
  sleep 0.5
done
[ "$ok" -eq 1 ] || { echo "[boot failed]"; sed -n '1,120p' /tmp/uv.log; exit 1; }

# ---- dump OpenAPI 并做强校验 ----
curl -sS "$BASE/openapi.json" > /tmp/openapi.json

# 必达路径（P0）
need=(
  "/v1/sources"
  "/v1/ports/{unlocode}/trend"
  "/v1/ports/{unlocode}/dwell"
  "/v1/ports/{unlocode}/snapshot"
)

miss=0
for p in "${need[@]}"; do
  if ! jq -e --arg k "$p" '.paths|has($k)' /tmp/openapi.json >/dev/null; then
    echo "Missing path in OpenAPI: $p"
    miss=1
  fi
done

# 额外打印诊断，便于定位
echo "---- OpenAPI paths (top 20) ----"
jq -r '.paths|keys[]' /tmp/openapi.json | head -20

[ "$miss" -eq 0 ] && echo "Guard OK: all required paths present."
exit "$miss"
