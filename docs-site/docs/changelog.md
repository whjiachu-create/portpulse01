---
id: changelog
title: Changelog
sidebar_label: Changelog
description: API-first, semantic changelog. Breaking changes only ship under /v1beta with ≥90 days deprecation; /v1 contract is frozen.
---

:::tip TL;DR
We follow semantic, API‑first change management. **Breaking changes** ship only under **`/v1beta`** with a **≥90‑day** deprecation window; the **`/v1`** contract is frozen.
:::

## How we version & deprecate
See [Versioning & Deprecation](/docs/Guides/versioning) for policy, timelines, and examples.

### Change types
- **Added** – new endpoints, fields, or docs that do not break existing clients.
- **Changed** – behavior or defaults without breaking contract.
- **Deprecated** – features scheduled for removal; always with an end date.
- **Fixed** – bug fixes.
- **Removed** – things removed after a deprecation window.
- **Security** – vulnerabilities or hardening work.

---

## Unreleased
- _No entries yet_. Add items here while developing, then move them into a dated release.

---

## 2025‑09‑14
### Added
- **Docs baseline online** (Docusaurus + Redocusaurus), OpenAPI served at **`/openapi`**.
- Initial **Guides**: Authentication, Errors, Rate limits, CSV & ETag, Quickstarts, Postman, Insomnia, Field Dictionary, Methodology.
- **Ops**: SLA & Status page stub.

### Changed
- Unified sidebar & navigation; consistent look & feel across Guides/Ops.

### Upgrade notes
- No breaking changes. If you linked to old paths, prefer `/docs/Guides/*` and `/openapi`.

---

## Conventions
- One dated section per release, newest first (YYYY‑MM‑DD).
- Use the categories above. Keep entries short and user‑facing.
- Each breaking change must link to migration notes in [Versioning & Deprecation](/docs/Guides/versioning).
