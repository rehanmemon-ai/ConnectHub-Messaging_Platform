# ConnectHub instructions

ConnectHub is a Real-Time Multi-Room Messaging Platform. Its approved modular-monolith stack is Python/FastAPI, PostgreSQL, SQLAlchemy, Alembic, React, TypeScript, Vite, and Tailwind CSS.

The approved portfolio deployment is one Render backend process, a separate Render/Nginx frontend preserving same-origin `/api`, `/health`, and `/ws` traffic, and Neon PostgreSQL. Do not introduce multi-worker realtime deployment without an explicit cross-process coordination design.

## Boundaries

- Keep exactly five initial entities: users, auth_sessions, rooms, room_memberships, and messages.
- Model user-room membership as many-to-many; ownership is only the membership role.
- PostgreSQL is durable truth; REST handles ordinary operations and WebSockets handle live delivery.
- The MVP is single-process and has no Redis, Kafka, microservices, Kubernetes, or Elasticsearch.
- Follow the specifications in `docs/`; do not silently change approved architecture.

## Engineering and security

- Prefer readable, typed, small modules with clear responsibilities and appropriate async patterns.
- Validate explicitly, reject unexpected fields, use safe transactions, and avoid unnecessary abstractions.
- Never expose secrets or trust client-provided sender identity, roles, ownership, IDs, or timestamps.
- Enforce authentication and authorization in the backend and return safe errors.
- Preserve the session, CSRF, Origin, deletion, and logging requirements in `docs/security-design.md`.
- Keep AI optional and disabled by default. Never send private conversations to a provider without explicit owner/user approval; never mix incompatible embedding profiles or expose provider keys to the frontend.

## Testing and Git

- Use real PostgreSQL for integration tests; never silently substitute SQLite.
- Test meaningful behavior and record exact evidence. Never claim an unexecuted test passed.
- Inspect Git status before changes. Preserve unrelated work; never reset, clean, or overwrite it.
- Do not stage or commit unless explicitly authorized.
- Keep `docs/PROJECT_HANDOFF.md` factual and updated after every authorized task.

The owner is learning the implementation. Explain significant decisions simply, and seek approval for architectural changes.

