---
id: examples
title: Examples
sidebar_label: Examples
description: Copy‑paste examples for PortPulse API using cURL, Python and JavaScript. Includes CSV + ETag/304 workflow and basic error handling.
---

> **Goal**: get a first **200 OK** in 5 minutes and plot a simple trend. All snippets work with a real port (e.g. `USLAX`).

:::info Prerequisites
1. Get an API key (trial or live) and set an env var:
   ```bash
   export PORTPULSE_API_KEY="DEMO_KEY"
   ```
2. See **Authentication** and **Rate limits** for details.
   
   – [/docs/authentication](./authentication)  
   – [/docs/rate-limits](./rate-limits)
:::

## 1) cURL — 30‑day congestion trend (JSON)
```bash
curl -sS \
  -H "X-API-Key: ${PORTPULSE_API_KEY}" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&fields=date,congestion_score"
```
**Sample response**
```json
[
  {"date":"2025-08-01","congestion_score":0.45},
  {"date":"2025-08-02","congestion_score":0.47}
]
```

## 2) Python — minimal plot (matplotlib)
```python
import os, requests, matplotlib.pyplot as plt
API_KEY = os.getenv("PORTPULSE_API_KEY", "DEMO_KEY")
url = "https://api.useportpulse.com/v1/ports/USLAX/trend"
params = {"window":"30d", "fields":"date,congestion_score"}
resp = requests.get(url, params=params, headers={"X-API-Key": API_KEY}, timeout=30)
resp.raise_for_status()
rows = resp.json()
xs = [r["date"] for r in rows]
ys = [r["congestion_score"] for r in rows]
plt.plot(xs, ys, marker="o")
plt.xticks(rotation=45)
plt.title("USLAX Congestion Trend (30d)")
plt.ylabel("Congestion Score")
plt.tight_layout()
plt.show()
```

## 3) JavaScript — Node 18+ (built‑in `fetch`)
```js
const API_KEY = process.env.PORTPULSE_API_KEY || "DEMO_KEY";
const url = new URL("https://api.useportpulse.com/v1/ports/USLAX/trend");
url.searchParams.set("window", "30d");
url.searchParams.set("fields", "date,congestion_score");
const res = await fetch(url, { headers: { "X-API-Key": API_KEY } });
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
console.log(data.slice(0, 3));
```
> Tip: in a project file, mark the top‑level scope as `module` or wrap in an async IIFE.

## 4) CSV download with strong ETag / 304
Use CSV for BI tools and caching. First request returns `ETag`; subsequent requests send `If-None-Match` to avoid re-downloading unchanged data.

**cURL**
```bash
# First GET (save CSV and capture ETag header)
curl -sD headers.txt \
  -H "X-API-Key: ${PORTPULSE_API_KEY}" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv" \
  -o uslax_trend.csv

ETAG=$(grep -i '^etag:' headers.txt | awk '{print $2}' | tr -d '\r')

# Second GET (server returns 304 if unchanged)
curl -s -o uslax_trend.csv \
  -H "X-API-Key: ${PORTPULSE_API_KEY}" \
  -H "If-None-Match: ${ETAG}" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv"
```

**Python**
```python
import os, requests
API_KEY = os.getenv("PORTPULSE_API_KEY", "DEMO_KEY")
url = "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv"
s = requests.Session()
r = s.get(url, headers={"X-API-Key": API_KEY}, timeout=30)
r.raise_for_status()
etag = r.headers.get("ETag")
with open("uslax_trend.csv", "wb") as f: f.write(r.content)
# Revalidate
r2 = s.get(url, headers={"X-API-Key": API_KEY, "If-None-Match": etag}, timeout=30)
print(r2.status_code)  # 304 means cached copy is still valid
```

## 5) Filtering fields & pagination
Many endpoints accept `fields`, `limit`, `offset`, `tz`.
```bash
curl -sS -H "X-API-Key: ${PORTPULSE_API_KEY}" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=90d&fields=date,congestion_score&limit=30&offset=0"
```

## 6) Error handling quick reference
- **401/403**: missing or invalid key → add `X-API-Key`.  
- **429**: rate limit → backoff + retry (see limits).  
- **5xx**: transient → retry with jitter and respect `Retry-After` when present.  

More details: [/docs/errors](./errors) · [/docs/rate-limits](./rate-limits)

## 7) What’s next
- Explore the OpenAPI at **/openapi** page.
- Try Postman or Insomnia collections: [/docs/Guides/postman](/docs/Guides/postman) · [/docs/Guides/insomnia](/docs/Guides/insomnia)
- Read methodology & field dictionary to understand metrics: [/docs/methodology](./methodology)
