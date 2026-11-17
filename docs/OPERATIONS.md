# ConnectHub Operations Runbook

Status: **runbook IMPLEMENTED; production operations NOT RUN**

## Service checks

- `GET /health/live` proves the API event loop is serving.
- `GET /health/ready` performs `SELECT 1` and returns 200 only when PostgreSQL is reachable.
- The frontend proxy should return the same health response at `/health/ready`.
- WebSocket clients connect at `/ws`; repeated reconnects or queue overflow are operational signals.

Do not log cookies, CSRF tokens, passwords, full database URLs, provider keys, or message bodies. Correlate API failures with `X-Request-ID`.

## Suggested alerts

| Signal | Initial threshold | Response |
|---|---:|---|
| readiness non-200 | 2 consecutive minutes | Check PostgreSQL/service credentials and pool exhaustion |
| HTTP 5xx ratio | >2% for 5 minutes | Correlate request IDs and recent release/migration |
| p95 API latency | >1 s for 10 minutes | Inspect database queries, pool, CPU, and provider calls |
| WebSocket abnormal closes | >5% for 10 minutes | Inspect proxy upgrade/timeout and auth expiry |
| embedding failures | sustained increase | Disable AI worker if core messaging is affected; core chat must remain available |
| disk/database usage | >80% | Plan capacity, retention, and vacuum/backup action |

Thresholds are starting points and need production baselines.

## Incident triage

1. Record start time, impact, recent changes, and request IDs.
2. Protect evidence; never paste secrets or raw user messages into tickets.
3. Confirm liveness/readiness and database identity.
4. If a release caused the incident, roll back the application image; do not blindly downgrade the database.
5. For credential exposure, revoke/rotate the affected secret and sessions, then assess logs and notifications.
6. For suspected unauthorized room access, preserve access logs and relevant database rows; stop exposure without deleting evidence.
7. Document timeline, root cause, affected data, recovery, and corrective actions.

## Database maintenance

- Run Alembic from a one-off job, never concurrently from every web worker.
- Monitor connection pool usage and PostgreSQL locks/slow queries.
- Use provider-supported vacuum/analyze and point-in-time recovery where available.
- Verify backups and an isolated restore on a schedule; see `BACKUP_RESTORE.md`.

## AI degradation

AI is optional. If provider latency, quota, privacy status, or errors become unacceptable, set `AI_ENABLED=false` and restart the single backend process. Summaries/semantic indexing become unavailable; authentication, rooms, exact search, messages, and WebSockets must continue.

## Planned maintenance

Announce the window, take a backup, verify migration direction, deploy, run health/smoke checks, and keep rollback artifacts. Record operator, versions, migration revision, start/end time, and outcome in the release log.

