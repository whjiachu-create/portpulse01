# Data Sourcing & Phased Rollout

**Principle**: *AIS-first (compute our own metrics), product APIs for calibration and content.*

## Phase 0 (now–4 weeks) — Ship the minimum lovable product
- Pick **one AIS** provider (VT Explorer or Datalastic) for broad coverage.
- Calibrate weekly with **Port of LA Signal / Control Tower** and **PortXchange** (EU).
- Add **U.S. Census** port+HS imports (free) for trade momentum endpoints.
- Cache everything behind **ETag/304 + edge**; keep supplier API usage in ETL, not in public APIs.

## Phase 1 (month 2–3) — Quality ceiling
- Add **Spire Port Events** on a small **hi-confidence port list** (USLAX, USNYC, SGSIN, GBFXT).
- Publish the **congestion scoring spec** (quantiles, denoise, backfill).
- Add weather factors (NOAA PORTS, Copernicus) to explain anomalies (Pro+).

## Phase 2 (month 4–9) — Redundancy & expansion
- Introduce a **second AIS** source for A/B and failover.
- Grow to **150–200 ports**; expand HS imports coverage.

## Phase 3 (month 10–18) — Enterprise features
- Enterprise plan: dedicated instance, data residency, stricter SLA, whitelisting.
- Consider higher-density satellite AIS if customers need minute-level refresh.

**Why this works**: fast to launch, retains reproducibility/IP, and keeps gross margin healthy.
