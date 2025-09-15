---
id: csv-etag
title: CSV & Caching (ETag/304)
sidebar_label: CSV & ETag
---

We serve CSV with strong **ETag** so you can use conditional requests:

```http
GET /v1/ports/USLAX/trend?format=csv
ETag: "abcd1234"

GET (conditional) If-None-Match: "abcd1234"  -> 304 Not Modified
```

Also expect `Cache-Control: public, max-age=300` on read endpoints.

---
id: csv-etag
title: CSV & Caching (ETag/304)
sidebar_label: CSV & ETag
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

PortPulse serves **CSV** responses with a strong **ETag**. Pair it with `If-None-Match` to avoid re-downloading unchanged data and to get **HTTP 304 Not Modified** when the content is identical.

:::tip TL;DR
1) First GET returns `200 OK` with an `ETag` header.  
2) Cache the body + ETag locally.  
3) Next time, send `If-None-Match: <etag>` → if unchanged, server returns `304` (no body).  
Also expect `Cache-Control: public, max-age=300` on read endpoints.
:::

## Endpoints that support CSV + ETag

Most read endpoints accept a `format=csv` query parameter and return ETag-enabled CSV:

- `/v1/ports/{UNLOCODE}/trend?format=csv`
- `/v1/ports/{UNLOCODE}/snapshot?format=csv`
- `/v1/ports/{UNLOCODE}/dwell?format=csv`
- `/v1/hs/{code}/imports?format=csv` *(beta)*

> **Strong validator**: PortPulse ETags are strong validators for CSV (not weak `W/` prefixes).

## Basic flow (HTTP)

```http
# 1) First request
GET /v1/ports/USLAX/trend?window=30d&format=csv HTTP/1.1
Host: api.useportpulse.com
X-API-Key: YOUR_KEY

HTTP/1.1 200 OK
Content-Type: text/csv
Cache-Control: public, max-age=300
ETag: "4b0a5dd8c6b7c0a0"

# CSV body...
```

```http
# 2) Conditional request with If-None-Match
GET /v1/ports/USLAX/trend?window=30d&format=csv HTTP/1.1
Host: api.useportpulse.com
X-API-Key: YOUR_KEY
If-None-Match: "4b0a5dd8c6b7c0a0"

HTTP/1.1 304 Not Modified
Cache-Control: public, max-age=300
ETag: "4b0a5dd8c6b7c0a0"

# No body
```

## Client examples

<Tabs>
  <TabItem value="curl" label="cURL">

```bash
# First fetch
curl -sS -H "X-API-Key: $API_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv" \
  -D headers.txt -o trend.csv

# Extract ETag and perform a conditional GET
ETAG=$(grep -i '^ETag:' headers.txt | awk '{print $2}' | tr -d '\r')

curl -sS -H "X-API-Key: $API_KEY" \
  -H "If-None-Match: $ETAG" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv" \
  -D headers2.txt -o trend_2.csv

# If unchanged → HTTP/1.1 304 and trend_2.csv will be empty.
```

  </TabItem>
  <TabItem value="python" label="Python">

```python
import os, requests
API = "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv"
HEADERS = {"X-API-Key": os.environ.get("API_KEY", "DEMO_KEY")}

# First fetch
r = requests.get(API, headers=HEADERS)
r.raise_for_status()
open("trend.csv", "wb").write(r.content)
etag = r.headers.get("ETag")

# Conditional fetch
h2 = dict(HEADERS)
if etag:
    h2["If-None-Match"] = etag
r2 = requests.get(API, headers=h2)

if r2.status_code == 304:
    print("Not modified; use local trend.csv")
else:
    r2.raise_for_status()
    open("trend.csv", "wb").write(r2.content)
    print("Updated CSV saved with new ETag:", r2.headers.get("ETag"))
```

  </TabItem>
  <TabItem value="node" label="Node.js">

```js
import fs from 'node:fs/promises';
import fetch from 'node-fetch';

const API = 'https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&format=csv';
const HEADERS = { 'X-API-Key': process.env.API_KEY || 'DEMO_KEY' };

const r1 = await fetch(API, { headers: HEADERS });
if (!r1.ok) throw new Error(`Fetch failed: ${r1.status}`);
await fs.writeFile('trend.csv', Buffer.from(await r1.arrayBuffer()));
const etag = r1.headers.get('etag');

const r2 = await fetch(API, {
  headers: { ...HEADERS, ...(etag ? { 'If-None-Match': etag } : {}) },
});
if (r2.status === 304) {
  console.log('Not modified; keep local CSV');
} else if (r2.ok) {
  await fs.writeFile('trend.csv', Buffer.from(await r2.arrayBuffer()));
  console.log('CSV updated. New ETag:', r2.headers.get('etag'));
} else {
  throw new Error(`Fetch failed: ${r2.status}`);
}
```

  </TabItem>
</Tabs>

## Behavior & semantics

| Aspect | Value |
|---|---|
| Cache header | `Cache-Control: public, max-age=300` on read endpoints |
| Validator | **Strong** `ETag` for CSV bodies |
| Conditional requests | Send `If-None-Match: <etag>` to receive `304` if unchanged |
| Methods | `GET` fully supported; `HEAD` may be used to probe headers (optional) |
| Scope of ETag | Calculated from the **exact CSV bytes** of the response |
| Change conditions | Data update, parameter change (e.g., `window`, `fields`), or bugfix that alters output order/format |

:::info Tip for schedulers
When polling, keep your last ETag and use `If-None-Match`. Only parse CSV when you get `200`. This reduces bandwidth and rate-limit usage.
:::

## Gotchas

- ETag is **per URL**. Any change to query params (like `window=7d` → `30d`, `fields=...`) yields a different ETag.
- Some proxies normalize headers. Always read the `ETag` value from the actual response you received.
- If you see a `412 Precondition Failed`, double-check the header name/value quoting.
- Clients must handle both `200` and `304` paths; do not assume one or the other.

## FAQ

**Is ETag stable across regions?**  
Yes—ETag represents the bytes of the CSV payload and is consistent across PoPs for the same response.

**Why 300s (5 minutes) max-age?**  
It balances freshness and cache efficiency for most operational dashboards. Use conditional requests for tighter polling.

**Do JSON endpoints also have ETag?**  
JSON endpoints may include cache validators, but the strong ETag guarantee primarily targets CSV downloads.

## See also

- [Rate limits](./Guides/rate-limits)
- [Errors & error codes](./Guides/errors)
- [Quickstarts](./Guides/quickstarts)