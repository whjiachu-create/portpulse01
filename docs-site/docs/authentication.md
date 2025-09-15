---
id: authentication
title: Authentication
sidebar_label: Authentication
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Authenticate every request with an **API key** via the HTTP header:

```http
X-API-Key: <YOUR_KEY>
```

**Key format**

- Development keys start with `pp_dev_…`
- Production keys start with `pp_live_…`
- Keys are long‑lived secrets. Treat them like passwords.

> Tip: Track the response header **`x-request-id`** in your logs/support tickets so we can quickly trace any issue.

---

## Quick check

Use your key against the public health endpoint:

<Tabs>
  <TabItem value="curl" label="cURL" default>

```bash
curl -s \
  -H "X-API-Key: $PORTPULSE_API_KEY" \
  https://api.useportpulse.com/v1/health
```

  </TabItem>
  <TabItem value="python" label="Python">

```python
import os, requests
API_KEY = os.getenv("PORTPULSE_API_KEY", "DEMO_KEY")
r = requests.get(
    "https://api.useportpulse.com/v1/health",
    headers={"X-API-Key": API_KEY}, timeout=15
)
print(r.status_code, r.json())
print("x-request-id:", r.headers.get("x-request-id"))
```

  </TabItem>
  <TabItem value="js" label="JavaScript (fetch)">

```js
const API_KEY = process.env.PORTPULSE_API_KEY || "DEMO_KEY";
const res = await fetch("https://api.useportpulse.com/v1/health", {
  headers: { "X-API-Key": API_KEY },
});
console.log(res.status, await res.json());
console.log("x-request-id:", res.headers.get("x-request-id"));
```

  </TabItem>
</Tabs>

---

## Using environment variables

Store your key in an **environment variable** instead of hardcoding it.

```bash
# macOS/Linux (temporary for the current shell)
export PORTPULSE_API_KEY="pp_live_xxxxxxxxxxxxx"

# or use a .env file with a loader (dotenv, python-dotenv, etc.)
```

In CI or serverless platforms, set `PORTPULSE_API_KEY` in the project’s secret settings.

---

## Common errors

| Status | Meaning | Typical cause | How to fix |
|-------:|---------|---------------|------------|
| **401** | Unauthorized | Missing header or malformed key | Send `X-API-Key` and verify the value/prefix |
| **403** | Forbidden | Key disabled or plan lacks access | Rotate/enable key; upgrade plan if endpoint is restricted |
| **429** | Too Many Requests | You were rate‑limited | See [Rate limits](./rate-limits); respect `Retry-After` |
| **5xx** | Server error | Transient issue | Retry with jitter/backoff; share `x-request-id` with support |

Related docs: [Rate limits](./rate-limits) · [Errors](./errors)

---

## Response headers you may see

| Header | Description |
|---|---|
| **x-request-id** | Unique id for this request – include in support tickets |
| **RateLimit-Limit** | Your current request-per-minute allotment |
| **RateLimit-Remaining** | Remaining requests in the current window |
| **RateLimit-Reset** | UTC epoch seconds when the window resets |
| **Retry-After** | Seconds to wait before retrying (sent on 429) |
| **ETag** | Strong validator for CSV endpoints – see [CSV & ETag](./csv-etag) |

---

## Security best practices

- **Do not** embed keys in frontend/mobile apps.
- Keep **separate keys** for dev (`pp_dev_*`) and prod (`pp_live_*`).
- **Rotate** immediately if leaked; contact us to revoke a compromised key.
- Restrict who can access the key in CI, servers, and notebooks.

---

## Postman / Insomnia

Use a workspace variable called `PORTPULSE_API_KEY` and set the default **Auth header**:

```http
Key: X-API-Key
Value: {{PORTPULSE_API_KEY}}
```

See guides: [Postman](./Guides/postman) · [Insomnia](./Guides/insomnia)

---

## Next steps

- Try a real dataset: 
  ```bash
  curl -H "X-API-Key: $PORTPULSE_API_KEY" \
    "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=json"
  ```
- Explore the full API in the **OpenAPI** page from the navbar.

If you hit any issue, send us the **`x-request-id`** and timestamp – we’ll trace it for you.
