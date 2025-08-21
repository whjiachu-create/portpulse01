#!/usr/bin/env bash
# scripts/notify_ops.sh  —— 无 jq 版
# 用法：
#   STATUS=GREEN TITLE="PortPulse selfcheck" LOG_FILE=./selfcheck.out \
#   SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
#   bash scripts/notify_ops.sh

set -euo pipefail
: "${SLACK_WEBHOOK_URL:?SLACK_WEBHOOK_URL not set}"

STATUS="${STATUS:-INFO}"
TITLE="${TITLE:-PortPulse notification}"
LOG_FILE="${LOG_FILE:-}"

# 用 Python 可靠地转义成 JSON
payload="$(python3 - <<'PY'
import json, os, sys, pathlib
title = os.environ.get("TITLE", "PortPulse")
status = os.environ.get("STATUS", "INFO")
log_file = os.environ.get("LOG_FILE", "")
tail = ""
if log_file and pathlib.Path(log_file).exists():
    with open(log_file, "r", errors="ignore") as f:
        lines = f.readlines()[-40:]  # 只取最后 40 行
        tail = "".join(lines)
text = f"*{title}*\nstatus: {status}\n```{tail}```"
print(json.dumps({"text": text}))
PY
)"

curl -fsS -X POST -H "Content-Type: application/json" \
  --data "$payload" "$SLACK_WEBHOOK_URL" \
  >/dev/null && echo "Slack notified."