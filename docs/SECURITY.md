# Security — TasteOS

## Secrets

- Qloo API keys stay **server-side only** (`QLOO_API_KEY`). Never use `NEXT_PUBLIC_*` for secrets.
- `.env` / `apps/api/.env` / `apps/web/.env.local` are gitignored. Ship `.env.example` with empty placeholders.
- Optional `TASTEOS_API_KEY` protects mutating profile endpoints via `X-TasteOS-Key` when set.
- **Do not paste** `docker compose config` output into chats/tickets — it can interpolate secret values into stdout. Prefer `docker compose config --quiet` for syntax checks.
- After accidental exposure in logs, **rotate** the hackathon Qloo key.

## Transport and CORS

- Production should serve HTTPS for both frontend and API.
- CORS allowlist is explicit: `FRONTEND_URL`, optional comma-separated `CORS_ORIGINS`, plus localhost in development.
- Allowed request headers: `Content-Type`, `Accept`, `X-TasteOS-Key`, `X-Requested-With`.

## Input and abuse controls

- Pydantic validation on all request bodies.
- ~1 MB request body limit middleware (`payload_too_large`).
- SlowAPI rate limiting (default 60/minute/IP).
- SQLAlchemy parameterized queries (no raw SQL string concatenation).

## Privacy

- Demo uses anonymous sample profiles (nickname only).
- No scraping of Spotify/Letterboxd or similar.
- Profile deletion removes the stored row.
- Do not infer sensitive attributes (health, religion, politics) from taste data.
- Logging redacts credential-like patterns and Bearer tokens; Qloo keys are never logged.

## Error handling

- Upstream Qloo failures return safe messages without secrets (`qloo_upstream`).
- Live mode does **not** silently fall back to demo mode after API errors.
- Database failures map to `503 database_unavailable`.

## Frontend bundle check

```bash
python scripts/scan_bundle_secrets.py
```

Fails if the configured `QLOO_API_KEY` appears under `apps/web/.next`.

## Audit trail

Keep detailed QA evidence in local `.cache/` if needed; do not commit secrets or raw key material.
