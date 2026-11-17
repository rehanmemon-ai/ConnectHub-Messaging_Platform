# ConnectHub Project Handoff

## Authoritative current snapshot — 2026-11-17 final QA closeout

This section supersedes contradictory historical status statements later in this append-only handoff. Historical milestone text is retained for traceability.

- Repository: public GitHub `rehanmemon-ai/ConnectHub-Messaging_Platform`; branch `main`; `HEAD` and `origin/main` are `04877d0f972fc85a096be989c9f1cd56fafb96c8` before the uncommitted closeout changes.
- Deployment: frontend <https://connecthub-web-w89e.onrender.com>, backend <https://connecthub-api-77hd.onrender.com>, Neon PostgreSQL in Singapore, Render/Nginx same-origin proxy, one backend process.
- Public read-only smoke: backend readiness, frontend root, and frontend-proxied readiness returned HTTP 200. No deployment was changed. The new favicon is not yet deployed; public `/favicon.svg` currently falls back to the SPA HTML.
- Final local gates: 97 backend tests; 21 Vitest tests; 3/3 Playwright scenarios; Ruff, formatting, `pip check`, ESLint, TypeScript, Vite build, Alembic drift, and production npm audit pass. A fresh full npm audit reports 12 high findings in development tooling; its listed fixes require incompatible major downgrades, so no blind downgrade was applied. One upstream Starlette/httpx deprecation warning remains.
- Corrected locally: chat follow/jump/history positioning, viewport-safe composer, accessible password visibility, connection/read-receipt contrast, favicon/metadata, deterministic WebSocket task cleanup, and Gemini evaluator string serialization plus average precision.
- AI: normal chat is independent of Gemini; `AI_ENABLED=false` remains the default. Configured source defaults are `gemini-3.5-flash-lite`, `gemini-embedding-001`, and 768 dimensions. This matches the existing Render override; real Gemini retrieval and summary quality are **NOT RUN** because no approved process key was available.
- Portfolio evidence: genuine synthetic E2E screenshots are outside Git under `D:\_Rehan\ConnectHub-Portfolio-Assets`. Playwright video capture was attempted but its bundled FFmpeg executable was absent; no video or MP4 was produced and no encoder was downloaded.
- Safety: no `.env` or private connection file was read or printed; no production database write/migration/test occurred; no key was accessed; no Render setting changed; no commit, push, or deploy occurred.
- Review documents: `QA_TEST_PLAN.md`, `QA_RESULTS.md`, `FEATURE_EVIDENCE_MATRIX.md`, and `portfolio/CONNECTHUB_CASE_STUDY.md`. Older claims below such as “no commits,” “no remote,” “frontend URL unknown,” or “public production not run” describe earlier milestones and are superseded by this snapshot.

The local working tree intentionally contains the owner-reviewable source, tests, and documentation listed by `git status`; nothing is staged. The live services continue to run the previously deployed commit until the owner reviews and deploys these changes.

## Current Render frontend deployment preparation — 2026-11-17

- Repository alignment: branch `main`, `HEAD` and `origin/main` both at `3e6d2e6`; no commit or push was performed.
- Backend target: `https://connecthub-api-77hd.onrender.com`.
- `frontend/deploy/nginx.conf` now preserves browser same-origin paths for `/api/`, `/health/`, and `/ws` while forwarding each unchanged path to the HTTPS backend. It sends the Render backend hostname as upstream `Host` and TLS SNI, explicitly preserves the browser `Origin`, forwards client/X-Forwarded information, and retains WebSocket upgrade semantics with 120-second read/send timeouts.
- Upstream certificate verification is enabled against Alpine's `/etc/ssl/certs/ca-certificates.crt`; `frontend/Dockerfile` explicitly installs `ca-certificates`. Nginx still listens on and exposes port 8080.
- Frontend verification: ESLint PASS, TypeScript PASS, Vitest PASS (17 tests), and Vite production build PASS (34 modules).
- Static proxy assertions PASS, including removal of every `http://backend:8000` reference. Native Nginx syntax validation and Docker image build are **BLOCKED / NOT RUN** because the installed Docker client cannot reach the Docker Desktop Linux daemon.
- The final Render frontend URL is still unknown. The owner must set frontend `PORT=8080`, then add the exact deployed HTTPS frontend origin to backend `ALLOWED_ORIGINS` and redeploy/restart the backend before authentication or WebSockets can pass Origin validation. Do not guess this value.
- Pre-existing untracked `connection_string.txt` was not read, changed, staged, or exposed. Treat it as potentially sensitive and keep it out of Git.

