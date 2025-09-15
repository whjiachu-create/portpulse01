---
id: methodology
title: Methodology (Metrics & Freshness)
sidebar_label: Methodology
description: How PortPulse defines & computes congestion, dwell/wait, trends and freshness SLO; data sources, de‑duplication, smoothing, quality controls, and reproducibility.
---

> This page documents the **calculation logic** behind PortPulse’s operational metrics and the **freshness SLO**. It is designed to be **auditable** and **reproducible**.

## What you get

- **Daily trend time series** per port (JSON/CSV)
- **Snapshot/Overview** with aggregated indicators
- **Dwell/Wait** breakdown (at‑anchor / at‑berth when available)
- **Alerts** (percentile thresholds + change‑point detection)
- **Freshness telemetry**: `as_of` and `last_updated` attached to outputs

:::tip TL;DR
- We aggregate **public/authorized sources** (port notices, movement events, AIS‑derived signals) and apply **de‑duplication + robust smoothing**.  
- **Congestion score** ∈ [0,1] is a normalized blend of queue length, average wait and terminal utilization proxies.  
- **Freshness SLO**: **p95 ≤ 2h**. 30‑day replay with no gaps on core ports.  
:::

---

## Data sources

- **Movement events:** arrivals/departures, alongside/anchor events (from public schedules, vessel traffic reports, AIS‑derived signals).
- **Port notices & bulletins:** closures, weather suspensions, labor updates.
- **Reference catalogs:** UN/LOCODE, terminal aliases, public holiday calendars.

**Access & licensing.** Only public or duly authorized datasets are used. We maintain a provenance trail per record.

---

## Ingestion & normalization

1. **Polling cadence:** hourly (burst faster during active windows).
2. **Parsing & standardization:** ISO‑8601 timestamps in **UTC**, canonical `UNLOCODE` (e.g., `USLAX`), consistent units (hours).
3. **De‑duplication:** keep **latest event of the day** per `(port, ship, event_type)`; collapse near‑duplicates within a tolerance window (e.g., ≤ 10 minutes).
4. **Outlier control:** *winsorize* extreme wait values at `[p1, p99]`, clip physically impossible durations.
5. **Gap filling:** forward‑fill short gaps ≤ 3 hours; longer gaps remain missing (not imputed).
6. **Confidence tagging:** each point carries a `confidence` ∈ {`high`,`medium`,`low`} driven by source consistency.

---

## Metrics definitions

### Average wait hours
Mean waiting time for vessels **arriving during the day**, measured from **port limits / anchor on‑scene** to **all fast/berth** (when berth signals are not available, we approximate using first alongside or departure with heuristics).

**Edge cases**
- Ballast shifts inside harbor excluded.
- Aborted calls removed (arrival without subsequent berth).
- Multi‑terminal ports: weighted by call counts.

### Queue length (proxy)
Count of vessels in **waiting state** within port’s AOR at snapshot time, filtered by commercial type (container/general cargo as applicable).

### Congestion score (0–1)
A bounded, unit‑free index combining normalized queue and wait:

```
let W = winsorized_avg_wait_hours;
let Q = queue_length_per_capacity;           # queue divided by rolling capacity proxy
let Z = 0.5 * zscore(W) + 0.5 * zscore(Q);   # standardized blend
# squash to [0,1]
congestion_score = sigmoid(Z)                # 1 / (1 + e^-Z)
```

**Notes**
- Capacity proxy derives from a rolling baseline of weekly handled calls.
- We also publish **raw components** where available.

---

## Trend & snapshot generation

We emit **one daily point per port** (UTC end‑of‑day), plus an intra‑day **snapshot**:

```text
for each port, hourly:
  fetch latest events + notices
  clean + dedupe + winsorize + fill short gaps
  compute wait/queue + congestion_score
  write snapshot {as_of, last_updated}
end

for each port, daily (UTC 23:59):
  aggregate daily metrics
  append to trend series (30d+ retention)
  publish CSV/JSON (ETag, Cache-Control)
end
```

- `as_of`: timestamp the metric represents.  
- `last_updated`: ETL completion time for that record.

---

## Freshness SLO & monitoring

- **SLO:** p95 of `(now - last_updated)` ≤ **2 hours** per port.
- **Dashboards:** freshness percentiles `p50/p95/max` tracked by port and region.
- **Alerting:** breach at `p95 &gt; 2h` for > 2 consecutive hours triggers incident.
- **Backfill policy:** missed windows retried automatically; next‑day backfill if needed (records keep original `as_of`).

See also: [SLA &amp; Status](/docs/Ops/sla-status).

---

## Quality controls

- **Schema checks:** required fields present, units consistent.
- **Statistical guards:** day‑to‑day delta bounds; structural break detection.
- **Replay audits:** 30‑day series must be **gapless** on core ports before release.
- **Manual review hooks:** anomalies with `confidence=low` surface to triage.

---

## Reproducibility & auditing

- **OpenAPI** describes every field and shape: `/openapi` (Redoc).  
- **CSV parity:** every trend endpoint supports `?format=csv`.  
- **Caching:** `Cache-Control: public, max-age=300` + strong `ETag` on CSV for `304` support ([CSV &amp; ETag](/docs/csv-etag)).  
- **Traceability:** each response carries `x-request-id`; errors use the unified body ([Errors](/docs/Guides/errors)).

Quick check (cURL):

```bash
curl -H "X-API-Key: DEMO_KEY" \
  "https://api.useportpulse.com/v1/ports/USLAX/trend?window=30d&amp;format=csv" \
  -i
```

---

## Limitations & caveats

- Some ports do **not** publish berth events; we approximate with robust heuristics.
- Extreme weather / labor events can distort baselines; we mark such windows.
- AIS coverage variance can affect queue detection; confidence will reflect sources.

---

## Changelog & versioning

- **Contract:** `/v1` is frozen for P1; breaking changes go to `/v1beta`.
- **Deprecation window:** ≥ **90 days**; changes announced on [/docs/changelog](/docs/changelog) and [Versioning](/docs/Guides/versioning).

---

## Field reference

See the curated **[Field Dictionary](/docs/Guides/field-dictionary)** for types, units, and nullability.

```
