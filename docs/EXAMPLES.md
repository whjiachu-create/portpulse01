# Quickstart

Base URL: `https://api.useportpulse.com`  
Demo API Key: `dev_demo_123`（放在请求头 `X-API-Key`）

## cURL

```bash
BASE="https://api.useportpulse.com"

# 1) 健康检查（无需鉴权）
curl -sS "$BASE/v1/health" | jq .

# 2) USLAX 最近 7 天 JSON（需要 API Key）
curl -sS -H "X-API-Key: dev_demo_123" \
  "$BASE/v1/ports/USLAX/trend?days=7" | jq .

# 3) USLAX 最近 7 天 CSV + ETag/304 验证
ET=$(curl -fsS -D - -H "X-API-Key: dev_demo_123" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o /dev/null \
  | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r|\"/,"");print $2}')
curl -fsSI -H "X-API-Key: dev_demo_123" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv"
import requests, os
BASE = "https://api.useportpulse.com"
KEY  = os.getenv("PORTPULSE_API_KEY", "dev_demo_123")

r = requests.get(f"{BASE}/v1/ports/USLAX/trend",
                 params={"days": 7},
                 headers={"X-API-Key": KEY})
r.raise_for_status()
print(r.json()["points"][-3:])
const BASE="https://api.useportpulse.com";
const r = await fetch(`${BASE}/v1/ports/USLAX/trend?days=7`, {
  headers: {"X-API-Key":"dev_demo_123"}
});
console.log(await r.json());