## 1. Project identity and status

- Repository: `D:\_Rehan\Project_Python_Chat_system`
- Git: branch `main`; no commits; no staged files; all project files remain untracked.
- Specifications: all six remain **Draft — Pending Project Owner Review**.
- Task 2 foundation/database: **COMPLETE / VERIFIED**.
- Task 3 identity/session/public-room backend: **COMPLETE / VERIFIED**.
- Complete backend milestone: **COMPLETE / VERIFIED locally**.
- Complete frontend integration: **COMPLETE / VERIFIED locally**.
- Release hardening and portable deployment preparation: **COMPLETE / VERIFIED locally**.
- Controlled staging/pilot: **CONDITIONAL GO**, subject to the owner actions in `RELEASE_READINESS.md`.
- Public production deployment: **NO-GO / NOT AUTHORIZED / NOT RUN** pending hosting, TLS, secrets, and isolated restore verification.

Status words are literal: PROPOSED is a recommendation, IMPLEMENTED is present in source, VERIFIED has current execution evidence, BLOCKED has a concrete prerequisite, and NOT RUN was not executed.

## 2. Verified environment

| Component | Current verified value |
|---|---|
| Windows | Windows 11 |
| Python | 3.13.14, project `.venv` |
| SQLAlchemy | 2.1.8 with asyncio; greenlet 3.5.6 |
| Psycopg/libpq | 3.3.9, pure-Python implementation, system libpq 18.7 |
| FastAPI/Uvicorn | 0.163.1 / 0.54.0 |
| WebSocket runtime | websockets 17.4 |
| Alembic | 1.20.1 |
| Node/npm | 24.22.3 / 11.19.1 from NVM |
| React/TypeScript/Vite | 19.3.1 / 6.0.3 / 8.3.8 |
| PostgreSQL | 18.7, service `postgresql-x64-18`, loopback 5432 |

Windows Application Control blocks optional native Python extensions. Backend shells require process-scoped `PSYCOPG_IMPL=python` and `C:\Program Files\PostgreSQL\18\bin` prepended to that process's PATH. No machine-wide setting was changed.

## 3. Configuration and database identities

`backend/app/core/config.py` resolves the ignored root `.env` by a stable source-derived path. The owner-managed `.env` was not changed or printed.

| Purpose | Driver/user | Host | Database | Result |
|---|---|---|---|---|
| Development | `postgresql+psycopg`, `connecthub_app` | `127.0.0.1:5432` | `connecthub_dev` | VERIFIED |
| Testing | `postgresql+psycopg`, `connecthub_app` | `127.0.0.1:5432` | `connecthub_test` | VERIFIED |

The local application role is not a superuser and has neither `CREATEDB` nor `CREATEROLE`. Test safety requires a distinct database ending in `_test` before migration or cleanup. AI is disabled by default and no provider credential belongs in source or this handoff.

## 4. Implemented frontend

### Application shell and identity

- History-based routing with protected navigation, session restoration without a login flash, responsive sidebar/header, unread indicator, theme persistence, skip link, and accessible loading/empty/error states.
- Registration, login, logout, current-profile display, and supported username/display-name updates.
- Cookie session authentication uses `credentials: include`; unsafe requests echo `connecthub_csrf` through `X-CSRF-Token`. Session credentials are never placed in local or session storage.
- Registration truthfully redirects to sign-in because the backend does not create a session on registration.

### Rooms, chat, and real-time behavior

- Joined rooms, public discovery/search/pagination/joining, public/private room creation, received invitation accept/decline, durable owner invitation history/revoke, member list/removal, leave, and confirmed owner deletion.
- Cursor history, older-page preservation, chronological UUID-aware deduplication, plain-text message rendering, 4,000-character composer, Enter-to-send/Shift+Enter, and HTTP sends with a cryptographic client UUID.
- Failed message retry preserves the original client UUID. The server remains authoritative for sender, membership, and idempotency.
- One authenticated root `/ws` connection, explicit room subscriptions, bounded exponential reconnect with jitter, heartbeat, event validation, resubscription, connection state, message/presence/typing/read/notification events, and cleanup on logout/unmount.
- Read-position updates are coalesced. Typing stops on blur, inactivity, send, and unmount.

