# ConnectHub Requirements Specification

| Metadata | Value |
|---|---|
| Project | ConnectHub |
| Document title | Requirements Specification |
| Status | Draft — Pending Project Owner Review |
| Version | 0.1 |
| Date of preparation | 2026-11-16 |

## 1. Project summary

ConnectHub is a real-time, multi-room messaging web application. Registered users discover public rooms, join several rooms, exchange messages in real time, and recover persistent history after reconnecting. This specification evolves a console-based OOP exercise into a maintainable modular monolith without pretending the educational program was already a networked system.

## 2. Problem statement

The original `Message`, `User`, and `ChatRoom` exercise demonstrates object collaboration using Python references, lists, a process-local counter, and `print()`. It cannot support independent clients, durable identity, secure access, concurrent rooms, or history after process exit. ConnectHub needs explicit trust boundaries, database-enforced relationships, authenticated APIs, and recoverable real-time delivery.

## 3. Goals and target users

Goals are to demonstrate sound Python/backend engineering; provide secure multi-room messaging; preserve messages in PostgreSQL; offer a responsive React interface; and remain practical on Windows 11 with an Intel Core i3-10110U, 8 GB RAM, and SSD.

Target users are registered participants in public rooms, room creators who manage their rooms, and users who connect from multiple browsers or devices.

## 4. Main use cases

1. Register, log in, view/update a profile, and log out.
2. Discover public rooms, create a room, and join or leave rooms.
3. Participate in several rooms without losing other memberships.
4. Retrieve stable, paginated message history.
5. Send a validated message and receive committed messages in real time.
6. Reconnect after interruption and recover missed messages from history.
7. Delete an owned room, subject to explicit approval of permanent deletion.

## 5. Functional requirements

### Identity and sessions

| ID | Requirement |
|---|---|
| FR-AUTH-01 | A visitor can register with normalized username, email, and password. Username and email are case-insensitively unique. |
| FR-AUTH-02 | Passwords are hashed with Argon2id; plaintext passwords and password hashes never appear in API responses or logs. |
| FR-AUTH-03 | Valid credentials create a configurable, database-backed session using a cryptographically secure opaque token with at least 256 bits of entropy. Only its 64-character lowercase SHA-256 hexadecimal digest is stored. |
| FR-AUTH-04 | The raw session token is sent only in an HttpOnly cookie, never JSON or a WebSocket query string. |
| FR-AUTH-05 | Logout is idempotent: it revokes a valid current session when present, clears session and CSRF cookies, closes identifiable local WebSockets, and returns `204` even when the session is absent, expired, or already revoked. Valid cookie-authenticated revocation requires valid CSRF proof. |
| FR-AUTH-06 | Expired or revoked sessions cannot authenticate HTTP or new WebSocket requests. Multiple device sessions are supported. |
| FR-AUTH-07 | A user can retrieve the profile and update username/display name subject to validation. Registration email is required, case-insensitively unique, and immutable in the MVP. Email verification and password recovery are not implemented. |
| FR-AUTH-08 | State-changing cookie-authenticated HTTP requests require CSRF protection in addition to SameSite cookies. |

### Rooms and membership

| ID | Requirement |
|---|---|
| FR-ROOM-01 | Authenticated users can list and inspect public, discoverable rooms. |
| FR-ROOM-02 | An authenticated user can create a room and atomically receive its single `owner` membership. |
| FR-ROOM-03 | A user can join multiple rooms; each user-room pair exists at most once. Duplicate joins have a documented conflict response. |
| FR-ROOM-04 | A normal member can leave; the membership is removed but prior messages remain. |
| FR-ROOM-05 | An owner cannot leave while the room exists. Ownership transfer is not supported in the MVP. |
| FR-ROOM-06 | Only an owner can delete a room. The project owner has APPROVED one-transaction hard deletion of the live room, memberships, and messages, with later destructive UI confirmation. Provider backups follow separate retention and are not guaranteed to disappear immediately. |
| FR-ROOM-07 | Membership is required to read history, open the room WebSocket, or send a message. Former members regain access only by rejoining. |
| FR-ROOM-08 | Room names need not be globally unique. Names are 1–100 trimmed characters; descriptions are 0–500 characters. |
| FR-ROOM-09 | Public room search is case-insensitive substring matching on room name, safely escapes SQL wildcard characters, and accepts at most 100 search characters. |
| FR-ROOM-10 | Public rooms use `(created_at DESC, id DESC)` cursors; joined rooms use `(joined_at DESC, room_id DESC)`. Defaults are 50 items and maximums are 100; every request reauthenticates. |

