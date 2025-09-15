---
id: endpoints
title: Endpoints Overview (/v1)
sidebar_label: Endpoints
---

- `GET /v1/health`
- `GET /v1/meta/sources`
- `GET /v1/ports/{UNLOCODE}/overview`
- `GET /v1/ports/{UNLOCODE}/trend`
- `GET /v1/ports/{UNLOCODE}/snapshot`
- `GET /v1/ports/{UNLOCODE}/dwell`
- `GET /v1/ports/{UNLOCODE}/alerts`
- `GET /v1/hs/{code}/imports` (beta)

> Contracts are frozen under `/v1`. Breaking changes ship only under `/v1beta` with ≥90 days deprecation.

---
id: endpoints
title: Endpoints Overview (/v1)
sidebar_label: Endpoints
---

> This page lists all **stable `/v1`** endpoints, shared query parameters, and copy‑pasteable examples.  
> **Contracts under `/v1` are frozen**. Any breaking change only ships behind `/v1beta` with **≥90‑day deprecation**.

## Base URL & Auth

- **Base**: `https://api.useportpulse.com`
- **Auth**: `X-API-Key: <YOUR_KEY>`
- **Formats**: `?format=json` (default) or `?format=csv`
- **Headers you will see**
  - `Cache-Control: public, max-age=300`
  - `ETag` (for CSV responses; strong ETag)
  - `x-request-id` (include this when contacting support)

:::tip Quickstart
Run a real request now (replace `DEMO_KEY` with your key):
```bash
curl -H "X-API-Key: DEMO_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d"
```
:::

---

## Endpoint catalog

### Health & Meta
- `GET /v1/health` — Service liveness probe; returns `{status:"ok"}`
- `GET /v1/meta/sources` — Data sources & last ingestion timestamps

### Port metrics
- `GET /v1/ports/{UNLOCODE}/overview` — Latest snapshot (e.g., `vessels`, `avg_wait_hours`, `congestion_score`)
- `GET /v1/ports/{UNLOCODE}/trend` — Time series; JSON/CSV; supports **window**/**start-end**, **fields**, **limit/offset**, **tz**, **order**
- `GET /v1/ports/{UNLOCODE}/snapshot` — Point‑in‑time snapshot. Defaults to “now”; use `as_of` for a historical point
- `GET /v1/ports/{UNLOCODE}/dwell` — Waiting/berth dwell time series; **no data returns `200 []`** (not 404)
- `GET /v1/ports/{UNLOCODE}/alerts` — Threshold/percentile & change‑point alerts; includes `severity` and `explain`

### Trade (beta)
- `GET /v1/hs/{code}/imports` — Monthly import momentum by HS2/4/6; JSON/CSV; strong ETag/304

---

## Path params

- **`{UNLOCODE}`** — 5‑letter UN/LOCODE, uppercase (e.g., `USLAX`, `SGSIN`)
- **`{code}`** — HS code, length **2/4/6** (e.g., `84`, `8407`, `840734`)

## Shared query params

| Param | Type | Default | Notes |
|---|---|---|---|
| `format` | `json\|csv` | `json` | CSV enables strong `ETag`/`304` |
| `window` | `7d\|30d\|90d...` | `30d` | Rolling window for time series |
| `start` / `end` | `YYYY-MM-DD` | — | Use instead of `window` for bounded ranges |
| `fields` | comma list | all | e.g., `date,congestion_score,avg_wait_hours` |
| `limit` / `offset` | int | `100` / `0` | Pagination for long series |
| `order` | `asc\|desc` | `asc` | Time ordering |
| `tz` | IANA TZ | `UTC` | e.g., `America/Los_Angeles` |
| `as_of` | ISO date/time | now | For `/snapshot` |

---

## Responses

### Standard success (example: `/v1/ports/USLAX/trend?window=7d`)
```json
[
  {"date":"2025-08-25","congestion_score":0.42,"avg_wait_hours":17.8},
  {"date":"2025-08-26","congestion_score":0.38,"avg_wait_hours":16.1}
]
```

### Standard error body
All 4xx/5xx responses share a unified envelope:
```json
{
  "code": "rate_limit_exceeded",
  "message": "Too many requests",
  "request_id": "req_01JABCDEF...",
  "hint": "Back off and retry after the window resets"
}
```

---

## Caching & ETag (important)

- Read endpoints return `Cache-Control: public, max-age=300`.
- **CSV** responses include **strong `ETag`**. Use it to save bandwidth:
  1) `GET ...?format=csv` → read `ETag: "abc123"`  
  2) Next request: add `If-None-Match: "abc123"` → server may reply **`304 Not Modified`** with empty body.

Example:
```bash
# First fetch
curl -i -H "X-API-Key: DEMO_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=7d&format=csv"

# Conditional fetch with ETag
curl -i -H "X-API-Key: DEMO_KEY" \
  -H 'If-None-Match: "abc123"' \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=7d&format=csv"
```

---

## Rate limits

Default **~60 requests/min** (burst ×5). Headers may be present:
- `x-ratelimit-limit`
- `x-ratelimit-remaining`
- `retry-after` (when throttled)

See **[Rate Limits](/docs/rate-limits)** for details.

---

## Copy‑paste examples

### cURL — 30‑day trend (JSON)
```bash
curl -H "X-API-Key: $PORTPULSE_API_KEY" \
  "https://api.useportpulse.com/v1/ports/SGSIN/trend?window=30d&fields=date,congestion_score,avg_wait_hours"
```

### Python — CSV + ETag
```python
import requests

url = "https://api.useportpulse.com/v1/ports/USLAX/trend?window=7d&format=csv"
headers = {"X-API-Key": "YOUR_KEY"}
etag = None

r1 = requests.get(url, headers=headers)
etag = r1.headers.get("ETag")

# Conditional re-fetch
hdrs = {**headers, "If-None-Match": etag} if etag else headers
r2 = requests.get(url, headers=hdrs)
print(r2.status_code)  # 200 or 304
```

### Node (fetch) — Alerts
```js
const url = "https://api.useportpulse.com/v1/ports/USLAX/alerts";
const r = await fetch(url, { headers: { "X-API-Key": process.env.PORTPULSE_API_KEY }});
const data = await r.json(); // [{date, kind, severity, explain, ...}]
console.log(data.slice(0,3));
```

---

## See also

- **[Authentication](/docs/authentication)** — how to use `X-API-Key`
- **[Errors](/docs/errors)** — common codes & envelopes
- **[Rate Limits](/docs/rate-limits)** — throttling behavior
- **[CSV + ETag](/docs/csv-etag)** — bandwidth‑efficient fetches
- **[Field Dictionary](/docs/Guides/field-dictionary)** — definitions of metrics