### Notifications, search, and AI

- Notification list/count, mark-one by navigation, mark-all, persistent recovery, and live refresh signaling.
- Exact text search and semantic search within joined rooms, with index state and similarity display.
- Room summary, embedding status, owner backfill, and explicit provider-disabled/error states. The UI never fabricates AI output.

### Honest contract limitations

- The backend has no room-edit route, so the client does not present a fake edit workflow.
- Owner invitation history is persisted and recovered through `GET /api/v1/rooms/{room_id}/invitations`; only the current owner is authorized.
- Multi-process WebSocket broadcast/presence is not supported; the backend remains deliberately single-process.
- Password recovery, email verification, account deletion, and room ownership transfer are outside the approved MVP.

## 5. Database and backend state

Migrations remain incremental and unchanged:

1. `20261116_0001` — five-table foundation.
2. `20261116_0002` — complete backend messaging, invitations, notifications, read state, AI summaries, embeddings, and durable job state.
3. `20261117_0003` — AI embedding-profile isolation, job origin/profile safety, and versioned summary-cache metadata.

Both local databases are currently verified at `20261117_0003 (head)`. Current `alembic history` discovers all three revisions and `alembic check` reports **No new upgrade operations detected**. The partial unique owner index enforces at most one owner; supported application transactions preserve the minimum-one-owner invariant.

The backend provides registration/session/CSRF, profiles, public/private rooms, membership and invitations, persistent messages/history/search/read receipts, notifications, authenticated WebSockets, AI summary, durable embedding jobs, and bounded semantic search. PostgreSQL remains authoritative and message commit precedes live broadcast.

## 6. Current verification evidence

### Frontend

| Check | Result |
|---|---|
| ESLint | PASS |
| TypeScript | PASS |
| Vitest | PASS — 3 files / 17 tests |
| Vite production build | PASS — 34 modules; JS 275.77 kB / 83.16 kB gzip; CSS 31.62 kB / 7.39 kB gzip |
| Full `npm audit` | PASS — 0 vulnerabilities |
| `npm audit --omit=dev` | PASS — 0 vulnerabilities |

Tests use mocked REST and WebSocket boundaries and do not connect to either local database. They cover session restoration, login/registration and validation, safe API errors, CSRF behavior, safe message rendering, room-scoped live events, subscription and typing messages, stable idempotent retry, public-room join, notification mutation, provider-unavailable summary behavior, and a genuine semantic-search response path.

The prior seven moderate dev-only `minimatch` findings were resolved by the focused compatible update from `typescript-eslint` 8.72.2 to 8.73.0. `npm ci` was then rerun and the complete frontend gate passed. No force, override, downgrade, or unrelated package upgrade was used.

### Backend

| Check | Result |
|---|---|
| `pip check` | PASS |
| Ruff lint | PASS |
| Ruff format | PASS — 80 files in the latest full portfolio verification |
| Full Pytest suite | PASS — 93 passed, 0 failed, 0 skipped |
| Alembic history | PASS — `0001 -> 0002 -> 0003 (head)` |
| Alembic drift check | PASS — no new upgrade operations |

These are the latest full-suite results from the portfolio milestone; this closeout changed documentation and the PowerShell lifecycle script, not Python application code. The passing backend run used the required process-scoped PostgreSQL `bin` PATH and `PSYCOPG_IMPL=python`; Psycopg reported 3.3.9, implementation `python`, and libpq 18.7. One non-failing upstream Starlette `TestClient` deprecation warning remains.

## 7. Local application and browser status