### Messages and real-time behavior

| ID | Requirement |
|---|---|
| FR-MSG-01 | Only an authenticated current member can send to a room. Sender identity, role, and timestamp come from trusted server state. |
| FR-MSG-02 | Message content is trimmed, non-empty, plain text, and at most 4,000 characters. |
| FR-MSG-03 | A message receives a database UUID and UTC timestamp and is committed before it is broadcast. |
| FR-MSG-04 | Connected members receive a consistent `message.created` event; exactly-once delivery is not promised. |
| FR-MSG-05 | History uses cursor pagination ordered stably by `(created_at, id)`, newest first at the API boundary, with at most 100 messages per page. |
| FR-MSG-06 | Reconnecting clients retrieve missed messages through REST and deduplicate live/history results by message UUID. |
| FR-MSG-07 | Invalid or oversized WebSocket payloads receive a safe protocol error; repeated abuse may close the connection. |
| FR-MSG-08 | Membership removal, room deletion, session expiry, or logout removes authorization; affected local connections are closed promptly and every incoming event is re-authorized as needed. |
| FR-MSG-09 | Incoming WebSocket frames are limited to 16 KiB in addition to the 4,000-character message limit; runtime enforcement is verified in Task 4. |
| FR-MSG-10 | Message send and membership removal acquire conflicting PostgreSQL row locks on the same membership. A send that locks first may commit before removal; a removal that completes first causes the later send to fail. |

### Interface and operations

| ID | Requirement |
|---|---|
| FR-UI-01 | The React interface provides registration, login, logout, profile, room discovery/creation, joined-room navigation, history, live messages, and a composer. |
| FR-UI-02 | The interface provides accessible loading, empty, validation, error, connection, and reconnection states on mobile and desktop. |
| FR-API-01 | REST endpoints are versioned under `/api/v1` and return a consistent safe error envelope. |
| FR-API-02 | The frontend never acts as an authorization authority; the backend enforces every protected operation. |
| FR-OPS-01 | Configuration and secrets come from environment-based settings with safe validation and no committed secret values. |
| FR-OPS-02 | The MVP deploys one backend process, one PostgreSQL database, and one frontend build; same-origin production delivery is preferred. |
| FR-OPS-03 | `GET /health/live` reports process liveness without database access; `GET /health/ready` checks database connectivity and returns only safe status detail. |
| FR-OPS-04 | Development prefers Vite proxies for `/api`, `/health`, and `/ws`; any credentialed CORS uses explicit origins and never `*`. Production is same-origin where practical. |

## 6. Non-functional requirements

| ID | Requirement / measurable evidence |
|---|---|
| NFR-MNT-01 | Backend modules separate identity, rooms, messaging, persistence, HTTP, and WebSocket concerns; tests map to requirement IDs. |
| NFR-REL-01 | Database transactions preserve room-owner and message-persistence invariants; failures do not broadcast uncommitted messages. |
| NFR-SEC-01 | Protected routes and sockets authenticate server-side and authorize against current membership. |
| NFR-SEC-02 | Production uses HTTPS/WSS, Secure and HttpOnly cookies, origin allowlists, CSRF controls, safe logs, and parameterized ORM queries. |
| NFR-DATA-01 | PostgreSQL constraints enforce primary/foreign keys, identity uniqueness, membership uniqueness, and valid content/roles. |
| NFR-PERF-01 | Lists are paginated and message history uses an indexed cursor query; no unmeasured concurrency claim is made. |
| NFR-UX-01 | Main controls are keyboard-operable, labeled, focus-visible, and usable at common mobile and desktop widths. |
| NFR-PORT-01 | Development remains practical on the stated laptop; Kubernetes, microservices, Redis, Kafka, and Elasticsearch are excluded. |
| NFR-CONF-01 | Startup fails clearly when required configuration is missing; test configuration refuses production database targets. |
| NFR-OBS-01 | Structured logs include request/event context without passwords, tokens, message bodies, or unnecessary personal data. |
| NFR-REP-01 | Documented commands reproduce setup, migrations, checks, tests, and deployment after dependency compatibility is verified. |

