# Error Codes

| http_status | code        | message                  | hint                          |
|---:|---|---|---|
| 401 | auth_required | API key missing/invalid     | Set header `X-API-Key`        |
| 403 | rate_limited  | Too many requests           | Respect `Retry-After`         |
| 404 | not_found     | Resource not found          | Check UN/LOCODE and params    |
| 422 | invalid_param | Validation failed           | See error details             |
| 500 | http_500      | Internal Server Error       | Contact support with request_id |
