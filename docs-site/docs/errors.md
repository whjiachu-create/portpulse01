id: errors
title: Errors & Conventions
sidebar_label: Errors
description: How PortPulse returns errors, how to debug issues quickly, and what to expect from headers & rate limits.
---

# Overview

All PortPulse API errors share a **uniform JSON envelope**. This makes client handling predictable across endpoints.

```json
{
  "code": "string",
  "message": "string",
  "request_id": "uuid",
  "hint": "string"
}
```

We guarantee:

- **Accurate HTTP status codes** (4xx for client issues, 5xx for server issues).
- A unique **`x-request-id`** on every response (success or error) to help support trace your call.
- Clear **rate-limit semantics** via `429 Too Many Requests` and standard headers.
- **No HTML error pages**—always machine-readable JSON.

:::tip TL;DR
Log `status`, `code`, `message`, and the `x-request-id` header. When contacting support, include the `request_id` (from body) **and** `x-request-id` (from headers).
:::

---

## Response headers you should capture

| Header | Example | Purpose |
|---|---|---|
| `x-request-id` | `req_01JABCDE...` | Unique ID for tracing a single request across services. |
| `content-type` | `application/json; charset=utf-8` | Machine-readable responses. |
| `retry-after` | `15` | Present on **429** to indicate when to retry (seconds). |
| `x-ratelimit-limit` | `60` | Your steady-state requests-per-minute quota. |
| `x-ratelimit-remaining` | `42` | Remaining tokens in the current window. |
| `x-ratelimit-reset` | `1726302000` | UNIX epoch when the window resets. |

> CSV endpoints also include caching headers (e.g., `ETag`, `Cache-Control`) but they do not affect error logic.

---

## Common errors & how to fix

| HTTP | `code` | When it happens | How to resolve |
|---:|---|---|---|
| 400 | `request.bad` | Malformed query/headers/body. | Check parameter names, types, and formats in the docs. |
| 401 | `auth.unauthorized` | Missing or invalid `X-API-Key`. | Send a valid key; do not use a dashboard or browser token. |
| 403 | `auth.forbidden` | Key exists but lacks permission (e.g., trial limits). | Upgrade plan or request access to the resource. |
| 404 | `resource.not_found` | Unknown path/port/UN/LOCODE. | Verify endpoint path and resource identifiers. |
| 409 | `request.conflict` | Idempotency/state conflict. | Retry with the same idempotency key or refresh state. |
| 422 | `validation.invalid` | Parameters are well-formed but semantically invalid. | Fix specific field errors listed in `hint`. |
| 429 | `rate_limited` | Exceeded RPM or burst constraints. | Back off per `Retry-After`; implement exponential backoff + jitter. |
| 500 | `internal` | Unexpected server fault. | Retry with backoff; if persistent, send us the `x-request-id`. |
| 503 | `unavailable` | Brief outage or maintenance. | Retry after a short delay; check **Status** page. |

:::note Error body schema
The envelope is **always** `{ code, message, request_id, hint }`. Fields are lowercase with dot-separated namespaces.
:::

---

## Examples

### 401 Unauthorized

**Request**

```bash
curl -sS "https://api.useportpulse.com/v1/ports/USLAX/trend?window=7d" \
  -H "X-API-Key: INVALID_OR_MISSING"
```

**Response**

```http
HTTP/1.1 401 Unauthorized
content-type: application/json; charset=utf-8
x-request-id: req_01J9ABCXYZ

{
  "code": "auth.unauthorized",
  "message": "Missing or invalid API key.",
  "request_id": "req_01J9ABCXYZ",
  "hint": "Pass a valid X-API-Key header. See /docs/authentication."
}
```

### 429 Too Many Requests

**Request**

```bash
# 100 requests in a tight loop will trigger 429.
for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    "https://api.useportpulse.com/v1/ports/USLAX/trend?window=1d" \
    -H "X-API-Key: DEMO_KEY";
done
```

**Response (sample)**

```http
HTTP/1.1 429 Too Many Requests
content-type: application/json; charset=utf-8
x-request-id: req_01J9LMNOPS
x-ratelimit-limit: 60
x-ratelimit-remaining: 0
x-ratelimit-reset: 1726302000
retry-after: 15

{
  "code": "rate_limited",
  "message": "Request rate exceeded. Please retry later.",
  "request_id": "req_01J9LMNOPS",
  "hint": "Respect Retry-After and implement exponential backoff with jitter."
}
```

### 422 Validation error

```http
HTTP/1.1 422 Unprocessable Entity
content-type: application/json; charset=utf-8
x-request-id: req_01J9PQRSUV

{
  "code": "validation.invalid",
  "message": "Invalid parameter(s).",
  "request_id": "req_01J9PQRSUV",
  "hint": "Invalid 'window' value: accept '7d','30d','90d'."
}
```

---

## Retry policy (recommended)

- **Do not retry** 4xx except **429**. Fix the request.
- **Retry with backoff** on **5xx**/**503**/**429** only.
- Use **exponential backoff with jitter** (e.g., 1s → 2s → 4s → …, ±25% jitter).
- Honor `Retry-After` when present.

```pseudo
delay = base * 2^attempt * (1 + rand(-0.25, +0.25))
```

---

## Error code catalog

Canonical `code` values we currently emit:

- `auth.unauthorized`
- `auth.forbidden`
- `request.bad`
- `request.conflict`
- `validation.invalid`
- `resource.not_found`
- `rate_limited`
- `internal`
- `unavailable`

> New codes will be added without breaking existing ones. We will not silently change meanings.

---

## Working with Support

When emailing support, include:

1. **Endpoint & method** (e.g., `GET /v1/ports/USLAX/trend?window=30d`)
2. **Timestamp** (UTC)
3. **Your IP (optional)** if behind a NAT/proxy
4. **`x-request-id` header** and the JSON **`request_id`** field
5. The **full response body** (redact keys)

This allows us to pinpoint your failure in seconds.

---

## FAQ

**Q: Why do I see 200 OK with an empty array on `/dwell`?**  
Some ports may have no dwell data for the selected window. We return `200 []` by design; absence of data **is not** an error.

**Q: Why do I get 404 on some ports?**  
Check the UN/LOCODE spelling and whether the port is part of your plan. See the **Ports Catalog** and pricing tiers.

**Q: Can I rely on the exact `message` text?**  
Treat `code` as stable for programmatic handling; `message` and `hint` are intended for humans and may evolve.