## 7. MVP scope

The MVP includes registration; login/logout; secure sessions; basic profiles; public room discovery and creation; many-to-many membership; owner/member permissions; persistent messages; real-time WebSockets; cursor history; validation; consistent errors; responsive UI; automated backend, database, API, WebSocket, and frontend tests; one-instance deployment; and technical documentation.

## 8. Original baseline and later implemented expansion

The original Task 1 baseline deferred AI summarization/search, private rooms, invitations, typing indicators, receipts, presence, and notifications. Those capabilities were subsequently authorized, implemented, and locally verified through the complete-backend and frontend milestones. Gemini-backed summaries, durable embedding jobs, bounded room-scoped semantic search, private-room invitations, typing/presence/read events, and persistent notifications are therefore part of the current application, even though they were outside the initial educational MVP.

Local LLMs, ownership transfer, moderators, message edit/delete, push notifications, Redis, Kafka, microservices, Kubernetes, Elasticsearch, and multi-process real-time fan-out remain deferred. AI stays disabled by default and is not approved for real-user processing until the provider/privacy decision is complete.

## 9. Constraints, assumptions, and open decisions

- Compatibility baseline remains Python 3.12 and Node.js 24. Local verification uses Python 3.13.14 and Node.js 24.22.3 while preserving the declared Python 3.12 compatibility baseline.
- Proposed stack: FastAPI, native WebSockets, SQLAlchemy 2.x async access, Alembic, PostgreSQL, React, TypeScript, Vite, Tailwind CSS, Pytest, Vitest, React Testing Library, Ruff, ESLint, and TypeScript checking.
- The architecture is a modular monolith and the real-time connection registry is process-local; the MVP therefore runs one backend process.
- Public and private rooms are implemented. Public discovery excludes private rooms, and every conversation operation remains membership-authorized.
- Recommended session lifetime is seven days from creation, configurable. This balances convenience and stolen-cookie exposure without refresh-token complexity.
- **APPROVED decision:** owner-controlled room deletion permanently removes live room, membership, and message rows. Provider backup retention is separate and cannot be promised as immediate deletion.
- Package pins, cookie/CSRF transport, and process-local operational limits are implemented and documented. Hosting has been researched but not selected or provisioned; staging remains an owner decision.

## 10. Acceptance criteria

The MVP is acceptable when automated tests demonstrate all identified requirements, including this end-to-end scenario: Alice and Bob join “Python Lounge”; Rehan does not. Alice sends a message; PostgreSQL commits it before Bob receives it; Rehan cannot connect or read history; after reconnecting, Bob retrieves the persisted message. Migrations apply to a clean test database, unauthorized paths fail safely, the frontend exposes required states, deployment is reproducible, known limitations are documented, and no critical security finding remains unresolved.

The six Task 1 documents themselves are accepted only after project-owner review confirms consistent membership, ownership, deletion, session, API, WebSocket, security, and roadmap decisions.

## 11. Current implementation status

As of 2026-11-17, the integrated application is IMPLEMENTED and locally VERIFIED: identity, sessions, public/private rooms, invitations, persistent messaging/history/search, authenticated WebSockets, read/typing/presence events, notifications, Gemini-backed summaries, profiled durable embeddings, bounded semantic search, and the responsive React client. Both local PostgreSQL databases are at `20261117_0003` without detected drift. Current evidence is 93 backend tests and 17 Vitest tests; three PostgreSQL-backed Playwright scenarios are preserved prior browser evidence and were not rerun after server-only AI changes. AI remains disabled by default; live Gemini quality is NOT RUN; controlled staging is conditional, and public production is unauthorized/unrun. Specifications remain draft pending owner review.
## AI evaluation and privacy requirements (implemented 2026-11-17)

Normal messaging is independent of AI. Disabled AI creates no automatic embedding backlog. New-message indexing and owner-controlled historical backfill require separate explicit configuration. Stored vectors are compatible only within a provider/model/dimension/profile version. Semantic responses disclose active-profile indexing and candidate-window truncation. Synthetic evaluation must remain reproducible without a provider key, while any live model-quality run is explicit, synthetic-only, dated, and never inferred from mocks.