- Backend expected URL: `http://127.0.0.1:8000`.
- Frontend expected URL: `http://127.0.0.1:5173`.
- Historical final-verification listeners: backend PID `20608` ran the project `.venv` Python command for `backend/run.py`; frontend PID `21760` ran this repository's Vite binary. Both were loopback-only and all four direct/proxied health checks returned HTTP 200 during final verification.
- Continuation capture on 2026-11-17: those processes have exited; ports `8000` and `5173` have no listeners, and current HTTP health requests are therefore **NOT RUNNING / connection refused**. They were not blindly restarted.
- Interactive browser QA VERIFIED the actual login and registration pages at 1280×720, registration at 390×844, client-side empty-form validation, no horizontal overflow at either tested viewport, no console errors/warnings, and absence of the legacy foundation-status text.
- PostgreSQL-backed Playwright E2E PASS — 3/3 scenarios. It used only the guarded `_test` database and cleaned it before/after. Three browser contexts verified auth, session restore, public joining, real WebSocket delivery, idempotent replay, private invite/accept, outsider concealment, durable invitation recovery, exact search, AI-disabled behavior, desktop/mobile layouts, axe scanning, and a bounded 20-write load smoke.
- A final visible browser check verified the live ConnectHub login page at `http://127.0.0.1:5173/login`.

## 8. Files changed in the complete frontend milestone

Implemented or updated frontend paths:

- `frontend/src/App.tsx`, `frontend/src/styles/global.css`
- `frontend/src/app/` — auth, routing, shell, toasts
- `frontend/src/components/ui/` — primitives and icon system
- `frontend/src/features/` — auth, dashboard, rooms, chat, notifications, profile, search
- `frontend/src/lib/` — API, formatting, async hook
- `frontend/src/realtime/RealtimeContext.tsx`
- `frontend/src/types/api.ts`
- `frontend/src/App.test.tsx`, `frontend/src/features/frontend-flows.test.tsx`, `frontend/src/lib/api.test.ts`, test helpers/setup
- `frontend/package.json`, `frontend/package-lock.json`
- `frontend/e2e/`, `frontend/playwright.config.ts`, frontend deployment image/proxy files
- backend release fixes, E2E safety scripts, and owner invitation route/test
- `README.md`, `.github/workflows/ci.yml`, Compose example, and release/security/operations/privacy/backup documentation

Generated ignored `frontend/dist`, `frontend/node_modules`, Playwright report, and test-result artifacts changed during verification. The frontend milestone did not edit backend source; the later release-hardening milestone intentionally added the documented backend fixes and tests. The real `.env`, `.venv`, existing migration files, and preserved empty root `package-lock.json` were not edited.

## 9. Git and preservation

- Branch `main`; no commits; nothing staged; project files untracked.
- No reset, clean, stash, checkout, commit, push, database drop/recreate, system installation, machine-setting change, or public deployment occurred.
- The owner-managed `.env` was neither modified nor disclosed.
- The browser harness used only `connecthub_test` and performed its guarded truncate-before/after cleanup. It did not use `connecthub_dev` for destructive setup; neither database was dropped or recreated.
- No Task 3/backend feature was rebuilt during frontend integration.

## 10. Remaining risks and next milestone

- An isolated database restore rehearsal is BLOCKED pending an authorized `_restore_test` target. The custom-format development backup archive and archive listing are VERIFIED.
- Docker Compose syntax is VERIFIED, but image build/run is BLOCKED because the local Docker daemon is unavailable.
- Production TLS/WSS, provider secrets/networking, remote CI, monitoring, and public deployment are NOT RUN.
- Live Gemini account/quota behavior is NOT RUN; normal messaging remains available with AI disabled.
- Multiple backend workers require approved shared pub/sub plus distributed presence/rate-limit infrastructure.
- JSONB vector ranking is bounded and is not a pgvector-scale index.
- The upstream Starlette TestClient warning remains documented.

**Next milestone:** project-owner release review, hosting-platform/privacy decisions, then an explicitly approved controlled staging deployment and isolated restore rehearsal. Do not provision or publish without approval.

## 11. Change log

