#!/usr/bin/env bash
set -euo pipefail

: "${OPS_WEBHOOK_URL:?missing OPS_WEBHOOK_URL}"  # 从 Secrets 读取

TITLE="${1:-PortPulse Alert}"
TEXT="${2:-No text}"

# Slack 最简单的 Webhook 负载（飞书见下方备注）
payload=$(jq -n --arg t "$TITLE" --arg x "$TEXT" '{text: ($t + "\n" + $x)}' 2>/dev/null \
  || python3 - <<'PY'
import json,os,sys
t=os.environ.get("TITLE","PortPulse Alert")
x=os.environ.get("TEXT","No text")
print(json.dumps({"text": f"{t}\n{x}"}))
PY
)

curl -fsS -X POST -H 'Content-Type: application/json' \
  --data "$payload" "$OPS_WEBHOOK_URL" >/dev/null
echo "ops webhook notified."