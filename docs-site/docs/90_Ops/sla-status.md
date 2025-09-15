---
id: sla-status
title: SLA, SLOs & Status Page
sidebar_label: SLA & Status
description: Availability, latency and freshness objectives, service credits, and public status page practices.
---

This page describes **targets (SLOs)**, contractual **SLA** for Pro+, and how we communicate incidents.

## SLO Targets (Non-contractual but measured)

| Metric                     | Target                          | Notes |
|---------------------------|---------------------------------|-------|
| Availability (monthly)    | **≥ 99.9%**                     | Excludes scheduled maintenance. |
| Read latency (p95)        | **&lt; 300ms**                  | From edge cache when applicable. |
| Freshness (p95)           | **≤ 2 hours**                   | `now - as_of` on read endpoints. |
| Replay window             | **30 days**                     | Continuous, no gaps. |

## SLA (Contractual, Pro and above)

If monthly availability (UTC) falls below:

- **99.9% → 99.5%**: service credit **10%** of monthly fee  
- **&lt; 99.5%**: service credit **25%** of monthly fee

Credits are applied to the **next invoice**. SLA excludes: (a) customer-caused incidents, (b) upstream carrier/ISP failures outside our control, (c) force majeure, (d) scheduled maintenance announced ≥24h in advance on the status page.

## Measurement

- External probes run from multiple regions against `/v1/health`, `/v1/meta/sources`, and `/v1/ports/USLAX/trend`.
- Uptime is computed as **1 − outage_minutes / total_minutes** per calendar month (UTC).
- Latency SLO is calculated on **p95** across successful reads.

## Status Page

- Public: **status.useportpulse.com** (incidents, historical uptime, regional partitions).  
- All incidents have a timeline: identification → mitigation → recovery → post‑mortem (published within **5 business days**).

## Maintenance

- Standard window (if needed): **Saturdays 02:00–04:00 UTC**, announced ≥24h in advance on the status page.
- We aim for **zero‑downtime** deploys; maintenance is rare.

## Support & Escalation

- Email: **support@useportpulse.com**  
- Include **`x-request-id`**, UTC timestamp, endpoint, query string, and minimal `curl` reproduction.

## Security & Privacy

- API Keys are prefixed (`pp_dev_*`, `pp_live_*`), least privilege.  
- GDPR/CCPA friendly by design; we avoid personal data.  
- Audit: structured logs with `request_id`; data retention aligned with legal requirements.