- 2026-11-16 — Task 1: six draft specifications created.
- 2026-11-16 — Task 2: foundation, PostgreSQL schema, environment, and regression verified.
- 2026-11-16 — Task 3: identity/session security and public-room backend completed.
- 2026-11-16 — Complete backend: messaging, WebSockets, private rooms, notifications, AI summaries/embeddings/search, and migration completed.
- 2026-11-17 — Complete frontend: full React client, real-time integration, 17 deterministic tests, dependency remediation, responsive public browser QA, local servers, and full regression completed.
- 2026-11-17 — Release hardening: 78 backend tests, 17 Vitest tests, 3 real browser E2E scenarios, security/accessibility/load corrections, durable invitation history, portable deployment artifacts, backup archive validation, and operations/privacy/release documentation completed.
- 2026-11-17 — Final continuation: documentation and preservation reconciled; Git/database state rechecked read-only; historical services found stopped and recorded without restart.
- 2026-11-17 — Post-hardening release preparation: provider options researched, owner decision pack and safe local lifecycle workflow added, CI audits added, backup/restore instructions tightened, and focused operational verification completed. No provider resource or public deployment was created.
- 2026-11-17 — Review package preparation: stale requirements/database/roadmap status notes reconciled with the verified integrated application; a source-only AI/documentation review ZIP and reproducible allowlist bundler were created and integrity-checked.

## 12. Post-hardening release-preparation continuation

### Current decision

- Local application: **COMPLETE / VERIFIED**.
- Controlled staging/pilot: **CONDITIONAL GO**, awaiting the explicit provider, region, budget, repository, privacy, and provisioning decisions in `PRODUCTION_OWNER_ACTIONS.md`.
- Public production: **NO-GO / NOT AUTHORIZED / NOT RUN**.

`STAGING_OPTIONS.md` compares current official provider capabilities and prices. The recommended low-cost pilot is Render Singapore: one paid 512 MB backend service, free static site, and smallest paid Render Postgres, estimated at USD 13 / approximately ₹1,224 monthly before tax and overages. DigitalOcean is the alternative at a published starting-price estimate of USD 20 / approximately ₹1,882 monthly, subject to confirming Bangalore placement for every required dynamic component. The INR conversion uses the 2026-11-16 RBI/FBIL reference rate of ₹94.1159/USD. No account, billing method, DNS, domain, or cloud resource was created.

### Local operations added and verified

`scripts/connecthub-dev.ps1` now provides `start`, `status`, and `stop`. It refuses occupied ports, uses the exact project interpreter and frontend Vite installation, scopes Psycopg/libpq and an unpredictable CSRF secret to child processes, binds to loopback, writes ignored PID/log state, verifies four HTTP endpoints, and only stops recorded processes after command-line identity checks.

Current execution evidence:

| Check | Result |
|---|---|
| PowerShell syntax parse | PASS |
| Clean start from unused ports | PASS — backend PID 4608, frontend PID 17576 during the verification run |
| Backend `/health/live` and `/health/ready` | PASS — HTTP 200 |
| Frontend root and proxied `/health/ready` | PASS — HTTP 200 |
| Owned-process status checks | PASS |
| Safe stop and final status | PASS — only recorded processes stopped; services currently stopped |

The verification PIDs are historical and no longer running. Runtime logs/PID state are ignored under `.runtime/`; the PID state file was removed by the successful stop.

### CI and container state

The workflow still defines backend PostgreSQL tests, Ruff, Alembic migration, frontend lint/typecheck/Vitest/build, and real PostgreSQL Playwright E2E. Full and production `npm audit` steps were added to the frontend job, and both audits were rerun locally with zero vulnerabilities. `actionlint` and a local YAML library are not installed, so GitHub-specific workflow validation remains **NOT RUN**; the YAML and job structure were inspected manually. Remote GitHub Actions remains **NOT RUN** because there is no Git remote or commit.

Docker Compose interpolation/syntax passed again using non-secret placeholder process variables. Docker CLI 29.6.2 is present, but its Desktop Linux daemon is unreachable, so image build, runtime health, image-content inspection, non-root runtime proof, proxy WebSocket smoke, SBOM, and scan remain **BLOCKED locally / NOT RUN**. Source inspection still shows a single Uvicorn worker and a non-root backend image user; the frontend runtime image must be runtime-tested before staging.

### Backup, databases, and AI/privacy

