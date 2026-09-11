# CDRR deployment configuration

## Recommended topology

Use the Next.js application as the only browser-facing application endpoint.

```text
Browser
   |
   | same-origin /api/*
   v
Next.js
   |
   | server-side rewrite
   v
FastAPI
   |
   +---- reads processed Parquet snapshots
   ^
   |
Collector ---- CoinMarketCap API
```

The browser no longer needs the FastAPI hostname. This removes production CORS from the normal request path and keeps infrastructure details out of client-side JavaScript.

## Frontend environment

Create `frontend/.env.local` for local use or configure the same variable in the deployment platform:

```text
API_INTERNAL_URL=http://127.0.0.1:8000
```

Common deployment values:

```text
# Same VM as FastAPI
API_INTERNAL_URL=http://127.0.0.1:8000

# Docker / Compose private service name
API_INTERNAL_URL=http://backend:8000

# Separate backend hosting provider
API_INTERNAL_URL=https://your-backend-host.example
```

`API_INTERNAL_URL` has no `NEXT_PUBLIC_` prefix. It is consumed by `next.config.ts` on the Next.js side and is not needed by browser code.

The configuration temporarily accepts the old `NEXT_PUBLIC_API_URL` as a migration fallback. Remove that variable after confirming `API_INTERNAL_URL` works.

## CORS

The current FastAPI application has explicit local CORS origins. With the recommended same-origin Next.js proxy, browser traffic never calls FastAPI cross-origin, so production does not depend on those CORS entries.

This is preferable to adding a wildcard production origin. CORS is not an authentication mechanism and does not protect a publicly reachable API from non-browser clients.

For deployment:

1. Prefer keeping FastAPI private to the Next.js service where the hosting platform permits it.
2. If FastAPI must be publicly reachable, restrict access at the network / reverse-proxy layer where practical.
3. Keep the existing local CORS origins only if direct local browser-to-FastAPI debugging is still useful.
4. If you deliberately switch back to direct browser-to-backend calls, add only the exact production frontend origin to FastAPI CORS; do not use `*` with credentialed requests.

## CoinMarketCap API key

The CoinMarketCap key remains in the root server-side environment used by the collector. It must never be placed in:

- `frontend/.env.local`;
- any variable beginning `NEXT_PUBLIC_`;
- frontend source code;
- Git history.

The frontend only consumes processed CDRR API responses.

## Data persistence

FastAPI reads processed Parquet snapshots written by the collector. Therefore the collector and API must see the same `data/` tree.

On a VM this is naturally the repository data directory. On managed hosting, use a persistent disk or shared volume if the service filesystem is ephemeral. A restart must not silently erase the accumulated processed and research history.

## Processes

Run the production API without the development reloader:

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Run the collector as a separate supervised process:

```bash
python scripts/collect_data.py
```

Use `systemd`, Docker Compose, or the hosting platform's process supervision so both restart after failure.

## Health behaviour

The frontend should reach health through the same-origin proxy:

```bash
curl http://localhost:3000/api/health
```

A healthy response should include the service status plus snapshot availability, row counts, modification times, ages, and read errors. The terminal already uses snapshot age to show `ONLINE`, `STALE`, or `DEGRADED` states.

Before a public deployment, verify:

```bash
curl -fsS http://localhost:3000/api/health
curl -fsS http://localhost:3000/api/risk/latest
curl -fsS http://localhost:3000/api/market/latest
```

## Production checklist

- `npm run lint` passes.
- `npm run build` passes.
- `API_INTERNAL_URL` is set for the frontend deployment.
- the CoinMarketCap key exists only on the collector/backend host;
- FastAPI and the collector share persistent `data/` storage;
- `/api/health` is reachable through the frontend origin;
- no public frontend bundle contains a CoinMarketCap key;
- the collector is supervised and has only one active instance;
- the backend is started without `--reload`;
- CDRR terminology follows `docs/TERMINOLOGY.md`.
