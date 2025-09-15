---
id: versioning
title: Versioning & Deprecations
sidebar_label: Versioning
description: How PortPulse versions its API and communicates deprecations, with concrete timelines and headers.
---

PortPulse uses **path-based versioning** with stability guarantees.

## Version Tiers

- **Stable**: `/v1` — the schema is **frozen** for backwards compatibility. Additive changes only (new optional fields/endpoints).
- **Preview**: `/v1beta` — for breaking or experimental changes. Expect iteration and feedback cycles.

## What counts as breaking?

Breaking changes include: removing fields, renaming fields or enums, changing required → optional, altering types, or changing semantics. **Adding an optional field** is **not** breaking.

## Deprecation Policy

We follow [RFC 8594](https://www.rfc-editor.org/rfc/rfc8594) style signals:

- Header: `Deprecation: true`
- Header: `Sunset: 2026-01-15`
- Header: `Link: <https://docs.useportpulse.com/docs/changelog>; rel="deprecation"`
- Changelog entry: migration notes, examples, and a minimal set of mapped cURL samples.

**Compatibility window:** deprecations are announced **≥ 90 days** before removal in stable environments.

## Client Guidance

- Generate clients from **OpenAPI** (recommended).
- Be tolerant of **unknown fields** and **enum extensions**.
- Use `x-request-id` in all support communications.

## Example: field rename flow

1. Introduce `new_field` in `/v1beta` with mapping from `old_field`.
2. Announce deprecation: `Deprecation: true`, `Sunset: +90 days`.
3. After clients switch, promote `new_field` to `/v1` (additive); freeze.
4. Remove `old_field` **after** the sunset date; record in changelog.

## Communication Channels

- **Changelog**: `/docs/changelog` (RSS/Atom available soon).
- **Status page**: incidents and scheduled maintenance.
- **Email**: opt-in advisories for Pro+ customers.