- The existing archive remains outside the repository at the owner machine's temporary backup directory: 32,883 bytes, 73 readable non-comment entries, with the expected database objects. Its listing contains database schema/data objects rather than unrelated application configuration. Archive readability is **VERIFIED**; restoration is **NOT RUN**.
- `BACKUP_RESTORE.md` now separates the administrator-only creation/removal of `connecthub_restore_test` from the application-role restore rehearsal. The local `connecthub_app` role remains non-superuser without `CREATEDB` or `CREATEROLE`; no privilege was bypassed.
- Read-only current database checks reconfirmed `connecthub_dev` and `connecthub_test` at `20261116_0002`, with 11 public tables each. Neither database was dropped, recreated, reset, truncated, migrated, or otherwise mutated in this continuation.
- Current settings load `AI_ENABLED=false`. Provider code rejects summary/embedding calls before outbound HTTP when AI is disabled or no key exists, and the background worker is not started. No AI call or credential was used. Existing engineering privacy disclosure documents Gemini message/search processing; a final user-facing consent/notice and provider-account retention review remain required before enabling AI.

### Files changed in this continuation

- `.gitignore`
- `.github/workflows/ci.yml`
- `README.md`
- `scripts/connecthub-dev.ps1` (new)
- `docs/STAGING_OPTIONS.md` (new)
- `docs/PRODUCTION_OWNER_ACTIONS.md` (new)
- `docs/BACKUP_RESTORE.md`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY_REVIEW.md`
- `docs/PRIVACY_DATA_FLOW.md`
- `docs/RELEASE_READINESS.md`
- `docs/PROJECT_HANDOFF.md`

The owner-managed `.env` remains 188 bytes with its original 2026-11-16 18:37 timestamp, and its contents were not printed or changed. `.venv`, both historical migrations, the empty 105-byte root `package-lock.json`, database data, and all prior untracked source were preserved. Branch `main` still has no commits, remote, or staged files; all project files remain untracked.

### Exact next action

The owner should review `STAGING_OPTIONS.md`, select the provider/region, and approve a staging budget ceiling. Next, create an owner-controlled GitHub repository, review the initial source snapshot before committing, and obtain a complete remote CI run. Provider resource creation requires a separate explicit authorization tied to that repository revision, provider, region, and budget.

## 13. Documentation and AI review package

`ConnectHub_Review_Files.zip` is an owner-shareable source review package generated by `scripts/bundle_review_files.py`. It contains the complete current `docs/` folder, README, the AI provider/service/router/schemas/worker, AI configuration and message-job integration, AI database models and migration, backend summary/embedding/semantic-search tests, the relevant frontend feature-flow tests, and a SHA-256 manifest.

The archive is produced from an explicit allowlist plus the `docs/` tree. The bundler rejects `.env`, `.venv`, `node_modules`, `.runtime`, `.git`, caches, generated browser output, database files/dumps, private-key formats, and nested ZIP files. It was regenerated after this closeout, passed `ZipFile.testzip()`, includes the complete documentation tree, evaluation package, and bundler, and contains zero forbidden paths. No test database, backup archive, credential, dependency directory, or runtime log was packaged. The final archive hash and entry count are reported externally because embedding its own hash inside an archived document would make that value stale.

## 14. Final portfolio and AI-evaluation milestone — 2026-11-17

### Outcome and correctness changes

The portfolio milestone is **COMPLETE / VERIFIED locally**, with live provider-quality evaluation and screenshots accurately marked **NOT RUN**. Gemini stored-message requests now use `RETRIEVAL_DOCUMENT`; search uses `RETRIEVAL_QUERY`. A provider/model/dimension/version profile prevents incompatible vector mixing. AI-disabled messages create no job. Automatic new-message indexing and historical owner backfill are independent opt-ins; enabling AI alone cannot release a backlog. Unexpected worker errors enter bounded durable retry/failure state, stale recovery runs periodically, and invalid/non-finite/zero vectors cannot be stored as successful embeddings.

Semantic responses now distinguish total, active-profile indexed, unindexed, candidate-count/window truncation, and failed jobs. Summary requests respect server message and character maxima, disclose truncation/input size, and cache by provider/model/prompt version/source fingerprint. Concurrent cache insertion uses the database uniqueness constraint. Migration `20261117_0003` preserves legacy vectors/jobs/summaries under explicit legacy labels.

### Evaluation evidence

- Synthetic retrieval dataset: 120 messages, 60 graded queries, no production/user content.
- Synthetic summary dataset: 18 fixtures including conflict, unresolved-state, and prompt-injection cases.
- Offline exact-substring baseline at K=5: P=0.1067, Recall=0.1778, MRR=0.4833, nDCG=0.1176, MAP=0.1778.
- Same baseline with newest 50 candidates: P=0.0533, Recall=0.0889, MRR=0.2333, nDCG=0.0583, MAP=0.0889. This measures recency-window loss, not Gemini quality.
- Live Gemini semantic and summary quality: **NOT RUN**. No provider key or real message was used.

### Current verification

| Gate | Current result |
|---|---|
| Backend Pytest | PASS — 93 passed, one known Starlette/httpx deprecation warning |
| Ruff lint / format | PASS / PASS — 80 files formatted |
| pip check | PASS — no broken requirements |
| Alembic test migration | PASS — guarded `connecthub_test` at `20261117_0003` |
| Alembic development migration | PASS — `connecthub_dev` upgraded incrementally to `20261117_0003` |
| Alembic metadata drift | PASS — no new upgrade operations |
| Frontend ESLint / TypeScript | PASS / PASS |
| Vitest | PASS — 17 passed |
| Vite production build | PASS |
| npm audit full / production | PASS — zero vulnerabilities / zero vulnerabilities |
| Playwright | NOT RERUN — historical 3/3 remains the latest authenticated E2E evidence |
| Live Gemini quality/cost | NOT RUN |
| Screenshots/demo recording | NOT RUN |

### Portfolio artifacts

Added a reproducible `backend/evals/` package, `AI_EVALUATION.md`, `AI_DATASET.md`, seven versioned Mermaid diagrams, six ADRs, demo/interview/publication/license/freeze documents, and a portfolio-focused README. The exact-search JSON artifacts are machine-readable. The specifications remain **Draft — Pending Project Owner Review**.

### Preservation and release status

The real `.env` was not printed or modified; AI stayed disabled and no Gemini call occurred. No database was dropped, recreated, or reset. The test suite used only guarded `connecthub_test`; development received only the approved incremental migration after test success. Branch `main` still has no commits, remote, or staged files; no reset, clean, stash, checkout, commit, push, cloud resource, or public deployment occurred. All project files remain untracked and must be owner-reviewed before a first commit.

Local application and portfolio evidence: **COMPLETE / VERIFIED**. Controlled staging: **CONDITIONAL GO**. Public production: **NO-GO / NOT AUTHORIZED / NOT RUN**. Owner actions remain provider/privacy approval, optional synthetic-only live evaluation, screenshot/demo capture, license selection, initial GitHub publication/remote CI, isolated restore rehearsal, and the previously documented hosting/TLS/secrets/monitoring approvals.

### Change-log entry

## 15. Definitive engineering closeout — 2026-11-17

### Owner quick start and current service state

PowerShell 7 is preferred; the same lifecycle is verified under Windows PowerShell 5.1. On the owner machine:

```powershell
cd "D:\_Rehan\Project_Python_Chat_system"
code .
.\scripts\connecthub-dev.ps1 start
.\scripts\connecthub-dev.ps1 status
.\scripts\connecthub-dev.ps1 stop
```

After `start` succeeds, use `http://127.0.0.1:5173` and `http://127.0.0.1:8000/health/ready`. The script starts both services, performs direct and proxied health checks, and refuses occupied ports rather than terminating unrelated processes. AI remains disabled by default. **Final closeout state: both services are stopped; ports 8000 and 5173 have no ConnectHub listeners.**

