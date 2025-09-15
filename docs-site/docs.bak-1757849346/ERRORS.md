# Errors

All non-2xx responses return a JSON envelope with `ok=false` and a structured `error`.

## Common error codes

- `bad_request` – Invalid parameters (e.g. start_date format)
- `unauthorized` – Missing or invalid API key
- `not_found` – Resource not found
- `rate_limited` – Too many requests
- `internal` – Unexpected server error

Example:

```bash
curl -fsS -H "X-API-Key: bad" "$API_BASE/v1/ports/USLAX/snapshot" | jq .
```
