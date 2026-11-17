# ConnectHub Deployment Guide

Status: **portable deployment path IMPLEMENTED; public deployment NOT AUTHORIZED / NOT RUN**

## Supported topology

The release example uses one PostgreSQL 18 database, one single-worker FastAPI process, and one Nginx process serving the built React assets and proxying `/api`, `/health`, and `/ws`. The WebSocket connection manager is process-local, so the backend must remain one worker until a shared broker/fan-out design is implemented.

Artifacts:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/deploy/nginx.conf`
- `compose.production.example.yml`

The Compose port is loopback-only by default. A production TLS load balancer or reverse proxy must terminate HTTPS in front of it; never publish this example directly to the internet.

## Required production configuration

Provide secrets through the hosting platform's secret manager, never a committed file:

- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg://...` for a least-privileged application role
- `ALLOWED_ORIGINS=["https://your-exact-host"]`
- `COOKIE_SECURE=true`
- `CSRF_SECRET` with at least 32 unpredictable characters
- optional AI settings; default `AI_ENABLED=false`

Recommended production cookie names are `__Host-connecthub_session` and `__Host-connecthub_csrf` after an HTTPS acceptance run. Do not expose `TEST_DATABASE_URL` to the production service.

## Build and pre-deploy gates

From a clean checkout with Docker available:

```powershell
docker compose -f compose.production.example.yml config
docker compose -f compose.production.example.yml build
```

Before promotion, require CI backend, frontend, and browser-E2E jobs; a current PostgreSQL backup; dependency audits; and approval of the release-readiness register. The current Windows host has a Docker CLI but no reachable daemon, so image build and container smoke tests are **BLOCKED locally**, not passed.

## Migration and rollout

The `migrate` service runs `alembic upgrade head` once and must succeed before the backend starts. Migrations must target a positively identified backup-protected production database. Do not use `create_all()`.

Suggested rollout:

1. Put the application in a maintenance window if a migration is not backwards compatible.
2. Create and validate a database backup.
3. Deploy immutable images by digest.
4. Run the one-off migration job.
5. Start one backend worker, then the frontend proxy.
6. Verify `/health/live`, `/health/ready`, login, one authorized room read, WebSocket connection, and CSP/secure-cookie headers over HTTPS.
7. Monitor 5xx, readiness, database saturation, WebSocket disconnect rate, and latency.

## Rollback

Application rollback means restoring the prior immutable image. Database downgrade is not automatic. Prefer forward-fix migrations; use `alembic downgrade` only when that exact revision has a reviewed, data-safe downgrade and a current backup. For destructive or irreversible changes, restore into an isolated database first and obtain owner approval before production recovery.

## Platform-specific gaps

Domain/DNS, TLS certificate, managed PostgreSQL, secret manager, network policy, log sink, metrics/alerting, backup schedule, region, scaling, cost, and data-residency settings require a hosting-platform decision. They are not inferred or provisioned by this repository.

Current official-provider research, cost assumptions, and the recommended one-instance topology are in `STAGING_OPTIONS.md`. The ordered approval and evidence gates are in `PRODUCTION_OWNER_ACTIONS.md`. Neither document authorizes provisioning or public deployment.

