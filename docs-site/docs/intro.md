---
id: intro
title: PortPulse — Introduction
sidebar_label: Intro
---

PortPulse is an **API‑first metrics service** for port congestion, dwell, snapshots, trends, alerts, and HS imports (beta). It is designed for engineers and analysts who need **reliable, auditable indicators** in **JSON or CSV** with strong caching (ETag/304).

- **Time‑to‑Value:** 5 minutes to first `200`, ~30 minutes to production.
- **Performance targets:** p95 latency &lt; 300 ms with edge caching; CSV **ETag/304** enabled.
- **Freshness target:** p95 ≤ 2 hours (per‑port freshness exposed).
- **Availability:** **99.9% SLA** on Pro tier.
- **Coverage target:** ≥ 67 ports with 30‑day replay.

> Base URL: `https://api.useportpulse.com`  
> Contracted version: **/v1** (breaking changes go to **/v1beta** with ≥90‑day deprecation window)

---

## Authentication

All requests require your API key in the `X-API-Key` header. See [Authentication](authentication) for key formats, scopes, and rotation tips.

```http
X-API-Key: DEMO_KEY
```

---

## Quickstart

### cURL

```bash
curl -sS "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d" \
  -H "X-API-Key: DEMO_KEY" \
  -H "Accept: application/json"
```

### Python

```python
import requests
res = requests.get(
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d",
  headers={"X-API-Key": "DEMO_KEY"}
)
res.raise_for_status()
print(res.json()[:3])  # first 3 points
```

### Node.js (fetch)

```js
const res = await fetch(
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d",
  { headers: { "X-API-Key": process.env.PORTPULSE_KEY } }
);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
console.log(data.slice(0, 3));
```

---

## CSV + ETag/304

Add `format=csv` and leverage strong validators for bandwidth‑efficient refreshes. Full details in [CSV &amp; ETag](csv-etag).

```bash
curl -I "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&amp;format=csv" \
  -H "X-API-Key: DEMO_KEY"
# ETag: "a1b2c3..."
# Cache-Control: public, max-age=300
```

---

## Rate limits

Default limits are set to keep the service fair for all tenants. See [Rate limits](rate-limits) for quotas, bursts, and backoff examples.

---

## Errors & request tracing

All error responses share a unified shape and include a `x-request-id` for support. See [Errors](errors) for catalog and diagnostics.

```json
{ "code": "not_found", "message": "Port not found", "request_id": "req_123", "hint": "Check UNLOCODE" }
```

---

## Versioning & deprecation

- **/v1** is contract‑frozen.  
- Breaking changes ship under **/v1beta** with **≥90 days** notice before migration.  
- Track releases in [Changelog](changelog) and guidance in [Guides / Versioning](Guides/versioning).

---

## SLA & status

Pro tier includes a **99.9% SLA** with public status and external probes. See [SLA &amp; Status page](Ops/sla-status) for scope, credits, and real‑time availability.

---

## What’s next?

- Read the [Endpoints overview](endpoints) and try the **live** [OpenAPI Reference](/openapi).
- Follow the end‑to‑end [Quickstarts](Guides/quickstarts).
- Review the [Field dictionary](Guides/field-dictionary) and [Methodology](methodology).
- Import our hands‑on collections for [Postman](Guides/postman) and [Insomnia](Guides/insomnia).
- Explore examples in [Examples](examples).

---

## Support

- Email: support@useportpulse.com  
- Include your `x-request-id` and endpoint path when reporting issues.
