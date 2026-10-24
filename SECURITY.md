# QueryMind Security Notes

## API keys and roles

The `POST /query` endpoint requires an `X-API-Key` header. The server maps configured keys to roles; a caller-supplied JSON `role` is not an authorization source.

- `QUERYMIND_VIEWER_API_KEY`: viewer
- `QUERYMIND_ANALYST_API_KEY`: analyst
- `QUERYMIND_ADMIN_API_KEY`: admin
- `QUERYMIND_API_KEY`: viewer-only fallback

Use long random secrets, store them in deployment environment settings, and rotate them if exposed. Never commit `.env` files or real keys. If no key is configured, the query endpoint fails closed with HTTP 503.

## SQL execution

QueryMind opens the SQLite database in read-only URI mode and uses a deny-by-default SQLite authorizer. Only SELECT-related read, function, and recursive-query actions are allowed. Existing column-level role governance remains in effect. Multi-statement execution is rejected by SQLite's `execute` API.

The application also applies a query timeout and result row cap. These safeguards reduce risk but do not replace a production database account with least-privilege grants, resource quotas, monitoring, and review of generated SQL.

## Rate limiting and deployment

The included limiter is in-process and therefore applies per application worker. For multiple workers or replicas, replace it with a shared store (for example Redis) at the gateway or application layer. Deploy behind HTTPS, configure secrets in the hosting provider, and avoid exposing raw database errors or sensitive audit fields to clients.

## Reporting

Do not publish API keys, customer data, database files containing sensitive data, or unredacted audit logs. Report security issues privately to the repository maintainer.
