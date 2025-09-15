# Quickstart

PortPulse is an API-first service for port congestion and dwell metrics. Endpoints are cache-friendly (strong ETag/304) and return a unified error envelope.

## Base URL

```
https://api.useportpulse.com
```

## Authentication

Every request must include your API key in the header:

```bash
-H "X-API-Key: YOUR_API_KEY"
```

## Endpoints Overview

- `GET /v1/ports/{unlocode}/trend?window=7|30&format=json|csv`
- `GET /v1/ports/{unlocode}/snapshot`
- `GET /v1/ports/{unlocode}/overview?format=csv`
- `HEAD /v1/ports/{unlocode}/trend`
- `HEAD /v1/ports/{unlocode}/overview`

### cURL examples

Fetch 30‑day JSON trend:

```bash
curl -fsS -H "X-API-Key: $API_KEY" \
  "$API_BASE/v1/ports/USLAX/trend?window=30&format=json" | jq .
```

Fetch CSV with strong ETag and conditional request:

```bash
curl -fsS -D /tmp/h.txt -o /tmp/t.csv -H "X-API-Key: $API_KEY" \
  "$API_BASE/v1/ports/USLAX/trend?window=30&format=csv" >/dev/null
ETAG=$(awk -F': ' 'BEGIN{IGNORECASE=1}/^ETag:/{gsub("\r","",$2);print $2}' /tmp/h.txt)

curl -fsSI -H "X-API-Key: $API_KEY" -H "If-None-Match: $ETAG" \
  "$API_BASE/v1/ports/USLAX/trend?window=30&format=csv"
```

### Error envelope

```json
{
  "ok": false,
  "error": {
    "code": "bad_request",
    "message": "Invalid date format. Use YYYY-MM-DD",
    "request_id": "12345abcd"
  }
}
```

### Rate limits

Reasonable per‑key limits are enforced. Please contact support for higher quotas.