This closeout independently completed start/status/health/stop under PowerShell 7.7.0 (historical verification PIDs 17312 and 9564) and Windows PowerShell 5.1.26100.9818 (historical verification PIDs 5892 and 18572). In both runs, backend liveness/readiness, frontend root, and frontend-proxied readiness returned HTTP 200; the recorded processes were then safely stopped and PID state removed. The script now uses a disposed cryptographic RNG compatible with both shells and uses `IndexOf(..., StringComparison)` rather than the PowerShell-7-only `String.Contains` overload.

### Architecture and repository map

- `backend/app/` — FastAPI application, identity/session security, rooms, messaging, notifications, WebSockets, and optional AI.
- `backend/migrations/` — immutable incremental Alembic history through `20261117_0003`.
- `backend/tests/` and `backend/evals/` — PostgreSQL integration/unit coverage and synthetic AI evaluation evidence.
- `frontend/src/` — React/TypeScript application and mocked feature-flow tests.
- `frontend/e2e/` — PostgreSQL-backed authenticated Playwright scenarios.
- `scripts/connecthub-dev.ps1` — the sole owner lifecycle entry point; `scripts/bundle_review_files.py` — allowlisted review-package builder.
- `docs/` — specifications, contracts, architecture/ADRs/diagrams, security/privacy/operations/deployment, portfolio evidence, staging decision material, and this handoff.
- `.github/workflows/ci.yml`, Dockerfiles, `frontend/deploy/nginx.conf`, and `compose.production.example.yml` — portable CI/deployment source; not evidence of a public deployment.

