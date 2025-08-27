# Quickstart

Base URL: `https://api.useportpulse.com`  
Demo API Key: `dev_demo_123` (header: `X-API-Key`)

## cURL

```bash
BASE="https://api.useportpulse.com"

# 1) Health (no auth)
curl -sS "$BASE/v1/health" | jq .

# 2) USLAX last 7 days (JSON)
curl -sS -H "X-API-Key: dev_demo_123" \
  "$BASE/v1/ports/USLAX/trend?days=7" | jq .

# 3) USLAX CSV + ETag/304
ET=$(curl -fsS -D - -H "X-API-Key: dev_demo_123" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv" -o /dev/null \
  | awk 'BEGIN{IGNORECASE=1}/^etag:/{gsub(/\r|\"/,"");print $2}')
curl -fsSI -H "X-API-Key: dev_demo_123" -H "If-None-Match: \"$ET\"" \
  "$BASE/v1/ports/USLAX/trend?days=7&format=csv"
import requests, os
BASE="https://api.useportpulse.com"
KEY=os.getenv("PORTPULSE_API_KEY","dev_demo_123")
r=requests.get(f"{BASE}/v1/ports/USLAX/trend",params={"days":7},headers={"X-API-Key":KEY})
r.raise_for_status()
print(r.json()["points"][-3:])
const BASE="https://api.useportpulse.com";
const r=await fetch(`${BASE}/v1/ports/USLAX/trend?days=7`,{headers:{"X-API-Key":"dev_demo_123"}});
console.log(await r.json());
