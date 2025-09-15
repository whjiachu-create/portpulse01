---
id: rate-limits
title: Rate Limits
sidebar_label: Rate limits
---

Default: **~60 rpm** per key with burst tolerance ×5.  
Contact us for higher limits on paid plans. `429` responses include `Retry-After`.

---
id: rate-limits
title: Rate limits
sidebar_label: Rate limits
description: How PortPulse enforces per‑key rate limits, burst behavior, returned headers, 429 semantics, and recommended client backoff.
---

> **TL;DR**
>
> - **Default**: ~**60 requests/minute** per API key, with **×5 burst tolerance**.  
> - **429** responses include a **`Retry-After`** header (seconds).  
> - Need more? **Contact us** to raise limits on paid plans.

---

## What is rate limiting?

To keep the service stable for everyone, PortPulse applies **per‑key** limits using a token‑bucket style controller on a **rolling 60‑second window**. You can send short bursts above the base rate, up to **5×** for brief periods; after that you’ll receive **HTTP `429 Too Many Requests`** until tokens refill.

### Scope

- **Per API key**, across all read endpoints.  
- **Write endpoints** (if/when available) may have stricter limits.  
- **Anonymous** calls (if enabled) have significantly lower limits.

---

## Headers we return

Successful responses generally include **informational headers** to help you pace requests:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 12
X-RateLimit-Reset: 1726310400
x-request-id: 4b4f5c8a-3d0d-4b01-9a3d-3d6f9b3d9a21
```

On throttle, you’ll get:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 23
Content-Type: application/json
x-request-id: d3b2c2a1-0dd1-4b8e-9c3a-0fbf3d2b9e0a
```

**Body (unified error format):**
```json
{
  "code": "RATE_LIMITED",
  "message": "Too many requests. Please retry later.",
  "request_id": "d3b2c2a1-0dd1-4b8e-9c3a-0fbf3d2b9e0a",
  "hint": "Honor the Retry-After header or back off with jitter."
}
```

> **Notes**
>
> - `X-RateLimit-Reset` is a **Unix timestamp (seconds)** indicating when the window fully refills.  
> - Always log `x-request-id` when you need to contact support.

---

## Recommended backoff

We strongly recommend **exponential backoff with jitter**. Below are minimal, copy‑pasteable examples.

### Python (requests)
```python
import time, random, requests

API_KEY = "YOUR_KEY"
URL = "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d"

def get_with_backoff(max_retries=5, base=0.5, cap=8.0):
    for attempt in range(max_retries):
        r = requests.get(URL, headers={"X-API-Key": API_KEY}, timeout=15)
        if r.status_code != 429:
            return r
        retry_after = float(r.headers.get("Retry-After", 0)) or min(cap, base * (2 ** attempt))
        # Add full jitter: sleep a random amount up to retry_after
        sleep_s = random.uniform(0, retry_after)
        time.sleep(sleep_s)
    raise RuntimeError("Exceeded max retries after throttling.")

resp = get_with_backoff()
print(resp.status_code, len(resp.content))
```

### Node.js (fetch)
```js
const fetch = (...args) => import('node-fetch').then(({default: f}) => f(...args));

const API_KEY = "YOUR_KEY";
const URL = "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d";

async function getWithBackoff(maxRetries = 5, base = 500, cap = 8000) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const res = await fetch(URL, { headers: { "X-API-Key": API_KEY }});
    if (res.status !== 429) return res;

    const retryAfter = Number(res.headers.get("retry-after")) * 1000;
    const backoffMs = Number.isFinite(retryAfter) && retryAfter > 0
      ? retryAfter
      : Math.min(cap, base * (2 ** attempt));
    const jitterMs = Math.random() * backoffMs;
    await new Promise(r => setTimeout(r, jitterMs));
  }
  throw new Error("Exceeded max retries after throttling.");
}

getWithBackoff().then(async r => {
  console.log(r.status, (await r.text()).length);
});
```

---

## Examples

### cURL
```bash
curl -H "X-API-Key: YOUR_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=json"
```

### Respect 304 + caching to save quota
If you consume **CSV**, pair calls with **ETag/If-None-Match** (see **CSV & ETag** page) to get **`304 Not Modified`** responses and **save rate‑limit tokens**.

```bash
# First request
curl -i -H "X-API-Key: YOUR_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?format=csv" -o trend.csv
# Suppose response included: ETag: "W/\"abc123\""
# Conditional request using the ETag:
curl -i -H "X-API-Key: YOUR_KEY" \
     -H 'If-None-Match: W/"abc123"' \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?format=csv"
# Expect: 304 Not Modified (no body, minimal cost)
```

---

## FAQs

**Is the limit per endpoint or global?**  
Global per key (read endpoints). Heavy endpoints may be tuned separately in the future.

**What counts toward the limit?**  
Every HTTP request that reaches our edge (including `304` responses). Connection retries/timeouts also count if the request is received.

**Do web caches affect my quota?**  
Yes—**edge cache hits still count** as requests for fairness, but they’re much faster and cheaper on our side.

**Can you raise my limit?**  
Absolutely. Paid plans can request higher limits. Please include your **use case**, **expected RPM**, and your **account email**.

---

## Best practices checklist

- ✅ Reuse HTTP connections (keep‑alive).  
- ✅ Batch requests where possible; avoid high‑cardinality poll loops.  
- ✅ Respect `Retry-After` and implement exponential backoff with jitter.  
- ✅ Use **ETag/If-None-Match** for CSV to get `304`.  
- ✅ Log and pass along `x-request-id` when opening a support ticket.

---