PostgreSQL is the source of truth. The browser uses cookie sessions plus CSRF protection; REST commits precede live WebSocket broadcast. The connection registry, presence, and rate limits are process-local, so the approved deployment remains exactly one backend process until a shared coordination layer is deliberately designed.

### Closeout audit, deployment, and preservation

- Read-only database identity checks reconfirmed `connecthub_dev` and `connecthub_test` as separate PostgreSQL databases owned through `connecthub_app`, both at revision `20261117_0003` with 11 application tables. No database mutation was performed in this closeout.
- Docker Compose interpolation/syntax passed with non-secret placeholders. The Docker CLI is installed, but its Linux daemon is unavailable, so image build/run, non-root runtime inspection, image scanning, and container health remain **BLOCKED / NOT RUN**.
- CI source includes PostgreSQL-backed backend and Playwright jobs plus frontend lint/typecheck/test/build and both npm audits. `actionlint` is unavailable and there is no Git remote or remote CI run; remote CI remains **NOT RUN**.
- The external custom-format archive remains readable at 32,883 bytes with 73 listed objects. Archive readability is **VERIFIED**; restore is **NOT RUN** pending an owner-authorized isolated `connecthub_restore_test` database.
- The ignored `.env` was neither printed nor modified; `.venv`, `node_modules`, migration history, the empty root `package-lock.json`, both databases, and all source/evaluation evidence were preserved. No staging, commit, remote, push, provider call, cloud resource, Gemini call, or public deployment occurred.
- Existing files edited in this closeout were copied byte-for-byte before editing to `C:\Users\DELL\AppData\Local\Temp\ConnectHub-closeout-20261117-101234-def2c77e`; `SHA256SUMS.txt` records and verifies their original SHA-256 values.

Generated cache/build/runtime directories were identified as disposable (`.pytest_cache`, `.ruff_cache`, Python `__pycache__`, `frontend/dist`, `frontend/playwright-report`, `frontend/test-results`, and `.runtime`). Their removal was attempted only after exact in-repository validation, but the execution host rejected recursive deletion. They remain untracked/generated and must not be included in the first commit. The 105-byte root `package-lock.json` is intentionally preserved for owner review even though the root has no `package.json`; do not silently delete it.

### Current release and maintenance freeze

- Local application and source evidence: **COMPLETE / VERIFIED**.
- Controlled staging/pilot: **CONDITIONAL GO**, requiring the ordered owner decisions in `PRODUCTION_OWNER_ACTIONS.md`.
- Public production: **NO-GO / NOT AUTHORIZED / NOT RUN**.
- Render Singapore remains the recommended low-cost pilot at a USD 13/month planning minimum; DigitalOcean is the alternative at a USD 20/month planning minimum, subject to confirming component placement. Both exclude tax, overages, domain, and provider-specific extras.
- Product expansion, dependency upgrades, schema changes, multi-worker scaling, AI enablement, and public deployment are frozen until separately approved. Routine future maintenance should begin from `FINAL_CLOSEOUT_REPORT.md`, this handoff, and the current source—not chat history.

- 2026-11-17 — Portfolio/AI evaluation: corrected Gemini retrieval profiles, disabled-backlog privacy, worker recovery, search accounting, and summary caching; added migration 0003, synthetic evaluation datasets/metrics, diagrams, ADRs, portfolio/interview/demo/publication/freeze evidence; verified 93 backend and 17 frontend tests.
